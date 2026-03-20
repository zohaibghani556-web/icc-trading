"""
services/icc_engine/indication.py — Indication Phase Scorer

FIXES:
  - Added all Pine Script indication_type names to INDICATION_QUALITY dict
  - Pine sends: bos_high, bos_low, choch_bull, choch_bear, liq_sweep_bull,
    liq_sweep_bear, or_breakout_bull, or_breakout_bear, displacement_up, displacement_down
"""

from typing import Dict, Any, Optional
from app.services.icc_engine.result import PhaseResult, RuleResult


INDICATION_QUALITY = {
    # ── Backend canonical names ───────────────────────────────────────────
    "structure_break_high":      85,
    "structure_break_low":       85,
    "liquidity_sweep_reclaim":   90,
    "displacement_up":           80,
    "displacement_down":         80,
    "momentum_expansion":        70,
    "level_reclaim":             65,
    "market_structure_shift":    75,
    "order_flow_shift":          70,
    "breakout_with_volume":      80,

    # ── Pine Script names (what actually gets sent) ───────────────────────
    "bos_high":          85,   # Break of Structure — swing high
    "bos_low":           85,   # Break of Structure — swing low
    "choch_bull":        80,   # Change of Character bullish
    "choch_bear":        80,   # Change of Character bearish
    "liq_sweep_bull":    90,   # Liquidity sweep + reclaim (bullish)
    "liq_sweep_bear":    90,   # Liquidity sweep + reclaim (bearish)
    "or_breakout_bull":  80,   # Opening range breakout bull
    "or_breakout_bear":  80,   # Opening range breakout bear
    # displacement_up / displacement_down already covered above
}

DEFAULT_INDICATION_QUALITY = 60


class IndicationScorer:

    def evaluate(
        self,
        signal_data: Dict[str, Any],
        config: Dict[str, Any],
    ) -> PhaseResult:
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

        # ── Rule 1: Signal is an indication ───────────────────────────────
        is_indication = signal_type in ("indication", "setup_complete")
        indication_present_rule = RuleResult(
            passed=is_indication,
            rule_id="ind_signal_present",
            label="Indication signal received",
            message=(
                f"Signal type '{signal_type}' recognized as indication."
                if is_indication
                else f"Signal type '{signal_type}' is not an indication."
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
                phase="indication", passed=False, score=0, rules=rules,
                summary="No indication signal.",
            )

        # ── Rule 2: Indication type quality ───────────────────────────────
        type_quality = INDICATION_QUALITY.get(indication_type, DEFAULT_INDICATION_QUALITY)
        type_recognized = indication_type in INDICATION_QUALITY

        type_rule = RuleResult(
            passed=True,
            rule_id="ind_type_recognized",
            label="Indication type quality",
            message=(
                f"Type '{indication_type}' quality: {type_quality}/100."
                if type_recognized
                else f"Type '{indication_type}' unrecognized. Using default quality {DEFAULT_INDICATION_QUALITY}."
            ),
            score=int(type_quality * 0.4),
            max_score=40,
            is_blocking=False,
        )
        rules.append(type_rule)
        total_score += type_rule.score
        max_possible += type_rule.max_score

        # ── Rule 3: Impulse size ──────────────────────────────────────────
        impulse_rule = self._check_impulse_size(
            price, high, low,
            min_impulse=config.get("min_structure_break_points", 0.5),
            symbol=signal_data.get("symbol", ""),
        )
        rules.append(impulse_rule)
        total_score += impulse_rule.score
        max_possible += impulse_rule.max_score

        # ── Rule 4: HTF alignment ─────────────────────────────────────────
        alignment_rule = self._check_htf_alignment(direction, htf_bias)
        rules.append(alignment_rule)
        total_score += alignment_rule.score
        max_possible += alignment_rule.max_score

        has_blocking_failure = any(r.is_blocking and not r.passed for r in rules)
        phase_passed = not has_blocking_failure and indication_present_rule.passed
        score = int((total_score / max_possible) * 100) if max_possible > 0 else 0

        is_countertrend = (
            (direction == "bullish" and htf_bias == "bearish") or
            (direction == "bearish" and htf_bias == "bullish")
        )

        if phase_passed:
            ct_note = " (COUNTERTREND)" if is_countertrend else ""
            summary = f"Indication confirmed. Type: {indication_type or 'unspecified'}. Quality: {type_quality}/100.{ct_note}"
        else:
            failures = [r.label for r in rules if r.is_blocking and not r.passed]
            summary = f"Indication failed: {', '.join(failures)}."

        return PhaseResult(
            phase="indication", passed=phase_passed, score=score,
            rules=rules, summary=summary,
        )

    def _check_impulse_size(self, price, high, low, min_impulse, symbol) -> RuleResult:
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
                    else f"Candle range {candle_range:.4f} below minimum {min_impulse}."
                ),
                score=20 if passed else 5,
                max_score=20, is_blocking=False,
            )
        return RuleResult(
            passed=True, rule_id="ind_impulse_size",
            label="Impulse size sufficient",
            message="No OHLC data. Proceeding unverified.",
            score=10, max_score=20, is_blocking=False,
        )

    def _check_htf_alignment(self, direction, htf_bias) -> RuleResult:
        if not htf_bias or htf_bias == "neutral":
            return RuleResult(
                passed=True, rule_id="ind_htf_alignment",
                label="HTF bias alignment",
                message="HTF bias neutral. No alignment bonus.",
                score=5, max_score=10, is_blocking=False,
            )

        is_aligned = (
            (direction == "bullish" and htf_bias == "bullish") or
            (direction == "bearish" and htf_bias == "bearish")
        )

        if is_aligned:
            return RuleResult(
                passed=True, rule_id="ind_htf_alignment",
                label="HTF bias alignment",
                message=f"Direction ({direction}) aligns with HTF bias ({htf_bias}). +10 pts.",
                score=10, max_score=10, is_blocking=False,
            )

        return RuleResult(
            passed=True, rule_id="ind_htf_alignment",
            label="HTF bias alignment",
            message=f"COUNTERTREND: {direction} vs HTF {htf_bias}. Score reduced.",
            score=0, max_score=10, is_blocking=False,
        )

    @staticmethod
    def get_detected_type(signal_data: Dict[str, Any]) -> Optional[str]:
        return signal_data.get("indication_type")
