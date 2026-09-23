#!/usr/bin/env python3
"""Month-over-month change for the metrics that can support it, calibrated league-wide.

    python3 monthly.py --db data/statcast.db --team NYM

WHY MONTHLY FOR SOME METRICS AND NOT OTHERS. The stabilisation study says bat
speed is reliable at about ten swings while xwOBA needs 250 plate appearances. A
month gives a regular ~150 swings and ~100 PA. So monthly resolution is real for
the physical measurements and close to pure noise for the outcome measures --
using one window for every metric is the same error as one MIN_PA for every
metric.

Only fast metrics are computed monthly here. Slow ones stay seasonal and are
reported in profiles.py.

HOW SIGNIFICANCE IS JUDGED. Not against zero. Every month-over-month change is
compared against the league-wide distribution of month-over-month changes for
that metric, decomposed into real movement and sampling noise:

    var(observed delta) = var(true delta) + var(noise)

A player's change is then reported three ways: raw, SHRUNK toward zero by that
metric's signal share (which is the best estimate of his true change), and as a
z against the true-change distribution. A raw number alone overstates every move
in a noisy metric.
"""
import argparse, json, math, sqlite3
from collections import defaultdict
from pathlib import Path
import numpy as np

SWING = "(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
WHIFF = "(description LIKE 'swinging_strike%' OR description='foul_tip')"
BAT = "CASE WHEN inning_topbot='Top' THEN away_team ELSE home_team END"
PIT = "CASE WHEN inning_topbot='Top' THEN home_team ELSE away_team END"

HIT = f"""SELECT batter, substr(game_date,1,7) m,
  COUNT(*) pit, SUM(CASE WHEN {SWING} THEN 1 ELSE 0 END) sw,
  SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END) oz,
  SUM(CASE WHEN zone>=11 AND {SWING} THEN 1 ELSE 0 END) ozsw,
  SUM(CASE WHEN {SWING} AND {WHIFF} THEN 1 ELSE 0 END) wh,
  SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END) nbs,
  SUM(bat_speed) sbs, SUM(bat_speed*bat_speed) ssbs,
  SUM(CASE WHEN swing_length IS NOT NULL THEN 1 ELSE 0 END) nsl,
  SUM(swing_length) ssl, SUM(swing_length*swing_length) sssl
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R' {{EXTRA}}
GROUP BY 1,2 HAVING nbs >= 60"""

PITQ = f"""SELECT pitcher, substr(game_date,1,7) m,
  SUM(CASE WHEN pitch_type IN ('FF','SI') AND release_speed IS NOT NULL THEN 1 ELSE 0 END) nv,
  SUM(CASE WHEN pitch_type IN ('FF','SI') THEN release_speed END) sv,
  SUM(CASE WHEN pitch_type IN ('FF','SI') THEN release_speed*release_speed END) ssv,
  SUM(CASE WHEN arm_angle IS NOT NULL THEN 1 ELSE 0 END) naa,
  SUM(arm_angle) saa, SUM(arm_angle*arm_angle) ssaa
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R' {{EXTRA}}
GROUP BY 1,2 HAVING nv >= 80"""


def mean(s, ss, n):
    if not n: return None, None
    m = s/n
    return m, math.sqrt(max(ss/n-m*m, 0)/n)


def rate(n, d):
    if not d: return None, None
    p = n/d
    return 100*p, 100*math.sqrt(max(p*(1-p), 0)/d)


def hit_metrics(r):
    _, _, pit, sw, oz, ozsw, wh, nbs, sbs, ssbs, nsl, ssl, sssl = r
    return {"bat speed": mean(sbs, ssbs, nbs), "swing length": mean(ssl, sssl, nsl),
            "swing%": rate(sw, pit), "chase%": rate(ozsw, oz), "whiff/sw%": rate(wh, sw)}


def pit_metrics(r):
    _, _, nv, sv, ssv, naa, saa, ssaa = r
    return {"fastball velo": mean(sv, ssv, nv), "arm angle": mean(saa, ssaa, naa)}


