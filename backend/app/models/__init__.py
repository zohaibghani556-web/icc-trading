"""
models/__init__.py — Import all models so SQLAlchemy can find them at startup.
"""

from app.models.alert import RawAlert
from app.models.signal import Signal
from app.models.setup import SetupEvaluation
from app.models.trade import Trade, TradeReview
from app.models.user import User
from app.models.instrument import Instrument
from app.models.icc_config import ICCConfiguration

__all__ = [
    "RawAlert", "Signal", "SetupEvaluation",
    "Trade", "TradeReview", "User",
    "Instrument", "ICCConfiguration",
]
