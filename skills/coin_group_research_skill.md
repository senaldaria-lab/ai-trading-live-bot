# COIN GROUP RESEARCH SKILL

## Role
This skill defines how the Deep Research Agent groups, scores, and ranks
coin categories to identify which groups deserve active agent coverage
and which should be deprioritized or avoided.

---

## Coin Group Taxonomy

### Tier 1 — Market Anchors
Always covered regardless of narrative cycle.

| Symbol | Category | Why Always Covered |
|--------|----------|--------------------|
| BTCUSDT | Store of Value | Market anchor, sentiment driver |
| ETHUSDT | Smart Contract L1 | Altcoin proxy, ecosystem anchor |

### Tier 2 — Core Altcoins (Active Agents When Healthy)

| Symbol | Category |
|--------|----------|
| BNBUSDT | CEX Token / BSC L1 |
| SOLUSDT | High-Performance L1 |
| XRPUSDT | Payments / XRP Ledger |
| SUIUSDT | Next-Gen L1 |

### Tier 3 — Watchlist Candidates (Agent Only If Criteria Met)
Evaluated monthly by Deep Research. Require all gates to pass before agent is added.

Examples: AVAXUSDT, DOTUSDT, LINKUSDT, APTUSDT, INJUSDT, TIAUSDT, STXUSDT

### Tier 4 — Research-Only (Never Get Dedicated Agents)
Narrative coins, memes, micro-caps. Monitored for macro sentiment only.

Examples: MEME tokens, gaming tokens with < $20M daily volume

---

## Group Scoring Criteria

For each group or coin category, score across 5 dimensions (0–20 each, max 100):

### 1. Liquidity Score (0–20)
- 24H Binance Spot volume > $500M: 20
- $100M–$499M: 15
- $50M–$99M: 10
- $20M–$49M: 5
- < $20M: 0

### 2. Narrative Strength Score (0–20)
- Active narrative with institutional interest: 20
- Growing narrative, retail interest: 15
- Stable but quiet narrative: 10
- Fading narrative: 5
- Dead or negative narrative: 0

### 3. Volatility Suitability Score (0–20)
- Daily ATR 1–3%: 20 (ideal for swing trading)
- Daily ATR 3–5%: 15 (manageable)
- Daily ATR 5–8%: 10 (elevated, reduced size needed)
- Daily ATR > 8%: 5 (high risk, requires strong setup)
- Extreme volatility or halted: 0

### 4. Regulatory Safety Score (0–20)
- No known regulatory risk: 20
- Minor uncertainty only: 15
- Active investigation or gray area: 10
- Ongoing lawsuit or warning: 5
- Active enforcement action: 0

### 5. Market Cycle Alignment Score (0–20)
- Coin is in the leading sector this cycle: 20
- Coin is in a recovering sector: 15
- Coin is neutral / sector-agnostic: 10
- Coin is in a lagging sector: 5
- Coin is in a dying sector: 0

---

## Group Evaluation Output

```yaml
group_evaluation:
  - group: "Layer 1s"
    coins: [BTCUSDT, ETHUSDT, SOLUSDT, SUIUSDT]
    liquidity_score: 18
    narrative_score: 20
    volatility_score: 15
    regulatory_score: 18
    cycle_alignment: 20
    total_score: 91/100
    verdict: STRONG — maintain all agents

  - group: "CEX Tokens"
    coins: [BNBUSDT]
    liquidity_score: 17
    narrative_score: 14
    volatility_score: 18
    regulatory_score: 14
    cycle_alignment: 15
    total_score: 78/100
    verdict: HEALTHY — keep agent

  - group: "Payments"
    coins: [XRPUSDT]
    liquidity_score: 15
    narrative_score: 12
    volatility_score: 16
    regulatory_score: 10
    cycle_alignment: 12
    total_score: 65/100
    verdict: WATCHLIST — monitor regulatory closely
```

---

## Group Verdict Rules

| Total Score | Verdict |
|-------------|---------|
| 80–100 | STRONG — prioritize, maintain all agents |
| 60–79 | HEALTHY — keep agents, standard monitoring |
| 40–59 | WATCHLIST — no new agents; review monthly |
| 20–39 | WEAK — pause agents, move to watchlist |
| 0–19 | AVOID — blacklist candidates; no coverage |

---

## Hard Restrictions
- This skill is research only — no signals, no trades
- Group scores feed Deep Research output only
- Main Brain receives group context as strategic advisory, not as trade commands
