"""
api/v1/__init__.py — Combines all route modules into one router

Every route group is registered here under its prefix.
"""

from fastapi import APIRouter

from app.api.v1.alerts import router as alerts_router
from app.api.v1.setups import router as setups_router
from app.api.v1.trades import router as trades_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.config import router as config_router
from app.api.v1.backtest import router as backtest_router

router = APIRouter()

router.include_router(alerts_router, prefix="/alerts", tags=["Alerts & Webhooks"])
router.include_router(setups_router, prefix="/setups", tags=["Setup Evaluations"])
router.include_router(trades_router, prefix="/trades", tags=["Trades"])
router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
router.include_router(config_router, prefix="/config", tags=["Configuration"])
router.include_router(backtest_router, prefix="/backtest", tags=["Backtesting"])
