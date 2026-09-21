#!/usr/bin/env python3
"""Head-to-head forecasting: P(A outperforms B over the next N days), and a
backtest that scores the estimator against the alternatives.

    python3 matchup.py                  # hitters, writes web/data/matchup.json
    python3 matchup.py --kind pit
    python3 matchup.py --window 2       # horizon in half-month blocks (default 2 = ~30d)

Why a probability and not a projected line
------------------------------------------
FINDINGS 2026-09-12 settled what a one-month point forecast is worth here: Marcel
scores R2 0.058, the 48-feature model 0.057, and every head-to-head gap straddles
zero. Against a realistic ceiling of 0.264 that is 22% of what is knowable. A site
that printed "we project .341" would be contradicting its own evidence.

Ordering a *pair* is a strictly easier question than estimating a level, because
only the sign of the gap has to beat the noise. So this asks the easy question and
reports the honest answer to it -- which, most of the time, is "closer to a coin
flip than you think".

The estimator
-------------
Talent is estimated the way D42 estimates a usual level, then updated with what has
happened this season. Two normal pieces, combined by precision:

    prior       N(mu_0, tau_n^2)   prior seasons, weighted 1/.8/.6 and regressed
                                   toward that season's league mean by k = s2/tau^2
    likelihood  N(w_season, s2/n)  this season's wOBA over n PA

    post_var  = 1 / (1/tau_n^2 + n/s2)
    post_mean = post_var * (mu_0/tau_n^2 + w_season*n/s2)

The difference between two players over the next N plate appearances then carries
three independent variances, and the split between them is the point of the view:

    talent    post_var_A + post_var_B        we do not know what they are
    drift     2 * drift_sd^2 * months        what they are will change
    sampling  s2/pa_A + s2/pa_B              luck over the window

    P(A outperforms B) = Phi( (post_mean_A - post_mean_B) / sqrt(total) )

For pitchers the sign flips: lower wOBA allowed is better.

What the backtest does
----------------------
Walks every block boundary in every season, builds each estimate from strictly
prior data only, pairs players off, and scores the resulting probabilities against
what actually happened in the following window. That is the prediction ledger from
PRODUCT.md #1, run over history instead of waiting a month per data point -- and it
scores four forecasters on identical pairs, so the comparison is paired.

Read the caveats printed at the end before quoting any of it. The honest headline
is expected to be "well calibrated, low resolution": the estimator should say 58%
a lot, and be right about 58% of the time.
"""
import argparse, json, math, pathlib, random, sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "web" / "data"

# Field order differs by player type -- hitters lead with 'pa', pitchers with
# 'bf', 'outs' -- so indices are always looked up by name from the shard itself.
# Hardcoding 0/1/2 silently read 'outs' as the wOBA numerator for pitchers and
# produced a forecaster that was pinned at a 50% hit rate in every bucket.
PA_KEY = {"bat": "pa", "pit": "bf"}
Z80 = 0.8416                  # z for 80% power
Z95 = 1.9600                  # z for a two-sided 95% test

# Month-to-month drift of true talent, sd of wOBA. Measured in FINDINGS
# 2026-09-12 from 16,228 within-season month pairs, alongside s2 itself.
DRIFT_SD_PER_MONTH = 0.0381


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# --------------------------------------------------------------------------- data
def load(kind):
    hist = json.loads((DATA / "history.json").read_text())
    shards = {}
    for p in sorted(DATA.glob(f"{kind}-*.json")):
        year = int(p.stem.split("-")[1])
        shards[year] = json.loads(p.read_text())
    if not shards:
        sys.exit(f"no {kind}-*.json shards in {DATA}; run blocks_all.py first")
    return hist, shards


def field_index(shard, kind):
    """(pa, wn, xn) column positions for this shard, by name."""
    f = shard["fields"]
    return f.index(PA_KEY[kind]), f.index("wn"), f.index("xn")


def totals(row, blocks, idx):
    """Sum a player's raw counters over a list of block labels."""
    ipa, iwn, ixn = idx
    pa = wn = xn = 0.0
    for b in blocks:
        v = row["b"].get(b)
        if not v:
            continue
        pa += v[ipa]; wn += v[iwn]; xn += v[ixn]
    return pa, wn, xn


