#!/usr/bin/env python3
"""Marcel the Monkey vs everything this project has built.

Marcel (Tom Tango, 2004) is the deliberately stupid baseline: weight the last
three seasons 5/4/3, regress hard toward the league mean, nudge for age. It has
no batted-ball data, no swing tracking, no model. It is the line a forecaster
has to clear before anyone should care about it.

Two honest complications, handled explicitly:

  1. Every model in predict.py saw only ONE window. Marcel sees a hitter's whole
     career. That is a handicap I imposed on my own models, not a property of
     Statcast, so the fair fight is run both ways: Marcel against the models as
     they stand, and against models that also get history.

  2. Marcel forecasts a season from seasons. Applying it to a one-month horizon
     is an extrapolation of the idea, so the season-to-season comparison is the
     one that is truly on Marcel's home ground, and it is reported first.

Nothing is fit on the test year in any arm.
"""
import json, math, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("/home/claude/predict.py").read().split("# ======================================================================= 1")[0])
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
OUT = {}

# ---------------------------------------------------------------- season table
seas = {}
for (b, y), g in raw.groupby(["batter", "game_year"]):
    a = agg(g)
    seas[(b, y)] = dict(pa=a["pa"], woba=a["woba"], xwoba=a["xwoba"], age=g["age"].max(),
                        wn=float(g.woba_num.sum()), xn=float(g.xwoba_num.sum()))
# league mean by season
lgs = {}
for y in sorted(raw.game_year.unique()):
    s = raw[raw.game_year == y]
    lgs[y] = float(s.woba_num.sum() / s.pa.sum())
print("league wOBA by season:", {k: round(v, 4) for k, v in lgs.items()})


def marcel(b, y, R=1200.0, use_x=False, w=(5, 4, 3), age_adj=True, thru=None):
    """Classic Marcel for hitter b entering season y.

    thru: optionally add season y's own months 0..thru-1 at the top weight,
    which is what a mid-season forecaster would actually have.
    """
    num = den = 0.0
    for k, yy in zip(w, (y - 1, y - 2, y - 3)):
        s = seas.get((b, yy))
        if not s or not s["pa"]: continue
        num += k * (s["xn"] if use_x else s["wn"]); den += k * s["pa"]
    if thru is not None:
        g = raw[(raw.batter == b) & (raw.game_year == y) & (raw.mon < thru)]
        if len(g):
            col = "xwoba_num" if use_x else "woba_num"
            num += w[0] * float(g[col].sum()); den += w[0] * float(g.pa.sum())
    lg = lgs.get(y, np.mean(list(lgs.values())))
    if den == 0: return lg, 0.0
    pred = (num + R * lg) / (den + R)
    if age_adj:
        a = seas.get((b, y), {}).get("age")
        if a is None:
            g = raw[(raw.batter == b) & (raw.game_year == y)]
            a = float(g["age"].max()) if len(g) else 29
        pred *= (1 + (29 - a) * 0.006) if a < 29 else (1 + (29 - a) * 0.003)
    return pred, den / w[0]


# ================================================================ 1 SEASON
hr("1  MARCEL ON ITS HOME GROUND — forecasting a full season")
print("""  Only 2026 can be forecast with a full three-year Marcel, since the backfill
  starts in 2023. 213 hitters with 250+ PA in both 2025 and 2026.""")
rows = []
for (b, y), s in seas.items():
    if y != 2026 or s["pa"] < 250: continue
    prev = seas.get((b, 2025))
    if not prev or prev["pa"] < 250: continue
    m_w, _ = marcel(b, 2026)
    m_x, _ = marcel(b, 2026, use_x=True)
    m_wn, _ = marcel(b, 2026, age_adj=False)
    rows.append(dict(b=b, act=s["woba"], pa=s["pa"], prev_w=prev["woba"], prev_x=prev["xwoba"],
                     marcel=m_w, marcel_x=m_x, marcel_noage=m_wn))
