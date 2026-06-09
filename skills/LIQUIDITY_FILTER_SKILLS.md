# LIQUIDITY_FILTER_SKILLS

Role:
- Protect from low-liquidity coins before any signal is accepted
- Act as a pre-filter — runs before technical analysis produces a signal
- Block any coin that fails liquidity standards

Checks performed:
1. Volume check
   - Compare current bar volume to 20-period average
   - volume_ratio < 0.8 → block: low volume
   - volume_ratio >= 0.8 → average: caution flag
   - volume_ratio >= 1.2 → high: clean confirmation

2. Abnormal candle detection
   - Single candle with body > 5% of price → flag as potential pump
   - Long upper wick (> 2× body) on a green candle → distribution warning
   - Long lower wick (> 2× body) on a red candle → capitulation warning

3. Pump risk detection
   - Price moved > 10% in last 4 candles on 1h → flag as possible pump
   - Volume spike > 5× 20-period average → flag as suspicious

4. Weak structure detection
   - No clear trend direction → flag as unclear
   - EMAs in conflicting order → flag as mixed structure

Block rules:
- Low volume (volume_ratio < 0.8) → block coin from STRONG_BUY or BUY_WATCH
- Low volume can never produce STRONG_BUY under any circumstances
- Pump flag → block STRONG_BUY, downgrade to WAIT or AVOID
- Unclear structure → output WAIT, not BUY_WATCH

Output:
- PASS: coin meets liquidity standards
- CAUTION: coin passes but has a warning flag
- BLOCK: coin fails liquidity check, reason stated

Constraints:
- Never overrides a BLOCK to force a trade
- No order execution
- Spot only
