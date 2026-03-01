from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Main application settings."""
    TELEGRAM_BOT_TOKEN: str
    AWS_REGION: str = "eu-central-1"
    DYNAMODB_TABLE: str = "Yad2Searches"
    
    # Scanner settings
    ADMIN_CHAT_ID: str = ""  # Telegram chat ID for admin notifications
    ADMIN_BOT_TOKEN: str = ""  # Separate bot token for admin stats (uses main bot if empty)
    
    # Rate limiting
    MAX_REQUESTS_PER_RUN: int = 3
    MAX_PAGES_INITIAL: int = 3  # Pages to scan on first run
    MAX_PAGES_REGULAR: int = 1  # Pages to scan on regular runs
    
    # Scheduling (Israel timezone)
    SCAN_START_HOUR: int = 6   # 6 AM Israel time
    SCAN_END_HOUR: int = 24    # 12 AM (midnight) Israel time
    TIMEZONE: str = "Asia/Jerusalem"
    
    # Storage
    # MAX_STORED_IDS should be at least 3x SMALL_SEARCH_THRESHOLD to handle item rotation
    MAX_STORED_IDS: int = 1500
    STATS_RETENTION_DAYS: int = 7
    STATS_TABLE: str = "Yad2Stats"
    MAX_SEARCHES_TOTAL: int = 50  # Maximum total searches across all users
    
    # Detection strategy threshold
    # Searches with <= this many items use ID-bank-only detection (faster, simpler)
    # Searches with > this many items use hybrid detection (ID bank + createdAt verification)
    #
    # For small searches: Initial scan fetches ALL pages to build complete ID bank
    #   (pages calculated dynamically from total_results / ~40 items per page)
    # For large searches: Initial scan fetches MAX_PAGES_INITIAL pages only
    #
    # DynamoDB Free Tier Analysis (100 searches, scans every 5 min):
    # - Storage: 100 searches × 200 IDs × 15 bytes = ~300 KB (0.001% of 25 GB free tier)
    # - Writes: Well within free tier capacity
    # - Reads: Minimal
    #
    # X=200 chosen because:
    # - Most targeted searches (specific neighborhoods, room counts) have 50-200 results
    # - ID-bank-only detection is more reliable (no createdAt dependency)
    # - Storage is negligible even with 100 searches
    SMALL_SEARCH_THRESHOLD: int = 200
    ITEMS_PER_PAGE: int = 40  # Approximate items per Yad2 page
    
    # Delay between page requests to avoid bot detection (in seconds)
    # Applied during initial scans when fetching multiple pages
    PAGE_REQUEST_DELAY: float = 2.0
    
    # Observability
    SEND_RUN_SUMMARY: bool = True
    ALERT_BLOCK_RATE_THRESHOLD: float = 0.5
    ALERT_ERROR_RATE_THRESHOLD: float = 0.2

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# AWS Lambda Free Tier Limits (per month)
LAMBDA_FREE_TIER_INVOCATIONS = 1_000_000  # 1 million requests
LAMBDA_FREE_TIER_GB_SECONDS = 400_000  # 400,000 GB-seconds
