"""
trade_guard.py — Pre-execution gate for the auto-trading layer.

Checks every condition required for a real order.  If ALL thirteen pass,
calls order_executor.place_spot_order(); otherwise returns a denial.

Conditions (ALL thirteen must be true for an order to be attempted):
  1.  TRADE_MODE            = AUTO_SPOT
  2.  LIVE_TRADING_ENABLED  = true
  3.  KILL_SWITCH           = false
  4.  signal                = STRONG_BUY  (BUY_WATCH is observation-only)
  5.  trend_4h              = bullish     (4H EMA20 > EMA50 required — neutral blocks too)
  6.  entry_1h              = bullish or improving  (1H structure must be aligned)
  7.  risk_level            = LOW
  8.  score                >= 75 / 100   (minimum confidence — HARD BLOCK below this)
  9.  macd                  > 0          (negative MACD blocks auto-trade)
  10. rsi                   45–65        (outside this band blocks auto-trade)
  11. volume confirmed       = True  (volume_ratio >= 0.8 — HARD BLOCK if not)
  12. trades_today          < MAX_TRADES_PER_DAY   (default 3)
  13. daily_loss_usdt       < MAX_DAILY_LOSS_USDT  (default $2 — HARD STOP)

This module is called by main.py once per symbol after signal generation.
It never imports from main.py or binance_service.py.
"""

import json
import logging
import os
from datetime import date

from config.settings import SETTINGS

logger = logging.getLogger(__name__)


