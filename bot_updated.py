import json
import math
import os
import time
from datetime import datetime, UTC

import requests
import pandas as pd
import ta
from binance.client import Client

# =========================
# CONFIG
# =========================
# "demo" = only simulated trades
# "live" = real Binance market buy/sell
MODE = "live"

TOKEN = ""
CHAT_ID = ""

API_KEY = ""
API_SECRET = ""

client = Client(API_KEY, API_SECRET)

# Fixed clean list. Old code could scan many symbols, but signal logic allowed only 4.
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "NEARUSDT",
    "XRPUSDT",
    "ADAUSDT",
]

print("Trading symbols:", SYMBOLS)

TIMEFRAME = "1h"
LIMIT = 200
STATE_FILE = "state.json"

DEMO_BALANCE_START = 100.0

# Your current risk setup: 50 USDT per trade.
# The bot opens only ONE position at a time.
TRADE_SIZE = {
    "BTCUSDT": 50.0,
    "ETHUSDT": 50.0,
    "BNBUSDT": 50.0,
    "SOLUSDT": 50.0,
    "AVAXUSDT": 50.0,
    "LINKUSDT": 50.0,
    "NEARUSDT": 50.0,
    "XRPUSDT": 50.0,
    "ADAUSDT": 50.0,
}

# TP/SL by coin volatility
TAKE_PROFIT = {
    "BTCUSDT": 0.020,
    "ETHUSDT": 0.022,
    "BNBUSDT": 0.023,
    "SOLUSDT": 0.025,
    "AVAXUSDT": 0.028,
    "LINKUSDT": 0.025,
    "NEARUSDT": 0.030,
    "XRPUSDT": 0.022,
    "ADAUSDT": 0.022,
}

STOP_LOSS = {
    "BTCUSDT": 0.012,
    "ETHUSDT": 0.013,
    "BNBUSDT": 0.014,
    "SOLUSDT": 0.015,
    "AVAXUSDT": 0.018,
    "LINKUSDT": 0.015,
    "NEARUSDT": 0.018,
    "XRPUSDT": 0.014,
    "ADAUSDT": 0.014,
}

MAX_TRADES_PER_DAY = 2
MAX_DAILY_LOSS_PCT = 3.0

SLEEP_SECONDS = 180


# =========================
# TELEGRAM
# =========================
def send(msg: str) -> None:
    if not TOKEN or not CHAT_ID:
        print("Telegram not configured:", msg)
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=15)
    except Exception as e:
        print("Telegram error:", e)


# =========================
# STATE
# =========================
def today_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def default_state() -> dict:
    return {
        "mode": MODE,
        "balance": DEMO_BALANCE_START,
        "position": None,
        "daily": {
            "date": today_utc(),
            "trades": 0,
            "loss_pct": 0.0,
        },
        "sent_signals": {},
    }


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return default_state()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return default_state()

    if "mode" not in data:
        data["mode"] = MODE
    if "balance" not in data:
        data["balance"] = DEMO_BALANCE_START
    if "position" not in data:
        data["position"] = None
    if "daily" not in data:
        data["daily"] = {"date": today_utc(), "trades": 0, "loss_pct": 0.0}
    if "loss_pct" not in data["daily"]:
        data["daily"]["loss_pct"] = 0.0
    if "sent_signals" not in data:
        data["sent_signals"] = {}

    return data


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def reset_daily_if_needed(state: dict) -> None:
    if state["daily"]["date"] != today_utc():
        state["daily"] = {
            "date": today_utc(),
            "trades": 0,
            "loss_pct": 0.0,
        }
        state["sent_signals"] = {}


# =========================
# DATA
# =========================
def get_data(symbol: str, interval: str = TIMEFRAME, limit: int = LIMIT) -> pd.DataFrame:
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)

    df = pd.DataFrame(
        klines,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "num_trades",
            "taker_buy_base", "taker_buy_quote", "ignore",
        ],
    )

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df


def get_last_price(symbol: str) -> float:
    return float(client.get_symbol_ticker(symbol=symbol)["price"])


# =========================
# EXCHANGE FILTERS
# =========================
def get_symbol_filters(symbol: str):
    info = client.get_symbol_info(symbol)
    if not info:
        raise ValueError(f"Symbol info not found for {symbol}")

    lot_step = None
    min_qty = None
    min_notional = None

    for f in info["filters"]:
        if f["filterType"] == "LOT_SIZE":
            lot_step = float(f["stepSize"])
            min_qty = float(f["minQty"])
        elif f["filterType"] in ["MIN_NOTIONAL", "NOTIONAL"]:
            min_notional = float(f.get("minNotional", 0))

    return {
        "lot_step": lot_step,
        "min_qty": min_qty,
        "min_notional": min_notional,
    }


