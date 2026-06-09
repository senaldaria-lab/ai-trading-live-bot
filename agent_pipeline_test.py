#!/usr/bin/env python3
"""
agent_pipeline_test.py

DRY-RUN SIMULATION TEST — AI Trading Agent Pipeline
=====================================================
PURPOSE:
    Simulates the full multi-agent architecture end-to-end using mock data.
    Verifies the decision pipeline logic before any live integration.

WHAT THIS FILE DOES:
    - Loads mock outputs for all agents (Deep Research, Coin Agents,
      News Sentiment, Risk Manager, Main Brain, Telegram Signal Agent)
    - Runs the complete signal pipeline in sequence
    - Prints a formatted signal preview to the console

WHAT THIS FILE DOES NOT DO:
    - Send real Telegram messages
    - Connect to Binance API
    - Execute any trades or place any orders
    - Use live market data
    - Modify any production file

SAFE TO RUN at any time. No external connections are made.
"""

from datetime import datetime

# =============================================================================
# SAFETY CONSTANTS — DO NOT CHANGE
# These are enforced by assertion at pipeline start.
# =============================================================================
SPOT_ONLY            = True
SIGNALS_ONLY         = True
AUTO_TRADING_ENABLED = False
FUTURES_ALLOWED      = False
LEVERAGE_ALLOWED     = False


# =============================================================================
# MOCK: DEEP RESEARCH CONTEXT
# Schema: deep_research_skill.md
# =============================================================================
MOCK_DEEP_RESEARCH = {
    "macro_phase":         "Accumulation",
    "btc_dominance_trend": "Stable",
    "leading_sector":      "L1s and AI tokens",
    "market_narrative":    "BTC ETF inflows growing; L1 ecosystem activity strong",
    "coin_group_status": {
        "L1s":        "STRONG",
        "DeFi":       "MODERATE",
        "CEX_tokens": "MODERATE",
        "Payments":   "WEAK",
        "Gaming":     "WEAK",
    },
    "coins_to_watch":     ["AVAXUSDT"],
    "coins_to_pause":     [],
    "coins_to_blacklist": [],
    "strategic_risk_notes": [
        "Fed meeting scheduled this week — macro volatility possible",
    ],
    "recommendation_for_main_brain": (
        "Focus on BTC and ETH. Altcoins require BTC RISK_ON confirmation."
    ),
}


