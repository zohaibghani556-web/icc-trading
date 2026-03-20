"""
api/v1/alerts.py — ICC Elite Engine v1.0

FIXES APPLIED:
  1. Claude AI moved to true background task — responds to TradingView in <200ms
  2. Symbol prefix stripping (handles CME_MINI:NQ1! → NQ1!)
  3. Session name mapping (Pine sends 'ny_open' → maps to 'us_regular')
  4. Full Elite Engine field passthrough
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from typing import Optional, List
from datetime import datetime
import json
import asyncio

from app.db.database import get_db
from app.core.config import settings
from app.models.alert import RawAlert
from app.models.signal import Signal
from app.models.setup import SetupEvaluation
from app.models.icc_config import ICCConfiguration
from app.schemas.alert import WebhookAlertPayload, AlertResponse, SetupEvaluationOut
from app.services.icc_engine import ICCEvaluator
from app.services.ai_analysis.claude_evaluator import analyze_with_claude

router = APIRouter()
evaluator = ICCEvaluator()

# ── Session name map: Pine Script names → backend allowed_sessions names ──
# Pine sends: london, ny_open, ny_mid, ny_power, premarket, asia, globex
# Backend config uses: us_regular, us_premarket, globex, london, asia
PINE_SESSION_MAP = {
    "ny_open":   "us_regular",
    "ny_mid":    "us_regular",
    "ny_power":  "us_regular",
    "premarket": "us_premarket",
    "london":    "london",
    "asia":      "asia",
    "globex":    "globex",
    # pass-through for values already in backend format
    "us_regular":    "us_regular",
    "us_premarket":  "us_premarket",
    "us_afterhours": "us_afterhours",
}

def normalize_symbol(symbol: str) -> str:
    """Strip exchange prefix. 'CME_MINI:NQ1!' → 'NQ1!'"""
    if ":" in symbol:
        return symbol.split(":", 1)[1]
    return symbol

def normalize_session(session: Optional[str]) -> str:
    """Map Pine Script session names to backend session names."""
    if not session:
        return "us_regular"
    return PINE_SESSION_MAP.get(session.lower(), session)


async def _run_ai_and_update(setup_eval_id: str, signal_dict: dict, api_key: str):
    """
    Background task: runs Claude AI after the webhook has already responded.
    Updates the SetupEvaluation record in the DB when done.
    Runs completely detached from the webhook response cycle.
    """
    if not api_key:
        return
    try:
        ai_analysis = await asyncio.wait_for(
            analyze_with_claude(signal_dict, api_key),
            timeout=30.0  # generous timeout since we're in background
        )
        if not ai_analysis:
            return

        # Re-open a fresh DB session for the background update
        from app.db.database import SyncSessionLocal
        db = SyncSessionLocal()
        try:
            from uuid import UUID
            result = db.execute(
                select(SetupEvaluation).where(
                    SetupEvaluation.id == UUID(setup_eval_id)
                )
            )
            setup = result.scalar_one_or_none()
            if setup:
                # Merge AI results into existing explanation
                existing_exp = setup.explanation or {}
                existing_exp.update({
                    "ai_summary": ai_analysis.get("plain_english_summary", ""),
                    "ai_execution": ai_analysis.get("execution_instruction", ""),
                    "ai_verdict": ai_analysis.get("verdict", setup.verdict),
                    "ai_confidence": ai_analysis.get("confidence", setup.confidence_score),
                    "ai_tier": ai_analysis.get("tier", ""),
                    "strongest_factor": ai_analysis.get("strongest_factor", ""),
                    "biggest_risk": ai_analysis.get("biggest_risk", ""),
                    "key_confirmations": ai_analysis.get("key_confirmations", []),
                    "key_risks": ai_analysis.get("key_risks", []),
                    "position_size": ai_analysis.get("position_size_recommendation", ""),
                    "dollar_risk_mnq": ai_analysis.get("dollar_risk_1_mnq"),
                    "dollar_risk_mes": ai_analysis.get("dollar_risk_1_mes"),
                    "invalidation_level": ai_analysis.get("invalidation_level"),
                    "ai_powered": True,
                    "ai_phase_scores": ai_analysis.get("phase_scores", {}),
                })
                setup.explanation = existing_exp

                # Upgrade verdict if AI is more confident
                if ai_analysis.get("verdict") == "valid_trade":
                    setup.verdict = "valid_trade"
                if ai_analysis.get("confidence"):
                    setup.confidence_score = float(ai_analysis["confidence"])

                db.commit()
                print(f"[AI] Updated setup {setup_eval_id} with Claude analysis")
        except Exception as e:
            print(f"[AI] DB update failed: {e}")
            db.rollback()
        finally:
            db.close()

    except asyncio.TimeoutError:
        print(f"[AI] Claude timeout for setup {setup_eval_id}")
    except Exception as e:
        print(f"[AI] Analysis failed for setup {setup_eval_id}: {e}")


@router.post("/webhook", response_model=AlertResponse)
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_webhook_token: Optional[str] = Header(None),
):
    raw_body = await request.body()
    client_ip = request.client.host if request.client else "unknown"

    print(f"[WEBHOOK] Received from {client_ip}, size={len(raw_body)} bytes")

    # Parse JSON
    try:
        payload_dict = json.loads(raw_body)
        print(f"[WEBHOOK] Symbol={payload_dict.get('symbol')} Dir={payload_dict.get('direction')} Session={payload_dict.get('session')}")
    except json.JSONDecodeError as e:
        print(f"[WEBHOOK] JSON parse error: {e}")
        raw_alert = RawAlert(
            payload={"raw": raw_body.decode("utf-8", errors="replace")},
            source_ip=client_ip,
            webhook_token_valid=False,
            processed=False,
            processing_error=f"Invalid JSON: {e}",
        )
        db.add(raw_alert)
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # ── Normalize symbol and session BEFORE storing ──
    raw_symbol = payload_dict.get("symbol", "")
    normalized_symbol = normalize_symbol(raw_symbol)
    raw_session = payload_dict.get("session", "")
    normalized_session = normalize_session(raw_session)

    # Patch the dict so downstream code sees normalized values
    payload_dict["symbol"] = normalized_symbol
    payload_dict["session"] = normalized_session

    print(f"[WEBHOOK] Normalized: symbol={raw_symbol}→{normalized_symbol} session={raw_session}→{normalized_session}")

    # Store raw alert
    raw_alert = RawAlert(
        payload=payload_dict,
        symbol=normalized_symbol,
        timeframe=payload_dict.get("timeframe"),
        direction=payload_dict.get("direction"),
        signal_type=payload_dict.get("signal_type"),
        price=payload_dict.get("price"),
        source_ip=client_ip,
        webhook_token_valid=True,
    )
    db.add(raw_alert)
    db.flush()

    # Validate schema
    try:
        alert_data = WebhookAlertPayload(**payload_dict)
    except Exception as e:
        print(f"[WEBHOOK] Schema validation error: {e}")
        raw_alert.processing_error = str(e)
        db.commit()
        raise HTTPException(status_code=422, detail=f"Payload validation failed: {str(e)}")

    # Parse timestamp
    signal_ts = datetime.utcnow()
    if alert_data.timestamp:
        try:
            ts = str(alert_data.timestamp)
            if ts.isdigit() and len(ts) > 10:
                signal_ts = datetime.fromtimestamp(int(ts) / 1000)
            elif ts.isdigit():
                signal_ts = datetime.fromtimestamp(int(ts))
            else:
                signal_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception as e:
            print(f"[WEBHOOK] Timestamp parse warning: {e}")

    # Store signal
    signal = Signal(
        raw_alert_id=raw_alert.id,
        symbol=normalized_symbol,
        timeframe=alert_data.timeframe,
        direction=alert_data.direction,
        signal_type=alert_data.signal_type,
        indication_type=alert_data.indication_type,
        price=alert_data.price,
        high=alert_data.high,
        low=alert_data.low,
        volume=alert_data.volume,
        htf_bias=alert_data.htf_bias,
        session=normalized_session,
        notes=alert_data.notes,
        signal_timestamp=signal_ts,
    )
    db.add(signal)
    db.flush()

    # Load ICC config
    config_result = db.execute(
        select(ICCConfiguration).where(ICCConfiguration.is_active == True).limit(1)
    )
    icc_config = config_result.scalar_one_or_none()
    config_dict = {}
    if icc_config:
        config_dict = {
            "allowed_sessions": icc_config.allowed_sessions,
            "require_htf_bias": icc_config.require_htf_bias,
            "min_structure_break_points": icc_config.min_structure_break_points,
            "min_retracement_pct": icc_config.min_retracement_pct,
            "max_retracement_pct": icc_config.max_retracement_pct,
            "require_correction_zone": icc_config.require_correction_zone,
            "allowed_correction_zones": icc_config.allowed_correction_zones,
            "min_risk_reward": icc_config.min_risk_reward,
            "max_risk_per_trade_pct": icc_config.max_risk_per_trade_pct,
            "daily_max_loss_pct": icc_config.daily_max_loss_pct,
            "max_consecutive_losses": icc_config.max_consecutive_losses,
            "max_open_positions": icc_config.max_open_positions,
            "countertrend_score_penalty": icc_config.countertrend_score_penalty,
            "min_continuation_trigger_score": icc_config.min_continuation_trigger_score,
        }
    else:
        # Fallback defaults that match Pine Script's sessions
        config_dict = {
            "allowed_sessions": ["us_regular", "us_premarket", "london", "globex", "asia"],
            "require_htf_bias": False,
            "min_retracement_pct": 0.236,
            "max_retracement_pct": 0.618,
            "require_correction_zone": False,
            "min_risk_reward": 2.0,
            "max_risk_per_trade_pct": 2.0,
            "daily_max_loss_pct": 5.0,
            "max_consecutive_losses": 5,
            "max_open_positions": 0,
            "countertrend_score_penalty": 10,
            "min_continuation_trigger_score": 40,
            "min_structure_break_points": 0.5,
        }

    # Build full signal dict with ALL Elite Engine fields
    signal_dict = {
        "symbol": normalized_symbol,
        "timeframe": alert_data.timeframe,
        "direction": alert_data.direction,
        "signal_type": alert_data.signal_type,
        "indication_type": alert_data.indication_type,
        "correction_zone_type": alert_data.correction_zone_type,
        "continuation_trigger_type": alert_data.continuation_trigger_type,
        "price": alert_data.price,
        "high": alert_data.high,
        "low": alert_data.low,
        "volume": alert_data.volume,
        "htf_bias": alert_data.htf_bias,
        "session": normalized_session,
        "retracement_pct": alert_data.retracement_pct,
        "entry_price": alert_data.entry_price,
        "stop_price": alert_data.stop_price,
        "target_price": alert_data.target_price,
        "signal_timestamp": signal_ts.isoformat(),
        # Elite Engine v1.0 fields
        "composite_score": payload_dict.get("composite_score"),
        "signal_tier": payload_dict.get("signal_tier"),
        "target2_price": payload_dict.get("target2_price"),
        "target3_price": payload_dict.get("target3_price"),
        "risk_reward": payload_dict.get("risk_reward"),
        "htf_bias_1h": payload_dict.get("htf_bias_1h"),
        "ema8": payload_dict.get("ema8"),
        "ema21": payload_dict.get("ema21"),
        "ema50": payload_dict.get("ema50"),
        "ema200": payload_dict.get("ema200"),
        "ema21_1h": payload_dict.get("ema21_1h"),
        "ema50_1h": payload_dict.get("ema50_1h"),
        "ema21_4h": payload_dict.get("ema21_4h"),
        "ema50_4h": payload_dict.get("ema50_4h"),
        "rsi": payload_dict.get("rsi"),
        "rsi_1h": payload_dict.get("rsi_1h"),
        "rsi_4h": payload_dict.get("rsi_4h"),
        "macd": payload_dict.get("macd"),
        "macd_hist": payload_dict.get("macd_hist"),
        "vwap": payload_dict.get("vwap"),
        "vwap_dev_pct": payload_dict.get("vwap_dev_pct"),
        "above_vwap": payload_dict.get("above_vwap"),
        "atr": payload_dict.get("atr"),
        "atr_ratio": payload_dict.get("atr_ratio"),
        "vol_expanding": payload_dict.get("vol_expanding"),
        "vol_spike": payload_dict.get("vol_spike"),
        "pos_delta": payload_dict.get("pos_delta"),
        "bos": payload_dict.get("bos"),
        "choch": payload_dict.get("choch"),
        "liq_sweep": payload_dict.get("liq_sweep"),
        "in_fvg": payload_dict.get("in_fvg"),
        "in_ob": payload_dict.get("in_ob"),
        "bull_div": payload_dict.get("bull_div"),
        "bear_div": payload_dict.get("bear_div"),
        "hidden_div": payload_dict.get("hidden_div"),
        "pdh": payload_dict.get("pdh"),
        "pdl": payload_dict.get("pdl"),
        "above_pdh": payload_dict.get("above_pdh"),
    }

    # ── Run rule-based ICC engine (fast, synchronous) ──
    icc_result = evaluator.evaluate(signal_dict, config_dict)
    print(f"[WEBHOOK] ICC verdict={icc_result.verdict} confidence={icc_result.confidence_score:.2f}")

    # ── Build explanation ──
    explanation = icc_result.explanation or {}
    # Enrich with Elite Engine composite score
    composite = payload_dict.get("composite_score")
    tier = payload_dict.get("signal_tier", "")
    if composite:
        explanation["composite_score"] = composite
        explanation["signal_tier"] = tier
        explanation["summary"] = (
            f"[{tier}-Tier | Score {composite}/100] {explanation.get('summary', '')}"
        ).strip()

    # ── Store SetupEvaluation ──
    setup_eval = SetupEvaluation(
        signal_id=signal.id,
        symbol=normalized_symbol,
        timeframe=alert_data.timeframe,
        direction=alert_data.direction,
        session=normalized_session,
        htf_bias=alert_data.htf_bias,
        verdict=icc_result.verdict,
        environment_score=icc_result.environment.score if icc_result.environment else 0,
        indication_score=icc_result.indication.score if icc_result.indication else 0,
        correction_score=icc_result.correction.score if icc_result.correction else 0,
        continuation_score=icc_result.continuation.score if icc_result.continuation else 0,
        risk_score=icc_result.risk.score if icc_result.risk else 0,
        confidence_score=icc_result.confidence_score,
        indication_type=icc_result.indication_type,
        correction_zone_type=icc_result.correction_zone_type,
        continuation_trigger_type=icc_result.continuation_trigger_type,
        entry_price=alert_data.entry_price if icc_result.verdict == "valid_trade" else None,
        stop_price=alert_data.stop_price if icc_result.verdict == "valid_trade" else None,
        target_price=alert_data.target_price if icc_result.verdict == "valid_trade" else None,
        risk_reward=icc_result.risk_reward,
        explanation=explanation,
        score_breakdown=icc_result.score_breakdown or {},
        is_countertrend=icc_result.is_countertrend,
        has_htf_alignment=icc_result.has_htf_alignment,
        signal_timestamp=signal_ts,
    )
    db.add(setup_eval)

    signal.evaluated = True
    raw_alert.processed = True
    raw_alert.processed_at = datetime.utcnow()
    db.commit()
    db.refresh(setup_eval)

    setup_eval_id = str(setup_eval.id)

    # ── Fire Claude AI in background — DO NOT await here ──
    if settings.ANTHROPIC_API_KEY:
        background_tasks.add_task(
            _run_ai_and_update,
            setup_eval_id,
            signal_dict,
            settings.ANTHROPIC_API_KEY,
        )
        print(f"[WEBHOOK] Claude AI queued for background processing: {setup_eval_id}")

    # ── Respond to TradingView immediately (<200ms) ──
    summary = explanation.get("summary", f"ICC {icc_result.verdict.replace('_', ' ').title()}")
    print(f"[WEBHOOK] Responding immediately. Verdict={icc_result.verdict}")

    return AlertResponse(
        received=True,
        alert_id=str(raw_alert.id),
        symbol=normalized_symbol,
        verdict=icc_result.verdict,
        confidence_score=icc_result.confidence_score,
        message=summary,
    )


@router.get("/recent", response_model=List[SetupEvaluationOut])
async def get_recent_setups(
    limit: int = 50,
    symbol: Optional[str] = None,
    verdict: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = select(SetupEvaluation).order_by(desc(SetupEvaluation.evaluated_at))
    if symbol:
        query = query.where(SetupEvaluation.symbol == symbol)
    if verdict:
        query = query.where(SetupEvaluation.verdict == verdict)
    query = query.limit(limit)
    result = db.execute(query)
    return result.scalars().all()


@router.get("/health")
async def webhook_health():
    """Quick health check — use this to verify the webhook endpoint is reachable."""
    return {
        "status": "ok",
        "webhook_url": "/api/v1/alerts/webhook",
        "method": "POST",
        "content_type": "application/json",
        "note": "No auth header required — TradingView does not support custom headers on free plans",
    }
