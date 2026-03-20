"""
ICC Backtesting Engine — pure Python, no pandas/numpy
"""
import httpx
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
                    raise Exception(f"Polygon error: {resp.status_code} {resp.text[:200]}")
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
                "open": float(b["o"]), "high": float(b["h"]),
                "low": float(b["l"]), "close": float(b["c"]),
                "volume": float(b["v"])
            })
        return bars


def calc_ema(values: List[float], period: int) -> List[Optional[float]]:
    result = [None] * len(values)
    k = 2.0 / (period + 1)
    seed_start = period - 1
    if seed_start >= len(values):
        return result
    result[seed_start] = sum(values[:period]) / period
    for i in range(seed_start + 1, len(values)):
        result[i] = values[i] * k + result[i-1] * (1 - k)
    return result


def calc_rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    result = [None] * len(closes)
    for i in range(period, len(closes)):
        gains, losses = 0.0, 0.0
        for j in range(i - period + 1, i + 1):
            d = closes[j] - closes[j-1]
            if d > 0:
                gains += d
            else:
                losses += abs(d)
        ag = gains / period
        al = losses / period
        result[i] = 100 - (100 / (1 + ag / al)) if al > 0 else 100.0
    return result


def calc_atr(bars: List[Dict], period: int = 14) -> List[Optional[float]]:
    result = [None] * len(bars)
    for i in range(1, len(bars)):
        tr = max(
            bars[i]["high"] - bars[i]["low"],
            abs(bars[i]["high"] - bars[i-1]["close"]),
            abs(bars[i]["low"] - bars[i-1]["close"])
        )
        if i >= period:
            window = []
            for k in range(i - period + 1, i + 1):
                window.append(max(
                    bars[k]["high"] - bars[k]["low"],
                    abs(bars[k]["high"] - bars[k-1]["close"]),
                    abs(bars[k]["low"] - bars[k-1]["close"])
                ))
            result[i] = sum(window) / period
    return result


def calc_vwap(bars: List[Dict]) -> List[float]:
    result = []
    cum_pv = cum_vol = 0.0
    current_date = None
    for b in bars:
        d = b["time"].date()
        if d != current_date:
            cum_pv = cum_vol = 0.0
            current_date = d
        hlc3 = (b["high"] + b["low"] + b["close"]) / 3.0
        cum_pv += hlc3 * b["volume"]
        cum_vol += b["volume"]
        result.append(cum_pv / cum_vol if cum_vol > 0 else b["close"])
    return result


def get_session(hour: int) -> str:
    if 4 <= hour < 9: return "us_premarket"
    if 9 <= hour < 16: return "us_regular"
    if 16 <= hour < 20: return "us_afterhours"
    return "globex"


