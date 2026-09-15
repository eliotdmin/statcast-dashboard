#!/usr/bin/env python3
"""
planner.py -- "How many swings do I need before I can tell whether this worked?"

Spearman-Brown run backwards, plus a power calculation. This is the same arithmetic
as a clinical-trial sample-size calculation, and it is used the same way: BEFORE the
intervention, not after. A hitting lab that changes a swing and evaluates it on 40
swings has run an underpowered trial; this tells you what powered would have been.

Two questions:

  --reliability 0.7           how many PA/swings until this metric's BETWEEN-PLAYER
                              ranking is 70% signal?
  --detect "1.5 mph"          how many until a change of this size in ONE player is
                              distinguishable from noise at alpha=.05, power=.80?

Derivations
-----------
(1) Reliability target. Spearman-Brown says rho(n) = k*p / (1 + (k-1)*p) with
    k = n/n0 and p = rho(n0). Solving for k at a target t:

            t * (1 + (k-1)p) = k p
        =>  t - t p = k p (1 - t)
        =>  k = t(1-p) / (p(1-t))        and      n = k * n0

    Note the (1-t) in the denominator: the cost of the last few points of
    reliability is unbounded. Going from .70 to .90 is not 1.3x the sample, it is
    about 3.9x.

(2) Detectable difference. Noise variance at sample n, from the decomposition:

        var_noise(n) = (1 - p) * var_obs(n0) * (n0 / n)

    Comparing a window of n against a baseline large enough to treat as known,
    se(n) = sd_obs(n0) * sqrt((1-p) * n0 / n). A two-sided test at alpha with
    power 1-beta needs |delta| >= (z_{alpha/2} + z_beta) * se(n), so

        n  =  n0 * (1-p) * var_obs(n0) * ( (z_{alpha/2} + z_beta) / delta )^2

    If the baseline is itself only m observations, multiply by (1 + n/m); the tool
    does this with --baseline.
"""
import json, math, os, argparse
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKS = os.path.join(HERE, "output", "blocks_all.json")

FIELDS = {
 "bat": {"bat speed":("sbs","nbs","mph"), "swing length":("ssl","nbs","ft"),
         "attack angle":("saa","naa","deg"), "attack direction":("sad","naa","deg"),
         "exit velo":("sev","nev","mph"), "launch angle":("sla","nev","deg"),
         "hard-hit%":("hh","nev","pp"), "barrel%":("brl","nev","pp"),
         "sweet-spot%":("sweet","nev","pp"), "ground-ball%":("gb","nbb","pp"),
         "K%":("k","pa","pp"), "BB%":("bb","pa","pp"), "whiff%":("whf","sw","pp"),
         "chase%":("ozsw","oz","pp"), "xwOBA":("xn","pa","pts"), "wOBA":("wn","pa","pts")},
 "pit": {"fastball velo":("sv","nv","mph"), "spin rate":("ssp","nsp","rpm"),
         "extension":("sex","nex","ft"), "arm angle":("saa","naa","deg"),
         "K%":("k","bf","pp"), "BB%":("bb","bf","pp"), "whiff%":("whf","sw","pp"),
         "zone%":("iz","zt","pp"), "edge%":("edge","loct","pp"),
         "exit velo allowed":("sev","nev","mph"), "hard-hit% allowed":("hh","nev","pp"),
         "ground-ball%":("gb","nbb","pp"), "xwOBA against":("xn","bf","pts"),
         "wOBA against":("wn","bf","pts")}}

