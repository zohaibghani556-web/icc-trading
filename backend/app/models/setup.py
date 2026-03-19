"""
models/setup.py — ICC Setup Evaluation

Every time the ICC engine evaluates a signal, it creates a SetupEvaluation.
This is the core scoring record — it captures every decision and its reasoning.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, Text, JSON, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class SetupEvaluation(Base):
    """
    The result of running the ICC rule engine on a signal.

    verdict options:
      - "valid_trade"    → all ICC criteria met, entry recommended
      - "watch_only"     → some criteria met, monitor but don't enter
      - "invalid_setup"  → failed one or more required checks
    """
    __tablename__ = "setup_evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"), nullable=True)

    # ── Instrument context ──────────────────────────────────────────────────
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    direction = Column(String(10), nullable=False)
    session = Column(String(50), nullable=True)
    htf_bias = Column(String(10), nullable=True)

    # ── ICC verdict ─────────────────────────────────────────────────────────
    verdict = Column(String(30), nullable=False)  # valid_trade / watch_only / invalid_setup

    # ── Individual category scores (0-100) ──────────────────────────────────
    environment_score = Column(Integer, nullable=False, default=0)
    indication_score = Column(Integer, nullable=False, default=0)
    correction_score = Column(Integer, nullable=False, default=0)
    continuation_score = Column(Integer, nullable=False, default=0)
    risk_score = Column(Integer, nullable=False, default=0)

    # ── Overall confidence ───────────────────────────────────────────────────
    confidence_score = Column(Float, nullable=False, default=0.0)  # 0.0 to 1.0

    # ── What was detected ───────────────────────────────────────────────────
    indication_type = Column(String(100), nullable=True)
    correction_zone_type = Column(String(100), nullable=True)
    continuation_trigger_type = Column(String(100), nullable=True)

    # ── Trade parameters (if verdict = valid_trade) ──────────────────────────
    entry_price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    risk_reward = Column(Float, nullable=True)

    # ── Full explanation — exactly why it passed or failed ───────────────────
    # This is a JSON object with keys: passed_rules, failed_rules, warnings, explanation
    explanation = Column(JSON, nullable=False, default=dict)

    # ── Score breakdown for the UI ───────────────────────────────────────────
    score_breakdown = Column(JSON, nullable=False, default=dict)

    # ── Flags ────────────────────────────────────────────────────────────────
    is_countertrend = Column(Boolean, default=False)
    has_htf_alignment = Column(Boolean, default=False)
    invalidation_level = Column(Float, nullable=True)

    # ── Screenshot URLs ──────────────────────────────────────────────────────
    screenshot_urls = Column(JSON, default=list)  # list of URLs

    # ── Notes ────────────────────────────────────────────────────────────────
    notes = Column(Text, nullable=True)

    # ── Timestamps ───────────────────────────────────────────────────────────
    evaluated_at = Column(DateTime, default=datetime.utcnow, index=True)
    signal_timestamp = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<SetupEvaluation {self.symbol} {self.verdict} score={self.confidence_score:.2f}>"
