"""
services/icc_engine/indication.py — Indication Phase Scorer

This module evaluates the FIRST leg of ICC: the initial directional signal.
It answers: "Is there a real, measurable directional move happening?"

A valid indication must be:
1. A recognizable pattern type (structure break, displacement, sweep, etc.)
2. Large enough to be meaningful (above minimum impulse threshold)
3. Aligned with (or at least not fighting) the higher timeframe bias
"""

from typing import Dict, Any, Optional
from app.services.icc_engine.result import PhaseResult, RuleResult


# ── Recognized indication types and their base quality scores ─────────────
# Higher score = stronger, more reliable indication type
INDICATION_QUALITY = {
    "structure_break_high":      85,   # Clear break of swing high
    "structure_break_low":       85,   # Clear break of swing low
    "liquidity_sweep_reclaim":   90,   # Sweep + reclaim = very strong
    "displacement_up":           80,   # Large bullish expansion candle
    "displacement_down":         80,   # Large bearish expansion candle
    "momentum_expansion":        70,   # Momentum accelerating in direction
    "level_reclaim":             65,   # Reclaim of key intraday level
    "market_structure_shift":    75,   # MSS / CHoCH
    "order_flow_shift":          70,   # Order flow flips direction
    "breakout_with_volume":      80,   # Level break + volume confirmation
}

# Default if type is unrecognized
DEFAULT_INDICATION_QUALITY = 50


