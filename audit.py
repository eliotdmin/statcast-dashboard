#!/usr/bin/env python3
"""Audit the Statcast database: coverage, distributions, and integrity.

    python3 audit.py                 # writes output/audit.json
    python3 audit.py --quick         # skip the per-column distribution pass

THE CENTRAL DISTINCTION this makes, which a naive "% null" report gets wrong:

    STRUCTURAL null  -- the column cannot apply to this row. `launch_speed` on a
                        called strike is not missing data; there was no batted
                        ball. `events` is null on every pitch but the last of a
                        plate appearance, by design.
    REAL null        -- the column should have a value here and does not. A
                        batted ball with no exit velocity is a tracking failure.

Reporting them together produces a table where `events` looks 75% "missing" and
a genuine 4% tracking gap is invisible next to it. So every column that has an
applicability condition gets audited against that condition, and the report
states the condition it used.
"""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import schema

ROOT = Path(__file__).parent
DB = ROOT / "data" / "statcast.db"
OUT = ROOT / "output" / "audit.json"

# Applicability, plausible ranges and the dead-column list all come from
# schema.yaml, which is also what DATA_DICTIONARY.md is generated from. Keeping
# one copy is the point: a check and a docs paragraph that state the same fact
# twice will disagree eventually, and the docs are the copy that fails silently.
APPLICABILITY = schema.applicability("pitches")
DEAD = schema.dead("pitches")
PLAUSIBLE = schema.plausible("pitches")


def cols(con, table="pitches"):
    return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]


def q1(con, sql, params=()):
    r = con.execute(sql, params).fetchone()
    return r[0] if r else None


def seasons(con):
    return [r[0] for r in con.execute(
        "SELECT DISTINCT game_year FROM pitches WHERE game_year IS NOT NULL ORDER BY 1")]


def coverage(con, years, columns):
    """Non-null coverage per column per season, measured against applicability.

    Columns are grouped by their applicability predicate so each (season,
    predicate) pair costs ONE table scan with 119 COUNT() aggregates, rather
    than one scan per column. On a four-season database that is the difference
    between ~24 scans and ~476.
    """
    groups = {}
    for c in columns:
        pred, label = APPLICABILITY.get(c, ("1=1", "all pitches"))
        groups.setdefault((pred, label), []).append(c)

    out = {c: {"condition": APPLICABILITY.get(c, ("1=1", "all pitches"))[1],
               "dead": c in DEAD, "by_year": {}} for c in columns}

    for (pred, label), cs in groups.items():
        sel = ", ".join(f'COUNT("{c}")' for c in cs)
        for y in years:
            row = con.execute(
                f"SELECT COUNT(*), {sel} FROM pitches WHERE game_year=? AND ({pred})", (y,)
            ).fetchone()
            denom, counts = row[0], row[1:]
            for c, nn in zip(cs, counts):
                out[c]["by_year"][str(y)] = {
                    "denom": denom, "present": nn,
                    "pct": round(100.0 * nn / denom, 2) if denom else None}
    return out


# Percentiles come from a deterministic 10% sample; counts, means and the
# out-of-range tallies are exact. At 700k rows a season a 10% sample places
# every percentile to well inside the precision this report displays, and it
# turns a multi-minute sort into seconds.
SAMPLE_PCT = 10


