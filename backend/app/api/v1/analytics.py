"""
api/v1/analytics.py — Performance analytics endpoints

Aggregates trade and setup data into stats for the dashboard.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from typing import Optional

from app.db.database import get_db
from app.models.trade import Trade
from app.models.setup import SetupEvaluation

router = APIRouter()


@router.get("/summary")
async def get_analytics_summary(
    mode: str = "paper",
    symbol: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns overall performance statistics.

    This is the data for the main analytics dashboard.
    """
    query = select(Trade).where(Trade.mode == mode, Trade.status == "closed")
    if symbol:
        query = query.where(Trade.symbol == symbol)

    result = db.execute(query)
    trades = result.scalars().all()

    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "avg_rr": 0,
            "expectancy_r": 0,
            "total_pnl_r": 0,
            "avg_winner_r": 0,
            "avg_loser_r": 0,
            "profit_factor": 0,
        }

    winners = [t for t in trades if t.pnl_r and t.pnl_r > 0]
    losers = [t for t in trades if t.pnl_r and t.pnl_r <= 0]

    win_rate = len(winners) / len(trades) if trades else 0
    avg_winner = sum(t.pnl_r for t in winners) / len(winners) if winners else 0
    avg_loser = sum(t.pnl_r for t in losers) / len(losers) if losers else 0
    total_pnl_r = sum(t.pnl_r for t in trades if t.pnl_r)
    avg_rr = sum(t.actual_rr for t in trades if t.actual_rr) / len(trades)

    # Expectancy = (win_rate * avg_win) + (loss_rate * avg_loss)
    expectancy = (win_rate * avg_winner) + ((1 - win_rate) * avg_loser)

    # Profit factor = gross wins / gross losses
    gross_wins = sum(t.pnl_r for t in winners if t.pnl_r) or 0
    gross_losses = abs(sum(t.pnl_r for t in losers if t.pnl_r)) or 1
    profit_factor = gross_wins / gross_losses

    return {
        "total_trades": len(trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": round(win_rate, 3),
        "avg_rr": round(avg_rr, 2),
        "expectancy_r": round(expectancy, 2),
        "total_pnl_r": round(total_pnl_r, 2),
        "avg_winner_r": round(avg_winner, 2),
        "avg_loser_r": round(avg_loser, 2),
        "profit_factor": round(profit_factor, 2),
    }


@router.get("/by-symbol")
async def get_performance_by_symbol(mode: str = "paper", db: AsyncSession = Depends(get_db)):
    """Win rate and expectancy broken down by symbol."""
    result = db.execute(
        select(Trade).where(Trade.mode == mode, Trade.status == "closed")
    )
    trades = result.scalars().all()

    by_symbol = {}
    for t in trades:
        sym = t.symbol
        if sym not in by_symbol:
            by_symbol[sym] = {"trades": [], "symbol": sym}
        by_symbol[sym]["trades"].append(t)

    output = []
    for sym, data in by_symbol.items():
        ts = data["trades"]
        wins = [t for t in ts if t.pnl_r and t.pnl_r > 0]
        output.append({
            "symbol": sym,
            "trades": len(ts),
            "win_rate": round(len(wins) / len(ts), 3) if ts else 0,
            "total_pnl_r": round(sum(t.pnl_r for t in ts if t.pnl_r), 2),
        })

    return sorted(output, key=lambda x: x["total_pnl_r"], reverse=True)


@router.get("/by-setup-score")
async def get_performance_by_score(mode: str = "paper", db: AsyncSession = Depends(get_db)):
    """Shows whether high-confidence setups actually perform better."""
    result = db.execute(
        select(Trade).where(
            Trade.mode == mode,
            Trade.status == "closed",
            Trade.confidence_score.isnot(None),
        )
    )
    trades = result.scalars().all()

    # Group into score buckets: low (<0.5), medium (0.5-0.75), high (>0.75)
    buckets = {
        "low_0_50": [],
        "medium_50_75": [],
        "high_75_100": [],
    }

    for t in trades:
        score = t.confidence_score or 0
        if score < 0.5:
            buckets["low_0_50"].append(t)
        elif score < 0.75:
            buckets["medium_50_75"].append(t)
        else:
            buckets["high_75_100"].append(t)

    output = {}
    for bucket_name, ts in buckets.items():
        if not ts:
            continue
        wins = [t for t in ts if t.pnl_r and t.pnl_r > 0]
        output[bucket_name] = {
            "trades": len(ts),
            "win_rate": round(len(wins) / len(ts), 3),
            "avg_pnl_r": round(sum(t.pnl_r for t in ts if t.pnl_r) / len(ts), 2),
        }

    return output


@router.get("/setup-verdicts")
async def get_setup_verdict_counts(db: AsyncSession = Depends(get_db)):
    """Count of setups by verdict — how often does each verdict fire?"""
    result = db.execute(
        select(
            SetupEvaluation.verdict,
            func.count(SetupEvaluation.id).label("count")
        ).group_by(SetupEvaluation.verdict)
    )
    rows = result.fetchall()
    return [{"verdict": r[0], "count": r[1]} for r in rows]
