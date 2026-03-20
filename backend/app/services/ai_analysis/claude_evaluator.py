"""
services/ai_analysis/claude_evaluator.py

Claude AI analysis engine — upgraded to handle all ICC Elite Engine v1.0 data.
"""

import httpx
import json
from typing import Dict, Any, Optional


CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL   = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are an elite futures day trader specializing in the ICC framework with Smart Money Concepts.

ICC Framework:
- INDICATION: BOS, CHoCH, liquidity sweep, displacement
- CORRECTION: FVG, Order Block, VWAP, EMA confluence  
- CONTINUATION: volume delta, RSI divergence, MACD cross

Signal Tiers:
- S-Tier (80-100): All aligned. TAKE IT full size.
- A-Tier (65-79): Most aligned. TAKE IT standard size.
- B-Tier (50-64): Valid but incomplete. REDUCE size or skip.
- Below 50: Do not trade.

Respond with valid JSON only. No markdown."""


def build_prompt(signal: Dict[str, Any]) -> str:
    score = signal.get('composite_score', signal.get('confidence_score', 0))
    if isinstance(score, float) and score <= 1:
        score = int(score * 100)

    return f"""Analyze this ICC Elite Engine signal.

SIGNAL: {signal.get('symbol')} {signal.get('direction')} {signal.get('timeframe')}min | Score: {score}/100 | Tier: {signal.get('signal_tier','?')} | Session: {signal.get('session')}

TIMEFRAMES: 4H={signal.get('htf_bias')} 1H={signal.get('htf_bias_1h')} | RSI 4H={signal.get('rsi_4h')} 1H={signal.get('rsi_1h')} 5M={signal.get('rsi')}
EMAs 5M: 8={signal.get('ema8')} 21={signal.get('ema21')} 50={signal.get('ema50')} 200={signal.get('ema200')}
EMAs 1H: 21={signal.get('ema21_1h')} 50={signal.get('ema50_1h')} | EMAs 4H: 21={signal.get('ema21_4h')} 50={signal.get('ema50_4h')}

SMC: BOS={signal.get('bos',False)} CHoCH={signal.get('choch',False)} LiqSweep={signal.get('liq_sweep',False)} FVG={signal.get('in_fvg',False)} OB={signal.get('in_ob',False)}
MOMENTUM: BullDiv={signal.get('bull_div',False)} HiddenDiv={signal.get('hidden_div',False)} VolSpike={signal.get('vol_spike',False)} PosDelta={signal.get('pos_delta',False)}
MACD={signal.get('macd')} | VWAP={signal.get('vwap')} DevPct={signal.get('vwap_dev_pct')}% AboveVWAP={signal.get('above_vwap',False)}
ATR={signal.get('atr')} Ratio={signal.get('atr_ratio')} | PDH={signal.get('pdh')} PDL={signal.get('pdl')} AbovePDH={signal.get('above_pdh',False)}

INDICATION: {signal.get('indication_type')} | CORRECTION: {signal.get('correction_zone_type')} | CONTINUATION: {signal.get('continuation_trigger_type')}
LEVELS: Entry={signal.get('entry_price')} Stop={signal.get('stop_price')} T1={signal.get('target_price')} T2={signal.get('target2_price')} T3={signal.get('target3_price')}

Return this JSON:
{{
  "verdict": "valid_trade|watch_only|invalid_setup",
  "confidence": 0.0-1.0,
  "tier": "S|A|B|X",
  "plain_english_summary": "One sentence: what is happening and what to do",
  "execution_instruction": "Exact step: price, size, platform",
  "entry_price": number,
  "stop_price": number,
  "target_price": number,
  "risk_reward": number,
  "htf_alignment": true/false,
  "is_countertrend": true/false,
  "smc_quality": "high|medium|low",
  "strongest_factor": "single best reason to take this",
  "biggest_risk": "single biggest reason it could fail",
  "phase_scores": {{
    "environment":  {{"score": 0-100, "note": "brief"}},
    "indication":   {{"score": 0-100, "note": "brief"}},
    "correction":   {{"score": 0-100, "note": "brief"}},
    "continuation": {{"score": 0-100, "note": "brief"}},
    "risk":         {{"score": 0-100, "note": "brief"}}
  }},
  "key_confirmations": ["c1", "c2", "c3"],
  "key_risks": ["r1", "r2"],
  "invalidation_level": number,
  "position_size_recommendation": "full|half|quarter|skip",
  "dollar_risk_1_mnq": number,
  "dollar_risk_1_mes": number
}}"""


async def analyze_with_claude(signal: Dict[str, Any], api_key: str) -> Optional[Dict[str, Any]]:
    if not api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                CLAUDE_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 1500,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": build_prompt(signal)}],
                },
            )

            if response.status_code != 200:
                print(f"Claude API error: {response.status_code}")
                return None

            text = data["content"][0]["text"].strip() if (data := response.json()) else ""
            if "```" in text:
                for part in text.split("```"):
                    part = part.strip().lstrip("json").strip()
                    if part.startswith("{"):
                        text = part
                        break

            return json.loads(text)

    except Exception as e:
        print(f"Claude analysis failed: {e}")
        return None
