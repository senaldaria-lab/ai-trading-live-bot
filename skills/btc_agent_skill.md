# BTC AGENT SKILL

## Role
The BTC Agent is the market-context anchor of the entire system.
Bitcoin dominance and trend direction serve as the global filter for all other coin agents.

## Assigned Symbol
**BTCUSDT** — Bitcoin / Tether

## Inherits
All analysis steps from `coin_agent_base_skill.md` apply in full.

## BTC-Specific Context Duties

### Market Context Output
In addition to the standard coin report, BTC Agent must output:
- BTC 4H trend direction (used by Main Brain to adjust all other signals)
- BTC dominance direction (if available): rising = altcoins under pressure
- Key BTC levels: major support, major resistance, current position within range
- BTC sentiment tag: `RISK_ON` / `RISK_OFF` / `NEUTRAL`

### BTC Sensitivity Rules
- BTC is the strongest signal in the system
- If BTC is in confirmed DOWNTREND (4H), Main Brain will suppress altcoin BUY signals
- If BTC is consolidating above key support with volume, tag as `RISK_ON`
- If BTC is breaking below support with volume, tag as `RISK_OFF`

### Extended Indicators for BTC
- Check weekly EMA200 level as long-term baseline
- Note whether price is above or below the 2024–2025 bull market channel
- If BTC RSI (daily) > 80: tag as overextended, flag for Risk Manager

## BTC-Specific Preliminary Score Adjustment
- BTC is weighted more heavily than altcoins in Main Brain ranking
- A BTC PRELIMINARY_BUY with score >= 70 can trigger global RISK_ON context
- A BTC AVOID with score < 40 triggers global RISK_OFF context

## Output Format (extends base)

```yaml
symbol: BTCUSDT
timeframe_4h_trend: UPTREND
timeframe_1h_trend: BULLISH
timeframe_15m_trend: BULLISH
timeframe_gate: PASS
ema_status: "Bullish (EMA20 > EMA50 > EMA200)"
rsi: 58.1
rsi_4h: 63.4
macd_status: "Bullish crossover, histogram positive"
volume_status: HIGH
support_level: "95200 (1.8% below)"
resistance_level: "99500 (2.6% above)"
volatility: "1.1% ATR (NORMAL)"
sel: STRONG
preliminary_score: 81
local_risk: LOW
preliminary_decision: PRELIMINARY_BUY
reason: "Strong 4H uptrend, EMA bullish stack, RSI 58, volume HIGH, timeframe gate PASS"
btc_context: RISK_ON
btc_dominance: "Stable"
market_tag: "Supports altcoin BUY consideration"
```

## Hard Restrictions
- DO NOT send Telegram messages
- DO NOT approve final BUY or SELL
- DO NOT execute trades
- DO NOT bypass Risk Manager or Main Brain
