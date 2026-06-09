# MONTHLY COIN REVIEW SKILL

## Purpose
This skill defines the monthly review process that Deep Research runs to
evaluate all active coin agents, watchlist candidates, and emerging opportunities.

The monthly review is the only process that can:
- Add a new coin agent
- Pause an existing coin agent
- Blacklist a coin
- Promote a watchlist coin to active agent status
- Remove a coin from the blacklist

---

## Review Frequency
- Full review: once per month (first Monday of each month)
- Emergency review: triggered immediately if any of these occur:
  - A coin drops > 30% in 24H with no recovery
  - A blacklist-trigger event is detected mid-month
  - A major new coin launches with strong narrative and volume
  - BTC dominance shifts > 5% in one week (macro regime change)

---

## Monthly Review Process

### Phase 1 — Active Agent Audit (Days 1–2)
Re-run all 7 mandatory gates from `coin_selection_rules.md` for every active agent.

For each active coin:
1. Check Binance Spot listing status
2. Measure 30-day average daily volume
3. Check order book depth
4. Measure 30-day average ATR%
5. Check regulatory status update
6. Check delisting notices
7. Confirm 6-month history still valid

Output per active coin:
```yaml
symbol: SOLUSDT
gate_results:
  binance_spot: PASS
  min_liquidity: PASS
  order_book: PASS
  volatility_range: PASS
  regulatory: PASS
  no_delisting: PASS
  price_history: PASS
gates_passed: 7/7
scoring_total: 82/100
monthly_verdict: KEEP_AGENT
```

### Phase 2 — Watchlist Evaluation (Days 2–3)
For every coin on the watchlist:
1. Run all 7 mandatory gates
2. If all gates pass AND scoring >= 70: recommend `ADD_AGENT`
3. If gates pass but scoring 50–69: remain on watchlist
4. If any gate fails: remain on watchlist (or blacklist if trigger hit)

### Phase 3 — Market Scan for New Candidates (Days 3–4)
Scan Binance Spot top 50 coins by 30-day volume that are NOT already tracked.

Filter criteria:
- Must be in top 50 by volume
- Must pass all 7 mandatory gates
- Must score >= 60 to enter watchlist
- Must score >= 70 to be recommended as new agent

### Phase 4 — Narrative Assessment (Days 4–5)
Evaluate which narratives are active, rising, or dying this month:
- Review crypto news sources for dominant themes
- Cross-reference with coin group scoring from `coin_group_research_skill.md`
- Update `strong_coin_groups` and `weak_coin_groups` in output

### Phase 5 — Compile Monthly Report (Day 5)
Produce the full Deep Research output in the format defined in `deep_research_skill.md`.

---

## Monthly Report Output Template

```yaml
review_date: "YYYY-MM-DD"
review_type: "MONTHLY / EMERGENCY"
reviewed_by: "Deep Research Agent"

active_agent_audit:
  - symbol: BTCUSDT
    gates_passed: 7/7
    score: 98/100
    verdict: KEEP_AGENT

  - symbol: ETHUSDT
    gates_passed: 7/7
    score: 94/100
    verdict: KEEP_AGENT

  - symbol: BNBUSDT
    gates_passed: 7/7
    score: 80/100
    verdict: KEEP_AGENT

  - symbol: SOLUSDT
    gates_passed: 7/7
    score: 82/100
    verdict: KEEP_AGENT

  - symbol: XRPUSDT
    gates_passed: 6/7
    score: 65/100
    failed_gate: regulatory
    verdict: WATCH — regulatory gate marginal

  - symbol: SUIUSDT
    gates_passed: 7/7
    score: 71/100
    verdict: KEEP_AGENT — monitor volume closely

watchlist_evaluation:
  - symbol: AVAXUSDT
    gates_passed: 7/7
    score: 68/100
    verdict: WATCHLIST — score not yet at 70 threshold

  - symbol: APTUSDT
    gates_passed: 5/7
    failed_gates: [min_liquidity, order_book]
    verdict: WATCHLIST — liquidity insufficient

new_candidates:
  - symbol: XXXX
    gates_passed: 7/7
    score: 74/100
    verdict: ADD_WATCHLIST — monitor one month before agent

market_summary:
  macro_phase: "Accumulation"
  btc_dominance_trend: "Stable"
  leading_sector: "L1s and AI tokens"
  market_narrative: "Institutional BTC adoption, ETH staking growth"

strong_coin_groups:
  - "Layer 1s (BTC, ETH, SOL)"
  - "AI-adjacent tokens"

weak_coin_groups:
  - "Gaming tokens"
  - "Low-cap DeFi"

coins_to_keep: [BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, SUIUSDT]
coins_to_add: []
coins_to_watch: [XRPUSDT, AVAXUSDT]
coins_to_pause: []
coins_to_blacklist: []

risk_notes:
  - "XRP regulatory gate borderline — reassess in 2 weeks"
  - "SUI volume is at minimum threshold — watch closely"
  - "Macro: Fed meeting this month may cause volatility spike"

recommendation_for_main_brain:
  - "Maintain all 6 active agents with standard operation"
  - "Reduce altcoin exposure if BTC dominance rises above 58%"
  - "Flag XRP signals for extra Risk Manager scrutiny this month"
```

---

## Escalation Protocol

If during monthly review a critical risk is discovered mid-cycle:

| Event | Action |
|-------|--------|
| Blacklist trigger detected | Immediate Deep Research emergency report to Main Brain |
| Active agent coin drops > 30% | Flag to Main Brain; Risk Manager auto-blocks signals |
| New high-conviction opportunity | Add to watchlist; full agent requires next monthly gate |
| Macro regime change (BTC dom +5%) | Emergency narrative reassessment within 48H |

---

## Hard Restrictions
- Monthly review output is sent to Main Brain as advisory context only
- Deep Research cannot directly pause or add coin agents — it recommends only
- Main Brain acknowledges the recommendation and applies it to the agent roster
- No coin is added as an active agent mid-month (except via emergency review)
- Blacklist decisions are permanent until the 60-day clean period elapses