def distributions(con, years):
    """Exact aggregates plus sampled percentiles, one scan per season."""
    import statistics
    cs = [c for c in PLAUSIBLE if c in cols(con)]
    out = {c: {} for c in cs}

    for y in years:
        agg = []
        for c in cs:
            lo, hi = PLAUSIBLE[c]
            agg += [f'COUNT("{c}")', f'AVG("{c}")',
                    f'MIN("{c}")', f'MAX("{c}")',
                    f'SUM(CASE WHEN "{c}" < {lo} THEN 1 ELSE 0 END)',
                    f'SUM(CASE WHEN "{c}" > {hi} THEN 1 ELSE 0 END)']
        row = con.execute(f"SELECT {', '.join(agg)} FROM pitches WHERE game_year=?", (y,)).fetchone()

        sel = ", ".join(f'"{c}"' for c in cs)
        samples = {c: [] for c in cs}
        for r in con.execute(
                f"SELECT {sel} FROM pitches WHERE game_year=? AND (rowid % {100 // SAMPLE_PCT}) = 0", (y,)):
            for c, v in zip(cs, r):
                if isinstance(v, (int, float)):
                    samples[c].append(v)

        for i, c in enumerate(cs):
            n, mean, mn, mx, bad_lo, bad_hi = row[i * 6:i * 6 + 6]
            if not n:
                continue
            v = sorted(samples[c])
            def pct(p, v=v):
                return v[min(len(v) - 1, max(0, int(round(p / 100 * (len(v) - 1)))))] if v else None
            lo, hi = PLAUSIBLE[c]
            out[c][str(y)] = {
                "n": n, "mean": round(mean, 3), "sd": round(statistics.pstdev(v), 3) if len(v) > 1 else 0.0,
                "min": round(mn, 3), "p1": round(pct(1), 3), "p25": round(pct(25), 3),
                "p50": round(pct(50), 3), "p75": round(pct(75), 3), "p99": round(pct(99), 3),
                "max": round(mx, 3),
                "implausible_low": bad_lo, "implausible_high": bad_hi,
                "implausible_pct": round(100.0 * (bad_lo + bad_hi) / n, 3),
                "bounds": [lo, hi], "sampled_pct": SAMPLE_PCT,
            }
    return {c: v for c, v in out.items() if v}


