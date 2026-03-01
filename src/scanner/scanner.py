"""
Item Scanner Module v2

This module scans all user searches for new Yad2 listings and sends
notifications when new items are found.

Rate Limiting Strategy:
- Maximum 3 requests per run
- Initial scan: 3 pages (uses full budget)
- Regular scan: 1 page (leaves spare requests for API fallback)

Detection Strategy (based on search size):

1. SMALL SEARCHES (≤ SMALL_SEARCH_THRESHOLD items):
   - Uses ID-bank-only detection
   - Any item not in the stored ID bank is considered new
   - Faster and simpler, no createdAt verification needed
   - Works well because all items fit in the ID bank

2. LARGE SEARCHES (> SMALL_SEARCH_THRESHOLD items):
   - Uses hybrid detection (ID bank + createdAt verification)
   - Compare item IDs with stored IDs to find potentially new items
   - Extract createdAt from image URL (no extra API call needed)
   - Fall back to API call only if image URL parsing fails
   - Verify item is truly new by comparing createdAt with last_scan_time
   - Necessary because items may rotate out of the ID bank
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from src.config import settings
from src.yad2.parser import Yad2Parser, Yad2Item, SearchResult
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
    
    # Maximum pages we can safely fetch in sequence without triggering bot protection
    # If a "small" search needs more pages than this, we reclassify it as "large"
    # so it uses hybrid detection (createdAt verification) instead of ID-bank-only
    MAX_SAFE_PAGES = 5
    
    def __init__(
        self,
        notifier: Optional[TelegramNotifier] = None,
        max_pages_initial: int = None,
        max_pages_regular: int = None,
        max_stored_ids: int = None,
        small_search_threshold: int = None,
        items_per_page: int = None,
        page_request_delay: float = None,
    ):
        """
        Initialize the scanner.
        
        Args:
            notifier: TelegramNotifier instance (creates default if not provided)
            max_pages_initial: Pages to scan on initial run for large searches (default from settings)
            max_pages_regular: Pages to scan on regular runs (default from settings)
            max_stored_ids: Maximum item IDs to store per search (default from settings)
            small_search_threshold: Threshold for small vs large search detection strategy
            items_per_page: Approximate items per Yad2 page (for calculating pages needed)
            page_request_delay: Delay in seconds between page requests (default from settings)
        """
        self.parser = Yad2Parser(track_stats=True)
        self.notifier = notifier or TelegramNotifier()
        self.max_pages_initial = max_pages_initial or settings.MAX_PAGES_INITIAL
        self.max_pages_regular = max_pages_regular or settings.MAX_PAGES_REGULAR
        self.max_stored_ids = max_stored_ids or settings.MAX_STORED_IDS
        self.small_search_threshold = small_search_threshold or settings.SMALL_SEARCH_THRESHOLD
        self.items_per_page = items_per_page or settings.ITEMS_PER_PAGE
        self.page_request_delay = page_request_delay if page_request_delay is not None else settings.PAGE_REQUEST_DELAY
        self.stats = ScanStats()
    
    async def scan_all_searches(self, lambda_context=None) -> Dict[str, Any]:
        """
        Scan all searches for new items.
        
        Args:
            lambda_context: AWS Lambda context object (optional) for tracking usage
        
        Returns:
            Summary of scan results including stats
        """
        logger.info("Starting scan of all searches")
        self.stats = ScanStats()
        self.stats.start()
        self._lambda_context = lambda_context
        
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
        
        self.stats.finish(context=self._lambda_context)
        
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
        Scan a single search for new items using size-based detection strategy.
        
        Strategy depends on search size:
        - Small searches (≤ threshold): ID-bank-only detection, fetch ALL pages on initial scan
        - Large searches (> threshold): Hybrid detection with createdAt verification
        
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
        stored_total_items = search.get("total_items")
        is_small_search = search.get("is_small_search")
        exclude_commercial = search.get("exclude_commercial", False)
        
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
        
        result = {
            "search_id": search_id,
            "new_items_count": 0,
            "notifications_sent": 0,
            "is_initial_scan": is_initial_scan,
        }
        
        # Fetch first page to get total_results and determine search size
        first_page_result = self.parser.get_search_result(search_link)
        total_results = first_page_result.total_results
        items = list(first_page_result.items)
        
        # Determine if this is a small search (for detection strategy and page count)
        # Use stored value if available, otherwise calculate from total_results
        if is_small_search is None:
            if total_results is not None:
                is_small_search = total_results <= self.small_search_threshold
            else:
                # Fallback: estimate based on items fetched
                is_small_search = len(items) <= self.small_search_threshold
        
        # Determine max pages based on scan type and search size
        if is_initial_scan:
            if is_small_search and total_results is not None:
                # Small search initial scan: fetch pages to build ID bank
                # Calculate pages needed: ceil(total_results / items_per_page)
                pages_needed = (total_results + self.items_per_page - 1) // self.items_per_page
                # Add 1 extra page as buffer (in case new items were added)
                pages_needed = max(pages_needed + 1, 2)
                
                if pages_needed > self.MAX_SAFE_PAGES:
                    # Too many pages to safely fetch — reclassify as "large" search
                    # Large searches use hybrid detection (createdAt verification)
                    # which only needs a few pages and won't trigger bot protection
                    logger.info(
                        f"Search '{search_name}' needs {pages_needed} pages but max safe is "
                        f"{self.MAX_SAFE_PAGES} — reclassifying as large search "
                        f"(will use hybrid detection with createdAt verification)"
                    )
                    is_small_search = False
                    max_pages = self.max_pages_initial
                else:
                    max_pages = pages_needed
                    logger.info(
                        f"Small search '{search_name}' initial scan: fetching {max_pages} pages "
                        f"to build complete ID bank (total_results={total_results})"
                    )
            elif is_small_search:
                # Small search but no total_results - use a reasonable default
                max_pages = min(self.MAX_SAFE_PAGES, (self.small_search_threshold // self.items_per_page) + 2)
                logger.info(
                    f"Small search '{search_name}' initial scan: fetching up to {max_pages} pages "
                    f"(no total_results available)"
                )
            else:
                # Large search initial scan: use standard initial pages
                max_pages = self.max_pages_initial
        else:
            # Regular scan: just first page (newest items appear first)
            max_pages = self.max_pages_regular
        
        logger.info(
            f"Scanning search '{search_name}' (ID: {search_id}) for user {user_id}, "
            f"initial_scan={is_initial_scan}, max_pages={max_pages}, "
            f"is_small_search={is_small_search}, total_items={total_results or stored_total_items}, "
            f"exclude_commercial={exclude_commercial}"
        )
        
        # Fetch additional pages if needed
        # Track whether all pages were successfully fetched (for initial scan completion)
        pages_fetched = 1  # First page already fetched
        all_pages_successful = True  # Assume success until proven otherwise
        reached_end_naturally = False  # True if we stopped because no more items
        
        if max_pages > 1 and items:
            seen_ids = {item.id for item in items}
            for page in range(2, max_pages + 1):
                # Add delay between page requests to avoid bot detection
                if self.page_request_delay > 0:
                    logger.debug(f"Waiting {self.page_request_delay}s before fetching page {page}")
                    await asyncio.sleep(self.page_request_delay)
                
                if "?" in search_link:
                    page_url = f"{search_link}&page={page}"
                else:
                    page_url = f"{search_link}?page={page}"
                
                page_items = self.parser.get_items(page_url)
                if not page_items:
                    # Check if this was a block or natural end
                    parser_stats = self.parser.get_stats()
                    if parser_stats.get("search_requests_blocked", 0) > 0:
                        logger.warning(f"Page {page} was blocked, initial scan incomplete")
                        all_pages_successful = False
                    else:
                        logger.info(f"No items on page {page}, reached end of results")
                        reached_end_naturally = True
                    break
                
                pages_fetched += 1
                new_items_count = 0
                for item in page_items:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        items.append(item)
                        new_items_count += 1
                
                logger.debug(f"Page {page}: {len(page_items)} items, {new_items_count} new unique")
                
                # Stop if we got fewer items than expected (reached end)
                if len(page_items) < 20:
                    logger.info(f"Fewer items than expected on page {page}, reached end of results")
                    reached_end_naturally = True
                    break
        
        # Update request stats from parser
        parser_stats = self.parser.get_stats()
        self.stats.requests_success += parser_stats.get("search_requests_success", 0)
        self.stats.requests_failed += parser_stats.get("search_requests_failed", 0)
        
        # Track blocked requests with search name
        blocked_count = parser_stats.get("search_requests_blocked", 0)
        if blocked_count > 0:
            for _ in range(blocked_count):
                self.stats.add_request_blocked(search_name)
            # Reset the HTTP session to prevent a blocked session from
            # poisoning all subsequent searches in this batch
            logger.warning(
                f"Search '{search_name}' was blocked {blocked_count} times, "
                f"resetting HTTP session for next search"
            )
            self.parser.reset_session()
        
        self.parser.reset_stats()
        
        if not items:
            logger.warning(f"No items fetched for search '{search_name}'")
            return result
        
        # Collect ALL item IDs before filtering (for the ID bank)
        # The ID bank must track all items regardless of commercial filter,
        # otherwise filtered-out items would be re-detected as "new" every scan
        all_fetched_item_ids = {item.id for item in items}
        
        # Filter out commercial items if requested (only affects notifications)
        # Uses feed_source (which section the item appears in) rather than ad_type,
        # because ad_type="commercial" just means the seller is a dealer, while
        # feed_source="commercial" means it's a promoted dealer listing section.
        # Items in the "private" feed section can still be from dealers (ad_type=commercial)
        # but they appear as regular listings on the website.
        if exclude_commercial:
            original_count = len(items)
            items = [item for item in items if item.feed_source not in ("commercial",)]
            filtered_count = original_count - len(items)
            if filtered_count > 0:
                logger.info(
                    f"Search '{search_name}': filtered out {filtered_count} commercial-section items "
                    f"({original_count} -> {len(items)})"
                )
        
        current_item_ids = {item.id for item in items}
        
        logger.info(
            f"Search '{search_name}': fetched {len(items)} items, "
            f"is_small_search={is_small_search}, threshold={self.small_search_threshold}"
        )
        
        # Find potentially new items (items not in stored IDs)
        potentially_new_ids = current_item_ids - last_item_ids
        
        verified_new_items: List[Yad2Item] = []
        
        if potentially_new_ids:
            if is_initial_scan:
                # First scan - just store IDs, don't verify or notify
                logger.info(
                    f"Initial scan for '{search_name}', storing {len(current_item_ids)} item IDs (no notifications)"
                )
            elif is_small_search:
                # SMALL SEARCH STRATEGY: ID-bank-only detection
                # Any item not in the stored ID bank is considered new
                logger.info(
                    f"Small search '{search_name}': using ID-bank-only detection for "
                    f"{len(potentially_new_ids)} new items"
                )
                for item in items:
                    if item.id in potentially_new_ids:
                        verified_new_items.append(item)
                        # Track as detected by ID bank
                        self.stats.add_detection_by_id_bank()
                        logger.info(f"New item (ID-bank detection): {item.id}")
            else:
                # LARGE SEARCH STRATEGY: Hybrid detection with createdAt verification
                # Verify each potentially new item using createdAt
                logger.info(
                    f"Large search '{search_name}': using hybrid detection for "
                    f"{len(potentially_new_ids)} potentially new items"
                )
                
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
                                self.stats.add_request_blocked(search_name)
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
        # Merge ALL fetched items (including commercial) with previous items
        # This ensures the ID bank tracks everything, preventing re-detection
        all_item_ids = list(last_item_ids.union(all_fetched_item_ids))
        
        # Limit stored item IDs to prevent unbounded growth
        if len(all_item_ids) > self.max_stored_ids:
            all_item_ids = all_item_ids[-self.max_stored_ids:]
        
        # Determine if initial scan is truly complete
        # For small searches: must have fetched all pages OR reached end naturally
        # For large searches: always mark as complete (uses hybrid detection anyway)
        initial_scan_complete = False
        if is_initial_scan:
            if is_small_search:
                # Small search: only complete if all pages fetched or reached end naturally
                initial_scan_complete = all_pages_successful and (pages_fetched >= max_pages or reached_end_naturally)
                if not initial_scan_complete:
                    logger.warning(
                        f"Initial scan for '{search_name}' incomplete: "
                        f"fetched {pages_fetched}/{max_pages} pages, "
                        f"all_successful={all_pages_successful}, reached_end={reached_end_naturally}"
                    )
                else:
                    logger.info(
                        f"Initial scan for '{search_name}' complete: "
                        f"fetched {pages_fetched} pages, {len(current_item_ids)} items in ID bank"
                    )
            else:
                # Large search: always mark as complete (uses hybrid detection)
                initial_scan_complete = True
        
        # Update search with scan results and metadata
        await update_search_scan_results(
            user_id=user_id,
            search_id=search_id,
            item_ids=all_item_ids,
            is_initial_scan_complete=initial_scan_complete if is_initial_scan else None,
            total_items=total_results if is_initial_scan and total_results else None,
            is_small_search=is_small_search if is_initial_scan else None,
        )
        
        return result
    
    def scan_all_searches_sync(self, lambda_context=None) -> Dict[str, Any]:
        """
        Synchronous wrapper for scan_all_searches.
        
        Args:
            lambda_context: AWS Lambda context object (optional) for tracking usage
        
        Returns:
            Summary of scan results
        """
        return asyncio.get_event_loop().run_until_complete(self.scan_all_searches(lambda_context))
    
    async def scan_batch(
        self,
        searches: List[Dict[str, Any]],
        batch_index: int = 0,
        lambda_context=None,
        send_admin_summary: bool = True,
    ) -> Dict[str, Any]:
        """
        Scan a specific batch of searches (for worker Lambda).
        
        This method is used by the worker Lambda to process a subset of searches
        that were assigned by the orchestrator.
        
        Args:
            searches: List of search dictionaries to scan
            batch_index: Index of this batch (for logging)
            lambda_context: AWS Lambda context for tracking usage
            send_admin_summary: Whether to send admin notification
        
        Returns:
            Summary of scan results including stats
        """
        logger.info(f"Starting batch {batch_index} scan with {len(searches)} searches")
        self.stats = ScanStats()
        self.stats.start()
        self._lambda_context = lambda_context
        
        for search in searches:
            try:
                await self._scan_single_search(search)
                self.stats.add_search_scanned()
            except Exception as e:
                error_msg = f"Error scanning search {search.get('id')}: {str(e)}"
                self.stats.add_error(error_msg)
                logger.error(error_msg, exc_info=True)
        
        logger.info(
            f"Batch {batch_index} complete: {self.stats.searches_scanned} searches, "
            f"{self.stats.items_found} new items found"
        )
        
        self.stats.finish(context=self._lambda_context)
        
        # Save stats to DynamoDB
        await save_stats(self.stats)
        
        # Send admin notification if configured
        if send_admin_summary and settings.ADMIN_CHAT_ID and settings.SEND_RUN_SUMMARY:
            await self._send_admin_summary()
        
        return self.stats.to_dict()
    
    def scan_batch_sync(
        self,
        searches: List[Dict[str, Any]],
        batch_index: int = 0,
        lambda_context=None,
        send_admin_summary: bool = True,
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for scan_batch.
        
        Args:
            searches: List of search dictionaries to scan
            batch_index: Index of this batch (for logging)
            lambda_context: AWS Lambda context for tracking usage
            send_admin_summary: Whether to send admin notification
        
        Returns:
            Summary of scan results
        """
        return asyncio.get_event_loop().run_until_complete(
            self.scan_batch(searches, batch_index, lambda_context, send_admin_summary)
        )


def scan_new_items() -> Dict[str, Any]:
    """
    Main entry point for scanning new items.
    
    Returns:
        Summary of scan results
    """
    scanner = ItemScanner()
    return scanner.scan_all_searches_sync()