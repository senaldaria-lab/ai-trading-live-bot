"""
agent_market_dry_run.py
Real Binance public API dry-run — NO trades, NO Telegram, NO API keys required.
Fetches live klines and runs the full agent pipeline in simulation mode.
"""

import urllib.request
import json
import time
from datetime import datetime, timezone

# ──────────────────────────────────────────────
# SAFETY CONSTANTS — DO NOT CHANGE
# ──────────────────────────────────────────────
SPOT_ONLY             = True
SIGNALS_ONLY          = True
AUTO_TRADING_ENABLED  = False
FUTURES_ALLOWED       = False
LEVERAGE_ALLOWED      = False
TELEGRAM_SEND_ENABLED = False

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "SUIUSDT"]
BINANCE_BASE = "https://api.binance.com/api/v3/klines"


# ──────────────────────────────────────────────
# DATA FETCHING
# ──────────────────────────────────────────────

def fetch_klines(symbol: str, interval: str, limit: int = 300) -> list:
    url = f"{BINANCE_BASE}?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return data
    except Exception as e:
        print(f"  [ERROR] fetch_klines({symbol},{interval}): {e}")
        return []


def parse_klines(raw: list) -> dict:
    """Return dict of lists: opens, highs, lows, closes, volumes."""
    if not raw:
        return {}
    opens   = [float(c[1]) for c in raw]
    highs   = [float(c[2]) for c in raw]
    lows    = [float(c[3]) for c in raw]
    closes  = [float(c[4]) for c in raw]
    volumes = [float(c[5]) for c in raw]
    return {"opens": opens, "highs": highs, "lows": lows,
            "closes": closes, "volumes": volumes}


# ──────────────────────────────────────────────
# TECHNICAL INDICATORS
# ──────────────────────────────────────────────

