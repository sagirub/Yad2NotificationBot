"""
DynamoDB database layer for user searches.

Table Schema:
- user_id (HASH key): Telegram user ID as string
- search_id (RANGE key): UUID for the search
- name: User-friendly name for the search
- link: Yad2 search URL
- created_at: ISO timestamp when search was created
- last_scanned_at: ISO timestamp of last scan (optional)
- last_item_ids: List of item IDs from last scan (for detecting new items)
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Get table name from environment
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "yad2-notification-bot-dev-searches")

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
    """Get the DynamoDB table."""
    dynamodb = get_dynamodb_resource()
    return dynamodb.Table(TABLE_NAME)


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
        }
        
    except ClientError as e:
        logger.error(f"Error getting search {search_id} for user {user_id}: {e}")
        return None


async def update_search_scan_results(
    user_id: str, 
    search_id: str, 
    item_ids: List[str]
) -> bool:
    """
    Updates a search with the latest scan results.
    
    Args:
        user_id: Telegram user ID
        search_id: UUID of the search
        item_ids: List of item IDs from the latest scan
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        table = get_table()
        table.update_item(
            Key={
                "user_id": str(user_id),
                "search_id": search_id,
            },
            UpdateExpression="SET last_scanned_at = :ts, last_item_ids = :ids",
            ExpressionAttributeValues={
                ":ts": datetime.utcnow().isoformat(),
                ":ids": item_ids,
            },
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
                })
        
        return searches
        
    except ClientError as e:
        logger.error(f"Error scanning all searches: {e}")
        return []