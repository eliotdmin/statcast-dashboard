#!/usr/bin/env python3
"""Does the luck gap predict anything? An out-of-sample test with the
artifacts controlled for.

  python3 regression_test.py --year 2026 --windows 15 30 45 60

WHY THIS VERSION EXISTS
-----------------------
A naive version of this test regressed (wOBA2 - wOBA1) on (xwOBA1 - wOBA1) and
reported a slope near 1.0, which looks like "the luck gap closes completely."
That number is largely an ARTIFACT. Both sides of that regression contain
-wOBA1, so noise in wOBA1 enters the predictor and the outcome with the same
sign and manufactures a positive slope even when xwOBA carries zero information.
This is mathematical coupling, and it is the classic way regression-to-the-mean
studies fool themselves.

Three controls are applied here instead:

1. PARTIAL REGRESSION. Fit  wOBA2 ~ wOBA1 + xwOBA1  on standardized inputs.
   The coefficient on xwOBA1 is its contribution AFTER wOBA1 is already
   accounted for. If contact quality only repeats what the results said, this
   lands near zero. Nothing here is coupled, because wOBA2 shares no term with
   either predictor.

2. PERMUTATION NULL. Shuffle xwOBA1 across players within each block and re-run
   everything. This measures what the coupled statistic produces from pure
   noise, and gives an empirical p-value rather than a story.

3. BOOTSTRAP INTERVAL. Resample players with replacement to put a 95% interval
   on the correlation difference, so a "winner" has to actually clear zero
   rather than merely have a larger point estimate.

A verdict is only declared when the bootstrap interval excludes zero. Otherwise
the honest answer is "not enough evidence," and it says so.

REMAINING LIMITS THIS STILL CANNOT FIX
--------------------------------------
* Survivorship: benched players vanish from period 2, biasing the sample toward
  players who stayed good.
* RMSE comparisons still favor xwOBA slightly by construction - it is a smoothed
  quantity with less spread, which flatters it against a mean-reverting target.
  Read the correlations and the partial beta, not the RMSE.
* Adjacent blocks share true talent, so neither predictor isolates luck.
* Block pairs are non-overlapping but not independent across window lengths.
"""
import argparse
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

import analyze
import db

RNG = np.random.default_rng(20260829)


def blocks(con, W):
    row = con.execute("SELECT MIN(game_date), MAX(game_date) FROM pitches").fetchone()
    if not row or not row[0]:
        return []
    lo = datetime.strptime(row[0], "%Y-%m-%d").date()
    hi = datetime.strptime(row[1], "%Y-%m-%d").date()
    out, cur = [], lo
    while cur + timedelta(days=2 * W) <= hi + timedelta(days=1):
        out.append((cur, cur + timedelta(days=W), cur + timedelta(days=2 * W)))
        cur += timedelta(days=W)          # sliding start, disjoint halves within a pair
    return out


def agg(df, a, b):
    m = (df.game_date >= a.isoformat()) & (df.game_date < b.isoformat())
    d = df[m]
    if d.empty:
        return pd.DataFrame()
    return (d.groupby("pid")
              .agg(pa=("woba_pa", "size"), woba=("woba_pa", "mean"),
                   xwoba=("xwoba_pa", "mean"))
              .reset_index())


def z(v):
    s = v.std(ddof=1)
    return (v - v.mean()) / s if s > 0 else v * 0.0


def ols(y, X):
    """Least squares with intercept; returns coefficients after the intercept."""
    A = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return beta[1:]


