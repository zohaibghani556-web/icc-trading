"""
api/v1/backtest.py — Backtesting API endpoints v2.0
Full learning-enabled backtester with persistent knowledge base.
"""

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import traceback

from app.db.database import get_db, SyncSessionLocal
from app.core.config import settings

router = APIRouter()


@router.post("/run")
async def run_backtest(
    background_tasks: BackgroundTasks,
    symbol: str = "NQ",
    days: int = 60,
    min_rr: float = 2.0,
    min_score: int = 40,
    require_4h_bias: bool = False,
    require_volume: bool = False,
    rsi_min: int = 40,
    rsi_max: int = 75,
    atr_stop_mult: float = 1.5,
    t2_rr: float = 3.0,
    t3_rr: float = 5.0,
    session_filter: str = "all",
    db: Session = Depends(get_db),
):
    """Start a backtest run in the background with full learning."""
    run_id = f"bt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{symbol}"

    sessions = (
        ["ny_open", "ny_mid", "ny_power", "london", "overlap"]
        if session_filter == "all"
        else [session_filter]
    )

    config = {
        "min_rr": min_rr,
        "min_score": min_score,
        "require_4h_bias": require_4h_bias,
        "require_volume": require_volume,
        "allowed_sessions": sessions,
        "rsi_min": rsi_min,
        "rsi_max": rsi_max,
        "atr_stop_mult": atr_stop_mult,
        "t2_rr": t2_rr,
        "t3_rr": t3_rr,
    }

    # Store initial run record
    try:
        from app.models.backtest import BacktestRun
        run_record = BacktestRun(
            run_id=run_id,
            symbol=symbol,
            period_days=days,
            config=config,
            status="running",
        )
        db.add(run_record)
        db.commit()
    except Exception as e:
        print(f"[BACKTEST] Could not persist run record: {e}")

    background_tasks.add_task(_run_backtest_task, run_id, symbol, days, config)

    return {
        "run_id": run_id,
        "status": "started",
        "message": f"Backtesting {symbol} over {days} days with learning engine. Check /backtest/status/{run_id}",
        "config": config,
    }


async def _run_backtest_task(run_id: str, symbol: str, days: int, config: Dict):
    """Background task that runs the full learning backtester."""
    try:
        from app.services.backtester.engine import ICCBacktester

        backtester = ICCBacktester(
            polygon_api_key=settings.POLYGON_API_KEY,
            anthropic_api_key=settings.ANTHROPIC_API_KEY,
        )

        result = await backtester.run(symbol=symbol, days=days, config=config)

        # Persist results
        db = SyncSessionLocal()
        try:
            from app.models.backtest import BacktestRun, BacktestKnowledge

            run_result = db.execute(
                select(BacktestRun).where(BacktestRun.run_id == run_id)
            )
            run_record = run_result.scalar_one_or_none()
            if run_record:
                if "error" in result:
                    run_record.status = "failed"
                    run_record.error = result.get("error", "Unknown error")
                else:
                    run_record.status = "complete"
                    run_record.total_bars = result.get("total_bars", 0)
                    run_record.total_trades = result.get("total_trades", 0)
                    run_record.winners = result.get("winners", 0)
                    run_record.losers = result.get("losers", 0)
                    run_record.win_rate = result.get("win_rate", 0)
                    run_record.expectancy_r = result.get("expectancy_r", 0)
                    run_record.profit_factor = result.get("profit_factor", 0)
                    run_record.total_pnl_r = result.get("total_pnl_r", 0)
                    run_record.max_drawdown_r = result.get("max_drawdown_r", 0)
                    run_record.max_consecutive_losses = result.get("max_consecutive_losses", 0)
                    run_record.grade = result.get("grade", "N/A")
                    run_record.executive_summary = result.get("executive_summary", "")
                    run_record.detailed_report = result.get("detailed_report", "")
                    run_record.recommendations = result.get("recommendations", [])
                    run_record.lessons_learned = result.get("lessons_learned", [])
                    run_record.knowledge_base = result.get("knowledge_base", {})
                    run_record.full_results = result
                    run_record.completed_at = datetime.utcnow()

                    # Update global knowledge base
                    _update_knowledge_base(db, symbol, result)

                db.commit()
                print(f"[BACKTEST] Results saved for {run_id}")
        except Exception as e:
            print(f"[BACKTEST] DB save error: {e}")
            traceback.print_exc()
            db.rollback()
        finally:
            db.close()

    except Exception as e:
        print(f"[BACKTEST] Fatal error: {e}")
        traceback.print_exc()
        # Try to update status
        db = SyncSessionLocal()
        try:
            from app.models.backtest import BacktestRun
            run_result = db.execute(select(BacktestRun).where(BacktestRun.run_id == run_id))
            rec = run_result.scalar_one_or_none()
            if rec:
                rec.status = "failed"
                rec.error = str(e)
                db.commit()
        except:
            db.rollback()
        finally:
            db.close()


