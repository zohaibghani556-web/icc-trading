"""
api/v1/setups.py — Setup evaluation query and management routes
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import Optional, List
from uuid import UUID

from app.db.database import get_db
from app.models.setup import SetupEvaluation
from app.schemas.alert import SetupEvaluationOut

router = APIRouter()


@router.get("/", response_model=List[SetupEvaluationOut])
async def list_setups(
    symbol: Optional[str] = None,
    verdict: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all setup evaluations with optional filters."""
    query = select(SetupEvaluation).order_by(desc(SetupEvaluation.evaluated_at))

    if symbol:
        query = query.where(SetupEvaluation.symbol == symbol)
    if verdict:
        query = query.where(SetupEvaluation.verdict == verdict)
    if direction:
        query = query.where(SetupEvaluation.direction == direction)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{setup_id}", response_model=SetupEvaluationOut)
async def get_setup(setup_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single setup evaluation by ID."""
    result = await db.execute(
        select(SetupEvaluation).where(SetupEvaluation.id == setup_id)
    )
    setup = result.scalar_one_or_none()
    if not setup:
        raise HTTPException(status_code=404, detail="Setup not found")
    return setup


@router.patch("/{setup_id}/notes")
async def update_setup_notes(
    setup_id: UUID,
    notes: str,
    db: AsyncSession = Depends(get_db),
):
    """Add or update notes on a setup evaluation."""
    result = await db.execute(
        select(SetupEvaluation).where(SetupEvaluation.id == setup_id)
    )
    setup = result.scalar_one_or_none()
    if not setup:
        raise HTTPException(status_code=404, detail="Setup not found")
    setup.notes = notes
    return {"updated": True}
