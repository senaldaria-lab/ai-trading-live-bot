# REFERENCE ONLY — NOT PRODUCTION — DO NOT RUN LIVE
# This file is for safe review and comparison with the modular bot only.
# It must NOT be imported by main.py.
# It must NOT be connected to the current bot in any way.
# To run live orders, MODE must be manually changed to "live" — it is "paper" by default.

import time
import logging
import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
import ta

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

MODE = "paper"  # ← CHANGE TO "live" ONLY AFTER TESTING

API_KEY    = "YOUR_API_KEY"
API_SECRET = "YOUR_API_SECRET"
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

# Trading parameters
TIMEFRAME          = "1h"
TRADE_SIZE_USDT    = 8.0        # FIX: 8 USDT (~16% of 50 USDT) — safer for small account
MAX_OPEN_POSITIONS = 1
MAX_TRADES_PER_DAY = 3          # FIX: reduced from 4 → 3
DAILY_LOSS_LIMIT   = 0.04       # FIX: 4% of account = $2 hard stop

# TP/SL
TP_BASE = 0.015   # 1.5% take profit
SL_BASE = 0.009   # 0.9% stop loss
# R:R = 1.67

# Scanner filters
MIN_VOLUME_USDT_24H  = 15_000_000
MIN_PRICE_CHANGE_1H  = 0.003
MAX_PRICE_CHANGE_1H  = 0.04
MIN_SCORE_TO_TRADE   = 7        # FIX: raised from 6 → 7

# BTC market filter
BTC_EMA_PERIOD       = 50
BTC_BEARISH_BLOCK    = True

# Blacklist
BLACKLIST = {"USDCUSDT", "BUSDUSDT", "TUSDUSDT", "USDTUSDT", "FDUSDUSDT"}

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────────

def send_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        log.error(f"Telegram error: {e}")

# ─────────────────────────────────────────────
#  BINANCE CLIENT
# ─────────────────────────────────────────────

client = Client(API_KEY, API_SECRET)

def get_balance_usdt() -> float:
    try:
        balance = client.get_asset_balance(asset="USDT")
        return float(balance["free"])
    except BinanceAPIException as e:
        log.error(f"Balance check failed: {e}")
        return 0.0

# ─────────────────────────────────────────────
#  DYNAMIC ALTCOIN SCANNER
# ─────────────────────────────────────────────

def get_tradeable_symbols() -> list:
    try:
        tickers = client.get_ticker()
        exchange_info = client.get_exchange_info()

        active_usdt = set()
        for s in exchange_info["symbols"]:
            if (s["quoteAsset"] == "USDT"
                    and s["status"] == "TRADING"
                    and s["isSpotTradingAllowed"]):
                active_usdt.add(s["symbol"])

        qualified = []
        for t in tickers:
            sym = t["symbol"]
            if sym not in active_usdt:
                continue
            if sym in BLACKLIST:
                continue
            volume_24h = float(t["quoteVolume"])
            if volume_24h < MIN_VOLUME_USDT_24H:
                continue
            qualified.append(sym)

        log.info(f"Scanner found {len(qualified)} liquid USDT pairs")
        return qualified

    except Exception as e:
        log.error(f"Scanner failed: {e}")
        return []

# ─────────────────────────────────────────────
#  OHLCV DATA
# ─────────────────────────────────────────────

def get_ohlcv(symbol: str, interval: str = TIMEFRAME, limit: int = 200) -> pd.DataFrame:
    try:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            "time","open","high","low","close","volume",
            "close_time","quote_vol","trades","tb_base","tb_quote","ignore"
        ])
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        return df
    except Exception as e:
        log.error(f"OHLCV error {symbol}: {e}")
        return pd.DataFrame()

# ─────────────────────────────────────────────
#  BTC MARKET FILTER
# ─────────────────────────────────────────────

