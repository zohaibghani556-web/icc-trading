"""
models/backtest.py — Backtest run and knowledge persistence

Stores backtest results, lessons learned, and the knowledge base
that gets fed into live signal evaluation.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, Text, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class BacktestRun(Base):
    """Stores a complete backtest run with all results."""
    __tablename__ = "backtest_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    period_days = Column(Integer, nullable=False)
    total_bars = Column(Integer, default=0)

    # Config used
    config = Column(JSON, default=dict)

    # Core stats
    total_trades = Column(Integer, default=0)
    winners = Column(Integer, default=0)
    losers = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    expectancy_r = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    total_pnl_r = Column(Float, default=0.0)
    max_drawdown_r = Column(Float, default=0.0)
    max_consecutive_losses = Column(Integer, default=0)
    grade = Column(String(5), default="N/A")

    # Reports
    executive_summary = Column(Text, default="")
    detailed_report = Column(Text, default="")
    recommendations = Column(JSON, default=list)

    # Full results blob
    full_results = Column(JSON, default=dict)

    # Learning
    lessons_learned = Column(JSON, default=list)
    knowledge_base = Column(JSON, default=dict)

    # Status
    status = Column(String(20), default="running")  # running, complete, failed
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<BacktestRun {self.run_id} {self.symbol} {self.status}>"


class BacktestKnowledge(Base):
    """
    Accumulated knowledge from all backtests.
    This is what live signals query to adjust their confidence.
    """
    __tablename__ = "backtest_knowledge"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    is_active = Column(Boolean, default=True)

    # Aggregated from all backtest runs
    total_runs_analyzed = Column(Integer, default=0)
    total_trades_analyzed = Column(Integer, default=0)
    overall_win_rate = Column(Float, default=0.0)

    # Best/worst patterns
    best_setup_types = Column(JSON, default=list)
    worst_setup_types = Column(JSON, default=list)
    best_hours_utc = Column(JSON, default=list)
    worst_hours_utc = Column(JSON, default=list)
    best_sessions = Column(JSON, default=list)
    worst_sessions = Column(JSON, default=list)

    # Score calibration
    score_vs_outcome = Column(JSON, default=dict)  # {"80+": {"wr": 0.7, "n": 50}, ...}

    # Risk insights
    optimal_stop_r = Column(Float, default=1.5)
    optimal_target_r = Column(Float, default=2.0)
    avg_mfe_winners = Column(Float, default=0.0)
    avg_mae_losers = Column(Float, default=0.0)

    # All lessons (merged from all runs)
    lessons = Column(JSON, default=list)

    # Raw knowledge blob
    knowledge_blob = Column(JSON, default=dict)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<BacktestKnowledge {self.symbol} runs={self.total_runs_analyzed}>"
