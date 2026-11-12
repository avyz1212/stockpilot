# Base Stocks Maxxing Builder Quest — Submission pack: StockPilot

**Project:** StockPilot — an explainable, guardrailed tokenized-stock agent for Base
**Track:** Agentic Stock Finance
**Repo (local, ready to push):** `~/workspace/base-stocks/repo/`
**Status:** prototype built and verified 2026-11-13 (inside the Quest build window, Nov 13 – Dec 5). Tests: 13/13 pass. Demo run recorded in `repo/docs/sample-run.md`.

---

## 1. What a complete submission requires (official rules, verified 2026-11-13)

Source: https://www.base.org/stocksmaxxing and https://www.base.org/stocksmaxxing/rules

A Submission is complete only when ALL of these are done:

1. **A public post on X** with a **video demo** of the project (e.g. a Loom recording) explaining how it works, **tagging @buildonbase**.
2. **The official submission form** (Google Form linked from the quest page "Apply Now"):
   https://docs.google.com/forms/d/1zotYvkeAtDjR2MKk3qNxyNIAfJ_IPQtzTtjNhOAF8js/viewform
   — include the X post link, the Track(s) entered, and the other requested info. *"A Submission is not complete until Sponsor receives the Submission Form."*
3. Any extra requirements in the Track section (Agentic Stock Finance) on the quest page.

Key rules facts:

- Quest period **Nov 5 – Dec 5, 2026**; the form header says **ends December 5, 2026, 11:59pm EST** (= Dec 6, 11:59 WIB). Rules say times are UTC unless the page says otherwise (Dec 5 23:59 UTC = Dec 6, 06:59 WIB). **Submit by Dec 4, 2026 to be safe under both readings.**
- **No purchase, transaction, wallet funding, token holding, or payment of any kind is required.** Testnet builds are explicitly allowed and "will not be judged less favorably."
- One submission per entrant/team per track; a project may win in only one track. Teams up to 5; individuals 18+; not residents of OFAC-sanctioned countries.
- Prizes are per-track (amounts in each Track section on the quest page), paid in **USDC on Base** within ~30 days after winner verification.
- **Winner verification (if selected): respond within 7 days** of first notification (email / X DM / form contact) with ID/age/residence proof, sanctions screening, IRS Form W-9 or **W-8 (W-8BEN for non-US)** or local equivalent, a compatible wallet address, and a signed eligibility/liability/publicity declaration. Failure = forfeiture.
- Form header warning: **"Any projects that enable trading for U.S. users are not in scope"** and winners are subject to identity verification + tax obligations. Do NOT put sensitive info (SSN, passwords) in the form.
- Judging (official rules §7): eligibility/compliance screening, then a judge panel scores against the criteria on the quest page. Launch coverage reports the weights as 50% traction (real onchain usage), 25% product quality, 25% build-in-public, plus a $6,000 prize for the best project built entirely in the open — treat as reported, not verbatim from the rules page.

**No Base/Coinbase account or registration is needed to enter** — only the X post + the Google Form.

---

## 2. Ready-to-paste form fields

| Field | Value |
|---|---|
| Project name | StockPilot |
| Track | Agentic Stock Finance |
| Team representative | Adzi Hadzmi |
| Contact email | adzihadzmi@gmail.com |
| X handle | @Th3_Bestt |
| GitHub repo | `<FILL AFTER PUSH: https://github.com/avyz1212/stockpilot>` |
| X post link | `<FILL AFTER POSTING>` |
| Demo video | (attached to / linked from the X post) |
| What was built during the Quest Period | The entire StockPilot prototype was designed and built during the Quest build window (from Nov 13, 2026): the policy engine, guardrails, Tokenized Stocks API client, read-only Base RPC reader, simulated ledger, audit log, CLI, tests, and docs in this repository. No pre-existing product code was reused. |

**Short description (~280 chars):**

> StockPilot is an explainable agent for tokenized stocks on Base: it rebalances a B20 stock basket to a user-written policy, refuses to buy on stale NAV data, applies the on-chain multiplier for true share accounting, and logs every decision with its reasons. Paper-mode first, kill switch built in.

**Long description (~1,200 chars):**

> Tokenized stocks on Base trade 24/7, but their reference price is a Chainlink NAV that goes stale outside market hours, and every B20 token carries an on-chain multiplier that changes with splits and dividends. Black-box trading bots are the wrong answer to both problems. StockPilot is a rules-first agent: the user writes a JSON policy (target weights, tolerance band, concentration and per-run caps, cash reserve floor, blocked symbols, kill switch), and the agent does the rest — loading reference data in the schema of Base's public Tokenized Stocks API, checking the network with read-only Base RPC, planning sells before buys, and explaining every BUY / SELL / HOLD / BLOCKED decision with the arithmetic behind it. Buys are refused on stale NAV, paused tokens are never touched, sells can never exceed holdings, and every run emits a JSONL audit log plus JSON/Markdown reports. This build is simulation-first by design: fills are modelled at NAV with explicit fee/slippage assumptions and stamped SIMULATED; no wallet, no keys, nothing is signed. The roadmap adds read-only wallet position sync (balanceOf × multiplier share view) and, only after legal review, user-approved execution via a smart wallet with hard limits — Base Sepolia first.

