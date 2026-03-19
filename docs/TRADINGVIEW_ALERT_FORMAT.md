# TradingView Alert Format

When creating alerts in TradingView, use this JSON format in the "Message" field.

## Minimal Alert (required fields only)

```json
{
  "symbol": "ES1!",
  "timeframe": "5",
  "direction": "bullish",
  "signal_type": "indication",
  "price": {{close}},
  "timestamp": "{{time}}"
}
```

## Full Alert (all supported fields)

```json
{
  "symbol": "{{ticker}}",
  "timeframe": "{{interval}}",
  "direction": "bullish",
  "signal_type": "indication",
  "indication_type": "structure_break_high",
  "price": {{close}},
  "high": {{high}},
  "low": {{low}},
  "volume": {{volume}},
  "htf_bias": "bullish",
  "session": "us_regular",
  "notes": "Break of morning high with expansion candle",
  "timestamp": "{{timenow}}"
}
```

## Field Descriptions

| Field | Required | Values |
|-------|----------|--------|
| symbol | Yes | ES1!, MES1!, NQ1!, etc. |
| timeframe | Yes | "1", "3", "5", "15", "60" (minutes) |
| direction | Yes | "bullish" or "bearish" |
| signal_type | Yes | "indication", "correction", "continuation", "setup_complete" |
| indication_type | No | See list below |
| price | Yes | Current price (use {{close}}) |
| high | No | Candle high |
| low | No | Candle low |
| volume | No | Candle volume |
| htf_bias | No | "bullish", "bearish", "neutral" |
| session | No | "us_premarket", "us_regular", "us_afterhours" |
| notes | No | Any free text |
| timestamp | Yes | Use {{timenow}} |

## Indication Types

- `structure_break_high` — Break of recent swing high
- `structure_break_low` — Break of recent swing low
- `liquidity_sweep_reclaim` — Sweep of lows/highs then reclaim
- `displacement_up` — Large bullish displacement candle
- `displacement_down` — Large bearish displacement candle
- `momentum_expansion` — Momentum expansion in direction
- `level_reclaim` — Reclaim of key intraday level

## Setting Up the Webhook in TradingView

1. Open any chart
2. Click the alarm clock icon (Alerts) in the toolbar
3. Click "Create Alert"
4. Set your condition (e.g., price crosses above a level)
5. Scroll to "Notifications"
6. Check "Webhook URL"
7. Enter your webhook URL: `https://your-server.com/api/v1/alerts/webhook`
8. In the "Message" field, paste your JSON from above
9. Save the alert

## Security

Always include the security header. Add this in TradingView's webhook settings:
```
X-Webhook-Token: your-secret-token-from-.env
```
