# MULTI_TIMEFRAME_SKILLS

Role:
- Confirm or reject signals by checking multiple timeframes
- Reduce false signals caused by noise on a single timeframe
- Never produce a signal alone — supports signal_decision only

Timeframe hierarchy:
- 4h: trend confirmation (macro direction)
- 1h: main signal timeframe (primary entry basis)
- 15m: entry timing (micro confirmation)

Rules per timeframe:

4h (trend confirmation):
- 4h EMA20 > EMA50 > EMA200 → bullish trend confirmed
- 4h EMA20 < EMA50 < EMA200 → bearish trend, block BUY signals
- 4h mixed → proceed with caution, lower score

1h (main signal):
- Primary signal is generated from 1h candles
- RSI, MACD, EMA, volume evaluated on 1h
- Final signal label is based on 1h analysis

15m (entry timing):
- Only used to time entry, not to generate the signal
- 15m RSI < 50 on a bullish 1h setup → entry may be premature, wait
- 15m MACD positive on bullish 1h → timing confirmed
- 15m oversold (RSI < 35) → possible dip entry, watch 1h first

Conflict resolution:
- 4h bearish + 1h bullish → WAIT, no BUY signal
- 4h neutral + 1h bullish → BUY_WATCH allowed, not STRONG_BUY
- 4h bullish + 1h bullish + 15m confirming → STRONG_BUY allowed if all other guards pass
- Strong conflict on any two timeframes → prefer WAIT

Constraints:
- BUY signal requires timeframes not to conflict strongly
- No order execution
- Signals are for manual review only