def btc_is_bullish() -> bool:
    df = get_ohlcv("BTCUSDT", interval=TIMEFRAME, limit=100)
    if df.empty:
        return False

    df["ema50"] = ta.trend.ema_indicator(df["close"], window=BTC_EMA_PERIOD)
    btc_price = df["close"].iloc[-1]
    btc_ema50 = df["ema50"].iloc[-1]

    is_bullish = btc_price > btc_ema50
    log.info(f"BTC filter: price={btc_price:.2f} | EMA50={btc_ema50:.2f} | bullish={is_bullish}")
    return is_bullish

# ─────────────────────────────────────────────
#  VOLATILITY / MOVEMENT FILTER — FIXED
# ─────────────────────────────────────────────

def passes_movement_filter(symbol: str) -> tuple:
    """
    FIX: Uses last 2 closed 1h candles to calculate real 1h change.
    Old version used priceChangePercent which is 24h — wrong.
    """
    try:
        df = get_ohlcv(symbol, interval=TIMEFRAME, limit=3)
        if df.empty or len(df) < 2:
            return False, 0.0

        # Real 1h change: last closed candle vs previous
        prev_close = df["close"].iloc[-2]
        last_close = df["close"].iloc[-1]
        change_1h = abs(last_close - prev_close) / prev_close

        passes = MIN_PRICE_CHANGE_1H <= change_1h <= MAX_PRICE_CHANGE_1H
        log.debug(f"{symbol} | 1h change={change_1h:.4f} | passes={passes}")
        return passes, change_1h

    except Exception as e:
        log.error(f"Movement filter error {symbol}: {e}")
        return False, 0.0

# ─────────────────────────────────────────────
#  INDICATORS + SCORE SYSTEM — FIXED
# ─────────────────────────────────────────────

def calculate_score(df: pd.DataFrame) -> tuple:
    """
    Score-based entry system (max 10 points).
    Returns (score: int, signal: str, reasons: list)

    FIX: Volume is now a HARD BLOCK — if volume is low, skip regardless of score.

    Scoring:
      +2 → RSI 35–55
      +2 → Price above EMA9 AND EMA20
      +1 → Price above EMA50
      +1 → Price above EMA200
      +2 → MACD line above signal line
      +1 → Volume above 1.2x 20-bar average (also hard block if fails)
      +1 → Breakout above last 5 highs
    """
    if len(df) < 50:
        return 0, "SKIP", ["Not enough data"]

    close  = df["close"]
    high   = df["high"]
    volume = df["volume"]

    rsi    = ta.momentum.rsi(close, window=14)
    ema9   = ta.trend.ema_indicator(close, window=9)
    ema20  = ta.trend.ema_indicator(close, window=20)
    ema50  = ta.trend.ema_indicator(close, window=50)
    ema200 = ta.trend.ema_indicator(close, window=200)
    macd   = ta.trend.MACD(close)

    c      = close.iloc[-1]
    r      = rsi.iloc[-1]
    e9     = ema9.iloc[-1]
    e20    = ema20.iloc[-1]
    e50    = ema50.iloc[-1]
    e200   = ema200.iloc[-1]
    macd_l = macd.macd().iloc[-1]
    macd_s = macd.macd_signal().iloc[-1]
    vol_now = volume.iloc[-1]
    vol_avg = volume.rolling(20).mean().iloc[-1]
    breakout_level = high.iloc[-6:-1].max()

    # ── FIX: HARD BLOCK — Volume gate ──────────────────────────
    vol_ok = vol_now > vol_avg * 1.2
    if not vol_ok:
        return 0, "SKIP", [f"❌ Volume hard block ({vol_now/vol_avg:.2f}x avg < 1.2x required)"]

    score = 0
    reasons = []

    # RSI check
    if 35 <= r <= 55:
        score += 2
        reasons.append(f"✅ RSI={r:.1f} (sweet spot)")
    elif r < 35:
        reasons.append(f"⚠️ RSI={r:.1f} (oversold, caution)")
    else:
        reasons.append(f"❌ RSI={r:.1f} (overbought)")

    # EMA short-term
    if c > e9 and c > e20:
        score += 2
        reasons.append(f"✅ Price above EMA9 & EMA20")
    else:
        reasons.append(f"❌ Price below EMA9/EMA20")

    # EMA50
    if c > e50:
        score += 1
        reasons.append(f"✅ Price above EMA50")
    else:
        reasons.append(f"❌ Price below EMA50")

    # EMA200
    if c > e200:
        score += 1
        reasons.append(f"✅ Price above EMA200")
    else:
        reasons.append(f"❌ Price below EMA200")

    # MACD
    if macd_l > macd_s:
        score += 2
        reasons.append(f"✅ MACD bullish")
    else:
        reasons.append(f"❌ MACD bearish")

    # Volume (passed hard block above, now score it)
    vol_ratio = vol_now / vol_avg
    if vol_ratio >= 1.5:
        score += 1
        reasons.append(f"✅ Volume strong ({vol_ratio:.1f}x avg)")
    elif vol_ratio >= 1.2:
        score += 1
        reasons.append(f"✅ Volume OK ({vol_ratio:.1f}x avg)")

    # Breakout
    if c > breakout_level:
        score += 1
        reasons.append(f"✅ Breakout above last 5 highs")
    else:
        reasons.append(f"❌ No breakout")

    signal = "BUY" if score >= MIN_SCORE_TO_TRADE else "SKIP"
    return score, signal, reasons

