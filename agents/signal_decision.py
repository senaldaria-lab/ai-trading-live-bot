"""
Signal decision agent — SIGNALS_ONLY mode.

Produces one of four labels:
  STRONG_BUY  — high-confidence bullish setup, all guards passed
  BUY_WATCH   — partial bullish setup worth monitoring
  WAIT        — mixed or unclear conditions, prefer patience
  AVOID       — bearish structure or failed risk check

Score is 0–100.  No orders are ever placed here.
"""

STRONG_BUY = "STRONG_BUY"
BUY_WATCH  = "BUY_WATCH"
WAIT       = "WAIT"
AVOID      = "AVOID"

# Score thresholds
_THRESHOLD_STRONG_BUY = 70
_THRESHOLD_BUY_WATCH  = 55
_THRESHOLD_WAIT       = 25

# Volume ratio tier thresholds (current bar / 20-period average)
_VOL_HIGH_RATIO    = 1.2   # ≥ 1.2× avg → high volume
_VOL_AVERAGE_RATIO = 0.8   # ≥ 0.8× avg → average volume  (below → low)


def _compute_score(analysis: dict, risk_level: str) -> int:
    """Return a 0–100 confidence score for a bullish spot setup.

    Component breakdown (max 100 pts):
      EMA alignment   30 pts
      MACD sign       25 pts  (–5 penalty when clearly negative)
      RSI zone        20 pts
      Volume tier     15 pts
      Risk level      10 pts
    """
    score = 0

    ema20        = analysis["ema20"]
    ema50        = analysis["ema50"]
    ema200       = analysis["ema200"]
    rsi          = analysis["rsi"]
    macd         = analysis["macd"]          # macd_line − macd_signal
    volume_ratio = analysis.get("volume_ratio", 1.0)

    # ── EMA trend structure: 30 pts ──────────────────────────────────────────
    if ema20 > ema50 > ema200:        # full bullish stack
        score += 30
    elif ema20 > ema50:               # short-term bullish only
        score += 18
    elif ema50 > ema200:              # medium-term bullish only
        score += 8
    # full bearish → 0 pts

    # ── MACD histogram sign: 25 pts, –5 bearish penalty ─────────────────────
    # near-zero band = 0.1% of EMA20 (scales with asset price).
    near_zero = abs(ema20) * 0.001
    if macd > near_zero:
        score += 25        # clearly positive — strong bullish momentum
    elif macd > -near_zero:
        score += 5         # near neutral — small credit only (was 10, now 5)
    else:
        score -= 5         # clearly negative — bearish penalty

    # ── RSI zone: 20 pts ─────────────────────────────────────────────────────
    if 45 <= rsi <= 60:
        score += 20        # sweet spot: momentum without overextension
    elif 40 <= rsi < 45:
        score += 10        # acceptable but showing weak momentum
    elif 60 < rsi <= 65:
        score += 8         # reduced — approaching overbought territory
    elif 35 <= rsi < 40:
        score += 4         # weak momentum warning
    elif 65 < rsi <= 70:
        score += 4         # overbought caution zone
    elif 30 <= rsi < 35:
        score += 2         # near oversold
    # RSI < 30 or RSI > 70 → 0 pts (extreme zones)

    # ── Volume tier: 15 pts ──────────────────────────────────────────────────
    if volume_ratio >= _VOL_HIGH_RATIO:
        score += 15        # high volume — strong confirmation
    elif volume_ratio >= _VOL_AVERAGE_RATIO:
        score += 8         # average volume — watch carefully
    # below average → 0 pts (weak signal)

    # ── Risk level: 10 pts ───────────────────────────────────────────────────
    if risk_level == "LOW":
        score += 10
    elif risk_level == "MEDIUM":
        score += 5
    # HIGH → 0 pts

    # Clamp: MACD penalty can push raw score below 0
    return max(0, min(score, 100))


def _score_to_signal(
    score: int,
    risk_ok: bool,
    risk_level: str,
    analysis: dict,
    trend_4h: str = "neutral",
) -> str:
    """Map score + risk context to a signal label.

    Override chain (applied top-to-bottom):
      1. Failed risk check → AVOID (HIGH) or WAIT (MEDIUM)
      2. Candidate from score thresholds
      3. STRONG_BUY structural guards: EMA bull stack, MACD positive,
         volume confirmed, RSI ≤ 65 — any failing → drops to BUY_WATCH
      4. BUY_WATCH guard: RSI > 70 → WAIT
      5. MEDIUM risk cap: STRONG_BUY → BUY_WATCH
      6. 4H trend bearish: STRONG_BUY and BUY_WATCH both → WAIT
    """
    rsi = analysis["rsi"]

    # 1. Failed risk check
    if not risk_ok:
        return AVOID if risk_level == "HIGH" else WAIT

    # 2. Candidate from score
    if score >= _THRESHOLD_STRONG_BUY:
        candidate = STRONG_BUY
    elif score >= _THRESHOLD_BUY_WATCH:
        candidate = BUY_WATCH
    elif score >= _THRESHOLD_WAIT:
        candidate = WAIT
    else:
        candidate = AVOID

    # 3. STRONG_BUY structural guards (all must pass)
    if candidate == STRONG_BUY:
        near_zero     = abs(analysis["ema20"]) * 0.001
        ema_bull      = analysis["ema20"] > analysis["ema50"] > analysis["ema200"]
        macd_positive = analysis["macd"] > near_zero
        # HIGH volume (≥1.2×) required for STRONG_BUY; average volume → BUY_WATCH only
        vol_high      = analysis.get("volume_tier") == "high"
        rsi_safe      = rsi <= 65               # RSI > 65 = overbought, block STRONG_BUY

        if not (ema_bull and macd_positive and vol_high and rsi_safe):
            candidate = BUY_WATCH

    # 4. BUY_WATCH guard: overbought RSI with no long signal
    if candidate == BUY_WATCH and rsi > 70:
        candidate = WAIT

    # 5. MEDIUM risk cap
    if risk_level == "MEDIUM" and candidate == STRONG_BUY:
        candidate = BUY_WATCH

    # 6. 4H macro trend override: bearish 4H blocks both STRONG_BUY and BUY_WATCH.
    # Trading a bullish 1H signal against a bearish 4H trend is a low-quality setup.
    if trend_4h == "bearish" and candidate in (STRONG_BUY, BUY_WATCH):
        candidate = WAIT

    return candidate


def decide_signal(
    symbol: str,
    analysis: dict,
    news_sentiment: str,
    risk_ok: bool,
    risk_level: str = "HIGH",
    trend_4h: str = "neutral",
) -> tuple[str, int]:
    """Return (signal_label, score_0_to_100).

    Never places orders.  Only produces a signal for manual review.
    """
    score  = _compute_score(analysis, risk_level)
    signal = _score_to_signal(score, risk_ok, risk_level, analysis, trend_4h)
    return signal, score