def integrity(con, years):
    """Checks that should pass. Each returns a verdict, not just a number."""
    checks = []

    def add(name, ok, detail, why):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "why": why})

    dupes = q1(con, """SELECT COUNT(*) FROM (
        SELECT game_pk, at_bat_number, pitch_number, COUNT(*) c
        FROM pitches GROUP BY 1,2,3 HAVING c > 1)""")
    add("No duplicate pitches", dupes == 0, f"{dupes:,} duplicated (game_pk, at_bat, pitch)",
        "A day fetched twice would double-count every rate stat. ingest_log is supposed to prevent this.")

    bad_count = q1(con, "SELECT COUNT(*) FROM pitches WHERE balls > 3 OR strikes > 2 OR balls < 0 OR strikes < 0")
    add("Count states legal", bad_count == 0, f"{bad_count:,} rows with impossible ball/strike counts",
        "Savant occasionally emits a 4-ball or 3-strike row on a mid-PA event; they should be excluded from count-state work.")

    gt = {r[0]: r[1] for r in con.execute("SELECT game_type, COUNT(*) FROM pitches GROUP BY 1")}
    non_reg = sum(v for k, v in gt.items() if k != "R")
    add("Regular season only", non_reg == 0, f"{gt}",
        "Spring training and postseason rows contaminate qualified-player leaderboards if not filtered.")

    # xwOBA's non-contact convention, PER SEASON. This is not a pass/fail: Savant
    # populates estimated_woba_using_speedangle on PA-ending strikeouts (0.0),
    # walks (~0.70) and HBP (~0.73) in recent vintages, whereas the long-standing
    # public understanding -- and older data -- is that it is NULL there.
    #
    # The danger is not either convention. It is a MIX of them across seasons in
    # one table: any code that branches on null-ness silently computes a
    # different statistic in 2023 than in 2026, with no error anywhere.
    conv = {}
    for y in years:
        tot = q1(con, "SELECT COUNT(*) FROM pitches WHERE game_year=? AND type!='X' AND woba_denom=1", (y,))
        pop = q1(con, "SELECT COUNT(estimated_woba_using_speedangle) FROM pitches "
                      "WHERE game_year=? AND type!='X' AND woba_denom=1", (y,))
        conv[y] = "folded-in" if tot and pop / tot > 0.9 else ("null" if tot and pop / tot < 0.1 else "MIXED")
    consistent = len(set(conv.values())) <= 1
    add("xwOBA non-contact convention is consistent across seasons", consistent,
        f"{conv}",
        "'folded-in' = strikeouts/walks carry an xwOBA (K=0.0, BB~0.70). 'null' = they do not. "
        "If seasons disagree, `WHERE estimated_woba_using_speedangle IS NOT NULL` means "
        "'batted ball' in one season and 'completed PA' in another. Use type='X' for contact.")

    # Balls in play that genuinely lack an xwOBA, excluding bunts (which the
    # model deliberately does not score).
    miss = q1(con, "SELECT COUNT(*) FROM pitches WHERE type='X' AND woba_denom=1 "
                   "AND estimated_woba_using_speedangle IS NULL "
                   "AND (events IS NULL OR events NOT LIKE '%bunt%')")
    bip = q1(con, "SELECT COUNT(*) FROM pitches WHERE type='X' AND woba_denom=1")
    rate = 100.0 * miss / bip if bip else 0
    add("Batted balls modelled by xwOBA", rate < 1.0,
        f"{miss:,} of {bip:,} non-bunt balls in play ({rate:.2f}%) have no xwOBA",
        "These are tracking failures, not structural nulls. Above ~1% means a real gap in "
        "the ball-tracking for that period, and every rate built on xwOBA is computed on a "
        "quietly non-random subset of contact.")

    documented = set(schema.columns("pitches"))
    actual = set(cols(con))
    undocumented = sorted(actual - documented)
    stale = sorted(documented - actual)
    add("Every database column is documented", not undocumented,
        f"undocumented: {undocumented or 'none'} | in schema but not in db: {stale or 'none'}",
        "Savant adds columns mid-season and the ingest widens the table to accept them. An undocumented "
        "column is a metric nobody has decided how to treat -- add it to schema.yaml, with its "
        "applicability condition, before anything downstream consumes it.")

    xba_nc = q1(con, "SELECT COUNT(*) FROM pitches WHERE type!='X' AND estimated_ba_using_speedangle IS NOT NULL")
    add("xBA/xSLG remain contact-only", xba_nc == 0,
        f"{xba_nc:,} non-contact rows carry an xBA",
        "xwOBA and xBA follow DIFFERENT conventions in the same row. Averaging xBA over all PA "
        "still drops strikeouts from the numerator while the denominator counts them.")

    # Sign conventions, checked empirically rather than assumed.
    rows = con.execute("""SELECT stand, ROUND(AVG(plate_x),3), COUNT(*) FROM pitches
                          WHERE plate_x IS NOT NULL AND stand IN ('L','R') GROUP BY 1""").fetchall()
    d = {r[0]: r[1] for r in rows}
    ok = "L" in d and "R" in d and (d["L"] * d["R"] < 0)
    add("plate_x sign flips by batter side", ok, f"mean plate_x: {d}",
        "Pitchers work away from both sides, so the two means must have OPPOSITE signs. If they don't, "
        "the handedness correction in any platoon split is backwards.")

    rows = con.execute("""SELECT p_throws, ROUND(AVG(pfx_x),3), COUNT(*) FROM pitches
                          WHERE pfx_x IS NOT NULL AND p_throws IN ('L','R') GROUP BY 1""").fetchall()
    d = {r[0]: r[1] for r in rows}
    ok = "L" in d and "R" in d and (d["L"] * d["R"] < 0)
    add("pfx_x sign flips by pitcher hand", ok, f"mean pfx_x: {d}",
        "Arm-side run is opposite-signed for lefties and righties. Pooling without flipping cancels the effect to ~zero.")

    # Schedule completeness at TEAM level. "2,430 games" is too coarse -- it
    # cannot distinguish a genuine cancellation from a missing fetch. Every team
    # plays exactly 162, so a season with one game missing shows up as exactly
    # two teams at 161, and those two teams name the game.
    for y in years:
        rows = con.execute("""
            SELECT t, SUM(n) g FROM (
              SELECT home_team t, COUNT(DISTINCT game_pk) n FROM pitches
                WHERE game_year=? AND game_type='R' GROUP BY 1
              UNION ALL
              SELECT away_team t, COUNT(DISTINCT game_pk) n FROM pitches
                WHERE game_year=? AND game_type='R' GROUP BY 1)
            GROUP BY t""", (y, y)).fetchall()
        if not rows:
            continue
        short = [(t, g) for t, g in rows if g != 162]
        complete = max(g for _, g in rows) >= 162
        if not complete:
            continue                      # season still in progress
        add(f"{y}: every team played 162", not short, f"{short or 'all 30 teams at 162'}",
            "A cancelled game that was never made up leaves exactly two teams at 161 and names them. "
            "Anything else -- one team short, or many -- is a fetch hole, not a rainout.")

    # Schedule completeness: every logged day with 0 rows should be a real off-day.
    per_year = {}
    for y in years:
        days = q1(con, "SELECT COUNT(DISTINCT game_date) FROM pitches WHERE game_year=?", (y,))
        logged = q1(con, "SELECT COUNT(*) FROM ingest_log WHERE scope='pitches' AND day LIKE ?", (f"{y}-%",))
        offdays = q1(con, "SELECT COUNT(*) FROM ingest_log WHERE scope='pitches' AND rows=0 AND day LIKE ?", (f"{y}-%",))
        games = q1(con, "SELECT COUNT(DISTINCT game_pk) FROM pitches WHERE game_year=?", (y,))
        pitches = q1(con, "SELECT COUNT(*) FROM pitches WHERE game_year=?", (y,))
        per_year[str(y)] = {"days_with_games": days, "days_logged": logged, "offdays": offdays,
                            "games": games, "pitches": pitches,
                            "pitches_per_game": round(pitches / games, 1) if games else None,
                            "games_vs_2430": round(100.0 * games / 2430, 1) if games else None}
    return checks, per_year


