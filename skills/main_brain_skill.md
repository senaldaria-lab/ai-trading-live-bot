# MAIN BRAIN SKILL

## Role
The Main Brain is the central decision-making agent of the AI Trading System.
It aggregates all inputs and makes the final trading decision.

## Inputs

### Technical Inputs (evaluated every cycle)
- Reports from all coin agents (BTC, ETH, BNB, SOL, XRP, SUI)
- BTC market context (trend, dominance signal)
- ETH market context (alt-market proxy)
- News sentiment score from News Sentiment Agent
- Risk Manager approval or rejection of each candidate

### Strategic Inputs (from Deep Research — advisory context only)
- `deep_research_context`: current macro phase and market structure summary
- `coin_group_status`: which coin groups are STRONG / WEAK / DEAD this cycle
- `coins_to_watch`: coins approaching signal readiness — monitor but do not act yet
- `coins_to_pause`: coins flagged for suspended analysis — treat as AVOID
- `coins_to_blacklist`: coins that must not receive any signal regardless of technicals
- `strategic_risk_notes`: macro or regulatory risks that should modulate confidence

**Deep Research inputs are advisory only. They do NOT generate BUY or SELL decisions.
Main Brain uses them to modulate confidence_level and pre-filter coin candidates only.**

## Responsibilities

### 1. Aggregate Coin Reports
- Collect preliminary scores, SEL, timeframe_gate, and volume_status from each coin agent
- Note which coins passed preliminary local risk checks
- Rank candidates by preliminary score (highest first)
- Discard any coin whose SEL = INVALID before further processing

### 2. Apply Deep Research Context
- Check `coins_to_blacklist`: discard coin immediately — no signal issued regardless of score
- Check `coins_to_pause`: treat coin signals as WATCH at best regardless of technical score
- Check `coin_group_status`: if a coin's group is WEAK or DEAD, reduce confidence_level one tier
- Apply `strategic_risk_notes`: if macro risk is flagged, reduce confidence for all altcoins
- Check `deep_research_context` macro phase: if BEAR or DISTRIBUTION, suppress all BUY signals globally
- Note: Deep Research context modulates confidence_level and filtering only — it does NOT produce BUY or SELL decisions directly

### 3. Apply Market Context
- If BTC 4H trend is DOWN: downgrade all BUY signals one level
- If BTC 4H trend is UP: allow normal scoring
- If ETH is bleeding while BTC holds: flag altcoins as higher risk

### 4. Apply News Sentiment
- POSITIVE sentiment (score >= 0.6): allow BUY signals to proceed
- NEUTRAL sentiment (score 0.3–0.59): require stronger technical confirmation
- NEGATIVE sentiment (score < 0.3): suppress BUY signals; prefer HOLD or AVOID
- News sentiment is applied here (Main Brain) only — Risk Manager does not apply news sentiment

### 5. Apply Risk Manager Decision
- Only consider coins that Risk Manager has NOT blocked
- For downgraded signals, reduce position size recommendation
- Never override a Risk Manager block

### 6. Compare All Opportunities
- Score each remaining candidate across all dimensions:
  - Technical score (from coin agent)
  - SEL quality (STRONG adds weight; WEAK reduces weight)
  - Market context alignment
  - News sentiment multiplier
  - Risk-adjusted weight
  - Deep Research confidence modifier (from coin_group_status and strategic_risk_notes)
- Select only the top 1–3 safest, highest-quality setups

### 7. Make Final Decision
The Main Brain issues one of the following labels per coin:

| Label | Meaning |
|-------|---------|
| `STRONG_BUY` | Setup + trigger confirmed, all filters passed, SEL = STRONG |
| `BUY` | Good setup, acceptable risk, timeframe_gate PASS, SEL = STRONG or MODERATE |
| `WATCH` | Interesting setup but not ready; monitor closely |
| `HOLD` | No new action; existing position management only |
| `SELL` | Exit signal: 4H trend reversed to DOWNTREND + 1H BEARISH + MACD bearish cross + volume HIGH |
| `AVOID` | Risk too high, data unclear, blocked by Risk Manager, or blacklisted by Deep Research |

## Output Format

```yaml
symbol: BTCUSDT
final_decision: BUY
final_score: 78
confidence_level: MEDIUM
risk: LOW
market_status: RISK_ON
deep_research_context: "Bull accumulation phase; L1s leading; no blacklist flags"
timeframe_4h_trend: UPTREND
timeframe_1h_trend: BULLISH
timeframe_15m_trend: BULLISH
rsi: 58.1
macd_status: "Bullish crossover, histogram positive"
volume_status: HIGH
sel: STRONG
reason: "Strong 4H uptrend, EMA aligned, RSI 58, volume HIGH, news positive, no DR flags"
telegram_action: SEND
```

## Confidence Level Definition

| Level | Condition |
|-------|-----------|
| `HIGH` | final_score >= 80 AND risk is LOW or MEDIUM |
| `MEDIUM` | final_score 65–79 AND risk is not HIGH |
| `LOW` | final_score < 65 OR conditions are unclear OR risk is HIGH |

Confidence level is included in the Telegram Signal Agent payload.
Telegram formats the signal differently based on confidence_level.

## Hard Rules
- Never issue STRONG_BUY without Trade Setup + Trigger both confirmed and SEL = STRONG
- Never issue BUY in a negative news + BTC downtrend environment
- Never issue any BUY for a coin on `coins_to_blacklist` from Deep Research
- Always prefer WATCH over premature BUY
- Maximum 3 active signals at any time
- final_decision and confidence_level are both required fields — neither can be empty
- Final decision is forwarded to Telegram Signal Agent only — not executed
