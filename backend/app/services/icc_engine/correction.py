"""
services/icc_engine/correction.py — Correction Phase Scorer

This module evaluates the "C" (first C) in ICC: the pullback after the initial move.

A valid correction must:
1. Pull back into a recognized zone (FVG, OB, prior level, VWAP, etc.)
2. Retrace a meaningful but not excessive amount (not too shallow, not too deep)
3. Be orderly — not impulsive in the opposite direction (that's a reversal, not a correction)
4. Not break the structure that the indication created

Think of this as: "Did price come back to offer you a good entry area?"
"""

from typing import Dict, Any, Optional
from app.services.icc_engine.result import PhaseResult, RuleResult


# ── Correction zone types and their quality scores ────────────────────────
# Higher score = more reliable zone with more institutional backing
CORRECTION_ZONE_QUALITY = {
    "fair_value_gap":        90,   # FVG / imbalance — strong institutional zone
    "order_block":           85,   # OB — area of prior institutional activity
    "breaker_block":         80,   # Failed OB that flips polarity
    "prior_breakout_level":  75,   # Prior resistance becomes support (or vice versa)
    "vwap":                  70,   # VWAP — intraday mean reversion area
    "anchored_vwap":         75,   # AVWAP from key anchor point
    "discount_zone":         65,   # Below 50% of the range (for longs)
    "premium_zone":          65,   # Above 50% of the range (for shorts)
    "fibonacci_zone":        70,   # 38.2-61.8% fib retracement
    "supply_demand_zone":    75,   # S/D zone from prior consolidation
    "ema_zone":              60,   # EMA cluster (8/21/50)
    "structure_level":       70,   # Previous swing high/low acting as support
}

DEFAULT_ZONE_QUALITY = 50


