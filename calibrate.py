#!/usr/bin/env python3
"""League-wide season-over-season change distributions for EVERY profile metric.

    python3 calibrate.py --db data/statcast.db

profiles.py reports a change per metric; this says how much that metric actually
moves league-wide, so a change can be judged against real movement rather than
against zero or against somebody's judgement of what counts as a lot.

For each metric:  var(observed change) = var(true change) + var(noise)
The signal share var_true/var_obs is also the shrinkage factor -- the fraction of
an observed change you should believe.

Also answers H16: is a hitter's luck gap (wOBA minus xwOBA) related to a change
in his swing? If the gap were mechanical, hitters whose bat speed moved should
show different gaps. If it is luck, there should be no relationship.
"""
import argparse, json, math, sqlite3
from pathlib import Path
import numpy as np

SWING = "(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
WHIFF = "(description LIKE 'swinging_strike%' OR description='foul_tip')"
INZ = "(zone BETWEEN 1 AND 9)"
EDGE = "(ABS(plate_x) BETWEEN 0.6 AND 1.1)"

HIT = f"""SELECT batter, game_year, SUM(woba_denom) pa,
 SUM(CASE WHEN woba_denom=1 THEN woba_value END) wn,
 SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END) xn,
 SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
 SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END) bb, COUNT(*) pit,
 SUM(CASE WHEN {SWING} THEN 1 ELSE 0 END) sw,
 SUM(CASE WHEN {INZ} THEN 1 ELSE 0 END) iz,
 SUM(CASE WHEN {INZ} AND {SWING} THEN 1 ELSE 0 END) zsw,
 SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END) oz,
 SUM(CASE WHEN zone>=11 AND {SWING} THEN 1 ELSE 0 END) ozsw,
 SUM(CASE WHEN {SWING} AND {WHIFF} THEN 1 ELSE 0 END) wh,
 SUM(CASE WHEN balls=0 AND strikes=0 THEN 1 ELSE 0 END) fp,
 SUM(CASE WHEN balls=0 AND strikes=0 AND {SWING} THEN 1 ELSE 0 END) fpsw,
 SUM(CASE WHEN strikes=2 THEN 1 ELSE 0 END) tk,
 SUM(CASE WHEN strikes=2 AND {SWING} THEN 1 ELSE 0 END) tksw,
 SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END) nbs,
 SUM(bat_speed) sbs, SUM(bat_speed*bat_speed) ssbs,
 SUM(CASE WHEN swing_length IS NOT NULL THEN 1 ELSE 0 END) nsl,
 SUM(swing_length) ssl, SUM(swing_length*swing_length) sssl,
 SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END) nev,
 SUM(CASE WHEN type='X' THEN launch_speed END) sev,
 SUM(CASE WHEN type='X' THEN launch_speed*launch_speed END) ssev,
 SUM(CASE WHEN type='X' AND launch_speed>=95 THEN 1 ELSE 0 END) hh,
 SUM(CASE WHEN type='X' AND launch_speed_angle=6 THEN 1 ELSE 0 END) brl,
 SUM(CASE WHEN type='X' AND launch_angle BETWEEN 8 AND 32 THEN 1 ELSE 0 END) sweet,
 SUM(CASE WHEN bb_type='ground_ball' THEN 1 ELSE 0 END) gb,
 SUM(CASE WHEN bb_type IS NOT NULL THEN 1 ELSE 0 END) bipt,
 SUM(CASE WHEN hc_x IS NOT NULL AND (CASE WHEN stand='L' THEN 1 ELSE -1 END)*
     (180/3.14159265*ATAN2((hc_x-125.42)*2.0,(198.27-hc_y)*2.0))>15 THEN 1 ELSE 0 END) pull,
 SUM(CASE WHEN hc_x IS NOT NULL THEN 1 ELSE 0 END) sprt,
 SUM(CASE WHEN pitch_type IN ('FF','SI','FC') THEN 1 ELSE 0 END) fbs,
 SUM(CASE WHEN pitch_type IS NOT NULL THEN 1 ELSE 0 END) ptt,
 SUM(CASE WHEN {EDGE} THEN 1 ELSE 0 END) edge,
 SUM(CASE WHEN plate_x IS NOT NULL THEN 1 ELSE 0 END) loct
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R'
GROUP BY 1,2 HAVING pa>=250"""

