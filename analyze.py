"""Turn stored Statcast data into breakout/regression signals and ROS projections.

Method, stated plainly so the numbers can be argued with
--------------------------------------------------------
1. LUCK GAP. Statcast's expected stats (est_woba) model what a batted ball
   *deserved* given exit velocity and launch angle, stripping out defense and
   park. The gap between deserved and actual is the core signal:

       luck_gap = est_woba - woba

   For a HITTER a positive gap means he has hit the ball better than his line
   shows -> positive-regression / breakout candidate.
   For a PITCHER the sign inverts: a positive gap means hitters deserved more
   than they got against him -> he has been lucky, negative regression ahead.
   `outlook` below normalises that so positive always means "expect improvement".

2. CALIBRATION. A raw .030 gap means nothing without context, so each gap is
   turned into a z-score against that season's own distribution of gaps for
   that player type. |z| >= 1.5 is flagged.

3. SAMPLE GATES. Expected-stat gaps are noisy early. We require a minimum PA
   (default 150 for hitters, 150 batters faced for pitchers) before a player is
   eligible to be flagged, which is roughly where wOBA-type metrics start to
   carry signal.

4. PROJECTION. Rest-of-season is a shrinkage (empirical-Bayes / Marcel-style)
   estimate: observed skill pulled toward league average by an amount that
   depends on sample size.

       proj = (est_woba * PA + league_mean * K) / (PA + K)

   with K a regression constant in PA. This is deliberately simple and
   transparent - it is NOT ZiPS or Steamer, it has no aging curve, no park
   factors, and no playing-time forecast. It answers one question: given how
   he has actually hit the ball, what is a reasonable expectation going
   forward?
"""
import sqlite3
from datetime import date

import numpy as np
import pandas as pd

import db

# Regression constants, in plate appearances. Larger = more skepticism.
K_BATTER = 200
K_PITCHER = 250

MIN_PA_BATTER = 150
MIN_PA_PITCHER = 150

FLAG_Z = 1.5


def latest_snapshot(con, table="expected_stats"):
    row = con.execute(f"SELECT MAX(snapshot_date) FROM {table}").fetchone()
    return row[0] if row else None


def load_expected(con, snapshot=None):
    snapshot = snapshot or latest_snapshot(con)
    if not snapshot:
        return pd.DataFrame()
    return pd.read_sql_query(
        "SELECT * FROM expected_stats WHERE snapshot_date = ?", con, params=(snapshot,)
    )


def load_batted_ball(con, snapshot=None):
    snapshot = snapshot or latest_snapshot(con, "batted_ball")
    if not snapshot:
        return pd.DataFrame()
    return pd.read_sql_query(
        "SELECT * FROM batted_ball WHERE snapshot_date = ?", con, params=(snapshot,)
    )


def build_signals(con):
    """Return one tidy frame of every qualified player with signals attached."""
    exp = load_expected(con)
    if exp.empty:
        return pd.DataFrame()
    bb = load_batted_ball(con)

    frames = []
    for kind, min_pa, K in (("batter", MIN_PA_BATTER, K_BATTER),
                            ("pitcher", MIN_PA_PITCHER, K_PITCHER)):
        d = exp[exp.player_type == kind].copy()
        if d.empty:
            continue
        for c in ("ba", "est_ba", "slg", "est_slg", "woba", "est_woba", "pa", "bip"):
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d = d.dropna(subset=["woba", "est_woba", "pa"])

        d["luck_gap"] = d.est_woba - d.woba
        d["ba_gap"] = d.est_ba - d.ba
        d["slg_gap"] = d.est_slg - d.slg

        # Calibrate against qualified players only, so the scale is not dragged
        # around by tiny-sample outliers.
        pool = d[d.pa >= min_pa]
        mu = pool.luck_gap.mean() if len(pool) > 5 else d.luck_gap.mean()
        sd = pool.luck_gap.std(ddof=1) if len(pool) > 5 else d.luck_gap.std(ddof=1)
        d["luck_z"] = (d.luck_gap - mu) / (sd if sd and sd > 0 else np.nan)

        # Positive outlook always means "expect things to get better for him".
        d["outlook"] = d.luck_z if kind == "batter" else -d.luck_z

        # Shrinkage projection toward the qualified-player mean.
        league = pool.est_woba.mean() if len(pool) > 5 else d.est_woba.mean()
        d["league_mean_est_woba"] = league
        d["proj_woba_ros"] = (d.est_woba * d.pa + league * K) / (d.pa + K)
        d["proj_vs_current"] = d.proj_woba_ros - d.woba

        d["qualified"] = d.pa >= min_pa
        d["flagged"] = d.qualified & (d.luck_z.abs() >= FLAG_Z)
        d["direction"] = np.where(
            d.outlook > 0, "positive regression", "negative regression"
        )

        # Percentile ranks among qualified players.
        for col, name in (("est_woba", "pct_est_woba"), ("woba", "pct_woba")):
            d[name] = np.nan
            q = d.qualified
            if q.sum() > 5:
                d.loc[q, name] = (d.loc[q, col].rank(pct=True) * 100).round(0)

        frames.append(d)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if out.empty or bb.empty:
        return out

    bbm = bb[["player_type", "player_id", "avg_hit_speed", "brl_percent",
              "ev95percent", "avg_launch_angle", "attempts"]]
    out = out.merge(bbm, on=["player_type", "player_id"], how="left")

    # Contact-quality percentiles give the "is this real?" corroboration.
    for col, name in (("avg_hit_speed", "pct_ev"),
                      ("brl_percent", "pct_barrel"),
                      ("ev95percent", "pct_hardhit")):
        out[name] = np.nan
        for kind in out.player_type.unique():
            m = (out.player_type == kind) & out.qualified & out[col].notna()
            if m.sum() > 5:
                out.loc[m, name] = (out.loc[m, col].rank(pct=True) * 100).round(0)
    return out


