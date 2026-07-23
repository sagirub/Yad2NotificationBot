"""
Scanner Orchestrator Module

This module provides the orchestrator Lambda that splits searches into batches
and invokes worker Lambdas to process them. This helps avoid rate limiting
by distributing requests across multiple Lambda instances (different IPs).

Batching Strategy:
    Searches are batched by estimated request count (not search count).
    Each worker gets a budget of MAX_REQUESTS_PER_WORKER requests.
    This ensures no single worker triggers Yad2's bot protection by
    making too many sequential requests from the same IP.

Architecture:
    CloudWatch Event (every 30 min)
            ↓
    Orchestrator Lambda (this module)
            ↓  estimates requests per search, packs into budget-based batches
    ├── Worker Lambda 1 (budget: 5 requests) → Different IP
    ├── Worker Lambda 2 (budget: 5 requests) → Different IP
    └── Worker Lambda N (remaining)          → Different IP
            ↓
    Orchestrator aggregates results and sends single notification
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import boto3


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types from DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            # Convert to int if it's a whole number, otherwise float
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)

from src.config import settings
from src.bot.db.dynamodb import get_all_searches
from src.scanner.notifier import TelegramNotifier
from src.scanner.scanner import ItemScanner

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Israel timezone
ISRAEL_TZ = ZoneInfo(settings.TIMEZONE)

# Configuration
# Maximum estimated requests a single worker Lambda should make.
# Yad2 typically blocks after ~5-6 rapid requests from the same IP/session.
MAX_REQUESTS_PER_WORKER = int(os.environ.get("MAX_REQUESTS_PER_WORKER", "5"))
WORKER_FUNCTION_NAME = os.environ.get("WORKER_FUNCTION_NAME", "")

# Items per page on Yad2 (used for estimating page count)
ITEMS_PER_PAGE = settings.ITEMS_PER_PAGE
# Max safe pages before reclassification (must match scanner.py)
MAX_SAFE_PAGES = ItemScanner.MAX_SAFE_PAGES


def is_within_scan_hours() -> bool:
    """
    Check if current time is within allowed scan hours (Israel timezone).
    
    Returns:
        True if current time is between SCAN_START_HOUR and SCAN_END_HOUR
    """
    now_israel = datetime.now(ISRAEL_TZ)
    current_hour = now_israel.hour
    
    # Handle the case where end hour is 24 (midnight)
    if settings.SCAN_END_HOUR == 24:
        return current_hour >= settings.SCAN_START_HOUR
    else:
        return settings.SCAN_START_HOUR <= current_hour < settings.SCAN_END_HOUR


def estimate_requests(search: Dict[str, Any]) -> int:
    """
    Estimate the number of HTTP requests a search will need.
    
    For initial scans:
      - Small searches: pages needed to fetch all items (capped at MAX_SAFE_PAGES)
      - Large searches: MAX_PAGES_INITIAL (default 3)
    For regular scans:
      - 1 page (newest items appear first on page 1)
    
    Args:
        search: Search dictionary from DynamoDB
        
    Returns:
        Estimated number of requests
    """
    is_initial_scan_complete = search.get("is_initial_scan_complete", False)
    last_item_ids = search.get("last_item_ids", [])
    is_initial = not is_initial_scan_complete or len(last_item_ids) == 0
    
    if not is_initial:
        # Regular scan: just 1 page
        return 1
    
    # Initial scan: estimate pages needed
    total_items = search.get("total_items")
    is_small_search = search.get("is_small_search")
    
    if is_small_search and total_items is not None:
        # Small search: pages needed to build complete ID bank
        pages_needed = (int(total_items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        pages_needed = max(pages_needed + 1, 2)  # +1 buffer
        
        if pages_needed > MAX_SAFE_PAGES:
            # Will be reclassified as large by scanner
            return settings.MAX_PAGES_INITIAL
        return pages_needed
    elif is_small_search:
        # Small search without total_items
        return min(MAX_SAFE_PAGES, (settings.SMALL_SEARCH_THRESHOLD // ITEMS_PER_PAGE) + 2)
    else:
        # Large search or unknown
        return settings.MAX_PAGES_INITIAL


def batch_by_request_budget(
    searches: List[Dict[str, Any]],
    max_requests: int,
) -> List[List[Dict[str, Any]]]:
    """
    Pack searches into batches based on estimated request budget.
    
    Each batch will have a total estimated request count ≤ max_requests.
    This ensures no single worker Lambda makes too many requests from one IP.
    
    Args:
        searches: List of search dictionaries
        max_requests: Maximum estimated requests per batch
        
    Returns:
        List of batches, where each batch is a list of search dictionaries
    """
    batches: List[List[Dict[str, Any]]] = []
    current_batch: List[Dict[str, Any]] = []
    current_budget = 0
    
    for search in searches:
        est = estimate_requests(search)
        search_name = search.get("name", "unknown")
        
        # If this single search exceeds the budget, give it its own batch
        if est >= max_requests:
            # Flush current batch if non-empty
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_budget = 0
            batches.append([search])
            logger.info(
                f"Search '{search_name}' needs ~{est} requests, "
                f"assigned to its own batch"
            )
            continue
        
        # If adding this search would exceed budget, start a new batch
        if current_budget + est > max_requests:
            batches.append(current_batch)
            current_batch = []
            current_budget = 0
        
        current_batch.append(search)
        current_budget += est
        logger.debug(f"Search '{search_name}': ~{est} requests, batch budget: {current_budget}/{max_requests}")
    
    # Don't forget the last batch
    if current_batch:
        batches.append(current_batch)
    
    return batches


async def get_searches_for_scanning() -> List[Dict[str, Any]]:
    """Get all searches that need to be scanned."""
    return await get_all_searches()


def invoke_worker_sync(lambda_client, batch: List[Dict], batch_index: int) -> Dict[str, Any]:
    """
    Invoke a worker Lambda synchronously and wait for results.
    
    Args:
        lambda_client: Boto3 Lambda client
        batch: List of search dictionaries
        batch_index: Index of this batch (for logging)
        
    Returns:
        Worker results including stats
    """
    payload = {
        "searches": batch,
        "batch_index": batch_index,
        "send_notification": False,  # Orchestrator will send centralized notification
    }
    
    logger.info(f"Invoking worker for batch {batch_index} with {len(batch)} searches")
    
    response = lambda_client.invoke(
        FunctionName=WORKER_FUNCTION_NAME,
        InvocationType="RequestResponse",  # Synchronous - wait for response
        Payload=json.dumps(payload, cls=DecimalEncoder),
    )
    
    # Parse response
    response_payload = json.loads(response["Payload"].read().decode("utf-8"))
    
    # Extract results from response body
    if response_payload.get("statusCode") == 200:
        body = json.loads(response_payload.get("body", "{}"))
        return {
            "batch_index": batch_index,
            "search_count": len(batch),
            "status_code": response.get("StatusCode"),
            "results": body.get("results", {}),
            "success": True,
        }
    else:
        return {
            "batch_index": batch_index,
            "search_count": len(batch),
            "status_code": response.get("StatusCode"),
            "error": response_payload.get("body", "Unknown error"),
            "success": False,
        }


def aggregate_stats(worker_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate stats from all workers into a single summary.
    
    Args:
        worker_results: List of results from each worker
        
    Returns:
        Aggregated stats dictionary
    """
    aggregated = {
        "searches_scanned": 0,
        "items_found": 0,
        "notifications_sent": 0,
        "requests_success": 0,
        "requests_failed": 0,
        "requests_blocked": 0,
        "detection_by_image": 0,
        "detection_by_api": 0,
        "duration_seconds": 0,
        "lambda_gb_seconds": 0,
        "blocked_searches": [],
        "errors": [],
        "batch_count": len(worker_results),
        "successful_batches": 0,
        "failed_batches": 0,
    }
    
    for result in worker_results:
        if result.get("success"):
            aggregated["successful_batches"] += 1
            stats = result.get("results", {})
            
            aggregated["searches_scanned"] += stats.get("searches_scanned", 0)
            aggregated["items_found"] += stats.get("items_found", 0)
            aggregated["notifications_sent"] += stats.get("notifications_sent", 0)
            aggregated["requests_success"] += stats.get("requests_success", 0)
            aggregated["requests_failed"] += stats.get("requests_failed", 0)
            aggregated["requests_blocked"] += stats.get("requests_blocked", 0)
            aggregated["detection_by_image"] += stats.get("detection_by_image", 0)
            aggregated["detection_by_api"] += stats.get("detection_by_api", 0)
            aggregated["duration_seconds"] += stats.get("duration_seconds", 0)
            aggregated["lambda_gb_seconds"] += stats.get("lambda_gb_seconds", 0)
            
            # Collect blocked searches
            blocked = stats.get("blocked_searches", [])
            if blocked:
                aggregated["blocked_searches"].extend(blocked)
            
            # Collect errors
            errors = stats.get("errors", [])
            if errors:
                aggregated["errors"].extend(errors)
        else:
            aggregated["failed_batches"] += 1
            aggregated["errors"].append(f"Batch {result.get('batch_index')} failed: {result.get('error', 'Unknown')}")
    
    return aggregated


