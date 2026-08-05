# Yad2 Notification Bot — Logic Summary

> Regenerated directly from source code.

## System Purpose
A Telegram bot that lets users register Yad2 search URLs (real estate / vehicles). On a schedule it re-scrapes each search, detects newly-listed items, and pushes a Telegram notification to the owning user. It runs entirely serverless on AWS Lambda, deployed via Serverless Framework (`serverless.yml`).

## Two Independent Runtime Paths
The app has two entirely separate entry paths sharing the same DynamoDB table and config:
1. **Telegram Bot path** (interactive) — handles user commands via a webhook.
2. **Scanner path** (scheduled) — polls Yad2 and sends notifications.

## 1. Configuration Layer
`Settings` (`src/config.py`) is a Pydantic `BaseSettings` class loaded from `.env`. Key settings:
- **Credentials**: `TELEGRAM_BOT_TOKEN`, `ADMIN_BOT_TOKEN`, `ADMIN_CHAT_ID`, `AWS_REGION`, `DYNAMODB_TABLE`, `STATS_TABLE`.
- **Scan tuning**: `MAX_REQUESTS_PER_RUN`, `MAX_PAGES_INITIAL`, `MAX_PAGES_REGULAR`, `SMALL_SEARCH_THRESHOLD` (200), `ITEMS_PER_PAGE`, `PAGE_REQUEST_DELAY`, `MAX_STORED_IDS`.
- **Schedule window**: `SCAN_START_HOUR` / `SCAN_END_HOUR` / `TIMEZONE` (Israel time).
- **Alerting**: `ALERT_BLOCK_RATE_THRESHOLD`, `ALERT_ERROR_RATE_THRESHOLD`.

## 2. Telegram Bot Path (Interactive)
**Entry → Webhook**
- API Gateway → Lambda via Mangum adapter in `src/api/lambda_entry.py`, wrapping the FastAPI app in `src/api/main.py`.
- Telegram POSTs updates to `telegram_webhook()` (`src/api/webhook.py`). It builds an aiogram `Dispatcher` via `get_dispatcher()`, sets the command menu once per cold start with `ensure_bot_commands()`, and feeds the update into the router.
- `scripts/set_webhook.py` registers the webhook URL with Telegram. `src/bot/run_polling.py` is the local-dev alternative (long-polling).

**Routing**
- `src/bot/router.py` registers all handler routers.

**Handlers** (aiogram FSM-driven conversations):
- **Start / menu**: `src/bot/handlers/start.py` shows the main menu (`src/bot/keyboards/main_menu.py`).
- **Add search**: `src/bot/handlers/add_search.py` drives a multi-step flow:
  - `cb_add_search()` starts the conversation (FSM states in `src/bot/states.py`).
  - `handle_link()` validates the URL via `is_valid_link()`, then asks about a commercial filter.
  - `handle_name()` probes search size with `get_initial_search_info()` (calls `Yad2Parser`) to classify small vs. large, then persists via `db_add_search`.
- **List / delete searches**: `src/bot/handlers/list_searches.py` with keyboards from `src/bot/keyboards/search_list.py`.
- **Stats**: `src/bot/handlers/stats.py` reads aggregates via `get_stats_summary()` and `get_latest_stats()`.

## 3. Persistence Layer (DynamoDB)
`src/bot/db/dynamodb.py` is the sole data access layer, using two tables (searches + stats).

Per-search record CRUD:
- `add_search()`, `get_searches()`, `delete_search()`, `get_search_by_id()`.
- `update_search_scan_results()` — after each scan, writes the merged item-ID bank (`last_item_ids`), initial-scan-complete flag, total item count, and small/large classification.
- `get_all_searches()` — full-table scan used by the scanner.
- `get_total_search_count()` enforces global limits.
- Stats: `save_scan_stats()`, `get_stats_summary()`, etc.
- `src/bot/db/mock_db.py` is an in-memory stand-in for local testing.

## 4. Yad2 Scraping Engine
`src/yad2/parser.py` is the core scraper. It does **HTML scraping, not a public API** — extracting the embedded `__NEXT_DATA__` JSON blob from the page.

