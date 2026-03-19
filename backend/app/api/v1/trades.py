"""
api/v1/trades.py — Trade management (paper trading and reviews)

All trades in MVP are paper trades.
Live broker integration is designed for later — the data model is ready.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.db.database import get_db
from app.models.trade import Trade, TradeReview
from app.schemas.trade import TradeCreate, TradeUpdate, TradeOut, TradeReviewCreate

router = APIRouter()


@router.post("/", response_model=TradeOut)
async def create_trade(trade_in: TradeCreate, db: AsyncSession = Depends(get_db)):
    """
    Open a new paper trade.

    Computes planned RR automatically from entry/stop/target.
    """
    planned_rr = None
    if trade_in.entry_price and trade_in.stop_price and trade_in.target_price:
        risk = abs(trade_in.entry_price - trade_in.stop_price)
        reward = abs(trade_in.target_price - trade_in.entry_price)
        if risk > 0:
            planned_rr = round(reward / risk, 2)

    trade = Trade(
        setup_id=trade_in.setup_id,
        mode=trade_in.mode,
        symbol=trade_in.symbol,
        timeframe=trade_in.timeframe,
        direction=trade_in.direction,
        session=trade_in.session,
        entry_price=trade_in.entry_price,
        entry_time=datetime.utcnow(),
        contracts=trade_in.contracts,
        stop_price=trade_in.stop_price,
        target_price=trade_in.target_price,
        planned_rr=planned_rr,
        account_risk_dollars=trade_in.account_risk_dollars,
        htf_bias=trade_in.htf_bias,
        indication_type=trade_in.indication_type,
        correction_zone_type=trade_in.correction_zone_type,
        continuation_trigger_type=trade_in.continuation_trigger_type,
        confidence_score=trade_in.confidence_score,
        notes=trade_in.notes,
        status="open",
    )
    db.add(trade)
    db.flush()

    return {**trade.__dict__, "has_review": False}


@router.get("/", response_model=List[TradeOut])
async def list_trades(
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    mode: str = "paper",
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List all trades with optional filters."""
    query = select(Trade).where(Trade.mode == mode).order_by(desc(Trade.entry_time))

    if status:
        query = query.where(Trade.status == status)
    if symbol:
        query = query.where(Trade.symbol == symbol)

    query = query.limit(limit)
    result = db.execute(query)
    trades = result.scalars().all()

    # Check which have reviews
    trade_ids = [t.id for t in trades]
    reviews_result = db.execute(
        select(TradeReview.trade_id).where(TradeReview.trade_id.in_(trade_ids))
    )
    reviewed_ids = {row[0] for row in reviews_result.fetchall()}

    return [{**t.__dict__, "has_review": t.id in reviewed_ids} for t in trades]


@router.get("/{trade_id}", response_model=TradeOut)
async def get_trade(trade_id: UUID, db: AsyncSession = Depends(get_db)):
    result = db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    review_result = db.execute(
        select(TradeReview).where(TradeReview.trade_id == trade_id)
    )
    has_review = review_result.scalar_one_or_none() is not None
    return {**trade.__dict__, "has_review": has_review}


@router.patch("/{trade_id}/close")
async def close_trade(
    trade_id: UUID,
    update: TradeUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Close a paper trade and compute P&L.

    P&L is computed in both dollar terms (if account_risk_dollars is set)
    and in R multiples (1R = amount risked on the trade).
    """
    result = db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    if trade.status == "closed":
        raise HTTPException(status_code=400, detail="Trade is already closed")

    # Apply updates
    if update.exit_price:
        trade.exit_price = update.exit_price
    if update.exit_time:
        trade.exit_time = update.exit_time
    else:
        trade.exit_time = datetime.utcnow()
    if update.exit_reason:
        trade.exit_reason = update.exit_reason
    if update.mae is not None:
        trade.mae = update.mae
    if update.mfe is not None:
        trade.mfe = update.mfe
    if update.notes:
        trade.notes = update.notes

    trade.status = "closed"

    # Compute P&L
    if trade.exit_price and trade.entry_price:
        direction_multiplier = 1 if trade.direction == "long" or trade.direction == "bullish" else -1
        pnl_points = (trade.exit_price - trade.entry_price) * direction_multiplier

        # Risk in points
        risk_points = abs(trade.entry_price - trade.stop_price)
        if risk_points > 0:
            trade.actual_rr = round(pnl_points / risk_points, 2)
            trade.pnl_r = round(pnl_points / risk_points, 2)

        # Dollar P&L (approximate — no multiplier without instrument spec)
        if trade.account_risk_dollars and risk_points > 0:
            trade.pnl_dollars = round(
                trade.account_risk_dollars * (pnl_points / risk_points), 2
            )

    return {"closed": True, "pnl_r": trade.pnl_r, "pnl_dollars": trade.pnl_dollars}


@router.post("/{trade_id}/review")
async def submit_review(
    trade_id: UUID,
    review_in: TradeReviewCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit a post-trade review with labels and notes."""
    trade_result = db.execute(select(Trade).where(Trade.id == trade_id))
    trade = trade_result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    # Remove existing review if any
    existing = db.execute(
        select(TradeReview).where(TradeReview.trade_id == trade_id)
    )
    existing_review = existing.scalar_one_or_none()
    if existing_review:
        db.delete(existing_review)

    review = TradeReview(
        trade_id=trade_id,
        **review_in.model_dump(),
    )
    db.add(review)
    return {"submitted": True}


@router.get("/{trade_id}/review")
async def get_review(trade_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get the post-trade review for a trade."""
    result = db.execute(
        select(TradeReview).where(TradeReview.trade_id == trade_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="No review found for this trade")
    return review
