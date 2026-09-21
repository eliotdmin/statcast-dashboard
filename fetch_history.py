#!/usr/bin/env python3
"""fetch_history.py -- pull prior seasons' wOBA/xwOBA for the site's "usual level" baseline.

    python3 fetch_history.py                    # 2015-2022, then rebuild web/data/history.json
    python3 fetch_history.py --years 2021 2022  # just some seasons

Run on the Mac, not the sandbox: it fetches from Savant and writes the database (CLAUDE.md).
One season-level expected-stats leaderboard per season and player type -- 16 small requests for
2015-2022, a few minutes -- not the pitch-level backfill. 2015 is the first Statcast season with
xwOBA. 2020 was 60 games; it enters with its actual (small) plate-appearance weight.
"""
import argparse, time
import db, fetch, history

ap = argparse.ArgumentParser()
ap.add_argument("--years", type=int, nargs="+", default=list(range(2015, 2023)))
ap.add_argument("--sleep", type=float, default=3.0)
args = ap.parse_args()

con = db.connect()
for y in args.years:
    print(f"{y}:")
    fetch.fetch_expected_stats(con, y, min_pa=1)
    time.sleep(args.sleep)
con.close()
history.main()
print("\nNext: re-deploy web/ so the site picks up the new history.json.")
