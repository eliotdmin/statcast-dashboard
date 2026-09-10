#!/usr/bin/env python3
"""Does repeat-beats-change survive a within-pitcher design? All pitchers, 2023-2025.

The league-level result (repeating a pitch beats changing by 0.58 runs/100) pools
across pitchers, so it is open to exactly the confound that just destroyed the
2-2 finding: pitchers who repeat more may simply be better pitchers. This runs
the same estimate WITHIN pitcher -- each pitcher against himself, in the same
count -- and then asks whether a pitcher's own gap persists across seasons.
"""
import json, math, sqlite3
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).parent / "output" / "repeat_within.json"
MIN = 60

con = sqlite3.connect(f"file:{Path(__file__).parent}/../../snap.db?mode=ro", uri=True)
import sys
if len(sys.argv) > 1:
    con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
con.execute("PRAGMA cache_size=-300000")

rows = con.execute("""
    SELECT p.pitcher, p.game_year, p.balls || '-' || p.strikes,
           CASE WHEN prev.pitch_type = p.pitch_type THEN 'R' ELSE 'C' END,
           COUNT(*), SUM(p.delta_run_exp), SUM(p.delta_run_exp*p.delta_run_exp)
    FROM pitches p
    JOIN pitches prev ON prev.game_pk=p.game_pk AND prev.at_bat_number=p.at_bat_number
         AND prev.pitch_number = p.pitch_number - 1
    WHERE p.game_year IN (2023,2024,2025) AND p.game_type='R'
      AND p.pitch_type IS NOT NULL AND prev.pitch_type IS NOT NULL
      AND p.delta_run_exp IS NOT NULL AND p.balls<=3 AND p.strikes<=2
    GROUP BY 1,2,3,4""").fetchall()

cell = defaultdict(dict)
for pid, yr, cnt, k, n, rv, ss in rows:
    cell[(pid, yr, cnt)][k] = (n, -rv, ss)

def gaps(years):
    acc = defaultdict(lambda: defaultdict(lambda: [0, 0.0, 0.0]))
    for (pid, yr, cnt), g in cell.items():
        if yr not in years or "R" not in g or "C" not in g: continue
        if g["R"][0] < MIN or g["C"][0] < MIN: continue
        for k in "RC":
            n, rv, ss = g[k]; a = acc[pid][k]
            a[0] += n; a[1] += rv; a[2] += ss
    out = {}
    for pid, g in acc.items():
        if "R" not in g or "C" not in g: continue
        s = {}
        for k in "RC":
            n, rv, ss = g[k]; m = rv / n
            s[k] = (n, 100 * m, 100 * math.sqrt(max(ss/n - m*m, 0)/n))
        out[pid] = {"gap": s["R"][1] - s["C"][1], "se": math.hypot(s["R"][2], s["C"][2]),
                    "n": min(s["R"][0], s["C"][0]),
                    "rate": s["R"][0]/(s["R"][0]+s["C"][0])}
    return out

g = gaps({2023, 2024, 2025})
w = [v["n"] for v in g.values()]; W = sum(w)
m = sum(v["gap"]*v["n"] for v in g.values())/W
se = math.sqrt(sum((v["n"]/W)**2 * v["se"]**2 for v in g.values()))
print(f"WITHIN-PITCHER repeat minus change, 2023-2025")
print(f"  {len(g)} pitchers   gap {m:+.3f}  95% [{m-1.96*se:+.3f}, {m+1.96*se:+.3f}]")
print(f"  mean repeat rate {100*sum(v['rate']*v['n'] for v in g.values())/W:.1f}%")

a, b = gaps({2023, 2024}), gaps({2025})
ids = [k for k in a if k in b]
x = [a[k]["gap"] for k in ids]; y = [b[k]["gap"] for k in ids]
n = len(ids); mx, my = sum(x)/n, sum(y)/n
sx = math.sqrt(sum((v-mx)**2 for v in x)); sy = math.sqrt(sum((v-my)**2 for v in y))
r = sum((p-mx)*(q-my) for p, q in zip(x, y))/(sx*sy)
z = 0.5*math.log((1+r)/(1-r)); s = 1/math.sqrt(n-3)
lo, hi = math.tanh(z-1.96*s), math.tanh(z+1.96*s)
print(f"\nPERSISTENCE  fit 2023-24 -> test 2025")
print(f"  {n} pitchers   r {r:+.3f}  95% [{lo:+.3f}, {hi:+.3f}]  "
      f"{'persists' if lo>0 else 'no evidence'}")

OUT.write_text(json.dumps({"n_pitchers": len(g), "gap": m, "se": se,
                           "persistence": {"n": n, "r": r, "ci": [lo, hi]}}, indent=1))
print(f"\nwrote {OUT}")
