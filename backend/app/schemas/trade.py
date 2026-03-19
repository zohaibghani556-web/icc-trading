"""
schemas/trade.py — Pydantic schemas for trades and reviews
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class TradeCreate(BaseModel):
    """Create a new paper trade."""
    setup_id: Optional[UUID] = None
    symbol: str
    timeframe: str
    direction: str
    session: Optional[str] = None
    entry_price: float
    stop_price: float
    target_price: Optional[float] = None
    contracts: int = 1
    account_risk_dollars: Optional[float] = None
    htf_bias: Optional[str] = None
    indication_type: Optional[str] = None
    correction_zone_type: Optional[str] = None
    continuation_trigger_type: Optional[str] = None
    confidence_score: Optional[float] = None
    notes: Optional[str] = None
    mode: str = "paper"


class TradeUpdate(BaseModel):
    """Update an existing trade (e.g., to close it)."""
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_reason: Optional[str] = None
    status: Optional[str] = None
    mae: Optional[float] = None
    mfe: Optional[float] = None
    notes: Optional[str] = None


class TradeOut(BaseModel):
    """Trade as returned by the API."""
    id: UUID
    symbol: str
    timeframe: str
    direction: str
    mode: str
    status: str
    entry_price: float
    stop_price: float
    target_price: Optional[float]
    exit_price: Optional[float]
    exit_time: Optional[datetime]
    exit_reason: Optional[str]
    contracts: int
    pnl_dollars: Optional[float]
    pnl_r: Optional[float]
    actual_rr: Optional[float]
    planned_rr: Optional[float]
    mae: Optional[float]
    mfe: Optional[float]
    confidence_score: Optional[float]
    indication_type: Optional[str]
    correction_zone_type: Optional[str]
    continuation_trigger_type: Optional[str]
    entry_time: datetime
    notes: Optional[str]
    has_review: bool = False

    class Config:
        from_attributes = True


class TradeReviewCreate(BaseModel):
    """Submit a post-trade review."""
    icc_was_valid: Optional[bool] = None
    bias_was_correct: Optional[bool] = None
    was_countertrend: Optional[bool] = None
    was_execution_mistake: Optional[bool] = None
    was_model_mistake: Optional[bool] = None
    had_timing_issue: Optional[bool] = None
    zone_quality: Optional[str] = None
    continuation_was_confirmed: Optional[bool] = None
    continuation_was_forced: Optional[bool] = None
    failure_reasons: List[str] = Field(default_factory=list)
    what_went_well: Optional[str] = None
    what_went_wrong: Optional[str] = None
    lesson_learned: Optional[str] = None
    indication_rating: Optional[int] = Field(None, ge=1, le=5)
    correction_rating: Optional[int] = Field(None, ge=1, le=5)
    continuation_rating: Optional[int] = Field(None, ge=1, le=5)
    execution_rating: Optional[int] = Field(None, ge=1, le=5)
