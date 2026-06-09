import pandas as pd
import ta


def analyze_technical_indicators(df: pd.DataFrame) -> dict:
    close = df["close"]
    volume = df["volume"]

    ema20 = ta.trend.ema_indicator(close, window=20).iloc[-1]
    ema50 = ta.trend.ema_indicator(close, window=50).iloc[-1]
    ema200 = ta.trend.ema_indicator(close, window=200).iloc[-1]
    rsi = ta.momentum.rsi(close, window=14).iloc[-1]
    macd_line = ta.trend.MACD(close).macd().iloc[-1]
    macd_signal = ta.trend.MACD(close).macd_signal().iloc[-1]
    macd_diff = macd_line - macd_signal

    volume_avg = volume.rolling(20).mean().iloc[-1]
    volume_ratio = float(volume.iloc[-1] / volume_avg) if volume_avg > 0 else 0.0
    volume_ok = volume_ratio >= 0.8
    # 3-tier classification: high ≥1.2×, average ≥0.8×, low <0.8×
    if volume_ratio >= 1.2:
        volume_tier = "high"
    elif volume_ratio >= 0.8:
        volume_tier = "average"
    else:
        volume_tier = "low"

    atr = ta.volatility.average_true_range(
        df["high"], df["low"], close, window=14
    ).iloc[-1]

    return {
        "ema20": float(ema20),
        "ema50": float(ema50),
        "ema200": float(ema200),
        "rsi": float(rsi),
        "macd": float(macd_diff),
        "volume_ok": bool(volume_ok),
        "volume_ratio": round(volume_ratio, 4),
        "volume_tier": volume_tier,
        "atr": round(float(atr), 8),
    }


def analyze_trend_4h(df: pd.DataFrame) -> str:
    """Return 4H macro trend: 'bullish', 'neutral', or 'bearish'.

    Uses EMA20 vs EMA50 on the 4H chart.
    Returns 'neutral' when fewer than 51 candles are available.
    """
    if df is None or len(df) < 51:
        return "neutral"
    close = df["close"]
    ema20 = ta.trend.ema_indicator(close, window=20).iloc[-1]
    ema50 = ta.trend.ema_indicator(close, window=50).iloc[-1]
    if ema20 > ema50:
        return "bullish"
    if ema20 < ema50:
        return "bearish"
    return "neutral"