OUTS = """CASE WHEN events IN ('grounded_into_double_play','double_play','strikeout_double_play',
   'sac_fly_double_play','sac_bunt_double_play') THEN 2 WHEN events='triple_play' THEN 3
   WHEN events IN ('field_out','strikeout','force_out','sac_fly','sac_bunt',
   'fielders_choice_out','other_out') THEN 1 ELSE 0 END"""

PITQ = f"""SELECT pitcher, game_year, SUM({OUTS}) outs, SUM(woba_denom) bf,
 SUM(CASE WHEN woba_denom=1 THEN woba_value END) wn,
 SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END) xn,
 SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
 SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END) bb, COUNT(*) pit,
 SUM(CASE WHEN {SWING} THEN 1 ELSE 0 END) sw,
 SUM(CASE WHEN {SWING} AND {WHIFF} THEN 1 ELSE 0 END) wh,
 SUM(CASE WHEN {INZ} THEN 1 ELSE 0 END) iz,
 SUM(CASE WHEN zone IS NOT NULL THEN 1 ELSE 0 END) zt,
 SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END) oz,
 SUM(CASE WHEN zone>=11 AND {SWING} THEN 1 ELSE 0 END) ozsw,
 SUM(CASE WHEN {EDGE} THEN 1 ELSE 0 END) edge,
 SUM(CASE WHEN plate_x IS NOT NULL THEN 1 ELSE 0 END) loct,
 SUM(CASE WHEN balls=0 AND strikes=0 THEN 1 ELSE 0 END) fp,
 SUM(CASE WHEN balls=0 AND strikes=0 AND (type='S' OR type='X') THEN 1 ELSE 0 END) fps,
 SUM(CASE WHEN pitch_type IN ('FF','SI') AND release_speed IS NOT NULL THEN 1 ELSE 0 END) nv,
 SUM(CASE WHEN pitch_type IN ('FF','SI') THEN release_speed END) sv,
 SUM(CASE WHEN pitch_type IN ('FF','SI') THEN release_speed*release_speed END) ssv,
 SUM(CASE WHEN arm_angle IS NOT NULL THEN 1 ELSE 0 END) naa,
 SUM(arm_angle) saa, SUM(arm_angle*arm_angle) ssaa,
 SUM(CASE WHEN release_extension IS NOT NULL THEN 1 ELSE 0 END) nex,
 SUM(release_extension) sex, SUM(release_extension*release_extension) ssex,
 SUM(CASE WHEN release_spin_rate IS NOT NULL THEN 1 ELSE 0 END) nsp,
 SUM(release_spin_rate) ssp, SUM(release_spin_rate*release_spin_rate) sssp
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R'
GROUP BY 1,2 HAVING outs>=150"""


def rate(n, d):
    if not d: return None, None
    p = n/d
    return 100*p, 100*math.sqrt(max(p*(1-p), 0)/d)


def mn(s, ss, n):
    if not n: return None, None
    m = s/n
    return m, math.sqrt(max(ss/n-m*m, 0)/n)


def hit_m(r):
    (_, _, pa, wn, xn, k, bb, pit, sw, iz, zsw, oz, ozsw, wh, fp, fpsw, tk, tksw,
     nbs, sbs, ssbs, nsl, ssl, sssl, nev, sev, ssev, hh, brl, sweet, gb, bipt,
     pull, sprt, fbs, ptt, edge, loct) = r
    return {"wOBA": (wn/pa, .30/math.sqrt(pa)), "xwOBA": (xn/pa, .22/math.sqrt(pa)),
        "K%": rate(k,pa), "BB%": rate(bb,pa), "swing%": rate(sw,pit),
        "z-swing%": rate(zsw,iz), "chase%": rate(ozsw,oz), "whiff/sw%": rate(wh,sw),
        "1st-pitch sw%": rate(fpsw,fp), "2K swing%": rate(tksw,tk),
        "bat speed": mn(sbs,ssbs,nbs), "swing length": mn(ssl,sssl,nsl),
        "exit velo": mn(sev,ssev,nev), "hard-hit%": rate(hh,nev), "barrel%": rate(brl,nev),
        "sweet-spot%": rate(sweet,nev), "GB%": rate(gb,bipt), "pull%": rate(pull,sprt),
        "FB seen%": rate(fbs,ptt), "edge% seen": rate(edge,loct)}


