# StockPilot — an explainable stock agent for tokenized stocks on Base

**Track: Agentic Stock Finance — Base Stocks Maxxing Builder Quest**
One-liner: *StockPilot watches a basket of Coinbase-issued tokenized stocks (B20) on Base, applies a transparent, user-written rule set — target-weight rebalancing plus scheduled DCA — and explains every decision in plain language with a complete audit log. Simulation-first, human kill switch, no custody, no keys.*

---

## The problem

Tokenized stocks on Base trade 24/7, but the data and mechanics underneath them are subtle:

- The official reference price is a **Chainlink NAV value**, not a live bid/ask. Feeds update on deviation/heartbeat and hold their last value outside market hours — an agent that trades blindly on a stale NAV is trading on a ghost price.
- B20 tokens carry an on-chain **`multiplier()`**: one token tracks one share *times* the multiplier, and the multiplier changes with splits and dividends. An agent that ignores it slowly misstates every position in share terms.
- Most "AI trading agents" are black boxes: they cannot answer the only question that matters — *why did you do that?*

## The solution

StockPilot is a **rules-first agent**: the strategy is a JSON policy the user writes and versions (target weights, tolerance band, caps, reserves, blocked symbols, kill switch). The agent:

1. **Loads reference data** in the exact schema of Base's public Tokenized Stocks API (fixture snapshot for offline/demo runs; the live read-only API when `--api-url` is supplied — no API key exists or is needed).
2. **Checks the network** with read-only Base JSON-RPC (`eth_chainId`, `eth_blockNumber`) and can read a wallet's ERC-20 `balanceOf` to derive share-equivalents via the API multiplier. It never signs anything.
3. **Plans** a rebalance: drift vs target per asset, sells before buys, buys scaled to cash above a reserve floor.
4. **Explains every decision** — BUY / SELL / HOLD / BLOCKED — with the arithmetic and the exact guardrail that fired, if any.
5. **Simulates fills** against its own ledger with explicit fee (10 bps) and slippage (15 bps) assumptions, correctly stamped `SIMULATED`.
6. **Writes an audit log** (`audit.jsonl`) plus `report.json` / `report.md` for every run, so anyone can replay *why*.

### Guardrails (all enforced, all tested)

| Guardrail | Behaviour |
|---|---|
| Kill switch | Policy flag → every decision BLOCKED, agent stands down |
| Stale NAV | Buys refused when NAV age > limit (default 24h); risk-reducing sells still allowed |
| Paused features | Token reporting paused mint/redeem/etc. → no trading in it |
| Missing NAV | No usable reference value → BLOCKED; the agent never invents a price |
| Concentration cap | No asset above max weight (default 30%); targets are capped too |
| Per-run trade cap | No single trade above 10% of portfolio value per run |
| Cash reserve floor | Buys never push cash below 5% of portfolio |
| Minimum trade size | Dust moves (< $100 default) become HOLD |
| No shorting | Sells capped at the quantity actually held |
| Blocked symbols | User list always wins |

### Sample demo run (real output, fixture scenario)

```
StockPilot run c758c236958585e9 [simulate] data=fixture:base_snapshot.fixture.json
Portfolio (reference NAV): 11127.54 -> 11622.93 USD
  AAPLc    BUY      934.71 USD  weight 11.96% vs target 20.00% (drift -8.04%); NAV age 1.0h
  AMZNc    HOLD         0 USD  weight 0.00% vs target 0.00%
  COINc    BLOCKED      0 USD  token reports paused features ['MINT']; no trading
  GOOGLc   BUY      470.46 USD  weight 9.95% vs target 14.00%; multiplier 1.02 applied
  METAc    HOLD         0 USD  inside the 3% tolerance band
  MSFTc    HOLD         0 USD  inside the 3% tolerance band
  NVDAc    SELL     440.66 USD  weight 25.79% vs target 22.00% (drift +3.79%)
  SPCXc    BLOCKED      0 USD  on the user's blocked-symbol list
  TSLAc    BLOCKED      0 USD  NAV is 48h old -> buys refused on stale data
Fills simulated: 3 (no transaction signed or broadcast)
```

Full recorded run: [`docs/sample-run.md`](docs/sample-run.md), [`docs/sample-report.json`](docs/sample-report.json), [`docs/sample-audit.jsonl`](docs/sample-audit.jsonl).

