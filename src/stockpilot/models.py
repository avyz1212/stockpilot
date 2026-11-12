"""Core data models for StockPilot.

All money math uses ``Decimal`` -- never binary floats -- because the audit
log is a financial record and must reconcile to the cent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


def dec(value: Any, default: Optional[Decimal] = None) -> Decimal:
    """Convert JSON-ish values (str/int/float) to Decimal safely."""
    if value is None:
        if default is not None:
            return default
        raise ValueError("missing numeric value")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"not a number: {value!r}") from exc


def parse_ts(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp (with trailing Z) into an aware datetime."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class StockQuote:
    """One tokenized-stock reference record, shaped after Base's public
    Tokenized Stocks API (see docs.base.org/sdks/tokenized-stocks).

    ``nav_price`` is a Chainlink-based NAV / reference value per token.
    It is NOT a live bid/ask and NOT an execution price.
    ``multiplier`` converts token units into share-equivalents and can
    change with corporate actions (splits / dividends).
    """

    symbol: str
    name: str
    nav_price: Decimal
    multiplier: Decimal = Decimal("1")
    contract_address: Optional[str] = None
    decimals: int = 8
    isin: Optional[str] = None
    total_supply: Optional[Decimal] = None
    nav_updated_at: Optional[datetime] = None
    paused_features: tuple[str, ...] = ()
    source: str = "fixture"

    @property
    def implied_underlying_price(self) -> Optional[Decimal]:
        """Reference value of one underlying share implied by the token NAV."""
        if self.multiplier == 0:
            return None
        return self.nav_price / self.multiplier

    def nav_age_hours(self, as_of: datetime) -> Optional[Decimal]:
        if self.nav_updated_at is None:
            return None
        delta = as_of - self.nav_updated_at
        return Decimal(str(delta.total_seconds())) / Decimal("3600")

    def is_stale(self, as_of: datetime, max_age_hours: Decimal) -> bool:
        age = self.nav_age_hours(as_of)
        return age is None or age > max_age_hours

    @classmethod
    def from_api_record(cls, record: dict[str, Any], source: str) -> "StockQuote":
        paused = record.get("paused_features") or ()
        return cls(
            symbol=str(record.get("symbol") or record.get("ticker") or "").strip(),
            name=str(record.get("name") or record.get("symbol") or "").strip(),
            nav_price=dec(record.get("nav_price")),
            multiplier=dec(record.get("multiplier"), Decimal("1")),
            contract_address=record.get("contract_address") or record.get("address"),
            decimals=int(record.get("decimals") or 8),
            isin=record.get("isin"),
            total_supply=dec(record["total_supply"]) if record.get("total_supply") is not None else None,
            nav_updated_at=parse_ts(record.get("nav_price_updated_at") or record.get("nav_updated_at")),
            paused_features=tuple(str(p) for p in paused),
            source=source,
        )


@dataclass
class Position:
    symbol: str
    token_quantity: Decimal = Decimal("0")
    avg_cost_per_token: Decimal = Decimal("0")

    def value(self, quote: StockQuote) -> Decimal:
        return self.token_quantity * quote.nav_price

    def share_equivalents(self, quote: StockQuote) -> Decimal:
        return self.token_quantity * quote.multiplier


@dataclass
class Portfolio:
    cash_usd: Decimal
    positions: dict[str, Position] = field(default_factory=dict)

    def total_value(self, quotes: dict[str, StockQuote]) -> Decimal:
        total = self.cash_usd
        for symbol, position in self.positions.items():
            quote = quotes.get(symbol)
            if quote is not None and position.token_quantity != 0:
                total += position.value(quote)
        return total

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Portfolio":
        positions = {}
        for symbol, raw in (payload.get("positions") or {}).items():
            positions[symbol] = Position(
                symbol=symbol,
                token_quantity=dec(raw.get("token_quantity"), Decimal("0")),
                avg_cost_per_token=dec(raw.get("avg_cost_per_token"), Decimal("0")),
            )
        return cls(cash_usd=dec(payload.get("cash_usd"), Decimal("0")), positions=positions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cash_usd": str(self.cash_usd),
            "positions": {
                symbol: {
                    "token_quantity": str(pos.token_quantity),
                    "avg_cost_per_token": str(pos.avg_cost_per_token),
                }
                for symbol, pos in sorted(self.positions.items())
            },
        }


@dataclass(frozen=True)
class Policy:
    """The user's explicit, version-controlled rule set. The agent may only
    act inside these bounds; it can never widen them itself."""

    target_weights: dict[str, Decimal]  # symbol -> fraction of portfolio; "CASH" allowed
    tolerance_band: Decimal = Decimal("0.03")        # drift band that triggers action
    min_trade_usd: Decimal = Decimal("100")
    max_single_asset_weight: Decimal = Decimal("0.30")
    max_trade_fraction_per_run: Decimal = Decimal("0.10")
    min_cash_reserve_fraction: Decimal = Decimal("0.05")
    max_nav_age_hours: Decimal = Decimal("24")
    fee_bps: Decimal = Decimal("10")
    slippage_bps: Decimal = Decimal("15")
    kill_switch: bool = False
    blocked_symbols: frozenset[str] = frozenset()

    def validate(self) -> None:
        total = sum(self.target_weights.values())
        if not (Decimal("0.99") <= total <= Decimal("1.01")):
            raise ValueError(f"target weights must sum to ~1.0, got {total}")
        for symbol, weight in self.target_weights.items():
            if symbol != "CASH" and weight > self.max_single_asset_weight:
                raise ValueError(
                    f"target for {symbol} ({weight}) exceeds max single-asset weight "
                    f"({self.max_single_asset_weight})"
                )
            if weight < 0:
                raise ValueError(f"negative target weight for {symbol}")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Policy":
        targets = {str(k): dec(v) for k, v in (payload.get("target_weights") or {}).items()}
        policy = cls(
            target_weights=targets,
            tolerance_band=dec(payload.get("tolerance_band"), Decimal("0.03")),
            min_trade_usd=dec(payload.get("min_trade_usd"), Decimal("100")),
            max_single_asset_weight=dec(payload.get("max_single_asset_weight"), Decimal("0.30")),
            max_trade_fraction_per_run=dec(payload.get("max_trade_fraction_per_run"), Decimal("0.10")),
            min_cash_reserve_fraction=dec(payload.get("min_cash_reserve_fraction"), Decimal("0.05")),
            max_nav_age_hours=dec(payload.get("max_nav_age_hours"), Decimal("24")),
            fee_bps=dec(payload.get("fee_bps"), Decimal("10")),
            slippage_bps=dec(payload.get("slippage_bps"), Decimal("15")),
            kill_switch=bool(payload.get("kill_switch", False)),
            blocked_symbols=frozenset(str(s) for s in payload.get("blocked_symbols", [])),
        )
        policy.validate()
        return policy


@dataclass
class Decision:
    symbol: str
    action: str  # BUY | SELL | HOLD | BLOCKED
    amount_usd: Decimal = Decimal("0")
    token_quantity: Decimal = Decimal("0")
    reference_price: Optional[Decimal] = None
    current_weight: Decimal = Decimal("0")
    target_weight: Decimal = Decimal("0")
    reasons: list[str] = field(default_factory=list)
    guardrails: list[str] = field(default_factory=list)
    status: str = "SIMULATED"  # this prototype never executes real orders

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "amount_usd": str(self.amount_usd),
            "token_quantity": str(self.token_quantity),
            "reference_price": str(self.reference_price) if self.reference_price is not None else None,
            "current_weight": str(self.current_weight),
            "target_weight": str(self.target_weight),
            "reasons": list(self.reasons),
            "guardrails": list(self.guardrails),
            "status": self.status,
        }
