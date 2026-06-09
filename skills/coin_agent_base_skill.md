# COIN AGENT BASE SKILL

## Role
Every coin agent inherits this base skill. It defines the standard analysis pipeline
that each coin agent must execute before generating a preliminary report.

A coin agent analyzes exactly ONE symbol assigned to it.
It NEVER takes final action — it only reports to the Main Brain.

## Analysis Pipeline (Required for Every Coin Agent)

### Step 1 — 4H Trend Analysis
- Fetch last 50 candles on 4H timeframe
- Determine trend: UPTREND / DOWNTREND / SIDEWAYS
- Criteria:
  - UPTREND: price above EMA50 4H AND higher highs + higher lows
  - DOWNTREND: price below EMA50 4H AND lower highs + lower lows
  - SIDEWAYS: price oscillating between EMA20 and EMA50 without clear direction

### Step 2 — 1H Trend Analysis
- Fetch last 50 candles on 1H timeframe
- Determine short-term momentum: BULLISH / BEARISH / NEUTRAL
- Used to confirm or deny 4H trend

### Step 3 — 15m Trend Analysis (Entry Timing)
- Fetch last 50 candles on 15m timeframe
- Determine entry timing signal: BULLISH / BEARISH / NEUTRAL
- Purpose: fine-tune entry timing; avoid buying into an active 15m breakdown

**3-Timeframe Confirmation Gate:**

| Timeframe | Required Condition |
|-----------|-------------------|
| 4H | NOT DOWNTREND |
| 1H | BULLISH or NEUTRAL (improving) |
| 15m | NOT BEARISH (not breaking down) |

- All three conditions met → `timeframe_gate: PASS`
- Any condition fails → `timeframe_gate: FAIL` → cap at WATCH; BUY blocked

### Step 4 — EMA Analysis
Compute and evaluate:
- EMA 20 (short-term momentum)
- EMA 50 (medium-term trend)
- EMA 200 (long-term baseline)

Alignment checks:
- Bullish alignment: EMA20 > EMA50 > EMA200
- Bearish alignment: EMA20 < EMA50 < EMA200
- Mixed: partial alignment (reduce score)

### Step 5 — RSI (14-period)
- Calculate RSI on 1H and 4H
- Scoring:
  - RSI 40–60: neutral zone → 0 impact
  - RSI 30–40: recovering → mild bullish
  - RSI 20–30: oversold → potential reversal
  - RSI 60–70: building momentum → bullish
  - RSI > 70: overbought → flag for Risk Manager
  - RSI < 20: extreme oversold → flag for Risk Manager

### Step 6 — MACD
- Calculate MACD (12, 26, 9) on 1H
- Check:
  - MACD line crossed above signal → bullish crossover
  - MACD line crossed below signal → bearish crossover
  - Histogram increasing → momentum building
  - Histogram shrinking → momentum fading

### Step 7 — Volume Analysis
Compare current volume to 20-period average. Apply the standard volume classification:

| Label | Threshold | Signal Impact |
|-------|-----------|--------------|
| `HIGH` | >= 1.5x average | Strong participation — supports signal |
| `NORMAL` | 0.8x–1.5x average | Acceptable — no penalty |
| `LOW` | < 0.8x average | Weak — flag for Risk Manager; downgrade or block BUY |

Rules:
- `LOW` volume must downgrade PRELIMINARY_BUY → WATCH
- `LOW` volume must block any STRONG_BUY regardless of other indicators
- `HIGH` volume on a bullish signal adds confirmation weight

### Step 8 — Support and Resistance
- Identify nearest:
  - Support level: most recent swing low below current price (last 50 candles on 1H)
  - Resistance level: most recent swing high above current price (last 50 candles on 1H)
- Compute:
  - Distance to support (%)
  - Distance to resistance (%)
  - Risk/Reward ratio = distance_to_resistance / distance_to_support

### Step 9 — Volatility
- Compute ATR (14-period) on 1H
- Express as % of current price
- Low volatility (< 1%): quiet market
- Medium (1–3%): normal
- High (> 3%): elevated risk → flag for Risk Manager

### Step 10 — SEL Calculation (Signal Evaluation Level)
SEL is a combined internal signal quality label. It summarises the overall health
of this coin's signal before the report is passed to Risk Manager and Main Brain.

**SEL = Signal Evaluation Level. It does NOT override Risk Manager or Main Brain.**

Score one point for each positive dimension:

| Dimension | Positive Condition |
|-----------|-------------------|
| Trend alignment | 4H not DOWNTREND AND 1H BULLISH |
| 15m entry timing | 15m not BEARISH (timeframe_gate PASS) |
| RSI condition | RSI (1H) between 40–70 |
| MACD confirmation | Bullish crossover OR histogram growing |
| Volume status | HIGH or NORMAL |
| S/R quality | R/R ratio >= 1.5 |

SEL values:
- `STRONG`: 5–6 positive dimensions
- `MODERATE`: 3–4 positive dimensions
- `WEAK`: 1–2 positive dimensions
- `INVALID`: missing data, BLOCKED flag, or contradictory signals that cannot be resolved

### Step 11 — Preliminary Score
Combine all signals into a score out of 100:

| Component | Max Points |
|-----------|-----------|
| 4H trend alignment | 20 |
| 1H trend confirmation | 10 |
| 15m entry timing | 10 |
| EMA stack alignment | 20 |
| RSI position | 10 |
| MACD crossover | 10 |
| Volume confirmation | 10 |
| Risk/Reward ratio | 10 |

### Step 12 — Local Risk Assessment
- Flag any of: high volatility, overbought RSI, LOW volume, missing data
- Output: LOW / MEDIUM / HIGH / BLOCKED

### Step 13 — Preliminary Decision
Based on score, local risk, and timeframe gate:

| Score | Local Risk | Timeframe Gate | Preliminary Decision |
|-------|-----------|----------------|---------------------|
| >= 75 | LOW | PASS | PRELIMINARY_BUY |
| 60–74 | LOW/MEDIUM | PASS | WATCH |
| 50–59 | any | any | WATCH |
| < 50 | any | any | AVOID |
| any | BLOCKED | any | AVOID |
| any | any | FAIL | WATCH (maximum) |

## Output Format

All coin agents must output a YAML-compatible dict with the following fields.
Coin-specific agents may add extra fields after `reason` (e.g. `btc_context`, `eth_context`).

```yaml
symbol: SYMBOL_USDT
timeframe_4h_trend: UPTREND
timeframe_1h_trend: BULLISH
timeframe_15m_trend: BULLISH
timeframe_gate: PASS
ema_status: "Bullish (EMA20 > EMA50 > EMA200)"
rsi: 54.3
rsi_4h: 61.2
macd_status: "Bullish crossover, histogram positive"
volume_status: HIGH
support_level: "XXXX (2.1% below)"
resistance_level: "XXXX (4.8% above)"
volatility: "1.4% ATR (NORMAL)"
sel: STRONG
preliminary_score: 78
local_risk: LOW
preliminary_decision: PRELIMINARY_BUY
reason: "Brief human-readable explanation of key signal drivers"
```

## Hard Restrictions — All Coin Agents
- DO NOT send Telegram messages
- DO NOT approve final BUY or SELL
- DO NOT execute trades or place orders
- DO NOT bypass Risk Manager
- DO NOT bypass Main Brain
- DO NOT analyze any symbol other than the one assigned
