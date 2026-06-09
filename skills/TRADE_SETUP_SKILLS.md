# TRADE_SETUP_SKILLS

Role:
- Separate market setup from entry trigger
- Prevent premature entries when conditions look good but timing is not confirmed
- Both setup and trigger must be present before outputting STRONG_BUY

Definitions:
- Setup: market conditions are favorable for a trade in that direction
- Trigger: price action or indicator confirms entry is good now
- A trade needs both setup AND trigger

Setup criteria (market conditions):
- EMA20 > EMA50 > EMA200 (bullish stack)
- RSI between 40 and 65
- MACD positive or turning up
- Volume average or above
- Risk level LOW or MEDIUM
- 4h trend not conflicting

Trigger criteria (entry confirmation):
- RSI turning up from below 50
- MACD crossing above signal line
- Price bouncing from EMA20 or EMA50 support
- Volume increasing on a bullish candle
- 15m chart confirming direction

Output rules:
- Setup exists + trigger confirmed → STRONG_BUY
- Setup exists + trigger weak or absent → BUY_WATCH
- Setup partial + trigger absent → WAIT
- No setup → AVOID or WAIT
- Never output STRONG_BUY from setup alone without trigger

Indicators used:
- EMA20, EMA50, EMA200 (trend and support)
- RSI (momentum)
- MACD (momentum direction)
- Volume (confirmation strength)
- Support and resistance levels (context)

Constraints:
- This agent defines rules only — never executes trades
- All signals are for manual review
- No futures, no leverage, spot only
