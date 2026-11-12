"""StockPilot test suite -- pure stdlib unittest, no network except fakes.

Run:  python3 -m unittest discover -s tests -v
"""
import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stockpilot.base_rpc import BaseChainReader
from stockpilot.data import BaseTokenizedStocksProvider
from stockpilot.ledger import SimulatedLedger
from stockpilot.models import Policy, Portfolio, Position, StockQuote
from stockpilot.strategy import RebalancePlanner

AS_OF = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)
FRESH = datetime(2026, 11, 13, 14, 0, tzinfo=timezone.utc)
STALE = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)


def quote(symbol, price, updated=FRESH, multiplier="1", paused=()):
    return StockQuote(
        symbol=symbol, name=symbol, nav_price=Decimal(price),
        multiplier=Decimal(multiplier), nav_updated_at=updated,
        paused_features=tuple(paused),
    )


def base_policy(**overrides):
    payload = {
        "target_weights": {"NVDAc": "0.25", "AAPLc": "0.25", "CASH": "0.50"},
        "tolerance_band": "0.03",
        "min_trade_usd": "100",
        "max_single_asset_weight": "0.30",
    }
    payload.update(overrides)
    return Policy.from_dict(payload)


class TestValuationMath(unittest.TestCase):
    def test_multiplier_share_equivalents(self):
        q = quote("GOOGLc", "289.35", multiplier="1.02")
        pos = Position("GOOGLc", Decimal("10"), Decimal("275"))
        self.assertEqual(pos.share_equivalents(q), Decimal("10.20"))
        self.assertEqual(pos.value(q), Decimal("2893.50"))
        # implied price of one underlying share = NAV / multiplier
        self.assertAlmostEqual(float(q.implied_underlying_price), 289.35 / 1.02, places=6)


class TestPlanner(unittest.TestCase):
    def setUp(self):
        self.quotes = {
            "NVDAc": quote("NVDAc", "100"),
            "AAPLc": quote("AAPLc", "50"),
        }

    def test_rebalance_sells_overweight_and_buys_underweight(self):
        portfolio = Portfolio(cash_usd=Decimal("5000"), positions={
            "NVDAc": Position("NVDAc", Decimal("40"), Decimal("90")),   # 4000 -> 40% (target 25%)
            "AAPLc": Position("AAPLc", Decimal("20"), Decimal("45")),   # 1000 -> 10% (target 25%)
        })
        decisions = {d.symbol: d for d in RebalancePlanner(base_policy()).plan(portfolio, self.quotes, AS_OF)}
        self.assertEqual(decisions["NVDAc"].action, "SELL")
        self.assertEqual(decisions["AAPLc"].action, "BUY")
        self.assertTrue(all(d.reasons for d in decisions.values()))

    def test_inside_band_holds(self):
        portfolio = Portfolio(cash_usd=Decimal("4800"), positions={
            "NVDAc": Position("NVDAc", Decimal("26"), Decimal("90")),   # 26%
            "AAPLc": Position("AAPLc", Decimal("48"), Decimal("45")),   # 24%
        })
        decisions = {d.symbol: d for d in RebalancePlanner(base_policy()).plan(portfolio, self.quotes, AS_OF)}
        self.assertEqual(decisions["NVDAc"].action, "HOLD")
        self.assertEqual(decisions["AAPLc"].action, "HOLD")

    def test_stale_nav_blocks_buys_but_not_risk_reducing_sells(self):
        quotes = {"NVDAc": quote("NVDAc", "100", updated=STALE), "AAPLc": quote("AAPLc", "50", updated=STALE)}
        portfolio = Portfolio(cash_usd=Decimal("5000"), positions={
            "NVDAc": Position("NVDAc", Decimal("40"), Decimal("90")),
            "AAPLc": Position("AAPLc", Decimal("20"), Decimal("45")),
        })
        decisions = {d.symbol: d for d in RebalancePlanner(base_policy()).plan(portfolio, quotes, AS_OF)}
        self.assertEqual(decisions["AAPLc"].action, "BLOCKED")
        self.assertIn("stale_nav_no_buy", decisions["AAPLc"].guardrails)
        self.assertEqual(decisions["NVDAc"].action, "SELL")

    def test_kill_switch_blocks_everything(self):
        portfolio = Portfolio(cash_usd=Decimal("5000"), positions={
            "NVDAc": Position("NVDAc", Decimal("40"), Decimal("90")),
        })
        decisions = RebalancePlanner(base_policy(kill_switch=True)).plan(portfolio, self.quotes, AS_OF)
        self.assertTrue(all(d.action == "BLOCKED" for d in decisions))
        self.assertTrue(all("kill_switch" in d.guardrails for d in decisions))

    def test_paused_token_blocked(self):
        quotes = dict(self.quotes)
        quotes["NVDAc"] = quote("NVDAc", "100", paused=("MINT",))
        portfolio = Portfolio(cash_usd=Decimal("5000"), positions={
            "NVDAc": Position("NVDAc", Decimal("40"), Decimal("90")),
        })
        decisions = {d.symbol: d for d in RebalancePlanner(base_policy()).plan(portfolio, quotes, AS_OF)}
        self.assertEqual(decisions["NVDAc"].action, "BLOCKED")
        self.assertIn("paused_features", decisions["NVDAc"].guardrails)

    def test_no_shorting_sell_capped_at_holdings(self):
        policy = base_policy(target_weights={"NVDAc": "0.0", "AAPLc": "0.25", "CASH": "0.75"})
        portfolio = Portfolio(cash_usd=Decimal("1000"), positions={
            "NVDAc": Position("NVDAc", Decimal("3"), Decimal("90")),  # only 300 USD held
        })
        decisions = {d.symbol: d for d in RebalancePlanner(policy).plan(portfolio, self.quotes, AS_OF)}
        self.assertEqual(decisions["NVDAc"].action, "SELL")
        self.assertLessEqual(decisions["NVDAc"].amount_usd, Decimal("300"))

    def test_min_trade_size_turns_dust_into_hold(self):
        # NVDAc is 29% vs a 25% target (drift beyond the 3% band), but the
        # required sell is only 80 USD -- below the 100 USD minimum trade.
        portfolio = Portfolio(cash_usd=Decimal("1420"), positions={
            "NVDAc": Position("NVDAc", Decimal("5.8"), Decimal("90")),
        })
        decisions = {d.symbol: d for d in RebalancePlanner(base_policy()).plan(portfolio, self.quotes, AS_OF)}
        self.assertEqual(decisions["NVDAc"].action, "HOLD")
        self.assertIn("min_trade_size", decisions["NVDAc"].guardrails)


