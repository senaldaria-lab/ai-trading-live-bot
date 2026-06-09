# CLAUDE

This repository is AI_TRADING_AGENT.

Key rules:
- Default mode is SIGNALS_ONLY.
- No auto-trading.
- No futures.
- No leverage.
- No real Binance orders.
- Use `.env` for secrets.

Claude Code behavior:
- Work like an autonomous coding assistant.
- Inspect code and project structure.
- Plan changes before applying them.
- Create files safely.
- Update code only when explicitly instructed.
- Test safely when appropriate.
- Report findings and changes clearly.
- Preserve backups before risky changes.
- Follow the skills files inside the `skills/` folder.
- When improving the bot, consult ALL skill files listed below before making changes.

Skills system (skills/ folder):

Core agents:
- MASTER_TRADER_SKILLS.md       — overall role and principles
- MARKET_WATCHER_SKILLS.md      — price and candle data collection
- NEWS_AGENT_SKILLS.md          — sentiment classification
- TECHNICAL_ANALYSIS_SKILLS.md  — indicators: EMA, RSI, MACD, volume
- RISK_MANAGER_SKILLS.md        — risk classification and safety rules
- SIGNAL_DECISION_SKILLS.md     — final signal label and output format

Extended skills (must be consulted for any bot improvement):
- MARKET_SCANNER_SKILLS.md      — scan watchlist, rank opportunities, TOP 3 only
- LIQUIDITY_FILTER_SKILLS.md    — block low-liquidity coins before signal is issued
- MULTI_TIMEFRAME_SKILLS.md     — 15m / 1h / 4h alignment before confirming BUY
- TRADE_SETUP_SKILLS.md         — separate setup from trigger; both required for STRONG_BUY
- POSITION_SIZING_SKILLS.md     — safe manual position size calculation, 0.5–1% risk only
- TRADE_JOURNAL_SKILLS.md       — log all signals and trades, measure quality over 50–100 samples
