#!/usr/bin/env python3
"""Marcel, done fairly. Four corrections to marcel.py.

  A  Tune Marcel's regression constant on training data. Using the off-the-shelf
     R=1200 against a tuned model is a strawman; the baseline gets the same
     courtesy the challenger got.
  B  Bootstrap every comparison. n=213 at season level is small enough that an
     R^2 gap of 0.08 may be nothing.
  C  Fix the ceiling. marcel.py dropped month-to-month drift from the
     denominator; predict2.py included it. They cannot both be right.
  D  The obvious next model: give the Statcast features the same weighted
     history Marcel gets. If Marcel's edge is history rather than simplicity,
     this is where it shows up.
"""
import json, math, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("/home/claude/predict.py").read().split("# ======================================================================= 1")[0])
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
OUT = {}
rng = np.random.default_rng(11)

raw2 = raw.sort_values(["batter", "game_year", "mon"]).reset_index(drop=True)
CUM = raw2.groupby(["batter", "game_year"])[SUMS].cumsum()
cum_ix = {(int(r.batter), int(r.game_year), int(r.mon)): i
          for i, r in enumerate(raw2.itertuples())}
SEA = raw2.groupby(["batter", "game_year"])[SUMS].sum()
AGE = raw2.groupby(["batter", "game_year"])["age"].max()
lgs = {int(y): float(g.woba_num.sum() / g.pa.sum()) for y, g in raw2.groupby("game_year")}


def derive(s):
    """Rates from a Series of summed counts — same derivation agg() uses."""
    d = {"pa": s.pa}
    r = lambda a, b: (s[a] / s[b]) if s[b] else np.nan
    m = lambda a, b: (s[a] / s[b]) if s[b] else np.nan
    d.update(woba=r("woba_num", "pa"), xwoba=r("xwoba_num", "pa"),
             k=r("k", "pa"), bb=r("bb", "pa"), whiff=r("whiff", "sw"),
             chase=r("ozsw", "oz"), zswing=r("izsw", "iz"),
             ev=m("sum_ev", "n_ev"), la=m("sum_la", "n_ev"),
             hardhit=r("hardhit", "n_ev"), barrel=r("barrel", "n_ev"),
             bat_speed=m("sum_bs", "n_bs"), swing_len=m("sum_sl", "n_bs"),
             attack_angle=m("sum_aa", "n_aa"), tilt=m("sum_tilt", "n_aa"),
             gb=r("gb", "n_bbt"), ld=r("ld", "n_bbt"), pull=r("pull", "n_spray"))
    return d


def hist_sums(b, y, thru, w=(5, 4, 3, 2)):
    """Marcel-weighted history: this season through month `thru`, then the three
    prior seasons. Returns summed counts, or None if the hitter has no past."""
    tot = None
    i = cum_ix.get((b, y, thru))
    if i is None:                      # fall back to latest month at or before thru
        for mm in range(thru - 1, 2, -1):
            i = cum_ix.get((b, y, mm))
            if i is not None: break
    if i is not None:
        tot = CUM.iloc[i] * w[0]
    for k, dy in zip(w[1:], (1, 2, 3)):
        key = (b, y - dy)
        if key in SEA.index:
            s = SEA.loc[key] * k
            tot = s if tot is None else tot + s
    return tot


def age_mult(a):
    return (1 + (29 - a) * 0.006) if a < 29 else (1 + (29 - a) * 0.003)


def marcel_from(tot, y, b, R, use_x=False, age=True):
    lg = lgs.get(y, 0.325)
    if tot is None or not tot.pa: return lg
    num = tot["xwoba_num" if use_x else "woba_num"]
    p = (num + R * lg) / (tot.pa + R)
    if age:
        a = AGE.get((b, y), 29)
        p *= age_mult(a)
    return p


def boot(y, preds, w, n=3000):
    """Bootstrap the weighted R^2 of each predictor, and all pairwise gaps."""
    y, w = np.asarray(y, float), np.asarray(w, float)
    keys = list(preds); P = {k: np.asarray(v, float) for k, v in preds.items()}
    N = len(y); out = {k: [] for k in keys}
    for _ in range(n):
        ix = rng.integers(0, N, N)
        yy, ww = y[ix], w[ix]
        mu = np.average(yy, weights=ww); tot = np.sum(ww * (yy - mu) ** 2)
        for k in keys:
            out[k].append(1 - np.sum(ww * (yy - P[k][ix]) ** 2) / tot)
    return {k: np.array(v) for k, v in out.items()}


