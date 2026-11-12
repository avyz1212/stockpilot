# StockPilot run c758c236958585e9

- Mode: **simulate** (all fills simulated)
- Data: fixture:base_snapshot.fixture.json @ 2026-11-13T15:00:00+00:00
- Portfolio value: 11127.54 -> 11622.92760190561008762269715 USD (reference NAV)

## Decisions (every one explained)

| Symbol | Action | Amount USD | Current -> Target | Why |
|---|---|---|---|---|
| AAPLc | BUY | 934.708000000000000000000000 | 0.1196125749728661436554937674 -> 0.2 | weight 11.96% vs target 20.00% (drift -8.04%); NAV reference 231.80 (age 1.0h, multiplier 1)<br>buy 934.708000000000000000000000 USD toward target (per-run cap 1162.754 USD; cash budget 2958.843538800000000000000000 USD) |
| AMZNc | HOLD | 0 | 0 -> 0 | weight 0.00% vs target 0.00% (drift 0.00%); NAV reference 238.15 (age 1.0h, multiplier 1)<br>inside the 3.00% tolerance band; no action |
| COINc | BLOCKED | 0 | 0 -> 0 | token reports paused features ['MINT']; no trading<br>Guardrails: paused_features |
| GOOGLc | BUY | 470.455600000000000000000000 | 0.09953954146792872783065033532 -> 0.14 | weight 9.95% vs target 14.00% (drift -4.05%); NAV reference 289.35 (age 2.0h, multiplier 1.02)<br>buy 470.455600000000000000000000 USD toward target (per-run cap 1162.754 USD; cash budget 2958.843538800000000000000000 USD) |
| METAc | HOLD | 0 | 0.1027216418950182067746058066 -> 0.1 | weight 10.27% vs target 10.00% (drift 0.27%); NAV reference 597.20 (age 0.5h, multiplier 1)<br>inside the 3.00% tolerance band; no action |
| MSFTc | HOLD | 0 | 0.1322136926641404802735574335 -> 0.16 | weight 13.22% vs target 16.00% (drift -2.78%); NAV reference 512.44 (age 3.0h, multiplier 1)<br>inside the 3.00% tolerance band; no action |
| NVDAc | SELL | 440.6611999999999999999999999 | 0.2578980592627503324004905595 -> 0.22 | weight 25.79% vs target 22.00% (drift 3.79%); NAV reference 187.42 (age 1.0h, multiplier 1)<br>sell 440.661200000000000000000000 USD toward target (capped by per-run cap 1162.754 USD and holdings 2998.72 USD) |
| SPCXc | BLOCKED | 0 | 0 -> 0 | SPCXc is on the user's blocked-symbol list<br>Guardrails: blocked_symbol |
| TSLAc | BLOCKED | 0 | 0.02140607557574517051758153487 -> 0.08 | weight 2.14% vs target 8.00% (drift -5.86%); NAV reference 248.90 (age 48.0h, multiplier 1)<br>NAV is stale (age 48.0h > limit 24h); buys are refused on stale data<br>Guardrails: stale_nav_no_buy |

## Simulated fills

| Symbol | Side | Tokens | Fill price (modelled) | Fee USD | Realized PnL |
|---|---|---|---|---|---|
| NVDAc | SELL | 2.354728336235010930652728639 | 187.138870 | 0.440661200000000000000000 | 34.47056199946061446240430969 |
| AAPLc | BUY | 4.026350465673362260319615486 | 232.147700 | 0.934708000000000000000000 | 0 |
| GOOGLc | BUY | 1.623469754759600706077569321 | 289.784025 | 0.470455600000000000000000 | 0 |

## Base network check (read-only)

```json
{
  "rpc_url": "https://mainnet.base.org",
  "reachable": false,
  "error": "HTTP Error 403: Forbidden"
}
```

## Disclaimers

- Prototype for the Base Stocks Maxxing Builder Quest (Agentic Stock Finance track).
- Not investment advice. Tokenized stocks are securities; eligibility and local law are the user's responsibility.
- NAV values are Chainlink-based reference values, not live bid/ask or execution prices.
- All fills in this build are SIMULATED. No wallet, no keys, no transaction was signed or broadcast.
