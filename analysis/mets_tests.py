#!/usr/bin/env python3
"""The well-powered Mets hypotheses: within-player change, and how they're pitched."""
import sqlite3, sys, json
from collections import defaultdict
from pathlib import Path
import numpy as np

con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
con.execute("PRAGMA cache_size=-400000")
SWING = "(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
BAT = "CASE WHEN inning_topbot='Top' THEN away_team ELSE home_team END"
PIT = "CASE WHEN inning_topbot='Top' THEN home_team ELSE away_team END"
NAMES = {}
for pid, nm in con.execute("SELECT player_id, player_name FROM expected_stats WHERE player_type='batter'"):
    NAMES[pid] = nm
SOTO = [k for k, v in NAMES.items() if v == "Juan Soto"][0]
VIEN = [k for k, v in NAMES.items() if v == "Mark Vientos"][0]
out = {}

print("=== H3. Is Soto's bat-speed drop situational or global? ===")
print(f"{'strikes':>8} {'2025':>8} {'2026':>8} {'change':>8} {'n25':>7} {'n26':>7}")
r3=[]
for st in (0, 1, 2):
    row = {}
    for yr in (2025, 2026):
        q = con.execute(f"""SELECT COUNT(*), AVG(bat_speed),
            AVG(bat_speed*bat_speed)-AVG(bat_speed)*AVG(bat_speed)
            FROM pitches WHERE batter=? AND game_year=? AND game_type='R'
            AND strikes=? AND {SWING} AND bat_speed IS NOT NULL""", (SOTO, yr, st)).fetchone()
        row[yr] = row.get(yr) or row
        row[yr] = {"n": q[0], "m": q[1], "sd": (max(q[2],0))**.5 if q[2] is not None else 0}
    a, b = row[2025], row[2026]
    d = b["m"] - a["m"]; se = (a["sd"]**2/a["n"] + b["sd"]**2/b["n"])**.5
    print(f"{st:>8} {a['m']:>8.2f} {b['m']:>8.2f} {d:>+8.2f} {a['n']:>7,} {b['n']:>7,}"
          f"  {'real' if abs(d)>1.96*se else ''}")
    r3.append({"strikes": st, "y2025": a["m"], "y2026": b["m"], "d": d, "se": se})
out["soto_by_strikes"] = r3

print("\n=== H1/H2. Vientos: when did bat speed jump, and did swing length follow? ===")
rows = con.execute(f"""SELECT game_date, AVG(bat_speed), AVG(swing_length), COUNT(*)
    FROM pitches WHERE batter=? AND game_year=2026 AND game_type='R'
      AND {SWING} AND bat_speed IS NOT NULL
    GROUP BY game_date ORDER BY game_date""", (VIEN,)).fetchall()
d = [r[0] for r in rows]; bs = np.array([r[1] for r in rows]); sl = np.array([r[2] or 0 for r in rows])
best = None
for i in range(10, len(bs)-10):
    t = (bs[i:].mean()-bs[:i].mean())/ (bs.std()*((1/i+1/(len(bs)-i))**.5) or 1)
    if best is None or abs(t) > abs(best[1]): best = (i, t)
i, t = best
print(f"  {len(rows)} games. strongest split at {d[i]}: "
      f"before {bs[:i].mean():.2f} mph -> after {bs[i:].mean():.2f} mph (t={t:.1f})")
print(f"  swing length across the same split: {sl[:i].mean():.2f} -> {sl[i:].mean():.2f} ft")
print(f"  2025 baseline bat speed for reference: "
      f"{con.execute(f'SELECT AVG(bat_speed) FROM pitches WHERE batter=? AND game_year=2025 AND {SWING}',(VIEN,)).fetchone()[0]:.2f}")
out["vientos"] = {"split_date": d[i], "before": float(bs[:i].mean()), "after": float(bs[i:].mean()),
                  "t": float(t), "sl_before": float(sl[:i].mean()), "sl_after": float(sl[i:].mean())}

print("\n=== H6/H7/H8. How are they being pitched? (mix against, share of pitches) ===")
def mix(where, params):
    rows = con.execute(f"""SELECT game_year, pitch_type, COUNT(*) FROM pitches
        WHERE game_type='R' AND pitch_type IS NOT NULL AND {where}
        GROUP BY 1,2""", params).fetchall()
    tot = defaultdict(int); by = defaultdict(dict)
    for y, pt, n in rows: tot[y] += n; by[y][pt] = n
    return {y: {pt: 100*n/tot[y] for pt, n in v.items()} for y, v in by.items()}, tot

