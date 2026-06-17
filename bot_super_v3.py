import json
import math
import os
import time
from datetime import datetime, UTC

import requests
import pandas as pd
import ta
from binance.client import Client

# ============================================================
# BINANCE ALTCOIN BOT SUPER v3
# Spot only | No leverage | No martingale | One position only
# Built for small account around 100 USDT
# ============================================================

# ============================================================
# CONFIG
# ============================================================
# IMPORTANT:
# demo = simulated trades only, no real Binance orders
# live = real Binance market buy/sell orders
MODE = "live"

def _load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env()

TOKEN = os.environ["TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
API_KEY = os.environ["API_KEY"]
API_SECRET = os.environ["API_SECRET"]

client = Client(API_KEY, API_SECRET)

TIMEFRAME = "1h"
LIMIT = 220
STATE_FILE = "state.json"

DEMO_BALANCE_START = 100.0

# Small account risk setup
TRADE_SIZE_USDT = 100.0
MAX_TRADES_PER_DAY = 4
MAX_DAILY_LOSS_PCT = 2.5

# TP/SL for aggressive but controlled spot trading
TP_BASE = 0.015   # +1.5%
SL_BASE = 0.009   # -0.9%

# Dynamic scanner filters
MIN_VOLUME_USDT_24H = 15_000_000
MIN_ABS_CHANGE_24H = 1.2      # absolute 24h movement, percent
MAX_ABS_CHANGE_24H = 12.0     # avoid already overheated pumps
MIN_SCORE_TO_TRADE = 6

# BTC market filter
BTC_BEARISH_BLOCK = True

# Stablecoins / risky synthetic names to skip
EXCLUDED_SYMBOLS = {
    "BTCUSDT", "ETHUSDT",
    "USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT", "DAIUSDT",
    "EURUSDT", "TRYUSDT", "USDPUSDT",
}

BAD_SYMBOL_PARTS = [
    "UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT",
]

# Preferred liquid altcoins first, then dynamic scanner adds live movers
BASE_SYMBOLS = [
    "BNBUSDT",
    "SOLUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "NEARUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "DOGEUSDT",
    "TRXUSDT",
]

SLEEP_SECONDS = 180


# ============================================================
# TELEGRAM
# ============================================================
def send(msg: str) -> None:
    if not TOKEN or not CHAT_ID:
        print("Telegram not configured:", msg)
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=15)
    except Exception as e:
        print("Telegram error:", e)


# ============================================================
# STATE
# ============================================================
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
            "pnl_usdt": 0.0,
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
        data["daily"] = {"date": today_utc(), "trades": 0, "loss_pct": 0.0, "pnl_usdt": 0.0}
    if "loss_pct" not in data["daily"]:
        data["daily"]["loss_pct"] = 0.0
    if "pnl_usdt" not in data["daily"]:
        data["daily"]["pnl_usdt"] = 0.0
    if "sent_signals" not in data:
        data["sent_signals"] = {}

    return data


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def reset_daily_if_needed(state: dict) -> None:
    if state["daily"]["date"] != today_utc():
        send(
            f"DAILY RESET\n"
            f"Date: {state['daily']['date']}\n"
            f"Trades: {state['daily'].get('trades', 0)}\n"
            f"PnL: {round(state['daily'].get('pnl_usdt', 0.0), 3)} USDT\n"
            f"Loss pct: {round(state['daily'].get('loss_pct', 0.0), 2)}%"
        )
        state["daily"] = {
            "date": today_utc(),
            "trades": 0,
            "loss_pct": 0.0,
            "pnl_usdt": 0.0,
        }
        state["sent_signals"] = {}


# ============================================================
# DATA
# ============================================================
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

    for col in ["open", "high", "low", "close", "volume", "quote_asset_volume"]:
        df[col] = df[col].astype(float)

    return df


def get_last_price(symbol: str) -> float:
    return float(client.get_symbol_ticker(symbol=symbol)["price"])


# ============================================================
# EXCHANGE FILTERS
# ============================================================
def get_symbol_filters(symbol: str) -> dict:
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