# ─────────────────────────────────────────────
#  TRADE EXECUTION (SPOT)
# ─────────────────────────────────────────────

def place_buy_order(symbol: str, usdt_amount: float) -> dict:
    if MODE == "paper":
        price = float(client.get_symbol_ticker(symbol=symbol)["price"])
        qty_approx = usdt_amount / price
        log.info(f"[PAPER] BUY {symbol} | ${usdt_amount:.2f} USDT | qty≈{qty_approx:.6f}")
        return {
            "status": "PAPER",
            "symbol": symbol,
            "amount": usdt_amount,
            "price": price,
            "qty": qty_approx
        }

    try:
        balance = get_balance_usdt()
        if balance < usdt_amount:
            log.warning(f"Insufficient balance: {balance:.2f} USDT < {usdt_amount:.2f}")
            return {}

        price = float(client.get_symbol_ticker(symbol=symbol)["price"])
        qty_raw = usdt_amount / price

        info = client.get_symbol_info(symbol)
        step_size = None
        for f in info["filters"]:
            if f["filterType"] == "LOT_SIZE":
                step_size = float(f["stepSize"])
                break

        if step_size:
            precision = len(str(step_size).rstrip("0").split(".")[-1])
            qty = round(qty_raw - (qty_raw % step_size), precision)
        else:
            qty = round(qty_raw, 6)

        order = client.order_market_buy(symbol=symbol, quantity=qty)
        log.info(f"BUY order placed: {symbol} | qty={qty} | ~${usdt_amount:.2f}")
        return order

    except BinanceAPIException as e:
        log.error(f"BUY order failed {symbol}: {e}")
        send_telegram(f"❌ BUY FAILED: {symbol}\n{e}")
        return {}

def place_sell_order(symbol: str, qty: float) -> dict:
    if MODE == "paper":
        log.info(f"[PAPER] SELL {symbol} | qty={qty:.6f}")
        return {"status": "PAPER", "symbol": symbol, "qty": qty}

    try:
        order = client.order_market_sell(symbol=symbol, quantity=qty)
        log.info(f"SELL order placed: {symbol} | qty={qty}")
        return order
    except BinanceAPIException as e:
        log.error(f"SELL order failed {symbol}: {e}")
        send_telegram(f"❌ SELL FAILED: {symbol}\n{e}")
        return {}

# ─────────────────────────────────────────────
#  POSITION MANAGER
# ─────────────────────────────────────────────

