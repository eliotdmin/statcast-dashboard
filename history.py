#!/usr/bin/env python3
"""history.py -- each player's completed seasons, for the site's "usual level" baseline.

    python3 history.py                 # writes web/data/history.json from the database

Reads Savant's season expected-stats leaderboards already stored in `expected_stats` (every
completed season it holds: 2023+ today, 2015+ once `fetch_history.py` has run on the Mac) and
writes, per player type, each player's seasons as [year, PA, wOBA, xwOBA], plus the league
wOBA per season and a measured spread of true talent.

Read-only: opens the database with mode=ro, so it is safe to run from the sandbox (CLAUDE.md).

Why the talent spread is measured here: the site regresses a player's prior seasons toward the
league by k = sigma^2 / tau^2 plate appearances (sigma^2 = 0.2258 per PA, FINDINGS noise-ceiling
entry). tau^2 = var(observed season wOBA) - mean(sigma^2 / PA) over full-time seasons; it is
estimated separately for hitters and pitchers, since only the hitter value (.035) was measured
before.
"""
import json, sqlite3, statistics
from pathlib import Path

ROOT = Path(__file__).parent
DB = ROOT / "data" / "statcast.db"
OUT = ROOT / "web" / "data" / "history.json"
S2 = 0.2258
FULL_TIME = 300          # PA / BF for a season to count toward the talent-spread estimate


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    # A completed season's final snapshot is its last snapshot_date; the in-progress season
    # (the latest year in the table) is left out -- it is "this season", not history.
    current = con.execute("SELECT MAX(year) FROM expected_stats").fetchone()[0]
    rows = con.execute("""
        SELECT e.player_type, e.player_id, e.year, e.pa, e.woba, e.est_woba
        FROM expected_stats e
        JOIN (SELECT player_type, year, MAX(snapshot_date) AS s FROM expected_stats
              WHERE year < ? GROUP BY player_type, year) f
          ON f.player_type = e.player_type AND f.year = e.year AND f.s = e.snapshot_date
        WHERE e.pa > 0 AND e.woba IS NOT NULL
    """, (current,)).fetchall()

    out = {"generated_by": "history.py", "sigma2": S2, "through": current - 1}
    for kind, key in (("batter", "bat"), ("pitcher", "pit")):
        mine = [r for r in rows if r[0] == kind]
        players, league = {}, {}
        for _, pid, y, pa, w, x in mine:
            players.setdefault(str(pid), []).append(
                [y, int(pa), round(w, 3), None if x is None else round(x, 3)])
            L = league.setdefault(y, [0.0, 0.0])
            L[0] += pa * w
            L[1] += pa
        for v in players.values():
            v.sort()
        full = [(pa, w) for _, _, _, pa, w, _ in mine if pa >= FULL_TIME]
        noise = statistics.fmean(S2 / pa for pa, _ in full)
        tau2 = max(statistics.pvariance([w for _, w in full]) - noise, 1e-5)
        out[key] = {
            "years": sorted(league),
            "league": {str(y): round(t / n, 4) for y, (t, n) in sorted(league.items())},
            "tau": round(tau2 ** 0.5, 4),
            "k": round(S2 / tau2),
            "players": players,
        }
        print(f"{key}: {len(players)} players, seasons {min(league)}-{max(league)}, "
              f"talent sd {tau2 ** 0.5:.4f} from {len(full)} full-time seasons, k = {S2 / tau2:.0f} PA")
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
