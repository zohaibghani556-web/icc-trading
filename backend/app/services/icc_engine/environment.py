"""
services/icc_engine/environment.py — Environment Filter

FIXES:
  - Accepts Pine Script session names (ny_open, london, ny_mid, ny_power, premarket)
  - Symbol check accepts exchange-prefixed symbols (CME_MINI:NQ1! → NQ1!)
  - More permissive defaults so real signals aren't silently blocked
"""

from typing import Dict, Any, Optional
from datetime import datetime, time

from app.services.icc_engine.result import PhaseResult, RuleResult
from app.core.config import settings


# ── All known session names (Pine Script + backend format) ────────────────
# Pine Script sends: london, ny_open, ny_mid, ny_power, premarket, asia, globex
# Backend config may use: us_regular, us_premarket, globex, london, asia
ALL_ACTIVE_SESSIONS = {
    # Pine Script names
    "ny_open", "ny_mid", "ny_power", "london", "premarket", "asia", "globex",
    # Backend names
    "us_regular", "us_premarket", "us_afterhours",
}

# Pine session → backend session mapping
PINE_TO_BACKEND = {
    "ny_open":   "us_regular",
    "ny_mid":    "us_regular",
    "ny_power":  "us_regular",
    "premarket": "us_premarket",
    "london":    "london",
    "asia":      "asia",
    "globex":    "globex",
}

# Which sessions are "prime" trading hours — used for scoring bonus
PRIME_SESSIONS = {"ny_open", "ny_power", "london", "us_regular"}

# Supported base symbols (without exchange prefix)
SUPPORTED_BASE_SYMBOLS = {
    "ES1!", "MES1!", "NQ1!", "MNQ1!",
    "YM1!", "MYM1!", "CL1!", "MCL1!",
    "GC1!", "MGC1!",
}


def normalize_symbol(symbol: str) -> str:
    """Strip exchange prefix. 'CME_MINI:NQ1!' → 'NQ1!'"""
    if ":" in symbol:
        return symbol.split(":", 1)[1]
    return symbol


def session_is_allowed(session: str, allowed_sessions: list) -> bool:
    """
    Check if a session is allowed, accounting for Pine Script naming vs backend naming.
    """
    if not session:
        return True  # no session info = don't block

    # Direct match
    if session in allowed_sessions:
        return True

    # Map Pine name to backend name and check
    backend_name = PINE_TO_BACKEND.get(session.lower())
    if backend_name and backend_name in allowed_sessions:
        return True

    # If allowed_sessions contains 'us_regular', also allow Pine's ny_* sessions
    if "us_regular" in allowed_sessions and session in ("ny_open", "ny_mid", "ny_power"):
        return True

    # If allowed_sessions contains 'us_premarket', allow Pine's 'premarket'
    if "us_premarket" in allowed_sessions and session == "premarket":
        return True

    return False


class EnvironmentFilter:
    """
    Checks whether market conditions are appropriate for trading.
    Updated to handle Pine Script session names and exchange-prefixed symbols.
    """

    def evaluate(
        self,
        signal_data: Dict[str, Any],
        config: Dict[str, Any],
    ) -> PhaseResult:
        rules = []
        total_score = 0
        max_possible = 0

        symbol = signal_data.get("symbol", "")
        session = signal_data.get("session", "")
        htf_bias = signal_data.get("htf_bias", "")

        # ── Rule 1: Symbol check ──────────────────────────────────────────
        symbol_rule = self._check_symbol(symbol)
        rules.append(symbol_rule)
        total_score += symbol_rule.score
        max_possible += symbol_rule.max_score

        # ── Rule 2: Session check ─────────────────────────────────────────
        allowed_sessions = config.get("allowed_sessions", list(ALL_ACTIVE_SESSIONS))
        session_rule = self._check_session(session, allowed_sessions)
        rules.append(session_rule)
        total_score += session_rule.score
        max_possible += session_rule.max_score

        # ── Rule 3: HTF bias ──────────────────────────────────────────────
        htf_rule = self._check_htf_bias(
            htf_bias,
            config.get("require_htf_bias", False),
        )
        rules.append(htf_rule)
        total_score += htf_rule.score
        max_possible += htf_rule.max_score

        has_blocking_failure = any(r.is_blocking and not r.passed for r in rules)
        phase_passed = not has_blocking_failure

        score = int((total_score / max_possible) * 100) if max_possible > 0 else 0

        if phase_passed:
            summary = f"Environment clear. Session: {session}. Symbol: {symbol}."
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
        """Accept both raw and exchange-prefixed symbols."""
        base = normalize_symbol(symbol)
        passed = base in SUPPORTED_BASE_SYMBOLS

        if passed:
            return RuleResult(
                passed=True,
                rule_id="env_symbol_check",
                label="Symbol allowed",
                message=f"{symbol} → {base} is on the approved list.",
                score=25, max_score=25, is_blocking=True,
            )

        # Unknown symbol — warn but don't hard-block (allows new instruments)
        print(f"[ENV] Unknown symbol '{symbol}' (base: '{base}') — allowing with reduced score")
        return RuleResult(
            passed=True,
            rule_id="env_symbol_check",
            label="Symbol allowed",
            message=f"Symbol '{symbol}' not in standard list, but proceeding. Add to SUPPORTED_BASE_SYMBOLS if legitimate.",
            score=10, max_score=25, is_blocking=False,
        )

    def _check_session(self, session: Optional[str], allowed_sessions: list) -> RuleResult:
        """Check session with Pine Script name awareness."""
        if not session:
            return RuleResult(
                passed=True,
                rule_id="env_session_check",
                label="Session allowed",
                message="No session info. Proceeding without session validation.",
                score=15, max_score=35, is_blocking=False,
            )

        allowed = session_is_allowed(session, allowed_sessions)
        is_prime = session in PRIME_SESSIONS

        if allowed:
            return RuleResult(
                passed=True,
                rule_id="env_session_check",
                label="Session allowed",
                message=f"Session '{session}' is allowed. {'Prime session — full score.' if is_prime else ''}",
                score=35 if is_prime else 25,
                max_score=35, is_blocking=False,
            )

        return RuleResult(
            passed=False,
            rule_id="env_session_check",
            label="Session allowed",
            message=f"Session '{session}' not in allowed list: {allowed_sessions}. Mapped backend name: {PINE_TO_BACKEND.get(session, 'unknown')}.",
            score=0, max_score=35, is_blocking=True,
        )

    def _check_htf_bias(self, htf_bias: Optional[str], require_htf_bias: bool) -> RuleResult:
        if htf_bias and htf_bias in ("bullish", "bearish"):
            return RuleResult(
                passed=True,
                rule_id="env_htf_bias",
                label="HTF bias available",
                message=f"Higher timeframe bias is {htf_bias}.",
                score=40, max_score=40, is_blocking=False,
            )

        if htf_bias == "neutral":
            return RuleResult(
                passed=True,
                rule_id="env_htf_bias",
                label="HTF bias available",
                message="HTF bias is neutral. Reduced confidence.",
                score=15, max_score=40, is_blocking=False,
            )

        if require_htf_bias:
            return RuleResult(
                passed=False,
                rule_id="env_htf_bias",
                label="HTF bias available",
                message="No HTF bias provided. Required by config.",
                score=0, max_score=40, is_blocking=False,
            )

        return RuleResult(
            passed=True,
            rule_id="env_htf_bias",
            label="HTF bias available",
            message="No HTF bias. Proceeding without bias check.",
            score=20, max_score=40, is_blocking=False,
        )