# ------------------------------------------------------------------- naive priors from official lines
# Three more naive rankings for the scoring record, from fetch_careers.py's official season lines:
# last season, career to date, and Marcel. They need seasons before 2023 (the pitch archive's
# start), which is why they come from the Stats API rather than from history.json. wOBA is rebuilt
# from counting stats with one fixed set of linear weights (FanGraphs 2023) -- close enough to rank
# a pair, which is all a slice baseline uses it for.
W_LIN = {"ubb": 0.696, "hbp": 0.726, "1b": 0.883, "2b": 1.244, "3b": 1.569, "hr": 2.004}
MARCEL_W = (5, 4, 3)
MARCEL_K = 3000          # PA of league average; the tuned constant from marcel3.py (FINDINGS 2026-09-12)
_CAREERS = {}


def _careers(kind):
    if kind not in _CAREERS:
        p = DATA / f"careers-{kind}.json"
        _CAREERS[kind] = None
        if p.exists():
            d = json.loads(p.read_text())
            f = {k: i for i, k in enumerate(d["fields"])}
            per, lg = {}, defaultdict(lambda: [0.0, 0.0])
            for pid, rec in d["players"].items():
                seasons = {}
                for row in rec["s"]:
                    g = lambda k: float(row[f[k]] or 0)
                    ibb, bb, hbp = g("intentionalWalks"), g("baseOnBalls"), g("hitByPitch")
                    h, d2, d3, hr = g("hits"), g("doubles"), g("triples"), g("homeRuns")
                    den = (g("atBats") + bb - ibb + g("sacFlies") + hbp) if kind == "bat" else \
                          (g("battersFaced") - ibb)
                    num = (W_LIN["ubb"] * (bb - ibb) + W_LIN["hbp"] * hbp +
                           W_LIN["1b"] * (h - d2 - d3 - hr) + W_LIN["2b"] * d2 +
                           W_LIN["3b"] * d3 + W_LIN["hr"] * hr)
                    if den > 0:
                        seasons[row[0]] = (den, num)
                        lg[row[0]][0] += den; lg[row[0]][1] += num
                born = rec.get("born") or ""
                per[int(pid)] = {"s": seasons, "born": int(born[:4]) if born[:4].isdigit() else None,
                                 "late": born[5:7] > "06" if len(born) >= 7 else False}
            _CAREERS[kind] = {"p": per, "lg": {y: n / d for y, (d, n) in lg.items() if d}}
    return _CAREERS[kind]


def naive_levels(kind, pid, year):
    """(last season, career before this season, Marcel) in wOBA; league average where he has none."""
    C = _careers(kind)
    if C is None:
        return None
    lgp = C["lg"].get(year - 1) or sum(C["lg"].values()) / len(C["lg"])
    p = C["p"].get(int(pid), {"s": {}, "born": None, "late": False})
    s = p["s"]
    last = (s[year - 1][1] / s[year - 1][0]) if year - 1 in s else lgp
    den = sum(v[0] for y, v in s.items() if y < year)
    career = sum(v[1] for y, v in s.items() if y < year) / den if den else lgp
    n = t = 0.0
    for w, dy in zip(MARCEL_W, (1, 2, 3)):
        if year - dy in s:
            n += w * s[year - dy][0]; t += w * s[year - dy][1]
    marcel = (t + MARCEL_K * lgp) / (n + MARCEL_K)
    if p["born"]:
        age = year - p["born"] - (1 if p["late"] else 0)      # age on 1 July
        marcel *= (1 + (29 - age) * 0.006) if age < 29 else (1 + (29 - age) * 0.003)
    return last, career, marcel


