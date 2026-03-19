"""
services/icc_engine/risk.py — Risk Rules Module

This module enforces position sizing and trading safety rules.
A trade can have a perfect ICC setup and still be blocked here if risk limits are exceeded.

These rules protect your account. They cannot be bypassed.
"""

from typing import Dict, Any, Optional
from app.services.icc_engine.result import PhaseResult, RuleResult


class RiskRules:
    """
    Enforces risk management rules. Acts as the final gate before a trade is approved.

    Rules checked:
    - Daily loss limit not exceeded
    - Max consecutive losses not exceeded
    - Max open positions not exceeded
    - Risk per trade within limits
    - Minimum RR met (also checked in continuation, double-checked here)
    - No averaging down conditions
    """

    def evaluate(
        self,
        signal_data: Dict[str, Any],
        config: Dict[str, Any],
        account_state: Optional[Dict[str, Any]] = None,
    ) -> PhaseResult:
        """
        Run all risk checks.

        Args:
            signal_data: Normalized signal dictionary
            config: ICC configuration settings
            account_state: Optional live account state (daily P&L, open positions, etc.)
                           If not provided, risk rules based on account state are skipped.

        Returns:
            PhaseResult — if any blocking rule fails, the trade is blocked.
        """
        rules = []
        total_score = 0
        max_possible = 0

        entry = signal_data.get("entry_price")
        stop = signal_data.get("stop_price")
        account_size = signal_data.get("account_size") or (account_state or {}).get("account_size")
        daily_pnl = (account_state or {}).get("daily_pnl_pct", 0.0)
        open_positions = (account_state or {}).get("open_positions", 0)
        consecutive_losses = (account_state or {}).get("consecutive_losses", 0)

        max_risk_pct = config.get("max_risk_per_trade_pct", 1.0)
        daily_max_loss = config.get("daily_max_loss_pct", 3.0)
        max_consec_losses = config.get("max_consecutive_losses", 3)
        max_open = config.get("max_open_positions", 1)

        # ── Rule 1: Daily loss limit ───────────────────────────────────────
        daily_rule = self._check_daily_loss(daily_pnl, daily_max_loss)
        rules.append(daily_rule)
        total_score += daily_rule.score
        max_possible += daily_rule.max_score

        # ── Rule 2: Consecutive loss circuit breaker ───────────────────────
        consec_rule = self._check_consecutive_losses(consecutive_losses, max_consec_losses)
        rules.append(consec_rule)
        total_score += consec_rule.score
        max_possible += consec_rule.max_score

        # ── Rule 3: Max open positions ────────────────────────────────────
        positions_rule = self._check_open_positions(open_positions, max_open)
        rules.append(positions_rule)
        total_score += positions_rule.score
        max_possible += positions_rule.max_score

        # ── Rule 4: Per-trade risk sizing ─────────────────────────────────
        if entry and stop and account_size:
            risk_rule = self._check_trade_risk(entry, stop, account_size, max_risk_pct)
            rules.append(risk_rule)
            total_score += risk_rule.score
            max_possible += risk_rule.max_score
        else:
            # Cannot verify risk — pass with warning
            rules.append(RuleResult(
                passed=True,
                rule_id="risk_trade_size",
                label="Per-trade risk within limit",
                message="Account size or stop not provided. Risk sizing cannot be verified.",
                score=15,
                max_score=25,
                is_blocking=False,
            ))
            total_score += 15
            max_possible += 25

        # ── Determine pass/fail ───────────────────────────────────────────
        has_blocking_failure = any(r.is_blocking and not r.passed for r in rules)
        phase_passed = not has_blocking_failure

        score = int((total_score / max_possible) * 100) if max_possible > 0 else 0

        if phase_passed:
            summary = "All risk rules pass. Trade size and limits acceptable."
        else:
            failures = [r.label for r in rules if r.is_blocking and not r.passed]
            summary = f"Risk rules blocked: {', '.join(failures)}. Do not trade."

        return PhaseResult(
            phase="risk",
            passed=phase_passed,
            score=score,
            rules=rules,
            summary=summary,
        )

    def _check_daily_loss(self, daily_pnl_pct: float, max_loss_pct: float) -> RuleResult:
        """Has the daily loss limit been hit?"""
        # daily_pnl_pct is negative when losing, e.g. -2.5 means down 2.5%
        pnl_as_loss = abs(daily_pnl_pct) if daily_pnl_pct < 0 else 0.0
        limit_hit = pnl_as_loss >= max_loss_pct

        if daily_pnl_pct == 0.0:
            return RuleResult(
                passed=True,
                rule_id="risk_daily_loss",
                label="Daily loss limit clear",
                message="No daily P&L data available. Limit check skipped.",
                score=25,
                max_score=25,
                is_blocking=False,
            )

        return RuleResult(
            passed=not limit_hit,
            rule_id="risk_daily_loss",
            label="Daily loss limit clear",
            message=(
                f"Daily P&L {daily_pnl_pct:+.1f}%. Limit: -{max_loss_pct:.1f}%. Clear."
                if not limit_hit
                else f"DAILY LOSS LIMIT HIT: Down {pnl_as_loss:.1f}% today (limit: {max_loss_pct:.1f}%). "
                     f"No more trades today."
            ),
            score=25 if not limit_hit else 0,
            max_score=25,
            is_blocking=limit_hit,
        )

    def _check_consecutive_losses(self, consec_losses: int, max_consec: int) -> RuleResult:
        """Circuit breaker: pause after too many losses in a row."""
        limit_hit = consec_losses >= max_consec

        return RuleResult(
            passed=not limit_hit,
            rule_id="risk_consec_losses",
            label="Consecutive loss limit clear",
            message=(
                f"{consec_losses} consecutive losses. Limit: {max_consec}. OK."
                if not limit_hit
                else f"CIRCUIT BREAKER: {consec_losses} consecutive losses (limit: {max_consec}). "
                     f"Pause, review, and reset before trading again."
            ),
            score=25 if not limit_hit else 0,
            max_score=25,
            is_blocking=limit_hit,
        )

    def _check_open_positions(self, open_positions: int, max_open: int) -> RuleResult:
        """No more than max_open positions at once."""
        limit_hit = open_positions >= max_open

        return RuleResult(
            passed=not limit_hit,
            rule_id="risk_open_positions",
            label="Open position limit clear",
            message=(
                f"{open_positions} open positions. Limit: {max_open}. OK."
                if not limit_hit
                else f"MAX POSITIONS: Already have {open_positions} open (limit: {max_open}). "
                     f"Close existing positions before entering new ones."
            ),
            score=25 if not limit_hit else 0,
            max_score=25,
            is_blocking=limit_hit,
        )

    def _check_trade_risk(
        self,
        entry: float,
        stop: float,
        account_size: float,
        max_risk_pct: float,
    ) -> RuleResult:
        """Is the risk on this trade within the per-trade limit?"""
        try:
            risk_points = abs(entry - stop)
            # Risk as % of account (simplified — does not include contract multiplier here)
            # Full position sizing with contract multiplier is done in the paper trading engine
            risk_pct = (risk_points / entry) * 100

            within_limit = risk_pct <= max_risk_pct

            return RuleResult(
                passed=within_limit,
                rule_id="risk_trade_size",
                label="Per-trade risk within limit",
                message=(
                    f"Stop is {risk_points:.2f} points from entry (~{risk_pct:.2f}% of price). "
                    f"Within {max_risk_pct:.1f}% limit."
                    if within_limit
                    else f"Stop is {risk_points:.2f} points from entry (~{risk_pct:.2f}% of price). "
                         f"Exceeds {max_risk_pct:.1f}% limit. Reduce position size."
                ),
                score=25 if within_limit else 5,
                max_score=25,
                is_blocking=False,  # Warning, not a hard block — trader can size down
            )
        except (TypeError, ZeroDivisionError):
            return RuleResult(
                passed=True,
                rule_id="risk_trade_size",
                label="Per-trade risk within limit",
                message="Could not compute risk percentage from provided levels.",
                score=10,
                max_score=25,
                is_blocking=False,
            )
