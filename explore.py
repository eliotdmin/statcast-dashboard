#!/usr/bin/env python3
"""Exploratory battery. Each part is an independent question; run one or all:

    python3 explore.py --db data/statcast.db --part tto

Parts
  tto      Times-through-the-order penalty, and whether a broad arsenal blunts it
  decay    Within-game velocity decay, and whether decayers get punished
  twok     Do hitters shorten up with two strikes, and does it pay
  abs      Did the 2026 challenge system change the called strike zone
  tunnel   Same release point, different location: is tunneling worth anything
  lead     Does a change in chase rate LEAD a change in production (H14, properly)
  platoon  Platoon splits, and who is unusually resistant
  park     Is bat speed measured the same way in every park

Everything is within-player where a between-player comparison would be a
selection effect wearing a trenchcoat.
"""
import argparse, json, math, sqlite3, sys
from pathlib import Path
import numpy as np

SWING = "(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
WHIFF = "(description LIKE 'swinging_strike%' OR description='foul_tip')"
OUT = Path("output"); OUT.mkdir(exist_ok=True)
R = {}


def wald(p, n):
    return math.sqrt(max(p*(1-p), 0)/n) if n else float("nan")


def ols(X, y, w=None):
    X = np.asarray(X, float); y = np.asarray(y, float)
    if w is None: w = np.ones(len(y))
    w = np.asarray(w, float); s = np.sqrt(w)
    Xw, yw = X*s[:, None], y*s
    b, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    res = yw - Xw@b; dof = max(len(y)-X.shape[1], 1)
    s2 = float(res@res)/dof
    cov = s2*np.linalg.pinv(Xw.T@Xw)
    ss = float(((yw-yw.mean())**2).sum())
    return b, np.sqrt(np.diag(cov)), 1-float(res@res)/ss if ss else 0


def hdr(t):
    print("\n" + "="*72); print(t); print("="*72); sys.stdout.flush()


# ---------------------------------------------------------------- tto
PA = """WITH pa AS (
 SELECT game_pk, pitcher, batter, at_bat_number, MAX(inning) inn,
   MAX(woba_denom) wd, MAX(woba_value) wv,
   MAX(COALESCE(estimated_woba_using_speedangle,woba_value)) xv,
   MAX(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
   SUM(delta_run_exp) dre, COUNT(*) np
 FROM pitches WHERE game_year=? AND game_type='R' GROUP BY 1,2,3,4),
r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY game_pk,pitcher,batter
      ORDER BY at_bat_number) tto FROM pa)
SELECT pitcher, tto, COUNT(*) n, SUM(wd) pa,
 SUM(CASE WHEN wd=1 THEN wv END) wn, SUM(CASE WHEN wd=1 THEN xv END) xn,
 SUM(k) k, SUM(dre) dre, SUM(np) np
FROM r WHERE tto<=3 GROUP BY 1,2"""

MIX = """SELECT pitcher, pitch_type, COUNT(*) FROM pitches
WHERE game_year=? AND game_type='R' AND pitch_type IS NOT NULL
  AND pitch_type NOT IN ('PO','EP','FO','IN','AB','UN','') GROUP BY 1,2"""