def round_step_size(quantity: float, step_size: float) -> float:
    if step_size is None or step_size == 0:
        return quantity

    precision = int(round(-math.log(step_size, 10), 0))
    return round(math.floor(quantity / step_size) * step_size, precision)


# =========================
# BTC MARKET FILTER
# =========================
def get_btc_filter() -> str:
    df = get_data("BTCUSDT")
    close = df["close"]

    ema20 = ta.trend.ema_indicator(close, window=20)
    ema50 = ta.trend.ema_indicator(close, window=50)

    last_close = float(close.iloc[-1])
    last_ema20 = float(ema20.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])

    if last_close > last_ema20 and last_ema20 >= last_ema50:
        return "BULLISH"

    if last_close < last_ema20 and last_ema20 < last_ema50:
        return "BEARISH"

    return "NEUTRAL"


# =========================
# ACTIVE H1 ENTRY
# =========================
def get_active_signal(symbol: str, btc_filter: str) -> dict | None:
    # Hard protection: if BTC is bearish, do not buy altcoins.
    # BTC/ETH are still allowed only if their own score is strong.
    if btc_filter == "BEARISH" and symbol not in ["BTCUSDT", "ETHUSDT"]:
        print(f"{symbol} | blocked by BTC BEARISH")
        return None

    df = get_data(symbol)

    close = df["close"]
    high = df["high"]
    volume = df["volume"]

    ema9 = ta.trend.ema_indicator(close, window=9)
    ema20 = ta.trend.ema_indicator(close, window=20)
    ema50 = ta.trend.ema_indicator(close, window=50)
    ema200 = ta.trend.ema_indicator(close, window=200)

    rsi = ta.momentum.rsi(close, window=14)
    macd = ta.trend.macd_diff(close)

    vol_avg = volume.rolling(20).mean()
    rolling_high = high.shift(1).rolling(10).max()

    last_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])

    last_ema9 = float(ema9.iloc[-1])
    last_ema20 = float(ema20.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])
    last_ema200 = float(ema200.iloc[-1])

    last_rsi = float(rsi.iloc[-1])
    last_macd = float(macd.iloc[-1])

    last_vol = float(volume.iloc[-1])
    last_vol_avg = float(vol_avg.iloc[-1]) if pd.notna(vol_avg.iloc[-1]) else 0
    last_breakout_level = float(rolling_high.iloc[-1]) if pd.notna(rolling_high.iloc[-1]) else 0

    score = 0
    reasons = []

    # 1. Main trend
    if last_close > last_ema20:
        score += 1
        reasons.append("price>EMA20")

    # 2. Short momentum
    if last_ema9 > last_ema20:
        score += 1
        reasons.append("EMA9>EMA20")

    # 3. H1 trend
    if last_ema20 >= last_ema50:
        score += 1
        reasons.append("EMA20>=EMA50")

    # 4. Large trend protection
    if last_close > last_ema200:
        score += 1
        reasons.append("price>EMA200")

    # 5. RSI not weak, not too overheated
    if 48 <= last_rsi <= 70:
        score += 1
        reasons.append("RSI_OK")

    # 6. MACD positive
    if last_macd > 0:
        score += 1
        reasons.append("MACD+")

    # 7. Volume
    if last_vol_avg > 0 and last_vol >= last_vol_avg * 0.8:
        score += 1
        reasons.append("volume_OK")

    # 8. Candle direction
    if last_close > prev_close:
        score += 1
        reasons.append("green_candle")

    # 9. Breakout / near breakout
    if last_breakout_level > 0 and last_close >= last_breakout_level * 0.997:
        score += 1
        reasons.append("near_breakout")

    # 10. BTC support
    if btc_filter == "BULLISH":
        score += 1
        reasons.append("BTC_BULLISH")

    if symbol in ["BTCUSDT", "ETHUSDT"]:
        min_score = 6
    elif symbol in ["BNBUSDT", "SOLUSDT", "AVAXUSDT", "LINKUSDT", "NEARUSDT"]:
        min_score = 6
    else:
        min_score = 7

    print(
        f"{symbol} | price={round(last_close, 6)} | "
        f"RSI={round(last_rsi, 2)} | score={score}/10 | "
        f"btc={btc_filter} | reasons={','.join(reasons)}"
    )

    if score >= min_score:
        return {
            "symbol": symbol,
            "mode": "ACTIVE_H1_V2",
            "entry": round(last_close, 6),
            "rsi": round(last_rsi, 2),
            "score": score,
            "reasons": reasons,
        }

    return None