**Base integration (if asked):** Base mainnet B20 tokenized stocks; public Tokenized Stocks API (reference data, multiplier, paused features); read-only Base JSON-RPC (chain identity, ERC-20 balanceOf for position sync); Chainlink NAV semantics (staleness-aware).

**Traction (honest):** Early prototype built in the open during the quest window: public repo, 13 passing tests, byte-reproducible demo run with a stable run fingerprint. No users or onchain volume yet — the growth path is the Phase 2 read-only dashboard (wallet position sync) promoted via build-in-public posts.

---

## 3. X post draft (must tag @buildonbase and include the video)

Main post:

> Meet StockPilot 🤖📈 — my entry for the @buildonbase Stocks Maxxing quest (Agentic Stock Finance).
>
> An agent that rebalances a basket of tokenized stocks on Base to YOUR written policy — and explains every decision. It refuses to buy on stale NAV data, applies the B20 multiplier for true share accounting, and has a kill switch.
>
> Demo 👇 Repo in the replies.

Thread / reply 2:

> How it works:
> 1. You write a policy: target weights, tolerance band, caps, cash floor, blocked symbols
> 2. StockPilot loads reference data in Base's Tokenized Stocks API schema + checks Base via read-only RPC
> 3. Every asset gets a decision — BUY / SELL / HOLD / BLOCKED — with the math shown
> 4. Fills are simulated (paper mode), every run writes a full audit log

Reply 3:

> Guardrails I'm proudest of: stale-NAV buy block (tokenized-stock NAVs freeze outside market hours), paused-token block, no shorting, per-run trade caps, and a one-flag kill switch.
>
> Code (MIT): <REPO LINK>
> Built solo during the quest window. Feedback welcome 🙏

*(Note: post from @Th3_Bestt himself — his account, his call on timing; he has flagged X suspension risk from posting too frequently in one day.)*

---

## 4. Demo video script (60–90 seconds, Loom or screen record)

1. **(0:00–0:10)** Open the repo README. Say: "StockPilot is an explainable agent for tokenized stocks on Base. No black box — every decision comes with its reasons."
2. **(0:10–0:25)** Show `config.example.json`: "This is the whole strategy — a policy the user writes: target weights, a 3% tolerance band, caps, a cash floor, blocked symbols, and a kill switch."
3. **(0:25–0:55)** Terminal: run `python3 run.py demo`. Walk the output: NVDAc overweight → SELL; AAPLc/GOOGLc underweight → BUY (note GOOGLc's 1.02 multiplier); TSLAc BLOCKED because its NAV is 48 hours old; COINc BLOCKED (paused); METAc/MSFTc HOLD inside the band.
4. **(0:55–1:15)** Open `runs/demo/report.md` and `audit.jsonl`: "Every run produces this report and a full audit log. Fills are simulated and stamped as such — NAV is a reference value, not an execution price, and the product says so everywhere."
5. **(1:15–1:30)** Close on the roadmap slide in the README: "Next: read-only wallet sync on Base, then user-approved execution with hard limits after legal review. Built for the Agentic Stock Finance track."

Recording steps: open a terminal in `repo/`, run the two commands from README ("Run it"), keep the fixture demo (works offline, deterministic).

---

## 5. Exact remaining steps for the user (nothing else is needed from him)

1. **Publish the repo** — create a public GitHub repo (suggested: `github.com/avyz1212/stockpilot`) and push `~/workspace/base-stocks/repo/` — or tell Muse "push it" and Muse will push via the browser like the NEAR repo (he may need to approve a GitHub 2FA prompt).
2. **Record the demo video** (script above, ~90 seconds, Loom is fine).
3. **Post on X** from @Th3_Bestt with the video attached, tagging **@buildonbase**, then add the repo-link replies.
4. **Submit the Google Form** (link in §1) with the X post URL + Track = Agentic Stock Finance — **target Dec 4, 2026; hard deadline Dec 5, 2026**.
5. **Only if contacted as a potential winner:** reply within 7 days and complete verification (ID, W-8BEN, Base wallet address for USDC — his supervised EVM wallet `0x622e4A9d26a73120Bcce965Cc269AE3bAB5e0400` works as a Base address).

No funds, no KYC, no wallet connection are needed for steps 1–4.

---

## 6. What was verified in this build (evidence)

- `python3 -m unittest discover -s tests` → **13 tests, OK** (valuation/multiplier math, rebalance direction, band HOLD, stale-NAV buy block, kill switch, paused block, no-shorting cap, min-trade HOLD, simulated ledger accounting, Base RPC reader incl. balanceOf calldata, API pagination + omitted fields).
- `python3 run.py demo` → completes offline; decisions/fills identical across repeated runs (stable run fingerprint `c758c236958585e9`); outputs in `repo/runs/demo/`, copies in `repo/docs/`.
- `--check-base` performs a live read-only Base RPC check and degrades gracefully (from this sandbox on 2026-11-13, `mainnet.base.org` returned HTTP 403 — recorded as `reachable: false` in the report rather than crashing or being faked).
- Hard gates respected: no real funds, no mainnet transactions, no KYC, no keys/seeds anywhere in the repo.