class TestLedger(unittest.TestCase):
    def test_simulated_fill_updates_cash_and_cost_basis(self):
        quotes = {"NVDAc": quote("NVDAc", "100")}
        portfolio = Portfolio(cash_usd=Decimal("1000"))
        policy = base_policy()
        planner = RebalancePlanner(policy)
        p2 = Portfolio(cash_usd=Decimal("0"), positions={"NVDAc": Position("NVDAc", Decimal("0"), Decimal("0"))})
        from stockpilot.models import Decision
        decision = Decision(symbol="NVDAc", action="BUY", amount_usd=Decimal("500"),
                            reference_price=Decimal("100"))
        ledger = SimulatedLedger(portfolio, policy)
        fills = ledger.apply([decision], quotes)
        self.assertEqual(fills[0]["status"], "SIMULATED")
        self.assertLess(portfolio.cash_usd, Decimal("500"))  # amount + fee left the cash
        self.assertGreater(portfolio.positions["NVDAc"].token_quantity, Decimal("4.9"))
        self.assertEqual(p2.cash_usd, Decimal("0"))


class TestBaseReader(unittest.TestCase):
    def test_chain_health_with_fake_transport(self):
        def fake(url, payload):
            if payload["method"] == "eth_chainId":
                return {"result": "0x2105"}
            return {"result": "0x100"}

        reader = BaseChainReader(transport=fake)
        health = reader.health()
        self.assertTrue(health["reachable"])
        self.assertEqual(health["chain_id"], 8453)
        self.assertTrue(health["is_base_mainnet"])
        self.assertEqual(health["block_number"], 256)

    def test_balance_of_calldata_and_position_math(self):
        seen = {}

        def fake(url, payload):
            seen["data"] = payload["params"][0]["data"]
            return {"result": "0x" + format(250_000_000, "x")}  # 2.5 tokens at 8 decimals

        reader = BaseChainReader(transport=fake)
        position = reader.token_position(
            "0x0000000000000000000000000000000000000001",
            "0x0000000000000000000000000000000000000002",
            decimals=8, multiplier=Decimal("1.5"),
        )
        self.assertTrue(seen["data"].startswith("0x70a08231"))
        self.assertEqual(position["token_quantity"], "2.5")
        self.assertEqual(position["share_equivalents"], "3.75")

    def test_unreachable_rpc_reports_not_crashes(self):
        def boom(url, payload):
            raise OSError("network down")

        health = BaseChainReader(transport=boom).health()
        self.assertFalse(health["reachable"])


class TestApiProvider(unittest.TestCase):
    def test_pagination_and_omitted_fields(self):
        calls = []

        def fetcher(url):
            calls.append(url)
            if "page_token" not in url:
                return {
                    "tokens": [
                        {"symbol": "NVDAc", "name": "NVIDIA", "nav_price": "187.42",
                         "multiplier": "1", "nav_price_updated_at": "2026-11-13T14:00:00Z"},
                        {"symbol": "BROKEN", "name": "No NAV"},  # unusable: skipped, never invented
                    ],
                    "next_page_token": "p2",
                }
            return {"tokens": [{"symbol": "AAPLc", "name": "Apple", "nav_price": "231.80"}]}

        provider = BaseTokenizedStocksProvider("https://example.invalid/api", fetcher=fetcher)
        quotes, _, label = provider.load()
        self.assertEqual(sorted(quotes), ["AAPLc", "NVDAc"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(quotes["NVDAc"].source, "base-tokenized-stocks-api")
        # fields the API omits fall back to documented defaults
        self.assertEqual(quotes["AAPLc"].multiplier, Decimal("1"))
        self.assertEqual(quotes["AAPLc"].decimals, 8)


if __name__ == "__main__":
    unittest.main()