# ================================================================= A  season
hr("A  SEASON LEVEL — with Marcel's regression constant tuned, and bootstrapped")
rows25, rows26 = [], []
for (b, y) in SEA.index:
    s = derive(SEA.loc[(b, y)])
    if s["pa"] < 250: continue
    tgt = rows26 if y == 2026 else (rows25 if y == 2025 else None)
    if tgt is None: continue
    prev = SEA.loc[(b, y - 1)] if (b, y - 1) in SEA.index else None
    if prev is None or prev.pa < 250: continue
    pv = derive(prev)
    tgt.append(dict(b=b, y=y, act=s["woba"], pa=s["pa"], prev_w=pv["woba"], prev_x=pv["xwoba"]))
T, S = pd.DataFrame(rows25), pd.DataFrame(rows26)
print(f"  tune on {len(T)} pairs ending 2025; test on {len(S)} pairs ending 2026")
best = None
for R in (200, 400, 600, 800, 1000, 1200, 1600, 2000, 2600):
    for ux in (False, True):
        p = [marcel_from(hist_sums(r.b, r.y, 99), r.y, r.b, R, ux) for r in T.itertuples()]
        sc = wr2(T.act, p, T.pa)
        if best is None or sc > best[0]: best = (sc, R, ux)
print(f"  tuned on training years: R = {best[1]}, "
      f"{'xwOBA' if best[2] else 'wOBA'} history  (train R^2 {best[0]:.4f})")
P = {}
P["MARCEL, classic R=1200"] = [marcel_from(hist_sums(r.b, r.y, 99), r.y, r.b, 1200) for r in S.itertuples()]
P["MARCEL, tuned"] = [marcel_from(hist_sums(r.b, r.y, 99), r.y, r.b, best[1], best[2]) for r in S.itertuples()]
for lab, col in (("last season's wOBA, shrunk", "prev_w"), ("last season's xwOBA, shrunk", "prev_x")):
    pr, _ = fit_ols(T[[col]].values, T.act.values, T.pa.values, S[[col]].values)
    P[lab] = pr
B = boot(S.act.values, P, S.pa.values)
print(f"\n  {'forecaster':>34} {'R^2':>8} {'95% interval':>20}")
for k in P:
    v = B[k]
    print(f"  {k:>34} {wr2(S.act,P[k],S.pa):>8.4f} "
          f"[{np.percentile(v,2.5):>+7.3f},{np.percentile(v,97.5):>+7.3f}]")
d = B["last season's xwOBA, shrunk"] - B["MARCEL, tuned"]
print(f"\n  shrunk xwOBA minus tuned Marcel: {d.mean():+.4f} "
      f"[{np.percentile(d,2.5):+.4f}, {np.percentile(d,97.5):+.4f}]  "
      f"P(xwOBA better) = {(d>0).mean():.2f}")
OUT["season"] = {k: dict(r2=float(wr2(S.act, P[k], S.pa)),
                         lo=float(np.percentile(B[k], 2.5)),
                         hi=float(np.percentile(B[k], 97.5))) for k in P}
OUT["season_gap"] = dict(mean=float(d.mean()), lo=float(np.percentile(d, 2.5)),
                         hi=float(np.percentile(d, 97.5)), p=float((d > 0).mean()))

# ================================================================= B  monthly
hr("B  ONE-MONTH HORIZON — tuned Marcel, history-fed models, bootstrapped")
D = build(1, 40)
HF = ["woba", "xwoba", "k", "bb", "whiff", "chase", "zswing", "ev", "la", "hardhit",
      "barrel", "bat_speed", "swing_len", "attack_angle", "tilt", "gb", "ld", "pull", "pa"]