def part_tto(con, years):
    hdr("TTO — the third time through, and whether a deep arsenal helps")
    rows, mix = {}, {}
    for y in years:
        for pid, tto, n, pa, wn, xn, k, dre, np_ in con.execute(PA, (y,)):
            if pa: rows[(pid, y)] = rows.get((pid, y), {})
            rows.setdefault((pid, y), {})[tto] = dict(n=n, pa=pa or 0, wn=wn or 0,
                                                      xn=xn or 0, k=k, dre=dre or 0, np=np_)
        c = {}
        for pid, pt, n in con.execute(MIX, (y,)): c.setdefault(pid, {})[pt] = n
        for pid, d in c.items():
            t = sum(d.values())
            if t < 200: continue
            ps = [v/t for v in d.values() if v]
            mix[(pid, y)] = dict(H=-sum(p*math.log(p) for p in ps),
                                 eff=math.exp(-sum(p*math.log(p) for p in ps)),
                                 top=max(ps), n=t,
                                 npitch=sum(1 for p in ps if p >= .05))

    # league-level penalty, pitcher-demeaned so the "good pitchers go deeper"
    # selection effect cannot produce it
    agg = {1: [0, 0, 0, 0], 2: [0, 0, 0, 0], 3: [0, 0, 0, 0]}
    dm = {1: [], 2: [], 3: []}
    for key, d in rows.items():
        if not all(t in d and d[t]["pa"] >= 25 for t in (1, 2, 3)): continue
        w = {t: d[t]["wn"]/d[t]["pa"] for t in (1, 2, 3)}
        base = sum(d[t]["wn"] for t in (1, 2, 3))/sum(d[t]["pa"] for t in (1, 2, 3))
        for t in (1, 2, 3):
            agg[t][0] += d[t]["wn"]; agg[t][1] += d[t]["pa"]
            agg[t][2] += d[t]["dre"]; agg[t][3] += d[t]["np"]
            dm[t].append((w[t]-base, d[t]["pa"]))
    print(f"{'pass':>5} {'PA':>8} {'wOBA':>7} {'rv/100p':>9} {'within-pitcher vs own avg':>27}")
    for t in (1, 2, 3):
        wn, pa, dre, np_ = agg[t]
        d = np.array([x[0] for x in dm[t]]); ww = np.array([x[1] for x in dm[t]], float)
        m = float((d*ww).sum()/ww.sum())
        se = float(np.sqrt(((d-m)**2*ww).sum()/ww.sum()/len(d)))
        print(f"{t:>5} {pa:>8.0f} {wn/pa:>7.4f} {100*dre/np_:>9.3f} "
              f"{m:>+19.4f} ± {se:.4f}")
    R["tto_within"] = {t: float((np.array([x[0] for x in dm[t]]) *
                       np.array([x[1] for x in dm[t]], float)).sum() /
                       np.array([x[1] for x in dm[t]], float).sum()) for t in (1, 2, 3)}

    # does arsenal breadth blunt the penalty?
    X, y, w, ent = [], [], [], []
    for key, d in rows.items():
        if key not in mix: continue
        if not all(t in d and d[t]["pa"] >= 40 for t in (1, 3)): continue
        pen = d[3]["wn"]/d[3]["pa"] - d[1]["wn"]/d[1]["pa"]
        n = min(d[1]["pa"], d[3]["pa"])
        y.append(pen); w.append(n); ent.append(mix[key]["eff"])
        X.append([1.0, mix[key]["eff"]])
    b, se, r2 = ols(X, y, w)
    e = np.array(ent); yy = np.array(y)
    print(f"\n  n={len(y)} starter-seasons with 40+ PA in both pass 1 and pass 3")
    print(f"  arsenal breadth (effective # pitches): mean {e.mean():.2f}  range {e.min():.2f}-{e.max():.2f}")
    print(f"  TTO3-minus-TTO1 wOBA penalty: mean {yy.mean():+.4f}")
    print(f"  penalty ~ breadth   slope {b[1]:+.4f} ± {se[1]:.4f}  "
          f"({'helps' if b[1]+1.96*se[1] < 0 else 'hurts' if b[1]-1.96*se[1] > 0 else 'NO EFFECT'})")
    print(f"  interpretation: each extra effective pitch type changes the third-time")
    print(f"  penalty by {b[1]:+.4f} wOBA. League sd of the penalty is {yy.std():.4f}.")
    R["tto_breadth"] = dict(n=len(y), slope=float(b[1]), se=float(se[1]),
                            mean_pen=float(yy.mean()))

    # split by breadth tercile, raw
    q = np.quantile(e, [1/3, 2/3])
    print(f"\n  {'breadth tercile':>18} {'n':>5} {'mean penalty':>14}")
    for lab, m in (("narrow", e <= q[0]), ("middle", (e > q[0]) & (e <= q[1])),
                   ("broad", e > q[1])):
        print(f"  {lab:>18} {m.sum():>5} {yy[m].mean():>+14.4f}")


