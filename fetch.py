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

# Regular season windows. Extend as needed.
SEASON_START = {2024: "2024-03-28", 2025: "2025-03-27", 2026: "2026-03-26"}


def season_days(year, through=None, days_back=None):
    start = datetime.strptime(SEASON_START.get(year, f"{year}-03-28"), "%Y-%m-%d").date()
    # Statcast lags ~1 day; never ask for today.
    end = through or (date.today() - timedelta(days=1))
    if end.year > year:
        end = date(year, 11, 5)
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
                  newest_first=False, verbose=True):
    """Fetch any un-ingested day of pitch-level data for `year`.

    Every column Savant returns is stored (see db.append_pitches) - recovering a
    dropped column later would mean re-downloading the season.
    """
    from pybaseball import statcast

    have = db.days_already_ingested(con, "pitches")
    todo = [d for d in season_days(year, days_back=days_back) if d not in have]
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


def fetch_expected_stats(con, year, snapshot=None):
    """Season-to-date expected vs actual leaderboards for hitters and pitchers."""
    from pybaseball import statcast_batter_expected_stats, statcast_pitcher_expected_stats
    snapshot = snapshot or date.today().isoformat()

    for kind, fn, minimum in (
        ("batter", statcast_batter_expected_stats, 50),
        ("pitcher", statcast_pitcher_expected_stats, 50),
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
    snapshot = snapshot or date.today().isoformat()

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
