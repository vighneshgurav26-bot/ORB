"""ONE-SHOT: install the v3 relaxed strategy. Run once, then delete."""
import json, sys
sys.path.insert(0, ".")
import yaml
from desk import clock
from desk import strategy as strat
from desk.store import Store

V3 = json.loads(r"""{"name": "ORB_v3_WideOpen_HardRiskOnly", "rationale": "v3: only the ORB body-break plus a minimal cost/liquidity floor are mandatory. Every confirmation (rel_volume 1.2->0.9, ema side, atr 0.030->0.020, range width, distance, rv/iv) is now any-one-of. Expiry floor eased 3->2 sessions, time-to-close 75->45min, max 3 trades/day. Stops, 1:2 RR, 9-EMA trail, 1.5% risk and the daily halt are UNCHANGED.", "universe": ["NIFTY", "BANKNIFTY", "RELIANCE", "ICICIBANK"], "session": {"start": "09:30", "no_new_after": "14:15", "force_exit": "15:10"}, "selection": {"expiry": "skip_expiry_day", "min_sessions_left": 2.0, "delta_band": [0.35, 0.68], "max_spread_pct": 0.9, "min_oi": 100000, "max_premium_per_lot": 22000}, "entry_long_call": {"all": [{"feature": "orb_body_break", "op": ">", "value": 0.5}, {"feature": "minutes_into_session", "op": ">=", "value": 15}, {"feature": "atm_total_friction_pct", "op": "<", "value": 1.9}, {"feature": "liquid_contracts", "op": ">=", "value": 4}, {"feature": "minutes_to_close", "op": ">", "value": 45}], "any": [{"feature": "rel_volume", "op": ">", "value": 0.9}, {"feature": "ema9_side", "op": ">", "value": 0.0}, {"feature": "atr_pct", "op": ">", "value": 0.02}, {"feature": "dist_from_or_pct", "op": ">", "value": 0.02}, {"feature": "orb_range_pct", "op": ">", "value": 0.06}, {"feature": "rv_iv_ratio", "op": ">", "value": 0.7}], "none": [{"feature": "atm_one_tick_pct", "op": ">", "value": 0.2}, {"feature": "sessions_left", "op": "<", "value": 2.0}]}, "entry_long_put": {"all": [{"feature": "orb_body_break", "op": "<", "value": -0.5}, {"feature": "minutes_into_session", "op": ">=", "value": 15}, {"feature": "atm_total_friction_pct", "op": "<", "value": 1.9}, {"feature": "liquid_contracts", "op": ">=", "value": 4}, {"feature": "minutes_to_close", "op": ">", "value": 45}], "any": [{"feature": "rel_volume", "op": ">", "value": 0.9}, {"feature": "ema9_side", "op": "<", "value": -0.0}, {"feature": "atr_pct", "op": ">", "value": 0.02}, {"feature": "dist_from_or_pct", "op": ">", "value": 0.02}, {"feature": "orb_range_pct", "op": ">", "value": 0.06}, {"feature": "rv_iv_ratio", "op": ">", "value": 0.7}], "none": [{"feature": "atm_one_tick_pct", "op": ">", "value": 0.2}, {"feature": "sessions_left", "op": "<", "value": 2.0}]}, "exit": {"target_pct": 30.0, "stop_pct": 15.0, "ema9_trail": true, "trail_after_pct": 20.0, "trail_giveback_pct": 45.0, "time_stop_min": 60, "iv_crush_exit_pct": 8.0}, "sizing": {"risk_per_trade_pct": 1.5, "max_lots": 2, "max_premium_pct": 22.0}, "risk": {"daily_loss_pct": 3.0, "max_trades_day": 3, "max_concurrent": 2, "cooldown_min_after_loss": 15}, "direction": "LONG_ONLY"}""")

cfg = yaml.safe_load(open("config.yaml"))
spec, notes = strat.clamp(V3, cfg)
st = Store()
nv = st.next_version()
st.save_strategy(nv, spec["name"], spec, spec["rationale"],
                 {"mode": "v3_relaxed"}, clock.now().isoformat(timespec="seconds"))
st.log(clock.now().isoformat(timespec="seconds"), "STRATEGY",
       "Installed v%d: %s" % (nv, spec["name"]),
       spec["rationale"][:300] + ((" | clamps: %s" % notes) if notes else ""))
print("Installed and activated v%d: %s" % (nv, spec["name"]))
