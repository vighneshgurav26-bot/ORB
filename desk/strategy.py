"""The strategy object the brain writes and rewrites.

A strategy is DATA, never code. It is a JSON document of rules over the flat
feature dictionary. That constraint is deliberate: a self-modifying bot can
never inject arbitrary logic, every version is diffable, and any version - past
or proposed - can be replayed against stored snapshots.

The brain owns everything inside the spec. config.yaml owns the ceilings, and
clamp() silently tightens any spec that exceeds them. The bot cannot loosen its
own leash.
"""
from __future__ import annotations

import copy
from typing import Any

from . import liquidity as liq

OPS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: abs(a - b) < 1e-9,
    "!=": lambda a, b: abs(a - b) >= 1e-9,
    "between": lambda a, b: b[0] <= a <= b[1],
    "outside": lambda a, b: a < b[0] or a > b[1],
    "abs>": lambda a, b: abs(a) > b,
    "abs<": lambda a, b: abs(a) < b,
}


def evaluate(rules: dict, feats: dict) -> tuple[bool, list[str]]:
    """rules = {"all":[cond...], "any":[cond...], "none":[cond...]}
    cond = {"feature": name, "op": ">", "value": x}
    Returns (passed, [readable reasons for whatever failed])."""
    fails: list[str] = []

    def check(c: dict) -> bool:
        name = c.get("feature")
        if name not in feats:
            fails.append(f"unknown feature '{name}'")
            return False
        fn = OPS.get(c.get("op"))
        if fn is None:
            fails.append(f"unknown op '{c.get('op')}'")
            return False
        try:
            ok = fn(float(feats[name]), c["value"])
        except (TypeError, ValueError):
            fails.append(f"bad value for {name}")
            return False
        if not ok:
            fails.append(f"{name}={feats[name]} fails {c['op']} {c['value']}")
        return ok

    ok = True
    for c in rules.get("all", []):
        if not check(c):
            ok = False
    anys = rules.get("any", [])
    if anys:
        hits = [check(c) for c in anys]
        if not any(hits):
            ok = False
        else:
            fails = [f for f in fails
                     if not any(str(c.get("feature")) in f for c in anys)]
    for c in rules.get("none", []):
        if check(c):
            fails.append(f"blocked by none-rule on {c.get('feature')}")
            ok = False
    return ok, fails


def clamp(spec: dict, cfg: dict) -> tuple[dict, list[str]]:
    """Force the spec inside the operator's hard ceilings. Returns notes."""
    s = copy.deepcopy(spec)
    cap = cfg["risk_ceiling"]
    notes: list[str] = []

    def limit(section: str, key: str, ceiling_key: str):
        node = s.setdefault(section, {})
        ceil = cap[ceiling_key]
        cur = node.get(key)
        if cur is None:
            node[key] = ceil
        elif cur > ceil:
            notes.append(f"{section}.{key} {cur} -> {ceil} (ceiling)")
            node[key] = ceil

    limit("sizing", "risk_per_trade_pct", "max_risk_per_trade_pct")
    limit("sizing", "max_lots", "max_lots_per_position")
    limit("sizing", "max_premium_pct", "max_premium_deployed_pct")
    limit("risk", "daily_loss_pct", "max_daily_loss_pct")
    limit("risk", "max_trades_day", "max_trades_per_day")
    limit("risk", "max_concurrent", "max_concurrent_positions")

    sess = s.setdefault("session", {})
    sess.setdefault("no_new_after", cfg["session"]["no_entry_after"])
    sess.setdefault("force_exit", cfg["session"]["force_flat_at"])
    sess.setdefault("start", cfg["session"]["no_entry_before"])

    # Selection filters may only be tightened past the global liquidity floor.
    sel = s.setdefault("selection", {})
    floor = cfg["liquidity"]["index"]
    if sel.get("max_spread_pct") is None or \
            sel["max_spread_pct"] > floor["max_spread_pct"] * 2:
        sel["max_spread_pct"] = floor["max_spread_pct"] * 2
        notes.append("selection.max_spread_pct capped")

    uni = [u for u in s.get("universe", []) if u]
    allowed = set(cfg["universe"]["indices"]) | set(cfg["universe"]["stocks"])
    dropped = [u for u in uni if u not in allowed]
    if dropped:
        notes.append(f"dropped non-permitted underlyings: {dropped}")
    uni = [u for u in uni if u in allowed][: cfg["universe"]["max_underlyings_live"]]
    s["universe"] = uni or [cfg["universe"]["indices"][0]]

    # Option BUYING only. A long-premium book is what this capital supports;
    # short options would need SPAN margin this account does not have.
    s["direction"] = "LONG_ONLY"
    return s, notes


