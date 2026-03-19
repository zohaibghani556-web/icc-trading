"""
models/trade.py — Trade records (paper and future live)

Every trade taken (paper or live) is stored here.
Post-trade review labels are stored in the TradeReview model.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, Text, JSON, Integer, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.db.database import Base


class TradeStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    PENDING = "pending"


class TradeMode(str, enum.Enum):
    PAPER = "paper"
    LIVE = "live"


class Trade(Base):
    """
    Represents a single trade (paper or live).

    MAE = Maximum Adverse Excursion (furthest it went against you)
    MFE = Maximum Favorable Excursion (furthest it went in your favor)
    Both are tracked for post-trade analysis.
    """
    __tablename__ = "trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    setup_id = Column(UUID(as_uuid=True), ForeignKey("setup_evaluations.id"), nullable=True)

    # ── Mode ────────────────────────────────────────────────────────────────
    mode = Column(String(10), nullable=False, default="paper")  # paper / live

    # ── Instrument ──────────────────────────────────────────────────────────
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    direction = Column(String(10), nullable=False)  # long / short
    session = Column(String(50), nullable=True)

    # ── Entry ────────────────────────────────────────────────────────────────
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    contracts = Column(Integer, nullable=False, default=1)
    account_risk_dollars = Column(Float, nullable=True)  # $ risked on this trade

    # ── Exit ─────────────────────────────────────────────────────────────────
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    exit_reason = Column(String(50), nullable=True)  # stop_hit / target_hit / manual / trailing

    # ── Levels ───────────────────────────────────────────────────────────────
    stop_price = Column(Float, nullable=False)
    target_price = Column(Float, nullable=True)
    planned_rr = Column(Float, nullable=True)  # planned risk-reward

    # ── Outcome ──────────────────────────────────────────────────────────────
    status = Column(String(20), nullable=False, default="open")
    pnl_dollars = Column(Float, nullable=True)        # realized P&L in dollars
    pnl_r = Column(Float, nullable=True)              # P&L in R multiples (1R = amount risked)
    actual_rr = Column(Float, nullable=True)          # actual RR achieved

    # ── Trade analytics ───────────────────────────────────────────────────────
    mae = Column(Float, nullable=True)  # Maximum Adverse Excursion
    mfe = Column(Float, nullable=True)  # Maximum Favorable Excursion
    mae_r = Column(Float, nullable=True)
    mfe_r = Column(Float, nullable=True)

    # ── ICC context ───────────────────────────────────────────────────────────
    htf_bias = Column(String(10), nullable=True)
    indication_type = Column(String(100), nullable=True)
    correction_zone_type = Column(String(100), nullable=True)
    continuation_trigger_type = Column(String(100), nullable=True)
    confidence_score = Column(Float, nullable=True)

    # ── Notes and media ───────────────────────────────────────────────────────
    notes = Column(Text, nullable=True)
    screenshot_urls = Column(JSON, default=list)

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Trade {self.symbol} {self.direction} {self.status}>"


class TradeReview(Base):
    """
    Post-trade review labels — filled in after a trade closes.
    This is where you label what went right/wrong for each trade.
    Over time, these labels train the system to recognize patterns.
    """
    __tablename__ = "trade_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id = Column(UUID(as_uuid=True), ForeignKey("trades.id"), nullable=False)

    # ── ICC validity ──────────────────────────────────────────────────────────
    icc_was_valid = Column(Boolean, nullable=True)       # Was the setup actually a valid ICC?
    bias_was_correct = Column(Boolean, nullable=True)    # Was the directional bias right?
    was_countertrend = Column(Boolean, nullable=True)

    # ── Error classification ──────────────────────────────────────────────────
    was_execution_mistake = Column(Boolean, nullable=True)   # You made an error executing
    was_model_mistake = Column(Boolean, nullable=True)       # The strategy rules were flawed
    had_timing_issue = Column(Boolean, nullable=True)        # Entry was early or late

    # ── Zone quality ─────────────────────────────────────────────────────────
    zone_quality = Column(String(20), nullable=True)  # excellent / good / fair / poor
    continuation_was_confirmed = Column(Boolean, nullable=True)
    continuation_was_forced = Column(Boolean, nullable=True)

    # ── Failure reasons (can have multiple) ───────────────────────────────────
    # Stored as a JSON list: ["chop", "news", "weak_indication"]
    failure_reasons = Column(JSON, default=list)

    # ── Qualitative notes ─────────────────────────────────────────────────────
    what_went_well = Column(Text, nullable=True)
    what_went_wrong = Column(Text, nullable=True)
    lesson_learned = Column(Text, nullable=True)

    # Ratings 1-5 for each phase
    indication_rating = Column(Integer, nullable=True)   # 1-5
    correction_rating = Column(Integer, nullable=True)   # 1-5
    continuation_rating = Column(Integer, nullable=True) # 1-5
    execution_rating = Column(Integer, nullable=True)    # 1-5

    reviewed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
