# COIN SELECTION RULES

## Purpose
This file defines the hard rules and minimum thresholds a coin must meet
before it receives a dedicated coin agent. These rules are enforced by
Deep Research and cannot be overridden by any other agent.

---

## Mandatory Gate Checks (All Must Pass)

A coin FAILS selection if it fails ANY single gate below.
There is no partial credit — all gates are binary PASS / FAIL.

### Gate 1 — Binance Spot Listing
- PASS: Coin is actively traded on Binance Spot with a USDT pair
- FAIL: Coin is not on Binance Spot, or pair is inactive / delisted

### Gate 2 — Minimum Liquidity
- PASS: 24H trading volume on Binance Spot >= $50M USDT (consistent over 7 days)
- FAIL: Volume below threshold or volume is spike-only (not sustained)

### Gate 3 — Order Book Depth
- PASS: Top 10 bid/ask spread <= 0.1% of price; no thin order book
- FAIL: Wide spreads, thin book, signs of low market maker participation

### Gate 4 — Volatility Range
- PASS: Daily ATR between 1% and 8% of price
- FAIL: ATR < 1% (too flat, no opportunity) or ATR > 8% (too dangerous)

### Gate 5 — No Active Regulatory Enforcement
- PASS: No active SEC lawsuit, government ban, or exchange enforcement action
- FAIL: Coin is subject to an active lawsuit, ban warning, or enforcement order

### Gate 6 — No Delisting Risk
- PASS: No Binance delisting notice in the past 90 days
- FAIL: Any delisting notice or warning flag present

### Gate 7 — Price History
- PASS: Coin has at least 6 months of trading history on Binance
- FAIL: Newly listed (< 6 months) — too little data for reliable technical analysis

---

## Scoring Gates (Used to Rank Coins That Passed All Hard Gates)

After passing all 7 mandatory gates, coins are scored for priority ranking:

| Criteria | Points |
|----------|--------|
| 24H volume > $500M | +20 |
| 24H volume $100M–$499M | +15 |
| 24H volume $50M–$99M | +10 |
| Strong active narrative | +20 |
| Bullish market cycle alignment | +15 |
| Clean regulatory status | +15 |
| ATR in 1–3% ideal range | +15 |
| Consistent volume (not spike-only) | +15 |
| **Maximum** | **100** |

Coins scoring >= 70: eligible for dedicated coin agent
Coins scoring 50–69: watchlist status
Coins scoring < 50: no coverage

---

## Blacklist Criteria (Immediate, No Review)

A coin is blacklisted immediately if ANY of the following are true:
- Active SEC enforcement action or government ban
- Suspected wash trading (volume/price ratio anomaly > 10x peers)
- Binance delisting notice issued
- Rug pull, hack, or exploit > 10% of supply
- Coin has no verifiable team or on-chain activity for > 30 days
- Price manipulation pattern confirmed (abnormal pump > 50% in < 24H with no news)

Blacklisted coins are logged in Deep Research output under `coins_to_blacklist`.
Blacklist status is reviewed monthly — a coin may be removed from blacklist
only after 60 days clean with full gate re-evaluation.

---

## Watchlist Rules

A coin enters the watchlist if:
- It passes Gates 1–7 but scores 50–69 in the scoring phase
- It previously had an agent but was paused (pending recovery)
- It is a new listing completing its 6-month history requirement

Watchlist coins:
- Are re-evaluated monthly by Deep Research
- Do NOT receive a dedicated coin agent
- DO NOT generate technical analysis reports
- Are flagged to Main Brain as "monitor — not yet ready"

---

## Pause Rules

An active coin agent is paused (not deleted) when:
- 24H volume drops below $30M for 5 consecutive days
- Coin narrative collapses with no recovery catalyst in sight
- Regulatory risk increases to ACTIVE status
- Binance issues a watchlist or margin removal notice

Paused agents are reviewed at the next monthly Deep Research cycle.
Resumption requires passing all 7 mandatory gates again.

---

## Current Active Coin Agents (As of Setup)

| Symbol | Status | Notes |
|--------|--------|-------|
| BTCUSDT | ACTIVE | Market anchor — never paused |
| ETHUSDT | ACTIVE | Altcoin proxy — never paused |
| BNBUSDT | ACTIVE | CEX token — monitor regulatory |
| SOLUSDT | ACTIVE | High-beta L1 — monitor volume |
| XRPUSDT | ACTIVE | Regulatory watch — monitor SEC |
| SUIUSDT | ACTIVE | New L1 — strict liquidity gate applies |

---

## Hard Restrictions
- These rules are enforced by Deep Research only
- Coin agents do not self-select or self-add
- Main Brain cannot add a coin agent without Deep Research clearance
- Risk Manager cannot override a blacklist decision
- No coin bypasses the 7 mandatory gates under any circumstance
