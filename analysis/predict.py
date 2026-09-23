#!/usr/bin/env python3
"""Does xwOBA predict next period's wOBA better than wOBA does, and can we beat it?

Six parts:
  1  the noise floor: how much of next period's wOBA is even predictable
  2  the horse race: wOBA vs xwOBA vs both, at four window lengths
  3  the blend: how much weight xwOBA deserves, as a function of sample size
  4  the model zoo: can a richer feature set beat xwOBA out of sample
  5  the gap: what explains wOBA minus xwOBA, short stretches and long
  6  the trichotomy: descriptive vs reliable vs predictive, for every candidate

Temporal holdout throughout. Nothing is fit on 2026.
"""
import json, math, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
UP = Path("/mnt/user-data/uploads/Projects--statcast-dashboard/output")
OUT = Path("/home/claude/out"); OUT.mkdir(exist_ok=True, parents=True)
RES = {}
rng = np.random.default_rng(7)

raw = pd.read_csv(UP / "hitter_months.csv")
names = pd.read_csv(UP / "batter_names.csv").set_index("player_id")["name"].to_dict()
raw["mon"] = raw["ym"].str[5:7].astype(int)
raw = raw.sort_values(["batter", "game_year", "mon"]).reset_index(drop=True)

SUMS = [c for c in raw.columns if c not in ("batter", "game_year", "ym", "mon", "stand", "age")]


def hr(t):
    print("\n" + "=" * 78); print(t); print("=" * 78)


def agg(block):
    """Sum a set of month rows into one window, then derive rates."""
    s = block[SUMS].sum()
    d = {"pa": s.pa, "n_months": len(block)}
    def r(a, b, k=1.0):
        return (s[a] / s[b] * k) if s[b] else np.nan
    def m(sm, n):
        return (s[sm] / s[n]) if s[n] else np.nan
    def sd(sm, ss, n):
        if not s[n]: return np.nan
        mu = s[sm] / s[n]
        return math.sqrt(max(s[ss] / s[n] - mu * mu, 0))
    d["woba"]   = r("woba_num", "pa")
    d["xwoba"]  = r("xwoba_num", "pa")
    d["xslg"]   = r("xslg_num", "pa")
    d["k"]      = r("k", "pa");        d["bb"] = r("bb", "pa")
    d["swing"]  = r("sw", "pitches");  d["zswing"] = r("izsw", "iz")
    d["chase"]  = r("ozsw", "oz");     d["whiff"]  = r("whiff", "sw")
    d["fpsw"]   = r("fpsw", "fp");     d["tksw"]   = r("tksw", "tk")
    d["bat_speed"]  = m("sum_bs", "n_bs");  d["swing_len"] = m("sum_sl", "n_bs")
    d["sd_bat_speed"] = sd("sum_bs", "ss_bs", "n_bs")
    d["attack_angle"] = m("sum_aa", "n_aa"); d["sd_attack_angle"] = sd("sum_aa", "ss_aa", "n_aa")
    d["attack_dir"]   = m("sum_ad", "n_aa"); d["sd_attack_dir"]   = sd("sum_ad", "ss_ad", "n_aa")
    d["tilt"] = m("sum_tilt", "n_aa")
    d["contact_depth"] = m("sum_icy", "n_ic"); d["contact_x"] = m("sum_icx", "n_ic")
    d["ev"]  = m("sum_ev", "n_ev");  d["sd_ev"] = sd("sum_ev", "ss_ev", "n_ev")
    d["la"]  = m("sum_la", "n_ev");  d["sd_la"] = sd("sum_la", "ss_la", "n_ev")
    d["hardhit"] = r("hardhit", "n_ev"); d["barrel"] = r("barrel", "n_ev")
    d["sweet"]   = r("sweet", "n_ev")
    d["gb"] = r("gb", "n_bbt"); d["fb"] = r("fbb", "n_bbt")
    d["ld"] = r("ld", "n_bbt"); d["pop"] = r("pop", "n_bbt")
    d["spray"] = m("sum_spray", "n_spray"); d["sd_spray"] = sd("sum_spray", "ss_spray", "n_spray")
    d["pull"] = r("pull", "n_spray"); d["distance"] = m("sum_dist", "n_dist")
    d["bip_rate"] = r("bip", "pa")
    d["gb_single"] = r("inf_single", "gb"); d["gidp"] = r("gidp", "gb")
    d["triple"] = r("triple", "n_bbt")
    d["home_share"] = r("home_pa", "pa")
    d["if_strat"] = r("if_strat", "bip"); d["if_shade"] = r("if_shade", "bip")
    d["of_strat"] = r("of_strat", "bip")
    d["fb_seen"] = r("fb_seen", "pt_seen"); d["brk_seen"] = r("brk_seen", "pt_seen")
    d["pvelo"] = m("sum_pvelo", "n_pvelo")
    d["gap"] = d["woba"] - d["xwoba"]
    return d