hist_rows = []
for r in D.itertuples():
    t = hist_sums(int(r.batter), int(r.year), int(r.start))
    dd = derive(t) if t is not None else {}
    hist_rows.append({f"h_{k}": dd.get(k, np.nan) for k in HF})
D = pd.concat([D.reset_index(drop=True), pd.DataFrame(hist_rows)], axis=1)
tr, te = D[D.year <= 2025], D[D.year == 2026]
# tune R on training months
bm = None
for R in (200, 400, 600, 900, 1200, 1600, 2200):
    for ux in (False, True):
        p = [marcel_from(hist_sums(int(r.batter), int(r.year), int(r.start)), int(r.year),
                         int(r.batter), R, ux) for r in tr.itertuples()]
        sc = wr2(tr.y_woba, p, tr.y_pa)
        if bm is None or sc > bm[0]: bm = (sc, R, ux)
print(f"  tuned on 2023-2025 months: R = {bm[1]}, {'xwOBA' if bm[2] else 'wOBA'} history")
for df in (tr, te):
    df["mar"] = [marcel_from(hist_sums(int(r.batter), int(r.year), int(r.start)), int(r.year),
                             int(r.batter), bm[1], bm[2]) for r in df.itertuples()]

BASE = ["x_woba", "x_xwoba"]
QUAL = ["x_ev", "x_la", "x_hardhit", "x_barrel", "x_sweet", "x_sd_ev", "x_sd_la", "x_distance"]
DISC = ["x_k", "x_bb", "x_swing", "x_zswing", "x_chase", "x_whiff", "x_fpsw", "x_tksw"]
BATT = ["x_gb", "x_fb", "x_ld", "x_pop", "x_pull", "x_spray", "x_sd_spray", "x_bip_rate"]
SWG = ["x_bat_speed", "x_swing_len", "x_attack_angle", "x_attack_dir", "x_tilt",
       "x_contact_depth", "x_contact_x", "x_sd_attack_angle", "x_sd_bat_speed"]
CTX = ["x_pa", "x_home_share", "x_if_strat", "x_if_shade", "x_of_strat", "x_fb_seen",
       "x_brk_seen", "x_pvelo", "age", "stand"]
SPD = ["x_gb_single", "x_gidp", "x_triple"]
NOW = [c for c in BASE + QUAL + DISC + BATT + SPD + CTX + SWG if c in D.columns]
HIST = [f"h_{k}" for k in HF]


def gbm(cols):
    cols = [c for c in cols if c in D.columns]
    imp = SimpleImputer(strategy="median").fit(tr[cols].values.astype(float))
    m = HistGradientBoostingRegressor(max_iter=350, learning_rate=.04, max_depth=3,
                                      min_samples_leaf=40, l2_regularization=1., random_state=7)
    m.fit(imp.transform(tr[cols].values.astype(float)), tr.y_woba.values,
          sample_weight=tr.y_pa.values.astype(float))
    return m.predict(imp.transform(te[cols].values.astype(float)))


PM = {}
p, _ = fit_ols(tr[["x_xwoba"]].values, tr.y_woba.values, tr.y_pa.values, te[["x_xwoba"]].values)
PM["this month's xwOBA alone"] = p
PM["MARCEL, tuned"] = te["mar"].values
PM["current window, 48 features"] = gbm(NOW)
PM["weighted history, 19 features"] = gbm(HIST)
PM["history + Marcel"] = gbm(HIST + ["mar"])
PM["EVERYTHING (now + history + Marcel)"] = gbm(NOW + HIST + ["mar"])
BM = boot(te.y_woba.values, PM, te.y_pa.values)
print(f"\n  {'forecaster':>38} {'R^2':>8} {'95% interval':>20}")
for k in PM:
    v = BM[k]
    print(f"  {k:>38} {wr2(te.y_woba,PM[k],te.y_pa):>8.4f} "
          f"[{np.percentile(v,2.5):>+7.3f},{np.percentile(v,97.5):>+7.3f}]")
