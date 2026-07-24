# ORB Desk — ₹1,00,000

Opening Range Breakout, built from your ORB document, running as a **separate
paper desk** from the main ₹5,00,000 momentum desk. Its own repo, its own
`state/desk.db`, its own dashboard.

## What it does, faithful to the doc

- Marks the **09:15–09:30 15-minute opening range**.
- Waits for a 5-minute candle **BODY** (not a wick) to close beyond it — the
  doc's body-breakout filter (`orb_body_break`).
- Up-break → buys a near-ATM **CALL**; down-break → a near-ATM **PUT**.
- **1:2 risk-reward**, and a **9-EMA trailing exit** so trend days can run to
  1:3 or 1:4 (`ema9_trail`).
- **Maximum 2 trades per day** — the doc's Two-Trade Rule, enforced as a hard
  ceiling the bot cannot raise.
- The doc's **"Stock in Play" relative-volume filter** (`rel_volume > 1.5`) is
  the primary edge.

## What it adds on top, and why

The doc's Section 4 already demands price / volume / ATR / relative-volume
screening, and its Key Terms name **theta decay** as the risk that quick exits
exist to dodge. So the desk keeps its liquidity and theta gates:

- minimum premium, spread, depth, book-walk impact (so cheap illiquid options
  are refused — see the main desk's calibration on real Zerodha books);
- `rv_iv_ratio > 0.80` — on a day when the tape delivers less than the options
  charge, even a correct breakout loses to decay, so it's skipped.

This is in the spirit of the doc, not a departure. On the 24-Jul NIFTY tape the
ORB logic fired a correct short at 09:35 — but that morning's front-expiry puts
had ~18%/session theta and RV/IV of 0.60, so the gate would (rightly) have held
it back.

## Setup

Identical to the main desk — see the main repo's SETUP.md. Only differences:
this is its **own** GitHub repo (or VPS folder), and the capital in
`config.yaml` is ₹1,00,000. Do not point both desks at the same `state/`.

The strategy auto-installs on first run; no manual step.

## The honest caveat

This is authored from a document, not yet validated on forward paper trades.
The ORB entry logic is sound and fires correctly on real data — but "fires
correctly" is not "makes money." Judge it on its forward paper record after a
few weeks, across at least one high-vol and one low-vol regime. At ₹1,00,000,
sizing is tight: one NIFTY lot of a ~₹150 option is ~10% of the account, so
most days it trades one lot or none.
