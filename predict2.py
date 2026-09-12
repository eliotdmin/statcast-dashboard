#!/usr/bin/env python3
"""Follow-ups to predict.py, plus export of a portable model.

  A  the noise floor, printed properly
  B  the crossover: wOBA vs xwOBA advantage as the window lengthens
  C  ablations: how much of the model's edge is playing time rather than hitting
  D  reliability of the fitted metric
  E  the gap, controlling for the level of xwOBA
  F  export: standardised linear coefficients + a real hitter-month panel
"""
import json, math, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("/home/claude/predict.py").read().split("# ======================================================================= 1")[0])

from sklearn.linear_model import RidgeCV
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
R2 = {}

# ---------------------------------------------------------------- A
hr("A  THE NOISE FLOOR")
pairs = []
for (b, y), g in raw.groupby(["batter", "game_year"]):
    g = g[g.pa >= 30]; v = g[["pa", "woba_num"]].values
    for i in range(len(v)):
        for j in range(i + 1, len(v)):
            p1, n1 = v[i]; p2, n2 = v[j]
            pairs.append(((n1/p1 - n2/p2) ** 2, 1/p1 + 1/p2))
P = np.array(pairs); A = np.c_[np.ones(len(P)), P[:, 1]]
coef, *_ = np.linalg.lstsq(A, P[:, 0], rcond=None)
var_drift, sigma2 = max(coef[0], 0), coef[1]
BET = raw[raw.pa >= 60]
btrue = BET.groupby("batter").apply(lambda g: np.average(g.woba_num/g.pa, weights=g.pa))
vb = np.var(btrue, ddof=1)
print(f"  {len(P):,} within-season month pairs")
print(f"  per-PA outcome variance      sigma^2 = {sigma2:.4f}   (sd {math.sqrt(sigma2):.3f} per PA)")
print(f"  real month-to-month drift    sd      = {math.sqrt(var_drift):.4f}")
print(f"  spread of hitter true talent sd      = {math.sqrt(vb):.4f}  ({len(btrue)} hitters)")
print(f"\n  {'PA in month':>12} {'noise sd':>10} {'signal share':>13} {'ceiling R^2':>13}")
FLOOR = []
for n in (40, 60, 80, 100, 150, 250, 400, 600):
    noise = sigma2 / n
    total = vb + var_drift + noise
    share = (vb + var_drift) / total
    print(f"  {n:>12} {math.sqrt(noise):>10.4f} {share:>13.3f} {vb/total:>13.3f}")
    FLOOR.append(dict(pa=n, noise_sd=math.sqrt(noise), signal=share, ceiling=vb/total))
R2["floor"] = dict(sigma2=float(sigma2), drift_sd=float(math.sqrt(var_drift)),
                   talent_sd=float(math.sqrt(vb)), table=FLOOR)
print("""
  Reading: at 60 PA in a month, 82% of the spread in observed wOBA between
  hitters is noise, not hitting. A perfect forecaster - one that knew every
  hitter's true talent exactly - would still only reach R^2 = 0.18 against that
  month's observed wOBA, because the target is mostly coin flips. Every R^2
  below should be read against this ceiling, not against 1.0.""")

# ---------------------------------------------------------------- B
hr("B  THE CROSSOVER — xwOBA's advantage shrinks as the window grows")
SWEEP = []
print(f"  {'window':>12} {'n test':>8} {'wOBA R^2':>10} {'xwOBA R^2':>11} {'both':>9} {'edge':>9}")
for W, min_pa, lab in ((1, 40, "1 month"), (1, 70, "1 month 70+"), (2, 80, "2 months"),
                       (2, 140, "2 months 140+"), (3, 110, "3 months")):
    D = build(W, min_pa); tr, te = D[D.year <= 2025], D[D.year == 2026]
    if len(te) < 60: continue
    out = {}
    for k, cols in (("woba", ["x_woba"]), ("xwoba", ["x_xwoba"]), ("both", ["x_woba", "x_xwoba"])):
        p, _ = fit_ols(tr[cols].values, tr.y_woba.values, tr.y_pa.values, te[cols].values)
        out[k] = wr2(te.y_woba.values, p, te.y_pa.values)
    print(f"  {lab:>12} {len(te):>8,} {out['woba']:>10.4f} {out['xwoba']:>11.4f} "
          f"{out['both']:>9.4f} {out['xwoba']-out['woba']:>+9.4f}")
    SWEEP.append(dict(label=lab, W=W, min_pa=min_pa, n=len(te), **{k: float(v) for k, v in out.items()}))
