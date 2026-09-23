import sqlite3, os
con = sqlite3.connect(f"file:{os.environ['HOME']}/snap.db?mode=ro", uri=True)
con.execute("PRAGMA cache_size=-500000")
SW="(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
G=[("balls in play","type='X'",["launch_speed","launch_angle","hit_distance_sc","hc_x",
    "bb_type","launch_speed_angle","hyper_speed","estimated_woba_using_speedangle",
    "estimated_slg_using_speedangle","hit_location","if_fielding_alignment","of_fielding_alignment"]),
   ("swings",SW,["bat_speed","swing_length","attack_angle","attack_direction","swing_path_tilt",
    "intercept_ball_minus_batter_pos_x_inches","intercept_ball_minus_batter_pos_y_inches"]),
   ("every pitch","1=1",["umpire","age_bat","age_pit","n_thruorder_pitcher",
    "n_priorpa_thisgame_player_at_bat","batter_days_since_prev_game","spin_axis",
    "api_break_z_with_gravity","arm_angle","miss_distance"])]
yrs=[2023,2024,2025,2026]
R={}
for lab,pred,cols in G:
    for y in yrs:
        sel=", ".join(f'COUNT("{c}")' for c in cols)
        R[(lab,y)]=con.execute(f"SELECT COUNT(*),{sel} FROM pitches WHERE game_year=? AND game_type='R' AND ({pred})",(y,)).fetchone()
print(f"{'column':>44} {'denominator':>14} " + " ".join(f"{y:>8}" for y in yrs))
for lab,pred,cols in G:
    print(f"  --- denominator size: " + "  ".join(f"{y}: {R[(lab,y)][0]:,}" for y in yrs))
    for i,c in enumerate(cols):
        cells=[]
        for y in yrs:
            r=R[(lab,y)]
            cells.append(f"{100*r[i+1]/r[0]:>7.1f}%" if r[0] else "    n/a")
        print(f"{c:>44} {lab:>14} " + " ".join(cells))
print("\nbb_type distribution, 2025 regular season")
for t,n in con.execute("SELECT bb_type, COUNT(*) FROM pitches WHERE game_year=2025 AND game_type='R' AND type='X' GROUP BY 1 ORDER BY 2 DESC"):
    print(f"  {str(t):>14} {n:>8,}")
print("\nfielding alignment values, 2025")
for c in ("if_fielding_alignment","of_fielding_alignment"):
    print(f"  {c}:")
    for v,n in con.execute(f"SELECT {c}, COUNT(*) FROM pitches WHERE game_year=2025 AND game_type='R' AND type='X' GROUP BY 1 ORDER BY 2 DESC LIMIT 6"):
        print(f"     {str(v):>22} {n:>8,}")