## Honest live-vs-simulated table

| Capability | Status in this build |
|---|---|
| Tokenized-stock reference data (schema, pagination, omitted fields) | **Real client** for Base's public Tokenized Stocks API; demo runs on a bundled fixture in the identical schema (scenario NAVs, clearly labelled) |
| Base network identity / block height | **Live read-only JSON-RPC** (`--check-base`); degrades to "unavailable" instead of failing the run |
| Wallet position read (`balanceOf` → share-equivalents × multiplier) | **Implemented, read-only**, unit-tested with a fake transport; needs a token contract address from the live API to run against mainnet |
| Strategy decisions + explanations | **Real** — the actual planner runs in demo and tests |
| Trade execution | **Simulated only.** Fills are modelled at NAV ± slippage with fees. No wallet, no keys, nothing is signed or broadcast, ever, in this build |
| Prices shown | NAV **reference values**, never presented as executable quotes |

## Run it

Requirements: Python ≥ 3.11, standard library only. No install, no keys, no network required for the demo.

```bash
python3 run.py demo                     # bundled example -> runs/demo/{report.md,report.json,audit.jsonl}
python3 -m unittest discover -s tests   # 13 tests
```

Custom run:

```bash
python3 run.py run \
  --config config.example.json \
  --portfolio data/demo_portfolio.json \
  --data data/base_snapshot.fixture.json \
  --dca 500 --check-base --out runs/manual

# Live reference data (copy the base URL from the official Tokenized Stocks API reference):
BASE_TOKENIZED_STOCKS_API_URL=<api-base-url> python3 run.py run \
  --config config.example.json --portfolio data/demo_portfolio.json --api-url "$BASE_TOKENIZED_STOCKS_API_URL"
```

Or install as a package: `pip install -e .` then `stockpilot demo`.

## Architecture

```
src/stockpilot/
  models.py    Decimal-safe domain models (quotes, positions, policy, decisions)
  data.py      Fixture provider + Tokenized Stocks API client (pagination, error-tolerant)
  base_rpc.py  Read-only Base JSON-RPC (chain check, balanceOf -> share-equivalents)
  strategy.py  Transparent planner: drift math, sells-first funding, guardrail engine
  ledger.py    Simulated fills with fee/slippage assumptions + realized PnL vs avg cost
  audit.py     Append-only JSONL audit log + stable run fingerprint (reproducible demos)
  cli.py       demo / run commands, report.json + report.md rendering
```

## Safety & compliance posture

- **Not investment advice.** StockPilot executes a user's own written allocation policy; it does not recommend securities.
- **No custody, no keys, no execution** in this build. The roadmap's execution phase (below) is gated on legal review and uses user-approved smart-wallet limits.
- Tokenized stocks are securities issued under Regulation S and are **not offered to U.S. persons**; Coinbase's own note limits availability to eligible jurisdictions outside the U.S. The quest form likewise states that projects enabling trading for U.S. users are out of scope. Eligibility screening is the operator's responsibility and is called out in the product docs, not buried.
- The agent never claims token holders receive rights (e.g. voting rights) that the underlying asset does not provide.

## Roadmap

1. **Phase 1 — this repo:** paper agent, fixture + live read-only data, audit-grade explanations.
2. **Phase 2:** read-only wallet dashboard on Base (live API + `balanceOf` position sync, multiplier-aware share view, corporate-action alerts when `multiplier` changes).
3. **Phase 3 (only after legal review):** user-approved execution through a smart wallet with hard per-trade and daily limits, the same policy file and audit log driving real orders on Base Sepolia first.

## Why this fits the quest

- **Agentic Stock Finance, literally:** an autonomous agent doing portfolio finance over Base's tokenized-stock primitives (B20, Tokenized Stocks API, Chainlink NAV, on-chain multiplier).
- **Product quality:** correct handling of the two details most demos get wrong — NAV-is-a-reference-value (with staleness enforcement) and multiplier-adjusted share accounting.
- **Build in public:** this repository, its tests, and its recorded demo runs are the public artifact; the demo above is byte-for-byte reproducible (stable run fingerprint `c758c236958585e9`).

## License

MIT — see `LICENSE`.
