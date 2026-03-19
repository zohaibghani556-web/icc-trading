"""
tests/test_icc_engine.py — Unit tests for the ICC evaluation engine

Run with:
  cd backend
  pytest tests/test_icc_engine.py -v
"""

import pytest
from app.services.icc_engine import ICCEvaluator

# ── Default test config (mirrors production defaults) ─────────────────────
DEFAULT_CONFIG = {
    "allowed_sessions": ["us_regular", "us_premarket"],
    "require_htf_bias": False,  # Relaxed for tests
    "min_structure_break_points": 2.0,
    "min_retracement_pct": 0.236,
    "max_retracement_pct": 0.618,
    "require_correction_zone": False,
    "min_risk_reward": 2.0,
    "max_risk_per_trade_pct": 1.0,
    "daily_max_loss_pct": 3.0,
    "max_consecutive_losses": 3,
    "max_open_positions": 0,  # 0 open = no blocking
    "countertrend_score_penalty": 20,
    "min_continuation_trigger_score": 50,
}

evaluator = ICCEvaluator()


# ── VALID TRADE TESTS ─────────────────────────────────────────────────────

def test_valid_trade_complete_setup():
    """A complete setup_complete signal with all fields should return valid_trade."""
    signal = {
        "symbol": "ES1!",
        "timeframe": "5",
        "direction": "bullish",
        "signal_type": "setup_complete",
        "indication_type": "structure_break_high",
        "correction_zone_type": "fair_value_gap",
        "continuation_trigger_type": "rejection_candle",
        "price": 5250.0,
        "high": 5252.0,
        "low": 5245.0,
        "htf_bias": "bullish",
        "session": "us_regular",
        "entry_price": 5248.0,
        "stop_price": 5240.0,
        "target_price": 5264.0,
        "signal_timestamp": "2024-01-15T15:30:00",
    }
    result = evaluator.evaluate(signal, DEFAULT_CONFIG)
    assert result.verdict == "valid_trade", f"Expected valid_trade, got {result.verdict}: {result.explanation.get('summary')}"
    assert result.confidence_score > 0.6


def test_valid_trade_htf_aligned_gets_higher_score():
    """HTF-aligned setups should score higher than countertrend."""
    base = {
        "symbol": "ES1!",
        "timeframe": "5",
        "signal_type": "setup_complete",
        "indication_type": "structure_break_high",
        "price": 5250.0,
        "session": "us_regular",
        "entry_price": 5248.0,
        "stop_price": 5240.0,
        "target_price": 5264.0,
        "signal_timestamp": "2024-01-15T15:30:00",
    }

    aligned = evaluator.evaluate({**base, "direction": "bullish", "htf_bias": "bullish"}, DEFAULT_CONFIG)
    countertrend = evaluator.evaluate({**base, "direction": "bullish", "htf_bias": "bearish"}, DEFAULT_CONFIG)

    assert aligned.confidence_score > countertrend.confidence_score, (
        f"Aligned ({aligned.confidence_score:.2f}) should beat countertrend ({countertrend.confidence_score:.2f})"
    )


# ── WATCH ONLY TESTS ──────────────────────────────────────────────────────

def test_watch_only_indication_only():
    """An indication-only signal should return watch_only."""
    signal = {
        "symbol": "NQ1!",
        "timeframe": "5",
        "direction": "bearish",
        "signal_type": "indication",
        "indication_type": "displacement_down",
        "price": 18500.0,
        "session": "us_regular",
        "signal_timestamp": "2024-01-15T15:30:00",
    }
    result = evaluator.evaluate(signal, DEFAULT_CONFIG)
    assert result.verdict == "watch_only", f"Expected watch_only, got {result.verdict}"


# ── INVALID SETUP TESTS ───────────────────────────────────────────────────

def test_invalid_unknown_symbol():
    """Unknown symbol should return invalid_setup."""
    signal = {
        "symbol": "AAPL",  # Not a futures symbol
        "timeframe": "5",
        "direction": "bullish",
        "signal_type": "setup_complete",
        "price": 185.0,
        "session": "us_regular",
        "signal_timestamp": "2024-01-15T15:30:00",
    }
    result = evaluator.evaluate(signal, DEFAULT_CONFIG)
    assert result.verdict == "invalid_setup"


