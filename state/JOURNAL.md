# Options Desk — Trading Journal

**Strategy v1 — ORB_BodyBreak_StockInPlay**

Opening Range Breakout, implemented from the user's document. Marks the 09:15-09:30 15-minute range, waits for a 5-minute candle BODY (not a wick) to close beyond it, buys near-ATM CE on an up-break or PE on a down-break, targets 1:2, caps at 2 trades per day, and trails on the 5m 9-EMA. The doc's 'Stock in Play' relative-volume filter (rel_volume > 1.5) is the primary edge. The desk's liquidity and theta gates ride on top: the doc's own Section 4 demands price/volume/ATR screening and its Key Terms name theta decay as the risk quick exits exist to dodge, so a low realised-vs-implied day is still skipped rather than bought.

## Performance

- **trades**: 0
- **note**: no trades generated

## Strategy versions

| v | name | status | created |
|---|---|---|---|
| 1 | ORB_BodyBreak_StockInPlay | ACTIVE | 2026-07-25T05:19:24+05:30 |

## Reviews

### 2026-07-27T16:27:07+05:30 — idle (v1 -> v1)
The strategy has zero trades, so there is no P&L, MFE/MAE, exit-reason mix, or charge analysis to evaluate — every diagnostic bucket is empty. With no executions the strategy is untestable in live conditions and learns nothing. The note in the payload makes the diagnosis explicit: entry rules are too tight. The combined filter stack (orb_range_pct > 0.12, rel_volume > 1.5, atr_pct > 0.03, rv_iv_ratio > 0.8, ema9_side confirmation, atm_one_tick_pct guard, liquid_contracts >= 6, minutes_to_close > 90, plus the screener's own liquidity×volatility gate) creates a conjunction of seven-plus conditions, each of which eliminates a fraction of candidates, and their product fires almost never on a 4-stock universe. The universe itself — NIFTY, BANKNIFTY, RELIANCE, ICICIBANK — is sensible for liquidity but too narrow to give enough at-bats for the filters to find a pass. Sample size is zero; any directional conclusion about edge is impossible, so the only valid response is to loosen enough to generate 1–3 trades per week and begin collecting real data.

*Changes:* proposal rejected: only 0 backtest trades (need 20); does not beat the incumbent's expectancy; expectancy is not positive

## Closed trades

| entry | symbol | contract | lots | in | out | why | gross | charges | net |
|---|---|---|---|---|---|---|---|---|---|

## Reasoning log
