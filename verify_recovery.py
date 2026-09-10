#!/usr/bin/env python3
"""Verify a recovered database against ingest_log, and queue bad days for refetch.

    python3 verify_recovery.py --db data/statcast_recovered.db          # report
    python3 verify_recovery.py --db data/statcast_recovered.db --fix    # queue refetch

`ingest_log` records the row count Savant returned for every day at fetch time.
That makes it a checksum the database carries with it: any day whose stored rows
no longer match its logged count lost data. With --fix, those days are deleted
from both tables so `backfill.py` re-fetches exactly them and nothing else.

RUN THIS ON THE MAC, not through the Cowork mount -- writing to a large SQLite
file over the mount is what damaged the database in the first place.
"""
import argparse
import sqlite3
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--fix", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    print("integrity:", con.execute("PRAGMA quick_check(5)").fetchone()[0][:200])

    logged = dict(con.execute(
        "SELECT day, rows FROM ingest_log WHERE scope='pitches'").fetchall())
    stored = dict(con.execute(
        "SELECT game_date, COUNT(*) FROM pitches GROUP BY 1").fetchall())

    bad, missing, ok = [], [], 0
    for day, n in sorted(logged.items()):
        have = stored.get(day, 0)
        if n == 0:
            ok += 1                     # genuine off-day
        elif have == n:
            ok += 1
        elif have == 0:
            missing.append((day, n))
        else:
            bad.append((day, n, have))

    orphan = sorted(set(stored) - set(logged))

    print(f"\n{ok} days intact, {len(bad)} short, {len(missing)} empty, {len(orphan)} unlogged")
    lost = sum(n - h for _, n, h in bad) + sum(n for _, n in missing)
    print(f"rows lost: {lost:,} of {sum(logged.values()):,} "
          f"({100.0*lost/max(1,sum(logged.values())):.2f}%)")
    for d, n, h in bad[:15]:
        print(f"  short  {d}  logged {n:,}  stored {h:,}")
    for d, n in missing[:15]:
        print(f"  empty  {d}  logged {n:,}")
    if orphan:
        print(f"  unlogged days present in pitches: {orphan[:10]}")

    if not (bad or missing):
        print("\nNothing to repair.")
        return 0

    if not args.fix:
        print("\nRe-run with --fix to queue these days, then: python3 backfill.py")
        return 1

    days = [d for d, _, _ in bad] + [d for d, _ in missing]
    q = ",".join("?" * len(days))
    con.execute(f"DELETE FROM pitches WHERE game_date IN ({q})", days)
    con.execute(f"DELETE FROM ingest_log WHERE scope='pitches' AND day IN ({q})", days)
    con.commit()
    print(f"\nqueued {len(days)} day(s) for refetch. Now run: python3 backfill.py")
    con.execute("VACUUM")
    return 0


if __name__ == "__main__":
    sys.exit(main())
