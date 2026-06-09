"""
order_executor.py — Isolated order execution layer.

This is the ONLY file in the project that may place real Binance spot orders.
Every public function performs a full runtime guard before any API call.

Real orders are impossible unless ALL of the following are true at call time:
  1. TRADE_MODE       = AUTO_SPOT          (env)
  2. LIVE_TRADING_ENABLED = true           (env)
  3. KILL_SWITCH      = false              (env)
  4. usdt_amount      > 0                  (caller)
  5. usdt_amount     <= MAX_POSITION_USDT  (capped automatically)

Conditions 1–3 are re-read from the environment on every call — not cached —
so a .env change takes effect on the next run without restarting.

This module is NOT imported by main.py.
It is called only by agents/trade_guard.py when all guard conditions pass.
"""

import logging
import os

from binance.client import Client

from config.settings import SETTINGS

logger = logging.getLogger(__name__)

# Lazy client — created only when execution is actually attempted.
_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(SETTINGS.BINANCE_API_KEY, SETTINGS.BINANCE_API_SECRET)
    return _client


def _blocked(symbol: str, reason: str) -> dict:
    logger.info(f"[ORDER BLOCKED] {symbol}: {reason}")
    return {
        "executed":     False,
        "order_id":     None,
        "amount_usdt":  0.0,
        "executed_qty": 0.0,
        "symbol":       symbol,
        "reason":       reason,
    }


def place_spot_order(symbol: str, usdt_amount: float, current_price: float) -> dict:
    """
    Attempt a market BUY order for `usdt_amount` USDT worth of `symbol`.

    Returns:
        {
          "executed":    bool,
          "order_id":    str | None,
          "amount_usdt": float,
          "symbol":      str,
          "reason":      str,
        }

    Defence-in-depth: even if trade_guard already checked these conditions,
    this function re-checks them independently on every call.
    """
    # ── Runtime guard 1: TRADE_MODE ──────────────────────────────────────────
    trade_mode = os.getenv("TRADE_MODE", "SIGNALS_ONLY")
    if trade_mode != "AUTO_SPOT":
        return _blocked(symbol, f"TRADE_MODE={trade_mode!r} — must be AUTO_SPOT")

    # ── Runtime guard 2: LIVE_TRADING_ENABLED ────────────────────────────────
    if os.getenv("LIVE_TRADING_ENABLED", "false").lower() != "true":
        return _blocked(symbol, "LIVE_TRADING_ENABLED is not true")

    # ── Runtime guard 3: KILL_SWITCH ─────────────────────────────────────────
    if os.getenv("KILL_SWITCH", "false").lower() == "true":
        return _blocked(symbol, "KILL_SWITCH is active — all orders blocked")

    # ── Input validation ──────────────────────────────────────────────────────
    if usdt_amount <= 0:
        return _blocked(symbol, "usdt_amount must be positive")
    if current_price <= 0:
        return _blocked(symbol, "current_price must be positive")

    # ── Cap position size ─────────────────────────────────────────────────────
    if usdt_amount > SETTINGS.MAX_POSITION_USDT:
        logger.warning(
            f"[ORDER CAP] {symbol}: {usdt_amount:.2f} USDT capped to "
            f"MAX_POSITION_USDT={SETTINGS.MAX_POSITION_USDT}"
        )
        usdt_amount = SETTINGS.MAX_POSITION_USDT

    # ── Place order ───────────────────────────────────────────────────────────
    try:
        order = _get_client().order_market_buy(
            symbol=symbol,
            quoteOrderQty=usdt_amount,
        )
        order_id      = str(order.get("orderId", "unknown"))
        # Use actual fill values from the Binance response — never approximate.
        # cummulativeQuoteQty = USDT actually spent (may differ from requested).
        # executedQty         = coin units actually received.
        filled_usdt   = float(order.get("cummulativeQuoteQty", usdt_amount))
        filled_qty    = float(order.get("executedQty", 0.0))
        logger.info(
            f"[ORDER EXECUTED] {symbol} market buy | "
            f"filledUSDT={filled_usdt:.4f} | filledQty={filled_qty:.6f} | "
            f"orderId={order_id}"
        )
        return {
            "executed":      True,
            "order_id":      order_id,
            "amount_usdt":   filled_usdt,   # actual USDT spent (from exchange)
            "executed_qty":  filled_qty,    # actual coin units received
            "symbol":        symbol,
            "reason":        f"Market buy placed — orderId={order_id}",
        }
    except Exception as exc:
        logger.error(f"[ORDER FAILED] {symbol}: {exc}")
        return {
            "executed":     False,
            "order_id":     None,
            "amount_usdt":  usdt_amount,
            "executed_qty": 0.0,
            "symbol":       symbol,
            "reason":       f"Binance API error: {exc}",
        }
