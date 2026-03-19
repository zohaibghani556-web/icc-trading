"""
schemas/alert.py — Pydantic schemas for TradingView alerts

These define the expected shape of data coming in and going out.
Pydantic validates and type-checks everything automatically.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class WebhookAlertPayload(BaseModel):
    """
    The JSON payload received from TradingView webhook.
    All fields except symbol, direction, signal_type, and price are optional
    so that simple alerts still work.
    """
    symbol: str = Field(..., description="e.g. ES1!, NQ1!")
    timeframe: str = Field(..., description="Candle timeframe in minutes, e.g. '5'")
    direction: str = Field(..., description="'bullish' or 'bearish'")
    signal_type: str = Field(..., description="'indication', 'correction', 'continuation', or 'setup_complete'")
    price: float = Field(..., description="Current price (use {{close}} in TradingView)")

    # Optional enrichment
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    htf_bias: Optional[str] = None        # 'bullish', 'bearish', or 'neutral'
    session: Optional[str] = None
    indication_type: Optional[str] = None
    correction_zone_type: Optional[str] = None
    continuation_trigger_type: Optional[str] = None
    retracement_pct: Optional[float] = None
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    notes: Optional[str] = None
    timestamp: Optional[str] = None       # ISO format string from TradingView

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v):
        if v.lower() not in ("bullish", "bearish"):
            raise ValueError("direction must be 'bullish' or 'bearish'")
        return v.lower()

    @field_validator("signal_type")
    @classmethod
    def validate_signal_type(cls, v):
        valid = ("indication", "correction", "continuation", "setup_complete")
        if v.lower() not in valid:
            raise ValueError(f"signal_type must be one of: {', '.join(valid)}")
        return v.lower()


class AlertResponse(BaseModel):
    """Response returned after receiving a webhook."""
    received: bool
    alert_id: str
    symbol: str
    verdict: Optional[str] = None          # Immediate ICC verdict if evaluated
    confidence_score: Optional[float] = None
    message: str

    class Config:
        from_attributes = True


class SignalOut(BaseModel):
    """Normalized signal as returned by the API."""
    id: UUID
    symbol: str
    timeframe: str
    direction: str
    signal_type: str
    indication_type: Optional[str]
    price: float
    htf_bias: Optional[str]
    session: Optional[str]
    signal_timestamp: datetime
    received_at: datetime
    evaluated: bool

    class Config:
        from_attributes = True


class SetupEvaluationOut(BaseModel):
    """ICC setup evaluation result as returned by the API."""
    id: UUID
    symbol: str
    timeframe: str
    direction: str
    verdict: str
    environment_score: int
    indication_score: int
    correction_score: int
    continuation_score: int
    risk_score: int
    confidence_score: float
    indication_type: Optional[str]
    correction_zone_type: Optional[str]
    continuation_trigger_type: Optional[str]
    entry_price: Optional[float]
    stop_price: Optional[float]
    target_price: Optional[float]
    risk_reward: Optional[float]
    explanation: Dict[str, Any]
    score_breakdown: Dict[str, Any]
    is_countertrend: bool
    has_htf_alignment: bool
    evaluated_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True
