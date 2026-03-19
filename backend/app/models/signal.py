"""
models/signal.py — Normalized signal events

After a raw alert is received and validated, it becomes a Signal.
Signals are cleaned, normalized, and ready for ICC evaluation.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class Signal(Base):
    """
    A normalized, validated trading signal derived from a raw alert.
    One raw alert → one Signal → zero or one SetupEvaluation.
    """
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Link back to the raw alert that created this
    raw_alert_id = Column(UUID(as_uuid=True), ForeignKey("raw_alerts.id"), nullable=True)

    # ── Instrument ─────────────────────────────────────────────────────────
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)  # "5", "15", "60"

    # ── Direction and type ─────────────────────────────────────────────────
    direction = Column(String(10), nullable=False)  # bullish / bearish
    signal_type = Column(String(50), nullable=False)  # indication / correction / continuation
    indication_type = Column(String(100), nullable=True)  # structure_break_high, etc.

    # ── Price data ─────────────────────────────────────────────────────────
    price = Column(Float, nullable=False)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)

    # ── Context ────────────────────────────────────────────────────────────
    htf_bias = Column(String(10), nullable=True)   # higher timeframe bias
    session = Column(String(50), nullable=True)     # us_regular, globex, etc.
    notes = Column(Text, nullable=True)

    # ── Timestamps ─────────────────────────────────────────────────────────
    signal_timestamp = Column(DateTime, nullable=False)   # when the signal occurred
    received_at = Column(DateTime, default=datetime.utcnow)

    # ── Status ─────────────────────────────────────────────────────────────
    evaluated = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Signal {self.symbol} {self.direction} {self.signal_type}>"