def pa_level(con, player_ids, role="batter", days=None, year=None):
    """Per-plate-appearance xwOBA and wOBA, correctly handling non-contact events.

    THE SUBTLETY: `estimated_woba_using_speedangle` is NULL for strikeouts,
    walks and HBP - there is no batted ball to model. Averaging that column
    across all PA silently drops those events from the numerator while the
    denominator still counts them, which inflates xwOBA for every high-strikeout
    hitter. Savant's own xwOBA folds the non-contact events back in at their
    ACTUAL value (a strikeout is worth 0 whether expected or not; a walk is
    worth its linear weight). So:

        xwOBA_pa = estimated_woba_using_speedangle   if batted ball
                 = woba_value                        otherwise (K, BB, HBP)

    wOBA itself needs no linear-weight table at all - Savant ships the numerator
    and denominator per event, so wOBA = sum(woba_value) / sum(woba_denom).
    """
    if not player_ids:
        return pd.DataFrame()
    col = "batter" if role == "batter" else "pitcher"
    where, params = [f"{col} IN ({','.join('?' * len(player_ids))})", ], list(player_ids)
    where.append("woba_denom = 1")          # one row per completed PA
    if days:
        where.append("game_date >= date('now', ?)"); params.append(f"-{days} days")
    if year:
        where.append("game_date >= ? AND game_date <= ?")
        params += [f"{year}-01-01", f"{year}-12-31"]

    df = pd.read_sql_query(
        f"""SELECT {col} AS pid, game_date, game_pk, at_bat_number, events,
                   estimated_woba_using_speedangle AS xw_bip,
                   woba_value, woba_denom, launch_speed, launch_angle
            FROM pitches WHERE {' AND '.join(where)}
            ORDER BY game_date, game_pk, at_bat_number""",
        con, params=params)
    if df.empty:
        return df

    df["woba_value"] = pd.to_numeric(df.woba_value, errors="coerce").fillna(0.0)
    df["xw_bip"] = pd.to_numeric(df.xw_bip, errors="coerce")
    # Fold non-contact events back in at their actual value.
    df["xwoba_pa"] = df.xw_bip.where(df.xw_bip.notna(), df.woba_value)
    df["woba_pa"] = df.woba_value
    df["is_bip"] = df.xw_bip.notna()
    return df


def rolling_trends(con, player_ids, role="batter", window=50, days=120):
    """Trailing-window xwOBA and wOBA per player, measured in PLATE APPEARANCES.

    A PA window rather than a calendar window keeps the sample size constant, so
    a bench player's line is not noisier than a regular's at the same x position.
    """
    df = pa_level(con, player_ids, role=role, days=days)
    if df.empty:
        return {}
    out = {}
    for pid, g in df.groupby("pid"):
        g = g.reset_index(drop=True)
        g["x_roll"] = g.xwoba_pa.rolling(window, min_periods=max(15, window // 3)).mean()
        g["w_roll"] = g.woba_pa.rolling(window, min_periods=max(15, window // 3)).mean()
        g["ev_roll"] = g.launch_speed.rolling(window, min_periods=10).mean()
        g = g.dropna(subset=["x_roll"])
        if g.empty:
            continue
        step = max(1, len(g) // 60)          # thin for payload size
        out[int(pid)] = [
            {"d": r.game_date, "pa": int(i),
             "x": round(float(r.x_roll), 4), "w": round(float(r.w_roll), 4),
             "ev": None if pd.isna(r.ev_roll) else round(float(r.ev_roll), 1)}
            for i, r in enumerate(g.itertuples()) if i % step == 0 or i == len(g) - 1
        ]
    return out
