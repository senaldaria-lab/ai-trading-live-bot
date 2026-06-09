"""
scanner.py — Whitelist market scanner for the AI Trading Agent.

Scans SCANNER_SYMBOLS using the existing strategy pipeline:
  4H trend · 1H entry · EMA · RSI · MACD · Volume · ATR · Score · Risk

Results are sorted: STRONG_BUY first → BUY_WATCH → WAIT → AVOID,
then LOW risk before MEDIUM/HIGH, then score descending.

Saves to data/scanner_log.csv.
Never places orders.  SIGNALS_ONLY by default.
Does not import from main.py, binance_service order functions, or legacy_tests.
"""

import logging
import os
from datetime import datetime, timezone

import pandas as pd

from agents.market_watcher import fetch_4h_data
from agents.news_agent import get_news_sentiment
from agents.risk_manager import assess_risk
from agents.signal_decision import decide_signal
from agents.technical_analysis import analyze_technical_indicators, analyze_trend_4h
from config.settings import SETTINGS
from services.binance_service import get_ohlcv

logger = logging.getLogger(__name__)

_SIGNAL_ORDER = {"STRONG_BUY": 0, "BUY_WATCH": 1, "WAIT": 2, "AVOID": 3}
_RISK_ORDER   = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def run_scanner(symbols: list[str]) -> list[dict]:
    """Scan all symbols and return results sorted by signal priority, risk, score."""
    results: list[dict] = []

    try:
        data_4h = fetch_4h_data(symbols)
    except Exception as exc:
        logger.warning(f"[SCANNER] 4H data fetch failed, trend filter disabled: {exc}")
        data_4h = {}

    for symbol in symbols:
        try:
            df = get_ohlcv(symbol, interval=SETTINGS.TIMEFRAME, limit=SETTINGS.LIMIT)
            if df is None or df.empty:
                logger.warning(f"[SCANNER] No 1H data for {symbol} — skipped")
                continue

            analysis = analyze_technical_indicators(df)

            df_4h    = data_4h.get(symbol)
            trend_4h = (
                analyze_trend_4h(df_4h)
                if df_4h is not None and not df_4h.empty
                else "neutral"
            )

            if analysis["ema20"] > analysis["ema50"] and analysis["macd"] > 0:
                entry_1h = "improving"
            elif analysis["ema20"] > analysis["ema50"]:
                entry_1h = "bullish"
            else:
                entry_1h = "mixed"

            price = float(df["close"].iloc[-1])
            atr   = analysis.get("atr", 0.0)
            sl    = round(price - atr * 1.5, 8) if atr > 0 else None
            tp1   = round(price + atr * 1.5, 8) if atr > 0 else None
            tp2   = round(price + atr * 3.0, 8) if atr > 0 else None

            news_sentiment             = get_news_sentiment(symbol)
            risk_ok, risk_note, risk_level = assess_risk(symbol, analysis, news_sentiment)
            signal, score              = decide_signal(
                symbol, analysis, news_sentiment, risk_ok, risk_level, trend_4h
            )

            results.append({
                "timestamp":       datetime.now(timezone.utc).isoformat(),
                "symbol":          symbol,
                "signal":          signal,
                "price":           price,
                "score":           score,
                "ema20":           analysis["ema20"],
                "ema50":           analysis["ema50"],
                "ema200":          analysis["ema200"],
                "rsi":             analysis["rsi"],
                "macd":            analysis["macd"],
                "volume_ok":       analysis["volume_ok"],
                "volume_ratio":    analysis.get("volume_ratio", 1.0),
                "news_sentiment":  news_sentiment,
                "risk_level":      risk_level,
                "notes":           risk_note,
                "trend_4h":        trend_4h,
                "entry_1h":        entry_1h,
                "atr":             atr,
                "sl":              sl,
                "tp1":             tp1,
                "tp2":             tp2,
                "time_stop_hours": 24,
            })
            logger.info(
                f"[SCANNER] {symbol}: {signal} score={score} "
                f"risk={risk_level} 4H={trend_4h}"
            )

        except Exception as exc:
            logger.warning(f"[SCANNER] {symbol} skipped: {exc}")

    results.sort(key=lambda r: (
        _SIGNAL_ORDER.get(r["signal"], 9),
        _RISK_ORDER.get(r["risk_level"], 9),
        -r["score"],
    ))
    return results


def save_scanner_results(results: list[dict]) -> None:
    """Append scanner results to SCANNER_LOG_CSV (creates file with header if new)."""
    if not results:
        return
    os.makedirs(SETTINGS.DATA_DIR, exist_ok=True)
    path = SETTINGS.SCANNER_LOG_CSV
    df = pd.DataFrame(results)
    write_header = not os.path.exists(path)
    df.to_csv(path, mode="a", header=write_header, index=False)
    logger.info(f"[SCANNER] Saved {len(results)} records to {path}")