class CorrectionScorer:
    """
    Evaluates whether price is in a valid correction after the indication.

    The Correction is what separates a good ICC entry from chasing.
    We want price to come back to offer value — not enter at the extension.
    """

    def evaluate(
        self,
        signal_data: Dict[str, Any],
        config: Dict[str, Any],
    ) -> PhaseResult:
        """
        Score the Correction phase.

        Args:
            signal_data: Normalized signal dictionary (may include correction zone data)
            config: Active ICC configuration settings

        Returns:
            PhaseResult with pass/fail and score for Correction
        """
        rules = []
        total_score = 0
        max_possible = 0

        signal_type = signal_data.get("signal_type", "")
        correction_zone = signal_data.get("correction_zone_type", "")
        retracement_pct = signal_data.get("retracement_pct")  # 0.0 to 1.0
        is_orderly = signal_data.get("correction_is_orderly", True)  # assume orderly if not specified

        min_ret = config.get("min_retracement_pct", 0.236)
        max_ret = config.get("max_retracement_pct", 0.618)
        require_zone = config.get("require_correction_zone", True)
        allowed_zones = config.get("allowed_correction_zones", list(CORRECTION_ZONE_QUALITY.keys()))

        # ── Rule 1: A correction signal is present ─────────────────────────
        # Corrections come from explicit "correction" signals OR are inferred
        # from the overall setup context when signal_type = "setup_complete"
        correction_present = signal_type in ("correction", "setup_complete", "continuation")
        correction_rule = RuleResult(
            passed=correction_present,
            rule_id="corr_signal_present",
            label="Correction phase present",
            message=(
                "Correction phase detected in signal context."
                if correction_present
                else f"Signal type '{signal_type}' does not include a correction phase."
            ),
            score=20 if correction_present else 0,
            max_score=20,
            is_blocking=False,  # If no correction yet, this is watch_only territory
        )
        rules.append(correction_rule)
        total_score += correction_rule.score
        max_possible += correction_rule.max_score

        # ── Rule 2: Correction zone type is recognized ─────────────────────
        zone_rule = self._check_zone_quality(
            correction_zone,
            allowed_zones,
            require_zone,
        )
        rules.append(zone_rule)
        total_score += zone_rule.score
        max_possible += zone_rule.max_score

        # ── Rule 3: Retracement depth is within acceptable range ──────────
        depth_rule = self._check_retracement_depth(
            retracement_pct,
            min_ret,
            max_ret,
        )
        rules.append(depth_rule)
        total_score += depth_rule.score
        max_possible += depth_rule.max_score

        # ── Rule 4: Correction is orderly (not an impulsive reversal) ─────
        order_rule = self._check_correction_quality(is_orderly)
        rules.append(order_rule)
        total_score += order_rule.score
        max_possible += order_rule.max_score

        # ── Determine pass/fail ───────────────────────────────────────────
        has_blocking_failure = any(r.is_blocking and not r.passed for r in rules)
        phase_passed = not has_blocking_failure and correction_present

        score = int((total_score / max_possible) * 100) if max_possible > 0 else 0

        # ── Build summary ─────────────────────────────────────────────────
        if phase_passed:
            zone_str = correction_zone or "unspecified zone"
            depth_str = f"{retracement_pct:.1%}" if retracement_pct else "unknown depth"
            summary = f"Correction valid. Zone: {zone_str}. Depth: {depth_str}."
        elif not correction_present:
            summary = "No correction yet. Waiting for pullback to develop."
        else:
            failures = [r.label for r in rules if r.is_blocking and not r.passed]
            summary = f"Correction invalid: {', '.join(failures)}."

        return PhaseResult(
            phase="correction",
            passed=phase_passed,
            score=score,
            rules=rules,
            summary=summary,
        )

    def _check_zone_quality(
        self,
        zone_type: Optional[str],
        allowed_zones: list,
        require_zone: bool,
    ) -> RuleResult:
        """Check if the correction is landing in a recognized high-quality zone."""

        if zone_type and zone_type in CORRECTION_ZONE_QUALITY:
            quality = CORRECTION_ZONE_QUALITY[zone_type]
            in_allowed = zone_type in allowed_zones

            if in_allowed:
                return RuleResult(
                    passed=True,
                    rule_id="corr_zone_quality",
                    label="Correction zone recognized",
                    message=f"Zone type '{zone_type}' is valid. Quality: {quality}/100.",
                    score=int(quality * 0.4),
                    max_score=40,
                    is_blocking=False,
                )
            else:
                return RuleResult(
                    passed=False,
                    rule_id="corr_zone_quality",
                    label="Correction zone recognized",
                    message=f"Zone '{zone_type}' exists but is not in the allowed zones list.",
                    score=10,
                    max_score=40,
                    is_blocking=False,
                )

        if zone_type:
            return RuleResult(
                passed=True,
                rule_id="corr_zone_quality",
                label="Correction zone recognized",
                message=f"Zone type '{zone_type}' is unrecognized. Using default quality.",
                score=int(DEFAULT_ZONE_QUALITY * 0.4),
                max_score=40,
                is_blocking=False,
            )

        # No zone specified
        if require_zone:
            return RuleResult(
                passed=False,
                rule_id="corr_zone_quality",
                label="Correction zone recognized",
                message="No correction zone specified. Config requires a zone for entry.",
                score=0,
                max_score=40,
                is_blocking=True,
            )

        return RuleResult(
            passed=True,
            rule_id="corr_zone_quality",
            label="Correction zone recognized",
            message="No zone specified. Zone not required by current config.",
            score=15,
            max_score=40,
            is_blocking=False,
        )

    def _check_retracement_depth(
        self,
        retracement_pct: Optional[float],
        min_ret: float,
        max_ret: float,
    ) -> RuleResult:
        """
        Check that the correction retraced an appropriate amount.
        Too shallow = price never offered a real entry.
        Too deep = structure may be invalidated.
        """
        if retracement_pct is None:
            return RuleResult(
                passed=True,
                rule_id="corr_depth_check",
                label="Retracement depth valid",
                message="Retracement percentage not provided. Depth check skipped.",
                score=15,
                max_score=30,
                is_blocking=False,
            )

        too_shallow = retracement_pct < min_ret
        too_deep = retracement_pct > max_ret

        if too_shallow:
            return RuleResult(
                passed=False,
                rule_id="corr_depth_check",
                label="Retracement depth valid",
                message=(
                    f"Retracement {retracement_pct:.1%} is too shallow (minimum: {min_ret:.1%}). "
                    f"Price did not pull back enough to offer a quality entry."
                ),
                score=0,
                max_score=30,
                is_blocking=True,
            )

        if too_deep:
            return RuleResult(
                passed=False,
                rule_id="corr_depth_check",
                label="Retracement depth valid",
                message=(
                    f"Retracement {retracement_pct:.1%} is too deep (maximum: {max_ret:.1%}). "
                    f"Deep retracement may indicate structure invalidation, not correction."
                ),
                score=0,
                max_score=30,
                is_blocking=True,
            )

        # Sweet spot: between 38.2% and 50% gets bonus
        ideal = 0.382 <= retracement_pct <= 0.500
        return RuleResult(
            passed=True,
            rule_id="corr_depth_check",
            label="Retracement depth valid",
            message=(
                f"Retracement {retracement_pct:.1%} is in the ideal zone (38.2-50%)."
                if ideal
                else f"Retracement {retracement_pct:.1%} is valid (within {min_ret:.1%}-{max_ret:.1%})."
            ),
            score=30 if ideal else 22,
            max_score=30,
            is_blocking=False,
        )

    def _check_correction_quality(self, is_orderly: bool) -> RuleResult:
        """
        Is the pullback an orderly correction or an impulsive reversal?
        An impulsive reversal (large, fast candles against the trend) suggests
        the indication was wrong — this is not a correction, it's a reversal.
        """
        return RuleResult(
            passed=is_orderly,
            rule_id="corr_orderly_check",
            label="Correction is orderly",
            message=(
                "Pullback appears orderly. Not an impulsive reversal."
                if is_orderly
                else "Pullback appears impulsive (large candles against trend). "
                     "This may be a reversal, not a correction. Avoid entry."
            ),
            score=10 if is_orderly else 0,
            max_score=10,
            is_blocking=not is_orderly,
        )

    @staticmethod
    def get_detected_zone(signal_data: Dict[str, Any]) -> Optional[str]:
        """Helper to extract the detected correction zone from a signal."""
        return signal_data.get("correction_zone_type")
