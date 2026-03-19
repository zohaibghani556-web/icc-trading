"""
config.py — Application configuration
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./icc_trading.db"
    WEBHOOK_SECRET: str = "change-me-in-.env"
    JWT_SECRET: str = "change-me-in-.env"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7
    ENVIRONMENT: str = "development"
    ANTHROPIC_API_KEY: str = ""

    ALLOWED_ORIGINS: List[str] = ["*"]

    ALLOWED_SYMBOLS: List[str] = [
        "ES1!", "MES1!", "NQ1!", "MNQ1!",
        "YM1!", "MYM1!", "CL1!", "MCL1!",
        "GC1!", "MGC1!",
    ]

    ALLOWED_SESSIONS: List[str] = [
        "us_premarket", "us_regular", "us_afterhours", "globex",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
