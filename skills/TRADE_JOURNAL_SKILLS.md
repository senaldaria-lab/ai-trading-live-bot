# TRADE_JOURNAL_SKILLS

Role:
- Log every signal and every manual trade taken from those signals
- Track outcomes to measure real strategy quality over time
- Identify patterns in winning and losing signals after 50–100 samples

What to log for every signal:
- date_time: UTC timestamp
- symbol: trading pair (e.g. BTCUSDT)
- signal: STRONG_BUY / BUY_WATCH / WAIT / AVOID
- score: 0–100
- risk_level: LOW / MEDIUM / HIGH
- ema_structure: bullish / mixed / bearish
- rsi: value at signal time
- macd: positive / near-zero / negative
- volume_tier: high / average / low
- entry_idea: suggested entry price level (manual)
- stop_idea: suggested stop loss level (manual)
- target_idea: suggested target level (manual)
- result: WIN / LOSS / BREAKEVEN / SKIPPED / PENDING
- pnl_pct: actual percentage gain or loss if taken
- notes: free text observation

Log files:
- data/signals_log.csv: automated signal records (written by bot)
- data/trades_log.csv: manual trade records (filled in by trader)

Review goals (after 50–100 signals):
- Signal accuracy rate: how often STRONG_BUY leads to a profitable manual trade
- Best performing risk levels
- Best performing market conditions (EMA structure, RSI zone, volume tier)
- Average score of winning vs losing setups
- Signals where WAIT was correct vs where entry was missed

Review rules:
- Do not judge a signal on 1 or 2 samples
- Minimum 50 signals before drawing conclusions
- Separate STRONG_BUY and BUY_WATCH results
- Note market conditions during review (bull / bear / sideways)

Constraints:
- This agent logs and reviews only — it does not trade
- Do not use journal results to override safety rules
- All entries are manual reference — no automated execution
