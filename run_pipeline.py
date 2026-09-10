#!/usr/bin/env python3
"""Statcast dashboard pipeline.

  python3 run_pipeline.py --year 2026                # normal daily refresh
  python3 run_pipeline.py --year 2026 --skip-pitches # leaderboards only (fast)
  python3 run_pipeline.py --year 2026 --limit-days 5 # first-run smoke test

Writes output/dashboard_data.json, which is what the dashboard renders.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import analyze
import db
import fetch

OUT = Path(__file__).parent / "output" / "dashboard_data.json"
TOP_N = 25


def jsonable(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


def rows(df, cols):
    cols = [c for c in cols if c in df.columns]
    return [{c: jsonable(r[c]) for c in cols} for _, r in df.iterrows()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=datetime.now().year)
    ap.add_argument("--skip-pitches", action="store_true")
    ap.add_argument("--limit-days", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--days-back", type=int, default=None,
                    help="only backfill the most recent N days (resumable; "
                         "extend later by raising or dropping this)")
    ap.add_argument("--newest-first", action="store_true",
                    help="fetch recent days first, so a partial run is useful")
    args = ap.parse_args()

    con = db.connect()

    print("== leaderboards ==")
    fetch.fetch_expected_stats(con, args.year)
    fetch.fetch_batted_ball(con, args.year)
    fetch.fetch_sprint_speed(con, args.year)

    if not args.skip_pitches:
        print("== pitch-level ==")
        fetch.fetch_pitches(con, args.year, sleep=args.sleep,
                            limit_days=args.limit_days,
                            days_back=args.days_back,
                            newest_first=args.newest_first)

    print("== analysis ==")
    sig = analyze.build_signals(con)
    if sig.empty:
        print("No data to analyse - did the leaderboard fetch fail?")
        sys.exit(1)

    cols = ["player_id", "player_name", "player_type", "pa", "bip",
            "ba", "est_ba", "slg", "est_slg", "woba", "est_woba",
            "luck_gap", "luck_z", "outlook", "proj_woba_ros", "proj_vs_current",
            "pct_est_woba", "pct_woba", "pct_ev", "pct_barrel", "pct_hardhit",
            "sprint_speed", "pct_sprint", "luck_gap_adj", "luck_z_adj", "outlook_adj",
            "avg_hit_speed", "brl_percent", "ev95percent", "avg_launch_angle",
            "qualified", "flagged", "direction"]

    payload = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "year": args.year,
               "method": {
                   "min_pa_batter": analyze.MIN_PA_BATTER,
                   "min_pa_pitcher": analyze.MIN_PA_PITCHER,
                   "flag_z": analyze.FLAG_Z,
                   "k_batter": analyze.K_BATTER,
                   "k_pitcher": analyze.K_PITCHER,
                   "speed_coef": analyze.LAST_SPEED_FIT.get("coef"),
                   "speed_r2": analyze.LAST_SPEED_FIT.get("r2"),
                   "speed_n": analyze.LAST_SPEED_FIT.get("n"),
               },
               "groups": {}}

    for kind in ("batter", "pitcher"):
        d = sig[(sig.player_type == kind) & sig.qualified].copy()
        if d.empty:
            continue
        payload["groups"][kind] = {
            "n_qualified": int(len(d)),
            "league_mean_est_woba": jsonable(d.league_mean_est_woba.iloc[0]),
            "breakout":   rows(d.nlargest(TOP_N, "outlook"), cols),
            "regression": rows(d.nsmallest(TOP_N, "outlook"), cols),
            "all":        rows(d.sort_values("est_woba", ascending=False), cols),
        }

    # Trend curves for the flagged players only - keeps the payload small.
    trends = {}
    for kind in ("batter", "pitcher"):
        g = payload["groups"].get(kind)
        if not g:
            continue
        ids = [r["player_id"] for r in (g["breakout"][:10] + g["regression"][:10])
               if r.get("player_id")]
        try:
            trends[kind] = {str(k): v for k, v in
                            analyze.rolling_trends(con, ids, role=kind).items()}
        except Exception as e:
            print(f"  ! trends[{kind}] skipped: {type(e).__name__}: {e}")
    payload["trends"] = trends

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))
    n = sum(g["n_qualified"] for g in payload["groups"].values())
    print(f"\nWrote {OUT}  ({n} qualified players, {OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