# ------------------------------------------------------------------- the estimator
def usual_level(hist, kind, pid, year):
    """D42's prior-season baseline: last three seasons, 1/.8/.6, regressed to league."""
    H = hist[kind]
    seasons = [s for s in H["players"].get(str(pid), [])
               if s[0] < year and s[0] >= year - 3 and s[2] is not None]
    lg_year = str(min(year - 1, H["years"][-1]))
    lg = H["league"].get(lg_year)
    if lg is None:
        return None
    n = t = 0.0
    for rec in seasons:                          # [year, pa, wOBA, xwOBA]
        yr, pa, w = rec[0], rec[1], rec[2]
        wt = (5 - (year - 1 - yr)) / 5.0        # 1, .8, .6
        n += wt * pa; t += wt * pa * w
    k = H["k"]
    mean = (t + k * lg) / (n + k)
    sd = H["tau"] * math.sqrt(k / (n + k))
    return {"mean": mean, "sd": sd, "lg": lg,
            "pa": sum(s[1] for s in seasons), "seasons": len(seasons)}


def talent(hist, kind, pid, year, season_pa, season_wn, s2):
    """Precision-weighted posterior for true talent, in wOBA."""
    u = usual_level(hist, kind, pid, year)
    if u is None:
        return None
    prior_prec = 1.0 / (u["sd"] ** 2)
    obs_prec = season_pa / s2 if season_pa > 0 else 0.0
    var = 1.0 / (prior_prec + obs_prec)
    mean = var * (u["mean"] * prior_prec +
                  (season_wn / season_pa if season_pa else 0.0) * obs_prec)
    return {"mean": mean, "var": var, "prior": u, "pa": season_pa}


def compare(a, b, exp_pa_a, exp_pa_b, months, s2, lower_is_better=False):
    """P(a outperforms b) over a window, plus the variance decomposition."""
    v_talent = a["var"] + b["var"]
    v_drift = 2.0 * (DRIFT_SD_PER_MONTH ** 2) * months
    v_sample = (s2 / exp_pa_a if exp_pa_a else 0.0) + (s2 / exp_pa_b if exp_pa_b else 0.0)
    total = v_talent + v_drift + v_sample
    delta = a["mean"] - b["mean"]
    if lower_is_better:
        delta = -delta
    p = phi(delta / math.sqrt(total)) if total > 0 else 0.5
    return {"p": p, "delta": delta, "total": total,
            "v_talent": v_talent, "v_drift": v_drift, "v_sample": v_sample}


def pa_to_separate(delta, s2, power_z=Z80, alpha_z=Z95):
    """PA *each* before a true gap of `delta` is detectable at 80% power."""
    if delta <= 0:
        return None
    return 2.0 * s2 * ((alpha_z + power_z) / delta) ** 2


# ------------------------------------------------------------------------ scoring
def brier(p, outcome):
    return (p - outcome) ** 2


def confidence_sequence(diffs, alpha=0.05, rho2=0.002):
    """Always-valid bound on the running mean of `diffs`, valid at every n at once.

    A fixed-horizon CI is only honest if you look once, at a sample size chosen in
    advance. Look after every observation and stop when it excludes zero and your
    false-positive rate goes to 1, not 0.05 -- the statistic is a random walk and
    it will eventually touch any fixed boundary. This project has already paid that
    bill: D28 records 2026 ceasing to be a holdout because it was scored dozens of
    times, and PREREGISTRATION.md is the pre-commitment answer to it. A confidence
    sequence is the other answer, the one that lets you keep looking.

    This is the variance-adaptive (asymptotic) normal-mixture sequence of
    Waudby-Smith et al. (2021): the same Robbins mixture boundary, scaled by the
    running sample sd rather than by a worst-case sub-Gaussian proxy. Using the
    proxy implied by boundedness (Brier differences live in [-1, 1], so sigma <= 1)
    is valid but useless here -- the observed sd is nearer 0.08, so the bound would
    come out about twelve times too wide and would badly overstate what peeking
    costs. `rho2` tunes where the boundary is tightest; it is set for a few
    thousand observations, which is the scale of this panel.
    """
    out, total, sq = [], 0.0, 0.0
    for i, d in enumerate(diffs, start=1):
        total += d; sq += d * d
        mean = total / i
        var = max(sq / i - mean * mean, 1e-12)          # running (biased) variance
        radius = math.sqrt(var) * math.sqrt(
            2.0 * (i * rho2 + 1.0) / (i * i * rho2) *
            math.log(math.sqrt(i * rho2 + 1.0) / alpha))
        out.append({"n": i, "mean": mean, "lo": mean - radius, "hi": mean + radius})
    return out


