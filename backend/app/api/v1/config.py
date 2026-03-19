"""
api/v1/config.py — ICC configuration management

Lets you read and update the active ICC rule settings from the UI.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

from app.db.database import get_db
from app.models.icc_config import ICCConfiguration

router = APIRouter()


class ConfigUpdate(BaseModel):
    min_retracement_pct: Optional[float] = None
    max_retracement_pct: Optional[float] = None
    min_risk_reward: Optional[float] = None
    daily_max_loss_pct: Optional[float] = None
    max_consecutive_losses: Optional[int] = None
    max_open_positions: Optional[int] = None
    require_htf_bias: Optional[bool] = None
    allowed_sessions: Optional[List[str]] = None
    require_correction_zone: Optional[bool] = None
    countertrend_score_penalty: Optional[int] = None
    max_risk_per_trade_pct: Optional[float] = None


@router.get("/active")
async def get_active_config(db: AsyncSession = Depends(get_db)):
    """Get the currently active ICC configuration."""
    result = await db.execute(
        select(ICCConfiguration).where(ICCConfiguration.is_active == True).limit(1)
    )
    config = result.scalar_one_or_none()

    if not config:
        # Create default config if none exists
        config = ICCConfiguration(name="Default")
        db.add(config)
        await db.flush()

    return config


@router.patch("/active")
async def update_active_config(update: ConfigUpdate, db: AsyncSession = Depends(get_db)):
    """Update the active ICC configuration."""
    result = await db.execute(
        select(ICCConfiguration).where(ICCConfiguration.is_active == True).limit(1)
    )
    config = result.scalar_one_or_none()

    if not config:
        config = ICCConfiguration(name="Default")
        db.add(config)

    # Apply only fields that were provided
    update_data = update.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    return {"updated": True, "fields_changed": list(update_data.keys())}
