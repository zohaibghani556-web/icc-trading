"""
models/icc_config.py — ICC rule configuration

Stores all the configurable thresholds for the ICC rule engine.
You can edit these from the Settings page in the dashboard.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class ICCConfiguration(Base):
    """
    User-configurable ICC rule settings.
    All thresholds and toggles live here — no magic numbers in code.
    """
    __tablename__ = "icc_configurations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, default="Default")
    is_active = Column(Boolean, default=True)

    # ── Environment rules ─────────────────────────────────────────────────
    allowed_sessions = Column(JSON, default=lambda: ["us_regular"])
    require_htf_bias = Column(Boolean, default=True)
    htf_bias_timeframe = Column(String(10), default="60")

    # ── Indication rules ──────────────────────────────────────────────────
    min_impulse_candles = Column(Integer, default=1)
    min_structure_break_points = Column(Float, default=2.0)

    # ── Correction rules ─────────────────────────────────────────────────
    min_retracement_pct = Column(Float, default=0.236)
    max_retracement_pct = Column(Float, default=0.618)
    require_correction_zone = Column(Boolean, default=True)
    allowed_correction_zones = Column(JSON, default=lambda: [
        "fair_value_gap", "order_block", "prior_breakout", "vwap", "discount_zone"
    ])

    # ── Continuation rules ────────────────────────────────────────────────
    require_rejection_candle = Column(Boolean, default=False)
    require_volume_expansion = Column(Boolean, default=False)
    min_continuation_trigger_score = Column(Integer, default=50)

    # ── Risk rules ────────────────────────────────────────────────────────
    min_risk_reward = Column(Float, default=2.0)
    max_risk_per_trade_pct = Column(Float, default=1.0)
    daily_max_loss_pct = Column(Float, default=3.0)
    max_consecutive_losses = Column(Integer, default=3)
    max_open_positions = Column(Integer, default=1)

    # ── Countertrend penalty ──────────────────────────────────────────────
    countertrend_score_penalty = Column(Integer, default=20)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
