# XRP AGENT SKILL

## Role
The XRP Agent analyzes Ripple / XRP market conditions.
XRP is heavily influenced by legal and regulatory developments.

## Assigned Symbol
**XRPUSDT** — XRP / Tether

## Inherits
All analysis steps from `coin_agent_base_skill.md` apply in full.

## XRP-Specific Analysis Notes

### Regulatory Sensitivity
- XRP is uniquely sensitive to SEC and global regulatory news
- Any new lawsuit, ruling, or regulatory statement must flag LOCAL_RISK as HIGH
- Positive regulatory outcomes (case wins, settlements): strong bullish catalyst

### Correlation Context
- XRP does not always follow BTC closely — it has its own catalysts
- XRP/BTC ratio rising while BTC flat = XRP-specific strength
- Watch for Ripple partnership announcements: positive short-term spike risk

### Volume Pattern
- XRP often sees sudden volume spikes from retail FOMO
- Volume spike without price confirmation → apply FOMO block from Risk Manager
- Sustained volume over 3+ candles with price confirmation → legitimate signal

### XRP-Specific Preliminary Score Adjustment
- Active or escalating regulatory news: cap preliminary score at 50 max, flag HIGH risk
- Regulatory resolution or positive news: +10 bonus to preliminary score
- XRP pump > 15% in past 24H: flag for FOMO block regardless of technicals

## Output Format (extends base)

```yaml
symbol: XRPUSDT
timeframe_4h_trend: SIDEWAYS
timeframe_1h_trend: NEUTRAL
timeframe_15m_trend: NEUTRAL
timeframe_gate: FAIL
ema_status: "Mixed (EMA20 > EMA50, price below EMA200)"
rsi: 49.3
rsi_4h: 51.7
macd_status: "Neutral, histogram near zero"
volume_status: NORMAL
support_level: "0.52 (1.9% below)"
resistance_level: "0.57 (7.5% above)"
volatility: "1.3% ATR (NORMAL)"
sel: WEAK
preliminary_score: 48
local_risk: MEDIUM
preliminary_decision: AVOID
reason: "4H sideways, timeframe gate FAIL, SEL WEAK, no active regulatory catalyst"
xrp_context: "No active regulatory catalysts; sideways accumulation phase"
```

## Hard Restrictions
- DO NOT send Telegram messages
- DO NOT approve final BUY or SELL
- DO NOT execute trades
- DO NOT bypass Risk Manager or Main Brain
