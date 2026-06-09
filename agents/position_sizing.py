"""
position_sizing.py — Safe position size calculator (manual reference only).

Formula:
  risk_amount    = account_usdt × (risk_pct / 100)
  stop_distance  = entry_price − stop_price
  position_units = risk_amount / stop_distance
  position_usdt  = position_units × entry_price

Caps applied (in order):
  1. risk_pct clamped to 0.5 – 1.0 %
  2. position_usdt capped at 30 % of account_usdt
  3. position_usdt capped at SETTINGS.MAX_POSITION_USDT

This module never executes orders.  Output is for manual review only.
"""

import logging

from config.settings import SETTINGS

logger = logging.getLogger(__name__)

_RISK_MIN_PCT          = 0.5
_RISK_MAX_PCT          = 1.0
_MAX_SINGLE_POSITION_PCT = 30.0   # no single position > 30 % of account


def calculate(
    entry_price:  float,
    stop_price:   float,
    account_usdt: float,
    risk_pct:     float = 1.0,
) -> dict:
    """
    Calculate a safe manual position size.

    Args:
        entry_price:  planned entry price in USDT
        stop_price:   stop-loss price (must be below entry for a long)
        account_usdt: total account value in USDT
        risk_pct:     percent of account to risk (clamped to 0.5 – 1.0)

    Returns:
        {
          "valid":            bool,
          "position_usdt":    float,
          "position_units":   float,
          "risk_amount_usdt": float,
          "stop_distance":    float,
          "risk_pct_used":    float,
          "cap_applied":      bool,
          "notes":            str,
        }
    """
    # ── Clamp risk percent ────────────────────────────────────────────────────
    risk_pct = max(_RISK_MIN_PCT, min(_RISK_MAX_PCT, risk_pct))

    # ── Input validation ──────────────────────────────────────────────────────
    if entry_price <= 0 or stop_price <= 0 or account_usdt <= 0:
        return _invalid("entry_price, stop_price, and account_usdt must all be > 0")

    if stop_price >= entry_price:
        return _invalid(
            f"stop_price ({stop_price}) must be below entry_price ({entry_price}) "
            "for a long position"
        )

    stop_distance = entry_price - stop_price
    if stop_distance <= 0:
        return _invalid("Stop distance is zero — cannot calculate position size")

    # ── Core formula ──────────────────────────────────────────────────────────
    risk_amount    = account_usdt * (risk_pct / 100.0)
    position_units = risk_amount / stop_distance
    position_usdt  = position_units * entry_price

    # ── Apply caps ────────────────────────────────────────────────────────────
    cap_30pct     = account_usdt * (_MAX_SINGLE_POSITION_PCT / 100.0)
    effective_cap = min(SETTINGS.MAX_POSITION_USDT, cap_30pct)
    cap_applied   = False
    notes: list[str] = []

    if position_usdt > effective_cap:
        cap_applied    = True
        position_usdt  = effective_cap
        position_units = position_usdt / entry_price
        notes.append(
            f"Position capped at ${effective_cap:.2f} "
            f"(MAX_POSITION_USDT=${SETTINGS.MAX_POSITION_USDT:.0f}, "
            f"30%-cap=${cap_30pct:.2f})"
        )

    notes += [
        "Spot only — no leverage",
        "Stop level must be confirmed before entry",
        "No profit guarantee",
    ]

    logger.debug(
        f"[POSITION SIZE] entry={entry_price} stop={stop_price} "
        f"risk={risk_pct}% account={account_usdt} "
        f"→ {position_usdt:.2f} USDT / {position_units:.6f} units"
    )

    return {
        "valid":            True,
        "position_usdt":    round(position_usdt, 2),
        "position_units":   round(position_units, 6),
        "risk_amount_usdt": round(risk_amount, 2),
        "stop_distance":    round(stop_distance, 6),
        "risk_pct_used":    risk_pct,
        "cap_applied":      cap_applied,
        "notes":            " | ".join(notes),
    }


def _invalid(reason: str) -> dict:
    logger.warning(f"[POSITION SIZE INVALID] {reason}")
    return {
        "valid":            False,
        "position_usdt":    0.0,
        "position_units":   0.0,
        "risk_amount_usdt": 0.0,
        "stop_distance":    0.0,
        "risk_pct_used":    0.0,
        "cap_applied":      False,
        "notes":            f"INVALID: {reason}",
    }