# =============================================================================
# MOCK: COIN AGENT REPORTS
# Schema: coin_agent_base_skill.md + individual coin skill files
# All 6 coins — BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, SUIUSDT
# =============================================================================
MOCK_COIN_REPORTS = [
    # --- BTC Agent ---
    {
        "symbol":               "BTCUSDT",
        "timeframe_4h_trend":   "UPTREND",
        "timeframe_1h_trend":   "BULLISH",
        "timeframe_15m_trend":  "BULLISH",
        "timeframe_gate":       "PASS",
        "ema_status":           "Bullish (EMA20 > EMA50 > EMA200)",
        "rsi":                  58.1,
        "rsi_4h":               63.4,
        "macd_status":          "Bullish crossover, histogram positive",
        "volume_status":        "HIGH",
        "support_level":        "95200 (1.8% below)",
        "resistance_level":     "99500 (2.6% above)",
        "volatility":           "1.1% ATR (NORMAL)",
        "sel":                  "STRONG",
        "preliminary_score":    81,
        "local_risk":           "LOW",
        "preliminary_decision": "PRELIMINARY_BUY",
        "reason": (
            "Strong 4H uptrend, EMA bullish stack, RSI 58, "
            "volume HIGH, timeframe gate PASS"
        ),
        "btc_context":  "RISK_ON",
        "btc_dominance": "Stable",
        "market_tag":   "Supports altcoin BUY consideration",
    },
    # --- ETH Agent ---
    {
        "symbol":               "ETHUSDT",
        "timeframe_4h_trend":   "UPTREND",
        "timeframe_1h_trend":   "BULLISH",
        "timeframe_15m_trend":  "BULLISH",
        "timeframe_gate":       "PASS",
        "ema_status":           "Bullish (EMA20 > EMA50 > EMA200)",
        "rsi":                  55.7,
        "rsi_4h":               60.1,
        "macd_status":          "Bullish histogram growing",
        "volume_status":        "NORMAL",
        "support_level":        "3150 (2.3% below)",
        "resistance_level":     "3420 (6.8% above)",
        "volatility":           "1.8% ATR (NORMAL)",
        "sel":                  "MODERATE",
        "preliminary_score":    74,
        "local_risk":           "LOW",
        "preliminary_decision": "PRELIMINARY_BUY",
        "reason": (
            "4H uptrend confirmed, 1H bullish, volume NORMAL, ETH leading alts"
        ),
        "eth_context": "ETH_LEADING",
        "alt_proxy":   "Positive — supports altcoin BUY signals",
    },
    # --- BNB Agent ---
    {
        "symbol":               "BNBUSDT",
        "timeframe_4h_trend":   "UPTREND",
        "timeframe_1h_trend":   "BULLISH",
        "timeframe_15m_trend":  "NEUTRAL",
        "timeframe_gate":       "PASS",
        "ema_status":           "Bullish (EMA20 > EMA50 > EMA200)",
        "rsi":                  53.2,
        "rsi_4h":               58.8,
        "macd_status":          "Neutral, slight bullish lean",
        "volume_status":        "NORMAL",
        "support_level":        "580 (1.5% below)",
        "resistance_level":     "615 (4.5% above)",
        "volatility":           "1.6% ATR (NORMAL)",
        "sel":                  "MODERATE",
        "preliminary_score":    69,
        "local_risk":           "LOW",
        "preliminary_decision": "WATCH",
        "reason": (
            "4H uptrend but 15m neutral, volume NORMAL, "
            "no exchange-specific catalysts"
        ),
        "bnb_context": "No exchange-specific catalysts detected",
    },
    # --- SOL Agent ---
    {
        "symbol":               "SOLUSDT",
        "timeframe_4h_trend":   "UPTREND",
        "timeframe_1h_trend":   "BULLISH",
        "timeframe_15m_trend":  "BULLISH",
        "timeframe_gate":       "PASS",
        "ema_status":           "Bullish (EMA20 > EMA50 > EMA200)",
        "rsi":                  57.4,
        "rsi_4h":               62.0,
        "macd_status":          "Bullish crossover, histogram positive",
        "volume_status":        "HIGH",
        "support_level":        "142 (2.8% below)",
        "resistance_level":     "158 (8.2% above)",
        "volatility":           "2.1% ATR (NORMAL-HIGH)",
        "sel":                  "MODERATE",
        "preliminary_score":    73,
        "local_risk":           "MEDIUM",
        "preliminary_decision": "WATCH",
        "reason": (
            "4H uptrend confirmed, volume HIGH, but local risk MEDIUM "
            "due to elevated ATR"
        ),
        "sol_context": "High-beta — requires BTC RISK_ON confirmation",
    },
    # --- XRP Agent ---
    {
        "symbol":               "XRPUSDT",
        "timeframe_4h_trend":   "SIDEWAYS",
        "timeframe_1h_trend":   "NEUTRAL",
        "timeframe_15m_trend":  "NEUTRAL",
        "timeframe_gate":       "FAIL",
        "ema_status":           "Mixed (EMA20 > EMA50, price below EMA200)",
        "rsi":                  49.3,
        "rsi_4h":               51.7,
        "macd_status":          "Neutral, histogram near zero",
        "volume_status":        "NORMAL",
        "support_level":        "0.52 (1.9% below)",
        "resistance_level":     "0.57 (7.5% above)",
        "volatility":           "1.3% ATR (NORMAL)",
        "sel":                  "WEAK",
        "preliminary_score":    48,
        "local_risk":           "MEDIUM",
        "preliminary_decision": "AVOID",
        "reason": (
            "4H sideways, timeframe gate FAIL, SEL WEAK, "
            "no active regulatory catalyst"
        ),
        "xrp_context": "No active regulatory catalysts; sideways accumulation phase",
    },
    # --- SUI Agent ---
    {
        "symbol":               "SUIUSDT",
        "timeframe_4h_trend":   "UPTREND",
        "timeframe_1h_trend":   "BULLISH",
        "timeframe_15m_trend":  "BULLISH",
        "timeframe_gate":       "PASS",
        "ema_status":           "Bullish (EMA20 > EMA50 > EMA200)",
        "rsi":                  60.2,
        "rsi_4h":               65.0,
        "macd_status":          "Bullish crossover, histogram positive",
        "volume_status":        "HIGH",
        "support_level":        "3.10 (3.2% below)",
        "resistance_level":     "3.55 (11.3% above)",
        "volatility":           "2.8% ATR (HIGH)",
        "sel":                  "MODERATE",
        "preliminary_score":    68,
        "local_risk":           "MEDIUM",
        "preliminary_decision": "WATCH",
        "reason": (
            "Uptrend confirmed but elevated ATR, local risk MEDIUM; "
            "needs BTC RISK_ON + ETH_LEADING"
        ),
        "sui_context":      "High-beta L1; needs BTC RISK_ON + ETH_LEADING",
        "liquidity_status": "28M USDT 24H volume (PASS — above 20M threshold)",
    },
]