# ============================================================
# DYNAMIC ALTCOIN SCANNER
# ============================================================
def get_live_symbols(limit: int = 12) -> list[str]:
    try:
        tickers = client.get_ticker()
        exchange_info = client.get_exchange_info()

        active_usdt = set()
        for s in exchange_info["symbols"]:
            if (
                s.get("quoteAsset") == "USDT"
                and s.get("status") == "TRADING"
                and s.get("isSpotTradingAllowed")
            ):
                active_usdt.add(s["symbol"])

        candidates = []
        for t in tickers:
            symbol = t.get("symbol", "")

            if symbol not in active_usdt:
                continue
            if symbol in EXCLUDED_SYMBOLS:
                continue
            if any(part in symbol for part in BAD_SYMBOL_PARTS):
                continue

            try:
                quote_volume = float(t.get("quoteVolume", 0))
                change_pct = abs(float(t.get("priceChangePercent", 0)))
            except Exception:
                continue

            if quote_volume < MIN_VOLUME_USDT_24H:
                continue
            if change_pct < MIN_ABS_CHANGE_24H:
                continue
            if change_pct > MAX_ABS_CHANGE_24H:
                continue

            candidates.append((symbol, quote_volume, change_pct))

        dynamic = sorted(candidates, key=lambda x: (x[2], x[1]), reverse=True)
        dynamic_symbols = [x[0] for x in dynamic]

        final = []
        for s in BASE_SYMBOLS + dynamic_symbols:
            if s not in final and s not in EXCLUDED_SYMBOLS:
                final.append(s)

        return final[:limit]

    except Exception as e:
        print("Scanner error:", e)
        return BASE_SYMBOLS[:limit]


# ============================================================
# BTC MARKET FILTER
# ============================================================
def get_btc_filter() -> str:
    df = get_data("BTCUSDT")
    close = df["close"]

    ema50 = ta.trend.ema_indicator(close, window=50)
    ema200 = ta.trend.ema_indicator(close, window=200)

    last_close = float(close.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])
    last_ema200 = float(ema200.iloc[-1])

    if last_close > last_ema50 and last_ema50 > last_ema200:
        return "BULLISH"

    if last_close < last_ema50 and last_ema50 < last_ema200:
        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# SCORE-BASED ENTRY LOGIC
# ============================================================
def get_active_signal(symbol: str, btc_filter: str) -> dict | None:
    # In spot trading we only buy. If BTC is bearish, block altcoin longs.
    if BTC_BEARISH_BLOCK and btc_filter == "BEARISH":
        print(f"{symbol} | blocked by BTC BEARISH")
        return None

    df = get_data(symbol)
    if df.empty or len(df) < 210:
        print(f"{symbol} | not enough data")
        return None

    close = df["close"]
    high = df["high"]
    volume = df["volume"]

    ema9 = ta.trend.ema_indicator(close, window=9)
    ema20 = ta.trend.ema_indicator(close, window=20)
    ema50 = ta.trend.ema_indicator(close, window=50)
    ema200 = ta.trend.ema_indicator(close, window=200)

    rsi = ta.momentum.rsi(close, window=14)
    macd_obj = ta.trend.MACD(close)
    macd_line = macd_obj.macd()
    macd_signal = macd_obj.macd_signal()

    vol_avg = volume.rolling(20).mean()
    breakout_level = high.shift(1).rolling(5).max()

    last_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])

    last_ema9 = float(ema9.iloc[-1])
    last_ema20 = float(ema20.iloc[-1])
    last_ema50 = float(ema50.iloc[-1])
    last_ema200 = float(ema200.iloc[-1])

    last_rsi = float(rsi.iloc[-1])
    last_macd_line = float(macd_line.iloc[-1])
    last_macd_signal = float(macd_signal.iloc[-1])

    last_vol = float(volume.iloc[-1])
    last_vol_avg = float(vol_avg.iloc[-1]) if pd.notna(vol_avg.iloc[-1]) else 0.0
    last_breakout = float(breakout_level.iloc[-1]) if pd.notna(breakout_level.iloc[-1]) else 0.0

    score = 0
    reasons = []

    # 1. RSI: aggressive but not crazy overbought
    if 35 <= last_rsi <= 58:
        score += 2
        reasons.append(f"RSI_GOOD:{round(last_rsi, 2)}")
    elif 58 < last_rsi <= 70:
        score += 1
        reasons.append(f"RSI_OK:{round(last_rsi, 2)}")
    else:
        reasons.append(f"RSI_BAD:{round(last_rsi, 2)}")

    # 2. Short-term trend
    if last_close > last_ema9 and last_close > last_ema20:
        score += 2
        reasons.append("price>EMA9/20")

    # 3. Medium trend
    if last_close > last_ema50:
        score += 1
        reasons.append("price>EMA50")

    # 4. Long trend protection
    if last_close > last_ema200:
        score += 1
        reasons.append("price>EMA200")

    # 5. EMA structure
    if last_ema9 > last_ema20 >= last_ema50:
        score += 1
        reasons.append("EMA9>20>=50")

    # 6. MACD momentum
    if last_macd_line > last_macd_signal:
        score += 1
        reasons.append("MACD_bullish")

    # 7. Volume activity
    if last_vol_avg > 0 and last_vol >= last_vol_avg * 1.05:
        score += 1
        reasons.append(f"volume:{round(last_vol / last_vol_avg, 2)}x")

    # 8. Candle direction
    if last_close > prev_close:
        score += 1
        reasons.append("green_candle")

    # 9. Breakout / near breakout
    if last_breakout > 0 and last_close >= last_breakout * 0.998:
        score += 1
        reasons.append("near_breakout")

    # 10. BTC support
    if btc_filter == "BULLISH":
        score += 1
        reasons.append("BTC_BULLISH")
    elif btc_filter == "NEUTRAL":
        reasons.append("BTC_NEUTRAL")

    print(
        f"{symbol} | price={round(last_close, 6)} | "
        f"RSI={round(last_rsi, 2)} | score={score}/12 | "
        f"btc={btc_filter} | reasons={','.join(reasons)}"
    )

    if score >= MIN_SCORE_TO_TRADE:
        # Dynamic TP: stronger score gets slightly more room
        tp_pct = TP_BASE + max(0, score - MIN_SCORE_TO_TRADE) * 0.001
        sl_pct = SL_BASE

        return {
            "symbol": symbol,
            "mode": "SUPER_ALT_V3",
            "entry": round(last_close, 6),
            "rsi": round(last_rsi, 2),
            "score": score,
            "reasons": reasons,
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
        }

    return None


