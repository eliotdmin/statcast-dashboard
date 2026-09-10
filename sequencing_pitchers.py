#!/usr/bin/env python3
"""Within-pitcher sequencing: does a pitch play differently after each other pitch?

    python3 sequencing_pitchers.py --db data/statcast.db --year 2025

TWO QUESTIONS

1. Does a pitch perform differently depending on what preceded it? Emitted as a
   transition cube: (previous pitch, this pitch, count) -> run value and whiffs.

2. Do specific pitchers change pitches more than is good for them? Compared
   WITHIN pitcher, so a pitcher is measured against himself rather than against
   a league that throws different stuff.

THE STANDARDISATION, which is the whole methodological point.

A pitcher does not choose his sequence at random. He goes to the breaking ball
ahead in the count and back to the fastball behind, and hitters perform far
better in hitter's counts. So a raw "after a curveball" number is mostly
measuring WHICH COUNTS curveballs precede.

Every cell here is therefore compared against what that same pitch type would be
worth in the SAME COUNT distribution:

    expected(cell) = sum over counts of  n(cell, count) * baseline(pitch, count)
                     -------------------------------------------------------
                                     n(cell)

    delta = actual - expected

`baseline(pitch, count)` is that pitch type's league run value in that exact
count. A delta of zero means the sequence told you nothing the count did not.

Cells are emitted un-aggregated (n, run-value sum, whiff count, per count) so a
viewer can re-standardise on any subset of counts without re-querying.

WHAT THIS STILL CANNOT DO: assign causation. A pitcher's sequence is chosen, and
the choice correlates with his confidence, the hitter, and the game state. Within
-pitcher comparison removes the "some pitchers are better" confound; it does not
remove "this pitcher repeats when he likes his fastball that day".
"""
import argparse
import json
import sqlite3
from pathlib import Path

OUT = Path(__file__).parent / "output" / "sequencing_pitchers.json"

# Outs credited to the pitcher on plate appearances he finished. Excludes
# pickoffs and caught stealing, which are not his PA outcomes -- so this is a
# very close proxy for innings pitched, not an exact one.
OUTS = """CASE
    WHEN events IN ('grounded_into_double_play','double_play','strikeout_double_play',
                    'sac_fly_double_play','sac_bunt_double_play') THEN 2
    WHEN events = 'triple_play' THEN 3
    WHEN events IN ('field_out','strikeout','force_out','sac_fly','sac_bunt',
                    'fielders_choice_out','other_out') THEN 1
    ELSE 0 END"""

WHIFF = ("CASE WHEN p.description LIKE 'swinging_strike%' OR p.description='foul_tip' "
         "THEN 1 ELSE 0 END")


def top_pitchers(con, year, n=5):
    rows = con.execute(f"""
        SELECT pitcher, SUM({OUTS}) outs, COUNT(*) pitches
        FROM pitches WHERE game_year=? AND game_type='R'
        GROUP BY pitcher ORDER BY outs DESC LIMIT ?""", (year, n)).fetchall()
    out = []
    for pid, outs, pitches in rows:
        # player_name on a pitch row IS the pitcher (a documented Savant quirk).
        nm = con.execute("SELECT player_name FROM pitches WHERE pitcher=? AND game_year=? LIMIT 1",
                         (pid, year)).fetchone()
        nm = nm[0] if nm else str(pid)
        if "," in nm:
            nm = " ".join(x.strip() for x in nm.split(",")[::-1])
        out.append({"id": pid, "name": nm, "outs": outs,
                    "ip": round(outs / 3, 1), "pitches": pitches})
    return out


def cube(con, year, pitcher=None):
    """(prev pitch, this pitch, count) -> n, run-value sum, whiffs. Un-aggregated."""
    where = "p.game_year=? AND p.game_type='R'"
    params = [year]
    if pitcher:
        where += " AND p.pitcher=?"; params.append(pitcher)
    rows = con.execute(f"""
        SELECT prev.pitch_type, p.pitch_type, p.balls, p.strikes,
               COUNT(*), SUM(p.delta_run_exp), SUM({WHIFF}),
               SUM(p.delta_run_exp*p.delta_run_exp)
        FROM pitches p
        JOIN pitches prev ON prev.game_pk=p.game_pk
             AND prev.at_bat_number=p.at_bat_number
             AND prev.pitch_number = p.pitch_number - 1
        WHERE {where} AND p.pitch_type IS NOT NULL AND prev.pitch_type IS NOT NULL
          AND p.delta_run_exp IS NOT NULL AND p.balls<=3 AND p.strikes<=2
        GROUP BY 1,2,3,4""", params).fetchall()
    # rv is negated at read time so positive = good for the pitcher. The sum of
    # squares travels with each cell so the viewer can compute a standard error
    # rather than reading a point estimate as if it were exact.
    return [[a, b, f"{c}-{d}", n, round(-rv, 4), w, round(ss, 4)]
            for a, b, c, d, n, rv, w, ss in rows]


def baseline(con, year):
    """League run value and whiff rate for each (pitch type, count). The yardstick."""
    rows = con.execute(f"""
        SELECT p.pitch_type, p.balls, p.strikes, COUNT(*),
               SUM(p.delta_run_exp), SUM({WHIFF})
        FROM pitches p
        WHERE p.game_year=? AND p.game_type='R' AND p.pitch_type IS NOT NULL
          AND p.delta_run_exp IS NOT NULL AND p.balls<=3 AND p.strikes<=2
        GROUP BY 1,2,3""", (year,)).fetchall()
    return [[t, f"{b}-{s}", n, round(-rv, 4), w] for t, b, s, n, rv, w in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent / "data" / "statcast.db"))
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--n", type=int, default=5)
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-300000")

    print("top pitchers by innings...", flush=True)
    tops = top_pitchers(con, args.year, args.n)
    for t in tops:
        print(f"  {t['name']:22s} {t['ip']:>6} IP  {t['pitches']:>6,} pitches", flush=True)

    print("league baseline...", flush=True)
    base = baseline(con, args.year)
    print("league transition cube...", flush=True)
    cubes = {"LEAGUE": cube(con, args.year)}
    for t in tops:
        print(f"  cube: {t['name']}", flush=True)
        cubes[str(t["id"])] = cube(con, args.year, t["id"])

    out = {"year": args.year, "pitchers": tops, "baseline": base, "cubes": cubes}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"\nwrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
    print(f"league cells: {len(cubes['LEAGUE']):,}  baseline cells: {len(base):,}")


if __name__ == "__main__":
    main()
