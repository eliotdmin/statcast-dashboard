#!/usr/bin/env python3
"""Two league-wide questions the Mets roster is too small to answer.

    python3 contact_quality.py --db data/statcast.db

A. DOES A FASTER SWING PRODUCE BETTER OUTCOMES?
   Faster swings should hit the ball harder. Whether they produce better RESULTS
   is a different question, because speed may cost contact and launch angle. Run
   both league-wide and WITHIN hitter -- a hitter's own faster-than-usual swings
   against his own baseline -- so the answer is not just "good hitters swing
   hard".

B. WHAT EXPLAINS wOBA MINUS xwOBA BESIDES LUCK?
   The dashboard treats that gap as luck. xwOBA is a function of exit velocity
   and launch angle ONLY, so anything systematic that it cannot see lands in the
   residual: a hitter's speed, where he sprays the ball, his batted-ball mix, the
   park. Regressing the gap on those says how much of "luck" is actually
   structure -- and any variance they explain is variance the dashboard is
   currently mislabelling.
"""
import argparse, json, math, sqlite3
from collections import defaultdict
from pathlib import Path
import numpy as np

OUT = Path(__file__).parent / "output" / "contact_quality.json"
SWING = "(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
YEARS = "(2023,2024,2025)"          # 2026 excluded: ABS changes the zone


def part_a(con, report):
    print("=== A1. league: bat speed vs what happens (batted balls) ===", flush=True)
    rows = con.execute(f"""
        SELECT CAST(bat_speed/3 AS INT)*3 b, COUNT(*), AVG(launch_speed),
               AVG(hit_distance_sc), AVG(estimated_woba_using_speedangle),
               AVG(woba_value), AVG(launch_angle),
               AVG(CASE WHEN launch_speed_angle=6 THEN 1.0 ELSE 0.0 END)
        FROM pitches
        WHERE game_year IN {YEARS} AND game_type='R' AND type='X'
          AND bat_speed IS NOT NULL AND launch_speed IS NOT NULL
        GROUP BY b HAVING COUNT(*)>2000 ORDER BY b""").fetchall()
    print(f"{'bat speed':>10} {'n':>9} {'EV':>7} {'dist':>7} {'xwOBA':>7} {'wOBA':>7} {'LA':>6} {'barrel':>7}")
    A1 = []
    for b, n, ev, dist, xw, wo, la, brl in rows:
        print(f"{b:>4}-{b+2:<5} {n:>9,} {ev:>7.1f} {dist or 0:>7.0f} {xw or 0:>7.3f} "
              f"{wo or 0:>7.3f} {la or 0:>6.1f} {100*brl:>6.1f}%")
        A1.append({"bin": b, "n": n, "ev": ev, "dist": dist, "xwoba": xw,
                   "woba": wo, "la": la, "barrel": 100*brl})
    report["A1_league_batted"] = A1

    print("\n=== A2. league: bat speed vs whiff (all swings) ===", flush=True)
    rows = con.execute(f"""
        SELECT CAST(bat_speed/3 AS INT)*3 b, COUNT(*),
               100.0*AVG(CASE WHEN description LIKE 'swinging_strike%' OR description='foul_tip'
                              THEN 1.0 ELSE 0.0 END)
        FROM pitches
        WHERE game_year IN {YEARS} AND game_type='R' AND {SWING} AND bat_speed IS NOT NULL
        GROUP BY b HAVING COUNT(*)>2000 ORDER BY b""").fetchall()
    A2 = [{"bin": b, "n": n, "whiff": w} for b, n, w in rows]
    for r in A2:
        print(f"{r['bin']:>4}-{r['bin']+2:<5} {r['n']:>9,} whiff {r['whiff']:>5.1f}%")
    report["A2_league_whiff"] = A2

    print("\n=== A3. WITHIN hitter: his own fast swings vs his own slow ones ===", flush=True)
    # z-score bat speed within hitter-season, then bucket. Removes "good hitters
    # swing hard" entirely -- every comparison is a hitter against himself.
    cur = con.execute(f"""
        SELECT batter, game_year, bat_speed, launch_speed, hit_distance_sc,
               estimated_woba_using_speedangle, woba_value
        FROM pitches
        WHERE game_year IN {YEARS} AND game_type='R' AND type='X'
          AND bat_speed IS NOT NULL AND launch_speed IS NOT NULL""")
    by = defaultdict(list)
    for bat, yr, bs, ev, dist, xw, wo in cur:
        by[(bat, yr)].append((bs, ev, dist, xw, wo))
    buckets = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0, 0])
    for k, v in by.items():
        if len(v) < 100: continue
        speeds = np.array([x[0] for x in v]); m, s = speeds.mean(), speeds.std()
        if s <= 0: continue
        for bs, ev, dist, xw, wo in v:
            z = (bs - m) / s
            b = max(-3, min(3, int(round(z))))
            t = buckets[b]
            t[0] += 1; t[1] += ev
            if dist is not None: t[2] += dist; t[5] += 1
            if xw is not None: t[3] += xw
            if wo is not None: t[4] += wo
    A3 = []
    print(f"{'own z':>7} {'n':>9} {'EV':>7} {'dist':>7} {'xwOBA':>7} {'wOBA':>7}")
    for b in sorted(buckets):
        n, ev, dist, xw, wo, dn = buckets[b]
        if n < 3000: continue
        A3.append({"z": b, "n": n, "ev": ev/n, "dist": dist/max(dn,1),
                   "xwoba": xw/n, "woba": wo/n})
        print(f"{b:>+7} {n:>9,} {ev/n:>7.1f} {dist/max(dn,1):>7.0f} {xw/n:>7.3f} {wo/n:>7.3f}")
    report["A3_within_hitter"] = A3