def build(W, min_pa):
    """Contiguous windows of W calendar months, paired with the next W months
    in the same season. Never spans an offseason."""
    rows = []
    for (b, y), g in raw.groupby(["batter", "game_year"]):
        g = g.sort_values("mon")
        mons = g["mon"].tolist()
        for i in range(len(mons) - 2 * W + 1):
            xw = mons[i:i + W]; yw = mons[i + W:i + 2 * W]
            if xw != list(range(xw[0], xw[0] + W)): continue
            if yw != list(range(yw[0], yw[0] + W)): continue
            X = agg(g[g.mon.isin(xw)]); Y = agg(g[g.mon.isin(yw)])
            if X["pa"] < min_pa or Y["pa"] < min_pa: continue
            rec = {f"x_{k}": v for k, v in X.items()}
            rec.update(batter=b, year=y, start=xw[0], age=g["age"].max(),
                       stand=1.0 if g["stand"].iloc[0] == "R" else 0.0,
                       y_woba=Y["woba"], y_xwoba=Y["xwoba"], y_pa=Y["pa"])
            rows.append(rec)
    return pd.DataFrame(rows)


def wr2(y, p, w):
    """Weighted out-of-sample R^2 against the weighted mean of the TEST set."""
    y, p, w = np.asarray(y, float), np.asarray(p, float), np.asarray(w, float)
    ok = np.isfinite(y) & np.isfinite(p) & np.isfinite(w)
    y, p, w = y[ok], p[ok], w[ok]
    mu = np.average(y, weights=w)
    ss_res = np.sum(w * (y - p) ** 2); ss_tot = np.sum(w * (y - mu) ** 2)
    return 1 - ss_res / ss_tot


def wrmse(y, p, w):
    y, p, w = np.asarray(y, float), np.asarray(p, float), np.asarray(w, float)
    ok = np.isfinite(y) & np.isfinite(p) & np.isfinite(w)
    return math.sqrt(np.average((y[ok] - p[ok]) ** 2, weights=w[ok]))


def fit_ols(Xtr, ytr, wtr, Xte):
    A = np.c_[np.ones(len(Xtr)), Xtr]; B = np.c_[np.ones(len(Xte)), Xte]
    s = np.sqrt(wtr)
    b, *_ = np.linalg.lstsq(A * s[:, None], ytr * s, rcond=None)
    return B @ b, b


# ======================================================================= 1
hr("1  THE NOISE FLOOR — how much of next month's wOBA is knowable at all")
print("""  Any forecast is graded against a target that is itself mostly noise at one
  month of playing time. Before comparing predictors, establish the ceiling.

  For two months of the same hitter in the same season:
      E[(w1 - w2)^2] = sigma^2 * (1/pa1 + 1/pa2) + var(true drift)
  Regressing squared differences on (1/pa1 + 1/pa2) identifies both: the slope
  is the per-plate-appearance outcome variance, the intercept is real
  month-to-month movement in skill.""")
pairs = []
for (b, y), g in raw.groupby(["batter", "game_year"]):
    g = g[g.pa >= 30]
    v = g[["pa", "woba_num"]].values
    for i in range(len(v)):
        for j in range(i + 1, len(v)):
            p1, n1 = v[i]; p2, n2 = v[j]
            pairs.append(((n1 / p1 - n2 / p2) ** 2, 1 / p1 + 1 / p2))
