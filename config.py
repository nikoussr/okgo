import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost/alltransfer"

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BOT_SECRET: Optional[str] = None  # Для валидации WebApp
    TELEGRAM_CHANNEL_ID: int = -1002901854857

    YOKASSA_TOKEN_LIVE: str


    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AllTransfer API"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
