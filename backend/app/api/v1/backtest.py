"""
api/v1/backtest.py — Backtesting API v3.0
=========================================
Receives backtest results from TradingView PineScript strategy
or manual input, stores them, generates knowledge, serves to frontend.

Flow:
  1. User runs ICC Backtest Strategy v3.0 on TradingView
  2. User submits results via POST /backtest/submit (manual or webhook)
  3. Backend stores results, generates lessons, builds knowledge base
  4. Frontend displays everything in plain English
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime
import json

from app.db.database import get_db
from app.core.config import settings

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class SessionStats(BaseModel):
    trades: int = 0
    wins: int = 0
    win_rate: Optional[float] = None

class TierStats(BaseModel):
    trades: int = 0
    wins: int = 0
    win_rate: Optional[float] = None

class SetupStats(BaseModel):
    trades: int = 0
    wins: int = 0
    win_rate: Optional[float] = None

class BacktestSubmission(BaseModel):
    """What the user submits after running TradingView backtest."""
    # Required
    symbol: str = Field(..., description="e.g. NQ1!, ES1!")
    timeframe: str = Field(default="5", description="Chart timeframe")
    period_description: str = Field(default="", description="e.g. '1 year on 5m chart'")

    # Core stats from Strategy Tester
    total_trades: int = 0
    winners: int = 0
    losers: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    expectancy: float = 0.0
    max_consec_wins: int = 0
    max_consec_losses: int = 0
    grade: str = "N/A"

    # From the PineScript dashboard — by session
    london: Optional[SessionStats] = None
    ny_open: Optional[SessionStats] = None
    ny_mid: Optional[SessionStats] = None
    ny_power: Optional[SessionStats] = None
    asia: Optional[SessionStats] = None

    # By tier
    s_tier: Optional[TierStats] = None
    a_tier: Optional[TierStats] = None
    bc_tier: Optional[TierStats] = None

    # By setup type
    bos: Optional[SetupStats] = None
    fvg: Optional[SetupStats] = None
    choch: Optional[SetupStats] = None
    liq_sweep: Optional[SetupStats] = None

    # Pine-generated lessons (text from dashboard)
    lessons: List[str] = Field(default_factory=list)

    # Strategy settings used
    min_score: int = 40
    min_rr: float = 2.0
    atr_stop_mult: float = 1.5
    rsi_min: int = 40
    rsi_max: int = 75

    # Free-form notes
    notes: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# LEARNING ENGINE — generates insights from submitted results
# ═══════════════════════════════════════════════════════════════════════════════

def generate_lessons(data: BacktestSubmission) -> List[Dict]:
    """Generate plain-English lessons from the backtest results."""
    lessons = []

    if data.total_trades < 5:
        lessons.append({
            "severity": "warning",
            "category": "general",
            "description": f"Only {data.total_trades} trades — not enough for reliable conclusions.",
            "recommendation": "Extend the chart period or loosen the min score filter.",
        })
        return lessons

    # ── Overall performance ──
    if data.win_rate >= 55 and data.profit_factor >= 1.5:
        lessons.append({
            "severity": "positive",
            "category": "performance",
            "description": f"Strategy is profitable: {data.win_rate:.1f}% win rate, {data.profit_factor:.2f}x profit factor.",
            "recommendation": "Parameters are working. Proceed to paper trading validation with 50+ trades.",
        })
    elif data.win_rate < 45:
        lessons.append({
            "severity": "critical",
            "category": "performance",
            "description": f"Win rate of {data.win_rate:.1f}% is too low for a viable strategy.",
            "recommendation": "Tighten entry criteria: raise min score to 50+, require 4H HTF alignment, or limit to S/A tier only.",
        })
    elif data.profit_factor < 1.0:
        lessons.append({
            "severity": "critical",
            "category": "performance",
            "description": f"Profit factor {data.profit_factor:.2f}x means the strategy is losing money overall.",
            "recommendation": "Major changes needed. Check if stops are too tight or targets unrealistic.",
        })
    elif data.profit_factor < 1.5:
        lessons.append({
            "severity": "warning",
            "category": "performance",
            "description": f"Profit factor {data.profit_factor:.2f}x is marginal. Barely profitable.",
            "recommendation": "Fine-tune: try different ATR stop multiplier (1.2 vs 1.5 vs 2.0) or adjust RR target.",
        })

    # ── Drawdown ──
    if data.max_drawdown > 0:
        dd_pct = (data.max_drawdown / 10000) * 100 if data.max_drawdown < 100000 else data.max_drawdown
        if data.max_drawdown > 2000:
            lessons.append({
                "severity": "critical",
                "category": "risk",
                "description": f"Max drawdown of ${data.max_drawdown:.0f} is very high.",
                "recommendation": "Reduce position size. Consider adding a daily max loss of 3 trades.",
            })

    # ── Consecutive losses ──
    if data.max_consec_losses >= 6:
        lessons.append({
            "severity": "critical",
            "category": "risk",
            "description": f"Hit {data.max_consec_losses} consecutive losses at some point.",
            "recommendation": "Add a circuit breaker: stop trading after 3-4 losses in a row. Reset the next day.",
        })

    # ── Session analysis ──
    sessions = [
        ("London", data.london),
        ("NY Open", data.ny_open),
        ("NY Power", data.ny_power),
    ]
    best_sess = None
    best_wr = 0
    worst_sess = None
    worst_wr = 100

    for name, stats in sessions:
        if stats and stats.trades >= 3:
            wr = (stats.wins / stats.trades * 100) if stats.trades > 0 else 0
            if wr > best_wr:
                best_wr = wr
                best_sess = name
            if wr < worst_wr:
                worst_wr = wr
                worst_sess = name

    if best_sess:
        lessons.append({
            "severity": "positive",
            "category": "session",
            "description": f"Best session: {best_sess} with {best_wr:.0f}% win rate.",
            "recommendation": f"Focus your trading during {best_sess}. This is your highest-probability window.",
        })

    if worst_sess and worst_wr < 40:
        lessons.append({
            "severity": "warning",
            "category": "session",
            "description": f"Worst session: {worst_sess} with only {worst_wr:.0f}% win rate.",
            "recommendation": f"Consider disabling {worst_sess} in your session filter, or require S-tier only.",
        })

    # ── Tier analysis ──
    if data.s_tier and data.s_tier.trades >= 3:
        s_wr = data.s_tier.wins / data.s_tier.trades * 100
        if s_wr >= 60:
            lessons.append({
                "severity": "positive",
                "category": "calibration",
                "description": f"S-Tier signals deliver: {s_wr:.0f}% win rate across {data.s_tier.trades} trades.",
                "recommendation": "Trust S-Tier signals. Take them with full position size.",
            })
        elif s_wr < 45:
            lessons.append({
                "severity": "critical",
                "category": "calibration",
                "description": f"S-Tier signals only winning {s_wr:.0f}% — the scoring engine needs recalibration.",
                "recommendation": "The composite score may be overweighting some factors. Review which conditions led to S-tier losers.",
            })

    if data.bc_tier and data.bc_tier.trades >= 3:
        bc_wr = data.bc_tier.wins / data.bc_tier.trades * 100
        if bc_wr < 35:
            lessons.append({
                "severity": "critical",
                "category": "calibration",
                "description": f"B/C-Tier trades are losing: {bc_wr:.0f}% win rate.",
                "recommendation": "Stop taking B/C-Tier trades. Raise min_score to 65+ to only take A and S tier.",
            })

    # ── Setup type analysis ──
    setups = [
        ("BOS (Break of Structure)", data.bos),
        ("FVG (Fair Value Gap)", data.fvg),
        ("CHoCH (Change of Character)", data.choch),
        ("Liquidity Sweep", data.liq_sweep),
    ]
    for name, stats in setups:
        if stats and stats.trades >= 3:
            wr = stats.wins / stats.trades * 100
            if wr >= 60:
                lessons.append({
                    "severity": "positive",
                    "category": "setup_type",
                    "description": f"{name} setups are strong: {wr:.0f}% win rate across {stats.trades} trades.",
                    "recommendation": f"Prioritize {name} entries — they have a proven edge.",
                })
            elif wr < 35:
                lessons.append({
                    "severity": "warning",
                    "category": "setup_type",
                    "description": f"{name} setups underperforming: {wr:.0f}% win rate.",
                    "recommendation": f"Add extra confirmation for {name} entries, or reduce size.",
                })

    # ── Win/loss ratio ──
    if data.avg_winner > 0 and data.avg_loser < 0:
        wl_ratio = abs(data.avg_winner / data.avg_loser)
        if wl_ratio < 1.0:
            lessons.append({
                "severity": "warning",
                "category": "risk",
                "description": f"Average winner (${data.avg_winner:.0f}) is smaller than average loser (${data.avg_loser:.0f}).",
                "recommendation": "Either widen your targets or tighten your stops. Aim for winners at least 1.5x your losers.",
            })
        elif wl_ratio >= 2.0:
            lessons.append({
                "severity": "positive",
                "category": "risk",
                "description": f"Great risk/reward: winners average ${data.avg_winner:.0f} vs losers ${abs(data.avg_loser):.0f} ({wl_ratio:.1f}x ratio).",
                "recommendation": "Excellent trade management. Your winners are large relative to losers.",
            })

    return lessons


def generate_recommendations(data: BacktestSubmission, lessons: List[Dict]) -> List[str]:
    """Top-level actionable recommendations."""
    recs = []

    criticals = [l for l in lessons if l["severity"] == "critical"]
    warnings = [l for l in lessons if l["severity"] == "warning"]
    positives = [l for l in lessons if l["severity"] == "positive"]

    if not criticals and len(positives) >= 2:
        recs.append("Strategy looks solid. Run 50+ paper trades to validate before going live.")
    elif criticals:
        recs.append("Fix the critical issues first before paper trading.")

    for c in criticals[:2]:
        recs.append(c["recommendation"])

    for w in warnings[:2]:
        recs.append(w["recommendation"])

    if data.total_trades < 30:
        recs.append("More data needed. Run the backtest on at least 6 months of 5-minute data.")

    return recs


def compute_grade(data: BacktestSubmission) -> str:
    """Compute strategy grade from results."""
    if data.total_trades < 5:
        return "N/A"
    score = 0
    if data.win_rate >= 55: score += 25
    elif data.win_rate >= 45: score += 15
    if data.expectancy > 0: score += 20
    if data.profit_factor >= 2.0: score += 20
    elif data.profit_factor >= 1.5: score += 12
    elif data.profit_factor >= 1.0: score += 5
    if data.max_consec_losses <= 4: score += 15
    elif data.max_consec_losses <= 6: score += 8
    if data.max_drawdown < 1000: score += 10
    elif data.max_drawdown < 2000: score += 5

    if score >= 85: return "A+"
    if score >= 70: return "A"
    if score >= 60: return "B+"
    if score >= 50: return "B"
    if score >= 35: return "C"
    return "F"


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/submit")
async def submit_backtest(
    data: BacktestSubmission,
    db: Session = Depends(get_db),
):
    """
    Submit backtest results from TradingView.
    User reads the PineScript dashboard and enters the numbers here.
    """
    # Generate analysis
    grade = data.grade if data.grade != "N/A" else compute_grade(data)
    lessons = generate_lessons(data)
    recommendations = generate_recommendations(data, lessons)

    # Build sessions breakdown
    sessions = {}
    for name, stats in [("london", data.london), ("ny_open", data.ny_open),
                         ("ny_mid", data.ny_mid), ("ny_power", data.ny_power), ("asia", data.asia)]:
        if stats and stats.trades > 0:
            sessions[name] = {
                "trades": stats.trades, "wins": stats.wins,
                "win_rate": round(stats.wins / stats.trades, 3),
            }

    # Build tier breakdown
    tiers = {}
    for name, stats in [("S", data.s_tier), ("A", data.a_tier), ("B/C", data.bc_tier)]:
        if stats and stats.trades > 0:
            tiers[name] = {
                "trades": stats.trades, "wins": stats.wins,
                "win_rate": round(stats.wins / stats.trades, 3),
            }

    # Build setup breakdown
    setups = {}
    for name, stats in [("bos", data.bos), ("fvg", data.fvg),
                         ("choch", data.choch), ("liq_sweep", data.liq_sweep)]:
        if stats and stats.trades > 0:
            setups[name] = {
                "trades": stats.trades, "wins": stats.wins,
                "win_rate": round(stats.wins / stats.trades, 3),
            }

    # Build summary
    if data.total_trades == 0:
        summary = "No trades to analyze."
    elif data.expectancy > 0:
        summary = (
            f"GRADE: {grade} — Strategy IS profitable. "
            f"{data.total_trades} trades with {data.win_rate:.1f}% win rate and "
            f"{data.profit_factor:.2f}x profit factor. "
            f"Average trade makes ${data.expectancy:.2f}."
        )
    else:
        summary = (
            f"GRADE: {grade} — Strategy is NOT profitable in current form. "
            f"{data.total_trades} trades with {data.win_rate:.1f}% win rate. "
            f"Profit factor {data.profit_factor:.2f}x. "
            f"Average trade loses ${abs(data.expectancy):.2f}."
        )

    # Store in DB
    run_id = f"tv_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{data.symbol}"
    try:
        from app.models.backtest import BacktestRun
        run = BacktestRun(
            run_id=run_id,
            symbol=data.symbol,
            period_days=0,
            config={
                "source": "tradingview",
                "timeframe": data.timeframe,
                "period": data.period_description,
                "min_score": data.min_score,
                "min_rr": data.min_rr,
                "atr_stop_mult": data.atr_stop_mult,
                "rsi_range": f"{data.rsi_min}-{data.rsi_max}",
            },
            total_trades=data.total_trades,
            winners=data.winners,
            losers=data.losers,
            win_rate=data.win_rate / 100 if data.win_rate > 1 else data.win_rate,
            expectancy_r=data.expectancy,
            profit_factor=data.profit_factor,
            total_pnl_r=data.total_pnl,
            max_drawdown_r=data.max_drawdown,
            max_consecutive_losses=data.max_consec_losses,
            grade=grade,
            executive_summary=summary,
            recommendations=recommendations,
            lessons_learned=lessons,
            knowledge_base={
                "sessions": sessions,
                "tiers": tiers,
                "setups": setups,
            },
            full_results={
                "symbol": data.symbol,
                "timeframe": data.timeframe,
                "period": data.period_description,
                "total_trades": data.total_trades,
                "winners": data.winners,
                "losers": data.losers,
                "win_rate": data.win_rate,
                "profit_factor": data.profit_factor,
                "total_pnl": data.total_pnl,
                "max_drawdown": data.max_drawdown,
                "avg_winner": data.avg_winner,
                "avg_loser": data.avg_loser,
                "expectancy": data.expectancy,
                "max_consec_wins": data.max_consec_wins,
                "max_consec_losses": data.max_consec_losses,
                "grade": grade,
                "by_session": sessions,
                "by_tier": tiers,
                "by_setup": setups,
                "lessons": lessons,
                "recommendations": recommendations,
                "executive_summary": summary,
                "notes": data.notes,
                "config": {
                    "min_score": data.min_score,
                    "min_rr": data.min_rr,
                    "atr_stop_mult": data.atr_stop_mult,
                },
            },
            status="complete",
            completed_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
    except Exception as e:
        print(f"[BACKTEST] DB save error: {e}")

    return {
        "run_id": run_id,
        "grade": grade,
        "executive_summary": summary,
        "lessons": lessons,
        "recommendations": recommendations,
        "by_session": sessions,
        "by_tier": tiers,
        "by_setup": setups,
    }


@router.get("/results")
async def list_backtest_results(
    symbol: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List all backtest runs."""
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
            "status": r.status,
            "grade": r.grade,
            "total_trades": r.total_trades,
            "win_rate": r.win_rate,
            "expectancy_r": r.expectancy_r,
            "profit_factor": r.profit_factor,
            "total_pnl_r": r.total_pnl_r,
            "max_drawdown_r": r.max_drawdown_r,
            "executive_summary": (r.executive_summary or "")[:300],
            "lessons_count": len(r.lessons_learned or []),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "config": r.config,
        }
        for r in runs
    ]


