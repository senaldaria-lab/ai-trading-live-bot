import json
import os
import sys
from datetime import date, datetime, timezone

import pandas as pd
from dotenv import load_dotenv

from agents.market_watcher import fetch_market_data, fetch_4h_data
from agents.technical_analysis import analyze_technical_indicators, analyze_trend_4h
from agents.news_agent import get_news_sentiment
from agents.risk_manager import assess_risk
from agents.signal_decision import decide_signal
from agents.scanner import run_scanner, save_scanner_results
from agents.trade_guard import evaluate_trade
from config.settings import SETTINGS
from services.binance_service import READONLY_MODE
from services.logger_service import get_logger
from services.telegram_service import send_telegram_message

logger = get_logger(__name__)

# ── SAFETY ASSERTIONS ────────────────────────────────────────────────────────
# Confirm binance_service is loaded in read-only mode before anything else runs.
assert READONLY_MODE is True, (
    "[SAFETY BLOCK] binance_service.READONLY_MODE is not True. Aborting."
)

# Explicitly block any Binance order-execution symbol from being imported here.
# These names must never appear in this module.
_FORBIDDEN_IMPORTS = [
    "create_order",
    "order_market_buy",
    "order_market_sell",
    "order_limit_buy",
    "order_limit_sell",
    "cancel_order",
]
for _name in _FORBIDDEN_IMPORTS:
    assert _name not in dir(), (
        f"[SAFETY BLOCK] Forbidden symbol '{_name}' found in main module scope."
    )
# ─────────────────────────────────────────────────────────────────────────────


# Valid operating modes.  Anything outside this set halts the bot.
_ALLOWED_TRADE_MODES = {"SIGNALS_ONLY", "AUTO_SPOT"}


def _enforce_trade_mode() -> None:
    """Hard stop if TRADE_MODE is not in the recognised set."""
    trade_mode = os.getenv("TRADE_MODE", "SIGNALS_ONLY")
    if trade_mode not in _ALLOWED_TRADE_MODES:
        msg = (
            "\n"
            "╔══════════════════════════════════════════════════════════╗\n"
            "║              *** SAFETY GATE TRIGGERED ***               ║\n"
            f"║  TRADE_MODE={trade_mode!r:<46}║\n"
            "║  Valid modes: SIGNALS_ONLY, AUTO_SPOT                    ║\n"
            "║  Bot has been stopped. No orders were placed.            ║\n"
            "║  Fix: set TRADE_MODE in your .env file.                  ║\n"
            "╚══════════════════════════════════════════════════════════╝\n"
        )
        print(msg)
        logger.critical(msg)
        try:
            send_telegram_message(
                f"[SAFETY GATE] Bot stopped: TRADE_MODE={trade_mode!r} is not valid. "
                "No orders were placed. Valid: SIGNALS_ONLY, AUTO_SPOT."
            )
        except Exception:
            pass
        sys.exit(1)