P = np.array(pairs)
A = np.c_[np.ones(len(P)), P[:, 1]]
coef, *_ = np.linalg.lstsq(A, P[:, 0], rcond=None)
var_drift, sigma2 = coef[0], coef[1]
print(f"\n  n = {len(P):,} within-season month pairs")
print(f"  per-PA outcome variance sigma^2 = {sigma2:.4f}  (sigma = {math.sqrt(sigma2):.4f} of wOBA per PA)")
print(f"  variance of real month-to-month drift = {max(var_drift,0):.6f} "
      f"(sd = {math.sqrt(max(var_drift,0)):.4f})")
print(f"\n  {'PA in a month':>15} {'noise sd':>10} {'ceiling R^2':>13}")
for n in (40, 60, 80, 100, 150, 250, 600):
    noise = sigma2 / n
    # signal available to a forecaster = between-hitter true variance + drift already realised
    print(f"  {n:>15} {math.sqrt(noise):>10.4f} {0.0:>13}", end="")
    print("")
BET = raw[raw.pa >= 60]
btrue = BET.groupby("batter").apply(lambda g: np.average(g.woba_num / g.pa, weights=g.pa))
var_between_obs = np.var(btrue, ddof=1)
print(f"\n  spread of hitter career wOBA (60+ PA months, {len(btrue)} hitters): "
      f"{math.sqrt(var_between_obs):.4f}")
for n in (40, 60, 80, 100, 150, 250, 600):
    ceil = var_between_obs / (var_between_obs + sigma2 / n)
    print(f"  at {n:>3} PA a perfect forecaster reaches R^2 = {ceil:.3f} "
          f"against that month's observed wOBA")
RES["floor"] = dict(sigma2=float(sigma2), var_drift=float(max(var_drift, 0)),
                    var_between=float(var_between_obs))

# ======================================================================= 2
hr("2  THE HORSE RACE — wOBA vs xwOBA as a predictor of the next window")
print("""  Fit on 2023-2025, evaluate once on 2026. Weighted by the target window's
  plate appearances, so a 40-PA month does not count as much as a 120-PA one.
  R^2 is measured against the test set's own weighted mean, so 0.00 means
  'no better than assuming everyone is league average'.""")
TABLE = []
for W, min_pa in ((1, 40), (2, 80), (3, 110)):
    D = build(W, min_pa)
    tr, te = D[D.year <= 2025], D[D.year == 2026]
    if len(te) < 60: continue
    print(f"\n  --- window = {W} month{'s' if W>1 else ''}, min {min_pa} PA each side"
          f"   train {len(tr):,}   test {len(te):,}")
    print(f"  {'predictor':>34} {'test R^2':>10} {'RMSE':>9} {'corr':>8}")
    for label, cols in (("this window's wOBA", ["x_woba"]),
                        ("this window's xwOBA", ["x_xwoba"]),
                        ("both", ["x_woba", "x_xwoba"]),
                        ("both + PA", ["x_woba", "x_xwoba", "x_pa"]),
                        ("xwOBA + K% + BB%", ["x_xwoba", "x_k", "x_bb"])):
        Xtr = tr[cols].values; Xte = te[cols].values
        ok_tr = np.isfinite(Xtr).all(1) & np.isfinite(tr.y_woba.values)
        ok_te = np.isfinite(Xte).all(1) & np.isfinite(te.y_woba.values)
        p, b = fit_ols(Xtr[ok_tr], tr.y_woba.values[ok_tr], tr.y_pa.values[ok_tr], Xte[ok_te])
        r2 = wr2(te.y_woba.values[ok_te], p, te.y_pa.values[ok_te])
        rm = wrmse(te.y_woba.values[ok_te], p, te.y_pa.values[ok_te])
        cr = np.corrcoef(te.y_woba.values[ok_te], p)[0, 1]
        print(f"  {label:>34} {r2:>10.4f} {rm:>9.4f} {cr:>8.3f}")
        TABLE.append(dict(W=W, predictor=label, r2=float(r2), rmse=float(rm), corr=float(cr)))