S = pd.DataFrame(rows)
print(f"\n  n = {len(S)}   actual 2026 wOBA: mean {np.average(S.act, weights=S.pa):.4f}")
print(f"  {'forecaster':>38} {'R^2':>9} {'RMSE':>9} {'corr':>8}")
res1 = {}
for lab, col in (("last season's wOBA (raw)", "prev_w"), ("last season's xwOBA (raw)", "prev_x"),
                 ("MARCEL (5/4/3, R=1200, age)", "marcel"),
                 ("MARCEL without the age bump", "marcel_noage"),
                 ("MARCEL built on xwOBA", "marcel_x")):
    r2 = wr2(S.act, S[col], S.pa); rm = wrmse(S.act, S[col], S.pa)
    cr = np.corrcoef(S.act, S[col])[0, 1]
    print(f"  {lab:>38} {r2:>9.4f} {rm:>9.4f} {cr:>8.3f}")
    res1[lab] = dict(r2=float(r2), rmse=float(rm), corr=float(cr))
# recalibrated raw predictors get a fair shot: fit the shrinkage on 2025 pairs
tr_rows = []
for (b, y), s in seas.items():
    if y != 2025 or s["pa"] < 250: continue
    p = seas.get((b, 2024))
    if not p or p["pa"] < 250: continue
    tr_rows.append(dict(act=s["woba"], pa=s["pa"], prev_w=p["woba"], prev_x=p["xwoba"]))
T = pd.DataFrame(tr_rows)
for lab, col in (("last season's wOBA, optimally shrunk", "prev_w"),
                 ("last season's xwOBA, optimally shrunk", "prev_x")):
    p, b_ = fit_ols(T[[col]].values, T.act.values, T.pa.values, S[[col]].values)
    r2 = wr2(S.act, p, S.pa)
    print(f"  {lab:>38} {r2:>9.4f} {wrmse(S.act,p,S.pa):>9.4f} "
          f"{np.corrcoef(S.act,p)[0,1]:>8.3f}")
    res1[lab] = dict(r2=float(r2))
OUT["season"] = res1

# ================================================================ 2 MONTHLY
hr("2  THE ONE-MONTH HORIZON — the test set every earlier number used")
D = build(1, 40)
D["mar"] = [marcel(r.batter, r.year, thru=r.start + 1)[0] for r in D.itertuples()]
D["mar_x"] = [marcel(r.batter, r.year, thru=r.start + 1, use_x=True)[0] for r in D.itertuples()]
D["mar_hist"] = [marcel(r.batter, r.year)[0] for r in D.itertuples()]
tr, te = D[D.year <= 2025], D[D.year == 2026]
print(f"  train {len(tr):,}   test {len(te):,} hitter-months in 2026")
print(f"\n  {'forecaster':>44} {'test R^2':>10} {'RMSE':>9}")
res2 = {}


def score(lab, pred, store=True):
    r2 = wr2(te.y_woba.values, pred, te.y_pa.values)
    rm = wrmse(te.y_woba.values, pred, te.y_pa.values)
    print(f"  {lab:>44} {r2:>10.4f} {rm:>9.4f}")
    if store: res2[lab] = dict(r2=float(r2), rmse=float(rm))
    return r2


print("  " + "-" * 63)
print(f"  {'--- current window only (last night''s models) ---':>44}")
for lab, cols in (("this month's wOBA", ["x_woba"]), ("this month's xwOBA", ["x_xwoba"])):
    p, _ = fit_ols(tr[cols].values, tr.y_woba.values, tr.y_pa.values, te[cols].values)
    score(lab, p)
BASE = ["x_woba", "x_xwoba"]
QUAL = ["x_ev", "x_la", "x_hardhit", "x_barrel", "x_sweet", "x_sd_ev", "x_sd_la", "x_distance"]
DISC = ["x_k", "x_bb", "x_swing", "x_zswing", "x_chase", "x_whiff", "x_fpsw", "x_tksw"]
BATT = ["x_gb", "x_fb", "x_ld", "x_pop", "x_pull", "x_spray", "x_sd_spray", "x_bip_rate"]
SWG = ["x_bat_speed", "x_swing_len", "x_attack_angle", "x_attack_dir", "x_tilt",
       "x_contact_depth", "x_contact_x", "x_sd_attack_angle", "x_sd_bat_speed"]
CTX = ["x_pa", "x_home_share", "x_if_strat", "x_if_shade", "x_of_strat", "x_fb_seen",
       "x_brk_seen", "x_pvelo", "age", "stand"]
SPD = ["x_gb_single", "x_gidp", "x_triple"]
FULL = [c for c in BASE + QUAL + DISC + BATT + SPD + CTX + SWG if c in D.columns]