# =============================================================================
# MOCK: NEWS SENTIMENT
# Schema: news_sentiment_skill.md
# =============================================================================
MOCK_NEWS_SENTIMENT = {
    "news_status":                   "POSITIVE",
    "btc_news_status":               "POSITIVE",
    "eth_news_status":               "NEUTRAL",
    "binance_news_status":           "NEUTRAL",
    "macro_status":                  "NEUTRAL",
    "regulation_status":             "CLEAR",
    "sentiment_score":               0.72,
    "risk_notes":                    "No major risk events detected this cycle",
    "recommendation_for_main_brain": (
        "Sentiment supports BUY signals; altcoins may follow BTC strength"
    ),
}


# =============================================================================
# RISK MANAGER
# Schema: risk_manager_skill.md
# Enforces: SPOT ONLY, SIGNALS ONLY, NO FUTURES, NO LEVERAGE
# =============================================================================
def run_risk_manager(coin_report, blacklist):
    """
    Applies Risk Manager block and downgrade rules to one coin agent report.
    Returns a risk manager verdict dict.
    risk_action: ALLOW | DOWNGRADE | BLOCK
    """
    symbol   = coin_report["symbol"]
    decision = coin_report["preliminary_decision"]
    score    = coin_report["preliminary_score"]
    risk     = coin_report["local_risk"]
    rsi      = coin_report.get("rsi", 0)
    sel      = coin_report.get("sel", "MODERATE")
    volume   = coin_report.get("volume_status", "NORMAL")
    tf_gate  = coin_report.get("timeframe_gate", "PASS")

    def verdict(action, block_reason=None, downgrade_reason=None):
        return {
            "symbol":               symbol,
            "input_decision":       decision,
            "input_score":          score,
            "input_risk":           risk,
            "risk_check_result":    "PASS" if action == "ALLOW" else "FAIL",
            "risk_action":          action,
            "block_reason":         block_reason,
            "downgrade_reason":     downgrade_reason,
            "final_risk_label":     risk if action != "BLOCK" else "HIGH",
            "allowed_for_main_brain": action == "ALLOW",
        }

    # --- BLOCK rules (hard, no override) ---
    if symbol in blacklist:
        return verdict("BLOCK", "Deep Research blacklist")
    if decision == "AVOID":
        return verdict("BLOCK", "Coin agent issued AVOID")
    if sel == "INVALID":
        return verdict("BLOCK", "SEL = INVALID — missing or contradictory data")
    if rsi > 78:
        return verdict("BLOCK", f"RSI overbought: {rsi:.1f} > 78")
    if volume == "LOW" and risk == "HIGH":
        return verdict("BLOCK", "volume_status LOW + local_risk HIGH")

    # --- DOWNGRADE rules ---
    if sel == "WEAK":
        return verdict("DOWNGRADE", downgrade_reason="SEL = WEAK — signal quality low for BUY")
    if 65 <= rsi <= 78:
        return verdict("DOWNGRADE", downgrade_reason=f"RSI elevated: {rsi:.1f} (65–78 zone)")
    if volume == "LOW":
        return verdict("DOWNGRADE", downgrade_reason="volume_status LOW — weak participation")
    if tf_gate == "FAIL":
        return verdict("DOWNGRADE", downgrade_reason="timeframe_gate FAIL — 3-TF not confirmed")
    if risk == "HIGH":
        return verdict("DOWNGRADE", downgrade_reason="local_risk HIGH — reducing signal strength")

    # --- ALLOW ---
    return verdict("ALLOW")


