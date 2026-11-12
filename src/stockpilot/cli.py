"""StockPilot command line.

One command runs the whole loop:

    python -m stockpilot demo           # bundled example, writes runs/demo/
    python -m stockpilot run --config config.example.json \
        --portfolio data/demo_portfolio.json --data data/base_snapshot.fixture.json \
        --dca 500 --check-base --out runs/manual

The agent loads reference data, explains every decision, simulates fills
against its own ledger, and writes report.json + report.md + audit.jsonl.
It never asks for a key and never broadcasts a transaction.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from .audit import AuditLog, run_fingerprint
from .base_rpc import BaseChainReader
from .data import provider_from_args
from .ledger import SimulatedLedger
from .models import Policy, Portfolio, StockQuote, dec
from .strategy import RebalancePlanner

ROOT = Path(__file__).resolve().parents[2]
DISCLAIMERS = [
    "Prototype for the Base Stocks Maxxing Builder Quest (Agentic Stock Finance track).",
    "Not investment advice. Tokenized stocks are securities; eligibility and local law are the user's responsibility.",
    "NAV values are Chainlink-based reference values, not live bid/ask or execution prices.",
    "All fills in this build are SIMULATED. No wallet, no keys, no transaction was signed or broadcast.",
]


def _weights(portfolio: Portfolio, quotes: dict[str, StockQuote]) -> dict[str, Any]:
    total = portfolio.total_value(quotes)
    rows: dict[str, Any] = {}
    if total <= 0:
        return {"total_value_usd": "0", "cash_weight": "0", "assets": rows}
    for symbol, position in sorted(portfolio.positions.items()):
        quote = quotes.get(symbol)
        if quote is None or position.token_quantity == 0:
            continue
        rows[symbol] = {
            "token_quantity": str(position.token_quantity),
            "share_equivalents": str(position.share_equivalents(quote)),
            "value_usd": str(position.value(quote)),
            "weight": str(position.value(quote) / total),
            "avg_cost_per_token": str(position.avg_cost_per_token),
            "multiplier": str(quote.multiplier),
        }
    return {
        "total_value_usd": str(total),
        "cash_usd": str(portfolio.cash_usd),
        "cash_weight": str(portfolio.cash_usd / total),
        "assets": rows,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# StockPilot run {report['run_id']}",
        "",
        f"- Mode: **{report['mode']}** (all fills simulated)",
        f"- Data: {report['data_source']} @ {report['as_of']}",
        f"- Portfolio value: {report['portfolio_before']['total_value_usd']} -> "
        f"{report['portfolio_after']['total_value_usd']} USD (reference NAV)",
        "",
        "## Decisions (every one explained)",
        "",
        "| Symbol | Action | Amount USD | Current -> Target | Why |",
        "|---|---|---|---|---|",
    ]
    for d in report["decisions"]:
        why = "<br>".join(d["reasons"])
        if d["guardrails"]:
            why += f"<br>Guardrails: {', '.join(d['guardrails'])}"
        lines.append(
            f"| {d['symbol']} | {d['action']} | {d['amount_usd']} | "
            f"{d['current_weight']} -> {d['target_weight']} | {why} |"
        )
    lines += ["", "## Simulated fills", ""]
    if report["fills"]:
        lines += ["| Symbol | Side | Tokens | Fill price (modelled) | Fee USD | Realized PnL |",
                  "|---|---|---|---|---|---|"]
        for f in report["fills"]:
            lines.append(
                f"| {f['symbol']} | {f['side']} | {f['token_quantity']} | "
                f"{f['modelled_fill_price']} | {f['fee_usd']} | {f['realized_pnl_usd']} |"
            )
    else:
        lines.append("No fills: every position was inside its band or blocked by a guardrail.")
    if report.get("base_health"):
        lines += ["", "## Base network check (read-only)", "", f"```json\n{json.dumps(report['base_health'], indent=2)}\n```"]
    lines += ["", "## Disclaimers", ""] + [f"- {d}" for d in report["disclaimers"]] + [""]
    return "\n".join(lines)


def run_agent(args: argparse.Namespace) -> dict[str, Any]:
    policy = Policy.from_dict(json.loads(Path(args.config).read_text(encoding="utf-8")))
    portfolio = Portfolio.from_dict(json.loads(Path(args.portfolio).read_text(encoding="utf-8")))
    provider = provider_from_args(args.api_url, args.data)
    quotes, fixture_as_of, source_label = provider.load()
    as_of = fixture_as_of or datetime.now(timezone.utc)
    if args.as_of:
        from .models import parse_ts

        as_of = parse_ts(args.as_of) or as_of

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    before = portfolio.to_dict()
    base_health: Optional[dict[str, Any]] = None
    with AuditLog(out_dir / "audit.jsonl") as audit:
        audit.emit("run_started", mode="simulate" if not args.plan_only else "plan_only",
                   data_source=source_label, as_of=as_of.isoformat())
        audit.emit("data_loaded", symbols=sorted(quotes), source=source_label)
        if args.check_base:
            base_health = BaseChainReader(args.rpc_url).health()
            audit.emit("base_health", **base_health)
        if args.dca and Decimal(args.dca) > 0:
            inflow = Decimal(args.dca)
            portfolio.cash_usd += inflow
            audit.emit("cash_inflow_simulated", amount_usd=str(inflow),
                       note="scheduled contribution simulated; no funds were deposited or moved")

        planner = RebalancePlanner(policy)
        decisions = planner.plan(portfolio, quotes, as_of)
        for decision in decisions:
            audit.emit("decision", **decision.to_dict())

        fills: list[dict[str, Any]] = []
        if not args.plan_only:
            ledger = SimulatedLedger(portfolio, policy)
            fills = ledger.apply(decisions, quotes)
            for fill in fills:
                audit.emit("simulated_fill", **fill)
        audit.emit("run_completed", fills=len(fills), portfolio_after=portfolio.to_dict())

    report: dict[str, Any] = {
        "run_id": run_fingerprint({"config": str(args.config), "before": before, "source": source_label}),
        "mode": "plan_only" if args.plan_only else "simulate",
        "data_source": source_label,
        "as_of": as_of.isoformat(),
        "base_health": base_health,
        "portfolio_before": _weights(Portfolio.from_dict(before), quotes),
        "portfolio_after": _weights(portfolio, quotes),
        "decisions": [d.to_dict() for d in decisions],
        "fills": fills,
        "disclaimers": DISCLAIMERS,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "report.md").write_text(_markdown(report), encoding="utf-8")
    return report


def _print_summary(report: dict[str, Any]) -> None:
    print(f"StockPilot run {report['run_id']} [{report['mode']}] data={report['data_source']}")
    print(f"Portfolio (reference NAV): {report['portfolio_before']['total_value_usd']} -> "
          f"{report['portfolio_after']['total_value_usd']} USD")
    for d in report["decisions"]:
        print(f"  {d['symbol']:<8} {d['action']:<8} {d['amount_usd']:>12} USD  {d['reasons'][0] if d['reasons'] else ''}")
    print(f"Fills simulated: {len(report['fills'])} (no transaction signed or broadcast)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stockpilot", description="Explainable tokenized-stock agent for Base (simulation-first).")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run the bundled example end to end")
    demo.add_argument("--out", default=str(ROOT / "runs" / "demo"))
    demo.add_argument("--dca", default="500")
    demo.add_argument("--check-base", action="store_true", default=True)

    run = sub.add_parser("run", help="run with your own config / portfolio / data")
    run.add_argument("--config", required=True)
    run.add_argument("--portfolio", required=True)
    run.add_argument("--data", default=str(ROOT / "data" / "base_snapshot.fixture.json"))
    run.add_argument("--api-url", default=None,
                       help="Base Tokenized Stocks API base URL (official docs); overrides fixture data")
    run.add_argument("--dca", default="0", help="simulated scheduled contribution in USD")
    run.add_argument("--check-base", action="store_true")
    run.add_argument("--rpc-url", default="https://mainnet.base.org")
    run.add_argument("--plan-only", action="store_true")
    run.add_argument("--as-of", default=None)
    run.add_argument("--out", default=str(ROOT / "runs" / "manual"))
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "demo":
        demo_args = argparse.Namespace(
            config=str(ROOT / "config.example.json"),
            portfolio=str(ROOT / "data" / "demo_portfolio.json"),
            data=str(ROOT / "data" / "base_snapshot.fixture.json"),
            api_url=None,
            dca=args.dca,
            check_base=args.check_base,
            rpc_url="https://mainnet.base.org",
            plan_only=False,
            as_of=None,
            out=args.out,
        )
        report = run_agent(demo_args)
    else:
        report = run_agent(args)
    _print_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