class PositionManager:

    def __init__(self):
        self.position = None

    def has_open(self) -> bool:
        return self.position is not None

    def open(self, symbol: str, entry_price: float, qty: float, score: int):
        tp_mult = TP_BASE + (score - MIN_SCORE_TO_TRADE) * 0.001
        sl_mult = SL_BASE

        tp_price = entry_price * (1 + tp_mult)
        sl_price = entry_price * (1 - sl_mult)

        self.position = {
            "symbol":      symbol,
            "entry_price": entry_price,
            "qty":         qty,
            "tp_price":    tp_price,
            "sl_price":    sl_price,
            "score":       score,
        }
        log.info(f"Position opened: {symbol} @ {entry_price:.6f} | TP={tp_price:.6f} | SL={sl_price:.6f}")

    def close(self):
        self.position = None

    def check_exit(self, current_price: float) -> str:
        if not self.position:
            return "HOLD"
        if current_price >= self.position["tp_price"]:
            return "TP"
        if current_price <= self.position["sl_price"]:
            return "SL"
        return "HOLD"

# ─────────────────────────────────────────────
#  DAILY STATS TRACKER
# ─────────────────────────────────────────────

class DailyStats:

    def __init__(self, account_size: float):
        self.account_size  = account_size
        self.trades_today  = 0
        self.pnl_today     = 0.0
        self.reset_hour    = 0

    def reset_if_new_day(self):
        from datetime import datetime, timezone
        now_hour = datetime.now(timezone.utc).hour
        if now_hour == self.reset_hour and self.trades_today > 0:
            log.info(f"Daily reset | trades={self.trades_today} | PnL={self.pnl_today:.2f}")
            send_telegram(
                f"📊 <b>Daily Summary</b>\n"
                f"Trades: {self.trades_today}\n"
                f"PnL: {'+'if self.pnl_today>0 else ''}{self.pnl_today:.2f} USDT"
            )
            self.trades_today = 0
            self.pnl_today    = 0.0

    def record_trade(self, pnl: float):
        self.trades_today += 1
        self.pnl_today    += pnl

    def can_trade(self) -> tuple:
        if self.trades_today >= MAX_TRADES_PER_DAY:
            return False, f"Max trades/day reached ({MAX_TRADES_PER_DAY})"
        loss_limit = self.account_size * DAILY_LOSS_LIMIT
        if self.pnl_today <= -loss_limit:
            return False, f"Daily loss limit hit (${loss_limit:.2f})"
        return True, "OK"

# ─────────────────────────────────────────────
#  MAIN BOT LOOP
# ─────────────────────────────────────────────