def leaderboard_reconciliation(con):
    """Does the leaderboard wOBA match a wOBA computed from the pitch table?

    They will not match exactly -- Savant's leaderboard is its own aggregate --
    but a large systematic gap means the pitch table is incomplete for that
    season, which is exactly what a partial backfill looks like.
    """
    out = []
    for (snap, year) in con.execute(
            "SELECT DISTINCT snapshot_date, year FROM expected_stats ORDER BY year"):
        rows = con.execute("""
            SELECT e.player_id, e.pa, e.woba,
                   (SELECT SUM(woba_value) FROM pitches p
                     WHERE p.batter = e.player_id AND p.game_year = e.year AND p.woba_denom = 1),
                   (SELECT COUNT(*) FROM pitches p
                     WHERE p.batter = e.player_id AND p.game_year = e.year AND p.woba_denom = 1)
            FROM expected_stats e
            WHERE e.snapshot_date = ? AND e.player_type='batter' AND e.pa >= 300
            LIMIT 60""", (snap,)).fetchall()
        diffs, pa_ratio = [], []
        for pid, pa, woba, num, den in rows:
            if not den or not pa or woba is None:
                continue
            diffs.append((num / den) - woba)
            pa_ratio.append(den / pa)
        if diffs:
            diffs.sort()
            out.append({"year": year, "snapshot": snap, "n_players": len(diffs),
                        "median_woba_diff": round(diffs[len(diffs)//2], 4),
                        "median_pa_coverage": round(sorted(pa_ratio)[len(pa_ratio)//2], 3)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--db", default=str(DB))
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA cache_size=-200000")          # ~200 MB page cache
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_pitches_bat_year ON pitches(batter, game_year)")
    except Exception as e:
        print(f"  ! index: {e}")
    ys = seasons(con)
    columns = cols(con)
    print(f"auditing {len(columns)} columns across seasons {ys}", flush=True)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "db_bytes": Path(args.db).stat().st_size,
        "seasons": ys,
        "n_columns": len(columns),
        "total_pitches": q1(con, "SELECT COUNT(*) FROM pitches"),
        "date_range": list(con.execute("SELECT MIN(game_date), MAX(game_date) FROM pitches").fetchone()),
    }
    print("  coverage...", flush=True)
    report["coverage"] = coverage(con, ys, columns)
    print("  integrity...", flush=True)
    report["integrity"], report["by_season"] = integrity(con, ys)
    print("  reconciliation...", flush=True)
    try:
        report["reconciliation"] = leaderboard_reconciliation(con)
    except Exception as e:
        report["reconciliation"] = {"error": f"{type(e).__name__}: {e}"}
    if not args.quick:
        print("  distributions...", flush=True)
        report["distributions"] = distributions(con, ys)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1))
    print(f"\nwrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")

    failed = [c for c in report["integrity"] if not c["ok"]]
    print(f"integrity: {len(report['integrity']) - len(failed)} passed, {len(failed)} failed")
    for c in failed:
        print(f"  FAIL  {c['name']}: {c['detail']}")


if __name__ == "__main__":
    main()
