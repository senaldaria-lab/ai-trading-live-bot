# NEWS SENTIMENT SKILL

## Role
The News Sentiment Agent reads, classifies, and scores crypto-relevant news.
It provides a sentiment signal that modulates the Main Brain's final decision.

## Inputs
- News headlines and summaries from configured news sources
- Social media sentiment (if available)
- Fear & Greed Index (if available)

## Classification Labels

| Label | Score Range | Meaning |
|-------|-------------|---------|
| `VERY_POSITIVE` | 0.80–1.00 | Strong bullish catalysts present |
| `POSITIVE` | 0.60–0.79 | Favorable news environment |
| `NEUTRAL` | 0.30–0.59 | No strong directional sentiment |
| `NEGATIVE` | 0.10–0.29 | Bearish news or uncertainty |
| `VERY_NEGATIVE` | 0.00–0.09 | Crisis, crash risk, regulatory attack |

## Scoring Method

### Step 1 — Headline Scan
- Collect last 10–20 headlines relevant to crypto (BTC, ETH, altcoins)
- Flag keywords: "ETF", "regulation", "ban", "hack", "crash", "adoption", "partnership", "upgrade"

### Step 2 — Classify Each Headline
- Bullish keyword hit: +1
- Bearish keyword hit: -1
- Neutral / unclear: 0

### Step 3 — Aggregate Score
- Sum scores, normalize to 0.0–1.0 range
- Weight recent headlines (< 2 hours) double

### Step 4 — Fear & Greed Adjustment
- Fear & Greed > 70 (Greed): add +0.05
- Fear & Greed < 30 (Fear): subtract -0.05
- Extreme readings override: Fear < 15 → cap sentiment at 0.2

## Output Format

```yaml
news_status: POSITIVE
btc_news_status: POSITIVE
eth_news_status: NEUTRAL
binance_news_status: NEUTRAL
macro_status: NEUTRAL
regulation_status: CLEAR
sentiment_score: 0.72
risk_notes: "No major risk events detected this cycle"
recommendation_for_main_brain: "Sentiment supports BUY signals; altcoins may follow BTC strength"
```

Allowed `news_status` values:
- `POSITIVE` — score >= 0.60; BUY signals may proceed
- `NEUTRAL` — score 0.30–0.59; require stronger technical confirmation
- `NEGATIVE` — score 0.10–0.29; suppress BUY signals
- `DANGER` — score < 0.10 or active crisis / extreme fear; suppress all BUY and STRONG_BUY globally

Allowed `regulation_status` values:
- `CLEAR` — no active enforcement events
- `WATCH` — minor uncertainty or pending ruling
- `ALERT` — active lawsuit, ban warning, or enforcement action in progress

## Hard Rules
- News sentiment alone cannot trigger a BUY
- Very Negative sentiment suppresses all BUY and STRONG_BUY signals globally
- Sentiment is re-evaluated every 30 minutes minimum
- Do NOT send Telegram messages directly — output goes to Main Brain only
