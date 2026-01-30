"""
Scanner Orchestrator Module

This module provides the orchestrator Lambda that splits searches into batches
and invokes worker Lambdas to process them. This helps avoid rate limiting
by distributing requests across multiple Lambda instances (different IPs).

Architecture:
    CloudWatch Event (every 30 min)
            ↓
    Orchestrator Lambda (this module)
            ↓
    ├── Worker Lambda 1 (searches 1-3) → Different IP
    ├── Worker Lambda 2 (searches 4-6) → Different IP
    └── Worker Lambda N (remaining)    → Different IP
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

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Israel timezone
ISRAEL_TZ = ZoneInfo(settings.TIMEZONE)

# Configuration
BATCH_SIZE = int(os.environ.get("SCANNER_BATCH_SIZE", "3"))
WORKER_FUNCTION_NAME = os.environ.get("WORKER_FUNCTION_NAME", "")


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


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """Split a list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


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
    3. Splits searches into batches of BATCH_SIZE
    4. Invokes worker Lambdas for each batch (synchronously)
    5. Aggregates results and sends a single centralized notification
    
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
        
        # Split into batches
        batches = chunk_list(searches, BATCH_SIZE)
        logger.info(f"Split into {len(batches)} batches of max {BATCH_SIZE} searches each")
        
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
        
        # Send centralized admin notification
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
                "batch_size": BATCH_SIZE,
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