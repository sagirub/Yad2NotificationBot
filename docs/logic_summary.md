# Yad2 Scanner Logic Summary

## Overview
The scanner monitors Yad2 search results for new listings. It uses a **dual detection strategy** based on search size:
- **Small searches** (≤200 items): ID-bank-only detection — fast, no createdAt needed
- **Large searches** (>200 items): Hybrid detection — ID bank + createdAt verification

## Architecture

```
CloudWatch Event (every 30 min, 6 AM - midnight Israel time)
        ↓
Orchestrator Lambda
        ↓  estimates requests per search, packs into budget-based batches
├── Worker Lambda 1 (budget: 5 requests) → Different IP
├── Worker Lambda 2 (budget: 5 requests) → Different IP
└── Worker Lambda N (remaining)          → Different IP
        ↓
Orchestrator aggregates results and sends single admin notification
```

## Configuration
- **SMALL_SEARCH_THRESHOLD**: 200 items (searches ≤ this use ID-bank-only)
- **MAX_STORED_IDS**: 1500 (maximum item IDs stored per search)
- **MAX_PAGES_INITIAL**: 3 (pages for large search initial scan)
- **MAX_PAGES_REGULAR**: 1 (pages for regular scans)
- **MAX_SAFE_PAGES**: 5 (max pages before reclassifying small → large)
- **MAX_REQUESTS_PER_WORKER**: 5 (request budget per worker Lambda)
- **ITEMS_PER_PAGE**: ~40 (approximate items per Yad2 page)

## 1. Item Discovery (Search Pages)
*   **Source**: The scanner fetches the user's saved search URL with pagination.
*   **Method**: HTML Scraping — parses `<script id="__NEXT_DATA__">` JSON.
*   **Extraction**: Navigates `props.pageProps.dehydratedState.queries` to find feed data.
*   **Feed sections**: Items are categorized by `feed_source`: platinum, boost, solo, commercial, private.
*   **Result**: A list of current items with basic details (ID, price, title, feed_source) AND creation date extracted from image URLs.

## 2. Detection Strategy

### Small Searches (≤200 items) — ID-Bank-Only
*   **Initial scan**: Fetches ALL pages to build a complete ID bank.
*   **Regular scan**: Fetches page 1 only. Any item NOT in the ID bank is new.
*   **No createdAt verification needed** — the complete ID bank is the source of truth.
*   **Reclassification**: If a small search needs >5 pages, it's reclassified as large.

### Large Searches (>200 items) — Hybrid Detection
*   **Initial scan**: Fetches 3 pages to build a partial ID bank.
*   **Regular scan**: Fetches page 1. Items not in the ID bank are *potentially* new.
*   **Verification**: Uses createdAt timestamp to confirm items are truly new (not just bumped).

## 3. Creation Date Extraction (Optimized - No Extra API Call)
*   **Source**: Image URLs in the search results contain timestamps.
*   **Format**: `https://img.yad2.co.il/Pic/202601/06/1_8/o/y2_1pa_010653_20260106114053.jpeg`
    *   The timestamp `20260106114053` = `2026-01-06 11:40:53`
*   **Extraction**: Regex pattern `_(\d{14})\.` extracts the 14-digit timestamp.
*   **Fallback**: If image URL has no timestamp, fetches item detail page via API.

## 4. Commercial Item Filtering
*   **Filter basis**: Uses `feed_source` (which section the item appears in), NOT `ad_type`.
*   **Reason**: `ad_type="commercial"` means the seller is a dealer, but `feed_source="commercial"` means it's a promoted dealer listing section. Items in the "private" feed section can still be from dealers but appear as regular listings.
*   **ID bank**: Tracks ALL items (including commercial) to prevent re-detection.

## 5. Anti-Bot Measures
*   **Headers**: Uses browser-like headers (User-Agent, Sec-Ch-Ua, etc.).
*   **Detection**: Checks responses for blocking keywords ("captcha", "shieldsquare", "radware").
*   **Session reset**: When blocked, creates a fresh HTTP session to avoid poisoned cookies.
*   **Budget-based batching**: Each worker Lambda makes at most 5 requests to avoid triggering bot protection from a single IP.
*   **Rate limiting**: Configurable delay between page requests (default 2s).

## 6. Notification & Storage
*   **Notification**: Telegram messages sent only for confirmed new items.
*   **Storage**: Updates `last_item_ids` with merged list of all seen IDs (limited to 1500).
*   **Admin summary**: Centralized notification sent by orchestrator after all workers complete.