def calc_htf_bias(bars: List[Dict], closes: List[float]):
    hourly_close = {}
    four_h_close = {}
    for i, b in enumerate(bars):
        hk = b["time"].replace(minute=0, second=0, microsecond=0)
        fhk = b["time"].replace(hour=(b["time"].hour // 4) * 4, minute=0, second=0, microsecond=0)
        hourly_close[hk] = closes[i]
        four_h_close[fhk] = closes[i]

    h_times = sorted(hourly_close.keys())
    h_closes = [hourly_close[t] for t in h_times]
    fh_times = sorted(four_h_close.keys())
    fh_closes = [four_h_close[t] for t in fh_times]

    h_e21 = calc_ema(h_closes, 21)
    h_e50 = calc_ema(h_closes, 50)
    fh_e21 = calc_ema(fh_closes, 21)
    fh_e50 = calc_ema(fh_closes, 50)

    h_bias = {}
    for i, t in enumerate(h_times):
        if h_e21[i] and h_e50[i]:
            if h_closes[i] > h_e21[i] and h_closes[i] > h_e50[i]:
                h_bias[t] = "bullish"
            elif h_closes[i] < h_e21[i] and h_closes[i] < h_e50[i]:
                h_bias[t] = "bearish"
            else:
                h_bias[t] = "neutral"

    fh_bias = {}
    for i, t in enumerate(fh_times):
        if fh_e21[i] and fh_e50[i]:
            if fh_closes[i] > fh_e21[i] and fh_e21[i] > fh_e50[i]:
                fh_bias[t] = "bullish"
            elif fh_closes[i] < fh_e21[i] and fh_e21[i] < fh_e50[i]:
                fh_bias[t] = "bearish"
            else:
                fh_bias[t] = "neutral"

    bar_1h = []
    bar_4h = []
    last_1h = "neutral"
    last_4h = "neutral"
    for b in bars:
        hk = b["time"].replace(minute=0, second=0, microsecond=0)
        fhk = b["time"].replace(hour=(b["time"].hour // 4) * 4, minute=0, second=0, microsecond=0)
        if hk in h_bias: last_1h = h_bias[hk]
        if fhk in fh_bias: last_4h = fh_bias[fhk]
        bar_1h.append(last_1h)
        bar_4h.append(last_4h)
    return bar_1h, bar_4h


class ICCBacktester:
    def __init__(self, polygon_api_key: str, anthropic_api_key: str = ""):
        self.fetcher = PolygonFetcher(polygon_api_key)
        self.anthropic_key = anthropic_api_key

    async def run(self, symbol: str = "NQ", days: int = 365, config: Optional[Dict] = None) -> Dict:
        if config is None:
            config = {
                "min_rr": 2.0, "require_4h_bias": False, "require_volume": False,
                "allowed_sessions": ["us_regular"], "rsi_min": 45, "rsi_max": 78,
                "ai_confidence_threshold": 0.65,
            }

        print(f"Fetching {symbol} data for {days} days...")
        bars = await self.fetcher.fetch_bars(symbol, days)
        if not bars:
            return {"error": f"No data returned for {symbol}", "setups_found": 0, "config": config}
        print(f"Fetched {len(bars)} bars")

        closes = [b["close"] for b in bars]
        highs  = [b["high"]  for b in bars]
        lows   = [b["low"]   for b in bars]
        vols   = [b["volume"] for b in bars]

        print("Computing indicators...")
        e8  = calc_ema(closes, 8)
        e21 = calc_ema(closes, 21)
        e50 = calc_ema(closes, 50)
        rsi_v = calc_rsi(closes, 14)
        atr_v = calc_atr(bars, 14)
        vwap_v = calc_vwap(bars)
        vol_sma = [None]*20 + [sum(vols[i-20:i])/20 for i in range(20, len(vols))]
        bar_1h, bar_4h = calc_htf_bias(bars, closes)

        print("Running ICC signal detection...")
        trades = []
        setups_found = 0
        skip_until = 0

        for i in range(55, len(bars) - 55):
            if i < skip_until:
                continue
            if not all([e8[i], e21[i], rsi_v[i], atr_v[i]]):
                continue

            b = bars[i]
            hour = b["time"].hour
            sess = get_session(hour)
            if sess not in config["allowed_sessions"]:
                continue

            ev8  = e8[i]
            ev21 = e21[i]
            rv   = rsi_v[i]
            av   = atr_v[i]
            vv   = vwap_v[i]
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

            rh = max(highs[max(0, i-10):i]) if i > 10 else h
            rl = min(lows[max(0, i-10):i])  if i > 10 else lo
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
                target = entry - (entry - stop) * min_rr
                indication = "structure_break_low" if bear_break else "displacement_down"
                correction = "fair_value_gap" if bear_fvg else "vwap"

            risk = abs(entry - stop)
            if risk < 0.01:
                continue

            # Score
            score = 0.5
            if b4h in ("bullish", "bearish"): score += 0.15
            if b1h in ("bullish", "bearish"): score += 0.10
            if bull_break or bear_break: score += 0.10
            if bull_fvg or bear_fvg: score += 0.08
            if vol_exp: score += 0.07
            score = min(score, 1.0)

            # Simulate outcome on next 50 bars
            exit_price = None
            exit_reason = "time_exit"
            mae = 0.0
            mfe = 0.0

            for j in range(i+1, min(i+51, len(bars))):
                fb = bars[j]
                fh = fb["high"]
                fl = fb["low"]
                fc = fb["close"]

                if direction == "bullish":
                    # Update MAE/MFE
                    adverse = entry - fl
                    favorable = fh - entry
                    if adverse > 0: mae = max(mae, adverse)
                    if favorable > 0: mfe = max(mfe, favorable)
                    # Check stop first (worst case)
                    if fl <= stop:
                        exit_price = stop
                        exit_reason = "stop_hit"
                        break
                    # Check target
                    if fh >= target:
                        exit_price = target
                        exit_reason = "target_hit"
                        break
                else:
                    # Bear trade
                    adverse = fh - entry
                    favorable = entry - fl
                    if adverse > 0: mae = max(mae, adverse)
                    if favorable > 0: mfe = max(mfe, favorable)
                    # Check stop first
                    if fh >= stop:
                        exit_price = stop
                        exit_reason = "stop_hit"
                        break
                    # Check target
                    if fl <= target:
                        exit_price = target
                        exit_reason = "target_hit"
                        break

            if exit_price is None:
                exit_price = bars[min(i+50, len(bars)-1)]["close"]
                exit_reason = "time_exit"

            pnl_pts = (exit_price - entry) if direction == "bullish" else (entry - exit_price)
            pnl_r = pnl_pts / risk

            trade = BacktestTrade(
                entry_time=str(b["time"]),
                exit_time=str(bars[min(i+50, len(bars)-1)]["time"]),
                symbol=symbol, direction=direction,
                entry_price=round(entry, 4), stop_price=round(stop, 4),
                target_price=round(target, 4), exit_price=round(exit_price, 4),
                exit_reason=exit_reason, pnl_r=round(pnl_r, 3),
                mae=round(mae, 4), mfe=round(mfe, 4),
                confidence_score=round(score, 2),
                indication_type=indication, correction_zone=correction,
                hour_of_day=hour, session=sess,
                htf_bias_4h=b4h, htf_bias_1h=b1h,
            )
            trades.append(trade)
            skip_until = i + 10  # Avoid overlapping trades

        print(f"Found {setups_found} setups, {len(trades)} trades")
        return self._results(trades, symbol, days, setups_found, config)

    def _results(self, trades, symbol, days, setups_found, config):
        if not trades:
            return {"error": "No trades found", "setups_found": setups_found, "config": config}

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

        eq = peak = dd = 0.0
        for t in trades:
            eq += t.pnl_r or 0
            peak = max(peak, eq)
            dd = max(dd, peak - eq)

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
            key=lambda x: x[1]["wins"] / x[1]["trades"] if x[1]["trades"] > 0 else 0,
            reverse=True
        )[:3]

        worst_hours = sorted(
            [(h, v) for h, v in by_hour.items() if v["trades"] >= 3],
            key=lambda x: x[1]["wins"] / x[1]["trades"] if x[1]["trades"] > 0 else 0
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
            bwr = v["wins"] / v["trades"] * 100 if v["trades"] > 0 else 0
            recs.append(f"Best hour: {h}:00 ET ({bwr:.0f}% win rate, {v['trades']} trades).")
        if expect > 0:
            recs.append(f"Positive expectancy {expect:.2f}R — strategy has edge.")
        else:
            recs.append("Negative expectancy — refine parameters before trading live.")

        return {
            "symbol": symbol,
            "period_days": days,
            "total_bars": len(trades) * 10,
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
            "avg_mae": round(sum(t.mae for t in trades)/total, 4),
            "avg_mfe": round(sum(t.mfe for t in trades)/total, 4),
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
                k: {"trades": v["trades"],
                    "win_rate": f"{v['wins']/v['trades']*100:.0f}%",
                    "total_r": round(v["total_r"], 2)}
                for k, v in by_ind.items()
            },
            "parameters_used": config,
            "recommendation": " ".join(recs),
        }
