#!/usr/bin/env python3
"""Two corrections.

1. ABS. In 2026 MLB replaced the per-pitch operator estimate of the strike zone
   with a formula: 390 distinct sz_top values league-wide, exactly one per
   batter, mean 0.22 ft lower than 2025. Any analysis measured RELATIVE to
   sz_top compares 2026 against a different ruler. Everything here is measured
   in absolute feet off the ground and off the center of the plate, which the
   rulebook fixes.

2. Velocity decay. Comparing pitchers whose velo fell to pitchers whose velo
   rose is a selection effect: a starter still throwing hard at pitch 90 is a
   starter who was cruising. The within-pitcher version asks whether the SAME
   pitcher does worse in his own steeper-decay starts.
"""
import os, math, sqlite3, numpy as np
con = sqlite3.connect(f"file:{os.environ['HOME']}/snap.db?mode=ro", uri=True)
con.execute("PRAGMA cache_size=-500000")
YRS = (2024, 2025, 2026)


def se(p, n): return math.sqrt(max(p*(1-p), 0)/n) if n else float("nan")


print("="*74)
print("THE CALLED ZONE IN ABSOLUTE FEET (immune to the 2026 sz_top redefinition)")
print("="*74)
Q = """SELECT SUM(CASE WHEN description='called_strike' THEN 1 ELSE 0 END), COUNT(*)
FROM pitches WHERE game_year=? AND game_type='R'
 AND description IN ('called_strike','ball','blocked_ball')
 AND plate_x IS NOT NULL AND plate_z IS NOT NULL AND {W}"""
res = {}
print("\n  TOP of the zone   (|plate_x| <= 0.7 ft, i.e. well inside the plate)")
print(f"  {'height (ft)':>14} " + " ".join(f"{y:>15}" for y in YRS) + f" {'26 vs 25':>11}")
for lo, hi in ((2.8,3.0),(3.0,3.2),(3.2,3.4),(3.4,3.6),(3.6,3.8)):
    cells, p = [], {}
    for y in YRS:
        cs, n = con.execute(Q.format(W=f"ABS(plate_x)<=0.7 AND plate_z>={lo} AND plate_z<{hi}"), (y,)).fetchone()
        p[y] = (cs/n, n); cells.append(f"{100*cs/n:>6.1f}% ({n//1000:>3}k)")
    d = p[2026][0]-p[2025][0]; s = math.hypot(se(*p[2025]), se(*p[2026]))
    print(f"  {f'{lo}-{hi}':>14} " + " ".join(cells) +
          f" {100*d:>+7.1f}pp{'*' if abs(d)>1.96*s else ' '}")
    res[("top", lo)] = (d, s)
print("\n  BOTTOM of the zone   (|plate_x| <= 0.7 ft)")
print(f"  {'height (ft)':>14} " + " ".join(f"{y:>15}" for y in YRS) + f" {'26 vs 25':>11}")
for lo, hi in ((1.2,1.4),(1.4,1.6),(1.6,1.8),(1.8,2.0)):
    cells, p = [], {}
    for y in YRS:
        cs, n = con.execute(Q.format(W=f"ABS(plate_x)<=0.7 AND plate_z>={lo} AND plate_z<{hi}"), (y,)).fetchone()
        p[y] = (cs/n, n); cells.append(f"{100*cs/n:>6.1f}% ({n//1000:>3}k)")
    d = p[2026][0]-p[2025][0]; s = math.hypot(se(*p[2025]), se(*p[2026]))
    print(f"  {f'{lo}-{hi}':>14} " + " ".join(cells) +
          f" {100*d:>+7.1f}pp{'*' if abs(d)>1.96*s else ' '}")
print("\n  SIDES   (1.7 <= plate_z <= 3.1 ft, a fixed vertical window)")
print(f"  {'|plate_x| (ft)':>14} " + " ".join(f"{y:>15}" for y in YRS) + f" {'26 vs 25':>11}")
for lo, hi in ((0.6,0.75),(0.75,0.9),(0.9,1.05),(1.05,1.2)):
    cells, p = [], {}
    for y in YRS:
        cs, n = con.execute(Q.format(
            W=f"plate_z BETWEEN 1.7 AND 3.1 AND ABS(plate_x)>={lo} AND ABS(plate_x)<{hi}"), (y,)).fetchone()
        p[y] = (cs/n, n); cells.append(f"{100*cs/n:>6.1f}% ({n//1000:>3}k)")
    d = p[2026][0]-p[2025][0]; s = math.hypot(se(*p[2025]), se(*p[2026]))
    print(f"  {f'{lo}-{hi}':>14} " + " ".join(cells) +
          f" {100*d:>+7.1f}pp{'*' if abs(d)>1.96*s else ' '}")
print("\n  * = 2026-vs-2025 gap exceeds 1.96 SE. The plate is 1.417 ft wide, so a")
print("    ball catching the very edge is around |plate_x| = 0.83 ft.")

