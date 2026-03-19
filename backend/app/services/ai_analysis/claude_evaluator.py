"""
services/ai_analysis/claude_evaluator.py

Claude AI reads multi-timeframe indicator data and delivers
a complete ICC trade evaluation in plain English.
"""

import httpx
import json
from typing import Dict, Any, Optional


CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL   = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are an expert futures day trader specializing in the ICC (Indication, Correction, Continuation) trading framework. 

You analyze multi-timeframe market data and make precise, objective trade decisions.

ICC Framework:
- INDICATION: Initial directional move — structure break, displacement candle, liquidity sweep
- CORRECTION: Orderly pullback into a zone — FVG, order block, VWAP, EMA confluence  
- CONTINUATION: Trigger confirming trend resumption — rejection candle, volume expansion, momentum shift

Your job:
1. Analyze the 4H and 1H trend (HTF bias)
2. Confirm the 5M/15M entry setup matches the ICC pattern
3. Validate the indicators support the trade
4. Give a clear verdict with exact levels

Always respond with valid JSON only. No markdown, no explanation outside the JSON."""

def build_analysis_prompt(signal: Dict[str, Any]) -> str:
    return f"""Analyze this real-time market data and evaluate the ICC trade setup.

MARKET DATA:
Symbol: {signal.get('symbol')} | Timeframe: {signal.get('timeframe')}min | Direction: {signal.get('direction')}
Current Price: {signal.get('price')} | High: {signal.get('high')} | Low: {signal.get('low')}

MULTI-TIMEFRAME BIAS:
4H Bias: {signal.get('htf_bias')} (EMA21: {signal.get('ema21_4h')}, EMA50: {signal.get('ema50_4h')})
1H Bias: {signal.get('htf_bias_1h')} (EMA21: {signal.get('ema21_1h')}, EMA50: {signal.get('ema50_1h')})
4H RSI: {signal.get('rsi_4h')} | 1H RSI: {signal.get('rsi_1h')}

ENTRY TIMEFRAME INDICATORS:
EMA8: {signal.get('ema8')} | EMA21: {signal.get('ema21')} | EMA50: {signal.get('ema50')}
RSI(14): {signal.get('rsi')} | VWAP: {signal.get('vwap')}
ATR(14): {signal.get('atr')} | Volume Expanding: {signal.get('vol_expanding')}
Session: {signal.get('session')}

ICC PATTERN DETECTED:
Signal Type: {signal.get('signal_type')}
Indication: {signal.get('indication_type')}
Correction Zone: {signal.get('correction_zone_type')}
Continuation Trigger: {signal.get('continuation_trigger_type')}
Retracement: {signal.get('retracement_pct', 0)*100:.1f}%

PROPOSED LEVELS:
Entry: {signal.get('entry_price')} | Stop: {signal.get('stop_price')} | Target: {signal.get('target_price')}

Evaluate this setup against the ICC framework and respond with this exact JSON:

{{
  "verdict": "valid_trade" | "watch_only" | "invalid_setup",
  "confidence": 0.0-1.0,
  "plain_english_summary": "One clear sentence: what is happening and what to do",
  "execution_instruction": "Exact step-by-step: what to click, what price, what size",
  "entry_price": number,
  "stop_price": number,
  "target_price": number,
  "risk_reward": number,
  "htf_alignment": true/false,
  "is_countertrend": true/false,
  "phase_analysis": {{
    "environment": {{"passed": bool, "score": 0-100, "note": "brief reason"}},
    "indication": {{"passed": bool, "score": 0-100, "note": "brief reason"}},
    "correction": {{"passed": bool, "score": 0-100, "note": "brief reason"}},
    "continuation": {{"passed": bool, "score": 0-100, "note": "brief reason"}},
    "risk": {{"passed": bool, "score": 0-100, "note": "brief reason"}}
  }},
  "key_reasons_to_take": ["reason1", "reason2", "reason3"],
  "key_risks": ["risk1", "risk2"],
  "invalidation_level": number,
  "suggested_contracts": 1,
  "dollar_risk_1_mes": number
}}"""


async def analyze_with_claude(signal: Dict[str, Any], api_key: str) -> Optional[Dict[str, Any]]:
    """
    Send market data to Claude for ICC analysis.
    Returns structured trade decision or None if API call fails.
    """
    if not api_key:
        return None

    prompt = build_analysis_prompt(signal)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                CLAUDE_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 1000,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

            if response.status_code != 200:
                print(f"Claude API error: {response.status_code} {response.text}")
                return None

            data = response.json()
            text = data["content"][0]["text"].strip()

            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            result = json.loads(text)
            return result

    except Exception as e:
        print(f"Claude analysis failed: {e}")
        return None