# =============================================================================
# MAIN BRAIN
# Schema: main_brain_skill.md
# =============================================================================
def run_main_brain(deep_research, coin_reports, news_sentiment, risk_verdicts):
    """
    Aggregates all inputs, applies all filters, produces final decisions.
    Returns a list of Main Brain output dicts (max 3 BUY/STRONG_BUY signals).
    """
    blacklist       = deep_research.get("coins_to_blacklist", [])
    pause_list      = deep_research.get("coins_to_pause", [])
    macro_phase     = deep_research.get("macro_phase", "Unknown")
    group_statuses  = deep_research.get("coin_group_status", {})
    dr_context      = deep_research.get("recommendation_for_main_brain", "")

    # BTC context (from BTC Agent report)
    btc_report  = next((r for r in coin_reports if r["symbol"] == "BTCUSDT"), None)
    btc_context = btc_report.get("btc_context", "NEUTRAL") if btc_report else "NEUTRAL"
    btc_4h      = btc_report.get("timeframe_4h_trend", "SIDEWAYS") if btc_report else "SIDEWAYS"

    news_status     = news_sentiment.get("news_status", "NEUTRAL")
    sentiment_score = news_sentiment.get("sentiment_score", 0.5)

    rm_index = {v["symbol"]: v for v in risk_verdicts}

    _COIN_GROUPS = {
        "BTCUSDT": "L1s", "ETHUSDT": "L1s",
        "BNBUSDT": "CEX_tokens", "SOLUSDT": "L1s",
        "XRPUSDT": "Payments",  "SUIUSDT": "L1s",
    }

    candidates = []

    for report in coin_reports:
        symbol = report["symbol"]
        rm = rm_index.get(symbol)

        # Step 4: Skip Risk Manager blocked coins
        if not rm or not rm["allowed_for_main_brain"]:
            continue
        # Step 2: Skip Deep Research blacklist
        if symbol in blacklist:
            continue

        score       = report["preliminary_score"]
        sel         = report.get("sel", "MODERATE")
        local_risk  = report.get("local_risk", "MEDIUM")
        preliminary = report.get("preliminary_decision", "WATCH")
        modifier    = 0

        # Step 2: Apply Deep Research context
        if symbol in pause_list:
            preliminary = "WATCH"
            modifier   -= 10
        group       = _COIN_GROUPS.get(symbol, "Other")
        group_status = group_statuses.get(group, "MODERATE")
        if group_status == "WEAK":
            modifier -= 5
        elif group_status == "DEAD":
            modifier -= 15
        if macro_phase in ("BEAR", "DISTRIBUTION") and symbol not in ("BTCUSDT", "ETHUSDT"):
            modifier -= 10

        # Step 3: Apply BTC market context
        if btc_4h == "DOWNTREND" and symbol != "BTCUSDT":
            if preliminary == "PRELIMINARY_BUY":
                preliminary = "WATCH"
                modifier   -= 10

        # Step 4: Apply News Sentiment (Main Brain only — not Risk Manager)
        if news_status in ("NEGATIVE", "DANGER") or sentiment_score < 0.3:
            if preliminary == "PRELIMINARY_BUY":
                preliminary = "WATCH"
                modifier   -= 10
        elif news_status == "POSITIVE" and sentiment_score >= 0.6:
            modifier += 5

        # Apply Risk Manager downgrade
        if rm["risk_action"] == "DOWNGRADE" and preliminary == "PRELIMINARY_BUY":
            preliminary = "WATCH"
            modifier   -= 5

        adjusted_score = max(0, min(100, score + modifier))
        candidates.append({
            "symbol":      symbol,
            "preliminary": preliminary,
            "score":       adjusted_score,
            "sel":         sel,
            "local_risk":  local_risk,
            "report":      report,
        })

    # Step 6: Rank — PRELIMINARY_BUY first, then by score
    candidates.sort(
        key=lambda c: (1 if c["preliminary"] == "PRELIMINARY_BUY" else 0, c["score"]),
        reverse=True,
    )

    final_decisions = []
    buy_count = 0

    for c in candidates:
        if buy_count >= 3:
            break

        symbol      = c["symbol"]
        score       = c["score"]
        sel         = c["sel"]
        local_risk  = c["local_risk"]
        preliminary = c["preliminary"]
        report      = c["report"]

        # Step 7: Make final decision label
        if preliminary == "PRELIMINARY_BUY":
            if score >= 80 and sel == "STRONG":
                final_decision = "STRONG_BUY"
            elif score >= 65 and sel in ("STRONG", "MODERATE"):
                final_decision = "BUY"
            else:
                final_decision = "WATCH"
        elif preliminary == "WATCH":
            final_decision = "WATCH"
        else:
            final_decision = "AVOID"

        # Confidence level
        if score >= 80 and local_risk in ("LOW", "MEDIUM"):
            confidence_level = "HIGH"
        elif 65 <= score < 80 and local_risk != "HIGH":
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        # Market status
        if btc_context == "RISK_ON" and news_status == "POSITIVE":
            market_status = "RISK_ON"
        elif btc_context == "RISK_OFF" or news_status in ("NEGATIVE", "DANGER"):
            market_status = "RISK_OFF"
        else:
            market_status = "NEUTRAL"

        telegram_action = (
            "SEND" if final_decision in ("STRONG_BUY", "BUY", "SELL", "WATCH")
            else "SUPPRESS"
        )

        final_decisions.append({
            "symbol":               symbol,
            "final_decision":       final_decision,
            "final_score":          score,
            "confidence_level":     confidence_level,
            "risk":                 local_risk,
            "market_status":        market_status,
            "deep_research_context": dr_context,
            "timeframe_4h_trend":   report.get("timeframe_4h_trend"),
            "timeframe_1h_trend":   report.get("timeframe_1h_trend"),
            "timeframe_15m_trend":  report.get("timeframe_15m_trend"),
            "rsi":                  report.get("rsi"),
            "macd_status":          report.get("macd_status"),
            "volume_status":        report.get("volume_status"),
            "sel":                  sel,
            "reason":               report.get("reason"),
            "telegram_action":      telegram_action,
        })

        if final_decision in ("STRONG_BUY", "BUY"):
            buy_count += 1

    return final_decisions


