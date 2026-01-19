"""
DynamoDB database layer for user searches and scanner stats.

Searches Table Schema:
- user_id (HASH key): Telegram user ID as string
- search_id (RANGE key): UUID for the search
- name: User-friendly name for the search
- link: Yad2 search URL
- created_at: ISO timestamp when search was created
- last_scanned_at: ISO timestamp of last scan (optional)
- last_item_ids: List of item IDs from last scan (for detecting new items)
- is_initial_scan_complete: Boolean indicating if 3-page initial scan is done

Stats Table Schema:
- stat_date (HASH key): Date in YYYY-MM-DD format
- stat_hour (RANGE key): Hour in HH format (00-23)
- searches_scanned: Number of searches processed
- items_found: New items detected
- notifications_sent: Successful notifications
- requests_success: Successful Yad2 requests
- requests_failed: Failed requests
- requests_blocked: Blocked by captcha/bot protection
- detection_by_image: Items detected via image URL
- detection_by_api: Items detected via API call
- ttl: TTL timestamp for auto-deletion (7 days)
"""

import os
import uuid
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Get table names from environment
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "yad2-notification-bot-dev-searches")
STATS_TABLE_NAME = os.environ.get("STATS_TABLE", "yad2-notification-bot-dev-stats")
STATS_RETENTION_DAYS = int(os.environ.get("STATS_RETENTION_DAYS", "7"))

# Initialize DynamoDB resource
# Use local endpoint for local development if specified
_dynamodb = None


def get_dynamodb_resource():
    """Get or create DynamoDB resource."""
    global _dynamodb
    if _dynamodb is None:
        endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
        if endpoint_url:
            # Local development with DynamoDB Local
            _dynamodb = boto3.resource(
                "dynamodb",
                endpoint_url=endpoint_url,
                region_name=os.environ.get("AWS_REGION", "eu-central-1"),
            )
        else:
            # AWS DynamoDB
            _dynamodb = boto3.resource(
                "dynamodb",
                region_name=os.environ.get("AWS_REGION", "eu-central-1"),
            )
    return _dynamodb


def get_table():
    """Get the searches DynamoDB table."""
    dynamodb = get_dynamodb_resource()
    return dynamodb.Table(TABLE_NAME)


def get_stats_table():
    """Get the stats DynamoDB table."""
    dynamodb = get_dynamodb_resource()
    return dynamodb.Table(STATS_TABLE_NAME)


async def get_searches(user_id: str) -> List[Dict[str, Any]]:
    """
    Fetches all searches for a user.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        List of search dictionaries with id, name, link, created_at
    """
    try:
        table = get_table()
        response = table.query(
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": str(user_id)},
        )
        
        searches = []
        for item in response.get("Items", []):
            searches.append({
                "id": item.get("search_id"),
                "name": item.get("name"),
                "link": item.get("link"),
                "created_at": item.get("created_at"),
                "last_scanned_at": item.get("last_scanned_at"),
            })
        
        return searches
        
    except ClientError as e:
        logger.error(f"Error fetching searches for user {user_id}: {e}")
        return []


async def add_search(user_id: str, name: str, link: str) -> Dict[str, Any]:
    """
    Adds a new search for a user.
    
    Args:
        user_id: Telegram user ID
        name: User-friendly name for the search
        link: Yad2 search URL
        
    Returns:
        The created search dictionary
    """
    search_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()
    
    item = {
        "user_id": str(user_id),
        "search_id": search_id,
        "name": name,
        "link": link,
        "created_at": created_at,
        "last_scanned_at": None,
        "last_item_ids": [],
        "is_initial_scan_complete": False,
    }
    
    try:
        table = get_table()
        table.put_item(Item=item)
        
        logger.info(f"Added search '{name}' for user {user_id}")
        
        return {
            "id": search_id,
            "name": name,
            "link": link,
            "created_at": created_at,
        }
        
    except ClientError as e:
        logger.error(f"Error adding search for user {user_id}: {e}")
        raise


