"""
services/icc_engine/continuation.py — Continuation Phase Scorer

This module evaluates the second "C" in ICC: the confirmation that the trend is resuming.

A valid continuation must:
1. Show a clear trigger (rejection candle, structure break in pullback, volume expansion, etc.)
2. Have an objective entry, stop, and target
3. Meet the minimum risk-reward requirement
4. Not be entering at a structurally unfavorable location

Think of this as: "Is there now objective evidence that price is resuming the original move?"
"""

from typing import Dict, Any, Optional
from app.services.icc_engine.result import PhaseResult, RuleResult


# ── Continuation trigger types and their quality scores ──────────────────
CONTINUATION_TRIGGER_QUALITY = {
    "rejection_candle":          85,  # Clear rejection (pin bar, hammer, etc.) from zone
    "structure_break_pullback":  90,  # Break of the pullback's own structure → very strong
    "micro_level_reclaim":       80,  # Reclaims a small level within the correction
    "displacement_candle":       85,  # Large candle in trade direction from zone
    "volume_expansion":          75,  # Volume surge in trade direction
    "breakout_correction_range": 80,  # Price breaks out of the correction range
    "engulfing_candle":          75,  # Bullish/bearish engulfing at zone
    "inside_bar_break":          70,  # Break of inside bar at zone
    "order_flow_confirmation":   85,  # Order flow tools confirm bid/ask
    "momentum_shift":            70,  # Momentum oscillator confirms direction
    "vwap_reclaim":              75,  # Reclaims VWAP from zone
}

DEFAULT_TRIGGER_QUALITY = 55