RES["race"] = TABLE

# season-to-season
hr("2b  THE LONG STRETCH — full season predicting the next full season")
seas = []
for (b, y), g in raw.groupby(["batter", "game_year"]):
    a = agg(g)
    if a["pa"] >= 250: seas.append(dict(batter=b, year=y, **{f"x_{k}": v for k, v in a.items()}))
S = pd.DataFrame(seas)
nxt = S.copy(); nxt["year"] = nxt["year"] - 1
J = S.merge(nxt[["batter", "year", "x_woba", "x_xwoba", "x_pa"]].rename(
    columns={"x_woba": "y_woba", "x_xwoba": "y_xwoba", "x_pa": "y_pa"}), on=["batter", "year"])
tr, te = J[J.year <= 2024], J[J.year == 2025]
print(f"  train {len(tr)} season pairs (2023->24, 2024->25), test {len(te)} (2025->26)")
print(f"  {'predictor':>34} {'test R^2':>10} {'RMSE':>9}")
for label, cols in (("this season's wOBA", ["x_woba"]),
                    ("this season's xwOBA", ["x_xwoba"]),
                    ("both", ["x_woba", "x_xwoba"])):
    Xtr, Xte = tr[cols].values, te[cols].values
    p, b = fit_ols(Xtr, tr.y_woba.values, tr.y_pa.values, Xte)
    print(f"  {label:>34} {wr2(te.y_woba.values,p,te.y_pa.values):>10.4f} "
          f"{wrmse(te.y_woba.values,p,te.y_pa.values):>9.4f}")

# ======================================================================= 3
hr("3  THE BLEND — how much weight xwOBA deserves, by sample size")
print("""  Fit  next_wOBA ~ a + b1*wOBA + b2*xwOBA  separately within buckets of input
  plate appearances, on training years only. The share b2/(b1+b2) is how much of
  the believable signal is coming from xwOBA rather than from what actually
  happened. Prediction on record: the share falls as sample grows, because wOBA's
  own noise shrinks while xwOBA's advantage is precisely that it has less.""")
D1 = build(1, 30)
tr1 = D1[D1.year <= 2025]
print(f"\n  {'input PA':>14} {'n':>6} {'b(wOBA)':>10} {'b(xwOBA)':>10} {'xwOBA share':>13}")
BL = []
edges = [(30, 55), (55, 70), (70, 85), (85, 100), (100, 130), (130, 400)]
for lo, hi in edges:
    s = tr1[(tr1.x_pa >= lo) & (tr1.x_pa < hi)]
    if len(s) < 120: continue
    X = s[["x_woba", "x_xwoba"]].values
    p, b = fit_ols(X, s.y_woba.values, s.y_pa.values, X)
    tot = b[1] + b[2]
    share = b[2] / tot if abs(tot) > 1e-9 else np.nan
    print(f"  {f'{lo}-{hi}':>14} {len(s):>6} {b[1]:>10.3f} {b[2]:>10.3f} {share:>13.2f}")
    BL.append(dict(lo=lo, hi=hi, n=len(s), b_woba=float(b[1]), b_xwoba=float(b[2]),
                   share=float(share)))
RES["blend"] = BL

# ======================================================================= 4
hr("4  THE MODEL ZOO — can a richer feature set beat xwOBA out of sample")
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

BASE   = ["x_woba", "x_xwoba"]
QUAL   = ["x_ev", "x_la", "x_hardhit", "x_barrel", "x_sweet", "x_sd_ev", "x_sd_la", "x_distance"]
DISC   = ["x_k", "x_bb", "x_swing", "x_zswing", "x_chase", "x_whiff", "x_fpsw", "x_tksw"]
BATTED = ["x_gb", "x_fb", "x_ld", "x_pop", "x_pull", "x_spray", "x_sd_spray", "x_bip_rate"]
SWING  = ["x_bat_speed", "x_swing_len", "x_attack_angle", "x_attack_dir", "x_tilt",
          "x_contact_depth", "x_contact_x", "x_sd_attack_angle", "x_sd_bat_speed"]
