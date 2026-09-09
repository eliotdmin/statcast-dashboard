"""Offline self-test: proves the analysis math with synthetic data (no network).

Run:  python3 selftest.py
"""
import sqlite3, sys, tempfile, os
from pathlib import Path
import numpy as np, pandas as pd

import db as dbmod

tmp = Path(tempfile.mkdtemp()) / "t.db"
dbmod.DB_PATH = tmp
import analyze

rng = np.random.default_rng(7)
N, SNAP = 200, "2026-08-29"
con = dbmod.connect()

def make(kind):
    est = rng.normal(0.320, 0.035, N).clip(0.200, 0.480)
    noise = rng.normal(0, 0.022, N)
    woba = (est - noise).clip(0.150, 0.520)
    # two deliberate extremes we can assert on
    est[0], woba[0] = 0.400, 0.290      # huge positive gap  (+.110)
    est[1], woba[1] = 0.270, 0.380      # huge negative gap  (-.110)
    return pd.DataFrame({
        "snapshot_date": SNAP, "player_type": kind,
        "player_id": [10_000 + i if kind=="batter" else 20_000+i for i in range(N)],
        "player_name": [f"{kind.title()} {i}" for i in range(N)],
        "year": 2026,
        "pa": rng.integers(160, 600, N), "bip": rng.integers(90, 400, N),
        "ba": woba*0.8, "est_ba": est*0.8,
        "slg": woba*1.4, "est_slg": est*1.4,
        "woba": woba, "est_woba": est,
    })

for k in ("batter","pitcher"):
    make(k).to_sql("expected_stats", con, if_exists="append", index=False)
con.commit()

sig = analyze.build_signals(con)
fails = []
def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else f"  <- {detail}"))
    if not cond: fails.append(name)

print("\n=== analysis self-test ===")
check("signals produced", not sig.empty)
check("both player types present", set(sig.player_type)=={"batter","pitcher"})

b = sig[sig.player_type=="batter"].set_index("player_id")
p = sig[sig.player_type=="pitcher"].set_index("player_id")

check("luck_gap = est_woba - woba",
      np.allclose(b.luck_gap, b.est_woba - b.woba))

# The batter with est .400 / actual .290 is the extreme unlucky case.
check("unlucky batter has large positive z", b.loc[10000,"luck_z"] > 2.5,
      f"z={b.loc[10000,'luck_z']:.2f}")
check("lucky batter has large negative z",   b.loc[10001,"luck_z"] < -2.5,
      f"z={b.loc[10001,'luck_z']:.2f}")

# SIGN CONVENTION - the bug most likely to go unnoticed.
check("batter outlook == +z (unlucky hitter -> improve)",
      np.allclose(b.outlook, b.luck_z))
check("pitcher outlook == -z (lucky pitcher -> decline)",
      np.allclose(p.outlook, -p.luck_z))
check("unlucky batter labelled positive regression",
      b.loc[10000,"direction"]=="positive regression", b.loc[10000,"direction"])
check("pitcher who allowed less than deserved is a NEGATIVE regression candidate",
      p.loc[20000,"direction"]=="negative regression", p.loc[20000,"direction"])

# Shrinkage must pull toward league mean and never overshoot the raw input.
lm = b.league_mean_est_woba.iloc[0]
hi = b.est_woba.idxmax()
check("projection pulled toward league mean",
      abs(b.loc[hi,"proj_woba_ros"] - lm) < abs(b.loc[hi,"est_woba"] - lm),
      f"proj={b.loc[hi,'proj_woba_ros']:.3f} est={b.loc[hi,'est_woba']:.3f} lg={lm:.3f}")
check("projection stays between est_woba and league mean",
      ((b.proj_woba_ros - lm) * (b.est_woba - lm) >= 0).all())

# Bigger sample -> less shrinkage. Compare two synthetic players directly.
def proj(est, pa, lm, K=analyze.K_BATTER): return (est*pa + lm*K)/(pa+K)
small, big = proj(0.420, 160, lm), proj(0.420, 600, lm)
check("more PA -> projection closer to observed skill", big > small,
      f"160PA={small:.3f} 600PA={big:.3f}")

check("flagging respects z threshold",
      ((sig.luck_z.abs() >= analyze.FLAG_Z) | ~sig.flagged.fillna(False)).all())
check("all flagged players are qualified", bool(sig[sig.flagged].qualified.all()))
check("percentiles in 0-100", bool(sig.pct_est_woba.dropna().between(0,100).all()))

print(f"\n{len(sig)} rows analysed | {int(sig.flagged.sum())} flagged "
      f"| {'ALL PASS' if not fails else str(len(fails))+' FAILURE(S)'}")
sys.exit(1 if fails else 0)
