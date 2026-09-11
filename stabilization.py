#!/usr/bin/env python3
"""How many events before a metric means something? Split-half reliability.

    python3 stabilization.py --db data/statcast.db

PRE-SPECIFIED: no hypothesis about which metric wins. This measures reliability,
not an effect, so there is nothing to fish for -- the output is a curve per
metric and the question is only where each one crosses.

METHOD. For each player-season and each sample size n, take that player's first
2n events of the metric, split them by odd/even index (which balances
within-season trend and opponent quality between the halves far better than a
first-half/second-half split), and correlate the two half-means across players.
Spearman-Brown then corrects that half-length correlation up to full length:

    r_full = 2 * r_half / (1 + r_half)

The conventional stabilisation point is where r_full = 0.5 -- the sample at which
half the observed variance between players is real skill rather than noise. 0.7
is reported too, because 0.5 is a low bar that gets quoted as though it were
high.

WHY IT MATTERS HERE. analyze.py gates every metric at MIN_PA = 150, one number
for all of them. If bat speed is reliable at 50 swings and xwOBA needs 300 PA,
that single gate is either far too strict or far too loose depending on which
signal you are reading, and a faster-stabilising metric buys earlier detection.

2026 is excluded: the ABS strike zone changes what `zone` means, and chase rate
depends on it.
"""
import argparse, json, math, sqlite3
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).parent / "output" / "stabilization.json"
ORDER = "ORDER BY game_date, game_pk, at_bat_number, pitch_number"
SWING = "(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"

# metric -> (id column, row filter, value expression)
METRICS = {
 "exit velocity":  ("batter", "type='X' AND launch_speed IS NOT NULL", "launch_speed"),
 "launch angle":   ("batter", "type='X' AND launch_angle IS NOT NULL", "launch_angle"),
 "barrel rate":    ("batter", "type='X' AND launch_speed_angle IS NOT NULL",
                    "CASE WHEN launch_speed_angle=6 THEN 1.0 ELSE 0.0 END"),
 "hard-hit rate":  ("batter", "type='X' AND launch_speed IS NOT NULL",
                    "CASE WHEN launch_speed>=95 THEN 1.0 ELSE 0.0 END"),
 "bat speed":      ("batter", f"{SWING} AND bat_speed IS NOT NULL", "bat_speed"),
 "swing length":   ("batter", f"{SWING} AND swing_length IS NOT NULL", "swing_length"),
 "whiff rate":     ("batter", SWING,
                    "CASE WHEN description LIKE 'swinging_strike%' OR description='foul_tip' "
                    "THEN 1.0 ELSE 0.0 END"),
 "chase rate":     ("batter", "zone>=11 AND zone IS NOT NULL",
                    f"CASE WHEN {SWING} THEN 1.0 ELSE 0.0 END"),
 "xwOBA":          ("batter", "woba_denom=1",
                    "COALESCE(estimated_woba_using_speedangle, woba_value)"),
 "pitcher velo":   ("pitcher", "pitch_type IN ('FF','SI') AND release_speed IS NOT NULL",
                    "release_speed"),
 "pitcher whiff":  ("pitcher", SWING,
                    "CASE WHEN description LIKE 'swinging_strike%' OR description='foul_tip' "
                    "THEN 1.0 ELSE 0.0 END"),
 "pitcher arm angle": ("pitcher", "arm_angle IS NOT NULL", "arm_angle"),
}
UNITS = {
 "exit velocity": "batted balls", "launch angle": "batted balls",
 "barrel rate": "batted balls", "hard-hit rate": "batted balls",
 "bat speed": "swings", "swing length": "swings", "whiff rate": "swings",
 "chase rate": "out-of-zone pitches", "xwOBA": "PA",
 "pitcher velo": "fastballs", "pitcher whiff": "swings against",
 "pitcher arm angle": "pitches",
}
GRID = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 250, 300, 400, 500, 700, 1000]


def pearson(x, y):
    n = len(x)
    if n < 20: return None
    mx, my = sum(x)/n, sum(y)/n
    sx = math.sqrt(sum((a-mx)**2 for a in x)); sy = math.sqrt(sum((b-my)**2 for b in y))
    if sx == 0 or sy == 0: return None
    return sum((a-mx)*(b-my) for a, b in zip(x, y))/(sx*sy)


def curve(streams):
    """streams: {player_season: [values in order]} -> {n: (r_full, n_players)}"""
    out = {}
    for n in GRID:
        pairs = [(sum(v[0::2][:n])/n, sum(v[1::2][:n])/n)
                 for v in streams.values()
                 if len(v[0::2]) >= n and len(v[1::2]) >= n]
        if len(pairs) < 25: continue
        r = pearson([p[0] for p in pairs], [p[1] for p in pairs])
        if r is None: continue
        r = max(min(r, 0.9999), -0.9999)
        out[n] = (2*r/(1+r), len(pairs))
    return out


def cross(c, target):
    """Smallest tested n at which corrected reliability reaches `target`.

    Scanning for the first n that CLEARS the bar, rather than for an upward
    crossing, matters: a metric already reliable at the smallest n tested has no
    crossing at all, and an interpolating version reports it as never
    stabilising -- exactly backwards for the most stable metrics there are.
    Returns a negative number to mean "at or below the smallest n tested".
    """
    ns = sorted(c)
    if not ns:
        return None
    if c[ns[0]][0] >= target:
        return -ns[0]
    for n in ns:
        if c[n][0] >= target:
            return n
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path(__file__).parent / "data" / "statcast.db"))
    args = ap.parse_args()
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    con.execute("PRAGMA cache_size=-400000")

    report = {}
    print(f"{'metric':20s} {'r=0.5 at':>10} {'r=0.7 at':>10} {'unit':>14}  {'players':>8}")
    print("-"*72)
    for name, (idcol, where, expr) in METRICS.items():
        streams = defaultdict(list)
        for yr in (2023, 2024, 2025):
            q = (f"SELECT {idcol}, {expr} FROM pitches "
                 f"WHERE game_year={yr} AND game_type='R' AND ({where}) {ORDER}")
            for pid, v in con.execute(q):
                if v is not None:
                    streams[(pid, yr)].append(float(v))
        c = curve(streams)
        if not c: continue
        unit = UNITS[name]
        n50, n70 = cross(c, 0.5), cross(c, 0.7)
        big = max(c)
        fmt = lambda v: ("never" if v is None else
                         (f"<={-v}" if v < 0 else str(v)))
        report[name] = {"curve": {str(k): [round(v[0], 4), v[1]] for k, v in c.items()},
                        "n50": n50, "n70": n70, "unit": unit,
                        "max_r": round(c[big][0], 3), "max_n": big}
        print(f"{name:20s} {fmt(n50):>10} {fmt(n70):>10} {unit:>20}  {c[big][1]:>7,}"
              f"  r@{big}={c[big][0]:.2f}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
