# Yad2 Scanner Logic Summary

## Overview
The scanner monitors Yad2 search results for new listings. It uses an **optimized detection strategy** that minimizes API calls by extracting creation timestamps from image URLs.

## Configuration
- **MAX_PAGES_PER_SEARCH**: 3 (scan up to 3 pages per search)
- **MAX_STORED_IDS**: 2000 (maximum item IDs stored per search)

## 1. Item Discovery (Search Pages)
*   **Source**: The scanner fetches the user's saved search URL with pagination (up to 3 pages).
*   **Method**: HTML Scraping. It does not use the deprecated API.
*   **Extraction**:
    *   Parses the HTML response.
    *   Extracts the JSON object from the `<script id="__NEXT_DATA__">` tag.
    *   Navigates through `props.pageProps.dehydratedState.queries` to find the feed data.
*   **Result**: A list of current items with basic details (ID, price, title) **AND** creation date extracted from image URLs.

## 2. Creation Date Extraction (Optimized - No Extra API Call)
*   **Source**: Image URLs in the search results contain timestamps.
*   **Format**: `https://img.yad2.co.il/Pic/202601/06/1_8/o/y2_1pa_010653_20260106114053.jpeg`
    *   The timestamp `20260106114053` = `2026-01-06 11:40:53`
*   **Extraction**: Regex pattern `_(\d{14})\.` extracts the 14-digit timestamp.
*   **Benefit**: **No extra API call needed** for most items!

## 3. New Item Detection
*   **State Tracking**: The system stores the list of `item_ids` seen in previous scans in DynamoDB (up to 2000 IDs).
*   **Comparison**:
    *   `Current IDs` - `Previous IDs` = `Potentially New IDs`
*   **Purpose**: This identifies items that have appeared since the last scan. However, these could be old items that were "bumped" to the top.

## 4. Verification (Optimized)
*   **Trigger**: Performed **only** for items identified as "Potentially New".
*   **Primary Method (Image URL)**:
    *   Uses `created_at` already extracted from image URL during parsing.
    *   **No extra API call needed!**
*   **Fallback Method (API Call)**:
    *   If image URL parsing failed (no image, different format, etc.).
    *   Sends HTTP GET request for the item page.
    *   Extracts `createdAt` from `dates.createdAt` in `__NEXT_DATA__`.
*   **Logic**:
    *   If `item.created_at > last_scan_time`: **CONFIRMED NEW**.
    *   If `item.created_at <= last_scan_time`: **IGNORED** (Old item bumped to top).

## 5. Notification & Storage
*   **Notification**: Telegram messages are sent **only** for confirmed new items.
*   **Storage**:
    *   Updates `last_item_ids` with the merged list of all seen IDs (limited to 2000).
    *   Updates `last_scan_time` to the current timestamp.

## Anti-Bot Measures
*   **Headers**: Uses browser-like headers (User-Agent, Sec-Ch-Ua, etc.) to mimic a real user.
*   **Detection**: Checks responses for known blocking keywords ("captcha", "shieldsquare", "radware").
*   **Traffic Optimization**:
    *   Extracts `createdAt` from image URLs (no extra API calls for most items).
    *   Only falls back to API calls when image URL parsing fails.
    *   Scans up to 3 pages per search to catch more items.

## Performance Benefits
1. **Reduced API Calls**: Most items have `createdAt` extracted from image URLs.
2. **Better Coverage**: Scanning 3 pages catches items that might be pushed down.
3. **Lower Block Risk**: Fewer API calls = less chance of triggering bot detection.