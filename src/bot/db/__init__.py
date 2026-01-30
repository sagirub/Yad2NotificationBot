"""
Database layer for user searches.

Uses DynamoDB in production (AWS Lambda) and mock_db for local development.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Check if we're running in AWS Lambda or locally
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
USE_DYNAMODB = IS_LAMBDA or os.environ.get("USE_DYNAMODB", "").lower() == "true"

logger.info(f"DB Init: IS_LAMBDA={IS_LAMBDA}, USE_DYNAMODB={USE_DYNAMODB}, LAMBDA_FUNC={os.environ.get('AWS_LAMBDA_FUNCTION_NAME')}")

if USE_DYNAMODB:
    logger.info("Using DynamoDB for database")
    # Use DynamoDB in production
    from src.bot.db.dynamodb import (
        get_searches,
        add_search,
        delete_search,
        get_search_by_id,
        update_search_scan_results,
        get_all_searches,
        get_total_search_count,
    )
else:
    logger.info("Using mock_db for database (local development)")
    # Use mock database for local development
    from src.bot.db.mock_db import (
        get_searches,
        add_search,
        delete_search,
    )
    
    # Provide stub implementations for functions not in mock_db
    async def get_search_by_id(user_id: str, search_id: str):
        """Stub for local development."""
        searches = await get_searches(user_id)
        for search in searches:
            if search["id"] == search_id:
                return search
        return None
    
    async def update_search_scan_results(user_id: str, search_id: str, item_ids: list):
        """Stub for local development."""
        return True
    
    async def get_all_searches():
        """Stub for local development."""
        from src.bot.db.mock_db import MOCK_DB
        all_searches = []
        for user_id, searches in MOCK_DB.items():
            for search in searches:
                all_searches.append({**search, "user_id": user_id})
        return all_searches
    
    async def get_total_search_count():
        """Stub for local development."""
        from src.bot.db.mock_db import MOCK_DB
        return sum(len(searches) for searches in MOCK_DB.values())

__all__ = [
    "get_searches",
    "add_search",
    "delete_search",
    "get_search_by_id",
    "update_search_scan_results",
    "get_all_searches",
    "get_total_search_count",
]