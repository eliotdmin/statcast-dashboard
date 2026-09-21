#!/usr/bin/env python3
"""Statcast dashboard pipeline.

  python3 run_pipeline.py --year 2026                 # normal daily refresh
  python3 run_pipeline.py --year 2026 --skip-pitches  # leaderboards only (fast)
  python3 run_pipeline.py --year 2026 --limit-days 5  # first-run smoke test
  python3 run_pipeline.py --year 2026 --skip-views    # data only, no view rebuild

Writes two families of output:

  output/dashboard_data.json   the original dashboard
  output/blocks_all.json       per-half-month block counts, 2023-2026, hitters and
  output/dontchase.json        pitchers -- the inputs to Statcast Reality Check's four
  output/changes.json          tabs and the streak board

The second family used to be built by hand, which meant it silently went stale
the moment the daily job started running without it. It is now part of the
refresh. These steps are NON-FATAL: a failure to rebuild a view is loud in the
log but does not fail the run, because the database and its integrity check are
what the exit code is for.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import analyze
import db
import fetch

HERE = Path(__file__).parent
OUT = HERE / "output" / "dashboard_data.json"
TOP_N = 25

# Scripts that rebuild Statcast Reality Check's inputs, in dependency order:
# streaks.py reads output/blocks_all.json, so blocks_all.py has to go first.
# (label, argv-after-interpreter, file it is expected to write)
VIEW_STEPS = [
    ("blocks",     ["blocks_all.py"],                   "output/blocks_all.json"),
    ("carry board", ["streaks.py", "--part", "wire"],   "output/dontchase.json"),
    ("change log", ["streaks.py", "--part", "changes"], "output/changes.json"),
    # matchup.py reads the per-season shards blocks_all.py publishes into web/data/
    # (a publish step added 2026-09-21; before it, nothing copied them there),
    # so it runs after it. Both player types, all four horizons the tab offers;
    # the whole backtest is about a second.
    # Official season lines for every player on the site (MLB Stats API): the Season line's whole
    # career, and the birth dates matchup.py's Marcel baseline ages with. Needs network, which the
    # scheduled refresh on the Mac has. Runs before matchup.py, which reads it.
    ("career lines", ["fetch_careers.py"], "web/data/careers-bat.json"),
    ("matchup (hitters)",  ["matchup.py", "--kind", "bat"], "web/data/matchup-bat.json"),
    ("matchup (pitchers)", ["matchup.py", "--kind", "pit"], "web/data/matchup-pit.json"),
    # Bootstrapped intervals on the reliabilities the whole site shrinks with.
    # Reads the shards blocks_all.py just wrote, so it runs after them.
    ("reliability (hitters)",  ["reliability.py", "--kind", "bat"], "web/data/reliability-bat.json"),
    ("reliability (pitchers)", ["reliability.py", "--kind", "pit"], "web/data/reliability-pit.json"),
]


def build_views():
    """Regenerate the interactive view's data files. Returns a list of failures.

    Run as subprocesses rather than imported, because each script is written as a
    stand-alone with its own __main__ block and its own argparse; importing them
    would execute module-level work at import time and fight over sys.argv.
    sys.executable keeps them on the same interpreter launchd already resolved --
    the one thing refresh.sh works hardest to get right.
    """
    failures = []
    for label, argv, expect in VIEW_STEPS:
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable] + argv, cwd=HERE,
                               capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            print(f"  ! {label}: timed out after 900s")
            failures.append(label)
            continue
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
            print(f"  ! {label}: exit {r.returncode}")
            for line in tail:
                print(f"      {line}")
            failures.append(label)
            continue
        f = HERE / expect
        if not f.exists():
            print(f"  ! {label}: exited 0 but did not write {expect}")
            failures.append(label)
            continue
        age = time.time() - f.stat().st_mtime
        # A step that succeeds without touching its output file is the failure
        # mode that looks like success in a log, so check the mtime, not just
        # the exit code. This is the same reasoning as the integrity check.
        if age > 3600:
            print(f"  ! {label}: {expect} was not rewritten (mtime {age/3600:.1f}h old)")
            failures.append(label)
            continue
        print(f"  {label}: {expect} {f.stat().st_size/1024:.0f} KB "
              f"in {time.time()-t0:.0f}s")
    return failures


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
    ap.add_argument("--skip-views", action="store_true",
                    help="do not rebuild Statcast Reality Check's data files")
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

    view_failures = []
    if args.skip_views:
        print("== views == skipped (--skip-views)")
    else:
        print("== views ==")
        view_failures = build_views()

    # One scannable line per run, so `grep SUMMARY logs/refresh.log` answers
    # "when did the views last actually rebuild" without reading the whole log.
    status = "ok" if not view_failures else "FAILED: " + ", ".join(view_failures)
    print(f"SUMMARY year={args.year} pitches=ok views={status}")


if __name__ == "__main__":
    main()
