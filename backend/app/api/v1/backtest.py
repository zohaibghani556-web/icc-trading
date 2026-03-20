"""
api/v1/backtest.py — Backtesting API endpoints
"""

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio

from app.db.database import get_db
from app.core.config import settings

router = APIRouter()

# Store running/completed backtest results in memory
backtest_results: Dict[str, Any] = {}
backtest_status: Dict[str, str] = {}


@router.post("/run")
async def run_backtest(
    background_tasks: BackgroundTasks,
    symbol: str = "NQ",
    days: int = 365,
    min_rr: float = 2.5,
    require_4h_bias: bool = True,
    require_volume: bool = False,
    rsi_min: int = 48,
    rsi_max: int = 75,
    session_filter: str = "us_regular",
    db: Session = Depends(get_db),
):
    """Start a backtest run in the background."""
    run_id = f"bt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    backtest_status[run_id] = "running"

    config = {
        "min_rr": min_rr,
        "require_4h_bias": require_4h_bias,
        "require_volume": require_volume,
        "allowed_sessions": [session_filter] if session_filter != "all" else ["us_regular", "us_premarket"],
        "rsi_min": rsi_min,
        "rsi_max": rsi_max,
        "ai_confidence_threshold": 0.65,
    }

    background_tasks.add_task(
        _run_backtest_task, run_id, symbol, days, config
    )

    return {
        "run_id": run_id,
        "status": "started",
        "message": f"Backtesting {symbol} for {days} days. Check /backtest/status/{run_id} for results.",
        "config": config,
    }


async def _run_backtest_task(run_id: str, symbol: str, days: int, config: Dict):
    """Background task that runs the backtest."""
    try:
        from app.services.backtester.engine import ICCBacktester

        backtester = ICCBacktester(
            polygon_api_key=settings.POLYGON_API_KEY,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
        )

        result = await backtester.run(symbol=symbol, days=days, config=config)

        backtest_results[run_id] = result
        backtest_status[run_id] = "complete"

    except Exception as e:
        backtest_status[run_id] = "failed"
        backtest_results[run_id] = {"error": str(e)}


@router.get("/status/{run_id}")
async def get_backtest_status(run_id: str):
    """Check status and get results of a backtest run."""
    status = backtest_status.get(run_id, "not_found")

    if status == "not_found":
        return {"status": "not_found", "run_id": run_id}

    if status == "running":
        return {"status": "running", "run_id": run_id, "message": "Backtest in progress..."}

    if status == "failed":
        return {
            "status": "failed",
            "run_id": run_id,
            "error": backtest_results.get(run_id, {}).get("error", "Unknown error"),
        }

    return {
        "status": "complete",
        "run_id": run_id,
        "results": backtest_results.get(run_id, {}),
    }


@router.get("/results")
async def list_backtest_results():
    """List all completed backtest runs."""
    return [
        {
            "run_id": run_id,
            "status": backtest_status[run_id],
            "summary": {
                "symbol": backtest_results[run_id].get("symbol"),
                "win_rate": backtest_results[run_id].get("win_rate"),
                "total_trades": backtest_results[run_id].get("total_trades"),
                "expectancy_r": backtest_results[run_id].get("expectancy_r"),
            } if backtest_status[run_id] == "complete" else None,
        }
        for run_id in backtest_status
    ]


def _get_best_hours(by_hour: Dict) -> list:
    """Return top 3 hours by win rate with minimum 5 trades."""
    qualified = {
        h: v for h, v in by_hour.items()
        if v.get("trades", 0) >= 5
    }
    sorted_hours = sorted(qualified.items(), key=lambda x: x[1].get("win_rate", 0), reverse=True)
    return [
        {"hour": f"{h}:00 ET", "win_rate": f"{v['win_rate']*100:.1f}%", "trades": v["trades"]}
        for h, v in sorted_hours[:3]
    ]


def _get_worst_hours(by_hour: Dict) -> list:
    qualified = {
        h: v for h, v in by_hour.items()
        if v.get("trades", 0) >= 5
    }
    sorted_hours = sorted(qualified.items(), key=lambda x: x[1].get("win_rate", 0))
    return [
        {"hour": f"{h}:00 ET", "win_rate": f"{v['win_rate']*100:.1f}%", "trades": v["trades"]}
        for h, v in sorted_hours[:3]
    ]


def _generate_recommendation(result) -> str:
    """Generate plain-English recommendation based on results."""
    if result.total_trades < 10:
        return "Not enough trades to make a recommendation. Try relaxing the filters."

    recs = []

    if result.win_rate >= 0.55 and result.profit_factor >= 1.5:
        recs.append("Strategy is profitable. Continue with current parameters.")
    elif result.win_rate < 0.45:
        recs.append("Win rate is low. Consider tightening entry criteria.")

    if result.max_consecutive_losses >= 6:
        recs.append("High max consecutive losses. Consider adding a daily loss limit.")

    best_hours = _get_best_hours(result.by_hour)
    if best_hours:
        hours_str = ", ".join([h["hour"] for h in best_hours])
        recs.append(f"Best performing hours: {hours_str}.")

    if result.avg_mfe > result.avg_mae * 2:
        recs.append("Good MFE/MAE ratio — consider trailing stops to capture more profit.")

    return " ".join(recs) if recs else "Results are inconclusive. Run more parameter variations."