# season level
seas = []
for (b, y), g in raw.groupby(["batter", "game_year"]):
    a = agg(g)
    if a["pa"] >= 250: seas.append(dict(batter=b, year=y, **{f"x_{k}": v for k, v in a.items()}))
S = pd.DataFrame(seas); nx = S.copy(); nx["year"] -= 1
J = S.merge(nx[["batter", "year", "x_woba", "x_pa"]].rename(columns={"x_woba": "y_woba", "x_pa": "y_pa"}),
            on=["batter", "year"])
tr, te = J[J.year <= 2024], J[J.year == 2025]
out = {}
for k, cols in (("woba", ["x_woba"]), ("xwoba", ["x_xwoba"]), ("both", ["x_woba", "x_xwoba"])):
    p, _ = fit_ols(tr[cols].values, tr.y_woba.values, tr.y_pa.values, te[cols].values)
    out[k] = wr2(te.y_woba.values, p, te.y_pa.values)
print(f"  {'full season':>12} {len(te):>8,} {out['woba']:>10.4f} {out['xwoba']:>11.4f} "
      f"{out['both']:>9.4f} {out['xwoba']-out['woba']:>+9.4f}")
SWEEP.append(dict(label="full season", W=6, min_pa=250, n=len(te), **{k: float(v) for k, v in out.items()}))
R2["sweep"] = SWEEP

# ---------------------------------------------------------------- C
hr("C  ABLATION — is the model predicting hitting, or predicting playing time?")
print("""  x_pa turned up as the second most important feature. Plate appearances in a
  month are not a hitting skill; they are a manager's opinion. A model that uses
  them is partly forecasting the lineup card. Run the whole thing with and
  without, so the two signals are not conflated.""")
BASE=["x_woba","x_xwoba"]
QUAL=["x_ev","x_la","x_hardhit","x_barrel","x_sweet","x_sd_ev","x_sd_la","x_distance"]
DISC=["x_k","x_bb","x_swing","x_zswing","x_chase","x_whiff","x_fpsw","x_tksw"]
BATTED=["x_gb","x_fb","x_ld","x_pop","x_pull","x_spray","x_sd_spray","x_bip_rate"]
SWING=["x_bat_speed","x_swing_len","x_attack_angle","x_attack_dir","x_tilt","x_contact_depth",
       "x_contact_x","x_sd_attack_angle","x_sd_bat_speed"]