def moments(kind):
    """League sd of each metric measured over half-seasons, i.e. at n0.
    This is var_obs(n0) -- the denominator of reliability, at the sample size the
    reliability was measured at. Both must come from the same window or the
    decomposition is inconsistent."""
    d = json.load(open(BLOCKS))[kind]
    F = {f:i for i,f in enumerate(d["fields"])}
    blocks = d["blocks"]; nf = len(d["fields"])
    byyear = {}
    for i,b in enumerate(blocks): byyear.setdefault(b[:4], []).append(i)
    out = {}
    for lab,(num,den,unit) in FIELDS[kind].items():
        xs = []
        for r in d["rows"]:
            yb = byyear[str(r["y"])]; half = yb[:len(yb)//2]
            tot = [0.0]*nf
            for i in half:
                v = r["b"].get(blocks[i])
                if v:
                    for j,x in enumerate(v): tot[j] += x
            if tot[F[den]] >= 40: xs.append(tot[F[num]]/tot[F[den]])
        if len(xs) > 50: out[lab] = (st.pstdev(xs), unit, len(xs))
    return d["rel"], out

Z = {0.80:0.8416, 0.90:1.2816, 0.95:1.6449, 0.975:1.9600, 0.99:2.3263}

def n_for_reliability(p, n0, t):
    if t >= 1: return float("inf")
    return n0 * (t*(1-p)) / (p*(1-t))

def n_for_detect(p, n0, sd0, delta, alpha=0.05, power=0.80, baseline=None):
    za = Z[1-alpha/2]; zb = Z[power]
    C = n0*(1-p)*(sd0**2)*((za+zb)/delta)**2     # n needed against a KNOWN baseline
    if not baseline: return C
    # Finite baseline m: se^2 = v(n) + v(m), so n solves n = C*(1 + n/m), i.e.
    #     n = C / (1 - C/m)
    # and if C >= m there is NO n that works -- the baseline itself is too noisy to
    # resolve a difference this small, no matter how long you watch. That is a real
    # answer, not an error: it means "lengthen the baseline first."
    if C >= baseline: return float("inf")
    return C/(1 - C/baseline)

def fmt_unit(u, v):
    return {"pp":f"{100*v:.1f} pp","pts":f"{v:.3f}","mph":f"{v:.1f} mph",
            "ft":f"{v:.2f} ft","deg":f"{v:.1f} deg","rpm":f"{v:.0f} rpm"}.get(u,f"{v:.3f}")

def parse_delta(s, unit):
    x = float("".join(c for c in s if c.isdigit() or c in ".-"))
    return x/100 if unit=="pp" else x

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["bat","pit"], default="bat")
    ap.add_argument("--metric"); ap.add_argument("--reliability", type=float)
    ap.add_argument("--detect"); ap.add_argument("--baseline", type=float)
    ap.add_argument("--power", type=float, default=0.80)
    a = ap.parse_args()
    rel, mom = moments(a.kind)
    unitname = "PA" if a.kind=="bat" else "BF"

    if not a.metric:
        print(f"\n  Sample size for a reliable BETWEEN-PLAYER ranking, in {unitname}\n"
              f"  (n0 and all projections are on the plate-appearance scale the\n"
              f"   split-half was measured on, including the tracked-swing metrics)\n")
        print(f"  {'metric':<20}{'rho at n0':>10}{'n0':>7}" +
              "".join(f"{'rho='+str(t):>10}" for t in (0.5,0.7,0.8,0.9)))
        for lab in FIELDS[a.kind]:
            if lab not in rel or lab not in mom: continue
            p, n0 = rel[lab]["sb"], rel[lab]["n0"]
            row = "".join(f"{n_for_reliability(p,n0,t):>10,.0f}" for t in (0.5,0.7,0.8,0.9))
            print(f"  {lab:<20}{p:>10.3f}{n0:>7.0f}{row}")
        print("\n  The last column is the point of the table: the price of the final")
        print("  increment of reliability is unbounded, and for wOBA it is off the map.")
        raise SystemExit

    lab = a.metric
    if lab not in rel: raise SystemExit(f"unknown metric {lab!r}; options: {', '.join(rel)}")
    p, n0 = rel[lab]["sb"], rel[lab]["n0"]
    sd0, unit, k = mom[lab]
    print(f"\n  {lab}  ({a.kind})")
    print(f"  measured split-half reliability {p:.3f} at n0 = {n0:.0f} {unitname}")
    print(f"  league sd over a half-season: {fmt_unit(unit, sd0)}  (n = {k} player-seasons)\n")
    if a.reliability:
        n = n_for_reliability(p, n0, a.reliability)
        print(f"  for a ranking that is {a.reliability:.0%} signal you need "
              f"{n:,.0f} {unitname}")
    if a.detect:
        dv = parse_delta(a.detect, unit)
        for pw in (0.80, 0.90):
            n = n_for_detect(p, n0, sd0, dv, power=pw, baseline=a.baseline)
            tail = (f" (against a {a.baseline:,.0f}-{unitname} baseline)" if a.baseline
                    else " (against a baseline treated as known)")
            if n == float("inf"):
                C = n_for_detect(p, n0, sd0, dv, power=pw)
                print(f"  to detect {fmt_unit(unit,dv)} at alpha=.05, power={pw:.0%}: "
                      f"IMPOSSIBLE against a {a.baseline:,.0f}-{unitname} baseline -- "
                      f"the baseline alone needs to exceed {C:,.0f} {unitname} "
                      f"before any follow-up window can resolve a difference this small.")
            else:
                print(f"  to detect a change of {fmt_unit(unit,dv)} at alpha=.05, "
                      f"power={pw:.0%}: {n:,.0f} {unitname}" + tail)