def select_contract(snapshot: dict, spec: dict, side: str, cost_model,
                    cfg: dict, lots_wanted: int = 1) -> tuple[dict | None, str]:
    """Pick the contract to buy. side = 'CE' or 'PE'.

    The liquidity gate runs FIRST and at the intended size - not on the
    strategy's greek preferences. A contract the brain loves but the book
    cannot fill cheaply is not a trade.
    """
    sel = spec.get("selection", {})
    symbol = snapshot["symbol"]
    min_sess = max(sel.get("min_sessions_left", 0.0),
                   liq.rules_for(cfg, symbol).get("min_sessions_left", 0.0))
    exp_key = _choose_expiry(snapshot, sel.get("expiry", "nearest"), min_sess)
    if not exp_key:
        return None, "no tradable expiry"
    exp = snapshot["expiries"][exp_key]
    if exp["sessions_left"] < min_sess:
        return None, (f"nearest usable expiry has {exp['sessions_left']:.1f} "
                      f"sessions, needs {min_sess:.1f} - theta cliff")
    symbol = snapshot["symbol"]

    band = sel.get("delta_band", [0.30, 0.60])
    max_spread = sel.get("max_spread_pct", 1.0)
    min_oi = sel.get("min_oi", 0)
    max_prem_lot = sel.get("max_premium_per_lot", 1e12)

    cands, rejected = [], []
    for c in exp["contracts"]:
        if c["opt_type"] != side or c["mid"] <= 0:
            continue

        lot = int(c.get("lot_size") or 0)
        if lot <= 0:
            continue
        v = liq.assess(c, lot * max(lots_wanted, 1), cfg, cost_model, symbol)
        if not v.tradable:
            rejected.append((c["strike"], v.reasons[0] if v.reasons else "illiquid"))
            continue

        d = abs(c["delta"])
        if not (band[0] <= d <= band[1]):
            rejected.append((c["strike"], f"delta {d:.2f}"))
            continue
        if v.spread_pct > max_spread:
            rejected.append((c["strike"], f"spread {v.spread_pct:.2f}%"))
            continue
        if c["oi"] < min_oi:
            rejected.append((c["strike"], f"oi {c['oi']:.0f}"))
            continue
        if c["premium_per_lot"] * max(lots_wanted, 1) > max_prem_lot:
            rejected.append((c["strike"], "premium too big"))
            continue

        # Score: gamma per rupee of theta, penalised by everything it costs to
        # get in and out, rewarded for a book deep enough to leave in a hurry.
        score = (c["gamma_theta_ratio"]
                 - v.total_friction_pct * 1.2
                 - c["breakeven_move_pct"] * 2.0
                 + min(v.lots_at_touch / 5.0, 1.5)
                 + min(c["oi"] / 1e6, 1.0))
        cands.append((score, c, v))

    if not cands:
        return None, f"nothing passed the gate (first rejections: {rejected[:4]})"
    cands.sort(key=lambda x: -x[0])
    _, best, v = cands[0]
    best = dict(best)
    best["_liquidity_at_size"] = v.to_dict()
    return best, (f"{best['tradingsymbol']} delta={best['delta']:.2f} "
                  f"iv={best['iv']:.1%} theta/session={best['theta_session']:.2f} "
                  f"breakeven={best['breakeven_move_pct']:.2f}% "
                  f"friction={v.total_friction_pct:.2f}% "
                  f"({v.lots_at_touch:.1f} lots on the offer)")


def _choose_expiry(snapshot: dict, mode: str,
                   min_sessions: float = 0.0) -> str | None:
    keys = sorted(snapshot["expiries"])
    if min_sessions:
        # Measured on NIFTY 24-Jul-2026: the front expiry with 2 sessions left
        # was bleeding 18.2% of premium per session, versus 5.9% on the next
        # weekly. Same underlying, same direction, three times the decay.
        keys = [k for k in keys
                if snapshot["expiries"][k]["sessions_left"] >= min_sessions] or keys
    if not keys:
        return None
    if mode in ("nearest", "nearest_weekly"):
        return keys[0]
    if mode == "next":
        return keys[1] if len(keys) > 1 else keys[0]
    if mode == "skip_expiry_day":
        for k in keys:
            if snapshot["expiries"][k]["days_to_expiry"] >= 1:
                return k
        return keys[-1]
    return keys[0]