def calc_ema(closes: list, period: int) -> list:
    """SMA-seeded EMA. Returns list same length as closes (None for first period-1)."""
    if len(closes) < period:
        return [None] * len(closes)
    ema = [None] * (period - 1)
    seed = sum(closes[:period]) / period
    ema.append(seed)
    k = 2 / (period + 1)
    for price in closes[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema


def calc_rsi(closes: list, period: int = 14) -> float | None:
    """Wilder-smoothed RSI. Returns single float or None."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calc_macd(closes: list, fast: int = 12, slow: int = 26,
              signal_period: int = 9) -> dict | None:
    """Returns dict with macd, signal, histogram, prev_histogram."""
    if len(closes) < slow + signal_period:
        return None
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    macd_line = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)
    valid_macd = [v for v in macd_line if v is not None]
    if len(valid_macd) < signal_period:
        return None
    # EMA of macd_line for signal
    sig_seed = sum(valid_macd[:signal_period]) / signal_period
    signal_line = [sig_seed]
    k = 2 / (signal_period + 1)
    for val in valid_macd[signal_period:]:
        signal_line.append(val * k + signal_line[-1] * (1 - k))
    macd_val   = valid_macd[-1]
    signal_val = signal_line[-1]
    histogram  = macd_val - signal_val
    prev_hist  = (valid_macd[-2] - signal_line[-2]) if len(signal_line) >= 2 else 0
    return {
        "macd": round(macd_val, 6),
        "signal": round(signal_val, 6),
        "histogram": round(histogram, 6),
        "prev_histogram": round(prev_hist, 6),
    }


def calc_atr(highs: list, lows: list, closes: list, period: int = 14) -> float | None:
    """Wilder ATR."""
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return round(atr, 6)


def find_support_resistance(highs: list, lows: list, price: float,
                             lookback: int = 50) -> tuple:
    """Return (support, resistance) using nearest swing low/high in last lookback bars."""
    recent_highs = highs[-lookback:]
    recent_lows  = lows[-lookback:]
    lows_below  = [l for l in recent_lows  if l < price]
    highs_above = [h for h in recent_highs if h > price]
    support    = max(lows_below)  if lows_below  else price * 0.97
    resistance = min(highs_above) if highs_above else price * 1.05
    return round(support, 6), round(resistance, 6)


# ──────────────────────────────────────────────
# TREND CLASSIFIERS
# ──────────────────────────────────────────────

def classify_4h_trend(closes: list, ema50: list) -> str:
    """UPTREND / DOWNTREND / SIDEWAYS based on EMA50 and HH/HL."""
    if len(closes) < 10 or ema50[-1] is None:
        return "SIDEWAYS"
    price = closes[-1]
    e50   = ema50[-1]
    # Check last 6 swing points for higher-high/higher-low or inverse
    recent = closes[-20:]
    highs_seq = recent[1::2]
    lows_seq  = recent[::2]
    hh = all(highs_seq[i] > highs_seq[i-1] for i in range(1, len(highs_seq))) if len(highs_seq) >= 2 else False
    hl = all(lows_seq[i]  > lows_seq[i-1]  for i in range(1, len(lows_seq)))  if len(lows_seq)  >= 2 else False
    lh = all(highs_seq[i] < highs_seq[i-1] for i in range(1, len(highs_seq))) if len(highs_seq) >= 2 else False
    ll = all(lows_seq[i]  < lows_seq[i-1]  for i in range(1, len(lows_seq)))  if len(lows_seq)  >= 2 else False
    if price > e50 and (hh or hl):
        return "UPTREND"
    if price < e50 and (lh or ll):
        return "DOWNTREND"
    return "SIDEWAYS"


def classify_1h_trend(closes: list, ema20: list, ema50: list) -> str:
    """BULLISH / BEARISH / NEUTRAL."""
    if ema20[-1] is None or ema50[-1] is None:
        return "NEUTRAL"
    price = closes[-1]
    if price > ema20[-1] and ema20[-1] > ema50[-1]:
        return "BULLISH"
    if price < ema20[-1] and ema20[-1] < ema50[-1]:
        return "BEARISH"
    return "NEUTRAL"


def classify_15m_trend(closes: list, ema20: list) -> str:
    """BULLISH / BEARISH / NEUTRAL."""
    if ema20[-1] is None or len(closes) < 3:
        return "NEUTRAL"
    price = closes[-1]
    slope = ema20[-1] - ema20[-3] if ema20[-3] is not None else 0
    if price > ema20[-1] and slope > 0:
        return "BULLISH"
    if price < ema20[-1] and slope < 0:
        return "BEARISH"
    return "NEUTRAL"


def classify_ema_status(ema20_val, ema50_val, ema200_val) -> str:
    if None in (ema20_val, ema50_val, ema200_val):
        return "Insufficient data"
    if ema20_val > ema50_val > ema200_val:
        return "Bullish (EMA20 > EMA50 > EMA200)"
    if ema20_val < ema50_val < ema200_val:
        return "Bearish (EMA20 < EMA50 < EMA200)"
    return "Mixed alignment"


def classify_volume(volume: float, avg_volume: float) -> str:
    ratio = volume / avg_volume if avg_volume > 0 else 0
    if ratio >= 1.5:
        return "HIGH"
    if ratio >= 0.8:
        return "NORMAL"
    return "LOW"


def classify_macd_status(macd_data: dict | None) -> str:
    if macd_data is None:
        return "Insufficient data"
    hist = macd_data["histogram"]
    prev = macd_data["prev_histogram"]
    macd = macd_data["macd"]
    sig  = macd_data["signal"]
    if macd > sig and hist > prev:
        return "Bullish crossover, histogram growing"
    if macd > sig and hist <= prev:
        return "Bullish, histogram shrinking"
    if macd <= sig and hist < prev:
        return "Bearish crossover, histogram falling"
    return "Neutral / inconclusive"


# ──────────────────────────────────────────────
# SCORING
# ──────────────────────────────────────────────

def score_4h(trend: str) -> int:
    return {"UPTREND": 20, "SIDEWAYS": 10, "DOWNTREND": 0}.get(trend, 0)


def score_1h(trend: str) -> int:
    return {"BULLISH": 10, "NEUTRAL": 5, "BEARISH": 0}.get(trend, 0)


def score_15m(gate: str) -> int:
    return 10 if gate == "PASS" else 0


def score_ema(status: str) -> int:
    if "EMA20 > EMA50 > EMA200" in status:
        return 20
    if "Mixed" in status:
        return 10
    return 0


def score_rsi(rsi: float | None) -> int:
    if rsi is None:
        return 0
    if 60 <= rsi <= 70:
        return 10
    if 40 <= rsi < 60:
        return 5
    if 30 <= rsi < 40:
        return 7
    if 20 <= rsi < 30:
        return 6
    if rsi > 70:
        return 2
    return 3  # < 20


def score_macd(status: str) -> int:
    if "growing" in status:
        return 10
    if "Bullish" in status:
        return 6
    if "Neutral" in status:
        return 3
    return 0


def score_volume(vol_status: str) -> int:
    return {"HIGH": 10, "NORMAL": 7, "LOW": 2}.get(vol_status, 0)


def score_rr(rr: float) -> int:
    if rr >= 3:
        return 10
    if rr >= 2:
        return 8
    if rr >= 1.5:
        return 6
    if rr >= 1:
        return 4
    return 0


def compute_sel(trend_4h: str, trend_1h: str, trend_15m: str,
                rsi_1h: float | None, macd_status: str, vol_status: str,
                rr: float, gate: str) -> str:
    score = 0
    if trend_4h != "DOWNTREND" and trend_1h == "BULLISH":
        score += 1
    if gate == "PASS":
        score += 1
    if rsi_1h is not None and 40 <= rsi_1h <= 70:
        score += 1
    if "Bullish" in macd_status:
        score += 1
    if vol_status in ("HIGH", "NORMAL"):
        score += 1
    if rr >= 1.5:
        score += 1
    if score >= 5:
        return "STRONG"
    if score >= 3:
        return "MODERATE"
    if score >= 1:
        return "WEAK"
    return "INVALID"


def compute_local_risk(rsi_1h: float | None, rsi_4h: float | None,
                       vol_status: str, atr_pct: float, missing_data: bool) -> str:
    if missing_data:
        return "BLOCKED"
    flags = 0
    if rsi_1h is not None and rsi_1h > 70:
        flags += 1
    if rsi_4h is not None and rsi_4h > 70:
        flags += 1
    if vol_status == "LOW":
        flags += 1
    if atr_pct > 3:
        flags += 2
    if atr_pct > 5:
        return "BLOCKED"
    if flags >= 3:
        return "HIGH"
    if flags >= 1:
        return "MEDIUM"
    return "LOW"


def compute_preliminary_decision(score: int, local_risk: str,
                                  gate: str, vol_status: str) -> str:
    if local_risk == "BLOCKED":
        return "AVOID"
    if gate == "FAIL":
        return "WATCH"
    if vol_status == "LOW":
        if score >= 75:
            return "WATCH"   # downgrade from PRELIMINARY_BUY
        if score >= 60:
            return "WATCH"
        return "AVOID"
    if score >= 75 and local_risk == "LOW":
        return "PRELIMINARY_BUY"
    if score >= 60 and local_risk in ("LOW", "MEDIUM"):
        return "WATCH"
    if score >= 50:
        return "WATCH"
    return "AVOID"


# ──────────────────────────────────────────────
# COIN AGENT
# ──────────────────────────────────────────────

def analyze_coin(symbol: str) -> dict:
    print(f"  Fetching {symbol} klines (4h/1h/15m)...", end=" ", flush=True)

    raw_4h  = fetch_klines(symbol, "4h",  limit=200)
    raw_1h  = fetch_klines(symbol, "1h",  limit=200)
    raw_15m = fetch_klines(symbol, "15m", limit=200)

    if not raw_4h or not raw_1h or not raw_15m:
        print("FAILED")
        return {"symbol": symbol, "error": "Missing data", "preliminary_decision": "AVOID",
                "local_risk": "BLOCKED", "preliminary_score": 0, "sel": "INVALID",
                "allowed_for_main_brain": False}

    d4h  = parse_klines(raw_4h)
    d1h  = parse_klines(raw_1h)
    d15m = parse_klines(raw_15m)
    print("OK")

    # EMAs on 1h (primary scoring frame)
    ema20_1h  = calc_ema(d1h["closes"], 20)
    ema50_1h  = calc_ema(d1h["closes"], 50)
    ema200_1h = calc_ema(d1h["closes"], 200)

    # EMAs on 4h for trend
    ema50_4h  = calc_ema(d4h["closes"], 50)
    ema20_4h  = calc_ema(d4h["closes"], 20)

    # EMA on 15m for gate
    ema20_15m = calc_ema(d15m["closes"], 20)

    trend_4h  = classify_4h_trend(d4h["closes"], ema50_4h)
    trend_1h  = classify_1h_trend(d1h["closes"], ema20_1h, ema50_1h)
    trend_15m = classify_15m_trend(d15m["closes"], ema20_15m)

    # 3-timeframe gate
    gate_pass = (trend_4h != "DOWNTREND"
                 and trend_1h in ("BULLISH", "NEUTRAL")
                 and trend_15m != "BEARISH")
    timeframe_gate = "PASS" if gate_pass else "FAIL"

    # RSI
    rsi_1h = calc_rsi(d1h["closes"])
    rsi_4h = calc_rsi(d4h["closes"])

    # MACD on 1h
    macd_data   = calc_macd(d1h["closes"])
    macd_status = classify_macd_status(macd_data)

    # Volume (last bar vs 20-period avg)
    vol_current = d1h["volumes"][-1]
    vol_avg     = sum(d1h["volumes"][-21:-1]) / 20 if len(d1h["volumes"]) >= 21 else vol_current
    vol_status  = classify_volume(vol_current, vol_avg)

    # Support / Resistance on 1h last 50
    price = d1h["closes"][-1]
    support, resistance = find_support_resistance(
        d1h["highs"][-50:], d1h["lows"][-50:], price)
    dist_support    = round((price - support)    / price * 100, 2)
    dist_resistance = round((resistance - price) / price * 100, 2)
    rr = round(dist_resistance / dist_support, 2) if dist_support > 0 else 0

    # ATR / Volatility
    atr     = calc_atr(d1h["highs"], d1h["lows"], d1h["closes"])
    atr_pct = round((atr / price) * 100, 2) if atr else 0
    if atr_pct < 1:
        vol_label = "LOW"
    elif atr_pct <= 3:
        vol_label = "NORMAL"
    else:
        vol_label = "HIGH"

    # EMA status
    ema_status = classify_ema_status(ema20_1h[-1], ema50_1h[-1], ema200_1h[-1])

    # Scoring
    pts_4h   = score_4h(trend_4h)
    pts_1h   = score_1h(trend_1h)
    pts_15m  = score_15m(timeframe_gate)
    pts_ema  = score_ema(ema_status)
    pts_rsi  = score_rsi(rsi_1h)
    pts_macd = score_macd(macd_status)
    pts_vol  = score_volume(vol_status)
    pts_rr   = score_rr(rr)
    preliminary_score = (pts_4h + pts_1h + pts_15m + pts_ema +
                         pts_rsi + pts_macd + pts_vol + pts_rr)

    # Risk / decision
    missing_data = ema200_1h[-1] is None or rsi_1h is None
    local_risk   = compute_local_risk(rsi_1h, rsi_4h, vol_status, atr_pct, missing_data)
    sel          = compute_sel(trend_4h, trend_1h, trend_15m, rsi_1h,
                               macd_status, vol_status, rr, timeframe_gate)
    preliminary_decision = compute_preliminary_decision(
        preliminary_score, local_risk, timeframe_gate, vol_status)

    return {
        "symbol":               symbol,
        "timeframe_4h_trend":   trend_4h,
        "timeframe_1h_trend":   trend_1h,
        "timeframe_15m_trend":  trend_15m,
        "timeframe_gate":       timeframe_gate,
        "ema_status":           ema_status,
        "rsi":                  rsi_1h,
        "rsi_4h":               rsi_4h,
        "macd_status":          macd_status,
        "volume_status":        vol_status,
        "support_level":        f"{support} ({dist_support}% below)",
        "resistance_level":     f"{resistance} ({dist_resistance}% above)",
        "rr_ratio":             rr,
        "volatility":           f"{atr_pct}% ATR ({vol_label})",
        "sel":                  sel,
        "preliminary_score":    preliminary_score,
        "local_risk":           local_risk,
        "preliminary_decision": preliminary_decision,
        "reason":               _build_reason(trend_4h, trend_1h, rsi_1h,
                                              macd_status, vol_status, timeframe_gate),
        "current_price":        round(price, 6),
        "score_breakdown": {
            "4h_trend": pts_4h, "1h_trend": pts_1h, "15m_gate": pts_15m,
            "ema": pts_ema, "rsi": pts_rsi, "macd": pts_macd,
            "volume": pts_vol, "rr": pts_rr,
        },
    }


def _build_reason(t4h, t1h, rsi, macd, vol, gate) -> str:
    parts = [f"4H:{t4h}", f"1H:{t1h}", f"Gate:{gate}", f"Vol:{vol}"]
    if rsi:
        parts.append(f"RSI:{rsi:.1f}")
    if "Bullish" in macd:
        parts.append("MACD:bullish")
    elif "Bearish" in macd:
        parts.append("MACD:bearish")
    return " | ".join(parts)


# ──────────────────────────────────────────────
# RISK MANAGER
# ──────────────────────────────────────────────

BLACKLIST: set = set()

def run_risk_manager(report: dict) -> dict:
    symbol   = report["symbol"]
    decision = report.get("preliminary_decision", "AVOID")
    score    = report.get("preliminary_score", 0)
    risk     = report.get("local_risk", "HIGH")
    sel      = report.get("sel", "INVALID")
    vol      = report.get("volume_status", "LOW")
    rsi_1h   = report.get("rsi")
    rsi_4h   = report.get("rsi_4h")
    gate     = report.get("timeframe_gate", "FAIL")

    block_reason     = None
    downgrade_reason = None

    # ── Blocking rules ──
    if symbol in BLACKLIST:
        block_reason = "Symbol on blacklist"
    elif report.get("error"):
        block_reason = "Missing candle data"
    elif risk == "BLOCKED":
        block_reason = "Local risk BLOCKED (ATR>5% or missing data)"
    elif decision == "AVOID":
        block_reason = "Coin agent preliminary decision: AVOID"
    elif sel == "INVALID":
        block_reason = "SEL = INVALID"
    elif rsi_1h and rsi_1h > 78:
        block_reason = f"RSI overbought chase: {rsi_1h:.1f} > 78"
    elif rsi_4h and rsi_4h > 78:
        block_reason = f"RSI 4H overbought: {rsi_4h:.1f} > 78"

    if block_reason:
        return {
            "symbol": symbol, "input_decision": decision, "input_score": score,
            "input_risk": risk, "risk_check_result": "FAIL", "risk_action": "BLOCK",
            "block_reason": block_reason, "downgrade_reason": None,
            "final_risk_label": risk, "allowed_for_main_brain": False,
        }

    # ── Downgrade rules ──
    current_decision = decision

    if sel == "WEAK":
        if "BUY" in current_decision:
            current_decision = "WATCH"
            downgrade_reason = (downgrade_reason or "") + "SEL=WEAK; "

    if rsi_1h and 65 <= rsi_1h <= 78:
        if current_decision == "PRELIMINARY_BUY":
            current_decision = "WATCH"
            downgrade_reason = (downgrade_reason or "") + f"RSI {rsi_1h:.1f} in 65-78 range; "

    if vol == "LOW":
        if current_decision == "PRELIMINARY_BUY":
            current_decision = "WATCH"
            downgrade_reason = (downgrade_reason or "") + "Volume LOW; "

    if gate == "FAIL":
        if current_decision == "PRELIMINARY_BUY":
            current_decision = "WATCH"
            downgrade_reason = (downgrade_reason or "") + "Timeframe gate FAIL; "

    if risk == "HIGH":
        if "BUY" in current_decision:
            current_decision = "WATCH"
            downgrade_reason = (downgrade_reason or "") + "Local risk HIGH; "

    risk_action = "DOWNGRADE" if downgrade_reason else "ALLOW"
    return {
        "symbol": symbol, "input_decision": decision, "input_score": score,
        "input_risk": risk, "risk_check_result": "PASS", "risk_action": risk_action,
        "block_reason": None,
        "downgrade_reason": downgrade_reason.strip("; ") if downgrade_reason else None,
        "final_risk_label": risk,
        "allowed_for_main_brain": True,
        "final_decision_after_rm": current_decision,
    }


# ──────────────────────────────────────────────
# NEWS & DEEP RESEARCH (MOCK — external data needed)
# ──────────────────────────────────────────────

def get_news_sentiment_mock() -> dict:
    return {
        "news_status": "NEUTRAL",
        "btc_news_status": "NEUTRAL",
        "eth_news_status": "NEUTRAL",
        "binance_news_status": "NEUTRAL",
        "macro_status": "NEUTRAL",
        "regulation_status": "CLEAR",
        "sentiment_score": 0.50,
        "risk_notes": "Live news feed not connected - using NEUTRAL baseline",
        "recommendation_for_main_brain": "No strong news catalyst detected; rely on technical signals",
    }


def get_deep_research_mock() -> dict:
    return {
        "market_summary": "Deep Research not connected - using permissive defaults",
        "coins_to_blacklist": [],
        "coins_to_pause": [],
        "risk_notes": "Deep Research layer is mocked for this dry-run",
        "recommendation_for_main_brain": "No macro red flags from Deep Research",
    }


# ──────────────────────────────────────────────
# MAIN BRAIN
# ──────────────────────────────────────────────

def run_main_brain(rm_results: list, coin_reports: dict,
                   news: dict, deep_research: dict) -> list:
    blacklisted  = set(deep_research.get("coins_to_blacklist", []))
    paused       = set(deep_research.get("coins_to_pause", []))
    news_status  = news.get("news_status", "NEUTRAL")

    # Find BTC context
    btc_report = coin_reports.get("BTCUSDT", {})
    btc_trend  = btc_report.get("timeframe_4h_trend", "SIDEWAYS")
    btc_risk_on = btc_trend in ("UPTREND", "SIDEWAYS")

    candidates = []
    for rm in rm_results:
        sym = rm["symbol"]
        if not rm["allowed_for_main_brain"]:
            candidates.append({
                "symbol": sym, "final_decision": "AVOID",
                "final_score": rm["input_score"],
                "confidence_level": "LOW",
                "block_reason": rm.get("block_reason"),
                "reason": f"Blocked by Risk Manager: {rm.get('block_reason')}",
            })
            continue

        if sym in blacklisted:
            candidates.append({
                "symbol": sym, "final_decision": "AVOID",
                "final_score": 0, "confidence_level": "LOW",
                "reason": "Deep Research blacklist",
            })
            continue

        if news_status == "DANGER":
            candidates.append({
                "symbol": sym, "final_decision": "AVOID",
                "final_score": rm["input_score"], "confidence_level": "LOW",
                "reason": "News DANGER - all BUY signals suppressed",
            })
            continue

        score    = rm["input_score"]
        risk     = rm["final_risk_label"]
        decision = rm.get("final_decision_after_rm", rm["input_decision"])

        # News modulation
        if news_status == "NEGATIVE" and "BUY" in decision:
            decision = "WATCH"
        if news_status == "POSITIVE" and score >= 70:
            score = min(score + 3, 100)

        # BTC context gates for altcoins
        if sym not in ("BTCUSDT",) and not btc_risk_on:
            if score > 45:
                score = 45
            decision = "WATCH" if decision != "AVOID" else "AVOID"

        # SUI extra gate
        if sym == "SUIUSDT":
            eth_trend = coin_reports.get("ETHUSDT", {}).get("timeframe_4h_trend", "SIDEWAYS")
            if not btc_risk_on or eth_trend == "DOWNTREND":
                if score > 45:
                    score = 45
                decision = "WATCH"

        # Paused coins capped at WATCH
        if sym in paused and "BUY" in decision:
            decision = "WATCH"

        # Final label mapping
        if decision == "PRELIMINARY_BUY":
            final = "STRONG_BUY" if score >= 80 else "BUY"
        elif decision == "WATCH":
            final = "WATCH"
        else:
            final = "AVOID"

        # Confidence level
        if score >= 80 and risk in ("LOW", "MEDIUM"):
            confidence = "HIGH"
        elif score >= 65 and risk != "HIGH":
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        report = coin_reports.get(sym, {})
        candidates.append({
            "symbol":           sym,
            "final_decision":   final,
            "final_score":      score,
            "confidence_level": confidence,
            "timeframe_gate":   report.get("timeframe_gate", "N/A"),
            "sel":              report.get("sel", "N/A"),
            "volume_status":    report.get("volume_status", "N/A"),
            "rsi":              report.get("rsi"),
            "rsi_4h":           report.get("rsi_4h"),
            "macd_status":      report.get("macd_status", "N/A"),
            "ema_status":       report.get("ema_status", "N/A"),
            "volatility":       report.get("volatility", "N/A"),
            "support_level":    report.get("support_level", "N/A"),
            "resistance_level": report.get("resistance_level", "N/A"),
            "current_price":    report.get("current_price"),
            "reason":           report.get("reason", "N/A"),
            "local_risk":       risk,
            "score_breakdown":  report.get("score_breakdown", {}),
        })

    return candidates


# ──────────────────────────────────────────────
# TELEGRAM SIGNAL AGENT (console preview only)
# ──────────────────────────────────────────────

def format_telegram_message(signal: dict) -> str | None:
    decision = signal["final_decision"]
    if decision == "AVOID":
        return None  # Never send AVOID

    sym   = signal["symbol"]
    score = signal["final_score"]
    conf  = signal["confidence_level"]
    price = signal.get("current_price", "N/A")

    if decision in ("STRONG_BUY", "BUY"):
        emoji_map = {"STRONG_BUY": "[STRONG BUY]", "BUY": "[BUY SIGNAL]"}
        header = emoji_map[decision]
        lines = [
            f"{header} {sym}",
            f"Price     : {price}",
            f"Score     : {score}/100",
            f"Confidence: {conf}",
            f"Gate      : {signal.get('timeframe_gate','N/A')} | SEL: {signal.get('sel','N/A')}",
            f"RSI 1H    : {signal.get('rsi','N/A')} | RSI 4H: {signal.get('rsi_4h','N/A')}",
            f"Volume    : {signal.get('volume_status','N/A')}",
            f"MACD      : {signal.get('macd_status','N/A')}",
            f"Support   : {signal.get('support_level','N/A')}",
            f"Resistance: {signal.get('resistance_level','N/A')}",
            f"Reason    : {signal.get('reason','N/A')}",
            "",
            "[SPOT ONLY | SIGNALS ONLY | NO AUTO EXECUTION]",
        ]
        return "\n".join(lines)

    if decision == "WATCH":
        return (f"[WATCH] {sym} | Score:{score} | Conf:{conf} | "
                f"Gate:{signal.get('timeframe_gate','N/A')} | "
                f"Reason: {signal.get('reason','N/A')}")

    if decision == "SELL":
        return (f"[SELL SIGNAL] {sym} @ {price} | "
                f"Risk:{signal.get('local_risk','N/A')} | SPOT ONLY")

    return None


# ──────────────────────────────────────────────
# PRINT HELPERS
# ──────────────────────────────────────────────

def print_separator(char: str = "-", width: int = 65):
    print(char * width)


def print_coin_report(r: dict):
    sym = r["symbol"]
    print_separator()
    print(f"  {sym}")
    print_separator(".")
    if r.get("error"):
        print(f"  ERROR: {r['error']}")
        return
    fields = [
        ("4H Trend",        r.get("timeframe_4h_trend")),
        ("1H Trend",        r.get("timeframe_1h_trend")),
        ("15m Trend",       r.get("timeframe_15m_trend")),
        ("Timeframe Gate",  r.get("timeframe_gate")),
        ("EMA Status",      r.get("ema_status")),
        ("RSI 1H",          r.get("rsi")),
        ("RSI 4H",          r.get("rsi_4h")),
        ("MACD",            r.get("macd_status")),
        ("Volume",          r.get("volume_status")),
        ("Support",         r.get("support_level")),
        ("Resistance",      r.get("resistance_level")),
        ("Volatility",      r.get("volatility")),
        ("SEL",             r.get("sel")),
        ("Score",           f"{r.get('preliminary_score',0)}/100"),
        ("Local Risk",      r.get("local_risk")),
        ("Decision",        r.get("preliminary_decision")),
    ]
    for label, val in fields:
        print(f"  {label:<20}: {val}")
    bd = r.get("score_breakdown", {})
    if bd:
        breakdown = " + ".join(f"{k}={v}" for k, v in bd.items())
        print(f"  {'Score Breakdown':<20}: {breakdown}")


def print_final_signals(signals: list):
    print_separator("=")
    print("  FINAL SIGNAL SUMMARY")
    print_separator("=")
    for s in signals:
        sym    = s["symbol"]
        dec    = s["final_decision"]
        score  = s["final_score"]
        conf   = s["confidence_level"]
        reason = s.get("reason", "N/A")
        br     = s.get("block_reason")
        if br:
            print(f"  {sym:<10} BLOCKED  ({br})")
        else:
            print(f"  {sym:<10} {dec:<12} score={score:<4} conf={conf:<6} | {reason[:55]}")
    print_separator("=")


def print_telegram_preview(signals: list):
    has_sendable = any(s["final_decision"] not in ("AVOID",) for s in signals)
    if not has_sendable:
        print("  No signals to send (all AVOID or BLOCKED).")
        return
    for s in signals:
        msg = format_telegram_message(s)
        if msg:
            print_separator(".")
            print(msg)


# ──────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────

def main():
    assert SPOT_ONLY,             "SAFETY: SPOT_ONLY must be True"
    assert SIGNALS_ONLY,          "SAFETY: SIGNALS_ONLY must be True"
    assert not AUTO_TRADING_ENABLED, "SAFETY: AUTO_TRADING must be disabled"
    assert not FUTURES_ALLOWED,   "SAFETY: FUTURES not allowed"
    assert not LEVERAGE_ALLOWED,  "SAFETY: LEVERAGE not allowed"
    assert not TELEGRAM_SEND_ENABLED, "SAFETY: Telegram send must be disabled"

    print()
    print_separator("=")
    print("  REAL MARKET DRY RUN")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("  Source : Binance Public API (no keys required)")
    print("  Mode   : SIGNALS ONLY | SPOT ONLY | NO TELEGRAM | NO TRADES")
    print_separator("=")

    # ── Step 1: Coin Agents ──
    print("\n[STEP 1] COIN AGENTS - fetching live data\n")
    coin_reports: dict = {}
    for sym in SYMBOLS:
        report = analyze_coin(sym)
        coin_reports[sym] = report
        time.sleep(0.3)  # polite rate limit

    print("\n[STEP 1] COIN AGENT REPORTS\n")
    for sym in SYMBOLS:
        print_coin_report(coin_reports[sym])
    print()

    # ── Step 2: News Sentiment (mock) ──
    print("[STEP 2] NEWS SENTIMENT (MOCK - live feed not connected)")
    news = get_news_sentiment_mock()
    print(f"  news_status     : {news['news_status']}")
    print(f"  sentiment_score : {news['sentiment_score']}")
    print(f"  regulation      : {news['regulation_status']}")
    print(f"  note            : {news['risk_notes']}\n")

    # ── Step 3: Deep Research (mock) ──
    print("[STEP 3] DEEP RESEARCH (MOCK)")
    dr = get_deep_research_mock()
    print(f"  blacklist: {dr['coins_to_blacklist']}")
    print(f"  paused   : {dr['coins_to_pause']}")
    print(f"  note     : {dr['risk_notes']}\n")

    # ── Step 4: Risk Manager ──
    print("[STEP 4] RISK MANAGER\n")
    rm_results = []
    for sym in SYMBOLS:
        rm = run_risk_manager(coin_reports[sym])
        rm_results.append(rm)
        action = rm["risk_action"]
        allowed = rm["allowed_for_main_brain"]
        note = rm.get("block_reason") or rm.get("downgrade_reason") or "OK"
        print(f"  {sym:<10} action={action:<10} allowed={str(allowed):<5} | {note}")
    print()

    # ── Step 5: Main Brain ──
    print("[STEP 5] MAIN BRAIN\n")
    final_signals = run_main_brain(rm_results, coin_reports, news, dr)
    print_final_signals(final_signals)

    # ── Step 6: Telegram Signal Agent ──
    print("\n[STEP 6] TELEGRAM SIGNAL AGENT (console preview - SEND DISABLED)\n")
    print_telegram_preview(final_signals)
    print()

    # ── Safety confirmation ──
    print_separator("=")
    print("  SAFETY CONFIRMATION")
    print_separator("-")
    print(f"  SPOT_ONLY             = {SPOT_ONLY}")
    print(f"  SIGNALS_ONLY          = {SIGNALS_ONLY}")
    print(f"  AUTO_TRADING_ENABLED  = {AUTO_TRADING_ENABLED}")
    print(f"  FUTURES_ALLOWED       = {FUTURES_ALLOWED}")
    print(f"  LEVERAGE_ALLOWED      = {LEVERAGE_ALLOWED}")
    print(f"  TELEGRAM_SEND_ENABLED = {TELEGRAM_SEND_ENABLED}")
    print_separator("-")
    print("  No trades executed.")
    print("  No Telegram messages sent.")
    print("  No existing Python files modified.")
    print_separator("=")
    print()


if __name__ == "__main__":
    main()
