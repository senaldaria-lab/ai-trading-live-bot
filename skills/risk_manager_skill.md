# RISK MANAGER SKILL

## Role
The Risk Manager is the safety gate between coin agent analysis and Main Brain approval.
It enforces strict rules to protect capital and block unsafe signals.

## Inputs
- Preliminary report from each coin agent (includes SEL, volume_status, timeframe_gate)
- Volume data
- Volatility measurement
- Liquidity status

## Standard Volume Classification
All volume checks use this shared definition:

| Label | Threshold | Meaning |
|-------|-----------|---------|
| `HIGH` | >= 1.5x 20-period average | Strong participation |
| `NORMAL` | 0.8x–1.5x 20-period average | Acceptable |
| `LOW` | < 0.8x 20-period average | Weak — triggers downgrade or block |

LOW volume must downgrade or block BUY signals. This rule applies at every layer.

## Blocking Rules (immediate BLOCK, no override)

### 1. High Risk Block
- Volatility ATR > 5% of price on 1H candle → BLOCK
- Coin listed on `coins_to_blacklist` by Deep Research → BLOCK (no analysis needed)
- volume_status = LOW AND 24H absolute volume < $30M USDT → BLOCK
- 24H absolute volume < $10M USDT → BLOCK (emergency hard floor; any coin below this should already be paused by coin_selection_rules)

### 2. FOMO Block
- Price already moved > 8% from support before signal → BLOCK
- RSI > 78 on 1H or 4H → BLOCK (overbought chase)
- Signal generated after a 3+ consecutive green candle run without pullback → BLOCK

### 3. Data Quality Block
- Missing candle data for any required timeframe → BLOCK
- API errors or stale data (> 5 min old) → BLOCK
- Conflicting signals across timeframes with no clear dominant trend → BLOCK

### 4. Mode Enforcement
- Futures signals → BLOCK (spot only)
- Leverage signals → BLOCK
- Auto-execution requests → BLOCK (signals only mode)
- Any trade instruction bypassing Main Brain → BLOCK

## Downgrade Rules (signal reduced, not blocked)

| Condition | Action |
|-----------|--------|
| RSI 65–78 on 1H | Downgrade BUY → WATCH |
| volume_status = LOW (< 0.8x average) | Downgrade STRONG_BUY → BUY; block if LOW for 3+ consecutive periods |
| Only 2 of 3 timeframes aligned (timeframe_gate FAIL) | Downgrade STRONG_BUY → BUY |
| SEL = WEAK | Downgrade any BUY → WATCH |
| Support distance < 1% | Downgrade BUY → WATCH |

## Output Format

```yaml
symbol: SOLUSDT
input_decision: PRELIMINARY_BUY
input_score: 73
input_risk: MEDIUM
risk_check_result: PASS
risk_action: ALLOW
block_reason: null
downgrade_reason: null
final_risk_label: MEDIUM
allowed_for_main_brain: true
```

Allowed `risk_action` values:
- `ALLOW` — signal passes to Main Brain unchanged
- `DOWNGRADE` — signal label reduced; `downgrade_reason` must be set
- `BLOCK` — signal discarded; `block_reason` must be set; `allowed_for_main_brain: false`

## Hard Rules
- Risk Manager cannot be bypassed by any agent
- Risk Manager cannot approve trades — only pass or block signals
- Every signal MUST pass through Risk Manager before reaching Main Brain
- Risk per trade cap: 0.5–1% of account — enforced in position sizing only
- No futures. No leverage. Spot only.
