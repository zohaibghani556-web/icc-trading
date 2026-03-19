"""
services/icc_engine/evaluator.py — Master ICC Evaluator

This is the conductor. It runs all four ICC phases in order and
combines their results into a single ICCResult with a verdict, score,
and full human-readable explanation.

The logic is deterministic and explicit — no black boxes.
Every decision is traceable to a specific rule.
"""

from typing import Dict, Any, Optional
from app.services.icc_engine.environment import EnvironmentFilter
from app.services.icc_engine.indication import IndicationScorer
from app.services.icc_engine.correction import CorrectionScorer
from app.services.icc_engine.continuation import ContinuationScorer
from app.services.icc_engine.risk import RiskRules
from app.services.icc_engine.result import ICCResult, PhaseResult


# ── How much each phase contributes to the final confidence score ─────────
# Adjust these weights to change what matters most to your overall score.
PHASE_WEIGHTS = {
    "environment":   0.10,   # 10% — gate, not scored heavily
    "indication":    0.30,   # 30% — most important signal
    "correction":    0.30,   # 30% — quality of entry zone
    "continuation":  0.25,   # 25% — confirmation of resumption
    "risk":          0.05,   # 5%  — usually pass/fail binary
}


class ICCEvaluator:
    """
    Orchestrates the complete ICC evaluation.

    Usage:
        evaluator = ICCEvaluator()
        result = evaluator.evaluate(signal_data, config, account_state)
    """

    def __init__(self):
        self.environment = EnvironmentFilter()
        self.indication = IndicationScorer()
        self.correction = CorrectionScorer()
        self.continuation = ContinuationScorer()
        self.risk = RiskRules()

    def evaluate(
        self,
        signal_data: Dict[str, Any],
        config: Dict[str, Any],
        account_state: Optional[Dict[str, Any]] = None,
    ) -> ICCResult:
        """
        Run the full ICC evaluation pipeline.

        Pipeline order:
        1. Environment — is it safe to trade?
        2. Indication — is there a directional signal?
        3. Correction — did price pull back appropriately?
        4. Continuation — is there a trigger confirming resumption?
        5. Risk — does this trade fit within our risk rules?

        The verdict is determined by:
        - "valid_trade"   → All phases pass (no blocking failures)
        - "watch_only"    → Environment + Indication pass, but Correction or Continuation is incomplete
        - "invalid_setup" → Any blocking failure in any phase
        """

        # ── Phase 1: Environment ──────────────────────────────────────────
        env_result = self.environment.evaluate(signal_data, config)

        # Hard stop if environment blocks — don't waste time on rest
        if not env_result.passed and env_result.blocking_failures:
            return self._build_result(
                verdict="invalid_setup",
                environment=env_result,
                signal_data=signal_data,
                config=config,
            )

        # ── Phase 2: Indication ───────────────────────────────────────────
        ind_result = self.indication.evaluate(signal_data, config)

        # ── Phase 3: Correction ───────────────────────────────────────────
        corr_result = self.correction.evaluate(signal_data, config)

        # ── Phase 4: Continuation ─────────────────────────────────────────
        cont_result = self.continuation.evaluate(signal_data, config)

        # ── Phase 5: Risk ─────────────────────────────────────────────────
        risk_result = self.risk.evaluate(signal_data, config, account_state)

        # ── Determine verdict ─────────────────────────────────────────────
        verdict = self._determine_verdict(
            env_result, ind_result, corr_result, cont_result, risk_result
        )

        return self._build_result(
            verdict=verdict,
            environment=env_result,
            indication=ind_result,
            correction=corr_result,
            continuation=cont_result,
            risk=risk_result,
            signal_data=signal_data,
            config=config,
        )

    def _determine_verdict(
        self,
        env: PhaseResult,
        ind: PhaseResult,
        corr: PhaseResult,
        cont: PhaseResult,
        risk: PhaseResult,
    ) -> str:
        """
        The verdict decision logic. Explicit rules, no ambiguity.

        invalid_setup: any blocking failure in any phase
        valid_trade: all phases pass (no blocking failures anywhere)
        watch_only: environment + indication pass, but correction/continuation incomplete
        """
        all_phases = [env, ind, corr, cont, risk]

        # Any blocking failure anywhere = invalid
        for phase in all_phases:
            if phase.blocking_failures:
                return "invalid_setup"

        # All phases fully passed = valid trade
        if all(p.passed for p in all_phases):
            return "valid_trade"

        # Environment and indication passed, but correction/continuation not complete
        if env.passed and ind.passed:
            return "watch_only"

        return "invalid_setup"

    def _build_result(
        self,
        verdict: str,
        signal_data: Dict[str, Any],
        config: Dict[str, Any],
        environment: Optional[PhaseResult] = None,
        indication: Optional[PhaseResult] = None,
        correction: Optional[PhaseResult] = None,
        continuation: Optional[PhaseResult] = None,
        risk: Optional[PhaseResult] = None,
    ) -> ICCResult:
        """Build the final ICCResult from all phase results."""

        # ── Compute confidence score (weighted average of phase scores) ───
        confidence = self._compute_confidence(
            environment, indication, correction, continuation, risk
        )

        # ── Detect countertrend ───────────────────────────────────────────
        direction = signal_data.get("direction", "")
        htf_bias = signal_data.get("htf_bias", "")
        is_countertrend = (
            (direction == "bullish" and htf_bias == "bearish") or
            (direction == "bearish" and htf_bias == "bullish")
        )
        has_htf_alignment = (
            (direction == "bullish" and htf_bias == "bullish") or
            (direction == "bearish" and htf_bias == "bearish")
        )

        # ── Apply countertrend penalty ────────────────────────────────────
        if is_countertrend:
            penalty = config.get("countertrend_score_penalty", 20) / 100
            confidence = max(0.0, confidence - penalty)

        # ── Extract detected components ───────────────────────────────────
        indication_type = signal_data.get("indication_type")
        correction_zone = signal_data.get("correction_zone_type")
        continuation_trigger = signal_data.get("continuation_trigger_type")

        # ── Extract trade levels ──────────────────────────────────────────
        entry = signal_data.get("entry_price")
        stop = signal_data.get("stop_price")
        target = signal_data.get("target_price")

        rr = None
        if entry and stop and target:
            risk_pts = abs(entry - stop)
            reward_pts = abs(target - entry)
            if risk_pts > 0:
                rr = round(reward_pts / risk_pts, 2)

        # ── Build score breakdown for UI ──────────────────────────────────
        score_breakdown = {}
        for phase_name, phase_result in [
            ("environment", environment),
            ("indication", indication),
            ("correction", correction),
            ("continuation", continuation),
            ("risk", risk),
        ]:
            if phase_result:
                score_breakdown[phase_name] = {
                    "score": phase_result.score,
                    "passed": phase_result.passed,
                    "summary": phase_result.summary,
                    "weight": PHASE_WEIGHTS.get(phase_name, 0.2),
                    "rules": [
                        {
                            "id": r.rule_id,
                            "label": r.label,
                            "passed": r.passed,
                            "message": r.message,
                            "score": r.score,
                            "max_score": r.max_score,
                            "is_blocking": r.is_blocking,
                        }
                        for r in phase_result.rules
                    ],
                }

        # ── Assemble result ───────────────────────────────────────────────
        result = ICCResult(
            verdict=verdict,
            confidence_score=round(confidence, 3),
            is_countertrend=is_countertrend,
            has_htf_alignment=has_htf_alignment,
            environment=environment,
            indication=indication,
            correction=correction,
            continuation=continuation,
            risk=risk,
            indication_type=indication_type,
            correction_zone_type=correction_zone,
            continuation_trigger_type=continuation_trigger,
            entry_price=entry if verdict == "valid_trade" else None,
            stop_price=stop if verdict == "valid_trade" else None,
            target_price=target if verdict == "valid_trade" else None,
            risk_reward=rr if verdict == "valid_trade" else None,
            score_breakdown=score_breakdown,
        )

        # Generate the full explanation dict
        result.explanation = result.to_explanation_dict()

        return result

    def _compute_confidence(
        self,
        environment: Optional[PhaseResult],
        indication: Optional[PhaseResult],
        correction: Optional[PhaseResult],
        continuation: Optional[PhaseResult],
        risk: Optional[PhaseResult],
    ) -> float:
        """
        Compute weighted confidence score from all phase scores.
        Returns a value between 0.0 and 1.0.
        """
        phases = {
            "environment": environment,
            "indication": indication,
            "correction": correction,
            "continuation": continuation,
            "risk": risk,
        }

        weighted_sum = 0.0
        total_weight = 0.0

        for phase_name, phase_result in phases.items():
            weight = PHASE_WEIGHTS.get(phase_name, 0.2)
            if phase_result is not None:
                weighted_sum += (phase_result.score / 100) * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight
