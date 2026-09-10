#!/usr/bin/env python3
"""Should a pitcher throw fewer fastballs in 2-2? A within-pitcher, out-of-sample test.

    python3 count_choice.py --db data/statcast.db

PRE-SPECIFIED BEFORE LOOKING (see FINDINGS.md):
  H1  Within a pitcher, offspeed outperforms his own fastball in 2-2 counts.
  H2  The size of that gap is a persistent property of the pitcher -- his
      2023-2024 gap predicts his 2025 gap.

H1 alone is not actionable. A pooled within-pitcher gap says the average pitcher
would gain by shifting his mix, but it cannot name anyone. H2 is what would make
a per-pitcher recommendation legitimate, and it is testable out of sample, which
is the only real defence against a story fitted to noise.

TWO THINGS THIS DESIGN BUYS

1. WITHIN-PITCHER. Every comparison is a pitcher against himself in the same
   count and season. That removes "pitchers who throw more offspeed are better
   pitchers", which is the confound that makes the league-level number
   uninterpretable as advice.

2. OUT-OF-SAMPLE. The 2023-2024 estimate is fitted; the 2025 estimate is the
   test. A gap that does not repeat is noise no matter how large it looked.

WHAT IT STILL CANNOT DO. Average is not marginal. A pitcher throws the changeup
in 2-2 when he can command it that day, so even a persistent within-pitcher gap
overstates what he would gain by throwing MORE of them -- the marginal changeup
is worse than the average one. A positive result here is a reason to run a real
causal design, not a recommendation on its own.

2026 is excluded: the ABS strike zone changes what a called strike is, and every
count-based metric with it.
"""
import argparse
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).parent / "output" / "count_choice.json"
FB = ("FF", "SI", "FC")
OS = ("SL", "ST", "CU", "KC", "CH", "FS", "SV")
MIN_PER_CELL = 40          # pitches of each group, per pitcher-year-count


def load(con, years):
    y = ",".join(str(i) for i in years)
    q = f"""
        SELECT pitcher, game_year, balls || '-' || strikes AS cnt,
               CASE WHEN pitch_type IN {FB} THEN 'FB'
                    WHEN pitch_type IN {OS} THEN 'OS' END grp,
               COUNT(*), SUM(delta_run_exp), SUM(delta_run_exp*delta_run_exp)
        FROM pitches
        WHERE game_year IN ({y}) AND game_type='R' AND delta_run_exp IS NOT NULL
          AND pitch_type IS NOT NULL AND balls<=3 AND strikes<=2
        GROUP BY 1,2,3,4"""
    d = defaultdict(dict)
    for pid, yr, cnt, grp, n, rv, ss in con.execute(q):
        if grp:
            # negate so positive favours the pitcher
            d[(pid, yr, cnt)][grp] = (n, -rv, ss)
    return d


def gaps(data, years, counts=None):
    """Per pitcher-count: offspeed minus fastball, within pitcher, pooled over years."""
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0.0]))
    for (pid, yr, cnt), g in data.items():
        if yr not in years or (counts and cnt not in counts):
            continue
        if "FB" not in g or "OS" not in g:
            continue
        if g["FB"][0] < MIN_PER_CELL or g["OS"][0] < MIN_PER_CELL:
            continue
        for k in ("FB", "OS"):
            n, rv, ss = g[k]
            a = acc[(pid, cnt)][k]
            a[0] += n; a[1] += rv; a[2] += ss
    out = {}
    for key, g in acc.items():
        if "FB" not in g or "OS" not in g:
            continue
        res = {}
        for k in ("FB", "OS"):
            n, rv, ss = g[k]
            mean = rv / n
            var = max(ss / n - mean * mean, 0)
            res[k] = (n, 100 * mean, 100 * math.sqrt(var / n))
        gap = res["OS"][1] - res["FB"][1]
        se = math.hypot(res["OS"][2], res["FB"][2])
        out[key] = {"gap": gap, "se": se,
                    "n_fb": res["FB"][0], "n_os": res["OS"][0],
                    "fb_share": res["FB"][0] / (res["FB"][0] + res["OS"][0])}
    return out


def wmean(vals, wts):
    W = sum(wts)
    return (sum(v * w for v, w in zip(vals, wts)) / W) if W else None


def pearson(x, y):
    n = len(x)
    if n < 8:
        return None, None, n
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return None, None, n
    r = sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)
    # Fisher z for the interval
    z = 0.5 * math.log((1 + r) / (1 - r)) if abs(r) < 1 else 0.0
    se = 1 / math.sqrt(n - 3)
    lo, hi = (math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se))
    return r, (lo, hi), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent / "data" / "statcast.db"))
    args = ap.parse_args()
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-300000")

    print("loading pitcher-year-count cells...", flush=True)
    data = load(con, [2023, 2024, 2025])

    report = {"min_per_cell": MIN_PER_CELL, "years": [2023, 2024, 2025]}

    # --- H1, and the specificity check across every count
    print("\n=== H1: within-pitcher offspeed minus fastball, by count (2023-2025) ===")
    print(f"{'count':>6} {'pitchers':>9} {'gap':>8} {'95% CI':>18} {'FB share':>9}")
    percount = {}
    all_counts = sorted({c for (_, _, c) in data})
    for cnt in all_counts:
        g = gaps(data, {2023, 2024, 2025}, [cnt])
        if len(g) < 20:
            continue
        vals = [v["gap"] for v in g.values()]
        wts = [min(v["n_fb"], v["n_os"]) for v in g.values()]
        m = wmean(vals, wts)
        # SE of the weighted mean from each pitcher's own SE
        W = sum(wts)
        se = math.sqrt(sum((w / W) ** 2 * v["se"] ** 2 for w, v in zip(wts, g.values())))
        share = wmean([v["fb_share"] for v in g.values()], wts)
        percount[cnt] = {"n_pitchers": len(g), "gap": m, "se": se, "fb_share": share}
        print(f"{cnt:>6} {len(g):>9} {m:>+8.2f} [{m-1.96*se:>+6.2f},{m+1.96*se:>+6.2f}] {100*share:>8.1f}%")
    report["per_count"] = percount

    # --- H2: does a pitcher's gap persist? Fit 2023-24, test 2025.
    print("\n=== H2: does a pitcher's own gap persist? fit 2023-24 -> test 2025 ===")
    print(f"{'count':>6} {'pitchers':>9} {'r':>7} {'95% CI':>18}  verdict")
    persist = {}
    for cnt in all_counts:
        a = gaps(data, {2023, 2024}, [cnt])
        b = gaps(data, {2025}, [cnt])
        pids = [k for k in a if k in b]
        if len(pids) < 15:
            continue
        x = [a[k]["gap"] for k in pids]
        y = [b[k]["gap"] for k in pids]
        r, ci, n = pearson(x, y)
        if r is None:
            continue
        v = "persists" if ci[0] > 0 else ("inverts" if ci[1] < 0 else "no evidence")
        persist[cnt] = {"r": r, "ci": ci, "n": n}
        print(f"{cnt:>6} {n:>9} {r:>+7.3f} [{ci[0]:>+6.3f},{ci[1]:>+6.3f}]  {v}")
    report["persistence"] = persist

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
