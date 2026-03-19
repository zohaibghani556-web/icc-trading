"""
models/instrument.py

Stores the spec for each tradeable futures contract.
Tick size, tick value, exchange, etc.
The ICC engine uses this to validate symbols and compute correct dollar risk.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol     = Column(String(20), unique=True, nullable=False, index=True)
    name       = Column(String(100), nullable=False)
    exchange   = Column(String(50), nullable=True)
    asset_class = Column(String(50), nullable=True)   # equity_index / energy / metal
    tick_size  = Column(Float, nullable=True)
    tick_value = Column(Float, nullable=True)          # dollars per tick
    is_micro   = Column(Boolean, default=False)
    is_active  = Column(Boolean, default=True)
    sessions   = Column(JSON, nullable=True)           # {"regular": ["09:30","16:00"]}
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Instrument {self.symbol}>"