CTX    = ["x_pa", "x_home_share", "x_if_strat", "x_if_shade", "x_of_strat",
          "x_fb_seen", "x_brk_seen", "x_pvelo", "age", "stand"]
SPEED  = ["x_gb_single", "x_gidp", "x_triple"]

SETS = [("wOBA only", BASE[:1]), ("xwOBA only", BASE[1:]), ("wOBA + xwOBA", BASE),
        ("+ contact quality", BASE + QUAL), ("+ discipline", BASE + QUAL + DISC),
        ("+ batted-ball mix", BASE + QUAL + DISC + BATTED),
        ("+ speed proxies", BASE + QUAL + DISC + BATTED + SPEED),
        ("+ context", BASE + QUAL + DISC + BATTED + SPEED + CTX),
        ("+ swing geometry (ALL)", BASE + QUAL + DISC + BATTED + SPEED + CTX + SWING)]

for W, min_pa, y0 in ((1, 40, 2023), (2, 80, 2023)):
    D = build(W, min_pa)
    D = D[D.year >= y0]
    tr, te = D[D.year <= 2025], D[D.year == 2026]
    if len(te) < 60: continue
    print(f"\n  --- window = {W} month{'s' if W>1 else ''}   train {len(tr):,}  test {len(te):,}")
    print(f"  {'feature set':>26} {'k':>4} {'ridge':>9} {'GBM':>9} {'forest':>9}")
    for label, cols in SETS:
        cols = [c for c in cols if c in D.columns]
        Xtr_r, Xte_r = tr[cols].values.astype(float), te[cols].values.astype(float)
        imp = SimpleImputer(strategy="median").fit(Xtr_r)
        Xtr, Xte = imp.transform(Xtr_r), imp.transform(Xte_r)
        ytr, yte = tr.y_woba.values, te.y_woba.values
        wtr, wte = tr.y_pa.values.astype(float), te.y_pa.values.astype(float)
        sc = StandardScaler().fit(Xtr)
        rg = RidgeCV(alphas=np.logspace(-3, 4, 40)).fit(sc.transform(Xtr), ytr, sample_weight=wtr)
        r_rid = wr2(yte, rg.predict(sc.transform(Xte)), wte)
        gb = HistGradientBoostingRegressor(max_iter=350, learning_rate=0.04, max_depth=3,
                                           min_samples_leaf=40, l2_regularization=1.0,
                                           random_state=7).fit(Xtr, ytr, sample_weight=wtr)
        r_gbm = wr2(yte, gb.predict(Xte), wte)
        rf = RandomForestRegressor(n_estimators=300, min_samples_leaf=12, max_features=0.4,
                                   n_jobs=-1, random_state=7).fit(Xtr, ytr, sample_weight=wtr)
        r_rf = wr2(yte, rf.predict(Xte), wte)
        print(f"  {label:>26} {len(cols):>4} {r_rid:>9.4f} {r_gbm:>9.4f} {r_rf:>9.4f}")
        RES.setdefault("zoo", []).append(dict(W=W, features=label, k=len(cols),
                                              ridge=float(r_rid), gbm=float(r_gbm),
                                              forest=float(r_rf)))

# ======================================================================= 5
hr("5  THE GAP — what explains wOBA minus xwOBA, and does it firm up over time")
print("""  Two questions. First: is the gap a repeatable property of a hitter, or is it
  luck that resets? Second: what is it made of, and does the explainable share
  grow as the window lengthens? If the gap is mostly luck, a longer window should
  average it away and leave a SMALLER but more explainable residue.""")

# 5a reliability of the gap
print("\n  5a  Is the gap a skill? Split-half within season, odd months vs even months.")
rowsA, rowsB = [], []
for (b, y), g in raw.groupby(["batter", "game_year"]):
    o, e = g[g.mon % 2 == 1], g[g.mon % 2 == 0]
    if len(o) == 0 or len(e) == 0: continue
    A_, B_ = agg(o), agg(e)
    if A_["pa"] < 100 or B_["pa"] < 100: continue
    rowsA.append(A_); rowsB.append(B_)
A_ = pd.DataFrame(rowsA); B_ = pd.DataFrame(rowsB)
print(f"  n = {len(A_)} hitter-seasons with 100+ PA in both halves")
print(f"  {'metric':>16} {'split-half r':>13} {'Spearman-Brown':>16}")
for k in ("woba", "xwoba", "gap", "ev", "bat_speed", "pull", "gb_single"):
    ok = np.isfinite(A_[k]) & np.isfinite(B_[k])
    r = np.corrcoef(A_[k][ok], B_[k][ok])[0, 1]
    print(f"  {k:>16} {r:>13.3f} {2*r/(1+r):>16.3f}")
    RES.setdefault("gap_rel", {})[k] = dict(r=float(r), sb=float(2 * r / (1 + r)))

# 5b what explains it, by window length
print("\n  5b  What the gap is made of. OLS, weighted by PA, train years only,")
print("      standardised coefficients so they compare across variables.")
GAPX = ["x_spray", "x_pull", "x_gb", "x_ld", "x_fb", "x_pop", "x_la", "x_ev", "x_sd_spray",
        "x_gb_single", "x_gidp", "x_triple", "x_home_share", "x_if_strat", "x_if_shade",
        "x_distance", "age"]
for W, min_pa, lab in ((1, 40, "1 month"), (3, 110, "3 months")):
    D = build(W, min_pa); tr = D[D.year <= 2025]
    y = (tr.x_woba - tr.x_xwoba).values
    X = tr[GAPX].values.astype(float)
    ok = np.isfinite(X).all(1) & np.isfinite(y)
    X, y, w = X[ok], y[ok], tr.x_pa.values[ok].astype(float)
    mu, sg = X.mean(0), X.std(0); Z = (X - mu) / np.where(sg == 0, 1, sg)
    A = np.c_[np.ones(len(Z)), Z]; s = np.sqrt(w)
    b, *_ = np.linalg.lstsq(A * s[:, None], y * s, rcond=None)
    pred = A @ b
    r2 = 1 - np.sum(w * (y - pred) ** 2) / np.sum(w * (y - np.average(y, weights=w)) ** 2)
    print(f"\n  window {lab}:  n={len(y):,}  sd(gap)={y.std():.4f}  in-sample R^2={r2:.4f}")
    order = np.argsort(-np.abs(b[1:]))
    for i in order[:8]:
        print(f"      {GAPX[i]:>16} {b[i+1]:>+9.5f}  (per 1 sd of the predictor)")
    RES.setdefault("gap_model", {})[lab] = dict(n=int(len(y)), sd=float(y.std()), r2=float(r2),
        coefs={GAPX[i]: float(b[i + 1]) for i in order[:8]})

# 5c does the gap predict anything about the future
print("\n  5c  Does this window's gap predict next window's gap, or next window's wOBA?")
for W, min_pa, lab in ((1, 40, "1 month"), (3, 110, "3 months")):
    D = build(W, min_pa)
    D["y_gap"] = D.y_woba - D.y_xwoba
    tr = D[D.year <= 2025]
    ok = np.isfinite(tr.x_gap) & np.isfinite(tr.y_gap)
    rg = np.corrcoef(tr.x_gap[ok], tr.y_gap[ok])[0, 1]
    rw = np.corrcoef(tr.x_gap[ok], tr.y_woba[ok])[0, 1]
    print(f"  {lab:>10}: corr(gap, NEXT gap) = {rg:+.3f}   corr(gap, NEXT wOBA) = {rw:+.3f}   n={ok.sum():,}")
    RES.setdefault("gap_persist", {})[lab] = dict(next_gap=float(rg), next_woba=float(rw))