async def delete_search(user_id: str, search_id: str) -> Optional[Dict[str, Any]]:
    """
    Deletes a search by its ID.
    
    Args:
        user_id: Telegram user ID
        search_id: UUID of the search to delete
        
    Returns:
        The deleted search dictionary, or None if not found
    """
    try:
        table = get_table()
        
        # First get the item to return it
        response = table.get_item(
            Key={
                "user_id": str(user_id),
                "search_id": search_id,
            }
        )
        
        item = response.get("Item")
        if not item:
            return None
        
        # Delete the item
        table.delete_item(
            Key={
                "user_id": str(user_id),
                "search_id": search_id,
            }
        )
        
        logger.info(f"Deleted search '{item.get('name')}' for user {user_id}")
        
        return {
            "id": item.get("search_id"),
            "name": item.get("name"),
            "link": item.get("link"),
        }
        
    except ClientError as e:
        logger.error(f"Error deleting search {search_id} for user {user_id}: {e}")
        return None


async def get_search_by_id(user_id: str, search_id: str) -> Optional[Dict[str, Any]]:
    """
    Gets a single search by its ID.
    
    Args:
        user_id: Telegram user ID
        search_id: UUID of the search
        
    Returns:
        The search dictionary, or None if not found
    """
    try:
        table = get_table()
        response = table.get_item(
            Key={
                "user_id": str(user_id),
                "search_id": search_id,
            }
        )
        
        item = response.get("Item")
        if not item:
            return None
            
        return {
            "id": item.get("search_id"),
            "name": item.get("name"),
            "link": item.get("link"),
            "created_at": item.get("created_at"),
            "last_scanned_at": item.get("last_scanned_at"),
            "last_item_ids": item.get("last_item_ids", []),
            "is_initial_scan_complete": item.get("is_initial_scan_complete", False),
        }
        
    except ClientError as e:
        logger.error(f"Error getting search {search_id} for user {user_id}: {e}")
        return None


