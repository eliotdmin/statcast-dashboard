"""SQLite storage layer for the Statcast dashboard."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "statcast.db"

SCHEMA = """
-- Season-to-date expected-stats leaderboards, snapshotted each run so we can
-- see how a player's divergence moves over time.
CREATE TABLE IF NOT EXISTS expected_stats (
    snapshot_date TEXT,
    player_type   TEXT,      -- 'batter' | 'pitcher'
    player_id     INTEGER,
    player_name   TEXT,
    year          INTEGER,
    pa            INTEGER,
    bip           INTEGER,
    ba            REAL, est_ba  REAL,
    slg           REAL, est_slg REAL,
    woba          REAL, est_woba REAL,
    PRIMARY KEY (snapshot_date, player_type, player_id)
);

CREATE TABLE IF NOT EXISTS batted_ball (
    snapshot_date TEXT,
    player_type   TEXT,
    player_id     INTEGER,
    player_name   TEXT,
    attempts      INTEGER,
    avg_hit_speed REAL,
    max_hit_speed REAL,
    avg_launch_angle REAL,
    barrels       INTEGER,
    brl_percent   REAL,
    brl_pa        REAL,
    ev95percent   REAL,
    PRIMARY KEY (snapshot_date, player_type, player_id)
);

-- Bookkeeping so daily refreshes only fetch what is missing.
CREATE TABLE IF NOT EXISTS ingest_log (
    scope      TEXT,   -- e.g. 'pitches'
    day        TEXT,
    rows       INTEGER,
    fetched_at TEXT,
    PRIMARY KEY (scope, day)
);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    _migrate_pitches(con)
    return con


# Columns the original narrow schema had. If we find a `pitches` table that
# still looks like that AND holds no rows, it predates the switch to storing
# every Savant column - drop it so the wide table is created on first fetch.
# A table with rows is never touched; widening happens per-append instead.
_LEGACY = {"game_pk", "game_date", "batter", "pitcher", "events", "description",
           "launch_speed", "launch_angle", "estimated_woba_using_speedangle",
           "woba_value", "woba_denom", "release_speed", "release_spin_rate",
           "pitch_type", "home_team", "away_team", "inning", "at_bat_number",
           "pitch_number"}


def _migrate_pitches(con):
    cols = set(table_columns(con, "pitches"))
    if not cols or "balls" in cols:
        return                                   # absent, or already wide
    if cols <= _LEGACY:
        n = con.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]
        if n == 0:
            con.execute("DROP TABLE pitches")
            con.execute("DELETE FROM ingest_log WHERE scope='pitches'")
            con.commit()
            print("[db] replaced empty legacy pitches table with the wide schema")


def days_already_ingested(con, scope="pitches"):
    rows = con.execute(
        "SELECT day FROM ingest_log WHERE scope=? AND rows >= 0", (scope,)
    ).fetchall()
    return {r[0] for r in rows}


def mark_ingested(con, day, rows, scope="pitches"):
    from datetime import datetime, timezone
    con.execute(
        "INSERT OR REPLACE INTO ingest_log(scope, day, rows, fetched_at) VALUES (?,?,?,?)",
        (scope, day, rows, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    con.commit()


# ---------------------------------------------------------------------------
# Pitch-level storage.
#
# We store EVERY column Savant returns rather than a hand-picked subset, because
# re-running a backfill to recover a column you did not save costs a full
# re-download. Savant occasionally adds columns mid-season (bat tracking arrived
# this way), so appends align to the live table and widen it when needed instead
# of failing.
# ---------------------------------------------------------------------------

PITCH_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pitches_date   ON pitches(game_date)",
    "CREATE INDEX IF NOT EXISTS idx_pitches_batter ON pitches(batter, game_date)",
    "CREATE INDEX IF NOT EXISTS idx_pitches_pitchr ON pitches(pitcher, game_date)",
    "CREATE INDEX IF NOT EXISTS idx_pitches_count  ON pitches(balls, strikes)",
    "CREATE INDEX IF NOT EXISTS idx_pitches_ptype  ON pitches(pitch_type)",
]


def table_columns(con, table):
    try:
        return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return []


def append_pitches(con, chunk):
    """Append a day of pitch data, reconciling any schema drift."""
    import pandas as pd

    # SQLite cannot store list/dict cells; stringify anything exotic.
    for c in chunk.columns:
        if chunk[c].dtype == object:
            chunk[c] = chunk[c].map(
                lambda v: v if v is None or isinstance(v, (str, int, float, bool))
                else str(v))

    existing = table_columns(con, "pitches")
    if not existing:
        chunk.to_sql("pitches", con, if_exists="append", index=False)
    else:
        new = [c for c in chunk.columns if c not in existing]
        for c in new:                       # Savant added a column - widen.
            con.execute(f'ALTER TABLE pitches ADD COLUMN "{c}"')
        if new:
            existing += new
            con.commit()
        missing = [c for c in existing if c not in chunk.columns]
        for c in missing:                   # Savant dropped one - keep NULLs.
            chunk[c] = None
        chunk = chunk[existing]
        chunk.to_sql("pitches", con, if_exists="append", index=False)

    for stmt in PITCH_INDEXES:
        try:
            con.execute(stmt)
        except Exception:
            pass                            # column absent in this vintage
    con.commit()
    return len(chunk)