# =========================
# TRADE RULES
# =========================
def can_open_trade(state: dict) -> tuple[bool, str]:
    if state["position"] is not None:
        return False, "already in position"

    if state["daily"]["trades"] >= MAX_TRADES_PER_DAY:
        return False, "daily trade limit"

    if state["daily"]["loss_pct"] >= MAX_DAILY_LOSS_PCT:
        return False, "daily loss limit"

    return True, ""


# =========================
# OPEN TRADE
# =========================
def open_trade(signal: dict, state: dict) -> None:
    symbol = signal["symbol"]
    entry = float(signal["entry"])

    trade_size_usdt = TRADE_SIZE.get(symbol, 50.0)
    take_profit_pct = TAKE_PROFIT.get(symbol, 0.025)
    stop_loss_pct = STOP_LOSS.get(symbol, 0.015)

    tp = entry * (1 + take_profit_pct)
    sl = entry * (1 - stop_loss_pct)

    if MODE == "demo":
        qty = trade_size_usdt / entry

        state["position"] = {
            "symbol": symbol,
            "mode": signal["mode"],
            "entry": entry,
            "qty": qty,
            "tp": tp,
            "sl": sl,
            "opened_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "order_type": "demo",
        }

        state["daily"]["trades"] += 1

        send(
            f"DEMO BUY\n"
            f"Symbol: {symbol}\n"
            f"Mode: {signal['mode']}\n"
            f"Entry: {round(entry, 6)}\n"
            f"Qty: {round(qty, 6)}\n"
            f"TP: {round(tp, 6)}\n"
            f"SL: {round(sl, 6)}\n"
            f"RSI: {signal['rsi']}\n"
            f"Score: {signal['score']}/10\n"
            f"Reasons: {', '.join(signal.get('reasons', []))}\n"
            f"Trade Size: {trade_size_usdt} USDT\n"
            f"Balance: {round(state['balance'], 2)} USDT"
        )
        return

    # LIVE MODE
    try:
        filters = get_symbol_filters(symbol)
        if filters["min_notional"] and trade_size_usdt < filters["min_notional"]:
            raise ValueError(
                f"trade_size_usdt too small for {symbol}. Need at least {filters['min_notional']}"
            )

        order = client.order_market_buy(
            symbol=symbol,
            quoteOrderQty=trade_size_usdt,
        )

        executed_qty = float(order["executedQty"])
        avg_price = entry

        if executed_qty > 0:
            cumulative_quote = float(order.get("cummulativeQuoteQty", 0))
            if cumulative_quote > 0:
                avg_price = cumulative_quote / executed_qty

        state["position"] = {
            "symbol": symbol,
            "mode": signal["mode"],
            "entry": avg_price,
            "qty": executed_qty,
            "tp": avg_price * (1 + take_profit_pct),
            "sl": avg_price * (1 - stop_loss_pct),
            "opened_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "order_type": "live",
            "buy_order_id": order["orderId"],
        }

        state["daily"]["trades"] += 1

        send(
            f"LIVE BUY\n"
            f"Symbol: {symbol}\n"
            f"Mode: {signal['mode']}\n"
            f"Entry: {round(avg_price, 6)}\n"
            f"Qty: {round(executed_qty, 6)}\n"
            f"TP: {round(state['position']['tp'], 6)}\n"
            f"SL: {round(state['position']['sl'], 6)}\n"
            f"RSI: {signal['rsi']}\n"
            f"Score: {signal['score']}/10\n"
            f"Reasons: {', '.join(signal.get('reasons', []))}\n"
            f"Trade Size: {trade_size_usdt} USDT"
        )

    except Exception as e:
        send(f"LIVE BUY ERROR\nSymbol: {symbol}\nError: {str(e)}")
        print("LIVE BUY ERROR:", e)


