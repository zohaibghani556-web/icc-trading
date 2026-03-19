"""
models/alert.py — Raw TradingView alert storage

Every webhook payload is stored exactly as received.
This is your audit log and the source of truth for all signal data.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class RawAlert(Base):
    """
    Stores the raw JSON payload exactly as TradingView sent it.
    Nothing is discarded — this is your complete audit trail.
    """
    __tablename__ = "raw_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # The full JSON payload from TradingView
    payload = Column(JSON, nullable=False)

    # Extracted fields for quick querying
    symbol = Column(String(20), nullable=True, index=True)
    timeframe = Column(String(10), nullable=True)
    direction = Column(String(10), nullable=True)  # bullish / bearish
    signal_type = Column(String(50), nullable=True)  # indication / correction / continuation
    price = Column(Float, nullable=True)

    # Request metadata
    source_ip = Column(String(50), nullable=True)
    webhook_token_valid = Column(Boolean, default=False)

    # Processing status
    processed = Column(Boolean, default=False)
    processing_error = Column(Text, nullable=True)

    received_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<RawAlert {self.symbol} {self.direction} @ {self.received_at}>"
