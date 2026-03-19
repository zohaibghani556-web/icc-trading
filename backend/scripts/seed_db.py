"""
scripts/seed_db.py
==================
Populates the database with default data so the app works out of the box.

Run this ONCE after the server has started for the first time:
    python scripts/seed_db.py

What it creates:
  - One default ICC configuration (all the rule thresholds)
  - All 10 supported instruments (ES, NQ, YM, CL, GC and their micros)
"""

import asyncio
import sys
import os

# Make sure Python can find the app package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import AsyncSessionLocal, engine, Base
from app.models.icc_config import ICCConfiguration
from app.models.instrument import Instrument


INSTRUMENTS = [
    dict(symbol="ES1!",  name="E-mini S&P 500",       asset_class="equity_index", exchange="CME",   tick_size=0.25,  tick_value=12.50,  is_micro=False),
    dict(symbol="MES1!", name="Micro E-mini S&P 500",  asset_class="equity_index", exchange="CME",   tick_size=0.25,  tick_value=1.25,   is_micro=True),
    dict(symbol="NQ1!",  name="E-mini Nasdaq 100",     asset_class="equity_index", exchange="CME",   tick_size=0.25,  tick_value=5.00,   is_micro=False),
    dict(symbol="MNQ1!", name="Micro E-mini Nasdaq",   asset_class="equity_index", exchange="CME",   tick_size=0.25,  tick_value=0.50,   is_micro=True),
    dict(symbol="YM1!",  name="E-mini Dow Jones",      asset_class="equity_index", exchange="CBOT",  tick_size=1.0,   tick_value=5.00,   is_micro=False),
    dict(symbol="MYM1!", name="Micro E-mini Dow",      asset_class="equity_index", exchange="CBOT",  tick_size=1.0,   tick_value=0.50,   is_micro=True),
    dict(symbol="CL1!",  name="Crude Oil",              asset_class="energy",       exchange="NYMEX", tick_size=0.01,  tick_value=10.00,  is_micro=False),
    dict(symbol="MCL1!", name="Micro Crude Oil",        asset_class="energy",       exchange="NYMEX", tick_size=0.01,  tick_value=1.00,   is_micro=True),
    dict(symbol="GC1!",  name="Gold",                  asset_class="metal",        exchange="COMEX", tick_size=0.10,  tick_value=10.00,  is_micro=False),
    dict(symbol="MGC1!", name="Micro Gold",             asset_class="metal",        exchange="COMEX", tick_size=0.10,  tick_value=1.00,   is_micro=True),
]


async def seed():
    async with AsyncSessionLocal() as db:
        seeded = []
        skipped = []

        # ── Instruments ──────────────────────────────────────────────────
        for spec in INSTRUMENTS:
            existing = await db.execute(
                select(Instrument).where(Instrument.symbol == spec["symbol"])
            )
            if existing.scalar_one_or_none():
                skipped.append(spec["symbol"])
                continue
            db.add(Instrument(**spec))
            seeded.append(spec["symbol"])

        # ── Default ICC configuration ────────────────────────────────────
        existing_config = await db.execute(
            select(ICCConfiguration).where(ICCConfiguration.name == "Default")
        )
        if not existing_config.scalar_one_or_none():
            db.add(ICCConfiguration(
                name="Default",
                is_active=True,
                allowed_sessions=["us_premarket", "us_regular", "globex"],
                require_htf_bias=True,
                min_retracement_pct=0.236,
                max_retracement_pct=0.618,
                require_correction_zone=True,
                allowed_correction_zones=[
                    "fair_value_gap", "order_block", "prior_breakout_level",
                    "vwap", "anchored_vwap", "discount_zone", "fibonacci_zone"
                ],
                min_risk_reward=2.0,
                max_risk_per_trade_pct=1.0,
                daily_max_loss_pct=3.0,
                max_consecutive_losses=3,
                max_open_positions=1,
                countertrend_score_penalty=20,
                min_continuation_trigger_score=50,
            ))
            seeded.append("Default ICC config")
        else:
            skipped.append("Default ICC config")

        await db.commit()

        print("\n✅ Seed complete")
        if seeded:
            print(f"   Created : {', '.join(seeded)}")
        if skipped:
            print(f"   Skipped (already exist): {', '.join(skipped)}")


if __name__ == "__main__":
    asyncio.run(seed())