class IndicationScorer:
    """
    Evaluates whether a valid Indication has occurred.

    The Indication is the "I" in ICC — it's the initial directional evidence
    that tells you which way price wants to move.
    """

    def evaluate(
        self,
        signal_data: Dict[str, Any],
        config: Dict[str, Any],
    ) -> PhaseResult:
        """
        Score the Indication phase.

        Args:
            signal_data: Normalized signal dictionary
            config: Active ICC configuration settings

        Returns:
            PhaseResult with pass/fail and score for Indication
        """
        rules = []
        total_score = 0
        max_possible = 0

        direction = signal_data.get("direction", "")
        signal_type = signal_data.get("signal_type", "")
        indication_type = signal_data.get("indication_type", "")
        htf_bias = signal_data.get("htf_bias", "neutral")
        price = signal_data.get("price", 0)
        high = signal_data.get("high")
        low = signal_data.get("low")

        # ── Rule 1: Signal is recognized as an indication ─────────────────
        is_indication = signal_type in ("indication", "setup_complete")
        indication_present_rule = RuleResult(
            passed=is_indication,
            rule_id="ind_signal_present",
            label="Indication signal received",
            message=(
                f"Signal type '{signal_type}' recognized as indication."
                if is_indication
                else f"Signal type '{signal_type}' is not an indication. Expected 'indication' or 'setup_complete'."
            ),
            score=30 if is_indication else 0,
            max_score=30,
            is_blocking=True,
        )
        rules.append(indication_present_rule)
        total_score += indication_present_rule.score
        max_possible += indication_present_rule.max_score

        if not is_indication:
            return PhaseResult(
                phase="indication",
                passed=False,
                score=0,
                rules=rules,
                summary="No indication signal. This is not an indication-type alert.",
            )

        # ── Rule 2: Indication type is recognized ─────────────────────────
        type_quality = INDICATION_QUALITY.get(indication_type, DEFAULT_INDICATION_QUALITY)
        type_recognized = indication_type in INDICATION_QUALITY

        type_rule = RuleResult(
            passed=True,  # unknown types still proceed, just with lower score
            rule_id="ind_type_recognized",
            label="Indication type quality",
            message=(
                f"Type '{indication_type}' recognized. Quality score: {type_quality}/100."
                if type_recognized
                else f"Indication type '{indication_type}' is unrecognized. Using default quality."
            ),
            score=int(type_quality * 0.4),  # type quality contributes up to 40 points
            max_score=40,
            is_blocking=False,
        )
        rules.append(type_rule)
        total_score += type_rule.score
        max_possible += type_rule.max_score

        # ── Rule 3: Candle body/range indicates meaningful impulse ─────────
        impulse_rule = self._check_impulse_size(
            price, high, low,
            min_impulse=config.get("min_structure_break_points", 2.0),
            symbol=signal_data.get("symbol", ""),
        )
        rules.append(impulse_rule)
        total_score += impulse_rule.score
        max_possible += impulse_rule.max_score

        # ── Rule 4: Directional alignment with HTF bias ───────────────────
        alignment_rule = self._check_htf_alignment(direction, htf_bias)
        rules.append(alignment_rule)
        total_score += alignment_rule.score
        max_possible += alignment_rule.max_score

        # ── Determine pass/fail ───────────────────────────────────────────
        has_blocking_failure = any(r.is_blocking and not r.passed for r in rules)
        phase_passed = not has_blocking_failure and indication_present_rule.passed

        score = int((total_score / max_possible) * 100) if max_possible > 0 else 0

        # ── Build summary ─────────────────────────────────────────────────
        is_countertrend = (
            (direction == "bullish" and htf_bias == "bearish") or
            (direction == "bearish" and htf_bias == "bullish")
        )

        if phase_passed:
            ct_note = " (COUNTERTREND — reduced confidence)" if is_countertrend else ""
            summary = (
                f"Indication confirmed. Type: {indication_type or 'unspecified'}. "
                f"Direction: {direction}.{ct_note}"
            )
        else:
            failures = [r.label for r in rules if r.is_blocking and not r.passed]
            summary = f"Indication failed: {', '.join(failures)}."

        return PhaseResult(
            phase="indication",
            passed=phase_passed,
            score=score,
            rules=rules,
            summary=summary,
        )

    def _check_impulse_size(
        self,
        price: float,
        high: Optional[float],
        low: Optional[float],
        min_impulse: float,
        symbol: str,
    ) -> RuleResult:
        """
        Check whether the candle or move is large enough to qualify as a real impulse.
        Uses the candle range (high - low) if available.
        """
        if high is not None and low is not None and high > 0 and low > 0:
            candle_range = high - low
            passed = candle_range >= min_impulse
            return RuleResult(
                passed=passed,
                rule_id="ind_impulse_size",
                label="Impulse size sufficient",
                message=(
                    f"Candle range {candle_range:.4f} exceeds minimum {min_impulse}."
                    if passed
                    else f"Candle range {candle_range:.4f} is below minimum impulse of {min_impulse}. "
                         f"Move may be too small to be meaningful."
                ),
                score=20 if passed else 5,
                max_score=20,
                is_blocking=False,
            )

        # No OHLC data — cannot verify impulse size
        return RuleResult(
            passed=True,
            rule_id="ind_impulse_size",
            label="Impulse size sufficient",
            message="No OHLC data available to verify impulse size. Proceeding unverified.",
            score=10,
            max_score=20,
            is_blocking=False,
        )

    def _check_htf_alignment(self, direction: str, htf_bias: Optional[str]) -> RuleResult:
        """
        Check if the indication aligns with the higher timeframe bias.
        Countertrend trades still pass but receive a lower score.
        """
        if not htf_bias or htf_bias == "neutral":
            return RuleResult(
                passed=True,
                rule_id="ind_htf_alignment",
                label="HTF bias alignment",
                message="HTF bias is neutral or unknown. No alignment bonus or penalty.",
                score=5,
                max_score=10,
                is_blocking=False,
            )

        is_aligned = (
            (direction == "bullish" and htf_bias == "bullish") or
            (direction == "bearish" and htf_bias == "bearish")
        )

        if is_aligned:
            return RuleResult(
                passed=True,
                rule_id="ind_htf_alignment",
                label="HTF bias alignment",
                message=f"Indication direction ({direction}) aligns with HTF bias ({htf_bias}). +10 pts.",
                score=10,
                max_score=10,
                is_blocking=False,
            )
        else:
            return RuleResult(
                passed=True,   # Still passes — countertrend allowed, just penalized
                rule_id="ind_htf_alignment",
                label="HTF bias alignment",
                message=(
                    f"COUNTERTREND: Indication is {direction} but HTF bias is {htf_bias}. "
                    f"Score reduced. Extra caution required."
                ),
                score=0,
                max_score=10,
                is_blocking=False,
            )

    @staticmethod
    def get_detected_type(signal_data: Dict[str, Any]) -> Optional[str]:
        """Helper to extract the detected indication type from a signal."""
        return signal_data.get("indication_type")