def format_centralized_summary(stats: Dict[str, Any], duration_total: float) -> str:
    """
    Format aggregated stats as a Telegram message.
    
    Args:
        stats: Aggregated stats dictionary
        duration_total: Total orchestrator duration in seconds
        
    Returns:
        Formatted string for Telegram notification
    """
    lines = [
        "🔍 *Scanner Run Complete*",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"📊 Searches: {stats['searches_scanned']} scanned",
        f"🆕 New Items: {stats['items_found']} found",
        f"📨 Notifications: {stats['notifications_sent']} sent",
        f"✅ Requests: {stats['requests_success']} success / {stats['requests_failed'] + stats['requests_blocked']} failed",
        f"⏱️ Total Duration: {duration_total:.1f}s",
        "",
        f"📦 *Batches:* {stats['successful_batches']}/{stats['batch_count']} successful",
    ]
    
    # Add Lambda usage info
    if stats['lambda_gb_seconds'] > 0:
        lines.append(f"☁️ *Lambda:* {stats['lambda_gb_seconds']:.4f} GB-seconds")
    
    # Add detection breakdown if items were found
    if stats['items_found'] > 0:
        lines.append("")
        lines.append("📍 *Detection Method:*")
        lines.append(f"  • Image URL: {stats['detection_by_image']}")
        lines.append(f"  • API Call: {stats['detection_by_api']}")
    
    # Add warnings if there are issues
    if stats['requests_blocked'] > 0:
        lines.append("")
        lines.append(f"⚠️ *Warning:* {stats['requests_blocked']} requests blocked")
        if stats['blocked_searches']:
            lines.append("🚫 *Blocked Searches:*")
            for search_name in stats['blocked_searches'][:5]:
                lines.append(f"  • {search_name}")
    
    if stats['errors']:
        lines.append("")
        lines.append(f"❌ *Errors:* {len(stats['errors'])}")
        for error in stats['errors'][:3]:
            lines.append(f"  • {str(error)[:50]}...")
    
    return "\n".join(lines)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Orchestrator Lambda handler.
    
    This function:
    1. Checks if we're within scan hours
    2. Fetches all searches from DynamoDB
    3. Estimates request count per search
    4. Packs searches into batches by request budget (MAX_REQUESTS_PER_WORKER)
    5. Invokes worker Lambdas for each batch (synchronously)
    6. Aggregates results and sends a single centralized notification
    
    Args:
        event: Lambda event (from CloudWatch Events)
        context: Lambda context
        
    Returns:
        Response with orchestration results
    """
    start_time = datetime.now(ISRAEL_TZ)
    logger.info("Orchestrator Lambda triggered")
    logger.info(f"Event: {json.dumps(event)}")
    
    # Get current Israel time for logging
    now_israel = datetime.now(ISRAEL_TZ)
    logger.info(f"Current Israel time: {now_israel.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Check if we're within scan hours
    if not is_within_scan_hours():
        logger.info(
            f"Outside scan hours ({settings.SCAN_START_HOUR}:00 - {settings.SCAN_END_HOUR}:00 Israel time). "
            f"Current hour: {now_israel.hour}. Skipping scan."
        )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Scan skipped - outside scan hours",
                "current_hour_israel": now_israel.hour,
                "scan_hours": f"{settings.SCAN_START_HOUR}:00 - {settings.SCAN_END_HOUR}:00",
            }),
        }
    
    # Check if worker function is configured
    if not WORKER_FUNCTION_NAME:
        logger.error("WORKER_FUNCTION_NAME not configured")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Configuration error",
                "error": "WORKER_FUNCTION_NAME not set",
            }),
        }
    
    try:
        # Get all searches
        searches = asyncio.get_event_loop().run_until_complete(get_searches_for_scanning())
        
        if not searches:
            logger.info("No searches to scan")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "No searches to scan",
                    "israel_time": now_israel.isoformat(),
                }),
            }
        
        logger.info(f"Found {len(searches)} searches to scan")
        
        # Log estimated requests per search
        for s in searches:
            est = estimate_requests(s)
            logger.info(
                f"Search '{s.get('name', 'unknown')}': "
                f"~{est} estimated requests "
                f"(initial={not s.get('is_initial_scan_complete', False) or len(s.get('last_item_ids', [])) == 0}, "
                f"total_items={s.get('total_items')}, "
                f"is_small={s.get('is_small_search')})"
            )
        
        # Split into batches by request budget
        batches = batch_by_request_budget(searches, MAX_REQUESTS_PER_WORKER)
        
        # Log batch composition
        for i, batch in enumerate(batches):
            batch_est = sum(estimate_requests(s) for s in batch)
            names = [s.get("name", "unknown") for s in batch]
            logger.info(
                f"Batch {i}: {len(batch)} searches, ~{batch_est} estimated requests: {names}"
            )
        
        logger.info(
            f"Split into {len(batches)} batches "
            f"(max {MAX_REQUESTS_PER_WORKER} requests per worker)"
        )
        
        # Invoke worker Lambdas synchronously and collect results
        lambda_client = boto3.client("lambda")
        worker_results = []
        
        for i, batch in enumerate(batches):
            result = invoke_worker_sync(lambda_client, batch, i)
            worker_results.append(result)
            logger.info(f"Batch {i} completed: success={result.get('success')}")
        
        # Aggregate stats from all workers
        aggregated_stats = aggregate_stats(worker_results)
        
        # Calculate total duration
        end_time = datetime.now(ISRAEL_TZ)
        total_duration = (end_time - start_time).total_seconds()
        
        logger.info(
            f"All batches complete: {aggregated_stats['searches_scanned']} searches, "
            f"{aggregated_stats['items_found']} new items, {total_duration:.1f}s total"
        )
        
        # Send urgent admin alert if scanner appears fully blocked
        # This is sent as a separate, prominent message BEFORE the regular summary
        # so it's impossible to miss when Yad2 blocks the entire AWS region.
        if settings.ADMIN_CHAT_ID:
            try:
                total_requests = (
                    aggregated_stats['requests_success']
                    + aggregated_stats['requests_blocked']
                    + aggregated_stats['requests_failed']
                )
                # Critical: 100% blocked AND we tried at least some requests
                if total_requests > 0 and aggregated_stats['requests_blocked'] == total_requests:
                    region = os.environ.get('AWS_REGION_NAME') or os.environ.get('AWS_REGION', 'unknown')
                    urgent_alert = (
                        "🚨🚨🚨 *SCANNER COMPLETELY BLOCKED* 🚨🚨🚨\n\n"
                        f"All `{total_requests}` requests blocked by Yad2!\n"
                        f"Region: `{region}`\n"
                        f"Searches affected: `{aggregated_stats['searches_scanned']}`\n"
                        f"Batches: `{aggregated_stats['successful_batches']}/{aggregated_stats['batch_count']}` workers ran\n\n"
                        "⚠️ *Action required:*\n"
                        "Yad2 likely added this AWS region to their IP blocklist.\n"
                        "Migration to a different region is needed.\n\n"
                        "_This alert is sent every run until resolved._"
                    )
                    notifier_alert = TelegramNotifier()
                    asyncio.get_event_loop().run_until_complete(
                        notifier_alert.send_admin_message(urgent_alert)
                    )
                    logger.warning(f"CRITICAL: Scanner fully blocked in region {region}! Sent urgent admin alert.")
            except Exception as alert_error:
                logger.error(f"Failed to send urgent blocked alert: {alert_error}")
        
        # Send centralized admin notification (regular summary)
        if settings.ADMIN_CHAT_ID and settings.SEND_RUN_SUMMARY:
            try:
                notifier = TelegramNotifier()
                summary_message = format_centralized_summary(aggregated_stats, total_duration)
                asyncio.get_event_loop().run_until_complete(
                    notifier.send_admin_message(summary_message)
                )
                logger.info("Sent centralized admin notification")
            except Exception as notify_error:
                logger.error(f"Failed to send admin notification: {notify_error}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Scan completed successfully",
                "total_searches": len(searches),
                "batch_count": len(batches),
                "max_requests_per_worker": MAX_REQUESTS_PER_WORKER,
                "aggregated_stats": aggregated_stats,
                "total_duration_seconds": total_duration,
                "israel_time": now_israel.isoformat(),
            }, cls=DecimalEncoder),
        }
        
    except Exception as e:
        logger.error(f"Orchestrator error: {e}", exc_info=True)
        
        # Send error notification to admin
        try:
            notifier = TelegramNotifier()
            asyncio.get_event_loop().run_until_complete(
                notifier.send_admin_message(f"🚨 Orchestrator Error: {str(e)}")
            )
        except Exception as notify_error:
            logger.error(f"Failed to send error notification: {notify_error}")
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Orchestrator failed",
                "error": str(e),
                "israel_time": now_israel.isoformat(),
            }),
        }