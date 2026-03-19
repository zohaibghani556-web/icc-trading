"""
services/icc_engine/environment.py — Environment Filter

This module answers the question: "Is conditions right to even look at setups?"

The environment filter runs FIRST. If it fails, no ICC evaluation happens.
Think of it as a pre-flight checklist before you even consider a trade.
"""

from typing import Dict, Any, Optional
from datetime import datetime, time

from app.services.icc_engine.result import PhaseResult, RuleResult
from app.core.config import settings


# ── Known trading sessions ─────────────────────────────────────────────────
SESSION_HOURS_UTC = {
    "us_premarket": (time(8, 0), time(13, 30)),      # 8:00-9:30 AM ET
    "us_regular": (time(13, 30), time(20, 0)),        # 9:30 AM-4:00 PM ET
    "us_afterhours": (time(20, 0), time(21, 0)),
    "globex": (time(23, 0), time(22, 0)),             # nearly 24h
    "london": (time(7, 0), time(15, 30)),
    "asia": (time(0, 0), time(8, 0)),
}

# ── Symbol metadata: minimum tick size, standard daily range ───────────────
SYMBOL_SPECS = {
    "ES1!":  {"min_volume": 50000, "typical_spread": 0.25},
    "MES1!": {"min_volume": 10000, "typical_spread": 0.25},
    "NQ1!":  {"min_volume": 30000, "typical_spread": 0.25},
    "MNQ1!": {"min_volume": 5000,  "typical_spread": 0.25},
    "YM1!":  {"min_volume": 20000, "typical_spread": 1.0},
    "MYM1!": {"min_volume": 3000,  "typical_spread": 1.0},
    "CL1!":  {"min_volume": 15000, "typical_spread": 0.01},
    "MCL1!": {"min_volume": 2000,  "typical_spread": 0.01},
    "GC1!":  {"min_volume": 8000,  "typical_spread": 0.10},
    "MGC1!": {"min_volume": 1000,  "typical_spread": 0.10},
}


