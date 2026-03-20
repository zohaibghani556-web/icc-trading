"""
services/icc_engine/continuation.py — Continuation Phase Scorer

FIXES:
  - Added all Pine Script continuation_trigger_type names
  - Pine sends: macd_cross, rsi_divergence, hidden_divergence,
    volume_delta, volume_expansion, rejection_candle
"""

from typing import Dict, Any, Optional
from app.services.icc_engine.result import PhaseResult, RuleResult


CONTINUATION_TRIGGER_QUALITY = {
    # ── Backend canonical names ───────────────────────────────────────────
    "rejection_candle":          85,
    "structure_break_pullback":  90,
    "micro_level_reclaim":       80,
    "displacement_candle":       85,
    "volume_expansion":          75,
    "breakout_correction_range": 80,
    "engulfing_candle":          75,
    "inside_bar_break":          70,
    "order_flow_confirmation":   85,
    "momentum_shift":            70,
    "vwap_reclaim":              75,

    # ── Pine Script names (what actually gets sent) ───────────────────────
    "macd_cross":        82,   # MACD line crosses signal — strong momentum confirmation
    "rsi_divergence":    85,   # RSI divergence — classic reversal/continuation signal
    "hidden_divergence": 80,   # Hidden divergence — trend continuation signal
    "volume_delta":      78,   # Positive/negative delta confirming direction
    # volume_expansion already covered above
    # rejection_candle already covered above
}

DEFAULT_TRIGGER_QUALITY = 60


