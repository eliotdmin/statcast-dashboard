#!/usr/bin/env python3
"""Hitter-month panel with everything needed to ask what predicts next period's wOBA.

    python3 extract_monthly.py --db data/statcast.db --out output/hitter_months.csv

One row per (batter, season, calendar month), regular season only. Counts and sums
rather than rates, so any window length can be composed by summing rows.
"""
import argparse, csv, sqlite3
from pathlib import Path

SW   = "(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
WH   = "(description LIKE 'swinging_strike%' OR description='foul_tip')"
# positive spray = pull side, for either handedness
SPRAY = ("(CASE WHEN stand='L' THEN 1 ELSE -1 END) * "
         "(180/3.14159265*ATAN2((hc_x-125.42)*2.0,(198.27-hc_y)*2.0))")
FB   = "pitch_type IN ('FF','SI','FC')"
OFF  = "pitch_type IN ('CH','FS','FO','SC')"
BRK  = "pitch_type IN ('SL','ST','CU','KC','SV','CS')"

Q = f"""
SELECT batter, game_year, substr(game_date,1,7) ym, MAX(age_bat) age,
 SUM(woba_denom) pa,
 SUM(CASE WHEN woba_denom=1 THEN woba_value END) woba_num,
 SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END) xwoba_num,
 SUM(CASE WHEN woba_denom=1 THEN estimated_slg_using_speedangle END) xslg_num,
 SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
 SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END) bb,
 SUM(CASE WHEN events='hit_by_pitch' THEN 1 ELSE 0 END) hbp,
 COUNT(*) pitches,
 SUM(CASE WHEN {SW} THEN 1 ELSE 0 END) sw,
 SUM(CASE WHEN {SW} AND {WH} THEN 1 ELSE 0 END) whiff,
 SUM(CASE WHEN zone BETWEEN 1 AND 9 THEN 1 ELSE 0 END) iz,
 SUM(CASE WHEN zone BETWEEN 1 AND 9 AND {SW} THEN 1 ELSE 0 END) izsw,
 SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END) oz,
 SUM(CASE WHEN zone>=11 AND {SW} THEN 1 ELSE 0 END) ozsw,
 SUM(CASE WHEN balls=0 AND strikes=0 THEN 1 ELSE 0 END) fp,
 SUM(CASE WHEN balls=0 AND strikes=0 AND {SW} THEN 1 ELSE 0 END) fpsw,
 SUM(CASE WHEN strikes=2 THEN 1 ELSE 0 END) tk,
 SUM(CASE WHEN strikes=2 AND {SW} THEN 1 ELSE 0 END) tksw,
 SUM(CASE WHEN {FB} THEN 1 ELSE 0 END) fb_seen,
 SUM(CASE WHEN {OFF} THEN 1 ELSE 0 END) off_seen,
 SUM(CASE WHEN {BRK} THEN 1 ELSE 0 END) brk_seen,
 SUM(CASE WHEN pitch_type IS NOT NULL THEN 1 ELSE 0 END) pt_seen,
 SUM(CASE WHEN release_speed IS NOT NULL THEN release_speed END) sum_pvelo,
 SUM(CASE WHEN release_speed IS NOT NULL THEN 1 ELSE 0 END) n_pvelo,
 -- swing tracking
 SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END) n_bs,
 SUM(bat_speed) sum_bs, SUM(bat_speed*bat_speed) ss_bs,
 SUM(swing_length) sum_sl, SUM(swing_length*swing_length) ss_sl,
 SUM(CASE WHEN attack_angle IS NOT NULL THEN 1 ELSE 0 END) n_aa,
 SUM(attack_angle) sum_aa, SUM(attack_angle*attack_angle) ss_aa,
 SUM(attack_direction) sum_ad, SUM(attack_direction*attack_direction) ss_ad,
 SUM(swing_path_tilt) sum_tilt,
 SUM(CASE WHEN intercept_ball_minus_batter_pos_y_inches IS NOT NULL THEN 1 ELSE 0 END) n_ic,
 SUM(intercept_ball_minus_batter_pos_y_inches) sum_icy,
 SUM(intercept_ball_minus_batter_pos_x_inches) sum_icx,
 -- batted balls
 SUM(CASE WHEN type='X' THEN 1 ELSE 0 END) bip,
 SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END) n_ev,
 SUM(CASE WHEN type='X' THEN launch_speed END) sum_ev,
 SUM(CASE WHEN type='X' THEN launch_speed*launch_speed END) ss_ev,
 SUM(CASE WHEN type='X' THEN launch_angle END) sum_la,
 SUM(CASE WHEN type='X' THEN launch_angle*launch_angle END) ss_la,
 SUM(CASE WHEN type='X' AND launch_speed>=95 THEN 1 ELSE 0 END) hardhit,
 SUM(CASE WHEN type='X' AND launch_speed_angle=6 THEN 1 ELSE 0 END) barrel,
 SUM(CASE WHEN type='X' AND launch_angle BETWEEN 8 AND 32 THEN 1 ELSE 0 END) sweet,
 SUM(CASE WHEN bb_type='ground_ball' THEN 1 ELSE 0 END) gb,
 SUM(CASE WHEN bb_type='fly_ball' THEN 1 ELSE 0 END) fbb,
 SUM(CASE WHEN bb_type='line_drive' THEN 1 ELSE 0 END) ld,
 SUM(CASE WHEN bb_type='popup' THEN 1 ELSE 0 END) pop,
 SUM(CASE WHEN bb_type IS NOT NULL THEN 1 ELSE 0 END) n_bbt,
 SUM(CASE WHEN hc_x IS NOT NULL THEN 1 ELSE 0 END) n_spray,
 SUM(CASE WHEN hc_x IS NOT NULL THEN {SPRAY} END) sum_spray,
 SUM(CASE WHEN hc_x IS NOT NULL THEN ({SPRAY})*({SPRAY}) END) ss_spray,
 SUM(CASE WHEN hc_x IS NOT NULL AND {SPRAY}>15 THEN 1 ELSE 0 END) pull,
 SUM(CASE WHEN type='X' AND hit_distance_sc IS NOT NULL THEN hit_distance_sc END) sum_dist,
 SUM(CASE WHEN type='X' AND hit_distance_sc IS NOT NULL THEN 1 ELSE 0 END) n_dist,
 -- outcomes that reveal speed / defence
 SUM(CASE WHEN events='single' AND bb_type='ground_ball' THEN 1 ELSE 0 END) inf_single,
 SUM(CASE WHEN events IN ('grounded_into_double_play','double_play') THEN 1 ELSE 0 END) gidp,
 SUM(CASE WHEN events='triple' THEN 1 ELSE 0 END) triple,
 -- context
 SUM(CASE WHEN inning_topbot='Bot' AND woba_denom=1 THEN 1 ELSE 0 END) home_pa,
 SUM(CASE WHEN type='X' AND if_fielding_alignment='Strategic' THEN 1 ELSE 0 END) if_strat,
 SUM(CASE WHEN type='X' AND if_fielding_alignment='Infield shade' THEN 1 ELSE 0 END) if_shade,
 SUM(CASE WHEN type='X' AND of_fielding_alignment='Strategic' THEN 1 ELSE 0 END) of_strat,
 MAX(stand) stand
FROM pitches
WHERE game_type='R' AND game_year BETWEEN 2023 AND 2026
GROUP BY 1,2,3
HAVING pa >= 15
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent/"data"/"statcast.db"))
    ap.add_argument("--out", default="output/hitter_months.csv")
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-600000")
    cur = con.execute(Q)
    cols = [d[0] for d in cur.description]
    Path(a.out).parent.mkdir(exist_ok=True)
    n = 0
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(cols)
        for r in cur:
            w.writerow(["" if v is None else v for v in r]); n += 1
    # player names, separate small file
    with open(str(Path(a.out).with_name("batter_names.csv")), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["player_id", "name"])
        for pid, nm in con.execute("SELECT DISTINCT player_id, player_name FROM expected_stats "
                                   "WHERE player_type='batter'"):
            w.writerow([pid, nm])
    print(f"wrote {a.out}: {n:,} hitter-months, {len(cols)} columns")


if __name__ == "__main__":
    main()
