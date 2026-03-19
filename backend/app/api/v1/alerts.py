"""
api/v1/alerts.py — TradingView webhook intake and alert management

This is the entry point for all TradingView alerts.
Every incoming alert is:
1. Validated (correct token, valid JSON shape)
2. Stored as a RawAlert
3. Normalized into a Signal
4. Evaluated by the ICC engine
5. Stored as a SetupEvaluation
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List
from datetime import datetime
import json
import uuid

from app.db.database import get_db
from app.core.config import settings
from app.models.alert import RawAlert
from app.models.signal import Signal
from app.models.setup import SetupEvaluation
from app.models.icc_config import ICCConfiguration
from app.schemas.alert import WebhookAlertPayload, AlertResponse, SignalOut, SetupEvaluationOut
from app.services.icc_engine import ICCEvaluator

router = APIRouter()
evaluator = ICCEvaluator()


@router.post("/webhook", response_model=AlertResponse)
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_webhook_token: Optional[str] = Header(None),
):
    """
    Receives webhook alerts from TradingView.

    TradingView sends a POST request to this endpoint whenever
    one of your configured alerts fires.

    Security: The X-Webhook-Token header must match your WEBHOOK_SECRET.
    """
    # ── Validate security token ───────────────────────────────────────────
    token_valid = (x_webhook_token == settings.WEBHOOK_SECRET)

    # ── Read raw body ─────────────────────────────────────────────────────
    raw_body = await request.body()
    client_ip = request.client.host if request.client else "unknown"

    try:
        payload_dict = json.loads(raw_body)
    except json.JSONDecodeError:
        # Store the failed attempt
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

    # ── Store raw alert ───────────────────────────────────────────────────
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

    # ── Reject if token invalid (after storing for audit) ─────────────────
    if not token_valid:
        raw_alert.processing_error = "Invalid webhook token"
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    # ── Validate payload shape ────────────────────────────────────────────
    try:
        alert_data = WebhookAlertPayload(**payload_dict)
    except Exception as e:
        raw_alert.processing_error = str(e)
        raise HTTPException(status_code=422, detail=f"Payload validation failed: {str(e)}")

    # ── Parse timestamp ───────────────────────────────────────────────────
    signal_ts = datetime.utcnow()
    if alert_data.timestamp:
        try:
            signal_ts = datetime.fromisoformat(alert_data.timestamp.replace("Z", "+00:00"))
        except ValueError:
            pass

    # ── Create normalized Signal ──────────────────────────────────────────
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

    # ── Load active ICC configuration ─────────────────────────────────────
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

    # ── Run ICC evaluation ─────────────────────────────────────────────────
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
        "session": alert_data.session,
        "retracement_pct": alert_data.retracement_pct,
        "entry_price": alert_data.entry_price,
        "stop_price": alert_data.stop_price,
        "target_price": alert_data.target_price,
        "signal_timestamp": signal_ts.isoformat(),
    }

    icc_result = evaluator.evaluate(signal_dict, config_dict)

    # ── Store SetupEvaluation ─────────────────────────────────────────────
    setup_eval = SetupEvaluation(
        signal_id=signal.id,
        symbol=alert_data.symbol,
        timeframe=alert_data.timeframe,
        direction=alert_data.direction,
        session=alert_data.session,
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
        entry_price=icc_result.entry_price,
        stop_price=icc_result.stop_price,
        target_price=icc_result.target_price,
        risk_reward=icc_result.risk_reward,
        explanation=icc_result.explanation,
        score_breakdown=icc_result.score_breakdown,
        is_countertrend=icc_result.is_countertrend,
        has_htf_alignment=icc_result.has_htf_alignment,
        signal_timestamp=signal_ts,
    )
    db.add(setup_eval)

    # Mark signal as evaluated and alert as processed
    signal.evaluated = True
    raw_alert.processed = True
    raw_alert.processed_at = datetime.utcnow()

    return AlertResponse(
        received=True,
        alert_id=str(raw_alert.id),
        symbol=alert_data.symbol,
        verdict=icc_result.verdict,
        confidence_score=icc_result.confidence_score,
        message=icc_result.explanation.get("summary", "Evaluation complete."),
    )


@router.get("/recent", response_model=List[SetupEvaluationOut])
async def get_recent_setups(
    limit: int = 50,
    symbol: Optional[str] = None,
    verdict: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get recent setup evaluations for the dashboard feed."""
    query = select(SetupEvaluation).order_by(desc(SetupEvaluation.evaluated_at))

    if symbol:
        query = query.where(SetupEvaluation.symbol == symbol)
    if verdict:
        query = query.where(SetupEvaluation.verdict == verdict)

    query = query.limit(limit)
    result = db.execute(query)
    setups = result.scalars().all()
    return setups
