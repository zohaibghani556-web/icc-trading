"""
ICC Backtesting Engine — pure Python, no pandas/numpy dependencies
"""
import httpx
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
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
    mae: Optional[float] = None
    mfe: Optional[float] = None
    confidence_score: float = 0.0
    indication_type: str = ""
    correction_zone: str = ""
    hour_of_day: int = 0
    session: str = ""
    htf_bias_4h: str = ""
    htf_bias_1h: str = ""


class PolygonFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def fetch_bars(self, symbol: str, days: int) -> List[Dict]:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        poly_symbol = symbol.replace("1!", "").replace("!", "")
        url = f"https://api.polygon.io/v2/aggs/ticker/{poly_symbol}/range/5/minute/{start_date}/{end_date}"
        params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": self.api_key}
        all_bars = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            while url:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    raise Exception(f"Polygon error: {resp.status_code} {resp.text}")
                data = resp.json()
                results = data.get("results", [])
                all_bars.extend(results)
                next_url = data.get("next_url")
                if next_url:
                    url = next_url
                    params = {"apiKey": self.api_key}
                else:
                    break
        bars = []
        for b in all_bars:
            bars.append({
                "time": datetime.fromtimestamp(b["t"] / 1000),
                "open": b["o"], "high": b["h"], "low": b["l"],
                "close": b["c"], "volume": b["v"]
            })
        return bars


def ema(values: List[float], period: int) -> List[float]:
    result = [None] * len(values)
    k = 2 / (period + 1)
    for i, v in enumerate(values):
        if i < period - 1:
            continue
        if i == period - 1:
            result[i] = sum(values[i-period+1:i+1]) / period
        else:
            result[i] = v * k + result[i-1] * (1 - k)
    return result


def rsi(closes: List[float], period: int = 14) -> List[float]:
    result = [None] * len(closes)
    for i in range(period, len(closes)):
        gains, losses = [], []
        for j in range(i - period + 1, i + 1):
            delta = closes[j] - closes[j-1]
            (gains if delta > 0 else losses).append(abs(delta))
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0
        result[i] = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 100
    return result


def atr(bars: List[Dict], period: int = 14) -> List[float]:
    result = [None] * len(bars)
    trs = []
    for i in range(1, len(bars)):
        tr = max(
            bars[i]["high"] - bars[i]["low"],
            abs(bars[i]["high"] - bars[i-1]["close"]),
            abs(bars[i]["low"] - bars[i-1]["close"])
        )
        trs.append(tr)
        if len(trs) >= period:
            result[i] = sum(trs[-period:]) / period
    return result


def vwap_daily(bars: List[Dict]) -> List[float]:
    result = []
    cum_pv = cum_vol = 0
    current_date = None
    for b in bars:
        d = b["time"].date()
        if d != current_date:
            cum_pv = cum_vol = 0
            current_date = d
        hlc3 = (b["high"] + b["low"] + b["close"]) / 3
        cum_pv += hlc3 * b["volume"]
        cum_vol += b["volume"]
        result.append(cum_pv / cum_vol if cum_vol > 0 else b["close"])
    return result


def session(hour_et: int) -> str:
    if 4 <= hour_et < 9: return "us_premarket"
    if 9 <= hour_et < 16: return "us_regular"
    if 16 <= hour_et < 20: return "us_afterhours"
    return "globex"