for label, where, params in [("Juan Soto", "batter=?", (SOTO,)),
                             ("Mark Vientos", "batter=?", (VIEN,)),
                             ("all NYM hitters", f"{BAT}='NYM'", ())]:
    m, tot = mix(where, params)
    fb = {y: sum(v.get(p,0) for p in ("FF","SI","FC")) for y, v in m.items()}
    print(f"  {label:18s} fastball share  " +
          "  ".join(f"{y}:{fb[y]:.1f}%" for y in sorted(fb) if tot[y] > 300))
out["fastball_share"] = {}

print("\n=== H9/H10. Lindor edge rate, and NYM mix with runners on ===")
LIN = [k for k,v in NAMES.items() if v=="Francisco Lindor"][0]
for y in (2025, 2026):
    r = con.execute("""SELECT COUNT(*),
        100.0*AVG(CASE WHEN ABS(plate_x) BETWEEN 0.6 AND 1.1 THEN 1.0 ELSE 0.0 END)
        FROM pitches WHERE batter=? AND game_year=? AND game_type='R' AND plate_x IS NOT NULL""",
        (LIN, y)).fetchone()
    print(f"  Lindor {y}: {r[1]:.1f}% of pitches on the horizontal edge  (n={r[0]:,})")
for y in (2025, 2026):
    r = con.execute(f"""SELECT
        100.0*AVG(CASE WHEN pitch_type IN ('FF','SI','FC') THEN 1.0 ELSE 0.0 END),
        COUNT(*) FROM pitches WHERE {BAT}='NYM' AND game_year=? AND game_type='R'
          AND (on_1b IS NOT NULL OR on_2b IS NOT NULL OR on_3b IS NOT NULL)
          AND pitch_type IS NOT NULL""", (y,)).fetchone()
    r2 = con.execute(f"""SELECT
        100.0*AVG(CASE WHEN pitch_type IN ('FF','SI','FC') THEN 1.0 ELSE 0.0 END)
        FROM pitches WHERE {BAT}='NYM' AND game_year=? AND game_type='R'
          AND on_1b IS NULL AND on_2b IS NULL AND on_3b IS NULL
          AND pitch_type IS NOT NULL""", (y,)).fetchone()
    print(f"  NYM {y}: fastball share  runners on {r[0]:.1f}%  bases empty {r2[0]:.1f}%")

print("\n=== H17/H18/H19. Mets pitchers: arm slot, velocity, arsenal ===")
pits = con.execute(f"""SELECT pitcher, player_name, COUNT(*) FROM pitches
    WHERE {PIT}='NYM' AND game_year=2026 AND game_type='R' GROUP BY 1
    HAVING COUNT(*)>800 ORDER BY 3 DESC LIMIT 8""").fetchall()
print(f"{'pitcher':22s} {'slot 25':>8} {'slot 26':>8} {'velo 25':>8} {'velo 26':>8}  arsenal shift")
for pid, nm, n in pits:
    nm = " ".join(x.strip() for x in nm.split(",")[::-1]) if "," in nm else nm
    v = {}
    for y in (2025, 2026):
        v[y] = con.execute("""SELECT AVG(arm_angle), AVG(release_speed) FROM pitches
            WHERE pitcher=? AND game_year=? AND game_type='R'
              AND pitch_type IN ('FF','SI')""", (pid, y)).fetchone()
    mixes = {}
    for y in (2025, 2026):
        rs = con.execute("""SELECT pitch_type, COUNT(*) FROM pitches WHERE pitcher=? AND game_year=?
            AND game_type='R' AND pitch_type IS NOT NULL GROUP BY 1""", (pid, y)).fetchall()
        t = sum(x[1] for x in rs) or 1
        mixes[y] = {p: 100*c/t for p, c in rs}
    if not v[2025][0] or not v[2026][0]:
        print(f"{nm[:22]:22s} {'—':>8} {'—':>8}  (no 2025 data)"); continue
    shifts = sorted(((mixes[2026].get(p,0)-mixes[2025].get(p,0), p)
                     for p in set(mixes[2025])|set(mixes[2026])), key=lambda x:-abs(x[0]))
    big = ", ".join(f"{p}{d:+.0f}pp" for d,p in shifts[:2] if abs(d)>=5) or "stable"
    print(f"{nm[:22]:22s} {v[2025][0]:>8.1f} {v[2026][0]:>8.1f} {v[2025][1]:>8.1f} "
          f"{v[2026][1]:>8.1f}  {big}")

Path("output/mets_tests.json").write_text(json.dumps(out, indent=1, default=float))
print("\nwrote output/mets_tests.json")