# =========================
# CLOSE TRADE
# =========================
def check_exit(state: dict) -> None:
    pos = state["position"]
    if pos is None:
        return

    symbol = pos["symbol"]

    last_price = get_last_price(symbol)

    df = get_data(symbol)
    close = df["close"]
    ema20 = ta.trend.ema_indicator(close, window=20)
    last_ema20 = float(ema20.iloc[-1])

    entry = float(pos["entry"])
    qty = float(pos["qty"])
    tp = float(pos["tp"])
    sl = float(pos["sl"])

    exit_reason = None
    if last_price >= tp:
        exit_reason = "TAKE_PROFIT"
    elif last_price <= sl:
        exit_reason = "STOP_LOSS"
    elif last_price < last_ema20 * 0.992:
        exit_reason = "TREND_BREAK"

    if exit_reason is None:
        print(
            f"Position open | {symbol} | entry={round(entry, 6)} | "
            f"price={round(last_price, 6)} | tp={round(tp, 6)} | sl={round(sl, 6)}"
        )
        return

    pnl_pct = ((last_price - entry) / entry) * 100.0

    if MODE == "demo":
        pnl_usdt = (last_price - entry) * qty
        state["balance"] = round(state["balance"] + pnl_usdt, 2)

        if exit_reason in ["STOP_LOSS", "TREND_BREAK"] and pnl_pct < 0:
            state["daily"]["loss_pct"] += abs(pnl_pct)

        send(
            f"DEMO CLOSE\n"
            f"Symbol: {symbol}\n"
            f"Mode: {pos['mode']}\n"
            f"Reason: {exit_reason}\n"
            f"Entry: {round(entry, 6)}\n"
            f"Exit: {round(last_price, 6)}\n"
            f"PnL: {round(pnl_usdt, 2)} USDT ({round(pnl_pct, 2)}%)\n"
            f"Balance: {round(state['balance'], 2)} USDT"
        )

        state["position"] = None
        state["sent_signals"] = {}
        return

    # LIVE MODE
    try:
        asset = symbol.replace("USDT", "")
        balance = client.get_asset_balance(asset=asset)
        free_qty = float(balance["free"])

        filters = get_symbol_filters(symbol)
        sell_qty = min(qty, free_qty)
        sell_qty = round_step_size(sell_qty, filters["lot_step"])

        if filters["min_qty"] and sell_qty < filters["min_qty"]:
            raise ValueError(f"Sell quantity too small after rounding: {sell_qty}")

        order = client.order_market_sell(
            symbol=symbol,
            quantity=sell_qty,
        )

        executed_qty = float(order["executedQty"])
        cumulative_quote = float(order.get("cummulativeQuoteQty", 0))
        avg_exit = last_price

        if executed_qty > 0 and cumulative_quote > 0:
            avg_exit = cumulative_quote / executed_qty

        pnl_usdt = (avg_exit - entry) * executed_qty
        pnl_pct_real = ((avg_exit - entry) / entry) * 100.0

        if exit_reason in ["STOP_LOSS", "TREND_BREAK"] and pnl_pct_real < 0:
            state["daily"]["loss_pct"] += abs(pnl_pct_real)

        send(
            f"LIVE CLOSE\n"
            f"Symbol: {symbol}\n"
            f"Mode: {pos['mode']}\n"
            f"Reason: {exit_reason}\n"
            f"Entry: {round(entry, 6)}\n"
            f"Exit: {round(avg_exit, 6)}\n"
            f"Qty: {round(executed_qty, 6)}\n"
            f"PnL: {round(pnl_usdt, 2)} USDT ({round(pnl_pct_real, 2)}%)"
        )

        state["position"] = None
        state["sent_signals"] = {}

    except Exception as e:
        send(f"LIVE CLOSE ERROR\nSymbol: {symbol}\nReason: {exit_reason}\nError: {str(e)}")
        print("LIVE CLOSE ERROR:", e)


# =========================
# MAIN CYCLE
# =========================
def run_cycle():
    state = load_state()
    reset_daily_if_needed(state)

    if state["position"] is not None:
        check_exit(state)
        save_state(state)
        return

    btc_filter = get_btc_filter()
    print(f"[{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}] BTC filter: {btc_filter}")

    can_trade, reason = can_open_trade(state)
    if not can_trade:
        print("SKIP:", reason)
        save_state(state)
        return

    for symbol in SYMBOLS:
        signal = get_active_signal(symbol, btc_filter)

        if signal is None:
            continue

        signal_key = f"{signal['symbol']}_{signal['mode']}_{signal['entry']}"
        if signal_key in state["sent_signals"]:
            print(f"{symbol} | duplicated signal skipped")
            continue

        open_trade(signal, state)
        state["sent_signals"][signal_key] = True
        break

    save_state(state)


# =========================
# START
# =========================
if __name__ == "__main__":
    print(f"Bot started in MODE={MODE}")
    send(f"Bot started\nMODE={MODE}\nSymbols: {', '.join(SYMBOLS)}")

    while True:
        try:
            run_cycle()
            print(f"Cycle finished. Sleeping {SLEEP_SECONDS} sec...\n")
            time.sleep(SLEEP_SECONDS)
        except Exception as e:
            print("ERROR:", e)
            send(f"BOT ERROR\n{str(e)}")
            time.sleep(60)
