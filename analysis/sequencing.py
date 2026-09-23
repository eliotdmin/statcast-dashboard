#!/usr/bin/env python3
"""Does mixing pitches actually work? Pitch-type value and sequencing effects.

    python3 sequencing.py --db data/statcast.db --years 2023 2024 2025 2026

TWO QUESTIONS, ONE OF WHICH IS HARDER THAN IT LOOKS

1. How does each pitch type perform? Straightforward: run value per 100 pitches,
   whiff rate, and xwOBA on contact, by pitch type.

2. Is a pitch harder to hit when it DIFFERS from the pitch before it? This is the
   "mix up your pitches" folk belief, and testing it naively gives the wrong
   answer, because the sequence is not randomly assigned.

THE CONFOUND, stated plainly:
   A pitcher throws a different pitch in different situations. He goes to the
   breaking ball ahead in the count, and back to the fastball behind it. Hitters
   perform far better in hitter's counts. So "pitch after a different pitch"
   silently over-samples pitcher's counts, and any raw comparison mostly measures
   THE COUNT, not the sequence.

   The same-count comparison below therefore holds (balls, strikes) fixed and
   compares like with like WITHIN each count state, then pools with each count
   weighted by its own sample. What survives that is the sequencing effect;
   what does not survive it was the count all along.

A second confound this does NOT fully fix: pitchers who mix more are different
pitchers. A true causal estimate would need within-pitcher variation, which is
noted where the numbers are reported rather than papered over.
"""
import argparse
import json
import sqlite3
from pathlib import Path

OUT = Path(__file__).parent / "output" / "sequencing.json"

# delta_run_exp is from the batting team's perspective, so a pitcher wants it
# negative. Sign is flipped here so "higher is better for the pitcher" reads
# naturally in every table below.
BASE = """
    SELECT p.pitch_type, p.balls, p.strikes,
           p.delta_run_exp, p.description, p.type,
           p.estimated_woba_using_speedangle AS xw,
           p.release_speed, p.stand, p.p_throws,
           prev.pitch_type AS prev_type, prev.release_speed AS prev_speed
    FROM pitches p
    LEFT JOIN pitches prev
      ON prev.game_pk = p.game_pk
     AND prev.at_bat_number = p.at_bat_number
     AND prev.pitch_number = p.pitch_number - 1
    WHERE p.game_type = 'R' AND p.game_year IN ({years})
      AND p.pitch_type IS NOT NULL AND p.delta_run_exp IS NOT NULL
"""


def q(con, sql, params=()):
    return con.execute(sql, params).fetchall()


def pitch_type_value(con, years):
    """Run value per 100 pitches, whiff rate and xwOBA on contact, by pitch type."""
    y = ",".join(str(i) for i in years)
    rows = q(con, f"""
        SELECT pitch_type,
               COUNT(*) n,
               -100.0 * AVG(delta_run_exp) rv100,
               100.0 * AVG(CASE WHEN description LIKE 'swinging_strike%' OR description='foul_tip'
                                THEN 1.0 ELSE 0.0 END)
                     / NULLIF(AVG(CASE WHEN description LIKE '%swing%' OR description LIKE 'foul%'
                                       OR type='X' THEN 1.0 ELSE 0.0 END), 0) whiff_per_swing,
               AVG(CASE WHEN type='X' THEN estimated_woba_using_speedangle END) xwoba_con,
               AVG(release_speed) velo
        FROM pitches
        WHERE game_type='R' AND game_year IN ({y}) AND pitch_type IS NOT NULL
          AND delta_run_exp IS NOT NULL
        GROUP BY pitch_type HAVING n > 20000 ORDER BY rv100 DESC""")
    return [{"pitch_type": r[0], "n": r[1], "rv100": round(r[2], 3),
             "whiff_per_swing": round(r[3], 1) if r[3] else None,
             "xwoba_contact": round(r[4], 4) if r[4] else None,
             "velo": round(r[5], 1) if r[5] else None} for r in rows]