SPEED=["x_gb_single","x_gidp","x_triple"]
CTXP=["x_home_share","x_if_strat","x_if_shade","x_of_strat","x_fb_seen","x_brk_seen","x_pvelo","age","stand"]
FULL_NOPA = BASE+QUAL+DISC+BATTED+SPEED+CTXP+SWING
FULL_PA   = FULL_NOPA + ["x_pa"]
D = build(1, 40); tr, te = D[D.year <= 2025], D[D.year == 2026]
print(f"\n  one-month horizon, train {len(tr):,} test {len(te):,}")
print(f"  {'feature set':>34} {'ridge':>9} {'GBM':>9} {'forest':>9}")
ABL = []
for lab, cols in (("everything, no playing time", FULL_NOPA), ("everything + playing time", FULL_PA),
                  ("playing time alone", ["x_pa"])):
    cols=[c for c in cols if c in D.columns]
    imp = SimpleImputer(strategy="median").fit(tr[cols].values.astype(float))
    Xtr, Xte = imp.transform(tr[cols].values.astype(float)), imp.transform(te[cols].values.astype(float))
    wtr = tr.y_pa.values.astype(float)
    sc = StandardScaler().fit(Xtr)
    rg = RidgeCV(alphas=np.logspace(-3,4,40)).fit(sc.transform(Xtr), tr.y_woba.values, sample_weight=wtr)
    r_rid = wr2(te.y_woba.values, rg.predict(sc.transform(Xte)), te.y_pa.values)
    gb = HistGradientBoostingRegressor(max_iter=350, learning_rate=.04, max_depth=3,
        min_samples_leaf=40, l2_regularization=1., random_state=7).fit(Xtr, tr.y_woba.values, sample_weight=wtr)
    r_gbm = wr2(te.y_woba.values, gb.predict(Xte), te.y_pa.values)
    rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=12, max_features=.4,
        n_jobs=-1, random_state=7).fit(Xtr, tr.y_woba.values, sample_weight=wtr)
    r_rf = wr2(te.y_woba.values, rf.predict(Xte), te.y_pa.values)
    print(f"  {lab:>34} {r_rid:>9.4f} {r_gbm:>9.4f} {r_rf:>9.4f}")
    ABL.append(dict(set=lab, ridge=float(r_rid), gbm=float(r_gbm), forest=float(r_rf)))
R2["ablation"] = ABL

# ---------------------------------------------------------------- D+F
hr("D  A PORTABLE MODEL — ridge on standardised inputs, no playing time")
KEEP = ["x_xwoba","x_woba","x_ev","x_la","x_hardhit","x_barrel","x_k","x_bb","x_whiff",
        "x_chase","x_zswing","x_bat_speed","x_swing_len","x_attack_angle","x_tilt",
        "x_contact_depth","x_ld","x_gb","x_pull","x_sd_ev","x_gb_single","age"]
KEEP = [c for c in KEEP if c in D.columns]
imp = SimpleImputer(strategy="median").fit(tr[KEEP].values.astype(float))
Xtr = imp.transform(tr[KEEP].values.astype(float)); Xte = imp.transform(te[KEEP].values.astype(float))
sc = StandardScaler().fit(Xtr)
rg = RidgeCV(alphas=np.logspace(-3,4,60)).fit(sc.transform(Xtr), tr.y_woba.values,
                                              sample_weight=tr.y_pa.values.astype(float))
pred_te = rg.predict(sc.transform(Xte))
r2_port = wr2(te.y_woba.values, pred_te, te.y_pa.values)
p_x, _ = fit_ols(tr[["x_xwoba"]].values, tr.y_woba.values, tr.y_pa.values, te[["x_xwoba"]].values)
r2_x = wr2(te.y_woba.values, p_x, te.y_pa.values)
print(f"  {len(KEEP)} features, alpha={rg.alpha_:.3g}")
print(f"  out-of-sample R^2 2026: portable ridge {r2_port:.4f}   vs xwOBA alone {r2_x:.4f}")
print(f"\n  {'feature':>20} {'coef (per 1 sd)':>17} {'mean':>10} {'sd':>9}")
for c, co, m_, s_ in sorted(zip(KEEP, rg.coef_, sc.mean_, sc.scale_), key=lambda x: -abs(x[1])):
    print(f"  {c:>20} {co:>+17.5f} {m_:>10.4f} {s_:>9.4f}")

