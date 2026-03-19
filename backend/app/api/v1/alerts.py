"""
api/v1/alerts.py — TradingView webhook intake with Claude AI analysis

Flow:
1. Receive webhook from TradingView Pine Script
2. Store raw alert
3. Run rule-based ICC engine (fast, always runs)
4. Run Claude AI analysis (deeper, uses all indicator data)
5. Store combined result
6. Return plain-English trade decision
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from typing import Optional, List
from datetime import datetime
import json

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


@router.post("/webhook", response_model=AlertResponse)
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_token: Optional[str] = Header(None),
):
    token_valid = (x_webhook_token == settings.WEBHOOK_SECRET)

    raw_body = await request.body()
    client_ip = request.client.host if request.client else "unknown"

    try:
        payload_dict = json.loads(raw_body)
    except json.JSONDecodeError:
        raw_alert = RawAlert(
            payload={"raw": raw_body.decode("utf-8", errors="replace")},
            source_ip=client_ip,
            webhook_token_valid=token_valid,
            processed=False,
            processing_error="Invalid JSON payload",
        )
        db.add(raw_alert)
        db.flush()
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    raw_alert = RawAlert(
        payload=payload_dict,
        symbol=payload_dict.get("symbol"),
        timeframe=payload_dict.get("timeframe"),
        direction=payload_dict.get("direction"),
        signal_type=payload_dict.get("signal_type"),
        price=payload_dict.get("price"),
        source_ip=client_ip,
        webhook_token_valid=token_valid,
    )
    db.add(raw_alert)
    db.flush()

    if not token_valid:
        raw_alert.processing_error = "Invalid webhook token"
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    try:
        alert_data = WebhookAlertPayload(**payload_dict)
    except Exception as e:
        raw_alert.processing_error = str(e)
        db.commit()
        raise HTTPException(status_code=422, detail=f"Payload validation failed: {str(e)}")

    signal_ts = datetime.utcnow()
    if alert_data.timestamp:
        try:
            signal_ts = datetime.fromisoformat(str(alert_data.timestamp).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    signal = Signal(
        raw_alert_id=raw_alert.id,
        symbol=alert_data.symbol,
        timeframe=alert_data.timeframe,
        direction=alert_data.direction,
        signal_type=alert_data.signal_type,
        indication_type=alert_data.indication_type,
        price=alert_data.price,
        high=alert_data.high,
        low=alert_data.low,
        volume=alert_data.volume,
        htf_bias=alert_data.htf_bias,
        session=alert_data.session,
        notes=alert_data.notes,
        signal_timestamp=signal_ts,
    )
    db.add(signal)
    db.flush()

    # ── Load active ICC config ────────────────────────────────────────────
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

    # ── Build full signal dict with all indicator data ────────────────────
    signal_dict = {
        "symbol": alert_data.symbol,
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
        "htf_bias_1h": payload_dict.get("htf_bias_1h"),
        "session": alert_data.session,
        "retracement_pct": alert_data.retracement_pct,
        "entry_price": alert_data.entry_price,
        "stop_price": alert_data.stop_price,
        "target_price": alert_data.target_price,
        "signal_timestamp": signal_ts.isoformat(),
        # Indicator data from Pine Script
        "ema8": payload_dict.get("ema8"),
        "ema21": payload_dict.get("ema21"),
        "ema50": payload_dict.get("ema50"),
        "ema21_1h": payload_dict.get("ema21_1h"),
        "ema50_1h": payload_dict.get("ema50_1h"),
        "ema21_4h": payload_dict.get("ema21_4h"),
        "ema50_4h": payload_dict.get("ema50_4h"),
        "rsi": payload_dict.get("rsi"),
        "rsi_1h": payload_dict.get("rsi_1h"),
        "rsi_4h": payload_dict.get("rsi_4h"),
        "vwap": payload_dict.get("vwap"),
        "atr": payload_dict.get("atr"),
        "vol_expanding": payload_dict.get("vol_expanding"),
    }

    # ── Run rule-based ICC engine ─────────────────────────────────────────
    icc_result = evaluator.evaluate(signal_dict, config_dict)

    # ── Run Claude AI analysis ────────────────────────────────────────────
    ai_analysis = None
    if settings.ANTHROPIC_API_KEY:
        try:
            ai_analysis = await analyze_with_claude(signal_dict, settings.ANTHROPIC_API_KEY)
        except Exception as e:
            print(f"AI analysis skipped: {e}")

    # ── Merge results — AI wins if available ─────────────────────────────
    final_verdict = icc_result.verdict
    final_confidence = icc_result.confidence_score
    final_entry = alert_data.entry_price
    final_stop = alert_data.stop_price
    final_target = alert_data.target_price
    final_rr = icc_result.risk_reward
    explanation = icc_result.explanation

    if ai_analysis:
        final_verdict = ai_analysis.get("verdict", final_verdict)
        final_confidence = ai_analysis.get("confidence", final_confidence)
        final_entry = ai_analysis.get("entry_price", final_entry)
        final_stop = ai_analysis.get("stop_price", final_stop)
        final_target = ai_analysis.get("target_price", final_target)
        final_rr = ai_analysis.get("risk_reward", final_rr)

        # Build rich explanation from AI
        explanation = {
            "summary": ai_analysis.get("plain_english_summary", ""),
            "execution": ai_analysis.get("execution_instruction", ""),
            "verdict": final_verdict,
            "confidence": final_confidence,
            "key_reasons": ai_analysis.get("key_reasons_to_take", []),
            "key_risks": ai_analysis.get("key_risks", []),
            "phase_analysis": ai_analysis.get("phase_analysis", {}),
            "invalidation_level": ai_analysis.get("invalidation_level"),
            "suggested_contracts": ai_analysis.get("suggested_contracts", 1),
            "dollar_risk_1_mes": ai_analysis.get("dollar_risk_1_mes"),
            "ai_powered": True,
            "passed_rules": icc_result.explanation.get("passed_rules", []),
            "failed_rules": icc_result.explanation.get("failed_rules", []),
            "suggested_review_note": icc_result.explanation.get("suggested_review_note", ""),
        }

    # ── Store SetupEvaluation ─────────────────────────────────────────────
    setup_eval = SetupEvaluation(
        signal_id=signal.id,
        symbol=alert_data.symbol,
        timeframe=alert_data.timeframe,
        direction=alert_data.direction,
        session=alert_data.session,
        htf_bias=alert_data.htf_bias,
        verdict=final_verdict,
        environment_score=icc_result.environment.score if icc_result.environment else 0,
        indication_score=icc_result.indication.score if icc_result.indication else 0,
        correction_score=icc_result.correction.score if icc_result.correction else 0,
        continuation_score=icc_result.continuation.score if icc_result.continuation else 0,
        risk_score=icc_result.risk.score if icc_result.risk else 0,
        confidence_score=final_confidence,
        indication_type=icc_result.indication_type,
        correction_zone_type=icc_result.correction_zone_type,
        continuation_trigger_type=icc_result.continuation_trigger_type,
        entry_price=final_entry if final_verdict == "valid_trade" else None,
        stop_price=final_stop if final_verdict == "valid_trade" else None,
        target_price=final_target if final_verdict == "valid_trade" else None,
        risk_reward=final_rr,
        explanation=explanation,
        score_breakdown=icc_result.score_breakdown,
        is_countertrend=icc_result.is_countertrend,
        has_htf_alignment=icc_result.has_htf_alignment,
        signal_timestamp=signal_ts,
    )
    db.add(setup_eval)

    signal.evaluated = True
    raw_alert.processed = True
    raw_alert.processed_at = datetime.utcnow()
    db.commit()

    summary = explanation.get("summary") or explanation.get("summary", "Evaluation complete.")

    return AlertResponse(
        received=True,
        alert_id=str(raw_alert.id),
        symbol=alert_data.symbol,
        verdict=final_verdict,
        confidence_score=final_confidence,
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