def sequencing(con, years):
    """Same pitch vs different pitch, raw and holding the count fixed."""
    y = ",".join(str(i) for i in years)
    sql = f"""
        SELECT p.balls, p.strikes,
               CASE WHEN prev.pitch_type = p.pitch_type THEN 'same' ELSE 'different' END seq,
               COUNT(*) n,
               -100.0 * AVG(p.delta_run_exp) rv100,
               100.0 * AVG(CASE WHEN p.description LIKE 'swinging_strike%'
                                 OR p.description='foul_tip' THEN 1.0 ELSE 0.0 END) whiff_rate
        FROM pitches p
        JOIN pitches prev
          ON prev.game_pk = p.game_pk AND prev.at_bat_number = p.at_bat_number
         AND prev.pitch_number = p.pitch_number - 1
        WHERE p.game_type='R' AND p.game_year IN ({y})
          AND p.pitch_type IS NOT NULL AND prev.pitch_type IS NOT NULL
          AND p.delta_run_exp IS NOT NULL AND p.balls <= 3 AND p.strikes <= 2
        GROUP BY 1,2,3"""
    rows = q(con, sql)

    by_count, raw = {}, {"same": [0, 0.0, 0.0], "different": [0, 0.0, 0.0]}
    for balls, strikes, seq, n, rv, whiff in rows:
        c = f"{balls}-{strikes}"
        by_count.setdefault(c, {})[seq] = {"n": n, "rv100": rv, "whiff": whiff}
        raw[seq][0] += n
        raw[seq][1] += rv * n
        raw[seq][2] += whiff * n

    out_counts, num_rv, num_wh, den = [], 0.0, 0.0, 0
    for c, d in sorted(by_count.items()):
        if "same" not in d or "different" not in d:
            continue
        s, x = d["same"], d["different"]
        w = s["n"] + x["n"]
        drv, dwh = x["rv100"] - s["rv100"], x["whiff"] - s["whiff"]
        num_rv += drv * w; num_wh += dwh * w; den += w
        out_counts.append({"count": c, "n_same": s["n"], "n_diff": x["n"],
                           "share_diff": round(x["n"] / w, 3),
                           "rv100_same": round(s["rv100"], 3),
                           "rv100_diff": round(x["rv100"], 3),
                           "delta_rv100": round(drv, 3),
                           "whiff_same": round(s["whiff"], 2),
                           "whiff_diff": round(x["whiff"], 2),
                           "delta_whiff": round(dwh, 2)})

    return {
        "raw": {k: {"n": v[0], "rv100": round(v[1] / v[0], 3), "whiff": round(v[2] / v[0], 2)}
                for k, v in raw.items() if v[0]},
        "by_count": out_counts,
        "count_adjusted": {"delta_rv100": round(num_rv / den, 3),
                           "delta_whiff": round(num_wh / den, 2), "n": den},
    }


def velocity_gap(con, years):
    """Does the SIZE of the velocity change matter, beyond merely being different?

    Bucketed by |this pitch - previous pitch| in mph, offspeed following a
    fastball only, so pitch identity is held roughly constant and what varies is
    how big a jump the hitter had to adjust to.
    """
    y = ",".join(str(i) for i in years)
    return [{"gap_mph": r[0], "n": r[1], "rv100": round(r[2], 3), "whiff": round(r[3], 2)}
            for r in q(con, f"""
        SELECT CAST(MIN(ABS(prev.release_speed - p.release_speed), 24) / 3 AS INT) * 3 bucket,
               COUNT(*) n,
               -100.0 * AVG(p.delta_run_exp),
               100.0 * AVG(CASE WHEN p.description LIKE 'swinging_strike%'
                                 OR p.description='foul_tip' THEN 1.0 ELSE 0.0 END)
        FROM pitches p
        JOIN pitches prev
          ON prev.game_pk=p.game_pk AND prev.at_bat_number=p.at_bat_number
         AND prev.pitch_number = p.pitch_number - 1
        WHERE p.game_type='R' AND p.game_year IN ({y})
          AND prev.pitch_type IN ('FF','SI','FC') AND p.pitch_type IN ('CH','CU','SL','ST','FS','KC')
          AND p.release_speed IS NOT NULL AND prev.release_speed IS NOT NULL
          AND p.delta_run_exp IS NOT NULL
        GROUP BY bucket HAVING n > 5000 ORDER BY bucket""")]


