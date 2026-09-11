#!/usr/bin/env python3
"""Full 2025 vs 2026 change profile per player: decisions, mechanics, results, and how they are pitched.

    python3 profiles.py --db data/statcast.db --team NYM

Hitters qualify at 600+ PA combined across the two seasons, pitchers at 100+ IP
combined. Every change carries a standard error, because the whole point of the
stabilisation work is that a change you cannot distinguish from zero is not a
change.

Rates use SE = sqrt(p(1-p)/n); means use the sample variance from the same pass.
SE(delta) = sqrt(se_a^2 + se_b^2).

2026 is a partial season, so every 2026 n is smaller. That widens intervals; it
does not bias the point estimates.
"""
import argparse, json, math, sqlite3
from pathlib import Path

SWING = "(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
WHIFF = "(description LIKE 'swinging_strike%' OR description='foul_tip')"
BAT = "CASE WHEN inning_topbot='Top' THEN away_team ELSE home_team END"
PIT = "CASE WHEN inning_topbot='Top' THEN home_team ELSE away_team END"
INZONE = "(zone BETWEEN 1 AND 9)"
EDGE = "(ABS(plate_x) BETWEEN 0.6 AND 1.1)"
OUTS = """CASE WHEN events IN ('grounded_into_double_play','double_play','strikeout_double_play',
             'sac_fly_double_play','sac_bunt_double_play') THEN 2
          WHEN events='triple_play' THEN 3
          WHEN events IN ('field_out','strikeout','force_out','sac_fly','sac_bunt',
             'fielders_choice_out','other_out') THEN 1 ELSE 0 END"""


def rate(num, den):
    """(value, se) for a proportion, as percentages."""
    if not den: return None, None
    p = num / den
    return 100 * p, 100 * math.sqrt(max(p * (1 - p), 0) / den)


def mean(s, ss, n):
    if not n: return None, None
    m = s / n
    return m, math.sqrt(max(ss / n - m * m, 0) / n)


def delta(a, b):
    """a=(val,se) 2025, b=(val,se) 2026 -> dict with change, se, significance."""
    if a[0] is None or b[0] is None: return None
    d = b[0] - a[0]
    se = math.hypot(a[1] or 0, b[1] or 0)
    return {"y25": a[0], "y26": b[0], "d": d, "se": se, "sig": abs(d) > 1.96 * se}


HIT_Q = f"""
SELECT batter, game_year,
  SUM(woba_denom) pa,
  SUM(CASE WHEN woba_denom=1 THEN woba_value END) woba_num,
  SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END) xw_num,
  SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
  SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END) bb,
  COUNT(*) pitches,
  SUM(CASE WHEN {SWING} THEN 1 ELSE 0 END) swings,
  SUM(CASE WHEN {INZONE} THEN 1 ELSE 0 END) inzone,
  SUM(CASE WHEN {INZONE} AND {SWING} THEN 1 ELSE 0 END) z_sw,
  SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END) oz,
  SUM(CASE WHEN zone>=11 AND {SWING} THEN 1 ELSE 0 END) oz_sw,
  SUM(CASE WHEN {SWING} AND {WHIFF} THEN 1 ELSE 0 END) whiffs,
  SUM(CASE WHEN balls=0 AND strikes=0 THEN 1 ELSE 0 END) fp,
  SUM(CASE WHEN balls=0 AND strikes=0 AND {SWING} THEN 1 ELSE 0 END) fp_sw,
  SUM(CASE WHEN strikes=2 THEN 1 ELSE 0 END) two_k,
  SUM(CASE WHEN strikes=2 AND {SWING} THEN 1 ELSE 0 END) two_k_sw,
  SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END) n_bs,
  SUM(bat_speed) s_bs, SUM(bat_speed*bat_speed) ss_bs,
  SUM(CASE WHEN swing_length IS NOT NULL THEN 1 ELSE 0 END) n_sl,
  SUM(swing_length) s_sl, SUM(swing_length*swing_length) ss_sl,
  SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END) n_ev,
  SUM(CASE WHEN type='X' THEN launch_speed END) s_ev,
  SUM(CASE WHEN type='X' THEN launch_speed*launch_speed END) ss_ev,
  SUM(CASE WHEN type='X' AND launch_speed>=95 THEN 1 ELSE 0 END) hh,
  SUM(CASE WHEN type='X' AND launch_speed_angle=6 THEN 1 ELSE 0 END) brl,
  SUM(CASE WHEN type='X' AND launch_angle BETWEEN 8 AND 32 THEN 1 ELSE 0 END) sweet,
  SUM(CASE WHEN bb_type='ground_ball' THEN 1 ELSE 0 END) gb,
  SUM(CASE WHEN bb_type IS NOT NULL THEN 1 ELSE 0 END) bip_t,
  SUM(CASE WHEN hc_x IS NOT NULL AND
       (CASE WHEN stand='L' THEN 1 ELSE -1 END)*
       (180/3.14159265*ATAN2((hc_x-125.42)*2.0,(198.27-hc_y)*2.0))>15 THEN 1 ELSE 0 END) pull,
  SUM(CASE WHEN hc_x IS NOT NULL THEN 1 ELSE 0 END) spray_t,
  SUM(CASE WHEN pitch_type IN ('FF','SI','FC') THEN 1 ELSE 0 END) fb_seen,
  SUM(CASE WHEN pitch_type IS NOT NULL THEN 1 ELSE 0 END) pt_t,
  SUM(CASE WHEN {EDGE} THEN 1 ELSE 0 END) edge,
  SUM(CASE WHEN plate_x IS NOT NULL THEN 1 ELSE 0 END) loc_t
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R' AND {BAT}=?
GROUP BY 1,2"""

