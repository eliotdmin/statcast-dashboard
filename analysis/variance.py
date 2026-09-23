#!/usr/bin/env python3
"""Measure per-PA outcome variance as a function of how good the hitter is.

    python3 variance.py            # hitters  -> web/data/variance.json
    python3 variance.py --kind pit
    python3 variance.py --report   # print the strata table, write nothing

Why this exists
---------------
The whole site sizes its uncertainty with one number: sigma^2 = 0.2258 per plate
appearance, measured in FINDINGS 2026-09-12 and applied to every hitter alike.
Every z on the change log, every shrunk percentile, and every head-to-head
probability divides by it.

It cannot be a constant. wOBA is a weighted sum over outcomes, and the weights
are far apart -- an out scores 0 and a home run about 2.0 -- so a hitter who
reaches more often, and reaches for more bases, has a larger per-PA second
moment almost by construction. Using one sigma^2 understates the uncertainty
around the best hitters and overstates it around the worst, which is exactly
backwards for a site whose whole claim is that it sizes uncertainty honestly.

Method
------
For adjacent half-month blocks of the same player inside one season,

    E[(w2 - w1)^2] = sigma^2 * (1/pa1 + 1/pa2) + var(drift over half a month)

so regressing the squared difference on (1/pa1 + 1/pa2) gives sigma^2 as the
slope and the drift variance as the intercept. That is the same decomposition
the 0.2258 came from, run inside strata instead of pooled.

The strata are defined by the hitter's PRIOR-SEASON rate, taken from
history.json -- never from the blocks being measured. Stratifying on the same
data would sort players partly on their own noise and manufacture the gradient
this script is trying to detect.
"""
import argparse, json, math, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "web" / "data"
PA_KEY = {"bat": "pa", "pit": "bf"}
MIN_BLOCK_PA = 25           # a block small enough to be mostly noise is still usable,
                            # but below ~25 the 1/pa term explodes and dominates the fit


def load(kind):
    hist = json.loads((DATA / "history.json").read_text())
    shards = {}
    for p in sorted(DATA.glob(f"{kind}-*.json")):
        shards[int(p.stem.split("-")[1])] = json.loads(p.read_text())
    if not shards:
        sys.exit(f"no {kind}-*.json shards in {DATA}; run blocks_all.py first")
    return hist, shards


def prior_rate(hist, kind, pid, year):
    """PA-weighted rate over seasons strictly before `year`. Out of sample by construction."""
    seasons = [s for s in hist[kind]["players"].get(str(pid), [])
               if s[0] < year and s[2] is not None]
    pa = sum(s[1] for s in seasons)
    return (sum(s[1] * s[2] for s in seasons) / pa, pa) if pa > 0 else (None, 0)


def pairs(hist, kind, shards, min_prior_pa=200):
    """Adjacent-block pairs, each tagged with the hitter's prior-season rate."""
    out = []
    for year, d in sorted(shards.items()):
        BL, f = d["blocks"], d["fields"]
        ipa, iwn = f.index(PA_KEY[kind]), f.index("wn")
        for r in d["rows"]:
            rate, ppa = prior_rate(hist, kind, r["id"], year)
            if rate is None or ppa < min_prior_pa:
                continue
            for i in range(len(BL) - 1):
                v1, v2 = r["b"].get(BL[i]), r["b"].get(BL[i + 1])
                if not v1 or not v2:
                    continue
                p1, p2 = v1[ipa], v2[ipa]
                if p1 < MIN_BLOCK_PA or p2 < MIN_BLOCK_PA:
                    continue
                w1, w2 = v1[iwn] / p1, v2[iwn] / p2
                out.append({"rate": rate, "x": 1.0 / p1 + 1.0 / p2,
                            "d2": (w2 - w1) ** 2, "id": r["id"]})
    return out


def fit(rows):
    """OLS of d2 on x. Slope is sigma^2, intercept is the half-month drift variance."""
    n = len(rows)
    if n < 30:
        return None
    mx = sum(r["x"] for r in rows) / n
    my = sum(r["d2"] for r in rows) / n
    sxx = sum((r["x"] - mx) ** 2 for r in rows)
    if sxx <= 0:
        return None
    sxy = sum((r["x"] - mx) * (r["d2"] - my) for r in rows)
    slope = sxy / sxx
    return {"sigma2": slope, "drift_var": my - slope * mx, "n": n}