# ---------------------------------------------------------------- decay
DEC = """WITH p AS (
 SELECT game_pk, pitcher, at_bat_number, pitch_number, release_speed, pitch_type,
   delta_run_exp, woba_denom, woba_value,
   ROW_NUMBER() OVER (PARTITION BY game_pk,pitcher ORDER BY at_bat_number,pitch_number) pn
 FROM pitches WHERE game_year=? AND game_type='R' AND pitch_type IN ('FF','SI'))
SELECT pitcher, game_pk, COUNT(*) n, SUM(pn) sx, SUM(pn*pn) sxx,
 SUM(release_speed) sy, SUM(pn*release_speed) sxy, MAX(pn) mx
FROM p WHERE release_speed IS NOT NULL GROUP BY 1,2 HAVING n>=25 AND mx>=60"""

LATE = """WITH p AS (
 SELECT game_pk, pitcher, at_bat_number, pitch_number, woba_denom, woba_value,
   COALESCE(estimated_woba_using_speedangle,woba_value) xv,
   ROW_NUMBER() OVER (PARTITION BY game_pk,pitcher ORDER BY at_bat_number,pitch_number) pn
 FROM pitches WHERE game_year=? AND game_type='R')
SELECT pitcher, game_pk, SUM(CASE WHEN pn<=45 AND woba_denom=1 THEN 1 ELSE 0 END) e_pa,
 SUM(CASE WHEN pn<=45 AND woba_denom=1 THEN woba_value END) e_w,
 SUM(CASE WHEN pn>=60 AND woba_denom=1 THEN 1 ELSE 0 END) l_pa,
 SUM(CASE WHEN pn>=60 AND woba_denom=1 THEN woba_value END) l_w
FROM p GROUP BY 1,2"""


def part_decay(con, years):
    hdr("VELOCITY DECAY — do starters who lose more velo get hit harder late?")
    slopes, late = {}, {}
    for y in years:
        for pid, gpk, n, sx, sxx, sy, sxy, mx in con.execute(DEC, (y,)):
            den = n*sxx - sx*sx
            if den <= 0: continue
            slopes[(pid, gpk)] = (n*sxy - sx*sy)/den * 100  # mph per 100 pitches
        for pid, gpk, epa, ew, lpa, lw in con.execute(LATE, (y,)):
            if epa and lpa: late[(pid, gpk)] = (epa, ew or 0, lpa, lw or 0)
    com = [k for k in slopes if k in late]
    s = np.array([slopes[k] for k in com])
    print(f"  {len(com)} starter-games with a fastball slope and both early & late PA")
    print(f"  velo change per 100 pitches: mean {s.mean():+.3f} mph  sd {s.std():.3f}")
    q = np.quantile(s, [.2, .4, .6, .8])
    print(f"\n  {'decay quintile':>16} {'slope':>8} {'early wOBA':>11} {'late wOBA':>10} {'late-early':>11}")
    rows = []
    for i, (lo, hi) in enumerate(zip([-99]+list(q), list(q)+[99])):
        m = [k for k, v in zip(com, s) if lo < v <= hi]
        epa = sum(late[k][0] for k in m); ew = sum(late[k][1] for k in m)
        lpa = sum(late[k][2] for k in m); lw = sum(late[k][3] for k in m)
        sl = np.mean([slopes[k] for k in m])
        rows.append((sl, ew/epa, lw/lpa))
        print(f"  {i+1:>16} {sl:>+8.3f} {ew/epa:>11.4f} {lw/lpa:>10.4f} {lw/lpa-ew/epa:>+11.4f}")
    a = np.array(rows)
    r = float(np.corrcoef(a[:, 0], a[:, 2]-a[:, 1])[0, 1])
    print(f"\n  corr(decay slope, late-minus-early wOBA) across quintiles: {r:+.3f}")
    print("  (negative = steeper decay goes with a bigger late-game penalty)")
    R["decay"] = dict(n=len(com), mean=float(s.mean()), sd=float(s.std()), corr=r)


