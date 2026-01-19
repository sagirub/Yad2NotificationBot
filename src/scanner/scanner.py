"""
Item Scanner Module v2

This module scans all user searches for new Yad2 listings and sends
notifications when new items are found.

Rate Limiting Strategy:
- Maximum 3 requests per run
- Initial scan: 3 pages (uses full budget)
- Regular scan: 1 page (leaves spare requests for API fallback)

Detection Strategy:
1. Compare item IDs with stored IDs to find potentially new items
2. Extract createdAt from image URL (no extra API call needed)
3. Fall back to API call only if image URL parsing fails
4. Verify item is truly new by comparing createdAt with last_scan_time
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from src.config import settings
from src.yad2.parser import Yad2Parser, Yad2Item
from src.bot.db.dynamodb import get_all_searches, update_search_scan_results
from src.scanner.notifier import TelegramNotifier
from src.scanner.stats import ScanStats, save_stats

logger = logging.getLogger(__name__)


class ItemScanner:
    """
    Scanner that checks all user searches for new items.
    
    The scanner uses an optimized detection strategy with rate limiting:
    - Initial scan: 3 pages to build comprehensive item ID cache
    - Regular scan: 1 page (newest items appear first)
    - API fallback: Use spare requests when image URL has no timestamp
    """
    
    def __init__(
        self,
        notifier: Optional[TelegramNotifier] = None,
        max_pages_initial: int = None,
        max_pages_regular: int = None,
        max_stored_ids: int = None,
    ):
        """
        Initialize the scanner.
        
        Args:
            notifier: TelegramNotifier instance (creates default if not provided)
            max_pages_initial: Pages to scan on initial run (default from settings)
            max_pages_regular: Pages to scan on regular runs (default from settings)
            max_stored_ids: Maximum item IDs to store per search (default from settings)
        """
        self.parser = Yad2Parser(track_stats=True)
        self.notifier = notifier or TelegramNotifier()
        self.max_pages_initial = max_pages_initial or settings.MAX_PAGES_INITIAL
        self.max_pages_regular = max_pages_regular or settings.MAX_PAGES_REGULAR
        self.max_stored_ids = max_stored_ids or settings.MAX_STORED_IDS
        self.stats = ScanStats()
    
    async def scan_all_searches(self) -> Dict[str, Any]:
        """
        Scan all searches for new items.
        
        Returns:
            Summary of scan results including stats
        """
        logger.info("Starting scan of all searches")
        self.stats = ScanStats()
        self.stats.start()
        
        try:
            searches = await get_all_searches()
            logger.info(f"Found {len(searches)} searches to scan")
            
            for search in searches:
                try:
                    await self._scan_single_search(search)
                    self.stats.add_search_scanned()
                except Exception as e:
                    error_msg = f"Error scanning search {search.get('id')}: {str(e)}"
                    self.stats.add_error(error_msg)
                    logger.error(error_msg, exc_info=True)
            
            logger.info(
                f"Scan complete: {self.stats.searches_scanned} searches, "
                f"{self.stats.items_found} new items found"
            )
            
        except Exception as e:
            error_msg = f"Error fetching searches: {str(e)}"
            self.stats.add_error(error_msg)
            logger.error(error_msg, exc_info=True)
        
        self.stats.finish()
        
        # Save stats to DynamoDB
        await save_stats(self.stats)
        
        # Send admin notification if configured
        if settings.ADMIN_CHAT_ID and settings.SEND_RUN_SUMMARY:
            await self._send_admin_summary()
        
        return self.stats.to_dict()
    
    async def _send_admin_summary(self):
        """Send run summary to admin chat."""
        try:
            summary = self.stats.format_summary()
            await self.notifier.send_admin_message(summary)
            
            # Check for alerts
            alerts = self.stats.check_alerts(
                block_threshold=settings.ALERT_BLOCK_RATE_THRESHOLD,
                error_threshold=settings.ALERT_ERROR_RATE_THRESHOLD,
            )
            
            for alert in alerts:
                await self.notifier.send_admin_message(alert)
                
        except Exception as e:
            logger.error(f"Failed to send admin summary: {e}")
    
    async def _scan_single_search(self, search: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scan a single search for new items using optimized createdAt-based detection.
        
        Strategy:
        1. Determine if this is initial or regular scan
        2. Fetch items from appropriate number of pages
        3. Find items not in stored IDs (potentially new)
        4. Check createdAt from image URL (already extracted during parsing)
        5. Fall back to API call only if image URL parsing failed
        6. Verify item is truly new by comparing createdAt with last_scan_time
        
        Args:
            search: Search dictionary from DynamoDB
            
        Returns:
            Scan result with new items count and notifications sent
        """
        scan_time = datetime.now(timezone.utc)
        
        search_id = search.get("id")
        user_id = search.get("user_id")
        search_name = search.get("name", "Unknown")
        search_link = search.get("link")
        last_item_ids = set(search.get("last_item_ids", []))
        is_initial_scan_complete = search.get("is_initial_scan_complete", False)
        
        # Get last_scan_time from search (if available)
        last_scan_time = None
        last_scan_time_str = search.get("last_scanned_at")
        if last_scan_time_str:
            try:
                last_scan_time = datetime.fromisoformat(last_scan_time_str)
                if last_scan_time.tzinfo is None:
                    last_scan_time = last_scan_time.replace(tzinfo=timezone.utc)
            except ValueError:
                logger.warning(f"Invalid last_scan_time format for search {search_id}")
        
        # Determine scan type
        is_initial_scan = not is_initial_scan_complete or len(last_item_ids) == 0
        max_pages = self.max_pages_initial if is_initial_scan else self.max_pages_regular
        
        logger.info(
            f"Scanning search '{search_name}' (ID: {search_id}) for user {user_id}, "
            f"initial_scan={is_initial_scan}, max_pages={max_pages}"
        )
        
        result = {
            "search_id": search_id,
            "new_items_count": 0,
            "notifications_sent": 0,
            "is_initial_scan": is_initial_scan,
        }
        
        # Fetch current items from Yad2 (with pagination)
        items = self.parser.get_items_paginated(search_link, max_pages=max_pages)
        
        # Update request stats from parser
        parser_stats = self.parser.get_stats()
        self.stats.requests_success += parser_stats.get("search_requests_success", 0)
        self.stats.requests_failed += parser_stats.get("search_requests_failed", 0)
        self.stats.requests_blocked += parser_stats.get("search_requests_blocked", 0)
        self.parser.reset_stats()
        
        if not items:
            logger.warning(f"No items fetched for search '{search_name}'")
            return result
        
        current_item_ids = {item.id for item in items}
        
        # Find potentially new items (items not in stored IDs)
        potentially_new_ids = current_item_ids - last_item_ids
        
        verified_new_items: List[Yad2Item] = []
        
        if potentially_new_ids:
            if is_initial_scan:
                # First scan - just store IDs, don't verify or notify
                logger.info(
                    f"Initial scan for '{search_name}', storing {len(current_item_ids)} item IDs (no notifications)"
                )
            else:
                # Not first scan - verify each potentially new item using createdAt
                logger.info(f"Found {len(potentially_new_ids)} potentially new items, verifying...")
                
                # Track API calls used for fallback
                api_calls_used = 0
                max_api_calls = settings.MAX_REQUESTS_PER_RUN - max_pages  # Spare requests
                
                for item in items:
                    if item.id in potentially_new_ids:
                        # Check if we already have createdAt from image URL
                        if item.created_at is not None and item.created_at_source == "image_url":
                            # Already have createdAt from image URL - no API call needed!
                            if item.is_newer_than(last_scan_time):
                                verified_new_items.append(item)
                                self.stats.add_detection_by_image()
                                logger.info(f"Verified new item (from image URL): {item.id}")
                            else:
                                logger.debug(f"Item {item.id} is not new (created: {item.created_at})")
                        elif api_calls_used < max_api_calls:
                            # No createdAt from image URL - fall back to API call
                            logger.debug(f"Item {item.id} has no createdAt from image URL, using API fallback")
                            self.parser.enrich_item_with_created_at(item)
                            api_calls_used += 1
                            
                            # Update API request stats
                            parser_stats = self.parser.get_stats()
                            if parser_stats.get("item_requests_success", 0) > 0:
                                self.stats.add_request_success()
                            elif parser_stats.get("item_requests_blocked", 0) > 0:
                                self.stats.add_request_blocked()
                            elif parser_stats.get("item_requests_failed", 0) > 0:
                                self.stats.add_request_failed()
                            self.parser.reset_stats()
                            
                            # Check if truly new based on createdAt
                            if item.created_at is None:
                                logger.warning(f"Could not verify item {item.id} - no createdAt found")
                            elif item.is_newer_than(last_scan_time):
                                verified_new_items.append(item)
                                self.stats.add_detection_by_api()
                                logger.info(f"Verified new item (from API): {item.id}")
                            else:
                                logger.debug(f"Item {item.id} is not new (created: {item.created_at})")
                        else:
                            logger.debug(f"Skipping API fallback for {item.id} - request budget exhausted")
        else:
            logger.info(f"No new items for search '{search_name}'")
        
        # Send notifications for verified new items
        if verified_new_items:
            result["new_items_count"] = len(verified_new_items)
            self.stats.add_items_found(len(verified_new_items))
            logger.info(f"Sending notification for {len(verified_new_items)} verified new items")
            
            try:
                await self.notifier.notify_new_items(
                    chat_id=user_id,
                    search_name=search_name,
                    items=verified_new_items,
                )
                result["notifications_sent"] = 1
                self.stats.add_notification_sent()
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
                self.stats.add_error(f"Notification failed: {str(e)}")
        
        # Update last scan results in DynamoDB
        # Merge current items with previous items (keep track of all seen items)
        all_item_ids = list(last_item_ids.union(current_item_ids))
        
        # Limit stored item IDs to prevent unbounded growth
        if len(all_item_ids) > self.max_stored_ids:
            all_item_ids = all_item_ids[-self.max_stored_ids:]
        
        await update_search_scan_results(
            user_id=user_id,
            search_id=search_id,
            item_ids=all_item_ids,
            is_initial_scan_complete=True if is_initial_scan else None,
        )
        
        return result
    
    def scan_all_searches_sync(self) -> Dict[str, Any]:
        """
        Synchronous wrapper for scan_all_searches.
        
        Returns:
            Summary of scan results
        """
        return asyncio.get_event_loop().run_until_complete(self.scan_all_searches())


def scan_new_items() -> Dict[str, Any]:
    """
    Main entry point for scanning new items.
    
    Returns:
        Summary of scan results
    """
    scanner = ItemScanner()
    return scanner.scan_all_searches_sync()