async def update_search_scan_results(
    user_id: str,
    search_id: str,
    item_ids: List[str],
    is_initial_scan_complete: bool = None,
) -> bool:
    """
    Updates a search with the latest scan results.
    
    Args:
        user_id: Telegram user ID
        search_id: UUID of the search
        item_ids: List of item IDs from the latest scan
        is_initial_scan_complete: If provided, update the initial scan flag
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        table = get_table()
        
        update_expr = "SET last_scanned_at = :ts, last_item_ids = :ids"
        expr_values = {
            ":ts": datetime.now(timezone.utc).isoformat(),
            ":ids": item_ids,
        }
        
        if is_initial_scan_complete is not None:
            update_expr += ", is_initial_scan_complete = :isc"
            expr_values[":isc"] = is_initial_scan_complete
        
        table.update_item(
            Key={
                "user_id": str(user_id),
                "search_id": search_id,
            },
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
        return True
        
    except ClientError as e:
        logger.error(f"Error updating scan results for search {search_id}: {e}")
        return False


async def get_all_searches() -> List[Dict[str, Any]]:
    """
    Gets all searches from all users (for the scanner job).
    
    Returns:
        List of all search dictionaries with user_id included
    """
    try:
        table = get_table()
        response = table.scan()
        
        searches = []
        for item in response.get("Items", []):
            searches.append({
                "user_id": item.get("user_id"),
                "id": item.get("search_id"),
                "name": item.get("name"),
                "link": item.get("link"),
                "created_at": item.get("created_at"),
                "last_scanned_at": item.get("last_scanned_at"),
                "last_item_ids": item.get("last_item_ids", []),
                "is_initial_scan_complete": item.get("is_initial_scan_complete", False),
            })
        
        # Handle pagination if there are more items
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            for item in response.get("Items", []):
                searches.append({
                    "user_id": item.get("user_id"),
                    "id": item.get("search_id"),
                    "name": item.get("name"),
                    "link": item.get("link"),
                    "created_at": item.get("created_at"),
                    "last_scanned_at": item.get("last_scanned_at"),
                    "last_item_ids": item.get("last_item_ids", []),
                    "is_initial_scan_complete": item.get("is_initial_scan_complete", False),
                })
        
        return searches
        
    except ClientError as e:
        logger.error(f"Error scanning all searches: {e}")
        return []


# ============================================================================
# Stats Table Functions
# ============================================================================

async def save_scan_stats(stats: Dict[str, Any]) -> bool:
    """
    Save scanner run statistics to the stats table.
    
    Args:
        stats: Dictionary containing scan statistics
        
    Returns:
        True if save was successful, False otherwise
    """
    try:
        table = get_stats_table()
        now = datetime.now(timezone.utc)
        
        # Calculate TTL (7 days from now)
        ttl = int((now + timedelta(days=STATS_RETENTION_DAYS)).timestamp())
        
        item = {
            "stat_date": now.strftime("%Y-%m-%d"),
            "stat_hour": now.strftime("%H"),
            "timestamp": now.isoformat(),
            "searches_scanned": stats.get("searches_scanned", 0),
            "items_found": stats.get("items_found", 0),
            "notifications_sent": stats.get("notifications_sent", 0),
            "requests_success": stats.get("requests_success", 0),
            "requests_failed": stats.get("requests_failed", 0),
            "requests_blocked": stats.get("requests_blocked", 0),
            "detection_by_image": stats.get("detection_by_image", 0),
            "detection_by_api": stats.get("detection_by_api", 0),
            "duration_seconds": stats.get("duration_seconds", 0),
            "ttl": ttl,
        }
        
        table.put_item(Item=item)
        logger.info(f"Saved scan stats for {now.strftime('%Y-%m-%d %H:%M')}")
        return True
        
    except ClientError as e:
        logger.error(f"Error saving scan stats: {e}")
        return False


async def get_stats_for_date(date_str: str) -> List[Dict[str, Any]]:
    """
    Get all stats for a specific date.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        
    Returns:
        List of stats records for that date
    """
    try:
        table = get_stats_table()
        response = table.query(
            KeyConditionExpression="stat_date = :date",
            ExpressionAttributeValues={":date": date_str},
        )
        return response.get("Items", [])
        
    except ClientError as e:
        logger.error(f"Error fetching stats for {date_str}: {e}")
        return []


async def get_stats_summary(days: int = 1) -> Dict[str, Any]:
    """
    Get aggregated stats summary for the last N days.
    
    Args:
        days: Number of days to include (default: 1 = today only)
        
    Returns:
        Aggregated stats dictionary
    """
    try:
        table = get_stats_table()
        now = datetime.now(timezone.utc)
        
        summary = {
            "total_searches_scanned": 0,
            "total_items_found": 0,
            "total_notifications_sent": 0,
            "total_requests_success": 0,
            "total_requests_failed": 0,
            "total_requests_blocked": 0,
            "total_detection_by_image": 0,
            "total_detection_by_api": 0,
            "total_runs": 0,
            "period_days": days,
        }
        
        for i in range(days):
            date = now - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            
            response = table.query(
                KeyConditionExpression="stat_date = :date",
                ExpressionAttributeValues={":date": date_str},
            )
            
            for item in response.get("Items", []):
                summary["total_searches_scanned"] += int(item.get("searches_scanned", 0))
                summary["total_items_found"] += int(item.get("items_found", 0))
                summary["total_notifications_sent"] += int(item.get("notifications_sent", 0))
                summary["total_requests_success"] += int(item.get("requests_success", 0))
                summary["total_requests_failed"] += int(item.get("requests_failed", 0))
                summary["total_requests_blocked"] += int(item.get("requests_blocked", 0))
                summary["total_detection_by_image"] += int(item.get("detection_by_image", 0))
                summary["total_detection_by_api"] += int(item.get("detection_by_api", 0))
                summary["total_runs"] += 1
        
        # Calculate rates
        total_requests = summary["total_requests_success"] + summary["total_requests_failed"] + summary["total_requests_blocked"]
        if total_requests > 0:
            summary["success_rate"] = round(summary["total_requests_success"] / total_requests * 100, 1)
            summary["block_rate"] = round(summary["total_requests_blocked"] / total_requests * 100, 1)
            summary["error_rate"] = round(summary["total_requests_failed"] / total_requests * 100, 1)
        else:
            summary["success_rate"] = 0
            summary["block_rate"] = 0
            summary["error_rate"] = 0
        
        return summary
        
    except ClientError as e:
        logger.error(f"Error fetching stats summary: {e}")
        return {}


async def get_latest_stats(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the most recent stats records.
    
    Args:
        limit: Maximum number of records to return
        
    Returns:
        List of recent stats records
    """
    try:
        table = get_stats_table()
        now = datetime.now(timezone.utc)
        
        all_items = []
        
        # Query last 2 days to ensure we get enough records
        for i in range(2):
            date = now - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            
            response = table.query(
                KeyConditionExpression="stat_date = :date",
                ExpressionAttributeValues={":date": date_str},
                ScanIndexForward=False,  # Descending order
            )
            all_items.extend(response.get("Items", []))
        
        # Sort by timestamp descending and limit
        all_items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return all_items[:limit]
        
    except ClientError as e:
        logger.error(f"Error fetching latest stats: {e}")
        return []