# =============================================================================
# TELEGRAM SIGNAL AGENT — DRY-RUN ONLY (console output, no real send)
# Schema: telegram_signal_skill.md
# =============================================================================
def format_telegram_message(mb_output):
    """
    Formats a Main Brain decision into a Telegram message string.
    DRY-RUN: returns the message text only. No Telegram API call is made.
    AVOID decisions return None (suppressed).
    """
    final_decision = mb_output["final_decision"]
    confidence     = mb_output["confidence_level"]
    symbol         = mb_output["symbol"]

    # Never send AVOID
    if final_decision == "AVOID" or mb_output.get("telegram_action") != "SEND":
        return None

    if final_decision in ("STRONG_BUY", "BUY"):
        lines = [
            f"[{confidence} CONFIDENCE] {final_decision} SIGNAL — {symbol}",
            "",
            f"Decision : {final_decision}",
            f"Score    : {mb_output['final_score']}/100",
            f"Risk     : {mb_output['risk']}",
            f"Market   : {mb_output['market_status']}",
            "",
            "Timeframes",
            f"4H  : {mb_output['timeframe_4h_trend']}",
            f"1H  : {mb_output['timeframe_1h_trend']}",
            f"15m : {mb_output['timeframe_15m_trend']}",
            "",
            "Indicators",
            f"RSI    : {mb_output['rsi']}",
            f"MACD   : {mb_output['macd_status']}",
            f"Volume : {mb_output['volume_status']}",
            f"SEL    : {mb_output['sel']}",
            "",
            "Reason",
            str(mb_output["reason"]),
            "",
            "SIGNALS ONLY — NOT FINANCIAL ADVICE",
            "SPOT ONLY — NO LEVERAGE — NO FUTURES",
        ]
        if confidence == "LOW":
            lines.append(
                "LOW CONFIDENCE — Reduce position size. Proceed with caution."
            )
        return "\n".join(lines)

    if final_decision == "WATCH":
        return "\n".join([
            f"WATCH ALERT — {symbol}",
            "",
            f"Score  : {mb_output['final_score']}/100",
            f"SEL    : {mb_output['sel']}",
            f"Volume : {mb_output['volume_status']}",
            f"Reason : {mb_output['reason']}",
            "",
            "Not a buy signal — monitoring only.",
        ])

    if final_decision == "SELL":
        return "\n".join([
            f"EXIT SIGNAL — {symbol}",
            "",
            f"Decision : SELL",
            f"Score    : {mb_output['final_score']}/100",
            f"Risk     : {mb_output['risk']}",
            "",
            "Exit Basis",
            f"4H   : {mb_output['timeframe_4h_trend']}",
            f"1H   : {mb_output['timeframe_1h_trend']}",
            f"MACD : {mb_output['macd_status']}",
            "",
            "Reason",
            str(mb_output["reason"]),
            "",
            "SIGNALS ONLY — NOT FINANCIAL ADVICE",
        ])

    return None


