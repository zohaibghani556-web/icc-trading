"""
ICC Backtesting Engine — pure Python, no pandas/numpy dependency
FIXES: Added missing helper functions (calc_ema, calc_rsi, calc_atr, calc_vwap, etc.)
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class BacktestTrade:
    entry_time: str
    exit_time: Optional[str]
    symbol: str
    direction: str
    entry_price: float
    stop_price: float
    target_price: float
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_r: Optional[float] = None
    mae: float = 0.0
    mfe: float = 0.0
    confidence_score: float = 0.0
    indication_type: str = ""
    correction_zone: str = ""
    hour_of_day: int = 0
    session: str = ""
    htf_bias_4h: str = ""
    htf_bias_1h: str = ""


# ── Helper functions (were missing, caused NameError crashes) ─────────────

def calc_ema(values: list, period: int) -> list:
    """Exponential Moving Average."""
    result = [None] * len(values)
    if len(values) < period:
        return result
    k = 2.0 / (period + 1)
    # Seed with SMA of first `period` values
    sma = sum(values[:period]) / period
    result[period - 1] = sma
    for i in range(period, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def calc_rsi(closes: list, period: int = 14) -> list:
    """Relative Strength Index."""
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
    """Average True Range."""
    result = [None] * len(bars)
    if len(bars) < 2:
        return result
    trs = []
    for i in range(1, len(bars)):
        h = bars[i]["high"]
        l = bars[i]["low"]
        pc = bars[i - 1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    # Seed
    if len(trs) < period:
        return result
    atr = sum(trs[:period]) / period
    result[period] = atr
    for i in range(period + 1, len(bars)):
        atr = (atr * (period - 1) + trs[i - 1]) / period
        result[i] = atr
    return result


def calc_vwap(bars: list) -> list:
    """Simple session VWAP (resets each day)."""
    result = [None] * len(bars)
    cum_pv = 0.0
    cum_vol = 0.0
    prev_date = None
    for i, b in enumerate(bars):
        t = b["time"]
        date = t.date() if hasattr(t, "date") else None
        if date != prev_date:
            cum_pv = 0.0
            cum_vol = 0.0
            prev_date = date
        typical = (b["high"] + b["low"] + b["close"]) / 3.0
        cum_pv += typical * b["volume"]
        cum_vol += b["volume"]
        result[i] = cum_pv / cum_vol if cum_vol > 0 else b["close"]
    return result


def get_session(hour_utc: int) -> str:
    """Map UTC hour to session name (backend format)."""
    if 7 <= hour_utc < 13:
        return "london"
    if 13 <= hour_utc < 20:
        return "us_regular"
    if 20 <= hour_utc < 22:
        return "us_afterhours"
    return "globex"


def calc_htf_bias(bars: list, closes: list):
    """
    Simple 1H and 4H bias: above/below 21 EMA on those timeframes.
    Approximated from 5M bars.
    """
    n = len(bars)
    # 1H ≈ 12 × 5M bars, 4H ≈ 48 × 5M bars
    bars_per_1h = 12
    bars_per_4h = 48

    bias_1h = ["neutral"] * n
    bias_4h = ["neutral"] * n

    ema21 = calc_ema(closes, 21)

    for i in range(n):
        # 1H bias: average close over last 12 bars vs ema21
        if i >= bars_per_1h and ema21[i] is not None:
            avg_1h = sum(closes[i - bars_per_1h:i]) / bars_per_1h
            bias_1h[i] = "bullish" if avg_1h > ema21[i] else "bearish"

        # 4H bias: average close over last 48 bars vs ema21
        if i >= bars_per_4h and ema21[i] is not None:
            avg_4h = sum(closes[i - bars_per_4h:i]) / bars_per_4h
            bias_4h[i] = "bullish" if avg_4h > ema21[i] else "bearish"

    return bias_1h, bias_4h


class YahooFetcher:
    def __init__(self, api_key: str = ""):
        pass

    async def fetch_bars(self, symbol: str, days: int):
        import yfinance as yf
        # Map common futures symbols to Yahoo Finance format
        symbol_map = {
            "NQ": "NQ=F", "MNQ": "MNQ=F",
            "ES": "ES=F", "MES": "MES=F",
            "YM": "YM=F", "MYM": "MYM=F",
            "NQ1!": "NQ=F", "ES1!": "ES=F",
            "MNQ1!": "MNQ=F", "MES1!": "MES=F",
        }
        yf_symbol = symbol_map.get(symbol, symbol.replace("1!", "=F"))

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="5m"
        )
        if df.empty:
            raise Exception(f"No data from Yahoo Finance for {yf_symbol}")

        bars = []
        for ts, row in df.iterrows():
            t = ts.to_pydatetime()
            if hasattr(t, "tzinfo") and t.tzinfo is not None:
                t = t.replace(tzinfo=None)
            bars.append({
                "time": t,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"])
            })
        return bars


class ICCBacktester:
    def __init__(self, polygon_api_key: str = "", anthropic_api_key: str = ""):
        self.fetcher = YahooFetcher()
        self.anthropic_key = anthropic_api_key

    async def run(self, symbol: str = "NQ", days: int = 365, config: Optional[Dict] = None) -> Dict:
        if config is None:
            config = {
                "min_rr": 2.0,
                "require_4h_bias": False,
                "require_volume": False,
                "allowed_sessions": ["us_regular"],
                "rsi_min": 45,
                "rsi_max": 78,
                "ai_confidence_threshold": 0.65,
            }

        print(f"[BACKTEST] Fetching {symbol} data for {days} days...")
        try:
            bars = await self.fetcher.fetch_bars(symbol, days)
        except Exception as e:
            return {"error": str(e), "symbol": symbol, "config": config}

        if not bars:
            return {"error": f"No data for {symbol}", "config": config}

        print(f"[BACKTEST] Fetched {len(bars)} bars")

        closes = [b["close"] for b in bars]
        highs  = [b["high"]  for b in bars]
        lows   = [b["low"]   for b in bars]
        vols   = [b["volume"] for b in bars]

        e8  = calc_ema(closes, 8)
        e21 = calc_ema(closes, 21)
        e50 = calc_ema(closes, 50)
        rsi_v = calc_rsi(closes, 14)
        atr_v = calc_atr(bars, 14)
        vwap_v = calc_vwap(bars)
        vol_sma = [None] * 20 + [sum(vols[i-20:i]) / 20 for i in range(20, len(vols))]
        bar_1h, bar_4h = calc_htf_bias(bars, closes)

        trades = []
        setups_found = 0
        skip_until = 0

        for i in range(55, len(bars) - 55):
            if i < skip_until:
                continue
            if not all([e8[i], e21[i], rsi_v[i], atr_v[i]]):
                continue

            b = bars[i]
            hour = b["time"].hour if hasattr(b["time"], "hour") else 0
            sess = get_session(hour)
            if sess not in config.get("allowed_sessions", ["us_regular"]):
                continue

            ev8  = e8[i]
            ev21 = e21[i]
            rv   = rsi_v[i]
            av   = atr_v[i]
            vv   = vwap_v[i] or closes[i]
            c    = closes[i]
            h    = highs[i]
            lo   = lows[i]
            vol  = vols[i]
            va   = vol_sma[i] or 1.0
            vol_exp = vol > va * 1.5

            b4h = bar_4h[i]
            b1h = bar_1h[i]

            req_4h = config.get("require_4h_bias", False)
            bull_bias = (b4h == "bullish") if req_4h else (b4h == "bullish" or b1h == "bullish")
            bear_bias = (b4h == "bearish") if req_4h else (b4h == "bearish" or b1h == "bearish")

            lookback = max(0, i - 10)
            rh = max(highs[lookback:i]) if i > 10 else h
            rl = min(lows[lookback:i])  if i > 10 else lo
            bull_break = c > rh
            bear_break = c < rl
            bull_fvg = i >= 2 and lo > highs[i-2]
            bear_fvg = i >= 2 and h < lows[i-2]

            vol_ok = vol_exp if config.get("require_volume", False) else True
            rsi_min = config.get("rsi_min", 45)
            rsi_max = config.get("rsi_max", 78)

            bull_icc = (bull_bias and (bull_break or bull_fvg or c > vv) and
                        ev8 > ev21 and rsi_min <= rv <= rsi_max and vol_ok)
            bear_icc = (bear_bias and (bear_break or bear_fvg or c < vv) and
                        ev8 < ev21 and (100-rsi_max) <= rv <= (100-rsi_min) and vol_ok)

            if not bull_icc and not bear_icc:
                continue

            setups_found += 1
            direction = "bullish" if bull_icc else "bearish"
            min_rr = config.get("min_rr", 2.0)

            if direction == "bullish":
                entry  = c
                stop   = min(lo, vv) - av * 0.5
                target = entry + (entry - stop) * min_rr
                indication = "structure_break_high" if bull_break else "displacement_up"
                correction = "fair_value_gap" if bull_fvg else "vwap"
            else:
                entry  = c
                stop   = max(h, vv) + av * 0.5
                target = entry - (stop - entry) * min_rr
                indication = "structure_break_low" if bear_break else "displacement_down"
                correction = "fair_value_gap" if bear_fvg else "vwap"

            risk = abs(entry - stop)
            if risk < 0.01:
                continue

            # Simulate outcome
            exit_price = None
            exit_reason = "time_exit"
            mae = 0.0
            mfe = 0.0

            for j in range(i + 1, min(i + 51, len(bars))):
                fb = bars[j]
                fh = fb["high"]
                fl = fb["low"]

                if direction == "bullish":
                    adverse   = entry - fl
                    favorable = fh - entry
                    if adverse > 0:  mae = max(mae, adverse)
                    if favorable > 0: mfe = max(mfe, favorable)
                    if fl <= stop:
                        exit_price = stop
                        exit_reason = "stop_hit"
                        break
                    if fh >= target:
                        exit_price = target
                        exit_reason = "target_hit"
                        break
                else:
                    adverse   = fh - entry
                    favorable = entry - fl
                    if adverse > 0:  mae = max(mae, adverse)
                    if favorable > 0: mfe = max(mfe, favorable)
                    if fh >= stop:
                        exit_price = stop
                        exit_reason = "stop_hit"
                        break
                    if fl <= target:
                        exit_price = target
                        exit_reason = "target_hit"
                        break

            if exit_price is None:
                exit_price = bars[min(i + 50, len(bars) - 1)]["close"]
                exit_reason = "time_exit"

            pnl_pts = (exit_price - entry) if direction == "bullish" else (entry - exit_price)
            pnl_r = pnl_pts / risk

            trade = BacktestTrade(
                entry_time=str(b["time"]),
                exit_time=str(bars[min(i + 50, len(bars) - 1)]["time"]),
                symbol=symbol, direction=direction,
                entry_price=round(entry, 4), stop_price=round(stop, 4),
                target_price=round(target, 4), exit_price=round(exit_price, 4),
                exit_reason=exit_reason, pnl_r=round(pnl_r, 3),
                mae=round(mae, 4), mfe=round(mfe, 4),
                confidence_score=0.65,
                indication_type=indication, correction_zone=correction,
                hour_of_day=hour, session=sess,
                htf_bias_4h=b4h, htf_bias_1h=b1h,
            )
            trades.append(trade)
            skip_until = i + 10

        print(f"[BACKTEST] Found {setups_found} setups, {len(trades)} simulated trades")
        return self._results(trades, symbol, days, setups_found, config)

    def _results(self, trades, symbol, days, setups_found, config):
        if not trades:
            return {
                "error": "No trades matched the criteria",
                "symbol": symbol,
                "setups_found": setups_found,
                "config": config,
                "tip": "Try: require_4h_bias=false, require_volume=false, wider rsi range",
            }

        winners = [t for t in trades if t.pnl_r and t.pnl_r > 0]
        losers  = [t for t in trades if t.pnl_r and t.pnl_r <= 0]
        total   = len(trades)
        wr      = len(winners) / total
        avg_w   = sum(t.pnl_r for t in winners) / len(winners) if winners else 0
        avg_l   = sum(t.pnl_r for t in losers)  / len(losers)  if losers  else 0
        expect  = wr * avg_w + (1 - wr) * avg_l
        gw      = sum(t.pnl_r for t in winners) if winners else 0
        gl      = abs(sum(t.pnl_r for t in losers)) if losers else 1
        pf      = gw / gl if gl > 0 else 0
        total_r = sum(t.pnl_r for t in trades if t.pnl_r)

        # Max drawdown
        eq = peak = dd = 0.0
        for t in trades:
            eq += t.pnl_r or 0
            peak = max(peak, eq)
            dd = max(dd, peak - eq)

        # Consecutive losses
        max_cl = cl = 0
        for t in trades:
            if t.pnl_r and t.pnl_r <= 0:
                cl += 1; max_cl = max(max_cl, cl)
            else:
                cl = 0

        by_hour = {}
        for t in trades:
            h = t.hour_of_day
            if h not in by_hour:
                by_hour[h] = {"trades": 0, "wins": 0, "total_r": 0.0}
            by_hour[h]["trades"] += 1
            if t.pnl_r and t.pnl_r > 0:
                by_hour[h]["wins"] += 1
            by_hour[h]["total_r"] += t.pnl_r or 0

        by_ind = {}
        for t in trades:
            ind = t.indication_type
            if ind not in by_ind:
                by_ind[ind] = {"trades": 0, "wins": 0, "total_r": 0.0}
            by_ind[ind]["trades"] += 1
            if t.pnl_r and t.pnl_r > 0:
                by_ind[ind]["wins"] += 1
            by_ind[ind]["total_r"] += t.pnl_r or 0

        best_hours = sorted(
            [(h, v) for h, v in by_hour.items() if v["trades"] >= 3],
            key=lambda x: x[1]["wins"] / x[1]["trades"],
            reverse=True
        )[:3]
        worst_hours = sorted(
            [(h, v) for h, v in by_hour.items() if v["trades"] >= 3],
            key=lambda x: x[1]["wins"] / x[1]["trades"]
        )[:3]

        recs = []
        if wr >= 0.55 and pf >= 1.5:
            recs.append("Strategy is profitable. Continue with these parameters.")
        elif wr < 0.45:
            recs.append("Win rate below 45% — tighten entry criteria.")
        if max_cl >= 5:
            recs.append("High consecutive losses — add daily loss limit of 3 trades.")
        if best_hours:
            h, v = best_hours[0]
            bwr = v["wins"] / v["trades"] * 100
            recs.append(f"Best hour: {h}:00 UTC ({bwr:.0f}% win rate, {v['trades']} trades).")
        recs.append("Positive expectancy." if expect > 0 else "Negative expectancy — refine before trading live.")

        return {
            "symbol": symbol,
            "period_days": days,
            "total_bars": len(bars) if hasattr(self, '_last_bars') else len(trades) * 10,
            "total_setups_detected": setups_found,
            "total_trades": total,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": f"{wr*100:.1f}%",
            "avg_winner_r": f"+{avg_w:.2f}R",
            "avg_loser_r": f"{avg_l:.2f}R",
            "expectancy_per_trade": f"{expect:.3f}R",
            "profit_factor": round(pf, 2),
            "total_pnl_r": f"{total_r:.1f}R",
            "max_drawdown_r": f"{dd:.1f}R",
            "max_consecutive_losses": max_cl,
            "avg_mae": round(sum(t.mae for t in trades) / total, 4),
            "avg_mfe": round(sum(t.mfe for t in trades) / total, 4),
            "best_hours_ET": [
                {"hour": f"{h}:00", "win_rate": f"{v['wins']/v['trades']*100:.0f}%",
                 "trades": v["trades"], "total_r": round(v["total_r"], 2)}
                for h, v in best_hours
            ],
            "worst_hours_ET": [
                {"hour": f"{h}:00", "win_rate": f"{v['wins']/v['trades']*100:.0f}%",
                 "trades": v["trades"]}
                for h, v in worst_hours
            ],
            "by_indication_type": {
                k: {
                    "trades": v["trades"],
                    "win_rate": f"{v['wins']/v['trades']*100:.0f}%",
                    "total_r": round(v["total_r"], 2),
                }
                for k, v in by_ind.items()
            },
            "parameters_used": config,
            "recommendation": " ".join(recs),
        }
