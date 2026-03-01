"""
Yad2 Parser Module

This module provides functionality to fetch and parse Yad2 search results
by extracting embedded JSON data from the HTML page (__NEXT_DATA__).

The legacy API (feed-search-legacy) is deprecated and returns 404.
This parser uses the HTML page approach which works reliably.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib import parse

import requests
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Yad2 constants
ITEM_BASE_URL = "https://www.yad2.co.il/item/"
YAD2_NETLOC = "www.yad2.co.il"

# Browser-like headers to avoid bot detection
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,he;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


# Israel timezone for date handling
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


def extract_datetime_from_image_url(image_url: str) -> Optional[datetime]:
    """
    Extract creation datetime from Yad2 image URL.
    
    Image URLs contain timestamps in the filename, e.g.:
    https://img.yad2.co.il/Pic/202601/06/1_8/o/y2_1pa_010653_20260106114053.jpeg
    
    The timestamp format is: YYYYMMDDHHMMSS (e.g., 20260106114053 = 2026-01-06 11:40:53)
    
    Args:
        image_url: The image URL to parse
        
    Returns:
        datetime object or None if parsing fails
    """
    if not image_url:
        return None
    
    try:
        # Pattern to match timestamp in image filename
        # Matches: _YYYYMMDDHHMMSS. (14 digits followed by a dot)
        pattern = r'_(\d{14})\.'
        match = re.search(pattern, image_url)
        
        if match:
            timestamp_str = match.group(1)
            # Parse: YYYYMMDDHHMMSS
            dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
            # Assume Israel timezone
            return dt.replace(tzinfo=ISRAEL_TZ)
        
        # Alternative pattern for XML-style images: xml_N_ORDERID_YYYYMMDDHHMMSS.jpg
        # e.g., xml_1_9956015616_20251031011019.jpg
        pattern2 = r'xml_\d+_\d+_(\d{14})\.'
        match2 = re.search(pattern2, image_url)
        
        if match2:
            timestamp_str = match2.group(1)
            dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
            return dt.replace(tzinfo=ISRAEL_TZ)
        
        return None
        
    except (ValueError, AttributeError) as e:
        logger.debug(f"Failed to extract datetime from image URL '{image_url}': {e}")
        return None


@dataclass
class SearchResult:
    """Result of a Yad2 search including items and metadata."""
    
    items: List["Yad2Item"]
    total_results: Optional[int] = None  # Total items in search (from API)
    current_page: int = 1
    
    def __len__(self) -> int:
        return len(self.items)
    
    def __iter__(self):
        return iter(self.items)


@dataclass
class Yad2Item:
    """Represents a single Yad2 listing item."""
    
    id: str  # token - unique identifier
    order_id: int  # orderId - for ordering
    title: str
    price: Optional[int]
    link: str
    image_url: Optional[str] = None
    location: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    hand: Optional[str] = None
    ad_type: str = "private"  # adType field from Yad2 (commercial = dealer, private = individual)
    feed_source: str = "private"  # Which feed section the item came from (platinum, boost, solo, commercial, private)
    created_at: Optional[datetime] = None  # Extracted from image URL or item detail page
    created_at_source: str = "unknown"  # "image_url", "api", or "unknown"
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_next_data(cls, item_data: dict, feed_source: str = "private") -> Optional["Yad2Item"]:
        """
        Create a Yad2Item from __NEXT_DATA__ item.
        
        Attempts to extract created_at from image URL to avoid extra API calls.
        
        Args:
            item_data: Raw item data from __NEXT_DATA__
            feed_source: Which feed section this item came from (platinum, boost, solo, commercial, private)
            
        Returns:
            Yad2Item instance or None if data is invalid
        """
        try:
            token = item_data.get("token")
            if not token:
                return None
            
            order_id = item_data.get("orderId", 0)
            
            # Build title from manufacturer, model, year
            manufacturer = item_data.get("manufacturer", {})
            model = item_data.get("model", {})
            sub_model = item_data.get("subModel", {})
            vehicle_dates = item_data.get("vehicleDates", {})
            
            manufacturer_text = manufacturer.get("text", "")
            model_text = model.get("text", "")
            year = vehicle_dates.get("yearOfProduction")
            
            # Build title
            title_parts = [p for p in [manufacturer_text, model_text, str(year) if year else None] if p]
            title = " ".join(title_parts) if title_parts else "ללא כותרת"
            
            # Get price
            price = item_data.get("price")
            
            # Get image and try to extract created_at from it
            metadata = item_data.get("metaData", {})
            image_url = metadata.get("coverImage")
            images = metadata.get("images", [])
            
            # Try to extract created_at from image URL
            created_at = None
            created_at_source = "unknown"
            
            # First try cover image
            if image_url:
                created_at = extract_datetime_from_image_url(image_url)
                if created_at:
                    created_at_source = "image_url"
            
            # If cover image failed, try first image in the list
            if not created_at and images:
                for img_url in images[:3]:  # Try first 3 images
                    created_at = extract_datetime_from_image_url(img_url)
                    if created_at:
                        created_at_source = "image_url"
                        break
            
            # Get location
            address = item_data.get("address", {})
            area = address.get("area", {})
            location = area.get("text")
            
            # Get hand
            hand_data = item_data.get("hand", {})
            hand = hand_data.get("text")
            
            # Get ad type
            ad_type = item_data.get("adType", "private")
            
            return cls(
                id=token,
                order_id=order_id,
                title=title,
                price=price,
                link=f"{ITEM_BASE_URL}{token}",
                image_url=image_url,
                location=location,
                manufacturer=manufacturer_text,
                model=model_text,
                year=year,
                hand=hand,
                ad_type=ad_type,
                feed_source=feed_source,
                created_at=created_at,
                created_at_source=created_at_source,
                raw_data=item_data,
            )
        except Exception as e:
            logger.warning(f"Failed to parse item data: {e}")
            return None
    
    def format_price(self) -> str:
        """Format price for display."""
        if self.price is None:
            return "לא צוין מחיר"
        return f"₪{self.price:,}"
    
    def is_newer_than(self, reference_time: datetime, assume_new_if_unknown: bool = False) -> bool:
        """
        Check if this item was created after the reference time.
        
        Args:
            reference_time: The reference datetime (should be timezone-aware)
            assume_new_if_unknown: If True, assume new when created_at is unknown.
                                   If False (default), assume NOT new when unknown.
            
        Returns:
            True if item was created after reference_time, False otherwise.
        """
        if self.created_at is None:
            return assume_new_if_unknown
        
        # Ensure both times are timezone-aware for comparison
        item_time = self.created_at
        if item_time.tzinfo is None:
            # Assume Israel timezone if not specified
            item_time = item_time.replace(tzinfo=ISRAEL_TZ)
        
        ref_time = reference_time
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        
        return item_time > ref_time


class Yad2Parser:
    """Parser for Yad2 search results using HTML page scraping."""
    
    def __init__(
        self,
        timeout: int = 30,
        track_stats: bool = False,
        request_delay: float = 0.5,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
    ):
        """
        Initialize the parser.
        
        Args:
            timeout: Request timeout in seconds
            track_stats: If True, track request statistics
            request_delay: Delay between requests in seconds (default: 0.5s)
                          Set to 0 to disable delays
            max_retries: Maximum number of retries for blocked requests (default: 3)
            retry_base_delay: Base delay for exponential backoff in seconds (default: 2.0s)
                             Actual delay = retry_base_delay * (2 ^ attempt)
        """
        self.timeout = timeout
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.last_request_time: float = 0
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
        self.track_stats = track_stats
        self.reset_stats()
    
    def reset_session(self):
        """
        Create a fresh HTTP session, discarding any cookies/state from the old one.
        
        This is useful when the current session has been flagged/blocked by
        Yad2's bot protection — subsequent requests on a blocked session will
        keep failing even if the IP isn't actually blocked.
        """
        old_session = self.session
        try:
            old_session.close()
        except Exception:
            pass
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
        self.last_request_time = 0
        logger.info("HTTP session reset (cleared cookies/state)")
    
    def _wait_for_rate_limit(self):
        """Wait if needed to respect rate limiting."""
        if self.request_delay <= 0:
            return
        
        # Always wait at least the delay between requests
        # (except for the very first request)
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.request_delay:
                sleep_time = self.request_delay - elapsed
                logger.info(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def reset_stats(self):
        """Reset request statistics."""
        self.stats = {
            "search_requests_success": 0,
            "search_requests_failed": 0,
            "search_requests_blocked": 0,
            "search_requests_retried": 0,
            "item_requests_success": 0,
            "item_requests_failed": 0,
            "item_requests_blocked": 0,
            "item_requests_no_dates": 0,
            "item_requests_retried": 0,
        }
    
    def get_stats(self) -> Dict[str, int]:
        """Get current request statistics."""
        return self.stats.copy()
    
    def get_items(self, search_url: str, retry_count: int = 0) -> List[Yad2Item]:
        """
        Fetch items from a Yad2 search URL with retry on blocking.
        
        Args:
            search_url: The Yad2 search URL
            retry_count: Current retry attempt (internal use)
            
        Returns:
            List of Yad2Item objects
        """
        result = self.get_search_result(search_url, retry_count)
        return result.items
    
    def get_search_result(self, search_url: str, retry_count: int = 0) -> SearchResult:
        """
        Fetch items and metadata from a Yad2 search URL with retry on blocking.
        
        Args:
            search_url: The Yad2 search URL
            retry_count: Current retry attempt (internal use)
            
        Returns:
            SearchResult with items and total_results count
        """
        logger.info(f"Fetching items from: {search_url}" + (f" (retry {retry_count})" if retry_count > 0 else ""))
        
        try:
            # Wait for rate limit before making request
            self._wait_for_rate_limit()
            
            # Fetch the HTML page
            response = self.session.get(search_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Check for bot protection
            if self._is_blocked(response.text):
                logger.warning(f"Request blocked by bot protection (attempt {retry_count + 1}/{self.max_retries + 1})")
                
                # Retry with exponential backoff if we haven't exceeded max retries
                if retry_count < self.max_retries:
                    # Calculate delay: base_delay * 2^retry_count (e.g., 2s, 4s, 8s)
                    delay = self.retry_base_delay * (2 ** retry_count)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    
                    if self.track_stats:
                        self.stats["search_requests_retried"] += 1
                    
                    # Retry the request
                    return self.get_search_result(search_url, retry_count + 1)
                else:
                    logger.error(f"Max retries ({self.max_retries}) exceeded, giving up")
                    if self.track_stats:
                        self.stats["search_requests_blocked"] += 1
                    return SearchResult(items=[])
            
            # Extract __NEXT_DATA__
            next_data = self._extract_next_data(response.text)
            if not next_data:
                logger.error("Could not find __NEXT_DATA__ in page")
                if self.track_stats:
                    self.stats["search_requests_failed"] += 1
                return SearchResult(items=[])
            
            # Parse items and metadata from the data
            items, total_results = self._parse_items_with_metadata(next_data)
            
            if self.track_stats:
                self.stats["search_requests_success"] += 1
            
            logger.info(f"Found {len(items)} items (total in search: {total_results})")
            return SearchResult(items=items, total_results=total_results)
            
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            if self.track_stats:
                self.stats["search_requests_failed"] += 1
            return SearchResult(items=[])
        except Exception as e:
            logger.error(f"Error fetching items: {e}")
            if self.track_stats:
                self.stats["search_requests_failed"] += 1
            return SearchResult(items=[])
    
    def get_items_paginated(self, search_url: str, max_pages: int = 3) -> List[Yad2Item]:
        """
        Fetch items from multiple pages of a Yad2 search.
        
        Args:
            search_url: The Yad2 search URL
            max_pages: Maximum number of pages to fetch (default: 3)
            
        Returns:
            List of Yad2Item objects from all pages
        """
        all_items: List[Yad2Item] = []
        seen_ids: set[str] = set()
        
        for page in range(1, max_pages + 1):
            # Add page parameter to URL
            if "?" in search_url:
                page_url = f"{search_url}&page={page}"
            else:
                page_url = f"{search_url}?page={page}"
            
            logger.info(f"Fetching page {page}: {page_url}")
            items = self.get_items(page_url)
            
            if not items:
                logger.info(f"No items on page {page}, stopping pagination")
                break
            
            # Add unique items
            new_items = 0
            for item in items:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    all_items.append(item)
                    new_items += 1
            
            logger.info(f"Page {page}: {len(items)} items, {new_items} new unique items")
            
            # If we got fewer items than expected, we've likely reached the end
            if len(items) < 20:  # Yad2 typically shows ~40 items per page
                logger.info(f"Fewer items than expected on page {page}, stopping pagination")
                break
        
        logger.info(f"Total: {len(all_items)} unique items from {page} pages")
        return all_items
    
    def get_item_ids(self, search_url: str) -> set[str]:
        """
        Get just the item IDs from a search URL.
        
        Useful for detecting new items by comparing ID sets.
        
        Args:
            search_url: The Yad2 search URL
            
        Returns:
            Set of item IDs (tokens)
        """
        items = self.get_items(search_url)
        return {item.id for item in items}
    
    def _is_blocked(self, html: str) -> bool:
        """Check if the response indicates bot protection."""
        html_lower = html.lower()
        blocked_indicators = [
            "captcha",
            "shieldsquare",
            "radware",
            "bouncer",
            "access denied",
            "blocked",
        ]
        return any(indicator in html_lower for indicator in blocked_indicators)
    
    def _extract_next_data(self, html: str) -> Optional[dict]:
        """Extract __NEXT_DATA__ JSON from HTML."""
        pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)
        
        if not match:
            return None
        
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse __NEXT_DATA__: {e}")
            return None
    
    def _parse_items(self, next_data: dict) -> List[Yad2Item]:
        """Parse items from __NEXT_DATA__ structure."""
        items, _ = self._parse_items_with_metadata(next_data)
        return items
    
    def _parse_items_with_metadata(self, next_data: dict) -> tuple[List[Yad2Item], Optional[int]]:
        """
        Parse items and metadata from __NEXT_DATA__ structure.
        
        Returns:
            Tuple of (items list, total_results count or None)
        """
        items: List[Yad2Item] = []
        total_results: Optional[int] = None
        
        try:
            # Navigate to the feed data
            props = next_data.get("props", {})
            page_props = props.get("pageProps", {})
            dehydrated_state = page_props.get("dehydratedState", {})
            queries = dehydrated_state.get("queries", [])
            
            if not queries:
                logger.warning("No queries found in dehydratedState")
                return items, total_results
            
            # Find the feed query (first query usually contains the feed)
            for query in queries:
                query_key = query.get("queryKey", [])
                
                # Look for feed query
                if query_key and query_key[0] == "feed":
                    state = query.get("state", {})
                    data = state.get("data", {})
                    
                    # Extract total results from pagination metadata
                    # Yad2 includes this in the feed data under pagination.total
                    pagination = data.get("pagination", {})
                    total_results = pagination.get("total")
                    
                    # Alternative locations for total count
                    if total_results is None:
                        total_results = pagination.get("totalResults")
                    if total_results is None:
                        total_results = data.get("totalResults")
                    if total_results is None:
                        total_results = data.get("total")
                    if total_results is None:
                        # Try to get from meta
                        meta = data.get("meta", {})
                        total_results = meta.get("totalResults") or meta.get("total")
                    
                    logger.debug(f"Extracted total_results: {total_results}")
                    
                    # Extract items from all categories
                    categories = ["platinum", "boost", "solo", "commercial", "private"]
                    
                    for category in categories:
                        category_items = data.get(category, [])
                        if isinstance(category_items, list):
                            for raw_item in category_items:
                                item = Yad2Item.from_next_data(raw_item, feed_source=category)
                                if item:
                                    items.append(item)
                    
                    break  # Found the feed query, no need to continue
            
            # Remove duplicates (items can appear in multiple categories)
            seen_ids = set()
            unique_items = []
            for item in items:
                if item.id not in seen_ids:
                    seen_ids.add(item.id)
                    unique_items.append(item)
            
            return unique_items, total_results
            
        except Exception as e:
            logger.error(f"Error parsing items: {e}")
            return items, total_results
    
    def get_item_created_at(self, item_id: str) -> Optional[datetime]:
        """
        Fetch the creation date of an item from its detail page.
        
        Args:
            item_id: The item token/ID
            
        Returns:
            datetime of creation or None if not found
        """
        item_url = f"{ITEM_BASE_URL}{item_id}"
        logger.debug(f"Fetching item details from: {item_url}")
        
        try:
            # Wait for rate limit before making request
            self._wait_for_rate_limit()
            
            response = self.session.get(item_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Log response details for debugging
            content_length = len(response.text)
            has_next_data = "__NEXT_DATA__" in response.text
            logger.info(f"Item {item_id}: status={response.status_code}, content_length={content_length}, has_next_data={has_next_data}")
            
            # Check for various types of blocks
            if self._is_blocked(response.text):
                logger.warning(f"Blocked when fetching item {item_id}")
                if self.track_stats:
                    self.stats["item_requests_blocked"] += 1
                return None
            
            # Check for redirect/challenge page (short response without __NEXT_DATA__)
            if content_length < 5000 and not has_next_data:
                # Log first 500 chars to understand what we got
                logger.warning(f"Item {item_id}: Got short response without __NEXT_DATA__, likely a challenge page. First 500 chars: {response.text[:500]}")
                if self.track_stats:
                    self.stats["item_requests_blocked"] += 1
                return None
            
            next_data = self._extract_next_data(response.text)
            if not next_data:
                logger.warning(f"No __NEXT_DATA__ in item page {item_id}")
                if self.track_stats:
                    self.stats["item_requests_failed"] += 1
                return None
            
            # Navigate to item data
            props = next_data.get("props", {})
            page_props = props.get("pageProps", {})
            dehydrated_state = page_props.get("dehydratedState", {})
            queries = dehydrated_state.get("queries", [])
            
            # Log available query keys for debugging
            query_keys = [q.get("queryKey", []) for q in queries]
            logger.info(f"Item {item_id}: Available query keys: {query_keys}")
            
            for query in queries:
                query_key = query.get("queryKey", [])
                # Look for item query - can be ['item'] or ['vehicles', 'item', 'token']
                is_item_query = (
                    (query_key and query_key[0] == "item") or
                    (len(query_key) >= 2 and query_key[1] == "item")
                )
                if is_item_query:
                    state = query.get("state", {})
                    data = state.get("data", {})
                    
                    # Log available keys in data for debugging
                    data_keys = list(data.keys()) if isinstance(data, dict) else "not a dict"
                    logger.info(f"Item {item_id}: Data keys: {data_keys}")
                    
                    dates = data.get("dates", {})
                    created_at_str = dates.get("createdAt")
                    
                    if created_at_str:
                        # Parse the date string (format: "2025-11-20T19:29:53")
                        try:
                            created_at = datetime.fromisoformat(created_at_str)
                            # Assume Israel timezone if not specified
                            if created_at.tzinfo is None:
                                created_at = created_at.replace(tzinfo=ISRAEL_TZ)
                            logger.debug(f"Item {item_id} created at: {created_at}")
                            if self.track_stats:
                                self.stats["item_requests_success"] += 1
                            return created_at
                        except ValueError as e:
                            logger.warning(f"Failed to parse date '{created_at_str}': {e}")
                            if self.track_stats:
                                self.stats["item_requests_failed"] += 1
                            return None
            
            logger.warning(f"No dates found for item {item_id}")
            if self.track_stats:
                self.stats["item_requests_no_dates"] += 1
            return None
            
        except requests.RequestException as e:
            logger.error(f"Request failed for item {item_id}: {e}")
            if self.track_stats:
                self.stats["item_requests_failed"] += 1
            return None
        except Exception as e:
            logger.error(f"Error fetching item {item_id}: {e}")
            if self.track_stats:
                self.stats["item_requests_failed"] += 1
            return None
    
    def enrich_item_with_created_at(self, item: Yad2Item, force_api: bool = False) -> Yad2Item:
        """
        Fetch and set the created_at field for an item.
        
        If the item already has created_at from image URL parsing, this is a no-op
        unless force_api is True.
        
        Args:
            item: The Yad2Item to enrich
            force_api: If True, always fetch from API even if created_at exists
            
        Returns:
            The same item with created_at populated (if available)
        """
        # Skip if already has created_at from image URL (unless forced)
        if item.created_at is not None and item.created_at_source == "image_url" and not force_api:
            logger.debug(f"Item {item.id} already has created_at from image URL, skipping API call")
            return item
        
        created_at = self.get_item_created_at(item.id)
        if created_at:
            item.created_at = created_at
            item.created_at_source = "api"
        return item
    
    def validate_url(self, search_url: str, check_access: bool = False) -> bool:
        """
        Validate a Yad2 search URL.
        
        Args:
            search_url: URL to validate
            check_access: If True, also verify the URL is accessible
            
        Returns:
            True if valid, False otherwise
        """
        try:
            parsed = parse.urlparse(search_url)
            
            if parsed.netloc != YAD2_NETLOC:
                logger.warning(f"Invalid netloc: {parsed.netloc}")
                return False
            
            if check_access:
                response = self.session.get(search_url, timeout=self.timeout)
                response.raise_for_status()
                
                if self._is_blocked(response.text):
                    logger.warning("URL is blocked by bot protection")
                    return False
                
                next_data = self._extract_next_data(response.text)
                if not next_data:
                    logger.warning("URL does not contain valid __NEXT_DATA__")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"URL validation failed: {e}")
            return False


# Convenience function for simple usage
def get_items(search_url: str) -> List[Yad2Item]:
    """
    Get items from a Yad2 search.
    
    Args:
        search_url: The Yad2 search URL
        
    Returns:
        List of Yad2Item objects
    """
    parser = Yad2Parser()
    return parser.get_items(search_url)


def get_item_ids(search_url: str) -> set[str]:
    """
    Get item IDs from a Yad2 search.
    
    Args:
        search_url: The Yad2 search URL
        
    Returns:
        Set of item IDs (tokens)
    """
    parser = Yad2Parser()
    return parser.get_item_ids(search_url)