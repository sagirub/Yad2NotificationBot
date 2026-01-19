from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Main application settings."""
    TELEGRAM_BOT_TOKEN: str
    AWS_REGION: str = "eu-central-1"
    DYNAMODB_TABLE: str = "Yad2Searches"
    
    # Scanner settings
    ADMIN_CHAT_ID: str = ""  # Telegram chat ID for admin notifications
    
    # Rate limiting
    MAX_REQUESTS_PER_RUN: int = 3
    MAX_PAGES_INITIAL: int = 3  # Pages to scan on first run
    MAX_PAGES_REGULAR: int = 1  # Pages to scan on regular runs
    
    # Scheduling (Israel timezone)
    SCAN_START_HOUR: int = 6   # 6 AM Israel time
    SCAN_END_HOUR: int = 24    # 12 AM (midnight) Israel time
    TIMEZONE: str = "Asia/Jerusalem"
    
    # Storage
    MAX_STORED_IDS: int = 200
    STATS_RETENTION_DAYS: int = 7
    STATS_TABLE: str = "Yad2Stats"
    
    # Observability
    SEND_RUN_SUMMARY: bool = True
    ALERT_BLOCK_RATE_THRESHOLD: float = 0.5
    ALERT_ERROR_RATE_THRESHOLD: float = 0.2

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
