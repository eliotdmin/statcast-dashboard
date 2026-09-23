#!/usr/bin/env python3
"""Did catcher framing collapse when ABS arrived in 2026?

    python3 abs_framing.py --db data/statcast.db

PRE-SPECIFIED: if the strike zone became automated in 2026, the spread BETWEEN
catchers in extra strikes gained should collapse toward zero. A catcher cannot
frame a call a machine makes.

THE TRAP THIS AVOIDS. sz_top/sz_bot cannot be the yardstick, because those
columns are themselves what changed -- operator-set through 2025, ABS-derived
after. Measuring "distance from the zone" with them would confound the rule
change with the ruler change. So the zone here is a FIXED geometric box,
identical in every season: |plate_x| <= 0.83 ft (half of a 17-inch plate plus a
ball) and 1.5 <= plate_z <= 3.5 ft.

EXPECTED CALLED-STRIKE RATE is computed WITHIN each season, per location bucket,
count and batter side. That deliberately absorbs any season-level shift in the
zone's size or shape -- the question is not whether the zone moved, it is whether
catchers still differ from each other. Framing is by definition a between-catcher
effect, so the between-catcher spread is the right statistic.

Reported as extra strikes per 1000 taken pitches rather than runs, so no run
conversion has to be assumed.
"""
import argparse, json, math, sqlite3
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).parent / "output" / "abs_framing.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent / "data" / "statcast.db"))
    ap.add_argument("--min", type=int, default=1500, help="taken pitches per catcher-season")
    args = ap.parse_args()
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-400000")

    # 0.1 ft location buckets on a fixed grid, plus count state and batter side.
    rows = con.execute("""
        SELECT game_year,
               CAST(ROUND(plate_x*10) AS INT), CAST(ROUND(plate_z*10) AS INT),
               balls, strikes, stand, fielder_2,
               SUM(CASE WHEN description='called_strike' THEN 1 ELSE 0 END),
               COUNT(*)
        FROM pitches
        WHERE game_type='R' AND description IN ('called_strike','ball')
          AND plate_x IS NOT NULL AND plate_z IS NOT NULL AND fielder_2 IS NOT NULL
          AND ABS(plate_x) < 2.0 AND plate_z BETWEEN 0.5 AND 4.5
          AND balls<=3 AND strikes<=2
        GROUP BY 1,2,3,4,5,6,7""").fetchall()

    # expected = that season's own strike rate for the identical bucket
    tot = defaultdict(lambda: [0, 0])
    for yr, bx, bz, b, s, st, _c, k, n in rows:
        t = tot[(yr, bx, bz, b, s, st)]; t[0] += k; t[1] += n

    per = defaultdict(lambda: [0.0, 0.0, 0])       # extra strikes, expected, n
    for yr, bx, bz, b, s, st, cat, k, n in rows:
        K, N = tot[(yr, bx, bz, b, s, st)]
        if N < 25:                                  # too thin to estimate a rate
            continue
        exp = n * (K / N)
        p = per[(yr, cat)]
        p[0] += k - exp; p[1] += exp; p[2] += n

    byyear = defaultdict(list)
    for (yr, cat), (extra, exp, n) in per.items():
        if n >= args.min:
            byyear[yr].append({"catcher": cat, "n": n, "per1000": 1000 * extra / n})

    report = {}
    print(f"{'season':>7} {'catchers':>9} {'sd':>7} {'best':>8} {'worst':>8} {'range':>8} "
          f"{'mean |x|':>9}")
    print("-" * 62)
    for yr in sorted(byyear):
        v = sorted(x["per1000"] for x in byyear[yr])
        m = sum(v) / len(v)
        sd = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
        report[yr] = {"n_catchers": len(v), "sd": sd, "best": v[-1], "worst": v[0],
                      "range": v[-1] - v[0],
                      "mean_abs": sum(abs(x - m) for x in v) / len(v)}
        print(f"{yr:>7} {len(v):>9} {sd:>7.2f} {v[-1]:>+8.2f} {v[0]:>+8.2f} "
              f"{v[-1]-v[0]:>8.2f} {report[yr]['mean_abs']:>9.2f}")

    yrs = sorted(report)
    if 2026 in report and len(yrs) > 1:
        pre = [report[y]["sd"] for y in yrs if y < 2026]
        drop = 100 * (1 - report[2026]["sd"] / (sum(pre) / len(pre)))
        print(f"\n2026 between-catcher SD is {drop:+.0f}% versus the 2023-2025 average")
        report["collapse_pct"] = drop

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({str(k): v for k, v in report.items()}, indent=1))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