def pit_m(r):
    (_, _, outs, bf, wn, xn, k, bb, pit, sw, wh, iz, zt, oz, ozsw, edge, loct, fp, fps,
     nv, sv, ssv, naa, saa, ssaa, nex, sex, ssex, nsp, ssp, sssp) = r
    return {"wOBA against": (wn/bf, .30/math.sqrt(bf)), "xwOBA against": (xn/bf, .22/math.sqrt(bf)),
        "K%": rate(k,bf), "BB%": rate(bb,bf), "whiff/sw%": rate(wh,sw), "zone%": rate(iz,zt),
        "chase induced%": rate(ozsw,oz), "edge%": rate(edge,loct), "1st-pitch strike%": rate(fps,fp),
        "fastball velo": mn(sv,ssv,nv), "arm angle": mn(saa,ssaa,naa),
        "extension": mn(sex,ssex,nex), "spin rate": mn(ssp,sssp,nsp)}


def decomp(ch):
    out = {}
    for k, v in ch.items():
        if len(v) < 40: continue
        d = np.array([x[0] for x in v]); se = np.array([x[1] for x in v])
        vo = d.var(ddof=1); vn = (se**2).mean(); vt = max(vo-vn, 0)
        out[k] = {"n": len(v), "sd_obs": math.sqrt(vo), "sd_noise": math.sqrt(vn),
                  "sd_true": math.sqrt(vt), "share": vt/vo if vo else 0}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent/"data"/"statcast.db"))
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True); con.execute("PRAGMA cache_size=-400000")
    cal = {}
    keep = {}
    for label, q, fn in (("hitters", HIT, hit_m), ("pitchers", PITQ, pit_m)):
        raw = {}
        for r in con.execute(q): raw.setdefault(r[0], {})[r[1]] = r
        ch = {}
        for pid, yrs in raw.items():
            if 2025 not in yrs or 2026 not in yrs: continue
            A, B = fn(yrs[2025]), fn(yrs[2026])
            for k in A:
                if A[k][0] is None or B[k][0] is None: continue
                ch.setdefault(k, []).append((B[k][0]-A[k][0], math.hypot(A[k][1], B[k][1])))
            if label == "hitters":
                keep[pid] = (A, B)
        d = decomp(ch); cal[label] = d
        print(f"\n=== {label}: league season-over-season change ===")
        print(f"{'metric':18s} {'n':>4} {'sd obs':>8} {'sd TRUE':>8} {'signal':>7}")
        for k, v in sorted(d.items(), key=lambda x: -x[1]["share"]):
            f = "{:>8.4f}" if "OBA" in k else "{:>8.2f}"
            print(f"{k:18s} {v['n']:>4} " + f.format(v['sd_obs']) + " " +
                  f.format(v['sd_true']) + f" {100*v['share']:>6.0f}%")

    # ---- H16: is the luck gap related to a swing change?
    xs, ys = [], []
    for pid, (A, B) in keep.items():
        if None in (A["bat speed"][0], B["bat speed"][0]): continue
        gap = B["wOBA"][0] - B["xwOBA"][0]
        xs.append(B["bat speed"][0] - A["bat speed"][0]); ys.append(gap)
    x, y = np.array(xs), np.array(ys)
    r = float(np.corrcoef(x, y)[0, 1]); n = len(x)
    z = 0.5*math.log((1+r)/(1-r)); s = 1/math.sqrt(n-3)
    lo, hi = math.tanh(z-1.96*s), math.tanh(z+1.96*s)
    print(f"\n=== H16: 2026 luck gap vs 2025->2026 bat-speed change ===")
    print(f"  n={n}  r={r:+.3f}  95% [{lo:+.3f}, {hi:+.3f}]  "
          f"{'related' if lo>0 or hi<0 else 'NO relationship'}")
    cal["h16"] = {"n": n, "r": r, "ci": [lo, hi]}

    Path("output").mkdir(exist_ok=True)
    Path("output/calibration.json").write_text(json.dumps(cal, indent=1))
    print("\nwrote output/calibration.json")


if __name__ == "__main__":
    main()
