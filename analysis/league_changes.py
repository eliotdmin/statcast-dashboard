#!/usr/bin/env python3
"""How much do players actually change year to year? Calibrating "a lot".

    python3 league_changes.py --db data/statcast.db

A change can clear its error bar and still be ordinary. The question "is +.040
wOBA a big move?" is not answered by a standard error -- it is answered by the
league-wide distribution of year-over-year changes.

THE DECOMPOSITION THAT MAKES THIS HONEST. The observed spread of changes is not
the real spread, because every measured change carries sampling noise:

    var(observed change) = var(true change) + var(noise)

so   sd(true change) = sqrt( max( var(observed) - mean(se^2), 0 ) )

That matters enormously. For a metric where most observed movement is noise, a
change in the 90th percentile of the OBSERVED distribution may be an ordinary
true change that got a lucky sample. Reporting both columns keeps the two apart,
and the ratio of the two is a reliability measure for CHANGE specifically --
which is what the dashboard actually cares about, and is not the same thing as
the reliability of a level.
"""
import argparse, json, math, sqlite3
from pathlib import Path
import numpy as np

SWING = "(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
WHIFF = "(description LIKE 'swinging_strike%' OR description='foul_tip')"

Q = f"""
SELECT batter, game_year, SUM(woba_denom) pa,
  SUM(CASE WHEN woba_denom=1 THEN woba_value END) wn,
  SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END) xn,
  SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
  SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END) bb,
  COUNT(*) pit, SUM(CASE WHEN {SWING} THEN 1 ELSE 0 END) sw,
  SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END) oz,
  SUM(CASE WHEN zone>=11 AND {SWING} THEN 1 ELSE 0 END) ozsw,
  SUM(CASE WHEN {SWING} AND {WHIFF} THEN 1 ELSE 0 END) wh,
  SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END) nbs,
  SUM(bat_speed) sbs, SUM(bat_speed*bat_speed) ssbs,
  SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END) nev,
  SUM(CASE WHEN type='X' THEN launch_speed END) sev,
  SUM(CASE WHEN type='X' THEN launch_speed*launch_speed END) ssev,
  SUM(CASE WHEN type='X' AND launch_speed>=95 THEN 1 ELSE 0 END) hh,
  SUM(CASE WHEN type='X' AND launch_speed_angle=6 THEN 1 ELSE 0 END) brl,
  SUM(CASE WHEN bb_type='ground_ball' THEN 1 ELSE 0 END) gb,
  SUM(CASE WHEN bb_type IS NOT NULL THEN 1 ELSE 0 END) bipt
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R'
GROUP BY 1,2 HAVING pa >= 250"""


def rate(n, d):
    if not d: return None, None
    p = n / d
    return 100*p, 100*math.sqrt(max(p*(1-p), 0)/d)


def mean(s, ss, n):
    if not n: return None, None
    m = s/n
    return m, math.sqrt(max(ss/n - m*m, 0)/n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent/"data"/"statcast.db"))
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-400000")

    raw = {}
    for r in con.execute(Q):
        raw.setdefault(r[0], {})[r[1]] = r

    def metrics(r):
        (_, _, pa, wn, xn, k, bb, pit, sw, oz, ozsw, wh, nbs, sbs, ssbs,
         nev, sev, ssev, hh, brl, gb, bipt) = r
        return {
          "wOBA": (wn/pa, 0.30/math.sqrt(pa)),
          "xwOBA": (xn/pa, 0.22/math.sqrt(pa)),
          "K%": rate(k, pa), "BB%": rate(bb, pa),
          "swing%": rate(sw, pit), "chase%": rate(ozsw, oz), "whiff/sw%": rate(wh, sw),
          "bat speed": mean(sbs, ssbs, nbs), "exit velo": mean(sev, ssev, nev),
          "hard-hit%": rate(hh, nev), "barrel%": rate(brl, nev), "GB%": rate(gb, bipt),
        }

    ch = {}
    for pid, yrs in raw.items():
        if 2025 not in yrs or 2026 not in yrs: continue
        A, B = metrics(yrs[2025]), metrics(yrs[2026])
        for k in A:
            if A[k][0] is None or B[k][0] is None: continue
            ch.setdefault(k, []).append((B[k][0]-A[k][0], math.hypot(A[k][1], B[k][1])))

    print(f"{len(set(raw)&set(p for p in raw if 2025 in raw[p] and 2026 in raw[p]))} hitters "
          f"with 250+ PA in both seasons\n")
    print(f"{'metric':12s} {'n':>4} {'sd obs':>8} {'sd noise':>9} {'sd TRUE':>8} "
          f"{'true/obs':>9} {'p90 true':>9}")
    print("-"*68)
    rep = {}
    for k, v in ch.items():
        d = np.array([x[0] for x in v]); se = np.array([x[1] for x in v])
        var_obs = d.var(ddof=1); var_noise = (se**2).mean()
        var_true = max(var_obs - var_noise, 0)
        sd_t = math.sqrt(var_true)
        ratio = var_true/var_obs if var_obs else 0
        p90 = 1.2816*sd_t          # 90th pct of a normal centred at 0
        rep[k] = {"n": len(v), "sd_obs": math.sqrt(var_obs), "sd_noise": math.sqrt(var_noise),
                  "sd_true": sd_t, "signal_share": ratio, "p90_true": p90}
        f = "{:>8.4f}" if k in ("wOBA", "xwOBA") else "{:>8.2f}"
        print(f"{k:12s} {len(v):>4} " + f.format(math.sqrt(var_obs)) + " " +
              f.format(math.sqrt(var_noise)).rjust(9) + " " + f.format(sd_t) +
              f" {100*ratio:>8.0f}% " + f.format(p90).rjust(9))

    Path("output").mkdir(exist_ok=True)
    Path("output/league_changes.json").write_text(json.dumps(rep, indent=1))
    print("\nsd TRUE is the real spread of year-over-year change once sampling noise is removed.")
    print("true/obs is how much of the observed movement in that metric is real.")
    print("p90 true = the change a player must make to sit at the 90th percentile of real movers.")
    print("\nwrote output/league_changes.json")


if __name__ == "__main__":
    main()