- `Yad2Parser` fetches pages (`_fetch_page_html()`) with rate limiting (`_wait_for_rate_limit()`) and browser-like headers.
- `Yad2Parser.get_search_result()` is the main workhorse: sanitizes the URL, fetches HTML, detects blocking via `_is_blocked()` (captcha/shieldsquare/radware keywords), extracts JSON via `_extract_next_data()`, and parses items with `_parse_items_with_metadata()`.
- **Anti-bot handling**: on a 403/block, `_handle_blocked_request()` resets the HTTP session (`reset_session()`) to shed poisoned cookies, then retries. `src/yad2/browser_fetcher.py` provides a heavier browser-based fallback fetch.
- Each listing becomes a `Yad2Item` via `Yad2Item.from_next_data()`, auto-detecting vehicle vs. real-estate categories. Items are tagged by `feed_source` (platinum/boost/solo/commercial/private) — commercial filtering uses this, not `ad_type`.
- **Creation timestamp** is extracted for free from the image filename via `extract_datetime_from_image_url()` (regex on a 14-digit timestamp); `get_item_created_at()` is a per-item detail-page fallback when the image has no timestamp.

## 5. Scanner Path (Scheduled Fan-Out Architecture)
Triggered by a CloudWatch schedule (Israel-time window). It uses an **orchestrator → worker fan-out** pattern to spread requests across multiple Lambda invocations (and thus IPs) to avoid bot-blocking.

**Orchestrator** — `handler()` (`src/scanner/orchestrator.py`):
1. Checks the schedule window with `is_within_scan_hours()`.
2. Loads all searches via `get_searches_for_scanning()`.
3. Estimates HTTP cost per search with `estimate_requests()` (large/initial searches need more pages).
4. Packs searches into request-budget-limited batches via `batch_by_request_budget()`.
5. Invokes worker Lambdas synchronously via `invoke_worker_sync()`.
6. Aggregates all worker results with `aggregate_stats()` and sends a single admin summary via `format_centralized_summary()` + `send_admin_message()`.

**Worker** — `handler()` (`src/scanner/worker.py`, containerized via `Dockerfile.worker`): receives one batch and runs `ItemScanner.scan_batch_sync()`.

**Detection logic** — `ItemScanner._scan_single_search()`:
- **Small searches (≤200 items)** — *ID-bank-only*: initial scan fetches all pages to build the full ID bank; regular scans fetch page 1, and any ID not in the bank is new. If a "small" search unexpectedly needs > `MAX_SAFE_PAGES` (5), it is reclassified as large.
- **Large searches (>200 items)** — *hybrid*: fetch page 1, treat unknown IDs as *candidates*, then confirm they're genuinely new (vs. bumped) using the `created_at` timestamp.
- After scanning, it writes the merged ID bank via `update_search_scan_results()` (capped at `MAX_STORED_IDS` = 1500).

**Notification** — confirmed-new items are sent to the owning user with `TelegramNotifier`, formatting each `Yad2Item`.

**Stats & alerting** — `src/scanner/stats.py` collects per-run counters (`ScanStats`), checks block/error-rate thresholds (`check_alerts`), and persists them. `src/scanner/lambda_usage.py` tracks Lambda cost/usage.

## End-to-End Flow Summary
1. User sends `/start` → adds a Yad2 URL → bot classifies it small/large and stores it in DynamoDB (webhook Lambda).
2. CloudWatch fires the orchestrator every ~30 min in the allowed window.
3. Orchestrator batches searches by request budget and fans out to worker Lambdas (distinct IPs).
4. Each worker scrapes Yad2 (`__NEXT_DATA__` JSON), compares against the stored ID bank, and for large searches verifies novelty via image-derived `created_at`.
5. Genuinely-new items → Telegram DM to the owning user; ID bank updated in DynamoDB.
6. Orchestrator aggregates all worker stats → single admin summary + saved run stats, with alerting on high block/error rates.

## Notes
Several files (`src/yad2/scraper.py`, `src/test_yad2_lambda/`, `src/load_test/`, `src/playwright_test/`, and the `serverless-*.yml` variants) are experimental/investigation artifacts and are **not part of the production flow**, which is driven by `serverless.yml`, and the `src/api`, `src/bot`, `src/scanner`, and `src/yad2/parser.py` modules.