def evaluate_trade(record: dict) -> dict:
    """
    Evaluate whether a signal record qualifies for auto-execution.

    Args:
        record: the signal record dict produced by main.py
                (keys: symbol, signal, risk_level, volume_ok, price, …)

    Returns:
        {
          "symbol":         str,
          "allowed":        bool,   # True only when ALL conditions pass
          "executed":       bool,   # True when an order was actually placed
          "reason":         str,
          "auto_check_msg": str,    # one-line string for Telegram AUTO CHECK
        }
    """
    symbol       = record.get("symbol", "UNKNOWN")
    signal       = record.get("signal", "")
    risk_level   = record.get("risk_level", "HIGH")
    volume_ok    = bool(record.get("volume_ok", False))
    volume_ratio = float(record.get("volume_ratio", 0.0))
    score        = int(record.get("score", 0))
    price        = float(record.get("price", 0.0))
    trend_4h     = record.get("trend_4h", "neutral")
    entry_1h     = record.get("entry_1h", "mixed")
    macd         = float(record.get("macd", 0.0))
    rsi          = float(record.get("rsi", 50.0))

    def _deny(reason: str) -> dict:
        logger.info(f"[TRADE GUARD] DENY  {symbol}: {reason}")
        return {
            "symbol":         symbol,
            "allowed":        False,
            "executed":       False,
            "reason":         reason,
            "auto_check_msg": f"🚫 {symbol}: {reason}",
        }

    # ── Condition 1: TRADE_MODE ───────────────────────────────────────────────
    trade_mode = os.getenv("TRADE_MODE", "SIGNALS_ONLY")
    if trade_mode == "SIGNALS_ONLY":
        return _deny("SIGNALS_ONLY mode — auto-trading disabled")
    if trade_mode != "AUTO_SPOT":
        return _deny(f"TRADE_MODE={trade_mode!r} is not a recognised active mode")

    # ── Condition 2: LIVE_TRADING_ENABLED ────────────────────────────────────
    if os.getenv("LIVE_TRADING_ENABLED", "false").lower() != "true":
        return _deny("LIVE_TRADING_ENABLED is not true")

    # ── Condition 3: KILL_SWITCH ─────────────────────────────────────────────
    if os.getenv("KILL_SWITCH", "false").lower() == "true":
        return _deny("KILL_SWITCH is active — all trades blocked")

    # ── Condition 4: Signal must be STRONG_BUY ───────────────────────────────
    # BUY_WATCH is for manual observation only — never eligible for auto-entry.
    if signal == "BUY_WATCH":
        return _deny("BLOCKED — observation only, not eligible for auto-entry")
    if signal != "STRONG_BUY":
        return _deny(f"Signal={signal!r} — only STRONG_BUY qualifies")

    # ── Condition 5: 4H trend must be bullish ────────────────────────────────
    # Neutral and bearish 4H structures both block auto-entry.
    # Only a confirmed bullish 4H (EMA20 > EMA50) qualifies.
    if trend_4h != "bullish":
        return _deny(f"4H trend={trend_4h!r} — must be bullish for auto-entry")

    # ── Condition 6: 1H entry must be bullish or improving ───────────────────
    if entry_1h not in ("bullish", "improving"):
        return _deny(f"1H entry={entry_1h!r} — must be bullish or improving")

    # ── Condition 7: Risk must be LOW ─────────────────────────────────────────
    if risk_level != "LOW":
        return _deny(f"Risk={risk_level!r} — only LOW risk qualifies")

    # ── Condition 8: Minimum confidence score — HARD BLOCK ────────────────────
    # 75/100 required for auto-execution (stricter than the 70 signal threshold).
    # Defence-in-depth: checked independently so no scoring change bypasses it.
    if score < 75:
        return _deny(f"Score={score}/100 below minimum 75 — HARD BLOCK")

    # ── Condition 9: MACD must be positive ────────────────────────────────────
    # Negative MACD means bearish momentum — auto-trade blocked regardless of label.
    if macd <= 0:
        return _deny(f"MACD={macd:.6f} ≤ 0 — negative MACD blocks auto-trade")

    # ── Condition 10: RSI must be in the 45–65 entry band ─────────────────────
    # Below 45: momentum not yet confirmed.  Above 65: overbought, reversal risk.
    if not (45.0 <= rsi <= 65.0):
        return _deny(f"RSI={rsi:.1f} outside 45–65 entry band — auto-trade blocked")

    # ── Condition 11: Volume confirmed — HARD BLOCK ───────────────────────────
    # Low volume can never produce an auto-trade regardless of other indicators.
    if not volume_ok or volume_ratio < 0.8:
        return _deny(
            f"Volume not confirmed — HARD BLOCK "
            f"(volume_ok={volume_ok}, volume_ratio={volume_ratio:.2f})"
        )

    # ── Condition 12: Daily trade cap ─────────────────────────────────────────
    trades_today = _read_trades_today()
    if trades_today >= SETTINGS.MAX_TRADES_PER_DAY:
        return _deny(
            f"Daily trade cap reached ({trades_today}/{SETTINGS.MAX_TRADES_PER_DAY})"
        )

    # ── Condition 13: Daily loss hard stop ────────────────────────────────────
    # Once the daily loss reaches MAX_DAILY_LOSS_USDT ($2 default), ALL further
    # auto-trades are blocked for the rest of the calendar day — no exceptions.
    daily_loss = _read_daily_loss()
    if daily_loss >= SETTINGS.MAX_DAILY_LOSS_USDT:
        return _deny(
            f"Daily loss HARD STOP reached "
            f"(${daily_loss:.2f} / ${SETTINGS.MAX_DAILY_LOSS_USDT:.2f}) — "
            f"no further auto-trades today"
        )

    # ── All conditions passed — attempt execution ─────────────────────────────
    logger.info(f"[TRADE GUARD] ALLOW {symbol}: all 13 conditions passed")

    from services.order_executor import place_spot_order  # local import — isolated
    exec_result = place_spot_order(
        symbol=symbol,
        usdt_amount=SETTINGS.MAX_POSITION_USDT,
        current_price=price,
    )

    if exec_result["executed"]:
        msg = (
            f"✅ {symbol}: Order placed | "
            f"USDT={exec_result['amount_usdt']:.4f} | "
            f"qty={exec_result.get('executed_qty', 0.0):.6f} | "
            f"orderId={exec_result['order_id']}"
        )
    else:
        msg = f"⚠️ {symbol}: Guard passed but order blocked — {exec_result['reason']}"

    return {
        "symbol":         symbol,
        "allowed":        True,
        "executed":       exec_result["executed"],
        "reason":         exec_result["reason"],
        "auto_check_msg": msg,
    }


# ── Stats helpers (read-only, never modify files) ─────────────────────────────

def _read_stats() -> dict:
    try:
        path = SETTINGS.DAILY_STATS_JSON
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _read_trades_today() -> int:
    stats = _read_stats()
    if stats.get("trades_date") != date.today().isoformat():
        return 0
    return int(stats.get("trades_today", 0))


def _read_daily_loss() -> float:
    stats = _read_stats()
    if stats.get("loss_date") != date.today().isoformat():
        return 0.0
    return float(stats.get("daily_loss_usdt", 0.0))
