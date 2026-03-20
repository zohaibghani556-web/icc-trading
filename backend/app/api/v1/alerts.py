"""
api/v1/alerts.py — Upgraded for ICC Elite Engine v1.0

Handles all 40+ fields from the Pine Script including:
- composite_score, signal_tier
- bos, choch, liq_sweep, in_fvg, in_ob
- bull_div, hidden_div, bear_div
- pdh, pdl, above_pdh
- atr_ratio, vwap_dev_pct, macd_hist
- target2_price, target3_price
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
    token_valid = True  # TradingView does not support custom headers

    raw_body = await request.body()
    client_ip = request.client.host if request.client else "unknown"

    try:
        payload_dict = json.loads(raw_body)
    except json.JSONDecodeError:
        raw_alert = RawAlert(
            payload={"raw": raw_body.decode("utf-8", errors="replace")},
            source_ip=client_ip,
            webhook_token_valid=False,
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

    try:
        alert_data = WebhookAlertPayload(**payload_dict)
    except Exception as e:
        raw_alert.processing_error = str(e)
        db.commit()
        raise HTTPException(status_code=422, detail=f"Payload validation failed: {str(e)}")

    signal_ts = datetime.utcnow()
    if alert_data.timestamp:
        try:
            ts = str(alert_data.timestamp)
            if ts.isdigit():
                signal_ts = datetime.fromtimestamp(int(ts) / 1000)
            else:
                signal_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
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

    # Build full signal dict with ALL Elite Engine fields
    signal_dict = {
        # Core
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
        "session": alert_data.session,
        "retracement_pct": alert_data.retracement_pct,
        "entry_price": alert_data.entry_price,
        "stop_price": alert_data.stop_price,
        "target_price": alert_data.target_price,
        "signal_timestamp": signal_ts.isoformat(),
        # Elite Engine fields
        "composite_score": payload_dict.get("composite_score"),
        "signal_tier": payload_dict.get("signal_tier"),
        "target2_price": payload_dict.get("target2_price"),
        "target3_price": payload_dict.get("target3_price"),
        "risk_reward": payload_dict.get("risk_reward"),
        "htf_bias_1h": payload_dict.get("htf_bias_1h"),
        # EMAs
        "ema8": payload_dict.get("ema8"),
        "ema21": payload_dict.get("ema21"),
        "ema50": payload_dict.get("ema50"),
        "ema200": payload_dict.get("ema200"),
        "ema21_1h": payload_dict.get("ema21_1h"),
        "ema50_1h": payload_dict.get("ema50_1h"),
        "ema21_4h": payload_dict.get("ema21_4h"),
        "ema50_4h": payload_dict.get("ema50_4h"),
        # RSI / MACD
        "rsi": payload_dict.get("rsi"),
        "rsi_1h": payload_dict.get("rsi_1h"),
        "rsi_4h": payload_dict.get("rsi_4h"),
        "macd": payload_dict.get("macd"),
        "macd_hist": payload_dict.get("macd_hist"),
        "macd_4h": payload_dict.get("macd_4h"),
        # VWAP
        "vwap": payload_dict.get("vwap"),
        "vwap_dev_pct": payload_dict.get("vwap_dev_pct"),
        "above_vwap": payload_dict.get("above_vwap"),
        # ATR
        "atr": payload_dict.get("atr"),
        "atr_ratio": payload_dict.get("atr_ratio"),
        # Volume
        "vol_expanding": payload_dict.get("vol_expanding"),
        "vol_spike": payload_dict.get("vol_spike"),
        "pos_delta": payload_dict.get("pos_delta"),
        # SMC
        "bos": payload_dict.get("bos"),
        "choch": payload_dict.get("choch"),
        "liq_sweep": payload_dict.get("liq_sweep"),
        "in_fvg": payload_dict.get("in_fvg"),
        "in_ob": payload_dict.get("in_ob"),
        # Divergence
        "bull_div": payload_dict.get("bull_div"),
        "bear_div": payload_dict.get("bear_div"),
        "hidden_div": payload_dict.get("hidden_div"),
        # Previous day levels
        "pdh": payload_dict.get("pdh"),
        "pdl": payload_dict.get("pdl"),
        "above_pdh": payload_dict.get("above_pdh"),
    }

    # Run rule-based ICC engine
    icc_result = evaluator.evaluate(signal_dict, config_dict)

    # Run Claude AI on everything
    ai_analysis = None
    if settings.ANTHROPIC_API_KEY:
        try:
            import asyncio as _asyncio
    try:
        ai_analysis = await _asyncio.wait_for(
            analyze_with_claude(signal_dict, settings.ANTHROPIC_API_KEY),
            timeout=4.0
        )
    except _asyncio.TimeoutError:
        print("Claude timeout - using rule-based result")
        ai_analysis = None
        except Exception as e:
            print(f"AI analysis skipped: {e}")

    # Merge results — AI takes priority
    final_verdict    = icc_result.verdict
    final_confidence = icc_result.confidence_score
    final_entry      = alert_data.entry_price
    final_stop       = alert_data.stop_price
    final_target     = alert_data.target_price
    final_rr         = icc_result.risk_reward
    explanation      = icc_result.explanation

    if ai_analysis:
        final_verdict    = ai_analysis.get("verdict", final_verdict)
        final_confidence = ai_analysis.get("confidence", final_confidence)
        final_entry      = ai_analysis.get("entry_price", final_entry)
        final_stop       = ai_analysis.get("stop_price", final_stop)
        final_target     = ai_analysis.get("target_price", final_target)
        final_rr         = ai_analysis.get("risk_reward", final_rr)

        explanation = {
            "summary": ai_analysis.get("plain_english_summary", ""),
            "execution": ai_analysis.get("execution_instruction", ""),
            "verdict": final_verdict,
            "confidence": final_confidence,
            "tier": ai_analysis.get("tier", payload_dict.get("signal_tier", "B")),
            "smc_quality": ai_analysis.get("smc_quality", ""),
            "strongest_factor": ai_analysis.get("strongest_factor", ""),
            "biggest_risk": ai_analysis.get("biggest_risk", ""),
            "key_confirmations": ai_analysis.get("key_confirmations", []),
            "key_risks": ai_analysis.get("key_risks", []),
            "phase_analysis": ai_analysis.get("phase_scores", {}),
            "invalidation_level": ai_analysis.get("invalidation_level"),
            "position_size": ai_analysis.get("position_size_recommendation", ""),
            "dollar_risk_mnq": ai_analysis.get("dollar_risk_1_mnq"),
            "dollar_risk_mes": ai_analysis.get("dollar_risk_1_mes"),
            "composite_score": payload_dict.get("composite_score"),
            "signal_tier": payload_dict.get("signal_tier"),
            "ai_powered": True,
            "passed_rules": icc_result.explanation.get("passed_rules", []),
            "failed_rules": icc_result.explanation.get("failed_rules", []),
            "suggested_review_note": icc_result.explanation.get("suggested_review_note", ""),
        }

    # Build phase scores from AI or rule engine
    score_breakdown = icc_result.score_breakdown or {}
    if ai_analysis and ai_analysis.get("phase_scores"):
        for phase, data in ai_analysis["phase_scores"].items():
            if phase in score_breakdown:
                score_breakdown[phase]["score"] = data.get("score", score_breakdown[phase].get("score", 0))
                score_breakdown[phase]["ai_note"] = data.get("note", "")
            else:
                score_breakdown[phase] = {"score": data.get("score", 0), "passed": data.get("score", 0) >= 50, "ai_note": data.get("note", "")}

    # Store SetupEvaluation
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
        score_breakdown=score_breakdown,
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