# ---------------------------------------------------------------- twok
TWOK = f"""SELECT batter, game_year,
 SUM(CASE WHEN strikes<2 AND bat_speed IS NOT NULL THEN 1 ELSE 0 END) n0,
 SUM(CASE WHEN strikes<2 THEN bat_speed END) b0,
 SUM(CASE WHEN strikes<2 THEN swing_length END) l0,
 SUM(CASE WHEN strikes=2 AND bat_speed IS NOT NULL THEN 1 ELSE 0 END) n2,
 SUM(CASE WHEN strikes=2 THEN bat_speed END) b2,
 SUM(CASE WHEN strikes=2 THEN swing_length END) l2,
 SUM(CASE WHEN strikes=2 AND {SWING} THEN 1 ELSE 0 END) sw2,
 SUM(CASE WHEN strikes=2 AND {SWING} AND {WHIFF} THEN 1 ELSE 0 END) wh2,
 SUM(CASE WHEN strikes=2 AND woba_denom=1 THEN 1 ELSE 0 END) pa2,
 SUM(CASE WHEN strikes=2 AND woba_denom=1 THEN woba_value END) w2,
 SUM(CASE WHEN strikes=2 AND events='strikeout' THEN 1 ELSE 0 END) k2,
 SUM(woba_denom) pa, SUM(CASE WHEN woba_denom=1 THEN woba_value END) w
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R'
GROUP BY 1,2 HAVING pa>=300 AND n2>=100"""


def part_twok(con, years):
    hdr("TWO STRIKES — who shortens up, and does it pay")
    rows = list(con.execute(TWOK))
    adj, k2r, w2r, wh = [], [], [], []
    ladj = []
    for r in rows:
        (_, _, n0, b0, l0, n2, b2, l2, sw2, wh2, pa2, w2, k2, pa, w) = r
        if not (n0 and n2 and sw2 and pa2): continue
        adj.append(b2/n2 - b0/n0); ladj.append(l2/n2 - l0/n0)
        k2r.append(k2/pa2); w2r.append((w2 or 0)/pa2); wh.append(wh2/sw2)
    a = np.array(adj); la = np.array(ladj); k = np.array(k2r)
    ww = np.array(w2r); h = np.array(wh)
    print(f"  n={len(a)} hitter-seasons (300+ PA, 100+ tracked 2K swings)")
    print(f"  bat speed with 2 strikes minus without: mean {a.mean():+.3f} mph  sd {a.std():.3f}")
    print(f"  swing length  with 2 strikes minus without: mean {la.mean():+.3f} ft  sd {la.std():.3f}")
    frac = float((a < 0).mean())
    print(f"  {100*frac:.0f}% of hitters swing SLOWER with two strikes")
    print(f"\n  {'adjustment tercile':>20} {'Δbat spd':>9} {'2K K-rate':>10} {'2K wOBA':>9} {'2K whiff/sw':>12}")
    q = np.quantile(a, [1/3, 2/3])
    for lab, m in (("shortens most", a <= q[0]), ("middle", (a > q[0]) & (a <= q[1])),
                   ("keeps swinging hard", a > q[1])):
        print(f"  {lab:>20} {a[m].mean():>+9.3f} {k[m].mean():>10.3f} "
              f"{ww[m].mean():>9.4f} {h[m].mean():>12.3f}")
    for nm, v in (("2K K-rate", k), ("2K wOBA", ww), ("2K whiff/sw", h)):
        r_ = float(np.corrcoef(a, v)[0, 1])
        z = 0.5*math.log((1+r_)/(1-r_)); s = 1/math.sqrt(len(a)-3)
        lo, hi = math.tanh(z-1.96*s), math.tanh(z+1.96*s)
        print(f"  corr(Δbat speed, {nm:<12}) = {r_:+.3f}  95% [{lo:+.3f},{hi:+.3f}]")
    R["twok"] = dict(n=len(a), mean_adj=float(a.mean()), frac_slower=frac)