# how sharp is the boundary? a crisper zone = steeper logistic slope
print("\n  ZONE SHARPNESS — width of the 20%-to-80% transition band, in inches")
for axis, w, rng in (("outside edge", "plate_z BETWEEN 1.7 AND 3.1 AND ABS(plate_x)", np.arange(.55, 1.30, .025)),
                     ("top edge", "ABS(plate_x)<=0.7 AND plate_z", np.arange(2.8, 4.0, .04))):
    print(f"  {axis:>14} " + " ".join(f"{y:>9}" for y in YRS))
    out = []
    for y in YRS:
        xs, ps = [], []
        for a, b in zip(rng[:-1], rng[1:]):
            cs, n = con.execute(Q.format(W=f"{w}>={a} AND {w}<{b}"), (y,)).fetchone()
            if n > 300: xs.append((a+b)/2); ps.append(cs/n)
        xs, ps = np.array(xs), np.array(ps)
        def cx(t):
            for i in range(len(ps)-1):
                if (ps[i]-t)*(ps[i+1]-t) <= 0:
                    return xs[i] + (t-ps[i])/(ps[i+1]-ps[i])*(xs[i+1]-xs[i])
            return float("nan")
        out.append(12*abs(cx(.2)-cx(.8)))
    print(f"  {'':>14} " + " ".join(f"{v:>9.2f}" for v in out) + "   (smaller = crisper)")

print("\n" + "="*74)
print("VELOCITY DECAY, WITHIN PITCHER (his steep starts vs his own flat starts)")
print("="*74)
DEC = """WITH p AS (
 SELECT game_pk, pitcher, release_speed, pitch_type, woba_denom, woba_value,
   ROW_NUMBER() OVER (PARTITION BY game_pk,pitcher ORDER BY at_bat_number,pitch_number) pn
 FROM pitches WHERE game_year IN (2025,2026) AND game_type='R')
SELECT pitcher, game_pk,
 SUM(CASE WHEN pitch_type IN ('FF','SI') AND release_speed IS NOT NULL THEN 1 ELSE 0 END) n,
 SUM(CASE WHEN pitch_type IN ('FF','SI') AND release_speed IS NOT NULL THEN pn END) sx,
 SUM(CASE WHEN pitch_type IN ('FF','SI') AND release_speed IS NOT NULL THEN pn*pn END) sxx,
 SUM(CASE WHEN pitch_type IN ('FF','SI') THEN release_speed END) sy,
 SUM(CASE WHEN pitch_type IN ('FF','SI') AND release_speed IS NOT NULL THEN pn*release_speed END) sxy,
 MAX(pn) mx,
 SUM(CASE WHEN pn<=45 AND woba_denom=1 THEN 1 ELSE 0 END) epa,
 SUM(CASE WHEN pn<=45 AND woba_denom=1 THEN woba_value END) ew,
 SUM(CASE WHEN pn>=60 AND woba_denom=1 THEN 1 ELSE 0 END) lpa,
 SUM(CASE WHEN pn>=60 AND woba_denom=1 THEN woba_value END) lw
FROM p GROUP BY 1,2 HAVING n>=25 AND mx>=60 AND epa>0 AND lpa>0"""
g = {}
for pid, gpk, n, sx, sxx, sy, sxy, mx, epa, ew, lpa, lw in con.execute(DEC):
    den = n*sxx-sx*sx
    if den <= 0: continue
    g.setdefault(pid, []).append(((n*sxy-sx*sy)/den*100, epa, ew or 0, lpa, lw or 0))
X, Y, W = [], [], []
for pid, gs in g.items():
    if len(gs) < 4: continue
    ms = np.mean([x[0] for x in gs])
    md = np.mean([x[4]/x[3]-x[2]/x[1] for x in gs])
    for s_, epa, ew, lpa, lw in gs:
        X.append(s_-ms); Y.append((lw/lpa-ew/epa)-md); W.append(min(epa, lpa))
X, Y, W = np.array(X), np.array(Y), np.array(W, float)
A = np.c_[np.ones(len(X)), X]
b, *_ = np.linalg.lstsq(A*np.sqrt(W)[:, None], Y*np.sqrt(W), rcond=None)
r = (Y*np.sqrt(W) - (A*np.sqrt(W)[:, None])@b)
s2 = float(r@r)/max(len(Y)-2, 1)
sb = math.sqrt(s2*np.linalg.pinv((A*np.sqrt(W)[:, None]).T@(A*np.sqrt(W)[:, None]))[1, 1])
print(f"  {len(X)} starts from {sum(1 for v in g.values() if len(v)>=4)} pitchers with 4+ qualifying starts")
print(f"  BETWEEN pitchers (the naive version) said: steeper decay -> SMALLER late penalty")
print(f"  WITHIN pitcher:  slope {b[1]:+.5f} ± {sb:.5f} wOBA per (mph/100 pitches)")
print(f"  -> a start where he loses 1 extra mph per 100 pitches costs him "
      f"{-b[1]:+.4f} late wOBA")
print(f"  {'REAL' if abs(b[1])>1.96*sb else 'NOT DISTINGUISHABLE FROM ZERO'}")
