"""
config.py — Application configuration

Reads from your .env file. Never hard-code secrets in code.
Add new settings here when you need them.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    All configuration comes from environment variables.
    If a variable is not set, the default value below is used.
    """

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/icc_trading"

    # ── Security ──────────────────────────────────────────────────────────
    # This secret must match what you set in TradingView's webhook headers
    WEBHOOK_SECRET: str = "change-me-in-.env"

    # Used to sign JWT tokens for user sessions
    JWT_SECRET: str = "change-me-in-.env"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # ── Environment ────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"

    # ── CORS — which URLs are allowed to call this API ─────────────────────
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",     # Local Next.js frontend
        "http://localhost:3001",
        "https://your-app.vercel.app",  # Replace with your Vercel URL
    ]

    # ── Trading configuration ───────────────────────────────────────────────
    # Symbols that can receive and evaluate alerts
    ALLOWED_SYMBOLS: List[str] = [
        "ES1!", "MES1!",    # S&P 500
        "NQ1!", "MNQ1!",    # Nasdaq 100
        "YM1!", "MYM1!",    # Dow Jones
        "CL1!", "MCL1!",    # Crude Oil
        "GC1!", "MGC1!",    # Gold
    ]

    # Sessions when trading is allowed
    ALLOWED_SESSIONS: List[str] = [
        "us_premarket",
        "us_regular",
        "us_afterhours",
        "globex",
    ]

    class Config:
        # Tells pydantic to read from the .env file
        env_file = ".env"
        case_sensitive = True


# Create a single shared instance — imported everywhere else
settings = Settings()
