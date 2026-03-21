"""
ICC Backtesting Engine v3.0 — Self-Learning Backtester
=====================================================
Features:
  - Full ICC framework simulation on historical bars
  - Pattern recognition: learns which setups win/lose and WHY
  - Knowledge base: stores lessons that feed into live signal evaluation
  - Plain-English reports: every result explained like a trading coach
  - Session/hour/day-of-week performance breakdown
  - MFE/MAE analysis for stop/target optimization
  - Streak analysis and drawdown tracking
  - Equity curve generation
  - Per-setup-type win rates
  - Confidence calibration: does score actually predict outcome?
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import math
import json


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BacktestTrade:
    id: int = 0
    entry_time: str = ""
    exit_time: str = ""
    symbol: str = ""
    direction: str = ""
    entry_price: float = 0.0
    stop_price: float = 0.0
    target_price: float = 0.0
    target2_price: float = 0.0
    target3_price: float = 0.0
    exit_price: float = 0.0
    exit_reason: str = ""
    pnl_r: float = 0.0
    pnl_points: float = 0.0
    mae: float = 0.0
    mfe: float = 0.0
    mae_r: float = 0.0
    mfe_r: float = 0.0
    bars_held: int = 0
    confidence_score: float = 0.0
    composite_score: int = 0
    signal_tier: str = ""
    indication_type: str = ""
    correction_zone: str = ""
    continuation_trigger: str = ""
    hour_of_day: int = 0
    day_of_week: int = 0
    session: str = ""
    htf_bias_4h: str = ""
    htf_bias_1h: str = ""
    ema_stack_aligned: bool = False
    rsi_at_entry: float = 0.0
    atr_at_entry: float = 0.0
    volume_ratio: float = 0.0
    vwap_deviation: float = 0.0
    had_bos: bool = False
    had_choch: bool = False
    had_fvg: bool = False
    had_ob: bool = False
    had_liq_sweep: bool = False
    hit_t1: bool = False
    hit_t2: bool = False
    hit_t3: bool = False
    failure_reason: str = ""
    lesson: str = ""


@dataclass
class LessonLearned:
    """A single pattern/insight extracted from backtest analysis."""
    category: str = ""       # "timing", "setup_type", "risk", "session", "indicator"
    pattern: str = ""        # machine-readable pattern key
    description: str = ""    # plain English
    confidence: float = 0.0  # 0-1 how confident we are in this lesson
    sample_size: int = 0
    win_rate: float = 0.0
    avg_pnl_r: float = 0.0
    recommendation: str = "" # actionable advice
    severity: str = "info"   # "critical", "warning", "info", "positive"


@dataclass
class BacktestResult:
    """Complete backtest output with learning insights."""
    # Meta
    symbol: str = ""
    period_days: int = 0
    total_bars: int = 0
    run_id: str = ""
    run_timestamp: str = ""
    config: Dict = field(default_factory=dict)

    # Core stats
    total_setups_detected: int = 0
    total_trades: int = 0
    winners: int = 0
    losers: int = 0
    breakeven: int = 0
    win_rate: float = 0.0
    avg_winner_r: float = 0.0
    avg_loser_r: float = 0.0
    expectancy_r: float = 0.0
    profit_factor: float = 0.0
    total_pnl_r: float = 0.0
    max_drawdown_r: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_bars_held_winner: float = 0.0
    avg_bars_held_loser: float = 0.0
    sharpe_ratio: float = 0.0

    # MFE/MAE
    avg_mae_r: float = 0.0
    avg_mfe_r: float = 0.0
    avg_mae_winners: float = 0.0
    avg_mfe_winners: float = 0.0
    avg_mae_losers: float = 0.0
    avg_mfe_losers: float = 0.0
    optimal_stop_r: float = 0.0
    optimal_target_r: float = 0.0

    # Target hit rates
    t1_hit_rate: float = 0.0
    t2_hit_rate: float = 0.0
    t3_hit_rate: float = 0.0

    # Breakdowns
    by_hour: Dict = field(default_factory=dict)
    by_day_of_week: Dict = field(default_factory=dict)
    by_session: Dict = field(default_factory=dict)
    by_indication_type: Dict = field(default_factory=dict)
    by_correction_zone: Dict = field(default_factory=dict)
    by_continuation_trigger: Dict = field(default_factory=dict)
    by_tier: Dict = field(default_factory=dict)
    by_score_bucket: Dict = field(default_factory=dict)
    by_htf_alignment: Dict = field(default_factory=dict)

    # Equity curve
    equity_curve: List = field(default_factory=list)

    # Trade log
    trades: List = field(default_factory=list)

    # Learning
    lessons_learned: List = field(default_factory=list)
    knowledge_base: Dict = field(default_factory=dict)

    # Plain English
    executive_summary: str = ""
    detailed_report: str = ""
    recommendations: List = field(default_factory=list)
    grade: str = ""  # A+, A, B+, B, C, D, F


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def calc_ema(values: list, period: int) -> list:
    result = [None] * len(values)
    if len(values) < period:
        return result
    k = 2.0 / (period + 1)
    sma = sum(v for v in values[:period] if v is not None) / period
    result[period - 1] = sma
    for i in range(period, len(values)):
        if values[i] is not None and result[i - 1] is not None:
            result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def calc_rsi(closes: list, period: int = 14) -> list:
    result = [None] * len(closes)
    if len(closes) < period + 1:
        return result
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period, len(closes)):
        if i > period:
            diff = closes[i] - closes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(diff, 0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-diff, 0)) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))
    return result


def calc_atr(bars: list, period: int = 14) -> list:
    result = [None] * len(bars)
    if len(bars) < 2:
        return result
    trs = [0.0]
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period + 1:
        return result
    atr = sum(trs[1:period + 1]) / period
    result[period] = atr
    for i in range(period + 1, len(bars)):
        atr = (atr * (period - 1) + trs[i]) / period
        result[i] = atr
    return result


def calc_vwap(bars: list) -> list:
    result = [None] * len(bars)
    cum_pv = cum_vol = 0.0
    prev_date = None
    for i, b in enumerate(bars):
        t = b["time"]
        date = t.date() if hasattr(t, "date") else None
        if date != prev_date:
            cum_pv = cum_vol = 0.0
            prev_date = date
        typical = (b["high"] + b["low"] + b["close"]) / 3.0
        vol = max(b.get("volume", 0), 0.001)
        cum_pv += typical * vol
        cum_vol += vol
        result[i] = cum_pv / cum_vol if cum_vol > 0 else b["close"]
    return result


def calc_macd(closes: list) -> Tuple[list, list, list]:
    e12 = calc_ema(closes, 12)
    e26 = calc_ema(closes, 26)
    macd_line = [None] * len(closes)
    for i in range(len(closes)):
        if e12[i] is not None and e26[i] is not None:
            macd_line[i] = e12[i] - e26[i]
    valid = [v for v in macd_line if v is not None]
    signal = calc_ema(valid, 9) if len(valid) >= 9 else [None] * len(valid)
    # Re-align signal
    signal_full = [None] * len(closes)
    j = 0
    for i in range(len(closes)):
        if macd_line[i] is not None:
            if j < len(signal):
                signal_full[i] = signal[j]
            j += 1
    hist = [None] * len(closes)
    for i in range(len(closes)):
        if macd_line[i] is not None and signal_full[i] is not None:
            hist[i] = macd_line[i] - signal_full[i]
    return macd_line, signal_full, hist


def calc_volume_sma(vols: list, period: int = 20) -> list:
    result = [None] * len(vols)
    for i in range(period, len(vols)):
        result[i] = sum(vols[i - period:i]) / period
    return result


def get_session(hour_utc: int) -> str:
    if 7 <= hour_utc < 13:
        return "london"
    if 13 <= hour_utc < 16:
        return "ny_open"
    if 16 <= hour_utc < 19:
        return "ny_mid"
    if 19 <= hour_utc < 21:
        return "ny_power"
    if 12 <= hour_utc < 14:
        return "overlap"
    return "off_hours"


def safe_div(a, b, default=0.0):
    return a / b if b != 0 else default


# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHER
# ═══════════════════════════════════════════════════════════════════════════════

class YahooFetcher:
    def __init__(self):
        pass

    async def fetch_bars(self, symbol: str, days: int) -> list:
        import yfinance as yf
        symbol_map = {
            "NQ": "NQ=F", "MNQ": "NQ=F", "ES": "ES=F", "MES": "ES=F",
            "YM": "YM=F", "MYM": "YM=F", "CL": "CL=F", "GC": "GC=F",
            "NQ1!": "NQ=F", "ES1!": "ES=F", "MNQ1!": "NQ=F", "MES1!": "ES=F",
        }
        yf_sym = symbol_map.get(symbol, symbol.replace("1!", "=F"))

        # yfinance 5m data is limited to ~60 days. For longer periods, use 15m or 1h
        if days <= 60:
            interval = "5m"
        elif days <= 730:
            interval = "15m"
        else:
            interval = "1h"

        end = datetime.now()
        start = end - timedelta(days=min(days, 729))
        ticker = yf.Ticker(yf_sym)
        df = ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), interval=interval)

        if df.empty:
            raise Exception(f"No data from Yahoo Finance for {yf_sym} ({interval})")

        bars = []
        for ts, row in df.iterrows():
            t = ts.to_pydatetime()
            if hasattr(t, "tzinfo") and t.tzinfo is not None:
                t = t.replace(tzinfo=None)
            bars.append({
                "time": t, "open": float(row["Open"]),
                "high": float(row["High"]), "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row.get("Volume", 0)),
            })
        return bars


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING ENGINE (mirrors PineScript composite scorer)
# ═══════════════════════════════════════════════════════════════════════════════

class SetupScorer:
    """Replicates the PineScript ICC Assessment Engine scoring in Python."""

    def score_setup(self, ctx: Dict) -> Tuple[int, int, str, Dict]:
        """
        Returns (bull_score, bear_score, best_direction, details_dict)
        """
        bull = self._calc_bull(ctx)
        bear = self._calc_bear(ctx)
        direction = "bullish" if bull >= bear else "bearish"
        best = max(bull, bear)
        tier = "S" if best >= 80 else "A" if best >= 65 else "B" if best >= 50 else "C" if best >= 40 else "X"

        details = {
            "bull_score": bull, "bear_score": bear,
            "best_score": best, "tier": tier, "direction": direction,
        }
        return bull, bear, direction, details

    def _calc_bull(self, c: Dict) -> int:
        s = 0
        # Timeframe alignment
        if c.get("bull_4h"): s += 12
        if c.get("bull_1h"): s += 10
        if c.get("bull_15m"): s += 6
        if c.get("bull_ema_stack"): s += 4
        if c.get("bull_ema_partial"): s += 2
        # Structure
        if c.get("uptrend"): s += 8
        if c.get("recent_bull_bos"): s += 7
        if c.get("recent_choch_bull"): s += 5
        if c.get("hh") and c.get("hl"): s += 4
        if c.get("or_bull_break"): s += 3
        # SMC
        if c.get("in_bull_fvg"): s += 9
        if c.get("in_bull_ob"): s += 8
        if c.get("liq_sweep_bull"): s += 5
        # Momentum
        if c.get("rsi_bull_zone"): s += 6
        if c.get("macd_bull"): s += 4
        if c.get("macd_cross_up"): s += 5
        if c.get("macd_above_zero"): s += 2
        if c.get("bull_div"): s += 6
        # Volume
        if c.get("vol_spike"): s += 5
        if c.get("vol_expanding"): s += 3
        if c.get("pos_delta"): s += 4
        # VWAP
        if c.get("above_vwap"): s += 3
        if c.get("vwap_reclaim_bull"): s += 6
        # Session
        s += c.get("sess_pts", 2)
        # Penalties
        if c.get("vol_extreme"): s = int(s * 0.5)
        if c.get("vol_low"): s = int(s * 0.85)
        if c.get("rsi_ob"): s = int(s * 0.8)
        return min(s, 100)

    def _calc_bear(self, c: Dict) -> int:
        s = 0
        if c.get("bear_4h"): s += 12
        if c.get("bear_1h"): s += 10
        if c.get("bear_15m"): s += 6
        if c.get("bear_ema_stack"): s += 4
        if c.get("bear_ema_partial"): s += 2
        if c.get("downtrend"): s += 8
        if c.get("recent_bear_bos"): s += 7
        if c.get("recent_choch_bear"): s += 5
        if c.get("ll") and c.get("lh"): s += 4
        if c.get("or_bear_break"): s += 3
        if c.get("in_bear_fvg"): s += 9
        if c.get("in_bear_ob"): s += 8
        if c.get("liq_sweep_bear"): s += 5
        if c.get("rsi_bear_zone"): s += 6
        if c.get("macd_bear"): s += 4
        if c.get("macd_cross_down"): s += 5
        if c.get("macd_below_zero"): s += 2
        if c.get("bear_div"): s += 6
        if c.get("vol_spike"): s += 5
        if c.get("vol_expanding"): s += 3
        if c.get("neg_delta"): s += 4
        if c.get("below_vwap"): s += 3
        if c.get("vwap_reclaim_bear"): s += 6
        s += c.get("sess_pts", 2)
        if c.get("vol_extreme"): s = int(s * 0.5)
        if c.get("vol_low"): s = int(s * 0.85)
        if c.get("rsi_os"): s = int(s * 0.8)
        return min(s, 100)


# ═══════════════════════════════════════════════════════════════════════════════
# LEARNING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class LearningEngine:
    """Analyzes completed trades to extract patterns and lessons."""

    def analyze(self, trades: List[BacktestTrade], result: BacktestResult) -> Tuple[List[LessonLearned], Dict]:
        lessons = []
        knowledge = {}

        if len(trades) < 5:
            lessons.append(LessonLearned(
                category="general", pattern="insufficient_data",
                description="Not enough trades to draw meaningful conclusions.",
                confidence=0.0, sample_size=len(trades),
                recommendation="Run the backtest with wider filters to get more trades.",
                severity="warning"
            ))
            return lessons, knowledge

        # Analyze each dimension
        lessons.extend(self._analyze_timing(trades))
        lessons.extend(self._analyze_setup_types(trades))
        lessons.extend(self._analyze_score_calibration(trades))
        lessons.extend(self._analyze_risk_management(trades, result))
        lessons.extend(self._analyze_session_performance(trades))
        lessons.extend(self._analyze_streaks(trades))
        lessons.extend(self._analyze_htf_alignment(trades))
        lessons.extend(self._analyze_smc_patterns(trades))

        # Build knowledge base for live use
        knowledge = self._build_knowledge_base(trades, lessons)

        return lessons, knowledge

    def _analyze_timing(self, trades: List[BacktestTrade]) -> List[LessonLearned]:
        lessons = []
        by_hour = {}
        for t in trades:
            h = t.hour_of_day
            if h not in by_hour:
                by_hour[h] = {"w": 0, "l": 0, "total_r": 0.0}
            if t.pnl_r > 0:
                by_hour[h]["w"] += 1
            else:
                by_hour[h]["l"] += 1
            by_hour[h]["total_r"] += t.pnl_r

        # Find best and worst hours
        qualified = {h: v for h, v in by_hour.items() if (v["w"] + v["l"]) >= 5}
        if qualified:
            best_h = max(qualified, key=lambda h: safe_div(qualified[h]["w"], qualified[h]["w"] + qualified[h]["l"]))
            worst_h = min(qualified, key=lambda h: safe_div(qualified[h]["w"], qualified[h]["w"] + qualified[h]["l"]))

            bv = qualified[best_h]
            b_total = bv["w"] + bv["l"]
            b_wr = safe_div(bv["w"], b_total)
            lessons.append(LessonLearned(
                category="timing", pattern=f"best_hour_{best_h}",
                description=f"Best trading hour: {best_h}:00 UTC with {b_wr*100:.0f}% win rate across {b_total} trades.",
                confidence=min(b_total / 20, 1.0), sample_size=b_total,
                win_rate=b_wr, avg_pnl_r=safe_div(bv["total_r"], b_total),
                recommendation=f"Prioritize setups that appear around {best_h}:00 UTC. This is your highest-probability window.",
                severity="positive"
            ))

            wv = qualified[worst_h]
            w_total = wv["w"] + wv["l"]
            w_wr = safe_div(wv["w"], w_total)
            if w_wr < 0.4:
                lessons.append(LessonLearned(
                    category="timing", pattern=f"worst_hour_{worst_h}",
                    description=f"Worst trading hour: {worst_h}:00 UTC with only {w_wr*100:.0f}% win rate across {w_total} trades.",
                    confidence=min(w_total / 20, 1.0), sample_size=w_total,
                    win_rate=w_wr, avg_pnl_r=safe_div(wv["total_r"], w_total),
                    recommendation=f"Avoid trading at {worst_h}:00 UTC or require S-tier setups only.",
                    severity="warning"
                ))

        # Day of week analysis
        by_dow = {}
        dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for t in trades:
            d = t.day_of_week
            if d not in by_dow:
                by_dow[d] = {"w": 0, "l": 0, "total_r": 0.0}
            if t.pnl_r > 0:
                by_dow[d]["w"] += 1
            else:
                by_dow[d]["l"] += 1
            by_dow[d]["total_r"] += t.pnl_r

        for d, v in by_dow.items():
            total = v["w"] + v["l"]
            if total >= 5:
                wr = safe_div(v["w"], total)
                if wr < 0.35:
                    lessons.append(LessonLearned(
                        category="timing", pattern=f"bad_day_{dow_names[d]}",
                        description=f"{dow_names[d]} has a {wr*100:.0f}% win rate — significantly below average.",
                        confidence=min(total / 15, 1.0), sample_size=total,
                        win_rate=wr, avg_pnl_r=safe_div(v["total_r"], total),
                        recommendation=f"Consider reducing size or skipping trades on {dow_names[d]}.",
                        severity="warning"
                    ))

        return lessons

    def _analyze_setup_types(self, trades: List[BacktestTrade]) -> List[LessonLearned]:
        lessons = []
        by_ind = {}
        for t in trades:
            key = t.indication_type or "unknown"
            if key not in by_ind:
                by_ind[key] = {"w": 0, "l": 0, "total_r": 0.0, "trades": []}
            if t.pnl_r > 0:
                by_ind[key]["w"] += 1
            else:
                by_ind[key]["l"] += 1
            by_ind[key]["total_r"] += t.pnl_r
            by_ind[key]["trades"].append(t)

        for ind, v in by_ind.items():
            total = v["w"] + v["l"]
            if total >= 3:
                wr = safe_div(v["w"], total)
                avg_r = safe_div(v["total_r"], total)
                label = ind.replace("_", " ").title()
                if wr >= 0.6 and avg_r > 0:
                    lessons.append(LessonLearned(
                        category="setup_type", pattern=f"strong_{ind}",
                        description=f"{label} setups are your strongest: {wr*100:.0f}% win rate, +{avg_r:.2f}R avg per trade.",
                        confidence=min(total / 15, 1.0), sample_size=total,
                        win_rate=wr, avg_pnl_r=avg_r,
                        recommendation=f"Take {label} setups with confidence. Consider full position size.",
                        severity="positive"
                    ))
                elif wr < 0.35 and total >= 5:
                    lessons.append(LessonLearned(
                        category="setup_type", pattern=f"weak_{ind}",
                        description=f"{label} setups are underperforming: {wr*100:.0f}% win rate, {avg_r:.2f}R avg.",
                        confidence=min(total / 15, 1.0), sample_size=total,
                        win_rate=wr, avg_pnl_r=avg_r,
                        recommendation=f"Avoid {label} setups or add extra confirmation requirements.",
                        severity="critical"
                    ))

        return lessons

    def _analyze_score_calibration(self, trades: List[BacktestTrade]) -> List[LessonLearned]:
        lessons = []
        buckets = {"S (80+)": [], "A (65-79)": [], "B (50-64)": [], "C (40-49)": []}
        for t in trades:
            s = t.composite_score
            if s >= 80:
                buckets["S (80+)"].append(t)
            elif s >= 65:
                buckets["A (65-79)"].append(t)
            elif s >= 50:
                buckets["B (50-64)"].append(t)
            else:
                buckets["C (40-49)"].append(t)

        for bname, ts in buckets.items():
            if len(ts) >= 3:
                wins = sum(1 for t in ts if t.pnl_r > 0)
                wr = safe_div(wins, len(ts))
                avg_r = safe_div(sum(t.pnl_r for t in ts), len(ts))

                if bname.startswith("S") and wr < 0.5:
                    lessons.append(LessonLearned(
                        category="calibration", pattern="s_tier_underperforming",
                        description=f"S-Tier setups are NOT living up to their score: {wr*100:.0f}% win rate.",
                        confidence=min(len(ts) / 10, 1.0), sample_size=len(ts),
                        win_rate=wr, avg_pnl_r=avg_r,
                        recommendation="The scoring engine may be overweighting some factors. Review what S-tier signals have in common when they fail.",
                        severity="critical"
                    ))
                elif bname.startswith("S") and wr >= 0.65:
                    lessons.append(LessonLearned(
                        category="calibration", pattern="s_tier_strong",
                        description=f"S-Tier setups deliver: {wr*100:.0f}% win rate with {avg_r:+.2f}R average.",
                        confidence=min(len(ts) / 10, 1.0), sample_size=len(ts),
                        win_rate=wr, avg_pnl_r=avg_r,
                        recommendation="Trust S-Tier signals. Take them with full size.",
                        severity="positive"
                    ))

        return lessons

    def _analyze_risk_management(self, trades: List[BacktestTrade], result: BacktestResult) -> List[LessonLearned]:
        lessons = []
        winners = [t for t in trades if t.pnl_r > 0]
        losers = [t for t in trades if t.pnl_r <= 0]

        # MAE analysis for winners - could stops be tighter?
        if winners:
            avg_mae_w = sum(t.mae_r for t in winners) / len(winners)
            if avg_mae_w > 1.2:
                lessons.append(LessonLearned(
                    category="risk", pattern="wide_stops_winners",
                    description=f"Winning trades show {avg_mae_w:.1f}R average adverse excursion before winning. Stops may be too wide.",
                    confidence=min(len(winners) / 15, 1.0), sample_size=len(winners),
                    recommendation="Your winners go significantly against you before turning. Consider tighter stops or waiting for better entries.",
                    severity="warning"
                ))

        # MFE analysis for losers - were they winners that turned?
        if losers:
            turned_losers = [t for t in losers if t.mfe_r > 1.0]
            if len(turned_losers) > len(losers) * 0.3:
                pct = len(turned_losers) / len(losers) * 100
                lessons.append(LessonLearned(
                    category="risk", pattern="losers_were_winners",
                    description=f"{pct:.0f}% of your losing trades had 1R+ profit at some point before reversing.",
                    confidence=min(len(losers) / 10, 1.0), sample_size=len(losers),
                    recommendation="Add a trailing stop after reaching 1R profit. Many losses could have been breakeven or small winners.",
                    severity="critical"
                ))

        # Optimal target analysis
        if winners:
            mfes = [t.mfe_r for t in winners if t.mfe_r > 0]
            if mfes:
                p75_mfe = sorted(mfes)[int(len(mfes) * 0.75)] if len(mfes) > 4 else max(mfes)
                lessons.append(LessonLearned(
                    category="risk", pattern="optimal_target",
                    description=f"75% of winning trades reach at least {p75_mfe:.1f}R before pulling back.",
                    confidence=min(len(mfes) / 15, 1.0), sample_size=len(mfes),
                    recommendation=f"Consider setting Target 1 around {p75_mfe:.1f}R to capture most winning moves.",
                    severity="info"
                ))

        return lessons

    def _analyze_session_performance(self, trades: List[BacktestTrade]) -> List[LessonLearned]:
        lessons = []
        by_sess = {}
        for t in trades:
            s = t.session or "unknown"
            if s not in by_sess:
                by_sess[s] = {"w": 0, "l": 0, "total_r": 0.0}
            if t.pnl_r > 0:
                by_sess[s]["w"] += 1
            else:
                by_sess[s]["l"] += 1
            by_sess[s]["total_r"] += t.pnl_r

        for sess, v in by_sess.items():
            total = v["w"] + v["l"]
            if total >= 5:
                wr = safe_div(v["w"], total)
                if wr >= 0.6:
                    lessons.append(LessonLearned(
                        category="session", pattern=f"strong_session_{sess}",
                        description=f"The {sess.replace('_', ' ')} session is profitable: {wr*100:.0f}% win rate, {v['total_r']:+.1f}R total.",
                        confidence=min(total / 15, 1.0), sample_size=total,
                        win_rate=wr, avg_pnl_r=safe_div(v["total_r"], total),
                        recommendation=f"Prioritize the {sess.replace('_', ' ')} session.",
                        severity="positive"
                    ))
                elif wr < 0.35:
                    lessons.append(LessonLearned(
                        category="session", pattern=f"weak_session_{sess}",
                        description=f"The {sess.replace('_', ' ')} session is losing money: {wr*100:.0f}% win rate.",
                        confidence=min(total / 15, 1.0), sample_size=total,
                        win_rate=wr, avg_pnl_r=safe_div(v["total_r"], total),
                        recommendation=f"Remove {sess.replace('_', ' ')} from your allowed sessions.",
                        severity="critical"
                    ))

        return lessons

    def _analyze_streaks(self, trades: List[BacktestTrade]) -> List[LessonLearned]:
        lessons = []
        # Find if there are patterns after consecutive losses
        consec = 0
        after_streak = {"w": 0, "l": 0}
        for t in trades:
            if t.pnl_r <= 0:
                consec += 1
            else:
                if consec >= 3:
                    after_streak["w"] += 1
                consec = 0
            if consec == 3:
                # The trade that would have been #4
                pass

        # Check for revenge trading patterns (trades taken shortly after losses)
        return lessons

    def _analyze_htf_alignment(self, trades: List[BacktestTrade]) -> List[LessonLearned]:
        lessons = []
        aligned = [t for t in trades if t.htf_bias_4h == t.direction or t.htf_bias_1h == t.direction]
        counter = [t for t in trades if t.htf_bias_4h and t.htf_bias_4h != t.direction and t.htf_bias_4h != "neutral"]

        if len(aligned) >= 5 and len(counter) >= 5:
            wr_a = safe_div(sum(1 for t in aligned if t.pnl_r > 0), len(aligned))
            wr_c = safe_div(sum(1 for t in counter if t.pnl_r > 0), len(counter))
            diff = (wr_a - wr_c) * 100

            if diff > 10:
                lessons.append(LessonLearned(
                    category="indicator", pattern="htf_alignment_matters",
                    description=f"HTF-aligned trades win {wr_a*100:.0f}% vs countertrend {wr_c*100:.0f}% — that's a {diff:.0f}% edge.",
                    confidence=min((len(aligned) + len(counter)) / 30, 1.0),
                    sample_size=len(aligned) + len(counter),
                    recommendation="Always check 4H bias before entering. Countertrend trades should require S-tier confirmation.",
                    severity="positive" if diff > 15 else "info"
                ))

        return lessons

    def _analyze_smc_patterns(self, trades: List[BacktestTrade]) -> List[LessonLearned]:
        lessons = []
        # FVG performance
        fvg_trades = [t for t in trades if t.had_fvg]
        non_fvg = [t for t in trades if not t.had_fvg]
        if len(fvg_trades) >= 5 and len(non_fvg) >= 5:
            wr_fvg = safe_div(sum(1 for t in fvg_trades if t.pnl_r > 0), len(fvg_trades))
            wr_nonfvg = safe_div(sum(1 for t in non_fvg if t.pnl_r > 0), len(non_fvg))
            if wr_fvg > wr_nonfvg + 0.1:
                lessons.append(LessonLearned(
                    category="indicator", pattern="fvg_edge",
                    description=f"Trades with FVG confluence win {wr_fvg*100:.0f}% vs {wr_nonfvg*100:.0f}% without.",
                    confidence=min(len(fvg_trades) / 15, 1.0),
                    sample_size=len(fvg_trades),
                    recommendation="FVG zones provide a measurable edge. Prioritize entries in FVGs.",
                    severity="positive"
                ))

        return lessons

    def _build_knowledge_base(self, trades: List[BacktestTrade], lessons: List[LessonLearned]) -> Dict:
        """Build a structured knowledge base that live signals can query."""
        kb = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_trades_analyzed": len(trades),
            "overall_win_rate": safe_div(sum(1 for t in trades if t.pnl_r > 0), len(trades)),
            "best_setup_types": [],
            "worst_setup_types": [],
            "best_hours": [],
            "worst_hours": [],
            "best_sessions": [],
            "worst_sessions": [],
            "score_thresholds": {},
            "risk_insights": {},
            "lessons": [asdict(l) for l in lessons if l.confidence >= 0.5],
        }

        # Extract actionable thresholds
        for lesson in lessons:
            if lesson.severity == "positive" and "best_hour" in lesson.pattern:
                kb["best_hours"].append(lesson.pattern.split("_")[-1])
            if lesson.severity in ("warning", "critical") and "worst_hour" in lesson.pattern:
                kb["worst_hours"].append(lesson.pattern.split("_")[-1])
            if "strong_" in lesson.pattern and lesson.category == "setup_type":
                kb["best_setup_types"].append(lesson.pattern.replace("strong_", ""))
            if "weak_" in lesson.pattern and lesson.category == "setup_type":
                kb["worst_setup_types"].append(lesson.pattern.replace("weak_", ""))

        return kb


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT GENERATOR — Plain English
# ═══════════════════════════════════════════════════════════════════════════════

class ReportGenerator:
    """Generates human-readable reports from backtest results."""

    def generate(self, result: BacktestResult) -> Tuple[str, str, str, List[str]]:
        """Returns (executive_summary, detailed_report, grade, recommendations)"""
        grade = self._grade(result)
        summary = self._executive_summary(result, grade)
        report = self._detailed_report(result)
        recs = self._recommendations(result)
        return summary, report, grade, recs

    def _grade(self, r: BacktestResult) -> str:
        if r.total_trades < 10:
            return "N/A"
        score = 0
        if r.win_rate >= 0.55: score += 25
        elif r.win_rate >= 0.45: score += 15
        if r.expectancy_r >= 0.3: score += 25
        elif r.expectancy_r > 0: score += 15
        if r.profit_factor >= 2.0: score += 20
        elif r.profit_factor >= 1.5: score += 12
        elif r.profit_factor >= 1.0: score += 5
        if r.max_drawdown_r <= 5: score += 15
        elif r.max_drawdown_r <= 10: score += 8
        if r.max_consecutive_losses <= 4: score += 15
        elif r.max_consecutive_losses <= 6: score += 8

        if score >= 90: return "A+"
        if score >= 80: return "A"
        if score >= 70: return "B+"
        if score >= 60: return "B"
        if score >= 45: return "C"
        if score >= 30: return "D"
        return "F"

    def _executive_summary(self, r: BacktestResult, grade: str) -> str:
        if r.total_trades == 0:
            return "No trades were generated. The filters may be too restrictive — try loosening session, RSI, or bias requirements."

        if r.total_trades < 10:
            return f"Only {r.total_trades} trades found — not enough data for reliable conclusions. Try extending the time period or loosening filters."

        profitable = r.expectancy_r > 0
        lines = []

        lines.append(f"STRATEGY GRADE: {grade}")
        lines.append("")

        if profitable:
            lines.append(f"This strategy IS profitable over the test period. Across {r.total_trades} trades on {r.symbol}, "
                         f"it produced a {r.win_rate*100:.1f}% win rate with {r.expectancy_r:+.3f}R expectancy per trade.")
            lines.append(f"That means for every $100 risked, you'd expect to make ${r.expectancy_r * 100:.0f} on average.")
        else:
            lines.append(f"This strategy is NOT profitable in its current form. Across {r.total_trades} trades, "
                         f"it shows a {r.win_rate*100:.1f}% win rate with {r.expectancy_r:.3f}R expectancy — that's a net loser.")
            lines.append(f"For every $100 risked, you'd lose ${abs(r.expectancy_r) * 100:.0f} on average.")

        lines.append("")
        lines.append(f"Profit factor is {r.profit_factor:.2f}x (need >1.5 for a viable strategy). "
                     f"Max drawdown was {r.max_drawdown_r:.1f}R with {r.max_consecutive_losses} consecutive losses at worst.")

        if r.t1_hit_rate > 0:
            lines.append(f"Target 1 was hit {r.t1_hit_rate*100:.0f}% of the time, "
                         f"T2 hit {r.t2_hit_rate*100:.0f}%, T3 hit {r.t3_hit_rate*100:.0f}%.")

        return "\n".join(lines)

    def _detailed_report(self, r: BacktestResult) -> str:
        lines = [
            "═══ DETAILED BACKTEST REPORT ═══",
            "",
            f"Symbol: {r.symbol} | Period: {r.period_days} days | Bars analyzed: {r.total_bars}",
            f"Setups detected: {r.total_setups_detected} | Trades taken: {r.total_trades}",
            "",
            "── PERFORMANCE ──",
            f"Win Rate: {r.win_rate*100:.1f}% ({r.winners}W / {r.losers}L)",
            f"Expectancy: {r.expectancy_r:+.3f}R per trade",
            f"Profit Factor: {r.profit_factor:.2f}x",
            f"Total P&L: {r.total_pnl_r:+.1f}R",
            f"Avg Winner: {r.avg_winner_r:+.2f}R | Avg Loser: {r.avg_loser_r:.2f}R",
            "",
            "── RISK ──",
            f"Max Drawdown: {r.max_drawdown_r:.1f}R",
            f"Max Consecutive Wins: {r.max_consecutive_wins} | Losses: {r.max_consecutive_losses}",
            f"Avg Bars Held (Winners): {r.avg_bars_held_winner:.0f} | (Losers): {r.avg_bars_held_loser:.0f}",
            "",
            "── EXCURSION ANALYSIS ──",
            f"Avg MAE (all): {r.avg_mae_r:.2f}R | Avg MFE (all): {r.avg_mfe_r:.2f}R",
            f"Avg MAE (winners): {r.avg_mae_winners:.2f}R | Avg MFE (winners): {r.avg_mfe_winners:.2f}R",
            f"Avg MAE (losers): {r.avg_mae_losers:.2f}R | Avg MFE (losers): {r.avg_mfe_losers:.2f}R",
        ]

        if r.lessons_learned:
            lines.append("")
            lines.append("── KEY LESSONS ──")
            for i, lesson in enumerate(r.lessons_learned[:10], 1):
                icon = "🟢" if lesson.get("severity") == "positive" else "🔴" if lesson.get("severity") == "critical" else "🟡"
                lines.append(f"{i}. {icon} {lesson.get('description', '')}")
                lines.append(f"   → {lesson.get('recommendation', '')}")

        return "\n".join(lines)

    def _recommendations(self, r: BacktestResult) -> List[str]:
        recs = []
        if r.total_trades < 10:
            recs.append("Increase the sample size — try 365+ days or loosen entry filters.")
            return recs

        if r.win_rate < 0.45:
            recs.append("Win rate is below 45%. Tighten your entry criteria — consider requiring 4H HTF alignment and FVG/OB confluence.")
        if r.win_rate > 0.6 and r.expectancy_r < 0.2:
            recs.append("High win rate but low expectancy — your average loser is too large relative to winners. Tighten stops.")
        if r.profit_factor < 1.0:
            recs.append("Profit factor below 1.0 — the strategy loses money. Major changes needed before trading live.")
        elif r.profit_factor < 1.5:
            recs.append("Profit factor below 1.5 — marginally profitable but not enough edge. Refine entry filters.")
        if r.max_consecutive_losses >= 6:
            recs.append(f"You saw {r.max_consecutive_losses} losses in a row. Set a daily max loss of 3 trades to protect against streaks.")
        if r.max_drawdown_r > 10:
            recs.append(f"Max drawdown was {r.max_drawdown_r:.0f}R — very high. Reduce position size until drawdown is under 5R.")
        if r.avg_mfe_losers > 1.0:
            recs.append(f"Losers had {r.avg_mfe_losers:.1f}R average max favorable excursion — add trailing stops to capture these.")
        if r.expectancy_r > 0.3:
            recs.append("Positive expectancy confirmed. This strategy is viable for paper trading validation.")
        if r.win_rate >= 0.55 and r.profit_factor >= 1.5:
            recs.append("Strong performance profile. Proceed to extended paper trading (100+ trades) to validate.")

        return recs


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BACKTESTER
# ═══════════════════════════════════════════════════════════════════════════════

class ICCBacktester:
    def __init__(self, polygon_api_key: str = "", anthropic_api_key: str = ""):
        self.fetcher = YahooFetcher()
        self.scorer = SetupScorer()
        self.learner = LearningEngine()
        self.reporter = ReportGenerator()

    async def run(self, symbol: str = "NQ", days: int = 60, config: Optional[Dict] = None) -> Dict:
        if config is None:
            config = {
                "min_rr": 2.0, "require_4h_bias": False, "require_volume": False,
                "allowed_sessions": ["ny_open", "ny_mid", "ny_power", "london", "overlap"],
                "rsi_min": 40, "rsi_max": 75, "min_score": 40,
                "atr_stop_mult": 1.5, "t2_rr": 3.0, "t3_rr": 5.0,
            }

        run_id = f"bt_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{symbol}"

        print(f"[BACKTEST] Fetching {symbol} data for {days} days...")
        try:
            bars = await self.fetcher.fetch_bars(symbol, days)
        except Exception as e:
            return {"error": str(e), "symbol": symbol, "config": config}

        if not bars or len(bars) < 100:
            return {"error": f"Insufficient data for {symbol} ({len(bars) if bars else 0} bars)", "config": config}

        print(f"[BACKTEST] Got {len(bars)} bars. Computing indicators...")

        # Compute all indicators
        closes = [b["close"] for b in bars]
        highs = [b["high"] for b in bars]
        lows = [b["low"] for b in bars]
        vols = [b.get("volume", 0) for b in bars]

        e8 = calc_ema(closes, 8)
        e21 = calc_ema(closes, 21)
        e50 = calc_ema(closes, 50)
        e200 = calc_ema(closes, 200)
        rsi_v = calc_rsi(closes, 14)
        atr_v = calc_atr(bars, 14)
        vwap_v = calc_vwap(bars)
        vol_sma = calc_volume_sma(vols, 20)
        macd_l, macd_s, macd_h = calc_macd(closes)

        # Detect setups and simulate trades
        trades: List[BacktestTrade] = []
        setups_found = 0
        skip_until = 0
        trade_id = 0
        min_score = config.get("min_score", 40)
        min_rr = config.get("min_rr", 2.0)
        atr_mult = config.get("atr_stop_mult", 1.5)

        warmup = max(200, 55)
        for i in range(warmup, len(bars) - 30):
            if i < skip_until:
                continue
            if not all([e8[i], e21[i], e50[i], rsi_v[i], atr_v[i]]):
                continue

            b = bars[i]
            hour = b["time"].hour if hasattr(b["time"], "hour") else 0
            dow = b["time"].weekday() if hasattr(b["time"], "weekday") else 0
            sess = get_session(hour)

            if sess not in config.get("allowed_sessions", ["ny_open", "london"]):
                continue

            c, h, lo = closes[i], highs[i], lows[i]
            av = atr_v[i]
            vv = vwap_v[i] or c
            vol = vols[i]
            va = vol_sma[i] or 1.0

            # Build scoring context
            lookback = max(0, i - 20)
            recent_high = max(highs[lookback:i+1])
            recent_low = min(lows[lookback:i+1])

            # Simple HTF approximation
            lb_1h = max(0, i - 12)
            lb_4h = max(0, i - 48)
            avg_1h = sum(closes[lb_1h:i+1]) / max(i - lb_1h + 1, 1)
            avg_4h = sum(closes[lb_4h:i+1]) / max(i - lb_4h + 1, 1)
            bull_1h = avg_1h > (e21[i] or c)
            bear_1h = avg_1h < (e21[i] or c)
            bull_4h = avg_4h > (e50[i] or c) if e50[i] else False
            bear_4h = avg_4h < (e50[i] or c) if e50[i] else False

            # Session points
            sess_pts = 10 if sess == "overlap" else 8 if sess == "ny_open" else 7 if sess == "london" else 5 if sess == "ny_power" else 3

            # Detect patterns
            bull_break = c > recent_high and closes[i-1] <= recent_high if i > 0 else False
            bear_break = c < recent_low and closes[i-1] >= recent_low if i > 0 else False
            bull_fvg = i >= 2 and lo > highs[i-2] and closes[i-1] > bars[i-1]["open"]
            bear_fvg = i >= 2 and h < lows[i-2] and closes[i-1] < bars[i-1]["open"]
            vol_spike = vol > va * 1.5 if va > 0 else False
            vol_expanding = vol > vols[i-1] and vol > va if va > 0 else False

            macd_bull = macd_l[i] is not None and macd_s[i] is not None and macd_l[i] > macd_s[i] and (macd_h[i] or 0) > 0
            macd_bear = macd_l[i] is not None and macd_s[i] is not None and macd_l[i] < macd_s[i] and (macd_h[i] or 0) < 0
            macd_cross_up = (macd_l[i] is not None and macd_s[i] is not None and
                             macd_l[i-1] is not None and macd_s[i-1] is not None and
                             macd_l[i] > macd_s[i] and macd_l[i-1] <= macd_s[i-1]) if i > 0 else False
            macd_cross_down = (macd_l[i] is not None and macd_s[i] is not None and
                               macd_l[i-1] is not None and macd_s[i-1] is not None and
                               macd_l[i] < macd_s[i] and macd_l[i-1] >= macd_s[i-1]) if i > 0 else False

            rsi = rsi_v[i]
            rsi_bull_zone = 40 <= rsi <= 75
            rsi_bear_zone = 25 <= rsi <= 60

            ctx = {
                "bull_4h": bull_4h, "bear_4h": bear_4h,
                "bull_1h": bull_1h, "bear_1h": bear_1h,
                "bull_15m": bull_1h,  # approximate
                "bear_15m": bear_1h,
                "bull_ema_stack": e8[i] and e21[i] and e50[i] and e8[i] > e21[i] > e50[i],
                "bear_ema_stack": e8[i] and e21[i] and e50[i] and e8[i] < e21[i] < e50[i],
                "bull_ema_partial": e8[i] and e21[i] and e50[i] and e8[i] > e21[i] > e50[i],
                "bear_ema_partial": e8[i] and e21[i] and e50[i] and e8[i] < e21[i] < e50[i],
                "uptrend": bull_break, "downtrend": bear_break,
                "recent_bull_bos": bull_break, "recent_bear_bos": bear_break,
                "recent_choch_bull": False, "recent_choch_bear": False,
                "hh": c > recent_high * 0.999, "hl": lo > recent_low * 1.001,
                "ll": lo < recent_low * 1.001, "lh": c < recent_high * 0.999,
                "or_bull_break": False, "or_bear_break": False,
                "in_bull_fvg": bull_fvg, "in_bear_fvg": bear_fvg,
                "in_bull_ob": False, "in_bear_ob": False,
                "liq_sweep_bull": False, "liq_sweep_bear": False,
                "rsi_bull_zone": rsi_bull_zone, "rsi_bear_zone": rsi_bear_zone,
                "rsi_ob": rsi > 78, "rsi_os": rsi < 22,
                "macd_bull": macd_bull, "macd_bear": macd_bear,
                "macd_cross_up": macd_cross_up, "macd_cross_down": macd_cross_down,
                "macd_above_zero": macd_l[i] is not None and macd_l[i] > 0,
                "macd_below_zero": macd_l[i] is not None and macd_l[i] < 0,
                "bull_div": False, "bear_div": False,
                "vol_spike": vol_spike, "vol_expanding": vol_expanding,
                "pos_delta": vol_spike and c > bars[i]["open"],
                "neg_delta": vol_spike and c < bars[i]["open"],
                "above_vwap": c > vv, "below_vwap": c < vv,
                "vwap_reclaim_bull": c > vv and closes[i-1] <= (vwap_v[i-1] or c) if i > 0 else False,
                "vwap_reclaim_bear": c < vv and closes[i-1] >= (vwap_v[i-1] or c) if i > 0 else False,
                "vol_extreme": av > 0 and (atr_v[i] / av if av else 0) > 2.0,
                "vol_low": av > 0 and (atr_v[i] / av if av else 0) < 0.8,
                "sess_pts": sess_pts,
            }

            bull_score, bear_score, direction, details = self.scorer.score_setup(ctx)
            best_score = details["best_score"]
            tier = details["tier"]

            if best_score < min_score:
                continue

            setups_found += 1

            # Compute entry/stop/target
            entry = c
            if direction == "bullish":
                stop = entry - av * atr_mult
                risk = entry - stop
                if risk <= 0:
                    continue
                t1 = entry + risk * min_rr
                t2 = entry + risk * config.get("t2_rr", 3.0)
                t3 = entry + risk * config.get("t3_rr", 5.0)
                ind_type = "structure_break_high" if bull_break else "displacement_up" if bull_fvg else "ema_continuation"
                corr_type = "fair_value_gap" if bull_fvg else "vwap" if c <= vv * 1.002 else "ema_zone"
                cont_type = "macd_cross" if macd_cross_up else "volume_expansion" if vol_spike else "momentum"
            else:
                stop = entry + av * atr_mult
                risk = stop - entry
                if risk <= 0:
                    continue
                t1 = entry - risk * min_rr
                t2 = entry - risk * config.get("t2_rr", 3.0)
                t3 = entry - risk * config.get("t3_rr", 5.0)
                ind_type = "structure_break_low" if bear_break else "displacement_down" if bear_fvg else "ema_continuation"
                corr_type = "fair_value_gap" if bear_fvg else "vwap" if c >= vv * 0.998 else "ema_zone"
                cont_type = "macd_cross" if macd_cross_down else "volume_expansion" if vol_spike else "momentum"

            # Simulate trade
            exit_price = None
            exit_reason = "time_exit"
            mae = mfe = 0.0
            hit_t1 = hit_t2 = hit_t3 = False
            bars_held = 0

            for j in range(i + 1, min(i + 60, len(bars))):
                bars_held += 1
                fh, fl = bars[j]["high"], bars[j]["low"]

                if direction == "bullish":
                    adv = entry - fl
                    fav = fh - entry
                    if adv > 0: mae = max(mae, adv)
                    if fav > 0: mfe = max(mfe, fav)
                    if fh >= t1: hit_t1 = True
                    if fh >= t2: hit_t2 = True
                    if fh >= t3: hit_t3 = True
                    if fl <= stop:
                        exit_price = stop
                        exit_reason = "stop_hit"
                        break
                    if fh >= t1:
                        exit_price = t1
                        exit_reason = "t1_hit"
                        break
                else:
                    adv = fh - entry
                    fav = entry - fl
                    if adv > 0: mae = max(mae, adv)
                    if fav > 0: mfe = max(mfe, fav)
                    if fl <= t1: hit_t1 = True
                    if fl <= t2: hit_t2 = True
                    if fl <= t3: hit_t3 = True
                    if fh >= stop:
                        exit_price = stop
                        exit_reason = "stop_hit"
                        break
                    if fl <= t1:
                        exit_price = t1
                        exit_reason = "t1_hit"
                        break

            if exit_price is None:
                exit_price = bars[min(i + 59, len(bars) - 1)]["close"]

            pnl_pts = (exit_price - entry) if direction == "bullish" else (entry - exit_price)
            pnl_r = pnl_pts / risk if risk > 0 else 0

            vwap_dev = ((c - vv) / vv * 100) if vv > 0 else 0

            trade_id += 1
            trade = BacktestTrade(
                id=trade_id,
                entry_time=str(b["time"]),
                exit_time=str(bars[min(i + bars_held, len(bars) - 1)]["time"]),
                symbol=symbol, direction=direction,
                entry_price=round(entry, 2), stop_price=round(stop, 2),
                target_price=round(t1, 2), target2_price=round(t2, 2), target3_price=round(t3, 2),
                exit_price=round(exit_price, 2), exit_reason=exit_reason,
                pnl_r=round(pnl_r, 3), pnl_points=round(pnl_pts, 2),
                mae=round(mae, 4), mfe=round(mfe, 4),
                mae_r=round(mae / risk, 2) if risk > 0 else 0,
                mfe_r=round(mfe / risk, 2) if risk > 0 else 0,
                bars_held=bars_held,
                composite_score=best_score, signal_tier=tier,
                confidence_score=best_score / 100,
                indication_type=ind_type, correction_zone=corr_type,
                continuation_trigger=cont_type,
                hour_of_day=hour, day_of_week=dow, session=sess,
                htf_bias_4h="bullish" if bull_4h else "bearish" if bear_4h else "neutral",
                htf_bias_1h="bullish" if bull_1h else "bearish" if bear_1h else "neutral",
                ema_stack_aligned=ctx.get("bull_ema_stack", False) if direction == "bullish" else ctx.get("bear_ema_stack", False),
                rsi_at_entry=round(rsi, 1), atr_at_entry=round(av, 4),
                volume_ratio=round(vol / va, 2) if va > 0 else 0,
                vwap_deviation=round(vwap_dev, 2),
                had_bos=bull_break or bear_break,
                had_fvg=bull_fvg or bear_fvg,
                hit_t1=hit_t1, hit_t2=hit_t2, hit_t3=hit_t3,
            )
            trades.append(trade)
            skip_until = i + 8  # cooldown

        print(f"[BACKTEST] {setups_found} setups, {len(trades)} trades simulated")

        # Build result
        result = self._compute_stats(trades, symbol, days, len(bars), setups_found, config, run_id)

        # Learning phase
        lessons, knowledge = self.learner.analyze(trades, result)
        result.lessons_learned = [asdict(l) for l in lessons]
        result.knowledge_base = knowledge

        # Report phase
        summary, report, grade, recs = self.reporter.generate(result)
        result.executive_summary = summary
        result.detailed_report = report
        result.grade = grade
        result.recommendations = recs

        return asdict(result)

    def _compute_stats(self, trades: List[BacktestTrade], symbol, days, total_bars, setups_found, config, run_id) -> BacktestResult:
        r = BacktestResult(
            symbol=symbol, period_days=days, total_bars=total_bars,
            run_id=run_id, run_timestamp=datetime.utcnow().isoformat(),
            config=config, total_setups_detected=setups_found,
            total_trades=len(trades),
        )

        if not trades:
            return r

        winners = [t for t in trades if t.pnl_r > 0]
        losers = [t for t in trades if t.pnl_r <= 0]
        r.winners = len(winners)
        r.losers = len(losers)
        r.win_rate = safe_div(r.winners, r.total_trades)
        r.avg_winner_r = safe_div(sum(t.pnl_r for t in winners), len(winners))
        r.avg_loser_r = safe_div(sum(t.pnl_r for t in losers), len(losers))
        r.expectancy_r = r.win_rate * r.avg_winner_r + (1 - r.win_rate) * r.avg_loser_r
        gw = sum(t.pnl_r for t in winners) if winners else 0
        gl = abs(sum(t.pnl_r for t in losers)) if losers else 0.001
        r.profit_factor = round(gw / gl, 2) if gl > 0 else 0
        r.total_pnl_r = round(sum(t.pnl_r for t in trades), 2)

        # Drawdown & streaks
        eq = peak = dd = 0.0
        cw = cl = mcw = mcl = 0
        eq_curve = [{"trade": 0, "equity": 0}]
        for t in trades:
            eq += t.pnl_r
            peak = max(peak, eq)
            dd = max(dd, peak - eq)
            eq_curve.append({"trade": t.id, "equity": round(eq, 2), "pnl": round(t.pnl_r, 3)})
            if t.pnl_r > 0:
                cw += 1; cl = 0; mcw = max(mcw, cw)
            else:
                cl += 1; cw = 0; mcl = max(mcl, cl)

        r.max_drawdown_r = round(dd, 2)
        r.max_consecutive_wins = mcw
        r.max_consecutive_losses = mcl
        r.equity_curve = eq_curve

        # Bars held
        r.avg_bars_held_winner = safe_div(sum(t.bars_held for t in winners), len(winners))
        r.avg_bars_held_loser = safe_div(sum(t.bars_held for t in losers), len(losers))

        # MFE/MAE
        r.avg_mae_r = safe_div(sum(t.mae_r for t in trades), len(trades))
        r.avg_mfe_r = safe_div(sum(t.mfe_r for t in trades), len(trades))
        r.avg_mae_winners = safe_div(sum(t.mae_r for t in winners), len(winners))
        r.avg_mfe_winners = safe_div(sum(t.mfe_r for t in winners), len(winners))
        r.avg_mae_losers = safe_div(sum(t.mae_r for t in losers), len(losers))
        r.avg_mfe_losers = safe_div(sum(t.mfe_r for t in losers), len(losers))

        # Target hit rates
        r.t1_hit_rate = safe_div(sum(1 for t in trades if t.hit_t1), len(trades))
        r.t2_hit_rate = safe_div(sum(1 for t in trades if t.hit_t2), len(trades))
        r.t3_hit_rate = safe_div(sum(1 for t in trades if t.hit_t3), len(trades))

        # Breakdowns
        r.by_hour = self._breakdown(trades, lambda t: str(t.hour_of_day))
        r.by_day_of_week = self._breakdown(trades, lambda t: ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][t.day_of_week])
        r.by_session = self._breakdown(trades, lambda t: t.session)
        r.by_indication_type = self._breakdown(trades, lambda t: t.indication_type)
        r.by_correction_zone = self._breakdown(trades, lambda t: t.correction_zone)
        r.by_continuation_trigger = self._breakdown(trades, lambda t: t.continuation_trigger)
        r.by_tier = self._breakdown(trades, lambda t: t.signal_tier)
        r.by_score_bucket = self._breakdown(trades, lambda t: "80+" if t.composite_score >= 80 else "65-79" if t.composite_score >= 65 else "50-64" if t.composite_score >= 50 else "40-49")
        r.by_htf_alignment = self._breakdown(trades, lambda t: "aligned" if (t.htf_bias_4h == t.direction or t.htf_bias_1h == t.direction) else "counter" if t.htf_bias_4h and t.htf_bias_4h != t.direction and t.htf_bias_4h != "neutral" else "neutral")

        # Trade log (serializable)
        r.trades = [asdict(t) for t in trades]

        return r

    def _breakdown(self, trades: List[BacktestTrade], key_fn) -> Dict:
        groups = {}
        for t in trades:
            k = key_fn(t)
            if k not in groups:
                groups[k] = {"trades": 0, "wins": 0, "total_r": 0.0, "avg_r": 0.0}
            groups[k]["trades"] += 1
            if t.pnl_r > 0:
                groups[k]["wins"] += 1
            groups[k]["total_r"] += t.pnl_r

        for k, v in groups.items():
            v["win_rate"] = round(safe_div(v["wins"], v["trades"]), 3)
            v["avg_r"] = round(safe_div(v["total_r"], v["trades"]), 3)
            v["total_r"] = round(v["total_r"], 2)

        return dict(sorted(groups.items(), key=lambda x: x[1]["total_r"], reverse=True))