# =============================================================================
# MAIN PIPELINE TEST
# =============================================================================
def run_pipeline_test():
    SEP  = "=" * 62
    DASH = "-" * 62

    print(SEP)
    print("  AI TRADING AGENT — DRY-RUN PIPELINE TEST")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)
    print()

    # --- Safety gate ---
    assert SPOT_ONLY            is True,  "SPOT_ONLY must be True"
    assert SIGNALS_ONLY         is True,  "SIGNALS_ONLY must be True"
    assert AUTO_TRADING_ENABLED is False, "AUTO_TRADING_ENABLED must be False"
    assert FUTURES_ALLOWED      is False, "FUTURES_ALLOWED must be False"
    assert LEVERAGE_ALLOWED     is False, "LEVERAGE_ALLOWED must be False"
    print("[SAFETY] All safety constants verified — DRY-RUN mode active")
    print()

    # --- Step 1: Deep Research ---
    print("[STEP 1] Deep Research Context")
    dr = MOCK_DEEP_RESEARCH
    print(f"  Macro Phase    : {dr['macro_phase']}")
    print(f"  BTC Dominance  : {dr['btc_dominance_trend']}")
    print(f"  Leading Sector : {dr['leading_sector']}")
    print(f"  Blacklist      : {dr['coins_to_blacklist'] or 'None'}")
    print(f"  Pause List     : {dr['coins_to_pause'] or 'None'}")
    print(f"  Risk Notes     : {dr['strategic_risk_notes'][0] if dr['strategic_risk_notes'] else 'None'}")
    print()

    # --- Step 2: News Sentiment ---
    print("[STEP 2] News Sentiment")
    ns = MOCK_NEWS_SENTIMENT
    print(f"  Status    : {ns['news_status']}")
    print(f"  Score     : {ns['sentiment_score']}")
    print(f"  Reg Status: {ns['regulation_status']}")
    print(f"  Notes     : {ns['risk_notes']}")
    print()

    # --- Step 3: Coin Agents ---
    print(f"[STEP 3] Coin Agent Reports ({len(MOCK_COIN_REPORTS)} coins)")
    print(f"  {'Symbol':<10} {'Score':>5}  {'SEL':<8}  {'TF Gate':<7}  Preliminary")
    print(f"  {'-'*10} {'-'*5}  {'-'*8}  {'-'*7}  -----------")
    for r in MOCK_COIN_REPORTS:
        print(
            f"  {r['symbol']:<10} {r['preliminary_score']:>5}  "
            f"{r['sel']:<8}  {r['timeframe_gate']:<7}  {r['preliminary_decision']}"
        )
    print()

    # --- Step 4: Risk Manager ---
    blacklist     = dr.get("coins_to_blacklist", [])
    risk_verdicts = [run_risk_manager(r, blacklist) for r in MOCK_COIN_REPORTS]

    print("[STEP 4] Risk Manager Verdicts")
    print(f"  {'Symbol':<10} {'Action':<10}  Reason")
    print(f"  {'-'*10} {'-'*10}  ------")
    for v in risk_verdicts:
        note = v["block_reason"] or v["downgrade_reason"] or "—"
        print(f"  {v['symbol']:<10} {v['risk_action']:<10}  {note}")
    print()

    # --- Step 5: Main Brain ---
    final_decisions = run_main_brain(
        MOCK_DEEP_RESEARCH,
        MOCK_COIN_REPORTS,
        MOCK_NEWS_SENTIMENT,
        risk_verdicts,
    )

    print(f"[STEP 5] Main Brain — {len(final_decisions)} decision(s) produced")
    print()

    # --- Step 6: Telegram Signal Agent (console preview only) ---
    print(SEP)
    print("  FINAL SIGNAL PREVIEW(S)  [DRY-RUN — NOT SENT]")
    print(SEP)

    sent_count      = 0
    suppressed_count = 0

    for mb in final_decisions:
        print()
        print(DASH)
        print("FINAL SIGNAL TEST")
        print(f"  symbol           : {mb['symbol']}")
        print(f"  final_decision   : {mb['final_decision']}")
        print(f"  final_score      : {mb['final_score']}/100")
        print(f"  confidence_level : {mb['confidence_level']}")
        print(f"  risk             : {mb['risk']}")
        print(f"  market_status    : {mb['market_status']}")
        print(f"  reason           : {mb['reason']}")
        print()

        msg = format_telegram_message(mb)
        if msg:
            print("  telegram_message_preview:")
            print()
            for line in msg.split("\n"):
                print(f"    {line}")
            sent_count += 1
        else:
            print("  telegram_message_preview: SUPPRESSED (AVOID — not sent)")
            suppressed_count += 1

    print()
    print(SEP)
    print("  DRY-RUN SUMMARY")
    print(SEP)
    print(f"  Coins evaluated              : {len(MOCK_COIN_REPORTS)}")
    print(f"  Risk Manager blocked         : {sum(1 for v in risk_verdicts if v['risk_action'] == 'BLOCK')}")
    print(f"  Risk Manager downgraded      : {sum(1 for v in risk_verdicts if v['risk_action'] == 'DOWNGRADE')}")
    print(f"  Main Brain decisions         : {len(final_decisions)}")
    print(f"  Signals ready for Telegram   : {sent_count}")
    print(f"  Signals suppressed (AVOID)   : {suppressed_count}")
    print()
    print(f"  Real Telegram messages sent  : 0  (DRY-RUN)")
    print(f"  Real Binance orders placed   : 0  (DRY-RUN)")
    print()
    print(f"  SPOT_ONLY             : {SPOT_ONLY}")
    print(f"  SIGNALS_ONLY          : {SIGNALS_ONLY}")
    print(f"  AUTO_TRADING_ENABLED  : {AUTO_TRADING_ENABLED}")
    print(f"  FUTURES_ALLOWED       : {FUTURES_ALLOWED}")
    print(f"  LEVERAGE_ALLOWED      : {LEVERAGE_ALLOWED}")
    print(SEP)
    print()
    print("Pipeline test complete. No external systems were contacted.")
    print()


# =============================================================================
# ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    run_pipeline_test()