def compute_htf_bias(bars: List[Dict], closes: List[float], times: List[datetime]):
    """Compute 1H and 4H EMA bias for each bar."""
    # Build hourly and 4H close arrays
    hourly = {}
    four_hourly = {}
    for i, b in enumerate(bars):
        hk = b["time"].replace(minute=0, second=0, microsecond=0)
        fhk = b["time"].replace(hour=(b["time"].hour // 4) * 4, minute=0, second=0, microsecond=0)
        hourly[hk] = closes[i]
        four_hourly[fhk] = closes[i]

    h_times = sorted(hourly.keys())
    h_closes = [hourly[t] for t in h_times]
    fh_times = sorted(four_hourly.keys())
    fh_closes = [four_hourly[t] for t in fh_times]

    h_ema21 = ema(h_closes, 21)
    h_ema50 = ema(h_closes, 50)
    fh_ema21 = ema(fh_closes, 21)
    fh_ema50 = ema(fh_closes, 50)

    h_bias = {}
    for i, t in enumerate(h_times):
        if h_ema21[i] and h_ema50[i]:
            if h_closes[i] > h_ema21[i] and h_closes[i] > h_ema50[i]:
                h_bias[t] = "bullish"
            elif h_closes[i] < h_ema21[i] and h_closes[i] < h_ema50[i]:
                h_bias[t] = "bearish"
            else:
                h_bias[t] = "neutral"

    fh_bias = {}
    for i, t in enumerate(fh_times):
        if fh_ema21[i] and fh_ema50[i]:
            if fh_closes[i] > fh_ema21[i] and fh_ema21[i] > fh_ema50[i]:
                fh_bias[t] = "bullish"
            elif fh_closes[i] < fh_ema21[i] and fh_ema21[i] < fh_ema50[i]:
                fh_bias[t] = "bearish"
            else:
                fh_bias[t] = "neutral"

    # Map back to 5m bars
    bar_1h_bias = []
    bar_4h_bias = []
    last_1h = "neutral"
    last_4h = "neutral"
    for b in bars:
        hk = b["time"].replace(minute=0, second=0, microsecond=0)
        fhk = b["time"].replace(hour=(b["time"].hour // 4) * 4, minute=0, second=0, microsecond=0)
        if hk in h_bias: last_1h = h_bias[hk]
        if fhk in fh_bias: last_4h = fh_bias[fhk]
        bar_1h_bias.append(last_1h)
        bar_4h_bias.append(last_4h)

    return bar_1h_bias, bar_4h_bias


class ICCBacktester:
    def __init__(self, polygon_api_key: str, anthropic_api_key: str = ""):
        self.fetcher = PolygonFetcher(polygon_api_key)
        self.anthropic_key = anthropic_api_key

    async def run(self, symbol: str = "NQ", days: int = 365, config: Optional[Dict] = None) -> Dict:
        if config is None:
            config = {
                "min_rr": 2.5, "require_4h_bias": True, "require_volume": False,
                "allowed_sessions": ["us_regular"], "rsi_min": 48, "rsi_max": 75,
                "ai_confidence_threshold": 0.65,
            }

        print(f"Fetching {symbol} data...")
        bars = await self.fetcher.fetch_bars(symbol, days)
        print(f"Fetched {len(bars)} bars")

        closes = [b["close"] for b in bars]
        highs  = [b["high"]  for b in bars]
        lows   = [b["low"]   for b in bars]
        vols   = [b["volume"] for b in bars]
        times  = [b["time"]  for b in bars]

        print("Computing indicators...")
        ema8_vals  = ema(closes, 8)
        ema21_vals = ema(closes, 21)
        ema50_vals = ema(closes, 50)
        rsi_vals   = rsi(closes, 14)
        atr_vals   = atr(bars, 14)
        vwap_vals  = vwap_daily(bars)
        vol_sma = [None]*20 + [sum(vols[i-20:i])/20 for i in range(20, len(vols))]

        bar_1h_bias, bar_4h_bias = compute_htf_bias(bars, closes, times)

        print("Running ICC signal detection...")
        trades = []
        setups_found = 0
        in_trade = False

        for i in range(50, len(bars) - 55):
            if in_trade:
                in_trade = False
                continue

            if not all([ema8_vals[i], ema21_vals[i], rsi_vals[i], atr_vals[i]]):
                continue

            b = bars[i]
            hour_et = b["time"].hour
            sess = session(hour_et)

            if sess not in config["allowed_sessions"]:
                continue

            e8  = ema8_vals[i]
            e21 = ema21_vals[i]
            rsi_v = rsi_vals[i]
            atr_v = atr_vals[i]
            vwap_v = vwap_vals[i]
            close = closes[i]
            high  = highs[i]
            low   = lows[i]
            vol   = vols[i]
            vol_avg = vol_sma[i] or 1
            vol_exp = vol > vol_avg * 1.5

            bias_4h = bar_4h_bias[i]
            bias_1h = bar_1h_bias[i]

            bull_bias = bias_4h == "bullish" if config["require_4h_bias"] else (bias_4h == "bullish" or bias_1h == "bullish")
            bear_bias = bias_4h == "bearish" if config["require_4h_bias"] else (bias_4h == "bearish" or bias_1h == "bearish")

            # Simple structure break
            recent_highs = highs[max(0,i-10):i]
            recent_lows  = lows[max(0,i-10):i]
            bull_break = close > max(recent_highs) if recent_highs else False
            bear_break = close < min(recent_lows)  if recent_lows  else False

            bull_fvg = i >= 2 and low > highs[i-2]
            bear_fvg = i >= 2 and high < lows[i-2]

            vol_ok = vol_exp if config["require_volume"] else True
            rsi_min = config["rsi_min"]
            rsi_max = config["rsi_max"]

            bull_icc = (bull_bias and (bull_break or bull_fvg or close > vwap_v) and
                        e8 > e21 and rsi_min <= rsi_v <= rsi_max and vol_ok)
            bear_icc = (bear_bias and (bear_break or bear_fvg or close < vwap_v) and
                        e8 < e21 and (100-rsi_max) <= rsi_v <= (100-rsi_min) and vol_ok)

            if not bull_icc and not bear_icc:
                continue

            setups_found += 1
            direction = "bullish" if bull_icc else "bearish"
            min_rr = config["min_rr"]

            if direction == "bullish":
                entry  = close
                stop   = min(low, vwap_v) - atr_v * 0.5
                target = entry + (entry - stop) * min_rr
                indication = "structure_break_high" if bull_break else "displacement_up"
                correction = "fair_value_gap" if bull_fvg else "vwap"
            else:
                entry  = close
                stop   = max(high, vwap_v) + atr_v * 0.5
                target = entry - (entry - stop) * min_rr
                indication = "structure_break_low" if bear_break else "displacement_down"
                correction = "fair_value_gap" if bear_fvg else "vwap"

            risk = abs(entry - stop)
            if risk == 0:
                continue

            # Confidence score
            score = 0.5
            if bias_4h in ("bullish", "bearish"): score += 0.15
            if bias_1h in ("bullish", "bearish"): score += 0.10
            if bull_break or bear_break: score += 0.10
            if bull_fvg or bear_fvg: score += 0.08
            if vol_exp: score += 0.07
            score = min(score, 1.0)

            # Simulate outcome
            exit_price, exit_reason, mae, mfe = None, "time_exit", 0.0, 0.0
            for j in range(i+1, min(i+51, len(bars))):
                fb = bars[j]
                if direction == "bullish":
                    mae = max(mae, entry - fb["low"])
                    mfe = max(mfe, fb["high"] - entry)
                    if fb["low"] <= stop:
                        exit_price, exit_reason = stop, "stop_hit"
                        break
                    if fb["high"] >= target:
                        exit_price, exit_reason = target, "target_hit"
                        break
                else:
                    mae = max(mae, fb["high"] - entry)
                    mfe = max(mfe, entry - fb["low"])
                    if fb["high"] >= stop:
                        exit_price, exit_reason = stop, "stop_hit"
                        break
                    if fb["low"] <= target:
                        exit_price, exit_reason = target, "target_hit"
                        break

            if exit_price is None:
                exit_price = bars[min(i+50, len(bars)-1)]["close"]

            pnl_pts = (exit_price - entry) if direction == "bullish" else (entry - exit_price)
            pnl_r   = pnl_pts / risk

            trade = BacktestTrade(
                entry_time=str(b["time"]),
                exit_time=str(bars[min(i+50, len(bars)-1)]["time"]),
                symbol=symbol, direction=direction,
                entry_price=entry, stop_price=stop, target_price=target,
                exit_price=exit_price, exit_reason=exit_reason,
                pnl_r=pnl_r, mae=mae, mfe=mfe,
                confidence_score=score,
                indication_type=indication, correction_zone=correction,
                hour_of_day=hour_et, session=sess,
                htf_bias_4h=bias_4h, htf_bias_1h=bias_1h,
            )
            trades.append(trade)
            in_trade = True

        print(f"Found {setups_found} setups, {len(trades)} trades")
        return self._results(trades, symbol, days, setups_found, config)

    def _results(self, trades, symbol, days, setups_found, config):
        if not trades:
            return {"error": "No trades found", "setups_found": setups_found, "config": config}

        winners = [t for t in trades if t.pnl_r and t.pnl_r > 0]
        losers  = [t for t in trades if t.pnl_r and t.pnl_r <= 0]
        total   = len(trades)
        win_rate = len(winners) / total
        avg_w   = sum(t.pnl_r for t in winners) / len(winners) if winners else 0
        avg_l   = sum(t.pnl_r for t in losers)  / len(losers)  if losers  else 0
        expect  = win_rate * avg_w + (1 - win_rate) * avg_l
        gross_w = sum(t.pnl_r for t in winners) if winners else 0
        gross_l = abs(sum(t.pnl_r for t in losers)) if losers else 1
        pf      = gross_w / gross_l if gross_l > 0 else 0
        total_r = sum(t.pnl_r for t in trades if t.pnl_r)

        # Max drawdown
        eq, peak, dd = 0, 0, 0
        for t in trades:
            eq += t.pnl_r or 0
            peak = max(peak, eq)
            dd = max(dd, peak - eq)

        # Max consec losses
        max_cl = cl = 0
        for t in trades:
            if t.pnl_r and t.pnl_r <= 0:
                cl += 1; max_cl = max(max_cl, cl)
            else:
                cl = 0

        # By hour
        by_hour = {}
        for t in trades:
            h = t.hour_of_day
            if h not in by_hour:
                by_hour[h] = {"trades": 0, "wins": 0, "total_r": 0.0}
            by_hour[h]["trades"] += 1
            if t.pnl_r and t.pnl_r > 0:
                by_hour[h]["wins"] += 1
            by_hour[h]["total_r"] += t.pnl_r or 0

        best_hours = sorted(
            [(h, v) for h, v in by_hour.items() if v["trades"] >= 3],
            key=lambda x: x[1]["wins"]/x[1]["trades"], reverse=True
        )[:3]

        worst_hours = sorted(
            [(h, v) for h, v in by_hour.items() if v["trades"] >= 3],
            key=lambda x: x[1]["wins"]/x[1]["trades"]
        )[:3]

        # By indication
        by_ind = {}
        for t in trades:
            ind = t.indication_type
            if ind not in by_ind:
                by_ind[ind] = {"trades": 0, "wins": 0}
            by_ind[ind]["trades"] += 1
            if t.pnl_r and t.pnl_r > 0:
                by_ind[ind]["wins"] += 1

        return {
            "symbol": symbol,
            "period_days": days,
            "total_setups_detected": setups_found,
            "total_trades": total,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": f"{win_rate*100:.1f}%",
            "avg_winner_r": f"+{avg_w:.2f}R",
            "avg_loser_r": f"{avg_l:.2f}R",
            "expectancy_per_trade": f"{expect:.3f}R",
            "profit_factor": round(pf, 2),
            "total_pnl_r": f"{total_r:.1f}R",
            "max_drawdown_r": f"{dd:.1f}R",
            "max_consecutive_losses": max_cl,
            "avg_mae": round(sum(t.mae or 0 for t in trades)/total, 2),
            "avg_mfe": round(sum(t.mfe or 0 for t in trades)/total, 2),
            "best_hours_ET": [
                {"hour": f"{h}:00", "win_rate": f"{v['wins']/v['trades']*100:.0f}%", "trades": v["trades"]}
                for h, v in best_hours
            ],
            "worst_hours_ET": [
                {"hour": f"{h}:00", "win_rate": f"{v['wins']/v['trades']*100:.0f}%", "trades": v["trades"]}
                for h, v in worst_hours
            ],
            "by_indication_type": {
                k: {"trades": v["trades"], "win_rate": f"{v['wins']/v['trades']*100:.0f}%"}
                for k, v in by_ind.items()
            },
            "parameters_used": config,
            "recommendation": self._recommend(win_rate, pf, max_cl, best_hours, expect),
        }

    def _recommend(self, wr, pf, max_cl, best_hours, expect):
        recs = []
        if wr >= 0.55 and pf >= 1.5:
            recs.append("Strategy is profitable with current parameters.")
        elif wr < 0.45:
            recs.append("Win rate below 45% — tighten entry criteria.")
        if max_cl >= 6:
            recs.append("Add daily loss limit — max 3 losses per day.")
        if best_hours:
            h, v = best_hours[0]
            recs.append(f"Best hour: {h}:00 ET ({v['wins']/v['trades']*100:.0f}% win rate).")
        if expect > 0:
            recs.append(f"Positive expectancy of {expect:.2f}R per trade — keep trading.")
        else:
            recs.append("Negative expectancy — do not trade live until improved.")
        return " ".join(recs)