class ContinuationScorer:

    def evaluate(
        self,
        signal_data: Dict[str, Any],
        config: Dict[str, Any],
    ) -> PhaseResult:
        rules = []
        total_score = 0
        max_possible = 0

        signal_type = signal_data.get("signal_type", "")
        trigger_type = signal_data.get("continuation_trigger_type", "")
        direction = signal_data.get("direction", "")
        entry = signal_data.get("entry_price")
        stop = signal_data.get("stop_price")
        target = signal_data.get("target_price")
        min_rr = config.get("min_risk_reward", 2.0)
        min_trigger_score = config.get("min_continuation_trigger_score", 40)

        # ── Rule 1: Continuation signal present ───────────────────────────
        has_continuation = signal_type in ("continuation", "setup_complete")
        cont_rule = RuleResult(
            passed=has_continuation,
            rule_id="cont_signal_present",
            label="Continuation trigger present",
            message=(
                "Continuation signal received."
                if has_continuation
                else f"Signal type '{signal_type}' is not a continuation trigger."
            ),
            score=25 if has_continuation else 0,
            max_score=25, is_blocking=True,
        )
        rules.append(cont_rule)
        total_score += cont_rule.score
        max_possible += cont_rule.max_score

        if not has_continuation:
            return PhaseResult(
                phase="continuation", passed=False, score=0, rules=rules,
                summary="No continuation trigger. Setup is watch-only.",
            )

        # ── Rule 2: Trigger type quality ──────────────────────────────────
        trigger_rule = self._check_trigger_quality(trigger_type, min_trigger_score)
        rules.append(trigger_rule)
        total_score += trigger_rule.score
        max_possible += trigger_rule.max_score

        # ── Rule 3: Trade levels defined ──────────────────────────────────
        levels_rule = self._check_levels_defined(entry, stop, target, direction)
        rules.append(levels_rule)
        total_score += levels_rule.score
        max_possible += levels_rule.max_score

        # ── Rule 4: Risk-reward ───────────────────────────────────────────
        rr_rule = self._check_risk_reward(entry, stop, target, direction, min_rr)
        rules.append(rr_rule)
        total_score += rr_rule.score
        max_possible += rr_rule.max_score

        has_blocking_failure = any(r.is_blocking and not r.passed for r in rules)
        phase_passed = not has_blocking_failure
        score = int((total_score / max_possible) * 100) if max_possible > 0 else 0
        actual_rr = self._compute_rr(entry, stop, target, direction)

        quality = CONTINUATION_TRIGGER_QUALITY.get(trigger_type or "", DEFAULT_TRIGGER_QUALITY)

        if phase_passed:
            rr_str = f"RR: {actual_rr:.1f}:1" if actual_rr else "RR: unknown"
            summary = f"Continuation confirmed. Trigger: {trigger_type or 'unspecified'} (quality {quality}/100). {rr_str}."
        else:
            failures = [r.label for r in rules if r.is_blocking and not r.passed]
            summary = f"Continuation blocked: {', '.join(failures)}."

        return PhaseResult(
            phase="continuation", passed=phase_passed, score=score,
            rules=rules, summary=summary,
        )

    def _check_trigger_quality(self, trigger_type, min_score) -> RuleResult:
        quality = CONTINUATION_TRIGGER_QUALITY.get(trigger_type or "", DEFAULT_TRIGGER_QUALITY)
        meets_min = quality >= min_score

        if not trigger_type:
            return RuleResult(
                passed=True, rule_id="cont_trigger_quality",
                label="Trigger type quality",
                message=f"No trigger type specified. Using default quality {DEFAULT_TRIGGER_QUALITY}.",
                score=int(DEFAULT_TRIGGER_QUALITY * 0.35),
                max_score=35, is_blocking=False,
            )

        return RuleResult(
            passed=meets_min,
            rule_id="cont_trigger_quality",
            label="Trigger type quality",
            message=(
                f"Trigger '{trigger_type}' quality {quality}/100 meets minimum {min_score}."
                if meets_min
                else f"Trigger '{trigger_type}' quality {quality}/100 below minimum {min_score}."
            ),
            score=int(quality * 0.35) if meets_min else int(quality * 0.15),
            max_score=35,
            is_blocking=not meets_min,
        )

    def _check_levels_defined(self, entry, stop, target, direction) -> RuleResult:
        if entry and stop and target:
            if direction == "bullish" and (stop >= entry or target <= entry):
                return RuleResult(
                    passed=False, rule_id="cont_levels_valid",
                    label="Trade levels valid",
                    message=f"Invalid bull levels: entry={entry}, stop={stop}, target={target}.",
                    score=0, max_score=20, is_blocking=True,
                )
            if direction == "bearish" and (stop <= entry or target >= entry):
                return RuleResult(
                    passed=False, rule_id="cont_levels_valid",
                    label="Trade levels valid",
                    message=f"Invalid bear levels: entry={entry}, stop={stop}, target={target}.",
                    score=0, max_score=20, is_blocking=True,
                )
            return RuleResult(
                passed=True, rule_id="cont_levels_valid",
                label="Trade levels valid",
                message=f"Entry: {entry}, Stop: {stop}, Target: {target}. All valid.",
                score=20, max_score=20, is_blocking=False,
            )

        missing = [n for n, v in [("entry", entry), ("stop", stop), ("target", target)] if not v]
        return RuleResult(
            passed=False, rule_id="cont_levels_valid",
            label="Trade levels valid",
            message=f"Missing trade levels: {', '.join(missing)}.",
            score=0, max_score=20, is_blocking=True,
        )

    def _check_risk_reward(self, entry, stop, target, direction, min_rr) -> RuleResult:
        rr = self._compute_rr(entry, stop, target, direction)
        if rr is None:
            return RuleResult(
                passed=False, rule_id="cont_risk_reward",
                label=f"Minimum RR {min_rr}:1 met",
                message="Cannot compute RR — missing levels.",
                score=0, max_score=20, is_blocking=True,
            )

        meets_rr = rr >= min_rr
        pts = 20 if rr >= min_rr * 2 else (15 if meets_rr else 0)

        return RuleResult(
            passed=meets_rr,
            rule_id="cont_risk_reward",
            label=f"Minimum RR {min_rr}:1 met",
            message=(
                f"RR {rr:.1f}:1 meets minimum {min_rr}:1."
                if meets_rr
                else f"RR {rr:.1f}:1 below minimum {min_rr}:1."
            ),
            score=pts, max_score=20, is_blocking=True,
        )

    @staticmethod
    def _compute_rr(entry, stop, target, direction) -> Optional[float]:
        if not all([entry, stop, target]):
            return None
        try:
            risk = abs(entry - stop)
            reward = abs(target - entry)
            return round(reward / risk, 2) if risk > 0 else None
        except (TypeError, ZeroDivisionError):
            return None

    @staticmethod
    def get_detected_trigger(signal_data: Dict[str, Any]) -> Optional[str]:
        return signal_data.get("continuation_trigger_type")