def part_b(con, report):
    print("\n=== B. what explains wOBA minus xwOBA? ===", flush=True)
    # spray angle: 0 = centre, + = toward right field. Pull is negative for a
    # righty and positive for a lefty, so sign-correct by stand.
    rows = con.execute(f"""
        SELECT batter, game_year,
               SUM(woba_value)/SUM(woba_denom) woba,
               -- xwOBA PER PLATE APPEARANCE, not on contact only. Comparing full
               -- wOBA (which counts strikeouts as zero) against a contact-only
               -- xwOBA manufactures a huge negative gap for every high-strikeout
               -- hitter, and the regression then "explains" the gap with the
               -- strikeout rate that created it. Savant populates xwOBA on
               -- PA-ending non-contact events at their linear weight, and the
               -- COALESCE mirrors analyze.pa_level for any vintage that does not.
               AVG(CASE WHEN woba_denom=1 THEN
                   COALESCE(estimated_woba_using_speedangle, woba_value) END) xw_con,
               SUM(CASE WHEN type='X' THEN 1 ELSE 0 END) bip,
               SUM(woba_denom) pa,
               AVG(CASE WHEN type='X' THEN launch_speed END) ev,
               AVG(CASE WHEN type='X' THEN launch_angle END) la,
               AVG(CASE WHEN bb_type='ground_ball' THEN 1.0 WHEN bb_type IS NOT NULL THEN 0.0 END) gb,
               AVG(CASE WHEN bb_type='line_drive' THEN 1.0 WHEN bb_type IS NOT NULL THEN 0.0 END) ld,
               AVG(CASE WHEN hc_x IS NOT NULL AND hc_y IS NOT NULL THEN
                   CASE WHEN (CASE WHEN stand='L' THEN 1 ELSE -1 END) *
                        (180/3.14159265*ATAN2((hc_x-125.42)*2.0,(198.27-hc_y)*2.0)) > 15
                        THEN 1.0 ELSE 0.0 END END) pull,
               100.0*AVG(CASE WHEN events='strikeout' THEN 1.0
                              WHEN woba_denom=1 THEN 0.0 END) k_rate
        FROM pitches
        WHERE game_year IN {YEARS} AND game_type='R' AND woba_denom IS NOT NULL
        GROUP BY 1,2 HAVING pa >= 300 AND bip >= 150""").fetchall()

    # xwOBA per PA needs the non-contact events folded in at their actual value,
    # which is what analyze.pa_level does; approximate it the same way.
    recs = []
    for bat, yr, woba, xw_con, bip, pa, ev, la, gb, ld, pull, kr in rows:
        if None in (woba, xw_con, ev, la, gb, ld, pull, kr): continue
        recs.append({"pid": bat, "yr": yr, "gap": woba - xw_con, "ev": ev, "la": la,
                     "gb": gb, "ld": ld, "pull": pull, "k": kr, "pa": pa})
    print(f"{len(recs)} player-seasons with 300+ PA")

    def corr(a, b):
        a, b = np.array(a), np.array(b)
        return float(np.corrcoef(a, b)[0, 1])

    g = [r["gap"] for r in recs]
    preds = {"ground-ball rate": "gb", "line-drive rate": "ld", "pull rate": "pull",
             "avg launch angle": "la", "avg exit velocity": "ev", "strikeout rate": "k"}
    print(f"\n{'predictor':22s} {'corr with gap':>14}")
    B = {"n": len(recs), "corr": {}}
    for label, k in preds.items():
        c = corr([r[k] for r in recs], g)
        B["corr"][label] = c
        print(f"{label:22s} {c:>+14.3f}")

    X = np.column_stack([[r[k] for r in recs] for k in preds.values()] + [np.ones(len(recs))])
    y = np.array(g)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ beta
    r2 = 1 - ((y-pred)**2).sum()/((y-y.mean())**2).sum()
    B["r2"] = float(r2)
    B["sd_gap"] = float(np.std(y))
    print(f"\nmultiple regression R^2 = {r2:.3f}")
    print(f"so {100*r2:.0f}% of the between-player 'luck' gap is explained by batted-ball "
          f"profile alone\nsd of gap = {np.std(y):.4f} wOBA")
    report["B_gap"] = B


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent/"data"/"statcast.db"))
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-400000")
    report = {}
    part_a(con, report); part_b(con, report)
    OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(report, indent=1))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
