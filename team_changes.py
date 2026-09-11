#!/usr/bin/env python3
"""Apply the stabilisation result: which player changes are actually detectable?

    python3 team_changes.py --db data/statcast.db --team NYM

NOT a team reliability curve. Reliability is a correlation ACROSS players, so
computing one on a 15-man roster would be a correlation on n=15 -- noise. There
is no such thing as one team's reliability.

What the stabilisation result IS good for is this: it tells you which
year-over-year changes you can believe. Bat speed reaches r=0.7 at about ten
swings, so a full season measures it precisely and a 1 mph move is real. xwOBA
needs 250 PA for the same confidence, so a season barely gets there and most
year-over-year xwOBA "changes" are noise.

Every change below is reported with the standard error of the change itself:

    SE(delta) = sqrt( sd_a^2/n_a + sd_b^2/n_b )

A player's team is derived from the half-inning: the batting team is the away
team in the top half and the home team in the bottom.
"""
import argparse, math, sqlite3, json
from pathlib import Path

SWING = "(p.description LIKE '%swing%' OR p.description LIKE 'foul%' OR p.type='X')"
BATTEAM = "CASE WHEN p.inning_topbot='Top' THEN p.away_team ELSE p.home_team END"


def stats(con, team, year, expr, where, idcol="batter"):
    q = f"""SELECT p.{idcol}, p.player_name, COUNT(*), AVG({expr}),
                   AVG({expr}*{expr}) - AVG({expr})*AVG({expr})
            FROM pitches p
            WHERE p.game_year=? AND p.game_type='R' AND {BATTEAM}=?
              AND ({where}) AND ({expr}) IS NOT NULL
            GROUP BY 1"""
    out = {}
    for pid, nm, n, mean, var in con.execute(q, (year, team)):
        out[pid] = {"n": n, "mean": mean, "sd": math.sqrt(max(var, 0)), "name": nm}
    return out


def name_of(con, pid):
    """Batter names come from expected_stats, NOT from pitches.player_name.

    pitches.player_name is the PITCHER's name on every row regardless of what you
    are grouping by -- a documented Savant quirk that DATA_DICTIONARY.md warns
    about, and which produced a table of bare player IDs on the first run of this
    script.
    """
    r = con.execute("SELECT player_name FROM expected_stats "
                    "WHERE player_id=? AND player_type='batter' LIMIT 1", (pid,)).fetchone()
    if r:
        return r[0]
    r = con.execute("SELECT player_name FROM pitches WHERE pitcher=? LIMIT 1", (pid,)).fetchone()
    return r[0] if r else str(pid)


def compare(a, b, minn, label, unit, con, fmt="{:+.2f}"):
    rows = []
    for pid in set(a) & set(b):
        x, y = a[pid], b[pid]
        if x["n"] < minn or y["n"] < minn:
            continue
        d = y["mean"] - x["mean"]
        se = math.sqrt(x["sd"]**2 / x["n"] + y["sd"]**2 / y["n"])
        rows.append({"pid": pid, "d": d, "se": se, "na": x["n"], "nb": y["n"],
                     "a": x["mean"], "b": y["mean"],
                     "sig": abs(d) > 1.96 * se})
    rows.sort(key=lambda r: -abs(r["d"] / r["se"]) if r["se"] else 0)
    print(f"\n=== {label} ({unit}) — 2025 vs 2026, min {minn} each ===")
    print(f"{'player':24s} {'2025':>8} {'2026':>8} {'change':>9} {'95% CI':>18}  n")
    for r in rows:
        nm = name_of(con, r["pid"])
        if "," in nm:
            nm = " ".join(s.strip() for s in nm.split(",")[::-1])
        ci = 1.96 * r["se"]
        flag = "  <-- real" if r["sig"] else ""
        print(f"{nm[:24]:24s} {r['a']:>8.2f} {r['b']:>8.2f} {fmt.format(r['d']):>9} "
              f"[{r['d']-ci:>+6.2f},{r['d']+ci:>+6.2f}] {r['na']:>5}/{r['nb']:<5}{flag}")
    n_sig = sum(1 for r in rows if r["sig"])
    print(f"  {n_sig} of {len(rows)} changes distinguishable from zero")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent / "data" / "statcast.db"))
    ap.add_argument("--team", default="NYM")
    args = ap.parse_args()
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-400000")

    T = args.team
    print(f"{T} hitters — which year-over-year changes are real?")

    bs25 = stats(con, T, 2025, "p.bat_speed", SWING)
    bs26 = stats(con, T, 2026, "p.bat_speed", SWING)
    compare(bs25, bs26, 150, "Bat speed", "mph", con)

    ev25 = stats(con, T, 2025, "p.launch_speed", "p.type='X'")
    ev26 = stats(con, T, 2026, "p.launch_speed", "p.type='X'")
    compare(ev25, ev26, 80, "Exit velocity", "mph", con)

    xw = "COALESCE(p.estimated_woba_using_speedangle, p.woba_value)"
    xw25 = stats(con, T, 2025, xw, "p.woba_denom=1")
    xw26 = stats(con, T, 2026, xw, "p.woba_denom=1")
    compare(xw25, xw26, 150, "xwOBA", "wOBA scale", con, fmt="{:+.3f}")


if __name__ == "__main__":
    main()