class ContinuationScorer:
    """
    Evaluates whether the trend is resuming after the correction.

    This is the final gate before a setup becomes a "valid_trade."
    Without continuation confirmation, we only have indication + correction = "watch_only."
    """

    def evaluate(
        self,
        signal_data: Dict[str, Any],
        config: Dict[str, Any],
    ) -> PhaseResult:
        """
        Score the Continuation phase.

        Returns:
            PhaseResult with pass/fail and score for Continuation
        """
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
        min_trigger_score = config.get("min_continuation_trigger_score", 50)

        # ── Rule 1: Continuation signal present ───────────────────────────
        has_continuation = signal_type in ("continuation", "setup_complete")
        cont_rule = RuleResult(
            passed=has_continuation,
            rule_id="cont_signal_present",
            label="Continuation trigger present",
            message=(
                "Continuation signal received."
                if has_continuation
                else f"Signal type '{signal_type}' is not a continuation trigger. "
                     f"Setup is incomplete — watch only."
            ),
            score=25 if has_continuation else 0,
            max_score=25,
            is_blocking=True,
        )
        rules.append(cont_rule)
        total_score += cont_rule.score
        max_possible += cont_rule.max_score

        if not has_continuation:
            return PhaseResult(
                phase="continuation",
                passed=False,
                score=0,
                rules=rules,
                summary="No continuation trigger yet. Setup is watch-only until trigger fires.",
            )

        # ── Rule 2: Trigger type quality ──────────────────────────────────
        trigger_rule = self._check_trigger_quality(trigger_type, min_trigger_score)
        rules.append(trigger_rule)
        total_score += trigger_rule.score
        max_possible += trigger_rule.max_score

        # ── Rule 3: Entry, stop, and target are defined ────────────────────
        levels_rule = self._check_levels_defined(entry, stop, target, direction)
        rules.append(levels_rule)
        total_score += levels_rule.score
        max_possible += levels_rule.max_score

        # ── Rule 4: Risk-reward meets minimum threshold ────────────────────
        rr_rule = self._check_risk_reward(entry, stop, target, direction, min_rr)
        rules.append(rr_rule)
        total_score += rr_rule.score
        max_possible += rr_rule.max_score

        # ── Determine pass/fail ───────────────────────────────────────────
        has_blocking_failure = any(r.is_blocking and not r.passed for r in rules)
        phase_passed = not has_blocking_failure

        score = int((total_score / max_possible) * 100) if max_possible > 0 else 0

        # ── Compute actual RR for output ───────────────────────────────────
        actual_rr = self._compute_rr(entry, stop, target, direction)

        if phase_passed:
            rr_str = f"RR: {actual_rr:.1f}:1" if actual_rr else "RR: unknown"
            summary = (
                f"Continuation confirmed. Trigger: {trigger_type or 'unspecified'}. "
                f"{rr_str}."
            )
        else:
            failures = [r.label for r in rules if r.is_blocking and not r.passed]
            summary = f"Continuation blocked: {', '.join(failures)}."

        return PhaseResult(
            phase="continuation",
            passed=phase_passed,
            score=score,
            rules=rules,
            summary=summary,
        )

    def _check_trigger_quality(
        self,
        trigger_type: Optional[str],
        min_score: int,
    ) -> RuleResult:
        quality = CONTINUATION_TRIGGER_QUALITY.get(trigger_type or "", DEFAULT_TRIGGER_QUALITY)
        meets_min = quality >= min_score

        if not trigger_type:
            return RuleResult(
                passed=True,
                rule_id="cont_trigger_quality",
                label="Trigger type quality",
                message="No trigger type specified. Using default quality.",
                score=int(DEFAULT_TRIGGER_QUALITY * 0.35),
                max_score=35,
                is_blocking=False,
            )

        return RuleResult(
            passed=meets_min,
            rule_id="cont_trigger_quality",
            label="Trigger type quality",
            message=(
                f"Trigger '{trigger_type}' quality {quality}/100 meets minimum {min_score}."
                if meets_min
                else f"Trigger '{trigger_type}' quality {quality}/100 is below minimum {min_score}."
            ),
            score=int(quality * 0.35) if meets_min else int(quality * 0.15),
            max_score=35,
            is_blocking=not meets_min,
        )

    def _check_levels_defined(
        self,
        entry: Optional[float],
        stop: Optional[float],
        target: Optional[float],
        direction: str,
    ) -> RuleResult:
        """All three trade levels must be defined for a valid trade."""
        if entry and stop and target:
            # Basic sanity checks
            if direction == "bullish" and (stop >= entry or target <= entry):
                return RuleResult(
                    passed=False,
                    rule_id="cont_levels_valid",
                    label="Trade levels valid",
                    message=f"Invalid levels for long: entry={entry}, stop={stop}, target={target}. "
                            f"Stop must be below entry, target above entry.",
                    score=0,
                    max_score=20,
                    is_blocking=True,
                )
            if direction == "bearish" and (stop <= entry or target >= entry):
                return RuleResult(
                    passed=False,
                    rule_id="cont_levels_valid",
                    label="Trade levels valid",
                    message=f"Invalid levels for short: entry={entry}, stop={stop}, target={target}. "
                            f"Stop must be above entry, target below entry.",
                    score=0,
                    max_score=20,
                    is_blocking=True,
                )
            return RuleResult(
                passed=True,
                rule_id="cont_levels_valid",
                label="Trade levels valid",
                message=f"Entry: {entry}, Stop: {stop}, Target: {target}. All levels valid.",
                score=20,
                max_score=20,
                is_blocking=False,
            )

        missing = [n for n, v in [("entry", entry), ("stop", stop), ("target", target)] if not v]
        return RuleResult(
            passed=False,
            rule_id="cont_levels_valid",
            label="Trade levels valid",
            message=f"Missing trade levels: {', '.join(missing)}. Cannot evaluate RR or risk.",
            score=0,
            max_score=20,
            is_blocking=True,
        )

    def _check_risk_reward(
        self,
        entry: Optional[float],
        stop: Optional[float],
        target: Optional[float],
        direction: str,
        min_rr: float,
    ) -> RuleResult:
        """The trade must offer at least the minimum risk-reward ratio."""
        rr = self._compute_rr(entry, stop, target, direction)

        if rr is None:
            return RuleResult(
                passed=False,
                rule_id="cont_risk_reward",
                label=f"Minimum RR {min_rr}:1 met",
                message="Cannot compute RR — missing entry, stop, or target.",
                score=0,
                max_score=20,
                is_blocking=True,
            )

        meets_rr = rr >= min_rr
        # Bonus points for exceptional RR
        if rr >= min_rr * 2:
            pts = 20
        elif meets_rr:
            pts = 15
        else:
            pts = 0

        return RuleResult(
            passed=meets_rr,
            rule_id="cont_risk_reward",
            label=f"Minimum RR {min_rr}:1 met",
            message=(
                f"RR {rr:.1f}:1 {'exceeds' if rr >= min_rr * 2 else 'meets'} minimum {min_rr}:1."
                if meets_rr
                else f"RR {rr:.1f}:1 is below minimum {min_rr}:1. Setup does not offer enough reward."
            ),
            score=pts,
            max_score=20,
            is_blocking=True,
        )

    @staticmethod
    def _compute_rr(
        entry: Optional[float],
        stop: Optional[float],
        target: Optional[float],
        direction: str,
    ) -> Optional[float]:
        """Compute the risk-reward ratio. Returns None if levels are missing."""
        if not all([entry, stop, target]):
            return None
        try:
            risk = abs(entry - stop)
            reward = abs(target - entry)
            if risk == 0:
                return None
            return round(reward / risk, 2)
        except (TypeError, ZeroDivisionError):
            return None

    @staticmethod
    def get_detected_trigger(signal_data: Dict[str, Any]) -> Optional[str]:
        return signal_data.get("continuation_trigger_type")