def decompose(deltas):
    """{metric: [(d, se)]} -> {metric: {sd_true, signal_share, ...}}"""
    out = {}
    for k, v in deltas.items():
        if len(v) < 40: continue
        d = np.array([x[0] for x in v]); se = np.array([x[1] for x in v])
        vo = d.var(ddof=1); vn = (se**2).mean()
        vt = max(vo - vn, 0)
        out[k] = {"n": len(v), "sd_obs": math.sqrt(vo), "sd_noise": math.sqrt(vn),
                  "sd_true": math.sqrt(vt), "share": vt/vo if vo else 0}
    return out


def series(con, q, mfn, team=None):
    sql = q.replace("{EXTRA}", f"AND {BAT if 'batter' in q else PIT}=?" if team else "")
    rows = con.execute(sql, (team,) if team else ()).fetchall()
    by = defaultdict(dict)
    for r in rows:
        by[r[0]][r[1]] = mfn(r)
    return by


def month_deltas(by):
    out = defaultdict(list)
    for pid, months in by.items():
        ms = sorted(months)
        for a, b in zip(ms, ms[1:]):
            if a[:4] != b[:4]:      # skip the offseason gap: Sep -> Apr is not a month
                continue
            for k in months[a]:
                x, y = months[a][k], months[b][k]
                if x[0] is None or y[0] is None: continue
                out[k].append((y[0]-x[0], math.hypot(x[1], y[1])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent/"data"/"statcast.db"))
    ap.add_argument("--team", default="NYM")
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-400000")

    print("=== league: how much do these move month to month? ===")
    lg = {}
    for label, q, fn in (("hitters", HIT, hit_metrics), ("pitchers", PITQ, pit_metrics)):
        d = decompose(month_deltas(series(con, q, fn)))
        lg.update(d)
        for k, v in d.items():
            print(f"  {k:14s} n={v['n']:>5,}  sd obs {v['sd_obs']:>6.2f}  "
                  f"noise {v['sd_noise']:>6.2f}  TRUE {v['sd_true']:>6.2f}  "
                  f"signal {100*v['share']:>3.0f}%")

    bn = dict(con.execute("SELECT player_id, player_name FROM expected_stats WHERE player_type='batter'"))
    pn = dict(con.execute("SELECT player_id, player_name FROM expected_stats WHERE player_type='pitcher'"))
    report = {"league": lg, "players": {}}

    for label, q, fn, names in (("HITTERS", HIT, hit_metrics, bn), ("PITCHERS", PITQ, pit_metrics, pn)):
        print(f"\n=== {a.team} {label}: month-over-month moves that beat the league distribution ===")
        by = series(con, q, fn, a.team)
        for pid, months in by.items():
            ms = sorted(months)
            if len(ms) < 4: continue
            hits = []
            for x, y in zip(ms, ms[1:]):
                if x[:4] != y[:4]:  # same: never call an offseason jump a monthly change
                    continue
                for k in months[x]:
                    A, B = months[x][k], months[y][k]
                    if A[0] is None or B[0] is None or k not in lg: continue
                    d = B[0]-A[0]; se = math.hypot(A[1], B[1])
                    vt = lg[k]["sd_true"]**2
                    shrunk = d * vt/(vt+se*se) if vt+se*se else 0
                    z = shrunk/lg[k]["sd_true"] if lg[k]["sd_true"] else 0
                    if abs(z) >= 1.5:
                        hits.append((abs(z), f"    {x}->{y}  {k:14s} "
                                     f"{A[0]:>7.2f}->{B[0]:>7.2f}  raw {d:>+6.2f}  "
                                     f"shrunk {shrunk:>+6.2f}  z {z:>+5.2f}"))
            if hits:
                print(f"  {names.get(pid, pid)}  ({len(ms)} months)")
                for _, line in sorted(hits, reverse=True)[:5]:
                    print(line)
        report["players"][label] = True

    Path("output").mkdir(exist_ok=True)
    Path("output/monthly.json").write_text(json.dumps(report, indent=1, default=float))
    print("\nz is against the TRUE month-over-month change distribution, after shrinking the")
    print("raw change by that metric's signal share. |z| >= 1.5 shown.")
    print("wrote output/monthly.json")


if __name__ == "__main__":
    main()
