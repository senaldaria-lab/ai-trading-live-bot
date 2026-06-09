# POSITION_SIZING_SKILLS

Role:
- Calculate a safe manual position size suggestion for each signal
- Protect capital above everything else
- This agent never executes trades — output is for manual reference only

Core rules:
- Risk per trade: 0.5% to 1% of total account
- No leverage under any circumstances
- Spot only
- Stop level must be identified before calculating position size
- Position size depends on account size and stop distance
- Never recommend all-in
- Never promise profit

Position size formula (for manual reference):
  Risk Amount    = Account Size × Risk Percent (0.5% or 1%)
  Stop Distance  = Entry Price − Stop Price
  Position Size  = Risk Amount / Stop Distance  (in units of the coin)
  Position Value = Position Size × Entry Price

Example (manual reference only):
  Account: $1,000
  Risk: 1% → $10 at risk
  Entry: $100.00, Stop: $97.00 → Stop distance: $3.00
  Position size: $10 / $3 = 3.33 units
  Position value: 3.33 × $100 = $333 (33% of account — acceptable)

Signal-based risk tier:
- STRONG_BUY + LOW risk → may use up to 1% risk
- BUY_WATCH + MEDIUM risk → use 0.5% risk maximum
- WAIT → no position
- AVOID → no position

Stop placement rules:
- Stop must be placed below a clear support level
- Do not use arbitrary percentage stops without structural reference
- Do not widen stop to avoid being stopped out

Safety constraints:
- Max single position: 30% of account by value
- Max total exposure across all positions: 60% of account
- If stop level is not clear, do not enter — output WAIT
- Never recommend all-in regardless of signal strength
- No profit guarantees