# ---------------------------------------------------------------- abs
ABSQ = """SELECT game_year,
 CAST(MIN(4, MAX(0, (ABS(plate_x)-0.83)/0.15 + 3)) AS INT) bx,
 SUM(CASE WHEN description='called_strike' THEN 1 ELSE 0 END) cs, COUNT(*) n
FROM pitches WHERE game_year IN (2024,2025,2026) AND game_type='R'
 AND description IN ('called_strike','ball','blocked_ball')
 AND plate_x IS NOT NULL AND plate_z BETWEEN sz_bot AND sz_top
GROUP BY 1,2"""

ABSV = """SELECT game_year,
 CAST(MIN(4, MAX(0, (plate_z-sz_top)/0.15 + 3)) AS INT) bz,
 SUM(CASE WHEN description='called_strike' THEN 1 ELSE 0 END) cs, COUNT(*) n
FROM pitches WHERE game_year IN (2024,2025,2026) AND game_type='R'
 AND description IN ('called_strike','ball','blocked_ball')
 AND plate_z IS NOT NULL AND ABS(plate_x)<=0.83 AND plate_z>sz_top-0.45
GROUP BY 1,2"""


def part_abs(con, years):
    hdr("THE 2026 CHALLENGE SYSTEM — did the called zone actually change shape?")
    for title, q, lab in (("horizontal (inside/outside edge)", ABSQ,
                           ["deep in", "in", "on edge", "just off", "clearly off"]),
                          ("vertical (top of zone)", ABSV,
                           ["below top", "at top", "on top edge", "just above", "clearly above"])):
        d = {}
        for y, b, cs, n in con.execute(q): d[(y, b)] = (cs, n)
        print(f"\n  {title}")
        print(f"  {'band':>14} " + " ".join(f"{y:>16}" for y in (2024, 2025, 2026)))
        for b in range(5):
            cells = []
            for y in (2024, 2025, 2026):
                cs, n = d.get((y, b), (0, 0))
                cells.append(f"{100*cs/n:>7.1f}% ({n//1000:>4}k)" if n else " " * 16)
            print(f"  {lab[b]:>14} " + " ".join(cells))
        # 2026 vs 2025 on the two ambiguous bands
        for b in (2, 3):
            c5, n5 = d.get((2025, b), (0, 1)); c6, n6 = d.get((2026, b), (0, 1))
            p5, p6 = c5/n5, c6/n6
            se = math.hypot(wald(p5, n5), wald(p6, n6))
            print(f"    {lab[b]:>12}: {100*(p6-p5):+6.2f} pp  ± {100*1.96*se:.2f}  "
                  f"{'CHANGED' if abs(p6-p5) > 1.96*se else 'no change'}")


# ---------------------------------------------------------------- tunnel
TUN = f"""WITH p AS (
 SELECT game_pk, at_bat_number, pitch_number, pitch_type, release_pos_x, release_pos_z,
   plate_x, plate_z, balls, strikes, description, type, delta_run_exp,
   LAG(pitch_type) OVER w pt0, LAG(release_pos_x) OVER w rx0, LAG(release_pos_z) OVER w rz0,
   LAG(plate_x) OVER w px0, LAG(plate_z) OVER w pz0
 FROM pitches WHERE game_year IN (2025,2026) AND game_type='R'
 WINDOW w AS (PARTITION BY game_pk,at_bat_number ORDER BY pitch_number))
SELECT pt0, pitch_type, balls, strikes,
 CAST(MIN(3, (ABS(release_pos_x-rx0)+ABS(release_pos_z-rz0))/0.15) AS INT) rb,
 CAST(MIN(3, (ABS(plate_x-px0)+ABS(plate_z-pz0))/0.8) AS INT) pb,
 SUM(CASE WHEN {SWING} THEN 1 ELSE 0 END) sw,
 SUM(CASE WHEN {SWING} AND {WHIFF} THEN 1 ELSE 0 END) wh,
 COUNT(*) n, SUM(delta_run_exp) dre
FROM p WHERE pt0 IS NOT NULL AND rx0 IS NOT NULL AND px0 IS NOT NULL
 AND pitch_type IS NOT NULL AND pt0<>pitch_type
GROUP BY 1,2,3,4,5,6"""


