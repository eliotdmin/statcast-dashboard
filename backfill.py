#!/usr/bin/env python3
"""Multi-season Statcast backfill.

    python3 backfill.py --years 2023 2024 2025 2026

Fetches pitch-level data one day at a time for each season, plus that season's
final expected-stats and batted-ball leaderboards. Every day is recorded in
`ingest_log`, so the run is fully resumable: kill it, re-run it, and it picks up
exactly where it stopped without re-downloading anything.

Ordering is oldest season first by default. That is deliberate -- the current
season is already partly loaded, so the missing history is what a resumed run
should be buying you. Use --newest-first to invert it.

Baseball Savant is a public courtesy endpoint. Default sleep is 2.5s between
day requests; raise it, don't lower it, if you start seeing failures.
"""
import argparse
import sys
import time
from datetime import datetime, timezone

import db
import fetch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025, 2026])
    ap.add_argument("--sleep", type=float, default=2.5)
    ap.add_argument("--limit-days", type=int, default=None,
                    help="stop after N days per season (smoke test)")
    ap.add_argument("--include-postseason", action="store_true")
    ap.add_argument("--skip-leaderboards", action="store_true")
    ap.add_argument("--newest-first", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan and exit without touching the network")
    args = ap.parse_args()

    con = db.connect()
    have = db.days_already_ingested(con, "pitches")

    plan = []
    for y in args.years:
        days = fetch.season_days(y, include_postseason=args.include_postseason)
        plan.append((y, len(days), len([d for d in days if d not in have])))

    todo_total = sum(p[2] for p in plan)
    print("=" * 62)
    print(f"BACKFILL PLAN   started {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    for y, n, todo in plan:
        print(f"  {y}: {todo:>4} of {n:>4} days to fetch")
    est = todo_total * (args.sleep + 9) / 3600
    print(f"  total: {todo_total} day-requests, rough ETA {est:.1f} h")
    print("=" * 62, flush=True)
    if args.dry_run:
        return 0

    years = sorted(args.years, reverse=args.newest_first)
    for y in years:
        print(f"\n### {y} ###", flush=True)
        if not args.skip_leaderboards:
            try:
                fetch.fetch_expected_stats(con, y)
                fetch.fetch_batted_ball(con, y)
            except Exception as e:
                print(f"  ! leaderboards[{y}] failed: {type(e).__name__}: {e}", flush=True)
        t0 = time.time()
        fetch.fetch_pitches(con, y, sleep=args.sleep,
                            limit_days=args.limit_days,
                            include_postseason=args.include_postseason)
        n = con.execute("SELECT COUNT(*) FROM pitches WHERE game_year=?", (y,)).fetchone()[0]
        print(f"### {y} done in {(time.time()-t0)/60:.1f} min -- {n:,} pitches stored", flush=True)

    total = con.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]
    print(f"\nBACKFILL COMPLETE -- {total:,} pitches total", flush=True)


if __name__ == "__main__":
    sys.exit(main())