# ----------------------------------------------------------------------- backtest
def backtest(hist, shards, kind, window, min_pa_base, min_pa_target, seed=7):
    """Every block boundary, every season: predict, then score against what happened.

    Pairs are drawn disjointly at each timepoint -- each player appears in at most
    one pair per boundary -- so that within a timepoint the pairs are independent.
    Across timepoints they are not, and the same players recur all season; that is
    the main reason the intervals below are reported as a confidence SEQUENCE
    rather than a fixed-horizon CI, and it is still not a full fix.
    """
    s2 = hist["sigma2"]
    lower_is_better = (kind == "pit")
    rng = random.Random(seed)
    rows = []                                   # one record per scored pair

    for year in sorted(shards):
        d = shards[year]
        BL = d["blocks"]
        idx = field_index(d, kind)
        by_id = {r["id"]: r for r in d["rows"]}
        for t in range(2, len(BL) - window + 1):
            base, targ = BL[:t], BL[t:t + window]
            months = len(targ) / 2.0
            cands = []
            for pid, r in by_id.items():
                bpa, bwn, _ = totals(r, base, idx)
                tpa, twn, _ = totals(r, targ, idx)
                if bpa < min_pa_base or tpa < min_pa_target:
                    continue
                est = talent(hist, kind, pid, year, bpa, bwn, s2)
                if est is None:
                    continue
                cands.append({"id": pid, "name": r["n"], "est": est,
                              "season_w": bwn / bpa, "base_pa": bpa,
                              "real": twn / tpa, "targ_pa": tpa})
            if len(cands) < 2:
                continue
            rng.shuffle(cands)
            for i in range(0, len(cands) - 1, 2):
                a, b = cands[i], cands[i + 1]
                if a["real"] == b["real"]:
                    continue                    # no winner to score
                c = compare(a["est"], b["est"], a["targ_pa"], b["targ_pa"],
                            months, s2, lower_is_better)
                better = (a["real"] < b["real"]) if lower_is_better else (a["real"] > b["real"])
                # the alternatives, on the identical pair
                sd_season = math.sqrt(s2 / a["base_pa"] + s2 / b["base_pa"] +
                                      s2 / a["targ_pa"] + s2 / b["targ_pa"])
                d_season = a["season_w"] - b["season_w"]
                d_usual = a["est"]["prior"]["mean"] - b["est"]["prior"]["mean"]
                if lower_is_better:
                    d_season, d_usual = -d_season, -d_usual
                sd_usual = math.sqrt(a["est"]["prior"]["sd"] ** 2 + b["est"]["prior"]["sd"] ** 2 +
                                     2.0 * (DRIFT_SD_PER_MONTH ** 2) * months +
                                     s2 / a["targ_pa"] + s2 / b["targ_pa"])
                rows.append({
                    "year": year, "t": t, "outcome": 1 if better else 0,
                    "full": c["p"],
                    "season": phi(d_season / sd_season),
                    "usual": phi(d_usual / sd_usual),
                    "coin": 0.5,
                    "v_talent": c["v_talent"], "v_drift": c["v_drift"],
                    "v_sample": c["v_sample"], "delta": abs(c["delta"]),
                    # the raw signed gaps (A minus B, better-is-positive), so a baseline can be
                    # built from them without borrowing this estimator's variance model
                    "g_full": c["delta"], "g_season": d_season, "g_usual": d_usual,
                })
                na, nb = naive_levels(kind, a["id"], year), naive_levels(kind, b["id"], year)
                if na and nb:
                    sgn = -1.0 if lower_is_better else 1.0
                    rows[-1].update({"g_last": sgn * (na[0] - nb[0]),
                                     "g_career": sgn * (na[1] - nb[1]),
                                     "g_marcel": sgn * (na[2] - nb[2])})
    return rows


