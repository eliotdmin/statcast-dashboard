"""Pull Statcast data via pybaseball, incrementally, into SQLite.

Design notes
------------
* Pitch-level data is fetched one day at a time and logged in `ingest_log`, so a
  crash or a Ctrl-C never forces a full re-download, and daily refreshes only
  ask Baseball Savant for days it has never seen.
* Savant is a courtesy endpoint, not a contracted API. We sleep between day
  requests and never re-fetch a day we already have.
"""
import time
from datetime import date, datetime, timedelta

import pandas as pd

import db

# Regular-season windows, (first game, last game) inclusive.
#
# Starts are deliberately a day or two early where MLB opened abroad: 2024 began
# with the Seoul Series on Mar 20 and 2025 with the Tokyo Series on Mar 18, both
# well before the domestic openers. An extra empty day costs one request and is
# logged as an off-day, so erring early is cheap; missing real games is not.
#
# Ends are the last day of the REGULAR season. Postseason is excluded by default
# because every downstream metric here is a regular-season qualified-player
# statistic, and October's roster and bullpen usage are a different population.
# Pass include_postseason=True to extend through early November.
SEASONS = {
    2023: ("2023-03-30", "2023-10-01"),
    2024: ("2024-03-20", "2024-09-30"),
    2025: ("2025-03-18", "2025-09-28"),
    2026: ("2026-03-25", "2026-10-04"),
}
POSTSEASON_END = "{year}-11-05"


def season_days(year, through=None, days_back=None, include_postseason=False):
    """Every calendar day of `year`'s regular season, oldest first."""
    start_s, end_s = SEASONS.get(year, (f"{year}-03-28", f"{year}-10-05"))
    start = datetime.strptime(start_s, "%Y-%m-%d").date()
    end = datetime.strptime(
        POSTSEASON_END.format(year=year) if include_postseason else end_s, "%Y-%m-%d"
    ).date()

    # Statcast lags ~1 day; never ask for today or the future.
    yesterday = date.today() - timedelta(days=1)
    if through:
        end = min(end, through)
    end = min(end, yesterday)

    if days_back:
        recent = end - timedelta(days=days_back - 1)
        if recent > start:
            start = recent
    d, out = start, []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def fetch_pitches(con, year, sleep=2.0, limit_days=None, days_back=None,
                  newest_first=False, verbose=True, include_postseason=False):
    """Fetch any un-ingested day of pitch-level data for `year`.

    Every column Savant returns is stored (see db.append_pitches) - recovering a
    dropped column later would mean re-downloading the season.
    """
    from pybaseball import statcast

    have = db.days_already_ingested(con, "pitches")
    todo = [d for d in season_days(year, days_back=days_back,
                                   include_postseason=include_postseason)
            if d not in have]
    if newest_first:
        todo = todo[::-1]
    if limit_days:
        todo = todo[:limit_days]
    if verbose:
        print(f"[pitches] {len(todo)} day(s) to fetch for {year}")

    for i, day in enumerate(todo, 1):
        try:
            raw = statcast(start_dt=day, end_dt=day, verbose=False)
        except Exception as e:
            print(f"  ! {day} failed: {type(e).__name__}: {e}")
            time.sleep(sleep * 3)
            continue

        if raw is None or len(raw) == 0:
            db.mark_ingested(con, day, 0, "pitches")   # off-day: remember it
            if verbose:
                print(f"  [{i}/{len(todo)}] {day}: no games")
            time.sleep(sleep)
            continue

        chunk = raw.copy()
        chunk["game_date"] = pd.to_datetime(chunk["game_date"]).dt.strftime("%Y-%m-%d")
        n = db.append_pitches(con, chunk)
        db.mark_ingested(con, day, n, "pitches")
        if verbose:
            print(f"  [{i}/{len(todo)}] {day}: {n:,} pitches x {len(chunk.columns)} cols")
        time.sleep(sleep)


def default_snapshot(year):
    """Snapshot label for a leaderboard pull.

    A completed season's leaderboard is final, so it is labelled with that
    season's last day. Only the in-progress season is labelled with today --
    otherwise backfilling four years today would stamp all four with the same
    snapshot_date and the primary key would collapse them into one.
    """
    today = date.today()
    _, end_s = SEASONS.get(year, (None, f"{year}-10-05"))
    end = datetime.strptime(end_s, "%Y-%m-%d").date()
    return today.isoformat() if today <= end else end.isoformat()


def _name(df):
    if {"last_name, first_name"} <= set(df.columns):
        s = df["last_name, first_name"].astype(str)
        return s.str.split(",").str[::-1].str.join(" ").str.strip()
    if {"first_name", "last_name"} <= set(df.columns):
        return (df["first_name"].astype(str).str.strip() + " "
                + df["last_name"].astype(str).str.strip())
    if "last_name" in df.columns:
        return df["last_name"].astype(str)
    return pd.Series(["unknown"] * len(df), index=df.index)