print("\n  head-to-head gaps, bootstrapped:")
for a, b_ in (("current window, 48 features", "MARCEL, tuned"),
              ("EVERYTHING (now + history + Marcel)", "MARCEL, tuned"),
              ("EVERYTHING (now + history + Marcel)", "current window, 48 features"),
              ("weighted history, 19 features", "MARCEL, tuned")):
    d = BM[a] - BM[b_]
    print(f"    {a:>38}\n      minus {b_:<34} {d.mean():+.4f} "
          f"[{np.percentile(d,2.5):+.4f},{np.percentile(d,97.5):+.4f}]  P(>0)={(d>0).mean():.2f}")
OUT["month"] = {k: dict(r2=float(wr2(te.y_woba, PM[k], te.y_pa)),
                        lo=float(np.percentile(BM[k], 2.5)),
                        hi=float(np.percentile(BM[k], 97.5))) for k in PM}
OUT["gaps"] = {f"{a} - {b_}": dict(mean=float((BM[a]-BM[b_]).mean()),
               lo=float(np.percentile(BM[a]-BM[b_], 2.5)),
               hi=float(np.percentile(BM[a]-BM[b_], 97.5)),
               p=float(((BM[a]-BM[b_]) > 0).mean()))
               for a, b_ in (("current window, 48 features", "MARCEL, tuned"),
                             ("EVERYTHING (now + history + Marcel)", "MARCEL, tuned"),
                             ("EVERYTHING (now + history + Marcel)", "current window, 48 features"))}

# ================================================================= C  ceiling
hr("C  THE CEILING, RECONCILED")
sig2 = 0.2258; vdiff = 0.0381 ** 2
vb = float(np.var(raw2[raw2.pa >= 60].groupby("batter").apply(
    lambda g: np.average(g.woba_num / g.pa, weights=g.pa)), ddof=1))
vmonth = vdiff / 2          # var of one month's true deviation from season baseline
mpa = float(np.average(te.y_pa))
den = vb + vmonth + sig2 / mpa
c_stable, c_oracle = vb / den, (vb + vmonth) / den
print(f"""  Two different numbers were reported for this and they used different
  denominators. Reconciled:

    var(true baseline talent)            {vb:.6f}   sd {math.sqrt(vb):.4f}
    var(one month's drift off baseline)  {vmonth:.6f}   sd {math.sqrt(vmonth):.4f}
    var(sampling noise) at {mpa:.0f} PA         {sig2/mpa:.6f}   sd {math.sqrt(sig2/mpa):.4f}

  A forecaster who knew every hitter's stable talent exactly, but could not see
  which month he would run hot, tops out at R^2 = {c_stable:.3f}. One that could
  also see the drift — an upper bound no forecaster reaches — tops out at
  {c_oracle:.3f}. The realistic ceiling is the first.""")
print(f"\n  {'forecaster':>38} {'R^2':>8} {'% of realistic ceiling':>24}")
for k in PM:
    print(f"  {k:>38} {OUT['month'][k]['r2']:>8.4f} "
          f"{100*OUT['month'][k]['r2']/c_stable:>23.0f}%")
OUT["ceiling"] = dict(stable=float(c_stable), oracle=float(c_oracle), mean_pa=mpa,
                      vb=float(vb), vmonth=float(vmonth), vnoise=float(sig2/mpa))

# ================================================================= D  sort
hr("D  THE SORTING TEST, FINAL")
te = te.copy()
for k, v in PM.items(): te[k] = v
print(f"  {'sorted by':>38} {'bottom fifth':>13} {'top fifth':>11} {'spread':>9}")
SORT = {}
for lab, col in [("what he just hit (wOBA)", "x_woba"), ("xwOBA", "x_xwoba")] + \
                [(k, k) for k in PM]:
    s = te.sort_values(col); n = len(s)
    lo, hi = s.iloc[:n // 5], s.iloc[-(n // 5):]
    a = float(np.average(lo.y_woba, weights=lo.y_pa)); b2 = float(np.average(hi.y_woba, weights=hi.y_pa))
    print(f"  {lab:>38} {a:>13.4f} {b2:>11.4f} {b2-a:>+9.4f}")
    SORT[lab] = dict(lo=a, hi=b2, spread=b2 - a)
OUT["sort"] = SORT
Path("/home/claude/out/marcel2.json").write_text(json.dumps(OUT, indent=1, default=float))
print("\nwrote /home/claude/out/marcel2.json")