PIT_Q = f"""
SELECT pitcher, game_year, SUM({OUTS}) outs, SUM(woba_denom) bf,
  SUM(CASE WHEN woba_denom=1 THEN woba_value END) woba_num,
  SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END) xw_num,
  SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
  SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END) bb,
  COUNT(*) pitches,
  SUM(CASE WHEN {SWING} THEN 1 ELSE 0 END) swings,
  SUM(CASE WHEN {SWING} AND {WHIFF} THEN 1 ELSE 0 END) whiffs,
  SUM(CASE WHEN {INZONE} THEN 1 ELSE 0 END) inzone,
  SUM(CASE WHEN zone IS NOT NULL THEN 1 ELSE 0 END) zone_t,
  SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END) oz,
  SUM(CASE WHEN zone>=11 AND {SWING} THEN 1 ELSE 0 END) oz_sw,
  SUM(CASE WHEN {EDGE} THEN 1 ELSE 0 END) edge,
  SUM(CASE WHEN plate_x IS NOT NULL THEN 1 ELSE 0 END) loc_t,
  SUM(CASE WHEN balls=0 AND strikes=0 THEN 1 ELSE 0 END) fp,
  SUM(CASE WHEN balls=0 AND strikes=0 AND (type='S' OR type='X') THEN 1 ELSE 0 END) fp_s,
  SUM(CASE WHEN pitch_type IN ('FF','SI') AND release_speed IS NOT NULL THEN 1 ELSE 0 END) n_v,
  SUM(CASE WHEN pitch_type IN ('FF','SI') THEN release_speed END) s_v,
  SUM(CASE WHEN pitch_type IN ('FF','SI') THEN release_speed*release_speed END) ss_v,
  SUM(CASE WHEN arm_angle IS NOT NULL THEN 1 ELSE 0 END) n_aa,
  SUM(arm_angle) s_aa, SUM(arm_angle*arm_angle) ss_aa,
  SUM(CASE WHEN release_extension IS NOT NULL THEN 1 ELSE 0 END) n_ext,
  SUM(release_extension) s_ext, SUM(release_extension*release_extension) ss_ext,
  SUM(CASE WHEN release_spin_rate IS NOT NULL THEN 1 ELSE 0 END) n_sp,
  SUM(release_spin_rate) s_sp, SUM(release_spin_rate*release_spin_rate) ss_sp
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R' AND {PIT}=?
GROUP BY 1,2"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent/"data"/"statcast.db"))
    ap.add_argument("--team", default="NYM")
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-400000")

    bn = {}
    for pid, nm in con.execute("SELECT player_id, player_name FROM expected_stats WHERE player_type='batter'"):
        bn[pid] = nm
    pn = {}
    for pid, nm in con.execute("SELECT player_id, player_name FROM expected_stats WHERE player_type='pitcher'"):
        pn[pid] = nm

    # ---------- hitters ----------
    raw = {}
    for r in con.execute(HIT_Q, (a.team,)):
        raw.setdefault(r[0], {})[r[1]] = r
    hitters = []
    for pid, yrs in raw.items():
        if 2025 not in yrs or 2026 not in yrs: continue
        if (yrs[2025][2] or 0) + (yrs[2026][2] or 0) < 600: continue
        def m(y):
            (_, _, pa, wn, xn, k, bb, pit, sw, iz, zsw, oz, ozsw, wh, fp, fpsw, tk, tksw,
             nbs, sbs, ssbs, nsl, ssl, sssl, nev, sev, ssev, hh, brl, sweet, gb, bipt,
             pull, sprt, fbs, ptt, edge, loct) = yrs[y]
            return {
              "pa": pa, "pitches": pit,
              "wOBA": (wn/pa*1, 0.30/math.sqrt(pa)) if pa else (None,None),
              "xwOBA": (xn/pa*1, 0.22/math.sqrt(pa)) if pa else (None,None),
              "K%": rate(k, pa), "BB%": rate(bb, pa),
              "swing%": rate(sw, pit), "z-swing%": rate(zsw, iz), "chase%": rate(ozsw, oz),
              "whiff/sw%": rate(wh, sw), "1st-pitch sw%": rate(fpsw, fp),
              "2K swing%": rate(tksw, tk),
              "bat speed": mean(sbs, ssbs, nbs), "swing length": mean(ssl, sssl, nsl),
              "exit velo": mean(sev, ssev, nev),
              "hard-hit%": rate(hh, nev), "barrel%": rate(brl, nev), "sweet-spot%": rate(sweet, nev),
              "GB%": rate(gb, bipt), "pull%": rate(pull, sprt),
              "FB seen%": rate(fbs, ptt), "edge% seen": rate(edge, loct),
            }
        A, B = m(2025), m(2026)
        prof = {"name": bn.get(pid, str(pid)), "pid": pid,
                "pa": (A["pa"], B["pa"]), "metrics": {}}
        for k in A:
            if k in ("pa", "pitches"): continue
            d = delta(A[k], B[k])
            if d: prof["metrics"][k] = d
        hitters.append(prof)
    hitters.sort(key=lambda h: -(h["pa"][0] + h["pa"][1]))

    # ---------- pitchers ----------
    raw = {}
    for r in con.execute(PIT_Q, (a.team,)):
        raw.setdefault(r[0], {})[r[1]] = r
    pitchers = []
    for pid, yrs in raw.items():
        if 2025 not in yrs or 2026 not in yrs: continue
        ip = ((yrs[2025][2] or 0) + (yrs[2026][2] or 0)) / 3
        if ip < 100: continue
        def m(y):
            (_, _, outs, bf, wn, xn, k, bb, pit, sw, wh, iz, zt, oz, ozsw, edge, loct,
             fp, fps, nv, sv, ssv, naa, saa, ssaa, nex, sex, ssex, nsp, ssp, sssp) = yrs[y]
            return {
              "bf": bf, "ip": (outs or 0)/3,
              "wOBA against": (wn/bf, 0.30/math.sqrt(bf)) if bf else (None,None),
              "xwOBA against": (xn/bf, 0.22/math.sqrt(bf)) if bf else (None,None),
              "K%": rate(k, bf), "BB%": rate(bb, bf),
              "whiff/sw%": rate(wh, sw), "zone%": rate(iz, zt), "chase induced%": rate(ozsw, oz),
              "edge%": rate(edge, loct), "1st-pitch strike%": rate(fps, fp),
              "fastball velo": mean(sv, ssv, nv), "arm angle": mean(saa, ssaa, naa),
              "extension": mean(sex, ssex, nex), "spin rate": mean(ssp, sssp, nsp),
            }
        A, B = m(2025), m(2026)
        prof = {"name": pn.get(pid, str(pid)), "pid": pid,
                "ip": (A["ip"], B["ip"]), "metrics": {}}
        for k in A:
            if k in ("bf", "ip"): continue
            d = delta(A[k], B[k])
            if d: prof["metrics"][k] = d
        # arsenal
        ars = {}
        for y in (2025, 2026):
            rs = con.execute("""SELECT pitch_type, COUNT(*) FROM pitches WHERE pitcher=? AND game_year=?
                AND game_type='R' AND pitch_type IS NOT NULL GROUP BY 1""", (pid, y)).fetchall()
            t = sum(x[1] for x in rs) or 1
            ars[y] = {p: 100*c/t for p, c in rs}
        prof["arsenal"] = {p: {"y25": ars[2025].get(p, 0), "y26": ars[2026].get(p, 0),
                               "d": ars[2026].get(p, 0)-ars[2025].get(p, 0)}
                           for p in set(ars[2025]) | set(ars[2026])}
        pitchers.append(prof)
    pitchers.sort(key=lambda p: -(p["ip"][0] + p["ip"][1]))

    out = {"team": a.team, "hitters": hitters, "pitchers": pitchers}
    Path("output").mkdir(exist_ok=True)
    Path("output/profiles.json").write_text(json.dumps(out, indent=1, default=float))

    print(f"{a.team}: {len(hitters)} hitters (600+ PA), {len(pitchers)} pitchers (100+ IP)\n")
    for h in hitters:
        sig = [(k, v) for k, v in h["metrics"].items() if v["sig"]]
        print(f"--- {h['name']}  ({h['pa'][0]:.0f} + {h['pa'][1]:.0f} PA) — "
              f"{len(sig)} of {len(h['metrics'])} changes real")
        for k, v in sorted(sig, key=lambda x: -abs(x[1]["d"]/x[1]["se"])):
            print(f"      {k:16s} {v['y25']:>8.2f} -> {v['y26']:>8.2f}  ({v['d']:+.2f})")
    print()
    for p in pitchers:
        sig = [(k, v) for k, v in p["metrics"].items() if v["sig"]]
        big = sorted((v["d"], k) for k, v in p["arsenal"].items() if abs(v["d"]) >= 5)
        print(f"--- {p['name']}  ({p['ip'][0]:.0f} + {p['ip'][1]:.0f} IP) — "
              f"{len(sig)} of {len(p['metrics'])} changes real")
        for k, v in sorted(sig, key=lambda x: -abs(x[1]["d"]/x[1]["se"])):
            print(f"      {k:18s} {v['y25']:>8.2f} -> {v['y26']:>8.2f}  ({v['d']:+.2f})")
        if big:
            print("      arsenal: " + ", ".join(f"{k}{d:+.0f}pp" for d, k in big))
    print("\nwrote output/profiles.json")


if __name__ == "__main__":
    main()