def part_tunnel(con, years):
    hdr("TUNNELING — same release point, different destination. Worth anything?")
    cells = list(con.execute(TUN))
    # baseline whiff per (pt0,pt,count) so release-distance is compared within
    # otherwise identical situations
    base = {}
    for pt0, pt, b, s, rb, pb, sw, wh, n, dre in cells:
        k = (pt0, pt, b, s)
        a = base.setdefault(k, [0, 0, 0, 0])
        a[0] += sw; a[1] += wh; a[2] += n; a[3] += dre or 0
    agg = {}
    for pt0, pt, b, s, rb, pb, sw, wh, n, dre in cells:
        k = (pt0, pt, b, s)
        bs, bw, bn, bd = base[k]
        if bs < 50 or sw < 5: continue
        a = agg.setdefault(rb, [0, 0, 0, 0, 0])
        a[0] += sw; a[1] += wh; a[2] += sw*(bw/bs)          # expected whiffs
        a[3] += n; a[4] += (dre or 0) - n*(bd/bn)            # excess run value
    print(f"  release-point distance between consecutive DIFFERENT pitch types,")
    print(f"  compared with the same (prev type, this type, count) baseline.\n")
    print(f"  {'release gap':>16} {'swings':>10} {'whiff%':>8} {'exp':>7} {'excess':>8} {'rv/100':>8}")
    labs = ["<1.8 in", "1.8-3.6 in", "3.6-5.4 in", ">5.4 in"]
    for rb in sorted(agg):
        sw, wh, ew, n, ex = agg[rb]
        se = 100*wald(wh/sw, sw)
        print(f"  {labs[rb]:>16} {sw:>10,} {100*wh/sw:>7.2f}% {100*ew/sw:>6.2f}% "
              f"{100*(wh-ew)/sw:>+7.2f}% {100*ex/n:>+8.3f}")
    print(f"  (± {se:.2f}pp on the whiff rate in the smallest bucket)")
    R["tunnel"] = {int(k): dict(sw=v[0], excess=float((v[1]-v[2])/v[0]),
                                rv100=float(100*v[4]/v[3])) for k, v in agg.items()}


# ---------------------------------------------------------------- lead
MON = f"""SELECT batter, substr(game_date,1,7) ym, SUM(woba_denom) pa,
 SUM(CASE WHEN woba_denom=1 THEN woba_value END) wn,
 SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END) xn,
 SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END) oz,
 SUM(CASE WHEN zone>=11 AND {SWING} THEN 1 ELSE 0 END) ozsw,
 SUM(CASE WHEN {SWING} THEN 1 ELSE 0 END) sw,
 SUM(CASE WHEN {SWING} AND {WHIFF} THEN 1 ELSE 0 END) wh,
 SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END) nbs, SUM(bat_speed) sbs
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R'
GROUP BY 1,2 HAVING pa>=60 AND oz>=40"""


