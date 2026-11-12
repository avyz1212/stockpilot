"""The transparent rule engine.

StockPilot is deliberately NOT a black-box predictor. Every decision comes
from the user's written policy (``Policy``) plus observable reference data,
and every decision carries the arithmetic that produced it:

  drift        = current weight - target weight
  desired move = target value - current value        (per asset)
  sells first  -> proceeds fund buys, cash reserve is never breached
  guardrails   -> kill switch, blocked symbols, paused features, stale or
                  missing NAV, concentration cap, per-run trade cap,
                  minimum trade size, no shorting, cash floor

If a guardrail fires, the decision is HOLD or BLOCKED and the audit log
says exactly which rule fired and with what numbers.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .models import Decision, Policy, Portfolio, StockQuote

ZERO = Decimal("0")
ONE = Decimal("1")


def _pct(value: Decimal) -> str:
    return f"{(value * 100).quantize(Decimal('0.01'))}%"


class RebalancePlanner:
    def __init__(self, policy: Policy):
        self.policy = policy

    def plan(
        self,
        portfolio: Portfolio,
        quotes: dict[str, StockQuote],
        as_of: datetime,
    ) -> list[Decision]:
        policy = self.policy
        total = portfolio.total_value(quotes)
        if total <= 0:
            return [
                Decision(
                    symbol="*",
                    action="BLOCKED",
                    reasons=["portfolio value is zero; nothing to plan"],
                    guardrails=["zero-value portfolio"],
                )
            ]

        symbols = sorted(set(policy.target_weights) | set(portfolio.positions) | set(quotes))
        symbols = [s for s in symbols if s != "CASH"]

        current_weight: dict[str, Decimal] = {}
        for symbol in symbols:
            position = portfolio.positions.get(symbol)
            quote = quotes.get(symbol)
            if position is not None and quote is not None:
                current_weight[symbol] = position.value(quote) / total
            else:
                current_weight[symbol] = ZERO

        # Effective targets respect the concentration cap even if the file
        # was edited after validation.
        target_weight = {
            s: min(policy.target_weights.get(s, ZERO), policy.max_single_asset_weight)
            for s in symbols
        }

        decisions: dict[str, Decision] = {}
        desired: dict[str, Decimal] = {}  # signed USD: + buy, - sell

        for symbol in symbols:
            quote = quotes.get(symbol)
            position = portfolio.positions.get(symbol)
            held = position.token_quantity if position else ZERO
            cur_w = current_weight[symbol]
            tgt_w = target_weight[symbol]
            reasons: list[str] = []
            guardrails: list[str] = []

            if policy.kill_switch:
                decisions[symbol] = Decision(
                    symbol=symbol, action="BLOCKED", current_weight=cur_w, target_weight=tgt_w,
                    reasons=["kill switch is ON in the policy; the agent stands down"],
                    guardrails=["kill_switch"],
                )
                continue
            if symbol in policy.blocked_symbols:
                decisions[symbol] = Decision(
                    symbol=symbol, action="BLOCKED", current_weight=cur_w, target_weight=tgt_w,
                    reasons=[f"{symbol} is on the user's blocked-symbol list"],
                    guardrails=["blocked_symbol"],
                )
                continue
            if quote is None or quote.nav_price is None or quote.nav_price <= 0:
                decisions[symbol] = Decision(
                    symbol=symbol, action="BLOCKED", current_weight=cur_w, target_weight=tgt_w,
                    reasons=["no usable NAV/reference value from the data source; refusing to guess a price"],
                    guardrails=["missing_nav"],
                )
                continue
            if quote.paused_features:
                decisions[symbol] = Decision(
                    symbol=symbol, action="BLOCKED", current_weight=cur_w, target_weight=tgt_w,
                    reference_price=quote.nav_price,
                    reasons=[f"token reports paused features {list(quote.paused_features)}; no trading"],
                    guardrails=["paused_features"],
                )
                continue

            drift = cur_w - tgt_w
            move_usd = tgt_w * total - cur_w * total
            stale = quote.is_stale(as_of, policy.max_nav_age_hours)
            age = quote.nav_age_hours(as_of)
            reasons.append(
                f"weight {_pct(cur_w)} vs target {_pct(tgt_w)} (drift {_pct(drift)}); "
                f"NAV reference {quote.nav_price} (age {age}h, multiplier {quote.multiplier})"
            )

            if abs(drift) <= policy.tolerance_band:
                decisions[symbol] = Decision(
                    symbol=symbol, action="HOLD", current_weight=cur_w, target_weight=tgt_w,
                    reference_price=quote.nav_price,
                    reasons=reasons + [f"inside the {_pct(policy.tolerance_band)} tolerance band; no action"],
                )
                continue

            if move_usd > 0 and stale:
                decisions[symbol] = Decision(
                    symbol=symbol, action="BLOCKED", current_weight=cur_w, target_weight=tgt_w,
                    reference_price=quote.nav_price,
                    reasons=reasons + [
                        f"NAV is stale (age {age}h > limit {policy.max_nav_age_hours}h); buys are refused on stale data"
                    ],
                    guardrails=["stale_nav_no_buy"],
                )
                continue

            if stale:
                guardrails.append("stale_nav_sell_only_to_reduce_risk")

            desired[symbol] = move_usd
            decisions[symbol] = Decision(
                symbol=symbol,
                action="BUY" if move_usd > 0 else "SELL",
                current_weight=cur_w, target_weight=tgt_w,
                reference_price=quote.nav_price,
                reasons=reasons,
                guardrails=guardrails,
            )

        # ---- sizing pass: caps, cash, no shorting -------------------------
        cap_usd = total * policy.max_trade_fraction_per_run
        cash_available = portfolio.cash_usd

        # Sells first: they fund the buys.
        for symbol in sorted(desired, key=lambda s: desired[s]):
            if desired[symbol] >= 0:
                continue
            quote = quotes[symbol]
            held_value = portfolio.positions[symbol].value(quote) if symbol in portfolio.positions else ZERO
            amount = min(-desired[symbol], cap_usd, held_value)  # never sell more than held (no shorting)
            decision = decisions[symbol]
            if amount < policy.min_trade_usd and held_value > amount:
                decision.action = "HOLD"
                decision.reasons.append(
                    f"required sell {amount} USD is below the minimum trade size {policy.min_trade_usd} USD"
                )
                decision.guardrails.append("min_trade_size")
                continue
            decision.amount_usd = amount
            decision.token_quantity = amount / quote.nav_price
            decision.reasons.append(
                f"sell {amount} USD toward target (capped by per-run cap {cap_usd} USD and holdings {held_value} USD)"
            )
            fee = amount * policy.fee_bps / Decimal("10000")
            cash_available += amount - fee

        # Buys share whatever cash remains above the reserve floor.
        reserve_floor = total * policy.min_cash_reserve_fraction
        buy_budget = max(ZERO, cash_available - reserve_floor)
        total_wanted = sum(v for v in desired.values() if v > 0)
        scale = ONE if total_wanted <= buy_budget or total_wanted == 0 else buy_budget / total_wanted

        for symbol in sorted(desired, key=lambda s: -desired[s]):
            if desired[symbol] <= 0:
                continue
            quote = quotes[symbol]
            decision = decisions[symbol]
            amount = min(desired[symbol] * scale, cap_usd)
            if amount < policy.min_trade_usd:
                decision.action = "HOLD"
                decision.amount_usd = ZERO
                decision.reasons.append(
                    f"required buy scaled to {amount} USD (cash budget {buy_budget} USD after the "
                    f"{_pct(policy.min_cash_reserve_fraction)} reserve floor), below the minimum trade size "
                    f"{policy.min_trade_usd} USD"
                )
                decision.guardrails.append("min_trade_size" if scale >= 1 else "cash_reserve_floor")
                continue
            decision.amount_usd = amount
            decision.token_quantity = amount / quote.nav_price
            decision.reasons.append(
                f"buy {amount} USD toward target (per-run cap {cap_usd} USD; cash budget {buy_budget} USD)"
            )

        return [decisions[s] for s in symbols if s in decisions]
