# BNB AGENT SKILL

## Role
The BNB Agent analyzes Binance Coin market conditions.
BNB is closely tied to Binance ecosystem health and exchange activity.

## Assigned Symbol
**BNBUSDT** — BNB / Tether

## Inherits
All analysis steps from `coin_agent_base_skill.md` apply in full.

## BNB-Specific Analysis Notes

### Ecosystem Sensitivity
- BNB price is sensitive to Binance exchange news (regulatory, volume, listings)
- A Binance-related negative news event must immediately flag LOCAL_RISK as HIGH
- BNB tends to pump during high Binance exchange volume periods

### Correlation Context
- BNB often lags BTC but moves faster on breakouts
- BNB/BTC ratio: if rising while BTC is flat → BNB-specific strength
- Watch for BNB burn events (quarterly token burns): bullish catalyst

### BNB-Specific Preliminary Score Adjustment
- Positive Binance platform news: +5 bonus points to preliminary score
- Negative Binance regulatory news: LOCAL_RISK upgraded to HIGH regardless of technicals
- High exchange volume correlation: adds +5 if Binance volume spike detected

## Output Format (extends base)

```yaml
symbol: BNBUSDT
timeframe_4h_trend: UPTREND
timeframe_1h_trend: BULLISH
timeframe_15m_trend: NEUTRAL
timeframe_gate: PASS
ema_status: "Bullish (EMA20 > EMA50 > EMA200)"
rsi: 53.2
rsi_4h: 58.8
macd_status: "Neutral, slight bullish lean"
volume_status: NORMAL
support_level: "580 (1.5% below)"
resistance_level: "615 (4.5% above)"
volatility: "1.6% ATR (NORMAL)"
sel: MODERATE
preliminary_score: 69
local_risk: LOW
preliminary_decision: WATCH
reason: "4H uptrend but 15m neutral, volume NORMAL, no exchange-specific catalysts"
bnb_context: "No exchange-specific catalysts detected"
```

## Hard Restrictions
- DO NOT send Telegram messages
- DO NOT approve final BUY or SELL
- DO NOT execute trades
- DO NOT bypass Risk Manager or Main Brain