def repeat_depth(con, years):
    """Third fastball in a row: does repetition itself degrade the pitch?"""
    y = ",".join(str(i) for i in years)
    return [{"consecutive": r[0], "n": r[1], "rv100": round(r[2], 3), "whiff": round(r[3], 2)}
            for r in q(con, f"""
        SELECT CASE WHEN p2.pitch_type = p.pitch_type AND p1.pitch_type = p.pitch_type THEN 3
                    WHEN p1.pitch_type = p.pitch_type THEN 2 ELSE 1 END streak,
               COUNT(*) n,
               -100.0 * AVG(p.delta_run_exp),
               100.0 * AVG(CASE WHEN p.description LIKE 'swinging_strike%'
                                 OR p.description='foul_tip' THEN 1.0 ELSE 0.0 END)
        FROM pitches p
        JOIN pitches p1 ON p1.game_pk=p.game_pk AND p1.at_bat_number=p.at_bat_number
                       AND p1.pitch_number = p.pitch_number - 1
        JOIN pitches p2 ON p2.game_pk=p.game_pk AND p2.at_bat_number=p.at_bat_number
                       AND p2.pitch_number = p.pitch_number - 2
        WHERE p.game_type='R' AND p.game_year IN ({y})
          AND p.pitch_type IN ('FF','SI') AND p.delta_run_exp IS NOT NULL
        GROUP BY streak ORDER BY streak""")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent / "data" / "statcast.db"))
    ap.add_argument("--years", type=int, nargs="+", default=[2023, 2024, 2025, 2026])
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-200000")

    print("pitch type value..."); pt = pitch_type_value(con, args.years)
    print("sequencing...");       sq = sequencing(con, args.years)
    print("velocity gap...");     vg = velocity_gap(con, args.years)
    print("repeat depth...");     rd = repeat_depth(con, args.years)

    out = {"years": args.years, "pitch_types": pt, "sequencing": sq,
           "velocity_gap": vg, "repeat_depth": rd}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))

    print(f"\nRUN VALUE PER 100 (pitcher's perspective, higher is better)")
    for r in pt:
        print(f"  {r['pitch_type']:>3} n={r['n']:>9,} rv100={r['rv100']:+.2f} "
              f"whiff/swing={r['whiff_per_swing']}% xwOBAcon={r['xwoba_contact']} velo={r['velo']}")
    print(f"\nSEQUENCING  raw: {sq['raw']}")
    print(f"  count-adjusted delta (different minus same): "
          f"rv100 {sq['count_adjusted']['delta_rv100']:+.3f}, "
          f"whiff {sq['count_adjusted']['delta_whiff']:+.2f} pts, n={sq['count_adjusted']['n']:,}")
    print("\nVELOCITY GAP (offspeed after a fastball)")
    for r in vg:
        print(f"  {r['gap_mph']:>2}-{r['gap_mph']+2} mph n={r['n']:>9,} rv100={r['rv100']:+.2f} whiff={r['whiff']:.1f}%")
    print("\nCONSECUTIVE SAME FASTBALL")
    for r in rd:
        print(f"  #{r['consecutive']} n={r['n']:>9,} rv100={r['rv100']:+.2f} whiff={r['whiff']:.1f}%")


if __name__ == "__main__":
    main()
