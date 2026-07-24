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

## Closed trades

| entry | symbol | contract | lots | in | out | why | gross | charges | net |
|---|---|---|---|---|---|---|---|---|---|

## Reasoning log