def run_bot():
    log.info("=" * 60)
    log.info("  Bot starting — Mode: " + MODE)
    log.info("=" * 60)
    send_telegram(
        f"🤖 <b>Bot started</b>\n"
        f"Mode: <b>{MODE}</b>\n"
        f"Trade size: ${TRADE_SIZE_USDT}\n"
        f"Min score: {MIN_SCORE_TO_TRADE}/10\n"
        f"Max trades/day: {MAX_TRADES_PER_DAY}\n"
        f"Daily loss limit: {DAILY_LOSS_LIMIT*100:.1f}%"
    )

    pos_manager = PositionManager()
    account_size = get_balance_usdt()
    if account_size < 10:
        log.error("Balance too low. Exiting.")
        send_telegram("❌ Balance too low to start bot.")
        return

    daily = DailyStats(account_size)
    log.info(f"Starting balance: {account_size:.2f} USDT")

    while True:
        try:
            daily.reset_if_new_day()

            # ── Check open position exit ──────────────────────────
            if pos_manager.has_open():
                pos = pos_manager.position
                sym = pos["symbol"]
                current_price = float(client.get_symbol_ticker(symbol=sym)["price"])
                exit_signal = pos_manager.check_exit(current_price)

                if exit_signal in ("TP", "SL"):
                    pnl = (current_price - pos["entry_price"]) * pos["qty"]
                    emoji = "✅" if exit_signal == "TP" else "🛑"
                    label = "Take Profit" if exit_signal == "TP" else "Stop Loss"

                    place_sell_order(sym, pos["qty"])
                    daily.record_trade(pnl)
                    pos_manager.close()

                    send_telegram(
                        f"{emoji} <b>{label} hit!</b>\n"
                        f"Pair: {sym}\n"
                        f"Entry: {pos['entry_price']:.6f}\n"
                        f"Exit:  {current_price:.6f}\n"
                        f"PnL:   {'+'if pnl>0 else ''}{pnl:.3f} USDT\n"
                        f"Today: {daily.trades_today} trades | {daily.pnl_today:+.3f} USDT"
                    )
                else:
                    pnl_now = (current_price - pos["entry_price"]) * pos["qty"]
                    log.info(
                        f"Holding {sym} | price={current_price:.6f} | "
                        f"PnL={pnl_now:+.4f} USDT | "
                        f"TP={pos['tp_price']:.6f} | SL={pos['sl_price']:.6f}"
                    )

            # ── Look for new trade ────────────────────────────────
            elif not pos_manager.has_open():
                ok, reason = daily.can_trade()
                if not ok:
                    log.info(f"Trading paused: {reason}")
                    time.sleep(300)
                    continue

                if BTC_BEARISH_BLOCK and not btc_is_bullish():
                    log.info("BTC filter: bearish — skipping scan")
                    send_telegram("⚠️ BTC below EMA50 — no new trades this hour")
                    time.sleep(3600)
                    continue

                symbols = get_tradeable_symbols()
                best_score = 0
                best_symbol = None
                best_reasons = []

                for sym in symbols:
                    passes, change = passes_movement_filter(sym)
                    if not passes:
                        continue

                    df = get_ohlcv(sym)
                    if df.empty:
                        continue

                    score, signal, reasons = calculate_score(df)

                    if signal == "BUY" and score > best_score:
                        best_score = score
                        best_symbol = sym
                        best_reasons = reasons

                    time.sleep(0.1)

                # ── FIX: Use real execution price and qty ─────────
                if best_symbol and best_score >= MIN_SCORE_TO_TRADE:
                    order = place_buy_order(best_symbol, TRADE_SIZE_USDT)

                    if order:
                        # FIX: get real qty and price from order (not approximation)
                        if MODE == "live":
                            real_qty   = float(order["executedQty"])
                            real_price = float(order["cummulativeQuoteQty"]) / real_qty
                        else:
                            # Paper mode: use values from order dict
                            real_qty   = order.get("qty", TRADE_SIZE_USDT / order.get("price", 1))
                            real_price = order.get("price", 0.0)

                        pos_manager.open(best_symbol, real_price, real_qty, best_score)

                        reasons_text = "\n".join(best_reasons)
                        send_telegram(
                            f"🚀 <b>NEW TRADE</b>\n"
                            f"Pair:  <b>{best_symbol}</b>\n"
                            f"Score: {best_score}/10\n"
                            f"Entry: {real_price:.6f}\n"
                            f"TP:    {pos_manager.position['tp_price']:.6f} (+{TP_BASE*100:.1f}%)\n"
                            f"SL:    {pos_manager.position['sl_price']:.6f} (-{SL_BASE*100:.1f}%)\n"
                            f"Size:  ${TRADE_SIZE_USDT}\n\n"
                            f"<b>Signals:</b>\n{reasons_text}"
                        )
                else:
                    log.info(f"No signal this cycle. Best score: {best_score}")

            time.sleep(60)

        except KeyboardInterrupt:
            log.info("Bot stopped by user.")
            send_telegram("🔴 Bot stopped manually.")
            break
        except Exception as e:
            log.error(f"Loop error: {e}")
            send_telegram(f"⚠️ Bot error: {e}")
            time.sleep(60)

# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    run_bot()
