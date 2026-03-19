"""
services/icc_engine/result.py — ICC evaluation result types

These dataclasses represent what the ICC engine outputs.
Every evaluation produces an ICCResult with full explanations.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class RuleResult:
    """
    The result of evaluating a single rule.

    passed:   did this rule pass?
    rule_id:  short identifier (e.g. "env_session_check")
    label:    human-readable name
    message:  explanation of why it passed or failed
    score:    points awarded (0 to max_score)
    max_score: maximum possible points for this rule
    """
    passed: bool
    rule_id: str
    label: str
    message: str
    score: int = 0
    max_score: int = 0
    is_blocking: bool = False  # if True, failure invalidates the whole setup


@dataclass
class PhaseResult:
    """
    Aggregated result for one ICC phase (Environment, Indication, Correction, Continuation, Risk).
    """
    phase: str              # "environment" / "indication" / "correction" / "continuation" / "risk"
    passed: bool
    score: int              # 0 to 100
    rules: List[RuleResult] = field(default_factory=list)
    summary: str = ""       # one-sentence summary of this phase

    @property
    def passed_rules(self) -> List[RuleResult]:
        return [r for r in self.rules if r.passed]

    @property
    def failed_rules(self) -> List[RuleResult]:
        return [r for r in self.rules if not r.passed]

    @property
    def blocking_failures(self) -> List[RuleResult]:
        return [r for r in self.rules if not r.passed and r.is_blocking]


@dataclass
class ICCResult:
    """
    The complete output of an ICC evaluation.

    verdict options:
      "valid_trade"   → Enter. All ICC criteria met.
      "watch_only"    → Monitor. Partial criteria, not enough to enter.
      "invalid_setup" → Skip. Failed blocking rules.
    """
    verdict: str                          # valid_trade / watch_only / invalid_setup
    confidence_score: float               # 0.0 to 1.0
    is_countertrend: bool = False
    has_htf_alignment: bool = False

    # Phase results
    environment: Optional[PhaseResult] = None
    indication: Optional[PhaseResult] = None
    correction: Optional[PhaseResult] = None
    continuation: Optional[PhaseResult] = None
    risk: Optional[PhaseResult] = None

    # Detected setup components
    indication_type: Optional[str] = None
    correction_zone_type: Optional[str] = None
    continuation_trigger_type: Optional[str] = None

    # Trade levels (populated if verdict = valid_trade)
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    risk_reward: Optional[float] = None
    invalidation_level: Optional[float] = None

    # Score breakdown per phase (for the UI)
    score_breakdown: Dict[str, Any] = field(default_factory=dict)

    # Human-readable explanation block
    explanation: Dict[str, Any] = field(default_factory=dict)

    def to_explanation_dict(self) -> Dict[str, Any]:
        """
        Builds the full explanation text that gets stored and shown in the UI.
        This is what the trader reads to understand why a setup passed or failed.
        """
        phases = [self.environment, self.indication, self.correction, self.continuation, self.risk]

        passed = []
        failed = []
        warnings = []

        for phase in phases:
            if phase is None:
                continue
            for rule in phase.rules:
                if rule.passed:
                    passed.append(f"✅ [{phase.phase.upper()}] {rule.label}: {rule.message}")
                else:
                    if rule.is_blocking:
                        failed.append(f"🚫 [{phase.phase.upper()}] {rule.label}: {rule.message}")
                    else:
                        warnings.append(f"⚠️ [{phase.phase.upper()}] {rule.label}: {rule.message}")

        # Generate a plain-English summary paragraph
        if self.verdict == "valid_trade":
            summary = (
                f"VALID TRADE. All ICC criteria met. "
                f"Confidence: {self.confidence_score:.0%}. "
                f"{'HTF aligned. ' if self.has_htf_alignment else ''}"
                f"{'COUNTERTREND — reduced score. ' if self.is_countertrend else ''}"
            )
        elif self.verdict == "watch_only":
            blocking = [r.label for p in phases if p for r in p.blocking_failures]
            summary = (
                f"WATCH ONLY. Partial ICC setup. "
                f"Missing: {', '.join(blocking) if blocking else 'some criteria'}. "
                f"Monitor for completion."
            )
        else:
            blocking = [r.label for p in phases if p for r in p.blocking_failures]
            summary = (
                f"INVALID SETUP. Blocked by: {', '.join(blocking) if blocking else 'rule failures'}. "
                f"Do not enter."
            )

        return {
            "verdict": self.verdict,
            "summary": summary,
            "confidence": self.confidence_score,
            "passed_rules": passed,
            "failed_rules": failed,
            "warnings": warnings,
            "phase_summaries": {
                p.phase: {"passed": p.passed, "score": p.score, "summary": p.summary}
                for p in phases if p is not None
            },
            "suggested_review_note": self._suggest_review_note(),
        }

    def _suggest_review_note(self) -> str:
        """
        Generates a suggested post-trade review note based on what the engine found.
        """
        if self.verdict == "invalid_setup":
            return "Setup did not qualify. Review which phase failed and whether market conditions were appropriate."
        if self.is_countertrend:
            return "Countertrend setup — extra caution required. Confirm HTF bias before considering."
        if self.confidence_score < 0.6:
            return "Low confidence setup. Consider waiting for stronger signal before entering."
        if self.verdict == "valid_trade" and self.confidence_score >= 0.8:
            return "High-confidence setup. Execute with full size according to risk rules."
        return "Moderate setup. Execute with standard size and monitor closely."
