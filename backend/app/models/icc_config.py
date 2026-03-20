"""
models/icc_config.py — ICC rule configuration

FIXES:
  - Added min_structure_break_points column (was referenced in code but missing from model)
  - Updated default allowed_sessions to include all Pine Script session names
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class ICCConfiguration(Base):
    __tablename__ = "icc_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, default="Default")
    is_active = Column(Boolean, default=True)

    # ── Environment rules ─────────────────────────────────────────────────
    # Includes both Pine Script session names AND backend session names
    allowed_sessions = Column(JSON, default=lambda: [
        "us_regular", "us_premarket", "london", "globex",
        "ny_open", "ny_mid", "ny_power", "premarket", "asia"
    ])
    require_htf_bias = Column(Boolean, default=False)
    htf_bias_timeframe = Column(String(10), default="60")

    # ── Indication rules ──────────────────────────────────────────────────
    min_impulse_candles = Column(Integer, default=1)
    min_structure_break_points = Column(Float, default=0.5)  # was missing, caused AttributeError

    # ── Correction rules ─────────────────────────────────────────────────
    min_retracement_pct = Column(Float, default=0.236)
    max_retracement_pct = Column(Float, default=0.618)
    require_correction_zone = Column(Boolean, default=False)
    allowed_correction_zones = Column(JSON, default=lambda: [
        "fair_value_gap", "order_block", "prior_breakout_level",
        "vwap", "anchored_vwap", "discount_zone", "fibonacci_zone",
        "ema_zone", "structure_level", "premium_zone",
    ])

    # ── Continuation rules ────────────────────────────────────────────────
    require_rejection_candle = Column(Boolean, default=False)
    require_volume_expansion = Column(Boolean, default=False)
    min_continuation_trigger_score = Column(Integer, default=40)

    # ── Risk rules ────────────────────────────────────────────────────────
    min_risk_reward = Column(Float, default=2.0)
    max_risk_per_trade_pct = Column(Float, default=2.0)
    daily_max_loss_pct = Column(Float, default=5.0)
    max_consecutive_losses = Column(Integer, default=5)
    max_open_positions = Column(Integer, default=0)  # 0 = no limit

    # ── Countertrend penalty ──────────────────────────────────────────────
    countertrend_score_penalty = Column(Integer, default=10)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