def part_lead(con, years):
    hdr("H14 DONE PROPERLY — does a chase-rate change LEAD a production change?")
    m = {}
    for bid, ym, pa, wn, xn, oz, ozsw, sw, wh, nbs, sbs in con.execute(MON):
        m.setdefault(bid, {})[ym] = dict(pa=pa, w=(wn or 0)/pa, x=(xn or 0)/pa,
                                         ch=ozsw/oz, wh=wh/sw if sw else None,
                                         bs=sbs/nbs if nbs else None)
    def nxt(a):
        y, mm = int(a[:4]), int(a[5:7])
        return f"{y}-{mm+1:02d}" if mm < 12 else None
    rows = []
    for bid, d in m.items():
        ks = sorted(d)
        for i in range(1, len(ks)-1):
            p, c, n = ks[i-1], ks[i], ks[i+1]
            if nxt(p) != c or nxt(c) != n: continue
            rows.append(dict(bid=bid, dch=d[c]["ch"]-d[p]["ch"],
                             dwh=(d[c]["wh"]-d[p]["wh"]) if d[c]["wh"] and d[p]["wh"] else None,
                             dw_now=d[c]["w"]-d[p]["w"], dw_next=d[n]["w"]-d[c]["w"],
                             x_next=d[n]["x"], x_now=d[c]["x"],
                             n=min(d[c]["pa"], d[n]["pa"])))
    print(f"  {len(rows)} hitter month-triples (3 consecutive months, 60+ PA each)")
    # demean within hitter so this is a within-player question
    byb = {}
    for r_ in rows: byb.setdefault(r_["bid"], []).append(r_)
    X, y, w = [], [], []
    for bid, rs in byb.items():
        if len(rs) < 2: continue
        mc = np.mean([r_["dch"] for r_ in rs]); mn_ = np.mean([r_["dw_now"] for r_ in rs])
        my = np.mean([r_["dw_next"] for r_ in rs])
        for r_ in rs:
            X.append([r_["dch"]-mc, r_["dw_now"]-mn_]); y.append(r_["dw_next"]-my); w.append(r_["n"])
    b, se, r2 = ols(X, y, w)
    print(f"  within-hitter regression, n={len(y)}")
    print(f"    next month's ΔwOBA  ~  this month's Δchase + this month's ΔwOBA")
    print(f"    Δchase   {b[0]:+.4f} ± {se[0]:.4f}   "
          f"({'LEADS' if abs(b[0]) > 1.96*se[0] else 'no lead effect'})")
    print(f"    ΔwOBA    {b[1]:+.4f} ± {se[1]:.4f}   "
          f"({'momentum' if b[1] > 1.96*se[1] else 'mean reversion' if b[1] < -1.96*se[1] else 'neither'})")
    print(f"    R²={r2:.4f}")
    print(f"  a 5-point chase increase would move next month's wOBA by "
          f"{5*b[0]/100:+.4f} [{5*(b[0]-1.96*se[0])/100:+.4f}, {5*(b[0]+1.96*se[0])/100:+.4f}]")
    R["lead_chase"] = dict(n=len(y), beta=float(b[0]), se=float(se[0]),
                           persist=float(b[1]), persist_se=float(se[1]))

    # contemporaneous, for contrast
    Xc, yc, wc = [], [], []
    for bid, rs in byb.items():
        if len(rs) < 2: continue
        mc = np.mean([r_["dch"] for r_ in rs]); mn_ = np.mean([r_["dw_now"] for r_ in rs])
        for r_ in rs:
            Xc.append([r_["dch"]-mc]); yc.append(r_["dw_now"]-mn_); wc.append(r_["n"])
    b2, se2, _ = ols(Xc, yc, wc)
    print(f"  same-month Δchase -> ΔwOBA: {b2[0]:+.4f} ± {se2[0]:.4f}  "
          f"({'real' if abs(b2[0]) > 1.96*se2[0] else 'nothing'})")
    R["chase_contemp"] = dict(beta=float(b2[0]), se=float(se2[0]))


# ---------------------------------------------------------------- platoon
PLQ = """SELECT batter, CASE WHEN stand=p_throws THEN 'same' ELSE 'opp' END h,
 SUM(woba_denom) pa, SUM(CASE WHEN woba_denom=1 THEN woba_value END) wn,
 SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END) xn,
 SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R' AND stand IN ('L','R')
GROUP BY 1,2"""


def part_platoon(con, years):
    hdr("PLATOON — how big is the real split, and is 'platoon-proof' a skill?")
    d = {}
    for bid, h, pa, wn, xn, k in con.execute(PLQ):
        d.setdefault(bid, {})[h] = (pa, wn or 0, xn or 0, k)
    ok = {b: v for b, v in d.items() if "same" in v and "opp" in v
          and v["same"][0] >= 150 and v["opp"][0] >= 250}
    sp, se_, w = [], [], []
    for b, v in ok.items():
        a, o = v["same"], v["opp"]
        sp.append(o[1]/o[0] - a[1]/a[0])
        se_.append(math.hypot(.30/math.sqrt(a[0]), .30/math.sqrt(o[0])))
        w.append(min(a[0], o[0]))
    s = np.array(sp); e = np.array(se_)
    vo = s.var(ddof=1); vn = (e**2).mean(); vt = max(vo-vn, 0)
    print(f"  n={len(s)} hitters (150+ same-hand PA, 250+ opposite, 2025+2026 pooled)")
    print(f"  mean advantage vs opposite hand: {s.mean():+.4f} wOBA")
    print(f"  observed spread {math.sqrt(vo):.4f}  noise {math.sqrt(vn):.4f}  "
          f"TRUE {math.sqrt(vt):.4f}  signal {100*vt/vo:.0f}%")
    print(f"  -> platoon split IS a real individual trait, but {100*vn/vo:.0f}% of the")
    print(f"     apparent spread between hitters is sampling noise.")
    R["platoon"] = dict(n=len(s), mean=float(s.mean()), sd_true=float(math.sqrt(vt)),
                        share=float(vt/vo))


