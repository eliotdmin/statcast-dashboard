#!/usr/bin/env python3
"""Put an interval on every reliability figure the site shrinks with.

    python3 reliability.py           # hitters  -> web/data/reliability-bat.json
    python3 reliability.py --kind pit
    python3 reliability.py --check   # verify we reproduce the shipped rel.sb, write nothing

Why this exists
---------------
Every shrunk percentile on the site is `50 + rho*(raw - 50)`, and every `% real`
chip is that same rho. It is published to three decimals -- bat speed .974,
swing length .982 -- with no indication of how precisely it is known, and it is
then projected to other sample sizes by Spearman-Brown, which carries whatever
error is in it along for the ride.

rho is a correlation across a few hundred player-seasons. It has a sampling
distribution like anything else, and "how much of this number is real" deserves
the same treatment the site gives every other number on the page.

Method
------
Exactly the estimator in blocks_all.py -- odd blocks against even blocks, pooled
across seasons, corrected by Spearman-Brown rho0 = 2r/(1+r) -- recomputed here
from the shipped shards so it needs no database, then bootstrapped by resampling
PLAYER-SEASONS with replacement. `--check` asserts the point estimates match
what blocks_all.py wrote, so this file cannot silently drift from the thing it
is putting error bars on.
"""
import argparse, json, math, pathlib, random, sys

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "web" / "data"

# (label, numerator field, denominator field) -- must match blocks_all.py's MB
METRICS = {
    "bat": [("xwOBA", "xn", "pa"), ("wOBA", "wn", "pa"), ("K%", "k", "pa"),
            ("BB%", "bb", "pa"), ("whiff%", "whf", "sw"), ("chase%", "ozsw", "oz"),
            ("bat speed", "sbs", "nbs"), ("swing length", "ssl", "nbs"),
            ("attack angle", "saa", "naa"), ("attack direction", "sad", "naa"),
            ("exit velo", "sev", "nev"), ("launch angle", "sla", "nev"),
            ("hard-hit%", "hh", "nev"), ("barrel%", "brl", "nev"),
            ("sweet-spot%", "sweet", "nev"), ("ground-ball%", "gb", "nbb")],
    "pit": [("xwOBA against", "xn", "bf"), ("wOBA against", "wn", "bf"),
            ("K%", "k", "bf"), ("BB%", "bb", "bf"), ("whiff%", "whf", "sw"),
            ("zone%", "iz", "zt"), ("chase induced%", "ozsw", "oz"),
            ("edge%", "edge", "loct"), ("fastball velo", "sv", "nv"),
            ("spin rate", "ssp", "nsp"), ("extension", "sex", "nex"),
            ("arm angle", "saa", "naa"), ("exit velo allowed", "sev", "nev"),
            ("hard-hit% allowed", "hh", "nev"), ("ground-ball%", "gb", "nbb")],
}
PA_KEY = {"bat": "pa", "pit": "bf"}
HALF_FLOOR = 60          # blocks_all.py requires 60 in each half


def halves(kind):
    """One (odd-half, even-half) pair of summed counters per qualifying player-season."""
    out, fields, shipped = [], None, None
    for p in sorted(DATA.glob(f"{kind}-*.json")):
        d = json.loads(p.read_text())
        fields = fields or d["fields"]
        shipped = shipped or d.get("rel")
        BL, F = d["blocks"], {f: i for i, f in enumerate(d["fields"])}
        ipa = F[PA_KEY[kind]]
        for r in d["rows"]:
            a = [0.0] * len(d["fields"]); b = [0.0] * len(d["fields"])
            for i, blk in enumerate(BL):
                v = r["b"].get(blk)
                if not v:
                    continue
                t = a if i % 2 == 0 else b
                for j in range(len(v)):
                    t[j] += v[j]
            if a[ipa] >= HALF_FLOOR and b[ipa] >= HALF_FLOOR:
                out.append((a, b))
    if not out:
        sys.exit(f"no {kind}-*.json shards in {DATA}; run blocks_all.py first")
    return out, {f: i for i, f in enumerate(fields)}, shipped


def corr(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def sb_for(rows, F, num, den):
    """Spearman-Brown corrected split-half reliability, as blocks_all.py computes it."""
    xs, ys = [], []
    for a, b in rows:
        if a[F[den]] > 0 and b[F[den]] > 0:
            xs.append(a[F[num]] / a[F[den]]); ys.append(b[F[num]] / b[F[den]])
    r = corr(xs, ys)
    if r is None:
        return None, 0
    return max(2 * r / (1 + r), 0.02), len(xs)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", default="bat", choices=["bat", "pit"])
    ap.add_argument("--reps", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--check", action="store_true",
                    help="only verify the point estimates match the shipped shards")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows, F, shipped = halves(a.kind)
    rng = random.Random(a.seed)
    print(f"{len(rows)} player-seasons with {HALF_FLOOR}+ in each half, {a.kind}\n")

    out, worst = {}, 0.0
    hdr = f"{'metric':>20} {'rho':>7} {'95% CI':>18} {'width':>7}"
    print(hdr + ("   shipped" if a.check else ""))
    for lab, num, den in METRICS[a.kind]:
        point, n = sb_for(rows, F, num, den)
        if point is None:
            continue
        vals = []
        for _ in range(a.reps):
            samp = [rows[rng.randrange(len(rows))] for _ in range(len(rows))]
            s, _ = sb_for(samp, F, num, den)
            if s is not None:
                vals.append(s)
        vals.sort()
        lo, hi = vals[int(.025 * len(vals))], vals[int(.975 * len(vals))]
        out[lab] = {"sb": point, "lo": lo, "hi": hi, "n": n}
        line = f"{lab:>20} {point:>7.3f}   [{lo:.3f}, {hi:.3f}] {hi-lo:>7.3f}"
        if a.check and shipped and lab in shipped:
            d = abs(point - shipped[lab]["sb"]); worst = max(worst, d)
            line += f"   {shipped[lab]['sb']:.3f} {'ok' if d < 5e-3 else 'MISMATCH'}"
        print(line)

    if a.check:
        print(f"\nlargest deviation from the shipped rel.sb: {worst:.5f}")
        return
    p = pathlib.Path(a.out) if a.out else DATA / f"reliability-{a.kind}.json"
    p.write_text(json.dumps({
        "generated_by": "reliability.py", "kind": a.kind,
        "n_player_seasons": len(rows), "reps": a.reps, "seed": a.seed,
        "metrics": out,
        "caveats": [
            "The bootstrap resamples player-seasons, which is the unit the correlation "
            "is taken over. It does not resample blocks, so it captures uncertainty in "
            "WHICH players were measured, not in how they were split into halves.",
            "The interval is on the split-half figure at n0. Spearman-Brown projection "
            "to another sample size carries this uncertainty with it and widens nothing, "
            "so a projected rho is at least this uncertain and probably more.",
        ],
    }, separators=(",", ":")))
    print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
