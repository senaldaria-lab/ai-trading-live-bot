from config.settings import SETTINGS

# Risk levels enforced by RISK_MANAGER_SKILLS: LOW, MEDIUM, HIGH
RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"


def _classify_risk(analysis: dict, news_sentiment: str) -> str:
    """Return LOW / MEDIUM / HIGH based on indicator extremes, volume tier, and news.

    Volume tier drives base risk level:
      low  (<0.8×)  → HIGH  (hard block — no auto-trade possible)
      average (0.8–1.2×) → MEDIUM  (BUY_WATCH / TEST WATCH only)
      high (≥1.2×)  → eligible for LOW (if other conditions clean)
    """
    rsi = analysis["rsi"]
    volume_tier = analysis.get("volume_tier", "low")

    # Extreme RSI → HIGH regardless of volume
    if rsi > 75 or rsi < 15:
        return RISK_HIGH

    # Low volume → HIGH risk (hard block)
    if volume_tier == "low":
        return RISK_HIGH

    # Average volume → MEDIUM risk ceiling (allows BUY_WATCH/TEST WATCH)
    if volume_tier == "average":
        return RISK_MEDIUM

    # High volume — check for MEDIUM promoters
    if news_sentiment != "neutral":
        return RISK_MEDIUM
    if rsi > 65 or rsi < 30:
        return RISK_MEDIUM

    return RISK_LOW


def assess_risk(symbol: str, analysis: dict, news_sentiment: str) -> tuple[bool, str, str]:
    """Return (risk_ok, note, risk_level).

    risk_level is one of LOW / MEDIUM / HIGH.
    """
    risk_level = _classify_risk(analysis, news_sentiment)

    if analysis["rsi"] > 75:
        return False, "RSI too high", risk_level
    if analysis["rsi"] < 15:
        return False, "RSI too low", risk_level
    volume_ratio = float(analysis.get("volume_ratio", 0.0))
    if volume_ratio < 0.8:
        return False, "Low volume signal", risk_level
    if news_sentiment != "neutral":
        return False, f"News sentiment: {news_sentiment}", risk_level

    return True, "Risk check passed", risk_level