def stats_for(M):
    """All statistics for one assembled set of (period1, period2) player rows."""
    w1, x1, w2 = M.woba_1.values, M.xwoba_1.values, M.woba_2.values
    r_w = np.corrcoef(w1, w2)[0, 1]
    r_x = np.corrcoef(x1, w2)[0, 1]
    # Partial contribution of xwOBA after wOBA is already in the model.
    b_partial = ols(z(pd.Series(w2)).values,
                    np.column_stack([z(pd.Series(w1)).values, z(pd.Series(x1)).values]))[1]
    # The coupled statistic, kept only so it can be compared to its own null.
    b_coupled = ols(w2 - w1, (x1 - w1).reshape(-1, 1))[0]
    return dict(r_w=r_w, r_x=r_x, dr=r_x - r_w, b_partial=b_partial,
                b_coupled=b_coupled,
                rmse_w=float(np.sqrt(np.mean((w1 - w2) ** 2))),
                rmse_x=float(np.sqrt(np.mean((x1 - w2) ** 2))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--windows", type=int, nargs="+", default=[15, 30, 45, 60])
    ap.add_argument("--min-pa", type=int, default=40)
    ap.add_argument("--role", default="batter", choices=["batter", "pitcher"])
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--perm", type=int, default=500)
    ap.add_argument("--db", default=None,
                    help="path to a database file; use a scratch copy rather than "
                         "the live one when the pipeline may be running")
    args = ap.parse_args()

    if args.db:
        db.DB_PATH = __import__("pathlib").Path(args.db)
    con = db.connect()
    n = con.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]
    if n == 0:
        print("The pitches table is empty. Run the backfill first."); return

    ids = [r[0] for r in con.execute(
        f"SELECT {args.role}, COUNT(*) c FROM pitches WHERE woba_denom=1 "
        f"GROUP BY {args.role} HAVING c >= ?", (args.min_pa * 2,)).fetchall()]
    df = analyze.pa_level(con, ids, role=args.role, year=args.year)
    span = con.execute("SELECT MIN(game_date), MAX(game_date) FROM pitches").fetchone()
    print(f"{len(ids)} {args.role}s · {n:,} pitch rows · {span[0]} to {span[1]}\n")
    if df.empty:
        print("No PA-level rows."); return

    print(f"{'win':>4} {'blk':>4} {'n':>5} | {'r(wOBA)':>8} {'r(xwOBA)':>9} "
          f"{'Δr [95% CI]':>22} | {'β partial':>10} {'[95% CI]':>16} | "
          f"{'b coupled':>10} {'null':>13} | verdict")
    print("-" * 128)

    for W in args.windows:
        rows = []
        for (a, b, c) in blocks(con, W):
            p1, p2 = agg(df, a, b), agg(df, b, c)
            if p1.empty or p2.empty:
                continue
            m = p1.merge(p2, on="pid", suffixes=("_1", "_2"))
            m = m[(m.pa_1 >= args.min_pa) & (m.pa_2 >= args.min_pa)]
            if len(m) >= 20:
                m = m.assign(_blk=f"{a}")
                rows.append(m)
        if not rows:
            print(f"{W:>4} {'-':>4} {'-':>5} | (not enough paired blocks — backfill more days)")
            continue

        M = pd.concat(rows, ignore_index=True)
        S = stats_for(M)

        # bootstrap over players
        drs, bps = [], []
        idx = np.arange(len(M))
        for _ in range(args.boot):
            s = M.iloc[RNG.choice(idx, len(idx), replace=True)]
            if s.woba_1.std() == 0 or s.xwoba_1.std() == 0:
                continue
            t = stats_for(s)
            drs.append(t["dr"]); bps.append(t["b_partial"])
        dr_lo, dr_hi = np.percentile(drs, [2.5, 97.5]) if drs else (np.nan, np.nan)
        bp_lo, bp_hi = np.percentile(bps, [2.5, 97.5]) if bps else (np.nan, np.nan)

        # permutation null for the coupled slope: shuffle xwOBA within block
        nulls = []
        for _ in range(args.perm):
            sh = M.copy()
            sh["xwoba_1"] = (sh.groupby("_blk").xwoba_1
                               .transform(lambda v: RNG.permutation(v.values)))
            nulls.append(stats_for(sh)["b_coupled"])
        null_mean = float(np.mean(nulls))
        null_hi = float(np.percentile(nulls, 97.5))

        if np.isnan(dr_lo):
            verdict = "inconclusive"
        elif dr_lo > 0:
            verdict = "xwOBA wins"
        elif dr_hi < 0:
            verdict = "wOBA wins"
        else:
            verdict = "no evidence"
        if len(rows) < 3:
            verdict += f" (only {len(rows)} blk)"

        print(f"{W:>4} {len(rows):>4} {len(M):>5} | {S['r_w']:>8.3f} {S['r_x']:>9.3f} "
              f"{('%+.3f [%+.3f,%+.3f]' % (S['dr'], dr_lo, dr_hi)):>22} | "
              f"{S['b_partial']:>10.3f} {('[%+.2f,%+.2f]' % (bp_lo, bp_hi)):>16} | "
              f"{S['b_coupled']:>10.3f} {('%.2f (null)' % null_mean):>13} | {verdict}")

    print("""
HOW TO READ THIS

  Δr        r(xwOBA→future) minus r(wOBA→future). Positive means contact quality
            beat results. It only counts if the 95% interval excludes zero.

  β partial Standardized coefficient on xwOBA1 in  wOBA2 ~ wOBA1 + xwOBA1.
            This is the honest measure: what xwOBA adds ON TOP OF what the
            player's own results already told you. Free of mathematical coupling.
            Near zero = xwOBA is just restating wOBA.

  b coupled The naive regression-to-mean slope, shown ONLY beside its
            permutation null. If b ≈ null, the slope is an artifact of the
            shared -wOBA1 term, not evidence of regression. Compare the two
            numbers; never read b on its own.

  RMSE is deliberately omitted: xwOBA is smoother than wOBA, so it wins on RMSE
  against a mean-reverting target regardless of whether it carries more signal.

  Blocks now slide by W (not 2W), so a season yields more pairs. Halves within
  a pair never overlap, but pairs overlap each other — treat block count as an
  optimistic sample size, and prefer window rows with 4+ blocks.
""")


if __name__ == "__main__":
    main()