def calibration(rows, key, edges=(.5, .55, .6, .65, .7, .8, 1.01)):
    """Reliability diagram. Probabilities are folded to >= .5 by symmetry:
    saying 40% for A is saying 60% for B, so both land in the same bucket."""
    buckets = []
    lo = 0.5
    for hi in edges[1:]:
        sel = [r for r in rows
               if lo <= max(r[key], 1 - r[key]) < hi]
        if len(sel) < 30:
            lo = hi
            continue
        said = sum(max(r[key], 1 - r[key]) for r in sel) / len(sel)
        hit = sum(1 for r in sel
                  if (r["outcome"] == 1) == (r[key] >= 0.5)) / len(sel)
        se = math.sqrt(max(hit * (1 - hit), 1e-9) / len(sel))
        buckets.append({"lo": round(lo, 3), "hi": round(min(hi, 1.0), 3),
                        "n": len(sel), "said": round(said, 4),
                        "hit": round(hit, 4), "se": round(se, 4)})
        lo = hi
    return buckets


def brier_decomposition(rows, key):
    """Murphy's decomposition: reliability - resolution + uncertainty."""
    n = len(rows)
    base = sum(r["outcome"] for r in rows) / n
    groups = defaultdict(list)
    for r in rows:
        groups[round(r[key], 2)].append(r)
    rel = res = 0.0
    for p, g in groups.items():
        o = sum(x["outcome"] for x in g) / len(g)
        rel += len(g) * (p - o) ** 2
        res += len(g) * (o - base) ** 2
    return {"brier": round(sum(brier(r[key], r["outcome"]) for r in rows) / n, 5),
            "reliability": round(rel / n, 5),
            "resolution": round(res / n, 5),
            "uncertainty": round(base * (1 - base), 5)}


# --------------------------------------------------------------------------- main
FORECASTERS = [
    ("full",   "prior seasons + this season, shrunk"),
    ("season", "this season's wOBA, unshrunk"),
    ("usual",  "prior seasons only"),
    ("coin",   "always 50%"),
]