# ======================================================================= 6
hr("6  DESCRIPTIVE vs RELIABLE vs PREDICTIVE — the three things a metric can be")
print("""  A metric can describe what happened, repeat with itself, or forecast what
  comes next, and these are different properties that trade off. wOBA is the
  perfect describer by construction and a poor forecaster. The question is where
  a fitted metric lands.""")
D = build(1, 40)
tr, te = D[D.year <= 2025], D[D.year == 2026]
FULL = [c for c in BASE + QUAL + DISC + BATTED + SPEED + CTX + SWING if c in D.columns]
imp = SimpleImputer(strategy="median").fit(tr[FULL].values.astype(float))
Xtr, Xte = imp.transform(tr[FULL].values.astype(float)), imp.transform(te[FULL].values.astype(float))
gbm = HistGradientBoostingRegressor(max_iter=350, learning_rate=0.04, max_depth=3,
                                    min_samples_leaf=40, l2_regularization=1.0,
                                    random_state=7).fit(Xtr, tr.y_woba.values,
                                                        sample_weight=tr.y_pa.values.astype(float))
D_all = D.copy()
D_all["xwoba_plus"] = gbm.predict(imp.transform(D[FULL].values.astype(float)))
te2 = D_all[D_all.year == 2026]
print(f"\n  {'metric':>22} {'describes now':>15} {'predicts next':>15} {'reliability':>13}")
# reliability: correlation of the metric with itself in the adjacent window
for label, col in (("wOBA", "x_woba"), ("xwOBA", "x_xwoba"), ("xwOBA+ (fitted)", "xwoba_plus")):
    v = D_all[col].values
    desc = np.corrcoef(v[np.isfinite(v)], D_all.x_woba.values[np.isfinite(v)])[0, 1]
    pr = wr2(te2.y_woba.values, te2[col].values if col != "xwoba_plus" else te2[col].values,
             te2.y_pa.values) if col == "xwoba_plus" else np.nan
    prc = np.corrcoef(te2[col].values, te2.y_woba.values)[0, 1]
    # self-consistency: this window vs next window of the same metric
    nxtcol = {"x_woba": "y_woba", "x_xwoba": "y_xwoba"}.get(col)
    if nxtcol:
        rel = np.corrcoef(D_all[col], D_all[nxtcol])[0, 1]
    else:
        rel = np.nan
    print(f"  {label:>22} {desc:>15.3f} {prc:>15.3f} "
          f"{(f'{rel:.3f}' if np.isfinite(rel) else 'n/a'):>13}")
r2_plus = wr2(te2.y_woba.values, te2.xwoba_plus.values, te2.y_pa.values)
p_x, _ = fit_ols(tr[["x_xwoba"]].values, tr.y_woba.values, tr.y_pa.values, te[["x_xwoba"]].values)
r2_x = wr2(te.y_woba.values, p_x, te.y_pa.values)
print(f"\n  out-of-sample R^2 on 2026, one-month horizon:")
print(f"      xwOBA alone      {r2_x:.4f}")
print(f"      xwOBA+ (fitted)  {r2_plus:.4f}   "
      f"{'BEATS IT' if r2_plus>r2_x else 'does NOT beat it'} "
      f"({100*(r2_plus-r2_x)/abs(r2_x) if r2_x else 0:+.0f}% relative)")
RES["trichotomy"] = dict(r2_xwoba=float(r2_x), r2_plus=float(r2_plus))

imps = None
try:
    from sklearn.inspection import permutation_importance
    pi = permutation_importance(gbm, Xte, te.y_woba.values, n_repeats=8, random_state=7,
                                sample_weight=te.y_pa.values.astype(float))
    imps = sorted(zip(FULL, pi.importances_mean), key=lambda x: -x[1])[:14]
    print("\n  what the fitted model actually uses (permutation importance, test set):")
    for k, v in imps:
        print(f"      {k:>22} {v:>9.5f}")
    RES["importance"] = [[k, float(v)] for k, v in imps]
except Exception as e:
    print("  (importance failed:", e, ")")

Path(OUT / "predict.json").write_text(json.dumps(RES, indent=1, default=float))
print(f"\nwrote {OUT/'predict.json'}")
