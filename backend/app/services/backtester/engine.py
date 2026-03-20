"""
services/backtester/engine.py

Institutional-grade ICC backtesting engine.
- Fetches real NQ 5-minute OHLCV data from Polygon.io
- Computes all indicators on every bar
- Runs ICC rule engine on every bar
- Runs Claude AI only on high-confidence setups (>0.65)
- Tracks every trade with full P&L, MAE, MFE
- Analyzes win rate by time, setup type, indicator combo
"""

import asyncio
import httpx
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field


# ── DATA STRUCTURES ───────────────────────────────────────────────────────

@dataclass
class BacktestTrade:
    entry_time: datetime
    exit_time: Optional[datetime]
    symbol: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # target_hit / stop_hit / time_exit
    pnl_points: Optional[float] = None
    pnl_r: Optional[float] = None
    mae: Optional[float] = None  # max adverse excursion
    mfe: Optional[float] = None  # max favorable excursion
    confidence_score: float = 0.0
    indication_type: str = ""
    correction_zone: str = ""
    continuation_trigger: str = ""
    hour_of_day: int = 0
    session: str = ""
    htf_bias_4h: str = ""
    htf_bias_1h: str = ""
    rsi_at_entry: float = 0.0
    vol_expanding: bool = False
    ai_analyzed: bool = False
    ai_verdict: Optional[str] = None


@dataclass 
class BacktestResult:
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    total_bars: int
    total_setups: int
    total_trades: int
    winners: int
    losers: int
    win_rate: float
    avg_winner_r: float
    avg_loser_r: float
    expectancy_r: float
    profit_factor: float
    total_pnl_r: float
    max_drawdown_r: float
    max_consecutive_losses: int
    avg_mae: float
    avg_mfe: float
    trades: List[BacktestTrade] = field(default_factory=list)
    by_hour: Dict[int, Dict] = field(default_factory=dict)
    by_session: Dict[str, Dict] = field(default_factory=dict)
    by_indication: Dict[str, Dict] = field(default_factory=dict)
    by_htf_bias: Dict[str, Dict] = field(default_factory=dict)
    parameter_set: Dict[str, Any] = field(default_factory=dict)


# ── POLYGON DATA FETCHER ──────────────────────────────────────────────────