# ---------------------------------------------------------------- park
PKQ = """SELECT CASE WHEN inning_topbot='Bot' THEN home_team ELSE away_team END tm,
 home_team park, game_year,
 SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END) n, SUM(bat_speed) s,
 SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END) ne,
 SUM(CASE WHEN type='X' THEN launch_speed END) se
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R' GROUP BY 1,2,3"""


def part_park(con, years):
    hdr("MEASUREMENT — is bat speed calibrated the same in every park?")
    rows = list(con.execute(PKQ))
    # a team's own hitters measured at home vs on the road: same hitters,
    # different sensors. any gap is the park, not the players.
    home, road = {}, {}
    for tm, park, y, n, s, ne, se in rows:
        if not n: continue
        tgt = home if tm == park else road
        a = tgt.setdefault(park if tm == park else tm, [0, 0, 0, 0])
        a[0] += n; a[1] += s or 0; a[2] += ne or 0; a[3] += se or 0
    print(f"  {'park':>6} {'home bs':>9} {'road bs':>9} {'Δ':>7} {'home EV':>9} {'road EV':>9} {'Δ':>7}")
    dd, de = [], []
    for t in sorted(set(home) & set(road)):
        h, r_ = home[t], road[t]
        if h[0] < 3000 or r_[0] < 3000: continue
        db = h[1]/h[0] - r_[1]/r_[0]; dev = h[3]/h[2] - r_[3]/r_[2]
        dd.append(db); de.append(dev)
        print(f"  {t:>6} {h[1]/h[0]:>9.2f} {r_[1]/r_[0]:>9.2f} {db:>+7.2f} "
              f"{h[3]/h[2]:>9.2f} {r_[3]/r_[2]:>9.2f} {dev:>+7.2f}")
    a, b = np.array(dd), np.array(de)
    print(f"\n  home-minus-road bat speed across parks: sd {a.std():.3f} mph, "
          f"range {a.min():+.2f} to {a.max():+.2f}")
    print(f"  home-minus-road exit velo  across parks: sd {b.std():.3f} mph, "
          f"range {b.min():+.2f} to {b.max():+.2f}")
    print(f"  corr between the two: {float(np.corrcoef(a,b)[0,1]):+.3f}  "
          "(high = a shared sensor/park effect, not hitting)")
    R["park"] = dict(sd_bs=float(a.std()), sd_ev=float(b.std()),
                     corr=float(np.corrcoef(a, b)[0, 1]))


PARTS = dict(tto=part_tto, decay=part_decay, twok=part_twok, abs=part_abs,
             tunnel=part_tunnel, lead=part_lead, platoon=part_platoon, park=part_park)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent/"data"/"statcast.db"))
    ap.add_argument("--part", default="all")
    ap.add_argument("--years", type=int, nargs="+", default=[2025, 2026])
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-500000")
    names = list(PARTS) if a.part == "all" else a.part.split(",")
    for n in names:
        try:
            PARTS[n](con, a.years)
        except Exception as e:
            print(f"\n!! part {n} failed: {type(e).__name__}: {e}")
        sys.stdout.flush()
    (OUT/"explore.json").write_text(json.dumps(R, indent=1, default=float))
    print("\nwrote output/explore.json")


if __name__ == "__main__":
    main()