def gbm_score(lab, cols, store=True):
    cols = [c for c in cols if c in D.columns]
    imp = SimpleImputer(strategy="median").fit(tr[cols].values.astype(float))
    Xtr, Xte = imp.transform(tr[cols].values.astype(float)), imp.transform(te[cols].values.astype(float))
    m = HistGradientBoostingRegressor(max_iter=350, learning_rate=.04, max_depth=3,
                                      min_samples_leaf=40, l2_regularization=1.,
                                      random_state=7).fit(Xtr, tr.y_woba.values,
                                                          sample_weight=tr.y_pa.values.astype(float))
    return score(lab, m.predict(Xte), store), m, imp, cols


gbm_score("full 48-feature model (boosted trees)", FULL)
print("  " + "-" * 63)
print(f"  {'--- Marcel, which sees the whole career ---':>44}")
score("MARCEL, prior seasons only", te.mar_hist.values)
score("MARCEL + this season to date", te.mar.values)
score("MARCEL built on xwOBA", te.mar_x.values)
print("  " + "-" * 63)
print(f"  {'--- the fair fight: models that also get history ---':>44}")
gbm_score("full model + Marcel as one extra feature", FULL + ["mar"])
gbm_score("Marcel + this month's wOBA and xwOBA only", ["mar", "x_woba", "x_xwoba"])
gbm_score("Marcel + contact quality, no wOBA/xwOBA", ["mar"] + QUAL + SWG)
p, bb = fit_ols(tr[["mar", "x_xwoba"]].values, tr.y_woba.values, tr.y_pa.values,
                te[["mar", "x_xwoba"]].values)
score("Marcel + xwOBA, plain linear", p)
print(f"       (that linear blend weights Marcel {bb[1]:+.3f}, this month's xwOBA {bb[2]:+.3f})")
OUT["month"] = res2
OUT["blend_coef"] = [float(bb[1]), float(bb[2])]

# ================================================================ 3 fifths
hr("3  THE SORTING TEST, WITH MARCEL ADDED")
print("""  The comparison used everywhere else: sort 2026 hitter-months into fifths by
  each signal, then report what those hitters ACTUALLY hit the next month.""")
r2f, mf, impf, colsf = gbm_score("(refit full model for the sort)", FULL, store=False)
Xte_f = impf.transform(te[colsf].values.astype(float))
te = te.copy(); te["full"] = mf.predict(Xte_f)
print(f"\n  {'sorted by':>34} {'bottom fifth':>13} {'top fifth':>11} {'spread':>9}")
SORT = {}
for lab, col in (("what he just hit (wOBA)", "x_woba"), ("xwOBA", "x_xwoba"),
                 ("MARCEL", "mar"), ("the 48-feature model", "full")):
    s = te.sort_values(col); n = len(s)
    lo = s.iloc[:n // 5]; hi = s.iloc[-(n // 5):]
    a = np.average(lo.y_woba, weights=lo.y_pa); b_ = np.average(hi.y_woba, weights=hi.y_pa)
    print(f"  {lab:>34} {a:>13.4f} {b_:>11.4f} {b_-a:>+9.4f}")
    SORT[lab] = dict(lo=float(a), hi=float(b_), spread=float(b_ - a))
OUT["sort"] = SORT

# ================================================================ 4 ceiling
hr("4  AGAINST THE CEILING")
sig2 = 0.2258
vb = float(np.var(raw[raw.pa >= 60].groupby("batter").apply(
    lambda g: np.average(g.woba_num / g.pa, weights=g.pa)), ddof=1))
mpa = float(np.average(te.y_pa))
ceil = vb / (vb + sig2 / mpa)
print(f"  mean target-month PA in the test set: {mpa:.0f}")
print(f"  best possible R^2 at that sample size: {ceil:.3f}")
print(f"\n  {'forecaster':>44} {'R^2':>9} {'% of knowable':>15}")
for lab in ("this month's xwOBA", "MARCEL + this season to date",
            "full 48-feature model (boosted trees)",
            "full model + Marcel as one extra feature"):
    if lab in res2:
        print(f"  {lab:>44} {res2[lab]['r2']:>9.4f} {100*res2[lab]['r2']/ceil:>14.0f}%")
OUT["ceiling"] = dict(ceiling=float(ceil), mean_pa=mpa)
Path("/home/claude/out/marcel.json").write_text(json.dumps(OUT, indent=1, default=float))
print("\nwrote /home/claude/out/marcel.json")