class PolygonDataFetcher:
    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch_bars(
        self,
        symbol: str,
        timeframe_minutes: int,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars from Polygon.io.
        Returns DataFrame with columns: time, open, high, low, close, volume
        """
        # Polygon uses different symbol format for futures
        # NQ1! -> NQ (continuous contract)
        poly_symbol = symbol.replace("1!", "").replace("!", "")

        multiplier = timeframe_minutes
        timespan = "minute"

        url = f"{self.BASE_URL}/v2/aggs/ticker/{poly_symbol}/range/{multiplier}/{timespan}/{start_date}/{end_date}"

        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": self.api_key,
        }

        all_bars = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    raise Exception(f"Polygon API error: {resp.status_code} {resp.text}")

                data = resp.json()
                results = data.get("results", [])
                all_bars.extend(results)

                # Handle pagination
                next_url = data.get("next_url")
                if next_url:
                    url = next_url
                    params = {"apiKey": self.api_key}
                else:
                    break

        if not all_bars:
            raise Exception(f"No data returned for {symbol}")

        df = pd.DataFrame(all_bars)
        df["time"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
        df = df[["time", "open", "high", "low", "close", "volume"]].sort_values("time").reset_index(drop=True)

        return df


# ── INDICATOR ENGINE ──────────────────────────────────────────────────────

class IndicatorEngine:
    """Computes all ICC indicators on a price DataFrame."""

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # EMAs
        df["ema8"]  = df["close"].ewm(span=8,  adjust=False).mean()
        df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

        # RSI
        df["rsi"] = self._rsi(df["close"], 14)

        # ATR
        df["atr"] = self._atr(df, 14)

        # Volume
        df["vol_sma20"] = df["volume"].rolling(20).mean()
        df["vol_expanding"] = df["volume"] > df["vol_sma20"] * 1.5

        # VWAP (daily reset)
        df["vwap"] = self._vwap(df)

        # Swing highs/lows (5-bar pivot)
        df["swing_high"] = df["high"].rolling(11, center=True).max() == df["high"]
        df["swing_low"]  = df["low"].rolling(11, center=True).min() == df["low"]

        # Last swing high/low
        df["last_swing_high"] = df.apply(
            lambda row: df.loc[:row.name][df["swing_high"] == True]["high"].iloc[-1]
            if len(df.loc[:row.name][df["swing_high"] == True]) > 0 else np.nan,
            axis=1
        )
        df["last_swing_low"] = df.apply(
            lambda row: df.loc[:row.name][df["swing_low"] == True]["low"].iloc[-1]
            if len(df.loc[:row.name][df["swing_low"] == True]) > 0 else np.nan,
            axis=1
        )

        # Structure breaks
        df["bull_break"] = (df["close"] > df["last_swing_high"].shift(1)).fillna(False)
        df["bear_break"] = (df["close"] < df["last_swing_low"].shift(1)).fillna(False)

        # FVG
        df["bull_fvg"] = df["low"] > df["high"].shift(2)
        df["bear_fvg"] = df["high"] < df["low"].shift(2)

        # Session (ET hours)
        df["hour_et"] = df["time"].dt.tz_convert("America/New_York").dt.hour
        df["session"] = df["hour_et"].apply(self._session)

        return df

    def compute_htf_bias(self, df_5m: pd.DataFrame) -> pd.DataFrame:
        """Compute 1H and 4H bias from 5-minute data by resampling."""
        df = df_5m.copy()
        df = df.set_index("time")

        # Resample to 1H
        df_1h = df.resample("1h").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna()
        df_1h["ema21_1h"] = df_1h["close"].ewm(span=21, adjust=False).mean()
        df_1h["ema50_1h"] = df_1h["close"].ewm(span=50, adjust=False).mean()
        df_1h["bull_1h"] = (df_1h["close"] > df_1h["ema21_1h"]) & (df_1h["close"] > df_1h["ema50_1h"])
        df_1h["bear_1h"] = (df_1h["close"] < df_1h["ema21_1h"]) & (df_1h["close"] < df_1h["ema50_1h"])

        # Resample to 4H
        df_4h = df.resample("4h").agg({
            "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"
        }).dropna()
        df_4h["ema21_4h"] = df_4h["close"].ewm(span=21, adjust=False).mean()
        df_4h["ema50_4h"] = df_4h["close"].ewm(span=50, adjust=False).mean()
        df_4h["bull_4h"] = (
            (df_4h["close"] > df_4h["ema21_4h"]) &
            (df_4h["ema21_4h"] > df_4h["ema50_4h"])
        )
        df_4h["bear_4h"] = (
            (df_4h["close"] < df_4h["ema21_4h"]) &
            (df_4h["ema21_4h"] < df_4h["ema50_4h"])
        )

        # Forward-fill HTF bias onto 5m bars
        df_5m = df_5m.set_index("time")
        df_5m["bull_1h"] = df_1h["bull_1h"].reindex(df_5m.index, method="ffill")
        df_5m["bear_1h"] = df_1h["bear_1h"].reindex(df_5m.index, method="ffill")
        df_5m["bull_4h"] = df_4h["bull_4h"].reindex(df_5m.index, method="ffill")
        df_5m["bear_4h"] = df_4h["bear_4h"].reindex(df_5m.index, method="ffill")
        df_5m["ema21_4h"] = df_4h["ema21_4h"].reindex(df_5m.index, method="ffill")
        df_5m["ema50_4h"] = df_4h["ema50_4h"].reindex(df_5m.index, method="ffill")
        df_5m["ema21_1h"] = df_1h["ema21_1h"].reindex(df_5m.index, method="ffill")
        df_5m["ema50_1h"] = df_1h["ema50_1h"].reindex(df_5m.index, method="ffill")

        return df_5m.reset_index()

    def _rsi(self, series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        hl = df["high"] - df["low"]
        hc = (df["high"] - df["close"].shift()).abs()
        lc = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def _vwap(self, df: pd.DataFrame) -> pd.Series:
        df = df.copy()
        df["date"] = df["time"].dt.date
        df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3
        df["cum_vol"] = df.groupby("date")["volume"].cumsum()
        df["cum_pv"] = df.groupby("date").apply(
            lambda g: (g["hlc3"] * g["volume"]).cumsum()
        ).reset_index(level=0, drop=True)
        return (df["cum_pv"] / df["cum_vol"]).fillna(df["close"])

    def _session(self, hour_et: int) -> str:
        if 4 <= hour_et < 9:
            return "us_premarket"
        elif 9 <= hour_et < 16:
            return "us_regular"
        elif 16 <= hour_et < 20:
            return "us_afterhours"
        else:
            return "globex"


# ── ICC SIGNAL DETECTOR ───────────────────────────────────────────────────

class ICCSignalDetector:
    """Detects ICC setups on each bar."""

    def detect(self, row: pd.Series, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Returns signal dict if ICC setup detected, else None."""

        min_rr      = config.get("min_rr", 2.5)
        req_4h_bias = config.get("require_4h_bias", True)
        req_vol     = config.get("require_volume", False)
        session_ok  = config.get("allowed_sessions", ["us_regular"])
        rsi_min     = config.get("rsi_min", 48)
        rsi_max     = config.get("rsi_max", 75)

        # Session filter
        if row.get("session") not in session_ok:
            return None

        # Skip if indicators not ready
        if pd.isna(row.get("ema21")) or pd.isna(row.get("rsi")):
            return None

        # HTF bias
        bull_4h = bool(row.get("bull_4h", False))
        bear_4h = bool(row.get("bear_4h", False))
        bull_1h = bool(row.get("bull_1h", False))
        bear_1h = bool(row.get("bear_1h", False))

        bull_bias = bull_4h if req_4h_bias else (bull_4h or bull_1h)
        bear_bias = bear_4h if req_4h_bias else (bear_4h or bear_1h)

        vol_ok = bool(row.get("vol_expanding", False)) if req_vol else True

        rsi = float(row.get("rsi", 50))
        ema8  = float(row.get("ema8", 0))
        ema21 = float(row.get("ema21", 0))
        vwap  = float(row.get("vwap", 0))
        close = float(row.get("close", 0))
        high  = float(row.get("high", 0))
        low   = float(row.get("low", 0))
        atr   = float(row.get("atr", 1))

        bull_break = bool(row.get("bull_break", False))
        bear_break = bool(row.get("bear_break", False))
        bull_fvg   = bool(row.get("bull_fvg", False))
        bear_fvg   = bool(row.get("bear_fvg", False))

        # ── BULLISH ICC ───────────────────────────────────────────────────
        bull_icc = (
            bull_bias and
            (bull_break or bull_fvg or close > vwap) and
            ema8 > ema21 and
            rsi_min <= rsi <= rsi_max and
            vol_ok
        )

        # ── BEARISH ICC ───────────────────────────────────────────────────
        bear_icc = (
            bear_bias and
            (bear_break or bear_fvg or close < vwap) and
            ema8 < ema21 and
            (100 - rsi_max) <= rsi <= (100 - rsi_min) and
            vol_ok
        )

        if not bull_icc and not bear_icc:
            return None

        direction = "bullish" if bull_icc else "bearish"

        # Entry/stop/target
        if direction == "bullish":
            entry  = close
            stop   = min(low, vwap) - atr * 0.5
            target = entry + (entry - stop) * min_rr
            indication = "structure_break_high" if bull_break else "displacement_up"
            correction = "fair_value_gap" if bull_fvg else "vwap"
        else:
            entry  = close
            stop   = max(high, vwap) + atr * 0.5
            target = entry - (entry - stop) * min_rr
            indication = "structure_break_low" if bear_break else "displacement_down"
            correction = "fair_value_gap" if bear_fvg else "vwap"

        risk = abs(entry - stop)
        if risk == 0:
            return None

        actual_rr = abs(target - entry) / risk

        # Quick confidence score
        score = 0.5
        if bull_4h or bear_4h:
            score += 0.15
        if bull_1h or bear_1h:
            score += 0.10
        if bull_break or bear_break:
            score += 0.10
        if bull_fvg or bear_fvg:
            score += 0.08
        if bool(row.get("vol_expanding", False)):
            score += 0.07
        if 50 < rsi < 65 and direction == "bullish":
            score += 0.05
        if 35 < rsi < 50 and direction == "bearish":
            score += 0.05

        return {
            "direction": direction,
            "entry_price": entry,
            "stop_price": stop,
            "target_price": target,
            "risk_reward": actual_rr,
            "confidence_score": min(score, 1.0),
            "indication_type": indication,
            "correction_zone_type": correction,
            "continuation_trigger_type": "rejection_candle",
            "htf_bias_4h": "bullish" if bull_4h else "bearish" if bear_4h else "neutral",
            "htf_bias_1h": "bullish" if bull_1h else "bearish" if bear_1h else "neutral",
            "rsi": rsi,
            "vol_expanding": bool(row.get("vol_expanding", False)),
            "session": row.get("session", ""),
            "hour": int(row.get("hour_et", 0)),
        }


# ── TRADE SIMULATOR ───────────────────────────────────────────────────────

class TradeSimulator:
    """Simulates trade outcomes on subsequent bars."""

    def simulate(
        self,
        signal: Dict[str, Any],
        entry_time: datetime,
        future_bars: pd.DataFrame,
        max_bars: int = 50,
    ) -> Tuple[Optional[float], Optional[str], Optional[float], Optional[float]]:
        """
        Returns (exit_price, exit_reason, mae, mfe)
        """
        entry  = signal["entry_price"]
        stop   = signal["stop_price"]
        target = signal["target_price"]
        direction = signal["direction"]

        mae = 0.0
        mfe = 0.0

        for i, (_, bar) in enumerate(future_bars.head(max_bars).iterrows()):
            if direction == "bullish":
                adverse   = entry - bar["low"]
                favorable = bar["high"] - entry
                if bar["low"] <= stop:
                    return stop, "stop_hit", max(mae, adverse), max(mfe, favorable)
                if bar["high"] >= target:
                    return target, "target_hit", max(mae, adverse), max(mfe, favorable)
            else:
                adverse   = bar["high"] - entry
                favorable = entry - bar["low"]
                if bar["high"] >= stop:
                    return stop, "stop_hit", max(mae, adverse), max(mfe, favorable)
                if bar["low"] <= target:
                    return target, "target_hit", max(mae, adverse), max(mfe, favorable)

            mae = max(mae, adverse if direction == "bullish" else bar["high"] - entry)
            mfe = max(mfe, favorable)

        # Time exit — close at last bar's close
        last_close = future_bars.iloc[-1]["close"] if len(future_bars) > 0 else entry
        return last_close, "time_exit", mae, mfe


# ── MAIN BACKTESTER ───────────────────────────────────────────────────────

class ICCBacktester:
    """
    Full backtesting engine. 
    Usage:
        backtester = ICCBacktester(polygon_api_key, anthropic_api_key)
        result = await backtester.run("NQ", days=365, config={...})
    """

    def __init__(self, polygon_api_key: str, anthropic_api_key: str = ""):
        self.fetcher   = PolygonDataFetcher(polygon_api_key)
        self.indicators = IndicatorEngine()
        self.detector  = ICCSignalDetector()
        self.simulator = TradeSimulator()
        self.anthropic_key = anthropic_api_key

    async def run(
        self,
        symbol: str = "NQ",
        days: int = 365,
        config: Optional[Dict[str, Any]] = None,
    ) -> BacktestResult:
        """Run full backtest. Returns BacktestResult."""

        if config is None:
            config = {
                "min_rr": 2.5,
                "require_4h_bias": True,
                "require_volume": False,
                "allowed_sessions": ["us_regular"],
                "rsi_min": 48,
                "rsi_max": 75,
                "ai_confidence_threshold": 0.65,
            }

        end_date   = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        print(f"Fetching {symbol} 5m data from {start_date} to {end_date}...")
        df = await self.fetcher.fetch_bars(symbol, 5, start_date, end_date)
        print(f"Fetched {len(df)} bars")

        print("Computing indicators...")
        df = self.indicators.compute(df)
        df = self.indicators.compute_htf_bias(df)

        print("Detecting ICC setups...")
        trades: List[BacktestTrade] = []
        in_trade = False
        setups_found = 0

        for i in range(50, len(df) - 50):
            if in_trade:
                continue

            row = df.iloc[i]
            signal = self.detector.detect(row, config)

            if signal is None:
                continue

            setups_found += 1

            # Run AI only on high-confidence setups
            ai_analyzed = False
            ai_verdict = None
            if signal["confidence_score"] >= config.get("ai_confidence_threshold", 0.65) and self.anthropic_key:
                try:
                    from app.services.ai_analysis.claude_evaluator import analyze_with_claude
                    ai_result = await analyze_with_claude(signal, self.anthropic_key)
                    if ai_result:
                        ai_analyzed = True
                        ai_verdict = ai_result.get("verdict")
                        # Skip if AI says invalid
                        if ai_verdict == "invalid_setup":
                            continue
                except Exception as e:
                    print(f"AI analysis error: {e}")

            # Simulate trade outcome
            future_bars = df.iloc[i+1:i+51]
            exit_price, exit_reason, mae, mfe = self.simulator.simulate(
                signal, row["time"], future_bars
            )

            if exit_price is None:
                continue

            risk = abs(signal["entry_price"] - signal["stop_price"])
            pnl_points = (exit_price - signal["entry_price"]) if signal["direction"] == "bullish" else (signal["entry_price"] - exit_price)
            pnl_r = pnl_points / risk if risk > 0 else 0

            trade = BacktestTrade(
                entry_time=row["time"],
                exit_time=df.iloc[min(i+51, len(df)-1)]["time"],
                symbol=symbol,
                direction=signal["direction"],
                entry_price=signal["entry_price"],
                stop_price=signal["stop_price"],
                target_price=signal["target_price"],
                exit_price=exit_price,
                exit_reason=exit_reason,
                pnl_points=pnl_points,
                pnl_r=pnl_r,
                mae=mae,
                mfe=mfe,
                confidence_score=signal["confidence_score"],
                indication_type=signal["indication_type"],
                correction_zone=signal["correction_zone_type"],
                continuation_trigger=signal["continuation_trigger_type"],
                hour_of_day=signal["hour"],
                session=signal["session"],
                htf_bias_4h=signal["htf_bias_4h"],
                htf_bias_1h=signal["htf_bias_1h"],
                rsi_at_entry=signal["rsi"],
                vol_expanding=signal["vol_expanding"],
                ai_analyzed=ai_analyzed,
                ai_verdict=ai_verdict,
            )
            trades.append(trade)
            in_trade = False  # Allow next trade (no position sizing for now)

        print(f"Found {setups_found} setups, {len(trades)} trades")

        return self._compute_results(
            trades, symbol, "5m", start_date, end_date,
            len(df), setups_found, config
        )

    def _compute_results(
        self,
        trades: List[BacktestTrade],
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        total_bars: int,
        total_setups: int,
        config: Dict,
    ) -> BacktestResult:

        if not trades:
            return BacktestResult(
                symbol=symbol, timeframe=timeframe,
                start_date=start_date, end_date=end_date,
                total_bars=total_bars, total_setups=total_setups,
                total_trades=0, winners=0, losers=0,
                win_rate=0, avg_winner_r=0, avg_loser_r=0,
                expectancy_r=0, profit_factor=0, total_pnl_r=0,
                max_drawdown_r=0, max_consecutive_losses=0,
                avg_mae=0, avg_mfe=0, parameter_set=config,
            )

        winners = [t for t in trades if t.pnl_r and t.pnl_r > 0]
        losers  = [t for t in trades if t.pnl_r and t.pnl_r <= 0]

        win_rate     = len(winners) / len(trades)
        avg_winner_r = sum(t.pnl_r for t in winners) / len(winners) if winners else 0
        avg_loser_r  = sum(t.pnl_r for t in losers)  / len(losers)  if losers  else 0
        expectancy_r = win_rate * avg_winner_r + (1 - win_rate) * avg_loser_r
        gross_wins   = sum(t.pnl_r for t in winners) if winners else 0
        gross_losses = abs(sum(t.pnl_r for t in losers)) if losers else 1
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else 0
        total_pnl_r  = sum(t.pnl_r for t in trades if t.pnl_r)

        # Max drawdown
        equity = 0
        peak   = 0
        max_dd = 0
        for t in trades:
            equity += t.pnl_r or 0
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)

        # Max consecutive losses
        max_consec = 0
        current_consec = 0
        for t in trades:
            if t.pnl_r and t.pnl_r <= 0:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0

        avg_mae = sum(t.mae or 0 for t in trades) / len(trades)
        avg_mfe = sum(t.mfe or 0 for t in trades) / len(trades)

        # By hour analysis
        by_hour = {}
        for t in trades:
            h = t.hour_of_day
            if h not in by_hour:
                by_hour[h] = {"trades": 0, "wins": 0, "total_r": 0}
            by_hour[h]["trades"] += 1
            if t.pnl_r and t.pnl_r > 0:
                by_hour[h]["wins"] += 1
            by_hour[h]["total_r"] += t.pnl_r or 0
        for h in by_hour:
            n = by_hour[h]["trades"]
            by_hour[h]["win_rate"] = by_hour[h]["wins"] / n if n > 0 else 0

        # By session
        by_session = {}
        for t in trades:
            s = t.session
            if s not in by_session:
                by_session[s] = {"trades": 0, "wins": 0, "total_r": 0}
            by_session[s]["trades"] += 1
            if t.pnl_r and t.pnl_r > 0:
                by_session[s]["wins"] += 1
            by_session[s]["total_r"] += t.pnl_r or 0

        # By indication type
        by_indication = {}
        for t in trades:
            ind = t.indication_type
            if ind not in by_indication:
                by_indication[ind] = {"trades": 0, "wins": 0, "total_r": 0}
            by_indication[ind]["trades"] += 1
            if t.pnl_r and t.pnl_r > 0:
                by_indication[ind]["wins"] += 1
            by_indication[ind]["total_r"] += t.pnl_r or 0

        # By HTF bias
        by_htf = {}
        for t in trades:
            bias = f"4H:{t.htf_bias_4h}/1H:{t.htf_bias_1h}"
            if bias not in by_htf:
                by_htf[bias] = {"trades": 0, "wins": 0, "total_r": 0}
            by_htf[bias]["trades"] += 1
            if t.pnl_r and t.pnl_r > 0:
                by_htf[bias]["wins"] += 1
            by_htf[bias]["total_r"] += t.pnl_r or 0

        return BacktestResult(
            symbol=symbol, timeframe=timeframe,
            start_date=start_date, end_date=end_date,
            total_bars=total_bars, total_setups=total_setups,
            total_trades=len(trades),
            winners=len(winners), losers=len(losers),
            win_rate=round(win_rate, 3),
            avg_winner_r=round(avg_winner_r, 2),
            avg_loser_r=round(avg_loser_r, 2),
            expectancy_r=round(expectancy_r, 3),
            profit_factor=round(profit_factor, 2),
            total_pnl_r=round(total_pnl_r, 2),
            max_drawdown_r=round(max_dd, 2),
            max_consecutive_losses=max_consec,
            avg_mae=round(avg_mae, 2),
            avg_mfe=round(avg_mfe, 2),
            trades=trades,
            by_hour=by_hour,
            by_session=by_session,
            by_indication=by_indication,
            by_htf_bias=by_htf,
            parameter_set=config,
        )