# --------------------------------------------------------------- naive baselines
def slice_baseline(rows, feat, nbins=10, shrink=20.0):
    """The dumbest calibrated forecaster there is: slice matchups by one raw gap, and predict the
    win rate that slice actually had.

    Fitted leave-one-season-out, so a season is never scored by rates learned from itself -- an
    in-sample lookup table is calibrated by construction and would look far better than it is.
    Folded by symmetry: "A favoured by +g" and "B favoured by -g" are the same matchup, so each
    slice is keyed on |g| and predicts how often the FAVOURED side won. Thin slices are shrunk
    toward the fold's overall favourite rate by `shrink` pseudo-matchups.

    This borrows nothing from the estimator: no sigma^2, no drift, no Phi. If it scores as well,
    the variance model is not earning its keep."""
    years = sorted({r["year"] for r in rows})
    out = {}
    for y in years:
        train = [r for r in rows if r["year"] != y and r[feat] != 0]
        test = [r for r in rows if r["year"] == y]
        if not train:
            for r in test: out[id(r)] = 0.5
            continue
        pts = sorted((abs(r[feat]), r["outcome"] if r[feat] > 0 else 1 - r["outcome"]) for r in train)
        base = sum(w for _, w in pts) / len(pts)
        k = max(1, min(nbins, len(pts) // 30))
        edges = [pts[int(i * len(pts) / k)][0] for i in range(1, k)]
        cells = [[] for _ in range(k)]
        for g, w in pts:
            cells[sum(g >= e for e in edges)].append(w)
        rate = [(sum(c) + shrink * base) / (len(c) + shrink) for c in cells]
        for r in test:
            g = r[feat]
            if g == 0:
                out[id(r)] = 0.5
                continue
            pf = rate[sum(abs(g) >= e for e in edges)]
            out[id(r)] = pf if g > 0 else 1 - pf
    return out


def cluster_boot(rows, a, b, reps=2000, seed=7):
    """95% CI on mean Brier(a) - Brier(b), resampling block boundaries (year, t): the pairs at one
    boundary share a date and league conditions, so they are not independent draws."""
    rng = random.Random(seed)
    by = {}
    for r in rows:
        by.setdefault((r["year"], r["t"]), []).append(brier(r[a], r["outcome"]) - brier(r[b], r["outcome"]))
    keys = list(by)
    vals = []
    for _ in range(reps):
        d = [x for k in (keys[rng.randrange(len(keys))] for _ in keys) for x in by[k]]
        vals.append(sum(d) / len(d))
    vals.sort()
    return vals[int(.025 * reps)], vals[int(.975 * reps)]


def score_window(hist, shards, kind, window, a, quiet=False):
    """Backtest one horizon and return everything the tab needs for it."""
    s2 = hist["sigma2"]
    rows = backtest(hist, shards, kind, window, a.min_base, a.min_target, a.seed)
    if not rows:
        return None
    scores = {k: brier_decomposition(rows, k) for k, _ in FORECASTERS}
    seqs, pairwise = {}, {}
    for other in ("season", "usual", "coin"):
        diffs = [brier(r[other], r["outcome"]) - brier(r["full"], r["outcome"]) for r in rows]
        seq = confidence_sequence(diffs)
        seqs[other] = seq
        n = len(diffs)
        mean = sum(diffs) / n
        sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1))
        half = Z95 * sd / math.sqrt(n)
        last = seq[-1]
        pairwise[other] = {
            "mean": mean, "fixed_lo": mean - half, "fixed_hi": mean + half,
            "seq_lo": last["lo"], "seq_hi": last["hi"],
            "verdict": ("full is better" if last["lo"] > 0 else
                        "full is worse" if last["hi"] < 0 else "not separated"),
            "fixed_verdict": "separated" if abs(mean) > half else "not separated",
            "width_ratio": (last["hi"] - last["lo"]) / (2 * half) if half else None,
        }
    # Naive baselines, fitted leave-one-season-out: slice by one raw gap and predict the win rate
    # that slice actually had. They borrow nothing from the estimator's variance model, so beating
    # them is the real test -- beating "always 50%" is a low bar any ranking clears.
    NAIVE = (("const", "g_usual", 1, "the player better last season wins a fixed share"),
             ("usual", "g_usual", 10, "slice by the gap in prior-season wOBA"),
             ("season", "g_season", 10, "slice by the gap in this season's wOBA"),
             ("last", "g_last", 10, "slice by the gap in last season's official wOBA"),
             ("career", "g_career", 10, "slice by the gap in career wOBA before this season"),
             ("marcel", "g_marcel", 10, "slice by the gap in Marcel projections (5/4/3, "
                                         "regressed with 3,000 PA, age-adjusted)"),
             ("recal", "g_full", 10, "slice by this estimator's own gap"))
    have_official = all("g_marcel" in r for r in rows)
    naive = {}
    for key, feat, nb, desc in NAIVE:
        if feat in ("g_last", "g_career", "g_marcel") and not have_official:
            continue
        pr = slice_baseline(rows, feat, nbins=nb)
        col = "n_" + key
        for r in rows:
            r[col] = pr[id(r)]
        b = sum(brier(r[col], r["outcome"]) for r in rows) / len(rows)
        lo, hi = cluster_boot(rows, col, "full")
        naive[key] = {"desc": desc, "brier": b, "diff": b - scores["full"]["brier"],
                      "lo": lo, "hi": hi,
                      "verdict": "estimator better" if lo > 0 else
                                 "baseline better" if hi < 0 else "no difference"}
    # the strongest honest competitor, excluding the recalibration (which is the estimator itself)
    best = min((k for k in ("const", "usual", "season", "last", "career", "marcel") if k in naive),
               key=lambda k: naive[k]["brier"])
    lo, hi = cluster_boot(rows, "coin", "full")
    skill = {"vs_coin": {"diff": scores["coin"]["brier"] - scores["full"]["brier"], "lo": lo, "hi": hi,
                         "significant": lo > 0},
             "best_naive": best,
             "naive_share": ((0.25 - naive[best]["brier"]) / (0.25 - scores["full"]["brier"])
                             if scores["full"]["brier"] < 0.25 else None)}

    cal = calibration(rows, "full")
    vt = sum(r["v_talent"] for r in rows) / len(rows)
    vd = sum(r["v_drift"] for r in rows) / len(rows)
    vs = sum(r["v_sample"] for r in rows) / len(rows)
    tot = vt + vd + vs
    med = sorted(abs(r["full"] - 0.5) for r in rows)[len(rows) // 2]

    if not quiet:
        print(f"\n=== window {window} ({window*15} days) — {len(rows):,} pairs ===")
        for k, desc in FORECASTERS:
            print(f"  {k:<8} Brier {scores[k]['brier']:.4f}  "
                  f"rel {scores[k]['reliability']:.5f}  res {scores[k]['resolution']:.5f}  {desc}")
        for b in cal:
            flag = "  <-- off" if abs(b["hit"] - b["said"]) > 2 * b["se"] else ""
            print(f"    said {b['said']:.3f} -> {b['hit']:.3f}  (n={b['n']:,}){flag}")
        print(f"  variance: talent {vt/tot:.1%}  drift {vd/tot:.1%}  sampling {vs/tot:.1%}"
              f"   median |P-.5| = {med:.3f}")

    return {
        "window": window, "days": window * 15, "n_pairs": len(rows),
        "scores": scores, "calibration": cal, "pairwise": pairwise,
        "variance_share": {"talent": vt / tot, "drift": vd / tot, "sampling": vs / tot},
        "median_edge": med,
        "naive": naive, "skill": skill,
        # Thinned hard: nothing in the UI plots these yet, and four horizons x three
        # comparisons at full resolution dominated the payload.
        "sequences": {k: v[::max(1, len(v) // 40)] + [v[-1]] for k, v in seqs.items()},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", default="bat", choices=["bat", "pit"])
    ap.add_argument("--windows", default="1,2,4,6",
                    help="horizons in half-month blocks; the tab offers 1,2,4,6 "
                         "(2 weeks / 1 month / 2 months / 3 months)")
    ap.add_argument("--min-base", type=float, default=100.0, help="min PA before the window")
    ap.add_argument("--min-target", type=float, default=40.0, help="min PA inside the window")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    hist, shards = load(a.kind)
    windows = [int(w) for w in a.windows.split(",") if w.strip()]
    print(f"{a.kind}, seasons {min(shards)}-{max(shards)}, horizons {windows}")

    horizons = {}
    for w in windows:
        r = score_window(hist, shards, a.kind, w, a)
        if r:
            horizons[str(w)] = r
    if not horizons:
        sys.exit("no scored pairs -- check the PA floors")

    # Calibration is conditioned on the horizon and NOT on how far into the
    # season the as-of date sits. Measured 2026-09-20: splitting the 30-day
    # panel at the season midpoint gives Brier .2373 early vs .2381 late and a
    # mean(actual - said) of +0.002 vs -0.006 -- no systematic effect, so
    # slicing on it would only thin the buckets.
    out = pathlib.Path(a.out) if a.out else DATA / f"matchup-{a.kind}.json"
    payload = {
        "generated_by": "matchup.py",
        "kind": a.kind,
        "seasons": [min(shards), max(shards)],
        "sigma2": hist["sigma2"], "drift_sd_per_month": DRIFT_SD_PER_MONTH,
        "horizons": horizons,
        "caveats": [
            "Pairs are disjoint within a block boundary but overlap across boundaries, "
            "and the same players recur all season, so the effective sample is smaller "
            "than n_pairs. This is why the interval is a confidence sequence rather "
            "than a fixed-horizon CI -- and that is a mitigation, not a fix.",
            "2026 is a development set, not a holdout (D28). It is included here "
            "because this estimator fits no coefficients to it, but any figure that "
            "moves a decision should be re-checked on 2027.",
            "Pairs are drawn from players who cleared both PA floors, so the sample "
            "is biased toward regulars: injuries, demotions and benchings are absent "
            "from the outcome, not scored as losses.",
            "The drift term is a league-average constant, not a per-player estimate. "
            "It cannot know about an injury, a swing change or a call-up.",
        ],
    }
    pathlib.Path(out).write_text(json.dumps(payload, separators=(",", ":")))
    print(f"\nwrote {out}  ({len(horizons)} horizons)")


if __name__ == "__main__":
    main()