def _load_daily_stats() -> dict:
    if not os.path.exists(SETTINGS.DAILY_STATS_JSON):
        return {"last_run": None, "signals_sent": 0, "signals_date": None}
    with open(SETTINGS.DAILY_STATS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_daily_stats(stats: dict) -> None:
    os.makedirs(SETTINGS.DATA_DIR, exist_ok=True)
    with open(SETTINGS.DAILY_STATS_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)


def _check_and_update_signal_count(stats: dict) -> tuple[bool, int]:
    """Return (allowed, current_count).

    Resets the counter when the calendar date has changed.
    Blocks when signals_sent >= MAX_SIGNALS_PER_DAY.
    """
    today = date.today().isoformat()
    if stats.get("signals_date") != today:
        stats["signals_sent"] = 0
        stats["signals_date"] = today

    count = stats.get("signals_sent", 0)
    if count >= SETTINGS.MAX_SIGNALS_PER_DAY:
        return False, count
    return True, count


def ensure_data_files():
    os.makedirs(SETTINGS.DATA_DIR, exist_ok=True)
    if not os.path.exists(SETTINGS.SIGNALS_CSV):
        pd.DataFrame(columns=[
            "timestamp",
            "symbol",
            "signal",
            "price",
            "score",
            "ema20",
            "ema50",
            "ema200",
            "rsi",
            "macd",
            "volume_ok",
            "volume_ratio",
            "news_sentiment",
            "risk_level",
            "notes",
            "trend_4h",
            "entry_1h",
            "atr",
            "sl",
            "tp1",
            "tp2",
            "time_stop_hours",
        ]).to_csv(SETTINGS.SIGNALS_CSV, index=False)
    if not os.path.exists(SETTINGS.TRADES_CSV):
        pd.DataFrame(columns=[
            "timestamp",
            "symbol",
            "signal",
            "price",
            "notes",
        ]).to_csv(SETTINGS.TRADES_CSV, index=False)
    if not os.path.exists(SETTINGS.DAILY_STATS_JSON):
        _save_daily_stats({"last_run": None, "signals_sent": 0, "signals_date": None})


def save_signal_record(record: dict) -> None:
    df = pd.DataFrame([record])
    df.to_csv(SETTINGS.SIGNALS_CSV, mode="a", header=False, index=False)
    logger.info(f"Saved signal record for {record['symbol']}")


# ── Telegram report helpers ───────────────────────────────────────────────────

def _signal_emoji(signal: str) -> str:
    return {
        "STRONG_BUY": "🟢",
        "BUY_WATCH":  "🟡",
        "WAIT":       "🔵",
        "AVOID":      "🔴",
    }.get(signal, "⚪")


def _rsi_label(rsi: float) -> str:
    if rsi > 80:
        return "Extremely overbought ⚠️"
    if rsi > 70:
        return "Overbought ⚠️"
    if rsi > 65:
        return "Approaching overbought"
    if rsi >= 45:
        return "Neutral zone ✓"
    if rsi >= 35:
        return "Below midpoint"
    if rsi >= 20:
        return "Oversold"
    return "Extremely oversold ⚠️"


def _ema_trend_label(ema20: float, ema50: float, ema200: float) -> str:
    if ema20 > ema50 > ema200:
        return "Bullish ✓  (EMA20 &gt; EMA50 &gt; EMA200)"
    if ema20 < ema50 < ema200:
        return "Bearish  (EMA20 &lt; EMA50 &lt; EMA200)"
    if ema20 > ema50:
        return "Mixed  (short-term up / long-term flat)"
    if ema50 > ema200:
        return "Mixed  (short-term down / medium-term up)"
    return "Mixed / unclear"


def _macd_label(macd: float, ema20: float) -> str:
    near_zero = abs(ema20) * 0.001
    if macd > near_zero:
        return "Positive ✓  (bullish momentum)"
    if macd > -near_zero:
        return "Near neutral  (watch for crossover)"
    return "Negative  (bearish momentum)"


def _volume_label(volume_ratio: float) -> str:
    if volume_ratio >= 1.2:
        return "High ✓  (strong confirmation)"
    if volume_ratio >= 0.8:
        return "Average  (watch carefully)"
    return "Low ⚠️  (weak signal — be cautious)"


def _trend_4h_label(trend: str) -> str:
    return {
        "bullish": "Bullish ✓  (4H EMA20 &gt; EMA50)",
        "neutral": "Neutral  (4H mixed structure)",
        "bearish": "Bearish ⚠️  (4H EMA20 &lt; EMA50)",
    }.get(trend, trend)


def _entry_1h_label(entry: str) -> str:
    return {
        "improving": "Improving ✓  (EMA bullish + MACD positive)",
        "bullish":   "Bullish  (EMA20 &gt; EMA50)",
        "mixed":     "Mixed  (structure not aligned)",
    }.get(entry, entry)


def _fmt_price(v: float | None) -> str:
    if v is None:
        return "N/A"
    if v >= 1_000:
        return f"${v:,.2f}"
    if v >= 1:
        return f"${v:,.4f}"
    return f"${v:.8f}"


def _scanner_block_reason(r: dict) -> str:
    """Primary market/strategy reason a symbol did not reach STRONG_BUY.

    Checks conditions in the same order as the signal decision pipeline.
    Never references TRADE_MODE or SIGNALS_ONLY — strategy conditions only.
    """
    if r["signal"] == "STRONG_BUY":
        return "Auto-eligible"

    ema20     = r["ema20"]
    ema50     = r["ema50"]
    ema200    = r["ema200"]
    macd      = r["macd"]
    rsi       = r["rsi"]
    risk      = r["risk_level"]
    trend_4h  = r.get("trend_4h", "neutral")
    score     = r["score"]
    volume_ok = bool(r.get("volume_ok", False))
    vol_ratio = float(r.get("volume_ratio", 1.0))
    near_zero = abs(ema20) * 0.001

    if risk == "HIGH":
        return "Risk HIGH"
    if trend_4h == "bearish":
        return "4H trend bearish"
    if ema20 < ema50 < ema200:
        return "EMA fully bearish"
    if ema20 < ema50:
        return "EMA20 below EMA50"
    if ema50 < ema200:
        return "EMA50 below EMA200"
    if macd <= near_zero:
        return "MACD not positive"
    if not volume_ok or vol_ratio < 0.8:
        return f"Low volume ({vol_ratio:.1f}x avg)"
    if rsi > 65:
        return f"RSI overbought ({rsi:.0f})"
    if trend_4h != "bullish":
        return f"4H trend {trend_4h} — needs bullish"
    if risk == "MEDIUM":
        return "Risk MEDIUM — capped to BUY_WATCH"
    if score < 70:
        return f"Score {score}/100 — below threshold"
    return "Conditions partially met"


def _build_reason(item: dict) -> str:
    """Generate a concise human-readable reason from signal data."""
    parts: list[str] = []

    ema20  = item["ema20"]
    ema50  = item["ema50"]
    ema200 = item["ema200"]
    rsi    = item["rsi"]
    macd   = item["macd"]
    vol_ok       = item["volume_ok"]
    volume_ratio = item.get("volume_ratio", 1.0)
    risk         = item["risk_level"]
    notes        = item.get("notes", "")
    near_zero    = abs(ema20) * 0.001

    if ema20 > ema50 > ema200:
        parts.append("full EMA bullish alignment")
    elif ema20 < ema50 < ema200:
        parts.append("full EMA bearish — avoid longs")
    elif ema20 > ema50:
        parts.append("short-term EMA bullish only")
    else:
        parts.append("EMA structure mixed")

    if macd > near_zero:
        parts.append("MACD bullish")
    elif macd > -near_zero:
        parts.append("MACD near crossover — watch")
    else:
        parts.append("MACD bearish")

    if 45 <= rsi <= 60:
        parts.append("RSI in sweet spot")
    elif rsi > 70:
        parts.append(f"RSI overbought ({rsi:.0f}) — reversal risk")
    elif rsi < 30:
        parts.append(f"RSI oversold ({rsi:.0f}) — potential bounce")

    if volume_ratio >= 1.2:
        parts.append("strong volume confirmation")
    elif volume_ratio >= 0.8:
        parts.append("average volume — watch carefully")
    else:
        parts.append("low volume — weak signal")

    if risk == "HIGH":
        parts.append("HIGH risk — conditions not safe")

    if notes and notes not in ("Risk check passed", ""):
        parts.append(notes)

    return " · ".join(parts) if parts else "No clear setup"


def _build_auto_check(guard_results: list[dict]) -> str:
    """Return the AUTO CHECK Telegram block appended after the signal report."""
    if not guard_results:
        return ""
    sep = "─" * 30
    lines = ["", sep, "🤖 <b>AUTO CHECK</b>", sep]
    for gr in guard_results:
        lines.append(gr.get("auto_check_msg", ""))
    return "\n".join(lines)


def build_report(results: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sep = "─" * 30
    lines: list[str] = [
        f"📊 <b>SIGNALS_ONLY REPORT</b>",
        f"🕐 {now}",
        "",
    ]

    for item in results:
        signal    = item["signal"]
        score     = item["score"]
        symbol    = item["symbol"]
        price     = item["price"]
        ema20     = item["ema20"]
        ema50     = item["ema50"]
        ema200    = item["ema200"]
        rsi       = item["rsi"]
        macd      = item["macd"]
        volume_ok    = item["volume_ok"]
        volume_ratio = item.get("volume_ratio", 1.0)
        risk         = item["risk_level"]

        lines.append(sep)
        lines.append(
            f"{_signal_emoji(signal)} <b>{symbol}</b>  ·  "
            f"<b>{signal}</b>  ·  Score: {score}/100"
        )
        lines.append(sep)
        lines.append(f"💰 Price:   ${price:,.2f}")
        lines.append(f"📈 Trend:   {_ema_trend_label(ema20, ema50, ema200)}")
        lines.append(f"📊 RSI:     {rsi:.1f} — {_rsi_label(rsi)}")
        lines.append(f"⚡ MACD:    {_macd_label(macd, ema20)}")
        lines.append(f"📦 Volume:  {_volume_label(volume_ratio)}")
        lines.append(f"🛡 Risk:    {risk}")
        lines.append(f"📝 {_build_reason(item)}")

        # ── Multi-timeframe + ATR levels ─────────────────────────────────────
        trend_4h     = item.get("trend_4h", "neutral")
        entry_1h     = item.get("entry_1h", "mixed")
        item_atr     = item.get("atr") or 0.0
        item_sl      = item.get("sl")
        item_tp1     = item.get("tp1")
        item_tp2     = item.get("tp2")

        lines.append(f"📐 4H Trend: {_trend_4h_label(trend_4h)}")
        lines.append(f"📍 1H Entry: {_entry_1h_label(entry_1h)}")
        if item_atr > 0:
            lines.append(f"〰 ATR(14):  {_fmt_price(item_atr)}")
            lines.append(f"🛑 SL idea:  {_fmt_price(item_sl)}  (entry − 1.5× ATR)")
            lines.append(f"🎯 TP1 idea: {_fmt_price(item_tp1)}  (entry + 1.5× ATR)")
            lines.append(f"   → after TP1: move SL to entry (breakeven)")
            lines.append(f"🎯 TP2 idea: {_fmt_price(item_tp2)}  (entry + 3.0× ATR)")
        lines.append(f"⏱ Time stop: exit if no momentum after 24h")
        lines.append("")

    # ── TOP OPPORTUNITIES ────────────────────────────────────────────────────
    top = sorted(
        [
            r for r in results
            if r["risk_level"] in ("LOW", "MEDIUM")
            and r["signal"] in ("STRONG_BUY", "BUY_WATCH")
        ],
        key=lambda r: r["score"],
        reverse=True,
    )

    lines.append(sep)
    lines.append("🎯 <b>TOP OPPORTUNITIES</b>")
    lines.append(sep)
    if top:
        for r in top:
            lines.append(
                f"✅ {r['symbol']}  {r['signal']}  |  "
                f"Score: {r['score']}/100  |  Risk: {r['risk_level']}"
            )
    else:
        lines.append("No clean setup now.")

    lines.append("")
    lines.append(sep)
    lines.append(
        "⚠️ <i>SIGNALS_ONLY — No orders placed. For manual review only.</i>"
    )

    return "\n".join(lines)


def build_scanner_section(scanner_results: list[dict]) -> str:
    """Build the compact SCANNER section appended after the main report."""
    if not scanner_results:
        return ""

    sep = "─" * 30
    lines: list[str] = [
        "", sep,
        f"🔍 <b>SCANNER — {len(scanner_results)} PAIRS</b>",
        sep, "",
    ]

    # ── AUTO ELIGIBLE (max 3, STRONG_BUY + LOW risk + HIGH volume) ──────────
    strong = [
        r for r in scanner_results
        if r["signal"] == "STRONG_BUY" and r["risk_level"] == "LOW"
    ][:3]
    lines.append("⚡ <b>AUTO ELIGIBLE</b>  (STRONG_BUY · LOW risk · HIGH volume)")
    if strong:
        for r in strong:
            atr = r.get("atr") or 0.0
            lines.append(
                f"🟢 <b>{r['symbol']}</b>  Score: {r['score']}/100"
                f"  |  {_fmt_price(r['price'])}"
            )
            lines.append(
                f"   4H: {r.get('trend_4h', '?').capitalize()}"
                f"  1H: {r.get('entry_1h', '?').capitalize()}"
                f"  RSI: {r['rsi']:.0f}"
                f"  Vol: {r.get('volume_tier', '?').upper()}"
            )
            if atr > 0:
                lines.append(
                    f"   🛑 {_fmt_price(r.get('sl'))}"
                    f"  🎯 TP1: {_fmt_price(r.get('tp1'))}"
                    f"  TP2: {_fmt_price(r.get('tp2'))}"
                )
            lines.append("")
    else:
        lines.append("   No auto-eligible setup now.")
        lines.append("")

    # ── TEST WATCH (max 3, BUY_WATCH — manual review only) ───────────────────
    watch = [r for r in scanner_results if r["signal"] == "BUY_WATCH"][:3]
    lines.append("📋 <b>TEST WATCH</b>  (BUY_WATCH — manual review, not auto-entry)")
    if watch:
        for r in watch:
            lines.append(
                f"🟡 <b>{r['symbol']}</b>  Score: {r['score']}/100"
                f"  |  {_fmt_price(r['price'])}"
                f"  |  4H: {r.get('trend_4h', '?').capitalize()}"
                f"  RSI: {r['rsi']:.0f}"
                f"  Vol: {r.get('volume_tier', '?').upper()}"
            )
            lines.append("   🚫 BLOCKED — observation only, not eligible for auto-entry")
            lines.append("")
    else:
        lines.append("   No BUY_WATCH setup now.")
        lines.append("")

    return "\n".join(lines)


def build_scanner_diagnostic(scanner_results: list[dict]) -> str:
    """Build a standalone diagnostic message: top 10 scanner results by score.

    Sent as a separate Telegram message so neither message exceeds the
    4096-character limit.  Shows signal, score, risk, 4H trend, 1H entry,
    RSI, MACD status, volume status, and the primary blocking condition.
    Block reason is always a market/strategy condition — never SIGNALS_ONLY.
    """
    if not scanner_results:
        return ""

    sep  = "─" * 30
    top  = sorted(scanner_results, key=lambda r: -r["score"])[:10]

    lines: list[str] = [
        sep,
        f"📋 <b>SCANNER DIAGNOSTIC — {len(scanner_results)} PAIRS</b>",
        f"Top {len(top)} by score",
        sep, "",
    ]

    _SIG_EMOJI = {
        "STRONG_BUY": "🟢", "BUY_WATCH": "🟡",
        "WAIT":       "🔵", "AVOID":     "🔴",
    }

    for r in top:
        signal    = r["signal"]
        score     = r["score"]
        risk      = r["risk_level"]
        trend_4h  = r.get("trend_4h", "neutral").capitalize()
        entry_1h  = r.get("entry_1h", "mixed").capitalize()
        rsi       = r["rsi"]
        macd      = r["macd"]
        vol_ratio = float(r.get("volume_ratio", 1.0))
        ema20     = r["ema20"]
        near_zero = abs(ema20) * 0.001
        emoji     = _SIG_EMOJI.get(signal, "⚪")

        macd_lbl = (
            "MACD positive"  if macd > near_zero  else
            "MACD neutral"   if macd > -near_zero else
            "MACD negative"
        )
        vol_lbl = (
            "Volume High"    if vol_ratio >= 1.2 else
            "Volume Average" if vol_ratio >= 0.8 else
            "Volume Low"
        )

        lines.append(
            f"{emoji} <b>{r['symbol']}</b>  |  {signal}  |  Score {score}  |  Risk {risk}"
        )
        lines.append(
            f"4H {trend_4h}  |  1H {entry_1h}"
            f"  |  RSI {rsi:.0f}  |  {macd_lbl}  |  {vol_lbl}"
        )
        if signal != "STRONG_BUY":
            lines.append(f"Blocked: {_scanner_block_reason(r)}")
        lines.append("")

    lines.append(sep)
    lines.append("⚠️ <i>SIGNALS_ONLY — No orders placed. Diagnostic only.</i>")
    return "\n".join(lines)


def main():
    load_dotenv()

    # ── SAFETY GATE: must be the very first check after loading env ──────────
    _enforce_trade_mode()
    # ─────────────────────────────────────────────────────────────────────────

    logger.info(
        f"Starting bot (TRADE_MODE={os.getenv('TRADE_MODE', 'SIGNALS_ONLY')} verified)"
    )
    ensure_data_files()

    # ── DAILY SIGNALS CAP (max 3 per day per RISK_MANAGER_SKILLS) ────────────
    stats = _load_daily_stats()
    signals_allowed, signals_today = _check_and_update_signal_count(stats)
    if not signals_allowed:
        msg = (
            f"Daily signal limit reached ({signals_today}/{SETTINGS.MAX_SIGNALS_PER_DAY}). "
            "Bot will not run until tomorrow."
        )
        logger.warning(msg)
        print(f"[DAILY CAP] {msg}")
        return
    logger.info(
        f"Signals sent today: {signals_today}/{SETTINGS.MAX_SIGNALS_PER_DAY}"
    )
    # ─────────────────────────────────────────────────────────────────────────

    try:
        market_data = fetch_market_data(SETTINGS.SYMBOLS, SETTINGS.TIMEFRAME, SETTINGS.LIMIT)
    except Exception as exc:
        logger.error(f"Market data fetch failed: {exc}")
        return

    try:
        data_4h = fetch_4h_data(SETTINGS.SYMBOLS)
    except Exception as exc:
        logger.warning(f"4H data fetch failed, trend filter disabled: {exc}")
        data_4h = {}

    results = []
    guard_results = []
    for symbol, df in market_data.items():
        if df is None or df.empty:
            logger.warning(f"No data for {symbol}")
            continue

        analysis = analyze_technical_indicators(df)

        # ── 4H trend filter ───────────────────────────────────────────────────
        df_4h    = data_4h.get(symbol)
        trend_4h = (
            analyze_trend_4h(df_4h)
            if df_4h is not None and not df_4h.empty
            else "neutral"
        )

        # ── 1H entry quality ──────────────────────────────────────────────────
        if analysis["ema20"] > analysis["ema50"] and analysis["macd"] > 0:
            entry_1h = "improving"
        elif analysis["ema20"] > analysis["ema50"]:
            entry_1h = "bullish"
        else:
            entry_1h = "mixed"

        # ── ATR-based SL / TP ideas ───────────────────────────────────────────
        price = float(df["close"].iloc[-1])
        atr   = analysis.get("atr", 0.0)
        sl    = round(price - atr * 1.5, 8) if atr > 0 else None
        tp1   = round(price + atr * 1.5, 8) if atr > 0 else None
        tp2   = round(price + atr * 3.0, 8) if atr > 0 else None

        news_sentiment = get_news_sentiment(symbol)
        risk_ok, risk_note, risk_level = assess_risk(symbol, analysis, news_sentiment)
        signal, score = decide_signal(
            symbol, analysis, news_sentiment, risk_ok, risk_level, trend_4h
        )

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "signal": signal,
            "price": price,
            "score": score,
            "ema20": analysis["ema20"],
            "ema50": analysis["ema50"],
            "ema200": analysis["ema200"],
            "rsi": analysis["rsi"],
            "macd": analysis["macd"],
            "volume_ok": analysis["volume_ok"],
            "volume_ratio": analysis.get("volume_ratio", 1.0),
            "news_sentiment": news_sentiment,
            "risk_level": risk_level,
            "notes": risk_note,
            "trend_4h": trend_4h,
            "entry_1h": entry_1h,
            "atr": atr,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "time_stop_hours": 24,
        }

        save_signal_record(record)
        results.append(record)
        guard_results.append(evaluate_trade(record))

    # ── Whitelist scanner (all 15 pairs) ─────────────────────────────────────
    scanner_results: list[dict] = []
    try:
        scanner_results = run_scanner(SETTINGS.SCANNER_SYMBOLS)
        save_scanner_results(scanner_results)
        logger.info(f"Scanner: {len(scanner_results)} pairs processed")
    except Exception as exc:
        logger.warning(f"Scanner failed: {exc}")
    # ─────────────────────────────────────────────────────────────────────────

    if results:
        message = (
            build_report(results)
            + _build_auto_check(guard_results)
            + build_scanner_section(scanner_results)
        )
        send_telegram_message(message)

        diag = build_scanner_diagnostic(scanner_results)
        if diag:
            send_telegram_message(diag)

        # Update daily counter only after a successful run with results
        stats["signals_sent"] = signals_today + 1
        stats["last_run"] = datetime.now(timezone.utc).isoformat()
        _save_daily_stats(stats)
        logger.info(
            f"Signals counter updated: {stats['signals_sent']}/{SETTINGS.MAX_SIGNALS_PER_DAY}"
        )
    else:
        logger.info("No valid results to report")


if __name__ == "__main__":
    main()
