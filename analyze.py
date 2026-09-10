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

# Filled in by build_signals() so run_pipeline can report the fitted speed
# relationship in the payload. Exposing the coefficient is the point: it is a
# number you can argue with, and if it ever comes back near zero the speed
# adjustment below is doing nothing and should be dropped.
LAST_SPEED_FIT = {}


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


def load_sprint_speed(con, snapshot=None):
    snapshot = snapshot or latest_snapshot(con, "sprint_speed")
    if not snapshot:
        return pd.DataFrame()
    return pd.read_sql_query(
        "SELECT player_id, sprint_speed FROM sprint_speed WHERE snapshot_date = ?",
        con, params=(snapshot,))


def speed_adjust(d):
    """Strip the part of a hitter's luck gap that his legs explain.

    THE PROBLEM this solves, stated in the README as a known limitation:
    xwOBA is computed from exit velocity and launch angle alone. It cannot see
    that a hitter runs. A 30 ft/s hitter beats his xwOBA every year, because he
    turns weakly-hit balls into infield singles that the model scores as outs.
    The raw luck gap therefore contains a large PERSISTENT component for fast
    players -- and calls them regression candidates season after season.

    The fix is a regression, not a rule: fit luck_gap on sprint_speed across
    qualified hitters, and treat the RESIDUAL as the part that is actually luck.
    A player is then measured against hitters of his own speed rather than
    against the league.

    This is added ALONGSIDE the raw signal, never in place of it. Which one
    predicts better is an empirical question for regression_test.py, not
    something to assume because the reasoning sounds good.
    """
    m = d.qualified & d.sprint_speed.notna() & d.luck_gap.notna()
    if m.sum() < 30:
        LAST_SPEED_FIT.update({"coef": None, "r2": None, "n": int(m.sum())})
        d["luck_gap_adj"] = d.luck_gap
        return d

    x = d.loc[m, "sprint_speed"].to_numpy(float)
    y = d.loc[m, "luck_gap"].to_numpy(float)
    coef, intercept = np.polyfit(x, y, 1)
    pred_all = intercept + coef * d.sprint_speed
    resid = y - (intercept + coef * x)
    ss_tot = ((y - y.mean()) ** 2).sum()
    LAST_SPEED_FIT.update({
        "coef": float(coef),                 # wOBA points of gap per ft/s
        "r2": float(1 - (resid ** 2).sum() / ss_tot) if ss_tot > 0 else None,
        "n": int(m.sum()),
    })
    # Where speed is unknown, fall back to the raw gap rather than inventing one.
    d["luck_gap_adj"] = (d.luck_gap - pred_all + pred_all.mean()).where(
        d.sprint_speed.notna(), d.luck_gap)
    return d


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
    if out.empty:
        return out

    # Sprint speed applies to hitters only -- for a pitcher it would describe the
    # wrong person entirely, so pitchers keep the raw signal.
    ss = load_sprint_speed(con)
    if ss.empty:
        out["sprint_speed"] = np.nan
    else:
        out = out.merge(ss.drop_duplicates("player_id"), on="player_id", how="left")
        out.loc[out.player_type != "batter", "sprint_speed"] = np.nan

    # Pitchers keep the raw gap; only the batter rows get the speed residual
    # written back. Assigning the whole frame through .loc would silently drop a
    # column the subset added, so the new column is written explicitly.
    bats = out.player_type == "batter"
    out["luck_gap_adj"] = out["luck_gap"]
    if bats.any():
        out.loc[bats, "luck_gap_adj"] = speed_adjust(out[bats].copy())["luck_gap_adj"].to_numpy()

    for kind, min_pa in (("batter", MIN_PA_BATTER), ("pitcher", MIN_PA_PITCHER)):
        m = out.player_type == kind
        pool = out[m & out.qualified]
        mu = pool.luck_gap_adj.mean() if len(pool) > 5 else out.loc[m, "luck_gap_adj"].mean()
        sd = pool.luck_gap_adj.std(ddof=1) if len(pool) > 5 else out.loc[m, "luck_gap_adj"].std(ddof=1)
        z = (out.loc[m, "luck_gap_adj"] - mu) / (sd if sd and sd > 0 else np.nan)
        out.loc[m, "luck_z_adj"] = z
        out.loc[m, "outlook_adj"] = z if kind == "batter" else -z

    out["pct_sprint"] = np.nan
    q = out.qualified & out.sprint_speed.notna() & (out.player_type == "batter")
    if q.sum() > 5:
        out.loc[q, "pct_sprint"] = (out.loc[q, "sprint_speed"].rank(pct=True) * 100).round(0)

    if bb.empty:
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

    THE SUBTLETY: in older Statcast vintages `estimated_woba_using_speedangle`
    is NULL for strikeouts, walks and HBP - there is no batted ball to model.
    (In the 2026 data Savant populates it at the event's linear weight instead;
    the fold-in below is a no-op there, and stays correct either way, which is
    why it is written as a coalesce rather than a branch.) Averaging that column
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
    # The backfill windows start before Opening Day to catch the Seoul and Tokyo
    # series, which also pulls in spring training. 50k spring pitches are in the
    # table; none of them belong in a rate stat.
    where.append("game_type = 'R'")
    if days:
        where.append("game_date >= date('now', ?)"); params.append(f"-{days} days")
    if year:
        where.append("game_date >= ? AND game_date <= ?")
        params += [f"{year}-01-01", f"{year}-12-31"]

    df = pd.read_sql_query(
        f"""SELECT {col} AS pid, game_date, game_pk, at_bat_number, events, type,
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
    # `type == 'X'` is the only reliable contact test. Savant now populates
    # xw_bip on PA-ending strikeouts and walks too, so notna() would flag them
    # as balls in play. See DATA_DICTIONARY.md.
    df["is_bip"] = df["type"].eq("X")
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