# reliability of the fitted metric: this window vs the next window
Dall = D.copy()
Dall["plus"] = rg.predict(sc.transform(imp.transform(D[KEEP].values.astype(float))))
nxt = Dall[["batter","year","start","plus"]].copy(); nxt["start"] -= 1
Dr = Dall.merge(nxt.rename(columns={"plus":"plus_next"}), on=["batter","year","start"], how="inner")
rel_plus = np.corrcoef(Dr.plus, Dr.plus_next)[0,1] if len(Dr) > 50 else np.nan
rel_w  = np.corrcoef(Dall.x_woba, Dall.y_woba)[0,1]
rel_x  = np.corrcoef(Dall.x_xwoba, Dall.y_xwoba)[0,1]
desc_p = np.corrcoef(Dall.plus, Dall.x_woba)[0,1]
print(f"\n  {'metric':>22} {'describes now':>15} {'repeats itself':>16} {'predicts next':>15}")
for lab, desc, rel, pr in (("wOBA", 1.0, rel_w, np.corrcoef(te.x_woba, te.y_woba)[0,1]),
                           ("xwOBA", np.corrcoef(Dall.x_xwoba, Dall.x_woba)[0,1], rel_x,
                            np.corrcoef(te.x_xwoba, te.y_woba)[0,1]),
                           ("xwOBA+ (ridge)", desc_p, rel_plus,
                            np.corrcoef(pred_te, te.y_woba)[0,1])):
    print(f"  {lab:>22} {desc:>15.3f} {rel:>16.3f} {pr:>15.3f}")
R2["portable"] = dict(features=KEEP, coef=[float(v) for v in rg.coef_],
                      mean=[float(v) for v in sc.mean_], sd=[float(v) for v in sc.scale_],
                      intercept=float(rg.intercept_), alpha=float(rg.alpha_),
                      r2=float(r2_port), r2_xwoba=float(r2_x),
                      rel_plus=float(rel_plus), rel_woba=float(rel_w), rel_xwoba=float(rel_x))

# ---------------------------------------------------------------- E
hr("E  THE GAP, controlling for the level of xwOBA")
print("""  The raw finding that a positive gap predicts a LOWER next wOBA is suspicious:
  gap and xwOBA are mechanically linked, so a hitter with a big gap is often a
  hitter with a low xwOBA. Partial the level out and see what survives.""")
for W, min_pa, lab in ((1,40,"1 month"), (3,110,"3 months")):
    Dg = build(W, min_pa); Dg["y_gap"] = Dg.y_woba - Dg.y_xwoba
    t = Dg[Dg.year <= 2025]
    X = np.c_[np.ones(len(t)), t.x_gap.values, t.x_xwoba.values]
    b, *_ = np.linalg.lstsq(X * np.sqrt(t.x_pa.values)[:,None], t.y_woba.values*np.sqrt(t.x_pa.values), rcond=None)
    res = t.y_woba.values - X@b
    se = math.sqrt(float(res@res)/(len(t)-3) * np.linalg.pinv(X.T@X)[1,1])
    print(f"  {lab:>10}: next wOBA ~ gap + xwOBA  ->  beta(gap) = {b[1]:+.4f} +/- {se:.4f}  "
          f"{'REAL' if abs(b[1])>1.96*se else 'null'}   n={len(t):,}")
    R2.setdefault("gap_ctrl", {})[lab] = dict(beta=float(b[1]), se=float(se), n=int(len(t)))

# ---------------------------------------------------------------- F
hr("F  EXPORT — real hitter-months for the interactive tool")
names = pd.read_csv(UP/"batter_names.csv").set_index("player_id")["name"].to_dict()
panel = []
Dx = build(1, 40)
for _, r in Dx[Dx.year >= 2025].iterrows():
    nm = names.get(int(r.batter))
    if not nm: continue
    rec = {"n": nm, "y": int(r.year), "m": int(r.start), "pa": int(r.x_pa),
           "next": round(float(r.y_woba), 4), "npa": int(r.y_pa)}
    for c in KEEP:
        v = r[c]
        rec[c[2:] if c.startswith("x_") else c] = None if not np.isfinite(v) else round(float(v), 4)
    panel.append(rec)
print(f"  {len(panel):,} hitter-months exported (2025-2026, 40+ PA both sides)")
R2["panel"] = panel
R2["league"] = {c: [float(np.nanmean(Dx[c])), float(np.nanstd(Dx[c]))] for c in KEEP}
Path("/home/claude/out/predict2.json").write_text(json.dumps(R2, indent=1, default=float))
print("  wrote /home/claude/out/predict2.json")