def test_invalid_wrong_session():
    """Signal outside allowed session should be blocked."""
    signal = {
        "symbol": "ES1!",
        "timeframe": "5",
        "direction": "bullish",
        "signal_type": "setup_complete",
        "price": 5250.0,
        "session": "asia",  # Not in allowed sessions
        "entry_price": 5248.0,
        "stop_price": 5240.0,
        "target_price": 5264.0,
        "signal_timestamp": "2024-01-15T15:30:00",
    }
    config = {**DEFAULT_CONFIG, "allowed_sessions": ["us_regular"]}
    result = evaluator.evaluate(signal, config)
    assert result.verdict == "invalid_setup"


def test_invalid_rr_too_low():
    """Trade with RR below minimum should be blocked."""
    signal = {
        "symbol": "ES1!",
        "timeframe": "5",
        "direction": "bullish",
        "signal_type": "setup_complete",
        "indication_type": "structure_break_high",
        "price": 5250.0,
        "session": "us_regular",
        "entry_price": 5248.0,
        "stop_price": 5240.0,     # 8 point risk
        "target_price": 5253.0,   # 5 point reward = 0.6:1 RR — below 2.0 minimum
        "signal_timestamp": "2024-01-15T15:30:00",
    }
    result = evaluator.evaluate(signal, DEFAULT_CONFIG)
    assert result.verdict == "invalid_setup"


def test_invalid_daily_loss_limit():
    """Should block trade when daily loss limit is hit."""
    signal = {
        "symbol": "ES1!",
        "timeframe": "5",
        "direction": "bullish",
        "signal_type": "setup_complete",
        "indication_type": "structure_break_high",
        "price": 5250.0,
        "session": "us_regular",
        "entry_price": 5248.0,
        "stop_price": 5240.0,
        "target_price": 5264.0,
        "signal_timestamp": "2024-01-15T15:30:00",
    }
    account_state = {"daily_pnl_pct": -4.0}  # Down 4% — past 3% limit
    result = evaluator.evaluate(signal, DEFAULT_CONFIG, account_state)
    assert result.verdict == "invalid_setup"


# ── EXPLANATION TESTS ─────────────────────────────────────────────────────

def test_explanation_is_complete():
    """Every result should have a non-empty explanation with all required keys."""
    signal = {
        "symbol": "ES1!",
        "timeframe": "5",
        "direction": "bullish",
        "signal_type": "indication",
        "price": 5250.0,
        "session": "us_regular",
        "signal_timestamp": "2024-01-15T15:30:00",
    }
    result = evaluator.evaluate(signal, DEFAULT_CONFIG)
    exp = result.explanation

    assert "verdict" in exp
    assert "summary" in exp
    assert "passed_rules" in exp
    assert "failed_rules" in exp
    assert "suggested_review_note" in exp
    assert isinstance(exp["passed_rules"], list)
    assert len(exp["summary"]) > 0


def test_countertrend_flagged():
    """Countertrend setups should be explicitly flagged."""
    signal = {
        "symbol": "ES1!",
        "timeframe": "5",
        "direction": "bullish",
        "htf_bias": "bearish",
        "signal_type": "setup_complete",
        "price": 5250.0,
        "session": "us_regular",
        "entry_price": 5248.0,
        "stop_price": 5240.0,
        "target_price": 5264.0,
        "signal_timestamp": "2024-01-15T15:30:00",
    }
    result = evaluator.evaluate(signal, DEFAULT_CONFIG)
    assert result.is_countertrend is True


if __name__ == "__main__":
    # Quick smoke test — run without pytest
    print("Running smoke tests…")
    test_valid_trade_complete_setup()
    print("✅ valid trade")
    test_watch_only_indication_only()
    print("✅ watch only")
    test_invalid_unknown_symbol()
    print("✅ invalid symbol")
    test_invalid_rr_too_low()
    print("✅ invalid RR")
    test_explanation_is_complete()
    print("✅ explanation complete")
    test_countertrend_flagged()
    print("✅ countertrend flagged")
    print("\n✅ All smoke tests passed!")
