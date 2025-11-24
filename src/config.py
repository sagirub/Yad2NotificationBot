from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    AWS_REGION: str = "eu-central-1"
    DYNAMODB_TABLE: str = "Yad2Searches"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