@router.get("/results/{run_id}")
async def get_backtest_result(run_id: str, db: Session = Depends(get_db)):
    """Get full results for a specific backtest run."""
    from app.models.backtest import BacktestRun

    result = db.execute(select(BacktestRun).where(BacktestRun.run_id == run_id))
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    return {
        "run_id": run.run_id,
        "symbol": run.symbol,
        "status": run.status,
        "grade": run.grade,
        "executive_summary": run.executive_summary,
        "recommendations": run.recommendations,
        "lessons": run.lessons_learned,
        "results": run.full_results,
        "knowledge": run.knowledge_base,
        "config": run.config,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/knowledge/{symbol}")
async def get_knowledge(symbol: str, db: Session = Depends(get_db)):
    """Get accumulated knowledge for a symbol — used by live signal evaluation."""
    from app.models.backtest import BacktestRun

    # Get latest completed run for this symbol
    result = db.execute(
        select(BacktestRun).where(
            BacktestRun.symbol.contains(symbol),
            BacktestRun.status == "complete",
        ).order_by(desc(BacktestRun.created_at)).limit(1)
    )
    run = result.scalar_one_or_none()

    if not run:
        return {"symbol": symbol, "has_knowledge": False}

    return {
        "symbol": symbol,
        "has_knowledge": True,
        "grade": run.grade,
        "win_rate": run.win_rate,
        "lessons": run.lessons_learned,
        "knowledge": run.knowledge_base,
        "last_updated": run.created_at.isoformat() if run.created_at else None,
    }


# Keep old endpoints for backwards compatibility
@router.get("/status/{run_id}")
async def get_backtest_status(run_id: str, db: Session = Depends(get_db)):
    """Backwards-compatible status endpoint."""
    from app.models.backtest import BacktestRun
    result = db.execute(select(BacktestRun).where(BacktestRun.run_id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        return {"status": "not_found", "run_id": run_id}
    return {
        "status": run.status or "complete",
        "run_id": run.run_id,
        "results": run.full_results,
    }