class EnvironmentFilter:
    """
    Checks whether market conditions are appropriate for trading.

    All rules here are binary go/no-go checks. Any blocking failure
    stops the evaluation immediately.
    """

    def evaluate(
        self,
        signal_data: Dict[str, Any],
        config: Dict[str, Any],
    ) -> PhaseResult:
        """
        Run all environment checks against the signal.

        Args:
            signal_data: Normalized signal dictionary
            config: Active ICC configuration settings

        Returns:
            PhaseResult with pass/fail for each environment rule
        """
        rules = []
        total_score = 0
        max_possible = 0

        # ── Rule 1: Symbol is on the allowed list ──────────────────────────
        symbol_rule = self._check_symbol(signal_data.get("symbol", ""))
        rules.append(symbol_rule)
        total_score += symbol_rule.score
        max_possible += symbol_rule.max_score

        # ── Rule 2: Session is allowed ─────────────────────────────────────
        session_rule = self._check_session(
            signal_data.get("session"),
            signal_data.get("signal_timestamp"),
            config.get("allowed_sessions", settings.ALLOWED_SESSIONS),
        )
        rules.append(session_rule)
        total_score += session_rule.score
        max_possible += session_rule.max_score

        # ── Rule 3: Higher timeframe bias is determinable ──────────────────
        htf_rule = self._check_htf_bias(
            signal_data.get("htf_bias"),
            config.get("require_htf_bias", True),
        )
        rules.append(htf_rule)
        total_score += htf_rule.score
        max_possible += htf_rule.max_score

        # ── Determine if any blocking rule failed ─────────────────────────
        has_blocking_failure = any(r.is_blocking and not r.passed for r in rules)
        phase_passed = not has_blocking_failure

        # ── Calculate score as percentage ─────────────────────────────────
        score = int((total_score / max_possible) * 100) if max_possible > 0 else 0

        # ── Build summary sentence ─────────────────────────────────────────
        if phase_passed:
            session = signal_data.get("session", "unknown")
            summary = f"Environment clear. Session: {session}. Symbol allowed."
        else:
            failures = [r.label for r in rules if r.is_blocking and not r.passed]
            summary = f"Environment blocked: {', '.join(failures)}."

        return PhaseResult(
            phase="environment",
            passed=phase_passed,
            score=score,
            rules=rules,
            summary=summary,
        )

    def _check_symbol(self, symbol: str) -> RuleResult:
        """Is this symbol on our approved list?"""
        allowed = settings.ALLOWED_SYMBOLS
        passed = symbol in allowed

        return RuleResult(
            passed=passed,
            rule_id="env_symbol_check",
            label="Symbol allowed",
            message=(
                f"{symbol} is on the approved list."
                if passed
                else f"{symbol} is not in the approved symbols list: {', '.join(allowed)}"
            ),
            score=25 if passed else 0,
            max_score=25,
            is_blocking=True,  # Unknown symbol → always block
        )

    def _check_session(
        self,
        session: Optional[str],
        timestamp: Optional[Any],
        allowed_sessions: list,
    ) -> RuleResult:
        """Is this signal occurring during an approved trading session?"""

        if session and session in allowed_sessions:
            return RuleResult(
                passed=True,
                rule_id="env_session_check",
                label="Session allowed",
                message=f"Session '{session}' is in the approved session list.",
                score=35,
                max_score=35,
                is_blocking=True,
            )

        # If no session provided, try to infer from timestamp
        if timestamp:
            try:
                dt = datetime.fromisoformat(str(timestamp)) if isinstance(timestamp, str) else timestamp
                current_time = dt.time()

                for session_name, (start, end) in SESSION_HOURS_UTC.items():
                    if session_name in allowed_sessions:
                        # Handle sessions that cross midnight
                        if start > end:
                            if current_time >= start or current_time <= end:
                                return RuleResult(
                                    passed=True,
                                    rule_id="env_session_check",
                                    label="Session allowed",
                                    message=f"Time {current_time} falls within {session_name} session.",
                                    score=25,  # slightly lower score since inferred
                                    max_score=35,
                                    is_blocking=True,
                                )
                        else:
                            if start <= current_time <= end:
                                return RuleResult(
                                    passed=True,
                                    rule_id="env_session_check",
                                    label="Session allowed",
                                    message=f"Time {current_time} falls within {session_name} session.",
                                    score=25,
                                    max_score=35,
                                    is_blocking=True,
                                )
            except (ValueError, AttributeError):
                pass

        # If session is provided but not allowed
        if session:
            return RuleResult(
                passed=False,
                rule_id="env_session_check",
                label="Session allowed",
                message=f"Session '{session}' is not in allowed sessions: {', '.join(allowed_sessions)}",
                score=0,
                max_score=35,
                is_blocking=True,
            )

        # No session info at all — pass with warning (allow evaluation to continue)
        return RuleResult(
            passed=True,
            rule_id="env_session_check",
            label="Session allowed",
            message="No session info provided. Proceeding without session validation.",
            score=15,  # low score for missing info
            max_score=35,
            is_blocking=False,
        )

    def _check_htf_bias(
        self,
        htf_bias: Optional[str],
        require_htf_bias: bool,
    ) -> RuleResult:
        """Is there a determinable higher timeframe bias?"""

        if htf_bias and htf_bias in ("bullish", "bearish"):
            return RuleResult(
                passed=True,
                rule_id="env_htf_bias",
                label="HTF bias available",
                message=f"Higher timeframe bias is {htf_bias}.",
                score=40,
                max_score=40,
                is_blocking=False,
            )

        if htf_bias == "neutral":
            return RuleResult(
                passed=True,
                rule_id="env_htf_bias",
                label="HTF bias available",
                message="HTF bias is neutral. Trend-following setups have reduced edge.",
                score=15,
                max_score=40,
                is_blocking=False,
            )

        # No bias provided
        if require_htf_bias:
            return RuleResult(
                passed=False,
                rule_id="env_htf_bias",
                label="HTF bias available",
                message="No higher timeframe bias provided. Required by current config.",
                score=0,
                max_score=40,
                is_blocking=False,  # Warning, not a hard block
            )

        return RuleResult(
            passed=True,
            rule_id="env_htf_bias",
            label="HTF bias available",
            message="No HTF bias provided. Proceeding without bias alignment check.",
            score=20,
            max_score=40,
            is_blocking=False,
        )
