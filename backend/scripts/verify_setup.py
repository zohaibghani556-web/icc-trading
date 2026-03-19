"""
scripts/verify_setup.py
========================
Run this to check everything is wired up correctly before starting the server.
It does NOT need a database — it just checks imports and configuration.

Run it with:
    python scripts/verify_setup.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("\n🔍 ICC Trading Assistant — Setup Verification\n")
errors = []

# 1. Check Python version
import platform
py = sys.version_info
if py.major < 3 or (py.major == 3 and py.minor < 11):
    errors.append(f"Python 3.11+ required. You have {py.major}.{py.minor}")
else:
    print(f"  ✅ Python {py.major}.{py.minor}.{py.micro}")

# 2. Check required packages
packages = [
    ("fastapi",           "FastAPI"),
    ("uvicorn",           "Uvicorn"),
    ("sqlalchemy",        "SQLAlchemy"),
    ("asyncpg",           "asyncpg (async PostgreSQL driver)"),
    ("pydantic",          "Pydantic"),
    ("pydantic_settings", "Pydantic Settings"),
    ("dotenv",            "python-dotenv"),
]
for pkg, label in packages:
    try:
        __import__(pkg)
        print(f"  ✅ {label}")
    except ImportError:
        errors.append(f"Missing package: {label}  →  run: pip install -r requirements.txt")

# 3. Check .env file exists
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    print(f"  ✅ .env file found")
else:
    errors.append(".env file missing. Copy .env.example to .env and fill in your values.")

# 4. Check app imports
try:
    from app.core.config import settings
    print(f"  ✅ Config loaded  (environment: {settings.ENVIRONMENT})")
except Exception as e:
    errors.append(f"Config error: {e}")

try:
    from app.services.icc_engine import ICCEvaluator
    evaluator = ICCEvaluator()
    print(f"  ✅ ICC engine imports OK")
except Exception as e:
    errors.append(f"ICC engine import error: {e}")

try:
    from app.models import RawAlert, Signal, SetupEvaluation, Trade, User, Instrument, ICCConfiguration
    print(f"  ✅ All models import OK")
except Exception as e:
    errors.append(f"Model import error: {e}")

try:
    from app.main import app
    print(f"  ✅ FastAPI app created OK  ({len(app.routes)} routes registered)")
except Exception as e:
    errors.append(f"App creation error: {e}")

# 5. Quick ICC engine smoke test
try:
    from app.services.icc_engine import ICCEvaluator
    ev = ICCEvaluator()
    result = ev.evaluate(
        signal_data={
            "symbol": "ES1!", "timeframe": "5", "direction": "bullish",
            "signal_type": "setup_complete", "price": 5250.0,
            "htf_bias": "bullish", "session": "us_regular",
            "indication_type": "structure_break_high",
            "correction_zone_type": "fair_value_gap",
            "continuation_trigger_type": "rejection_candle",
            "entry_price": 5255.0, "stop_price": 5245.0, "target_price": 5275.0,
        },
        config={}
    )
    print(f"  ✅ ICC engine smoke test passed  (verdict: {result.verdict}, confidence: {result.confidence_score:.0%})")
except Exception as e:
    errors.append(f"ICC engine smoke test failed: {e}")

# ── Summary ──────────────────────────────────────────────────────
print()
if errors:
    print(f"❌ Found {len(errors)} issue(s) to fix:\n")
    for i, err in enumerate(errors, 1):
        print(f"   {i}. {err}")
    print()
    sys.exit(1)
else:
    print("✅ All checks passed. You're ready to start the server.\n")
    print("   Next step:  uvicorn app.main:app --reload --port 8000\n")