def fetch_expected_stats(con, year, snapshot=None, min_pa=None):
    """Season-to-date expected vs actual leaderboards for hitters and pitchers.

    min_pa overrides the 50-PA leaderboard floor; history pulls pass 1 so a part-time season
    still counts toward a player's usual level (history.py)."""
    from pybaseball import statcast_batter_expected_stats, statcast_pitcher_expected_stats
    snapshot = snapshot or default_snapshot(year)

    for kind, fn, minimum in (
        ("batter", statcast_batter_expected_stats, min_pa or 50),
        ("pitcher", statcast_pitcher_expected_stats, min_pa or 50),
    ):
        try:
            df = fn(year, minimum)
        except Exception as e:
            print(f"  ! expected_stats[{kind}] failed: {type(e).__name__}: {e}")
            continue
        if df is None or len(df) == 0:
            print(f"  ! expected_stats[{kind}] returned nothing")
            continue

        out = pd.DataFrame({
            "snapshot_date": snapshot,
            "player_type": kind,
            "player_id": df.get("player_id"),
            "player_name": _name(df),
            "year": year,
            "pa": df.get("pa"),
            "bip": df.get("bip"),
            "ba": df.get("ba"), "est_ba": df.get("est_ba"),
            "slg": df.get("slg"), "est_slg": df.get("est_slg"),
            "woba": df.get("woba"), "est_woba": df.get("est_woba"),
            # xERA is a 1:1 rescaling of xwOBA onto the ERA scale (Savant glossary).
            # It carries no information beyond est_woba, but capture it so the
            # published number is available without a re-derivation. Pitchers only.
            "era": df.get("era"), "xera": df.get("xera"),
        })
        con.execute(
            "DELETE FROM expected_stats WHERE snapshot_date=? AND player_type=?",
            (snapshot, kind),
        )
        out.to_sql("expected_stats", con, if_exists="append", index=False)
        con.commit()
        print(f"  [expected_stats] {kind}: {len(out)} players")


def fetch_batted_ball(con, year, snapshot=None):
    """Exit velocity / barrel leaderboards - the 'is the contact real' layer."""
    from pybaseball import (statcast_batter_exitvelo_barrels,
                            statcast_pitcher_exitvelo_barrels)
    snapshot = snapshot or default_snapshot(year)

    for kind, fn in (("batter", statcast_batter_exitvelo_barrels),
                     ("pitcher", statcast_pitcher_exitvelo_barrels)):
        try:
            df = fn(year, 30)
        except Exception as e:
            print(f"  ! exitvelo[{kind}] failed: {type(e).__name__}: {e}")
            continue
        if df is None or len(df) == 0:
            continue

        out = pd.DataFrame({
            "snapshot_date": snapshot,
            "player_type": kind,
            "player_id": df.get("player_id"),
            "player_name": _name(df),
            "attempts": df.get("attempts"),
            "avg_hit_speed": df.get("avg_hit_speed"),
            "max_hit_speed": df.get("max_hit_speed"),
            "avg_launch_angle": df.get("avg_hit_angle"),
            "barrels": df.get("barrels"),
            "brl_percent": df.get("brl_percent"),
            "brl_pa": df.get("brl_pa"),
            "ev95percent": df.get("ev95percent"),
        })
        con.execute(
            "DELETE FROM batted_ball WHERE snapshot_date=? AND player_type=?",
            (snapshot, kind),
        )
        out.to_sql("batted_ball", con, if_exists="append", index=False)
        con.commit()
        print(f"  [batted_ball] {kind}: {len(out)} players")


def fetch_sprint_speed(con, year, snapshot=None, min_opp=10):
    """Sprint speed leaderboard - feet per second in a player's fastest one-second window.

    Statcast counts an "opportunity" as a two-plus base run on a non-homer, or a
    home-to-first on a topped or weakly-hit ball, and averages roughly the fastest
    two thirds of them. min_opp=10 is Savant's own qualifying default.

    Column names on this endpoint have drifted before, so every field is read
    through .get() and a missing one lands as NULL rather than raising.
    """
    from pybaseball import statcast_sprint_speed
    snapshot = snapshot or default_snapshot(year)

    try:
        df = statcast_sprint_speed(year, min_opp)
    except Exception as e:
        print(f"  ! sprint_speed failed: {type(e).__name__}: {e}")
        return
    if df is None or len(df) == 0:
        print("  ! sprint_speed returned nothing")
        return

    def col(*names):
        for n in names:
            if n in df.columns:
                return df[n]
        return None

    out = pd.DataFrame({
        "snapshot_date": snapshot,
        "player_id": col("player_id"),
        "player_name": _name(df),
        "year": year,
        "age": col("age"),
        "competitive_runs": col("competitive_runs", "n_competitive_runs", "opportunities"),
        "bolts": col("bolts", "n_bolts"),
        "hp_to_1b": col("hp_to_1b", "hp_to_1b_secs"),
        "sprint_speed": col("sprint_speed", "sprint_speed_fps"),
    })
    out = out[out.player_id.notna()]
    con.execute("DELETE FROM sprint_speed WHERE snapshot_date=?", (snapshot,))
    out.to_sql("sprint_speed", con, if_exists="append", index=False)
    con.commit()
    print(f"  [sprint_speed] {len(out)} players "
          f"(mean {out.sprint_speed.mean():.2f} ft/s)" if len(out) else "  [sprint_speed] none")