# --------------------------------------------------------------------------
# Seed strategy. Deliberately conservative and deliberately mediocre - it
# exists so the desk has something to start measuring, not because it works.
# The brain replaces it at the first review.
#
# Sized for Rs 5,00,000: 1.5% risk = Rs 7,500, which funds ~3 lots of a NIFTY
# weekly at Rs 210 with a 15% stop. Multi-lot matters - it is what dilutes the
# flat Rs 20 per order down to a rounding error.
# --------------------------------------------------------------------------
SEED_SPEC: dict[str, Any] = {
    "name": "ORB_BodyBreak_StockInPlay",
    "rationale": (
        "Opening Range Breakout, implemented from the user's document. Marks the "
        "09:15-09:30 15-minute range, waits for a 5-minute candle BODY (not a "
        "wick) to close beyond it, buys near-ATM CE on an up-break or PE on a "
        "down-break, targets 1:2, caps at 2 trades per day, and trails on the 5m "
        "9-EMA. The doc's 'Stock in Play' relative-volume filter (rel_volume > "
        "1.5) is the primary edge. The desk's liquidity and theta gates ride on "
        "top: the doc's own Section 4 demands price/volume/ATR screening and its "
        "Key Terms name theta decay as the risk quick exits exist to dodge, so a "
        "low realised-vs-implied day is still skipped rather than bought."),
    "universe": ["NIFTY", "BANKNIFTY", "RELIANCE", "ICICIBANK"],
    "session": {"start": "09:30", "no_new_after": "13:30", "force_exit": "15:10"},
    "selection": {
        "expiry": "skip_expiry_day",
        "min_sessions_left": 3.0,
        "delta_band": [0.40, 0.62],
        "max_spread_pct": 0.70,
        "min_oi": 150000,
        "max_premium_per_lot": 22000,
    },
    "entry_long_call": {
        "all": [
            {"feature": "orb_body_break",        "op": ">",  "value": 0.5},
            {"feature": "minutes_into_session",  "op": ">=", "value": 15},
            {"feature": "orb_range_pct",         "op": ">",  "value": 0.12},
            {"feature": "rel_volume",            "op": ">",  "value": 1.5},
            {"feature": "atr_pct",               "op": ">",  "value": 0.030},
            {"feature": "ema9_side",             "op": ">",  "value": 0.0},
            {"feature": "rv_iv_ratio",           "op": ">",  "value": 0.80},
            {"feature": "atm_total_friction_pct","op": "<",  "value": 1.45},
            {"feature": "liquid_contracts",      "op": ">=", "value": 6},
            {"feature": "minutes_to_close",      "op": ">",  "value": 90},
        ],
        "none": [
            {"feature": "atm_one_tick_pct",      "op": ">",  "value": 0.12},
            {"feature": "sessions_left",         "op": "<",  "value": 3.0},
        ],
    },
    "entry_long_put": {
        "all": [
            {"feature": "orb_body_break",        "op": "<",  "value": -0.5},
            {"feature": "minutes_into_session",  "op": ">=", "value": 15},
            {"feature": "orb_range_pct",         "op": ">",  "value": 0.12},
            {"feature": "rel_volume",            "op": ">",  "value": 1.5},
            {"feature": "atr_pct",               "op": ">",  "value": 0.030},
            {"feature": "ema9_side",             "op": "<",  "value": 0.0},
            {"feature": "rv_iv_ratio",           "op": ">",  "value": 0.80},
            {"feature": "atm_total_friction_pct","op": "<",  "value": 1.45},
            {"feature": "liquid_contracts",      "op": ">=", "value": 6},
            {"feature": "minutes_to_close",      "op": ">",  "value": 90},
        ],
        "none": [
            {"feature": "atm_one_tick_pct",      "op": ">",  "value": 0.12},
            {"feature": "sessions_left",         "op": "<",  "value": 3.0},
        ],
    },
    "exit": {
        "target_pct": 30.0,
        "stop_pct": 15.0,
        "ema9_trail": True,
        "trail_after_pct": 20.0,
        "trail_giveback_pct": 45.0,
        "time_stop_min": 60,
        "iv_crush_exit_pct": 8.0,
    },
    "sizing": {"risk_per_trade_pct": 1.5, "max_lots": 2, "max_premium_pct": 22.0},
    "risk": {"daily_loss_pct": 3.0, "max_trades_day": 2,
             "max_concurrent": 1, "cooldown_min_after_loss": 20},
}
