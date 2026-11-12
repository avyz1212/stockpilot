"""Simulated execution ledger.

This prototype NEVER signs or broadcasts a transaction. Fills are modelled
against the NAV reference value with the policy's explicit fee + slippage
assumptions, so a demo run shows realistic mechanics while staying honest:
every fill is stamped ``SIMULATED`` and the report repeats that the NAV is
a reference value, not an executable quote.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from .models import Decision, Policy, Portfolio, Position, StockQuote

ZERO = Decimal("0")


class SimulatedLedger:
    def __init__(self, portfolio: Portfolio, policy: Policy):
        self.portfolio = portfolio
        self.policy = policy
        self.fills: list[dict[str, Any]] = []

    def _fill_price(self, decision: Decision) -> Decimal:
        slip = self.policy.slippage_bps / Decimal("10000")
        if decision.action == "BUY":
            return decision.reference_price * (Decimal("1") + slip)
        return decision.reference_price * (Decimal("1") - slip)

    def apply(self, decisions: list[Decision], quotes: dict[str, StockQuote]) -> list[dict[str, Any]]:
        # Sells settle before buys, mirroring the planner's funding logic.
        ordered = sorted(decisions, key=lambda d: 0 if d.action == "SELL" else 1)
        for decision in ordered:
            if decision.action not in ("BUY", "SELL") or decision.amount_usd <= 0:
                continue
            assert decision.reference_price is not None
            price = self._fill_price(decision)
            quantity = decision.amount_usd / price
            fee = decision.amount_usd * self.policy.fee_bps / Decimal("10000")
            position = self.portfolio.positions.setdefault(
                decision.symbol, Position(symbol=decision.symbol)
            )
            realized = ZERO
            if decision.action == "BUY":
                total_cost = position.avg_cost_per_token * position.token_quantity + decision.amount_usd
                new_qty = position.token_quantity + quantity
                position.avg_cost_per_token = total_cost / new_qty if new_qty > 0 else ZERO
                position.token_quantity = new_qty
                self.portfolio.cash_usd -= decision.amount_usd + fee
            else:
                quantity = min(quantity, position.token_quantity)
                proceeds = quantity * price
                realized = (price - position.avg_cost_per_token) * quantity
                position.token_quantity -= quantity
                decision.amount_usd = proceeds
                self.portfolio.cash_usd += proceeds - fee
            decision.token_quantity = quantity
            fill = {
                "symbol": decision.symbol,
                "side": decision.action,
                "status": "SIMULATED",
                "reference_nav": str(decision.reference_price),
                "modelled_fill_price": str(price),
                "token_quantity": str(quantity),
                "share_equivalents": str(quantity * quotes[decision.symbol].multiplier),
                "gross_usd": str(decision.amount_usd),
                "fee_usd": str(fee),
                "realized_pnl_usd": str(realized),
                "assumptions": {
                    "fee_bps": str(self.policy.fee_bps),
                    "slippage_bps": str(self.policy.slippage_bps),
                    "note": "NAV is a reference value, not an executable quote; no transaction was signed or broadcast.",
                },
            }
            self.fills.append(fill)
        return self.fills