# ============================================================
# TRADE RULES
# ============================================================
def can_open_trade(state: dict) -> tuple[bool, str]:
    if state["position"] is not None:
        return False, "already in position"

    if state["daily"]["trades"] >= MAX_TRADES_PER_DAY:
        return False, "daily trade limit"

    if state["daily"]["loss_pct"] >= MAX_DAILY_LOSS_PCT:
        return False, "daily loss limit"

    return True, ""


# ============================================================
# OPEN TRADE
# ============================================================
def open_trade(signal: dict, state: dict) -> None:
    symbol = signal["symbol"]
    entry = float(signal["entry"])

    trade_size_usdt = TRADE_SIZE_USDT
    take_profit_pct = float(signal.get("tp_pct", TP_BASE))
    stop_loss_pct = float(signal.get("sl_pct", SL_BASE))

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
            "tp_pct": take_profit_pct,
            "sl_pct": stop_loss_pct,
            "opened_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "order_type": "demo",
            "score": signal["score"],
            "reasons": signal.get("reasons", []),
        }

        state["daily"]["trades"] += 1

        send(
            f"DEMO BUY\n"
            f"Symbol: {symbol}\n"
            f"Mode: {signal['mode']}\n"
            f"Entry: {round(entry, 6)}\n"
            f"Qty: {round(qty, 6)}\n"
            f"TP: {round(tp, 6)} (+{round(take_profit_pct * 100, 2)}%)\n"
            f"SL: {round(sl, 6)} (-{round(stop_loss_pct * 100, 2)}%)\n"
            f"RSI: {signal['rsi']}\n"
            f"Score: {signal['score']}/12\n"
            f"Reasons: {', '.join(signal.get('reasons', []))}\n"
            f"Trade Size: {trade_size_usdt} USDT\n"
            f"Demo Balance: {round(state['balance'], 2)} USDT"
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

        cumulative_quote = float(order.get("cummulativeQuoteQty", 0))
        if executed_qty > 0 and cumulative_quote > 0:
            avg_price = cumulative_quote / executed_qty

        state["position"] = {
            "symbol": symbol,
            "mode": signal["mode"],
            "entry": avg_price,
            "qty": executed_qty,
            "tp": avg_price * (1 + take_profit_pct),
            "sl": avg_price * (1 - stop_loss_pct),
            "tp_pct": take_profit_pct,
            "sl_pct": stop_loss_pct,
            "opened_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "order_type": "live",
            "buy_order_id": order["orderId"],
            "score": signal["score"],
            "reasons": signal.get("reasons", []),
        }

        state["daily"]["trades"] += 1

        send(
            f"LIVE BUY\n"
            f"Symbol: {symbol}\n"
            f"Mode: {signal['mode']}\n"
            f"Entry: {round(avg_price, 6)}\n"
            f"Qty: {round(executed_qty, 6)}\n"
            f"TP: {round(state['position']['tp'], 6)} (+{round(take_profit_pct * 100, 2)}%)\n"
            f"SL: {round(state['position']['sl'], 6)} (-{round(stop_loss_pct * 100, 2)}%)\n"
            f"RSI: {signal['rsi']}\n"
            f"Score: {signal['score']}/12\n"
            f"Reasons: {', '.join(signal.get('reasons', []))}\n"
            f"Trade Size: {trade_size_usdt} USDT"
        )

    except Exception as e:
        send(f"LIVE BUY ERROR\nSymbol: {symbol}\nError: {str(e)}")
        print("LIVE BUY ERROR:", e)


# ============================================================
# CLOSE TRADE
# ============================================================
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
        pnl_now_pct = ((last_price - entry) / entry) * 100.0
        print(
            f"Position open | {symbol} | entry={round(entry, 6)} | "
            f"price={round(last_price, 6)} | pnl={round(pnl_now_pct, 2)}% | "
            f"tp={round(tp, 6)} | sl={round(sl, 6)}"
        )
        return

    pnl_pct = ((last_price - entry) / entry) * 100.0

    if MODE == "demo":
        pnl_usdt = (last_price - entry) * qty
        state["balance"] = round(state["balance"] + pnl_usdt, 2)
        state["daily"]["pnl_usdt"] = round(state["daily"].get("pnl_usdt", 0.0) + pnl_usdt, 4)

        if exit_reason in ["STOP_LOSS", "TREND_BREAK"] and pnl_pct < 0:
            state["daily"]["loss_pct"] += abs(pnl_pct)

        send(
            f"DEMO CLOSE\n"
            f"Symbol: {symbol}\n"
            f"Mode: {pos['mode']}\n"
            f"Reason: {exit_reason}\n"
            f"Entry: {round(entry, 6)}\n"
            f"Exit: {round(last_price, 6)}\n"
            f"PnL: {round(pnl_usdt, 3)} USDT ({round(pnl_pct, 2)}%)\n"
            f"Demo Balance: {round(state['balance'], 2)} USDT\n"
            f"Today PnL: {round(state['daily'].get('pnl_usdt', 0.0), 3)} USDT"
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
            print("Skip sell: quantity too small")
            state["position"] = None
            return

        price = get_last_price(symbol)
        notional = sell_qty * price

        if filters["min_notional"] and notional < filters["min_notional"]:
            print("Skip sell: notional too small")
            state["position"] = None
            return

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
        state["daily"]["pnl_usdt"] = round(state["daily"].get("pnl_usdt", 0.0) + pnl_usdt, 4)

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
            f"PnL: {round(pnl_usdt, 3)} USDT ({round(pnl_pct_real, 2)}%)\n"
            f"Today PnL: {round(state['daily'].get('pnl_usdt', 0.0), 3)} USDT"
        )

        state["position"] = None
        state["sent_signals"] = {}

    except Exception as e:
        send(f"LIVE CLOSE ERROR\nSymbol: {symbol}\nReason: {exit_reason}\nError: {str(e)}")
        print("LIVE CLOSE ERROR:", e)


# ============================================================
# MAIN CYCLE
# ============================================================
def run_cycle() -> None:
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

    symbols = get_live_symbols(limit=12)
    print("Live symbols:", symbols)

    best_signal = None
    best_score = -1

    for symbol in symbols:
        signal = get_active_signal(symbol, btc_filter)
        if signal is None:
            continue

        signal_key = f"{signal['symbol']}_{signal['mode']}_{signal['entry']}"
        if signal_key in state["sent_signals"]:
            print(f"{symbol} | duplicated signal skipped")
            continue

        if signal["score"] > best_score:
            best_signal = signal
            best_score = signal["score"]

        time.sleep(0.15)

    if best_signal is not None:
        open_trade(best_signal, state)
        signal_key = f"{best_signal['symbol']}_{best_signal['mode']}_{best_signal['entry']}"
        state["sent_signals"][signal_key] = True
    else:
        print("No valid signal this cycle")

    save_state(state)


# ============================================================
# START
# ============================================================
if __name__ == "__main__":
    print(f"Bot started in MODE={MODE}")
    send(
        f"Bot started\n"
        f"MODE={MODE}\n"
        f"Strategy: SUPER_ALT_V3\n"
        f"Trade size: {TRADE_SIZE_USDT} USDT\n"
        f"Max trades/day: {MAX_TRADES_PER_DAY}\n"
        f"Daily loss stop: {MAX_DAILY_LOSS_PCT}%\n"
        f"Dynamic live altcoin scanner enabled"
    )

    while True:
        try:
            run_cycle()
            print(f"Cycle finished. Sleeping {SLEEP_SECONDS} sec...\n")
            time.sleep(SLEEP_SECONDS)
        except Exception as e:
            print("ERROR:", e)
            send(f"BOT ERROR\n{str(e)}")
            time.sleep(60)