def _update_knowledge_base(db, symbol: str, result: Dict):
    """Merge this backtest's knowledge into the global knowledge base for the symbol."""
    from app.models.backtest import BacktestKnowledge

    existing = db.execute(
        select(BacktestKnowledge).where(
            BacktestKnowledge.symbol == symbol,
            BacktestKnowledge.is_active == True,
        )
    ).scalar_one_or_none()

    kb = result.get("knowledge_base", {})

    if not existing:
        existing = BacktestKnowledge(symbol=symbol)
        db.add(existing)

    existing.total_runs_analyzed = (existing.total_runs_analyzed or 0) + 1
    existing.total_trades_analyzed = (existing.total_trades_analyzed or 0) + result.get("total_trades", 0)
    existing.overall_win_rate = result.get("win_rate", 0)

    # Merge best/worst lists
    existing.best_setup_types = kb.get("best_setup_types", existing.best_setup_types or [])
    existing.worst_setup_types = kb.get("worst_setup_types", existing.worst_setup_types or [])
    existing.best_hours_utc = kb.get("best_hours", existing.best_hours_utc or [])
    existing.worst_hours_utc = kb.get("worst_hours", existing.worst_hours_utc or [])

    existing.score_vs_outcome = result.get("by_score_bucket", existing.score_vs_outcome or {})
    existing.avg_mfe_winners = result.get("avg_mfe_winners", 0)
    existing.avg_mae_losers = result.get("avg_mae_losers", 0)
    existing.lessons = result.get("lessons_learned", [])
    existing.knowledge_blob = kb
    existing.updated_at = datetime.utcnow()


@router.get("/status/{run_id}")
async def get_backtest_status(run_id: str, db: Session = Depends(get_db)):
    """Check status and get results of a backtest run."""
    from app.models.backtest import BacktestRun

    result = db.execute(select(BacktestRun).where(BacktestRun.run_id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        return {"status": "not_found", "run_id": run_id}

    if run.status == "running":
        return {"status": "running", "run_id": run_id, "message": "Backtest in progress..."}

    if run.status == "failed":
        return {"status": "failed", "run_id": run_id, "error": run.error}

    return {
        "status": "complete",
        "run_id": run_id,
        "results": run.full_results,
    }


@router.get("/results")
async def list_backtest_results(
    symbol: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List all backtest runs with summaries."""
    from app.models.backtest import BacktestRun

    query = select(BacktestRun).order_by(desc(BacktestRun.created_at))
    if symbol:
        query = query.where(BacktestRun.symbol == symbol)
    query = query.limit(limit)

    result = db.execute(query)
    runs = result.scalars().all()

    return [
        {
            "run_id": r.run_id,
            "symbol": r.symbol,
            "period_days": r.period_days,
            "status": r.status,
            "grade": r.grade,
            "total_trades": r.total_trades,
            "win_rate": r.win_rate,
            "expectancy_r": r.expectancy_r,
            "profit_factor": r.profit_factor,
            "total_pnl_r": r.total_pnl_r,
            "max_drawdown_r": r.max_drawdown_r,
            "executive_summary": (r.executive_summary or "")[:200],
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "config": r.config,
        }
        for r in runs
    ]


@router.get("/knowledge/{symbol}")
async def get_knowledge_base(symbol: str, db: Session = Depends(get_db)):
    """Get accumulated knowledge for a symbol — used by live signal evaluation."""
    from app.models.backtest import BacktestKnowledge

    result = db.execute(
        select(BacktestKnowledge).where(
            BacktestKnowledge.symbol == symbol,
            BacktestKnowledge.is_active == True,
        )
    )
    kb = result.scalar_one_or_none()

    if not kb:
        return {"symbol": symbol, "has_knowledge": False, "message": "No backtest data yet. Run a backtest first."}

    return {
        "symbol": symbol,
        "has_knowledge": True,
        "total_runs": kb.total_runs_analyzed,
        "total_trades": kb.total_trades_analyzed,
        "overall_win_rate": kb.overall_win_rate,
        "best_setup_types": kb.best_setup_types,
        "worst_setup_types": kb.worst_setup_types,
        "best_hours_utc": kb.best_hours_utc,
        "worst_hours_utc": kb.worst_hours_utc,
        "score_vs_outcome": kb.score_vs_outcome,
        "lessons": kb.lessons,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
    }


@router.get("/compare")
async def compare_runs(
    run_ids: str = "",
    db: Session = Depends(get_db),
):
    """Compare multiple backtest runs side by side."""
    from app.models.backtest import BacktestRun

    ids = [r.strip() for r in run_ids.split(",") if r.strip()]
    if not ids:
        return {"error": "Provide run_ids as comma-separated list"}

    results = []
    for rid in ids:
        run = db.execute(select(BacktestRun).where(BacktestRun.run_id == rid)).scalar_one_or_none()
        if run and run.status == "complete":
            results.append({
                "run_id": run.run_id,
                "symbol": run.symbol,
                "config": run.config,
                "win_rate": run.win_rate,
                "expectancy_r": run.expectancy_r,
                "profit_factor": run.profit_factor,
                "total_pnl_r": run.total_pnl_r,
                "max_drawdown_r": run.max_drawdown_r,
                "grade": run.grade,
                "total_trades": run.total_trades,
            })

    return {"runs": results, "count": len(results)}