def boot_sigma2(rows, reps=400, seed=7):
    """Resample PLAYERS, not pairs: a hitter contributes many correlated pairs."""
    rng = random.Random(seed)
    by_id = {}
    for r in rows:
        by_id.setdefault(r["id"], []).append(r)
    ids = list(by_id)
    vals = []
    for _ in range(reps):
        samp = []
        for _ in range(len(ids)):
            samp.extend(by_id[ids[rng.randrange(len(ids))]])
        f = fit(samp)
        if f:
            vals.append(f["sigma2"])
    vals.sort()
    if len(vals) < 20:
        return None, None
    return vals[int(.025 * len(vals))], vals[int(.975 * len(vals))]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", default="bat", choices=["bat", "pit"])
    ap.add_argument("--strata", type=int, default=5)
    ap.add_argument("--report", action="store_true", help="print only, write nothing")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    hist, shards = load(a.kind)
    rows = pairs(hist, a.kind, shards)
    if not rows:
        sys.exit("no usable block pairs")
    pooled = fit(rows)
    plo, phi = boot_sigma2(rows)
    print(f"{len(rows):,} adjacent-block pairs, {a.kind}, "
          f"{min(shards)}-{max(shards)}, {len({r['id'] for r in rows})} players\n")
    print(f"pooled sigma^2 = {pooled['sigma2']:.4f}  95% [{plo:.4f}, {phi:.4f}]"
          f"   (site constant 0.2258)")
    print(f"half-month drift sd = {math.sqrt(max(pooled['drift_var'],0)):.4f}\n")

    rows.sort(key=lambda r: r["rate"])
    per = len(rows) // a.strata
    strata = []
    print(f"{'stratum (prior-season rate)':<30} {'pairs':>7} {'sigma^2':>9} {'95% CI':>20}")
    for i in range(a.strata):
        chunk = rows[i * per:] if i == a.strata - 1 else rows[i * per:(i + 1) * per]
        f = fit(chunk)
        if not f:
            continue
        lo, hi = boot_sigma2(chunk, reps=250)
        mid = sum(r["rate"] for r in chunk) / len(chunk)
        strata.append({"rate": mid, "sigma2": f["sigma2"], "n": f["n"],
                       "lo": lo, "hi": hi,
                       "lo_rate": chunk[0]["rate"], "hi_rate": chunk[-1]["rate"]})
        print(f"  {chunk[0]['rate']:.3f}-{chunk[-1]['rate']:.3f} (mean {mid:.3f})"
              f"{'':<4} {f['n']:>7,} {f['sigma2']:>9.4f}"
              f"   [{lo:.4f}, {hi:.4f}]" if lo else "")

    # straight line through the strata, weighted by pair count: sigma^2 = a + b*rate
    n = sum(s["n"] for s in strata)
    mx = sum(s["n"] * s["rate"] for s in strata) / n
    my = sum(s["n"] * s["sigma2"] for s in strata) / n
    sxx = sum(s["n"] * (s["rate"] - mx) ** 2 for s in strata)
    b = sum(s["n"] * (s["rate"] - mx) * (s["sigma2"] - my) for s in strata) / sxx
    aa = my - b * mx
    print(f"\nfitted  sigma^2(rate) = {aa:+.4f} {b:+.4f} * rate")
    for s in strata:
        print(f"    rate {s['rate']:.3f}: measured {s['sigma2']:.4f}  "
              f"fitted {aa + b * s['rate']:.4f}")

    if a.report:
        return
    out = pathlib.Path(a.out) if a.out else DATA / f"variance-{a.kind}.json"
    out.write_text(json.dumps({
        "generated_by": "variance.py", "kind": a.kind,
        "seasons": [min(shards), max(shards)],
        "pooled": {"sigma2": pooled["sigma2"], "lo": plo, "hi": phi,
                   "drift_var_half_month": pooled["drift_var"], "n_pairs": pooled["n"]},
        "model": {"form": "sigma2 = a + b * rate", "a": aa, "b": b,
                  "rate_lo": strata[0]["rate"], "rate_hi": strata[-1]["rate"]},
        "strata": strata,
        "legacy_constant": 0.2258,
        "caveats": [
            "Strata are defined by PRIOR-SEASON rate, never by the blocks measured, so "
            "the gradient is not an artefact of sorting players on their own noise.",
            "The fit is clamped to the measured rate range in use; outside it the line "
            "is an extrapolation and the pooled constant is used instead.",
            "Bootstrap resamples players, not pairs, because one hitter contributes many "
            "correlated adjacent pairs.",
        ],
    }, separators=(",", ":")))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
