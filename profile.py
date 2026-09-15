#!/usr/bin/env python3
"""
profile.py -- assemble the evidence packet for one player over one stretch, and
(optionally) ask an LLM to write the scouting profile from it.

The whole design principle: THE MODEL NEVER SEES A RAW NUMBER WITHOUT ITS ERROR BAR.

Every metric in the packet arrives with four things attached:
  value        what he actually did
  pct_raw      where that ranks among comparable players in the same span
  reliability  the share of the spread in that ranking that is real at this sample
               size (var_true / var_observed, projected via Spearman-Brown from the
               measured half-season split-half -- see FINDINGS.md / D9)
  pct_shrunk   50 + reliability * (pct_raw - 50), the honest point estimate
and, where a baseline exists, a change block:
  base         the same rate over the player's comparison window
  delta        stretch minus baseline
  delta_z      delta divided by the standard error that sampling noise alone would
               produce over these two sample sizes
  verdict      one of: noise / weak / real  -- thresholds at |z| < 1.5, < 2.5, >= 2.5

An LLM handed pct_raw alone will write "his sweet-spot rate collapsed to the 12th
percentile" about a number that is 0-34% signal over two weeks. Handed delta_z it
cannot, because the packet says so in the same breath.

Usage
  python profile.py --kind bat --player "Alex Bregman" --year 2026 \
                    --from 2026-04-B --to 2026-05-B --dry-run
  python profile.py --kind pit --player "Sandy Alcantara" --year 2026 --last 3
  # add --write to actually call the API (needs ANTHROPIC_API_KEY in the environment)

Baseline default is "the rest of the same season" (within-season change), which is
what a mid-season profile is actually asking about.  --base prior uses the prior
season instead.  A stretch with no usable baseline gets change=None and the prompt
tells the model to describe rather than diagnose.
"""
import argparse, json, math, os, sys, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKS = os.path.join(HERE, "output", "blocks_all.json")
PROMPT = os.path.join(HERE, "profile_prompt.md")

# label, numerator field, denominator field, formatter, higher-is-better, group
METRICS = {
"bat": [
 ("bat speed",      "sbs","nbs", "{:.1f} mph",  1, "swing"),
 ("swing length",   "ssl","nbs", "{:.2f} ft",   1, "swing"),
 ("attack angle",   "saa","naa", "{:.1f} deg",  1, "swing"),
 ("attack direction","sad","naa","{:+.1f} deg", 1, "swing"),
 ("K%",             "k",  "pa",  "{:.1%}",      0, "discipline"),
 ("BB%",            "bb", "pa",  "{:.1%}",      1, "discipline"),
 ("whiff%",         "whf","sw",  "{:.1%}",      0, "discipline"),
 ("chase%",         "ozsw","oz", "{:.1%}",      0, "discipline"),
 ("exit velo",      "sev","nev", "{:.1f} mph",  1, "contact"),
 ("hard-hit%",      "hh", "nev", "{:.1%}",      1, "contact"),
 ("barrel%",        "brl","nev", "{:.1%}",      1, "contact"),
 ("launch angle",   "sla","nev", "{:.1f} deg",  1, "contact"),
 ("sweet-spot%",    "sweet","nev","{:.1%}",     1, "contact"),
 ("ground-ball%",   "gb", "nbb", "{:.1%}",      0, "contact"),
 ("xwOBA",          "xn", "pa",  "{:.3f}",      1, "results"),
 ("wOBA",           "wn", "pa",  "{:.3f}",      1, "results"),
],
"pit": [
 ("fastball velo",  "sv", "nv",  "{:.1f} mph",  1, "delivery"),
 ("spin rate",      "ssp","nsp", "{:.0f} rpm",  1, "delivery"),
 ("extension",      "sex","nex", "{:.2f} ft",   1, "delivery"),
 ("arm angle",      "saa","naa", "{:.1f} deg",  1, "delivery"),
 ("K%",             "k",  "bf",  "{:.1%}",      1, "command"),
 ("BB%",            "bb", "bf",  "{:.1%}",      0, "command"),
 ("whiff%",         "whf","sw",  "{:.1%}",      1, "command"),
 ("zone%",          "iz", "zt",  "{:.1%}",      1, "command"),
 ("chase induced%", "ozsw","oz", "{:.1%}",      1, "command"),
 ("edge%",          "edge","loct","{:.1%}",     1, "command"),
 ("exit velo allowed","sev","nev","{:.1f} mph", 0, "contact"),
 ("hard-hit% allowed","hh","nev","{:.1%}",      0, "contact"),
 ("ground-ball%",   "gb", "nbb", "{:.1%}",      1, "contact"),
 ("xwOBA against",  "xn", "bf",  "{:.3f}",      0, "results"),
 ("wOBA against",   "wn", "bf",  "{:.3f}",      0, "results"),
]}
# Things that move a metric without the underlying skill moving. These ride along in
# the packet so the model cannot write a mechanical story that a mix change explains.
CONFOUND = {
 "arm angle": "averaged over every pitch type thrown; a change in pitch mix moves it "
              "without the delivery changing",
 "spin rate": "averaged over every pitch type; mix changes move it",
 "fastball velo": "four-seam/sinker only, but a starter moved to relief (or the reverse) "
                  "will show a velocity change that is a role change",
 "attack angle": "measured on competitive swings; a hitter who sees more breaking balls "
                 "can show an attack-angle change from pitch diet alone",
 "ground-ball%": "strongly park- and opponent-independent, but tiny denominators early; "
                 "check the batted-ball count before reading anything into it",
 "sweet-spot%": "the least reliable Statcast rate in this dataset -- measured signal share "
                "0.0 at league-change scale (see FINDINGS.md). Treat as decoration.",
 "wOBA": "outcome statistic. At any stretch length in this tool it is mostly the sequence "
         "of balls in play finding gloves or grass.",
 "wOBA against": "outcome statistic, and for a pitcher it also contains his defense.",
}
PAKEY = {"bat":"pa", "pit":"bf"}
PANAME= {"bat":"plate appearances", "pit":"batters faced"}

def load(kind):
    d = json.load(open(BLOCKS))[kind]
    F = {f:i for i,f in enumerate(d["fields"])}
    return d, F

def summ(row, blocks, idxs, nfields):
    out = [0.0]*nfields
    for i in idxs:
        v = row["b"].get(str(i)) or row["b"].get(blocks[i])
        if not v: continue
        for j,x in enumerate(v): out[j] += x
    return out

def rel_at(rel, label, n):
    """Spearman-Brown projection of the measured split-half to sample size n."""
    r = rel.get(label)
    if not r or n <= 0: return None
    k = n / r["n0"]; p = r["sb"]
    return max(0.0, min(1.0, k*p / (1 + (k-1)*p)))

def pct_of(pool, v):
    if not pool: return None
    return 100.0 * sum(1 for x in pool if x < v) / len(pool)

def build(kind, name, year, i0, i1, base_mode="season", min_n=20):
    d, F = load(kind)
    blocks = d["blocks"]; rel = d["rel"]; PK = PAKEY[kind]; nf = len(d["fields"])
    rows = [r for r in d["rows"] if r["y"] == year]
    me = next((r for r in rows if r["n"].lower() == name.lower()), None)
    if me is None:
        cand = [r["n"] for r in rows if name.lower() in r["n"].lower()]
        raise SystemExit(f"no {kind} named {name!r} in {year}." +
                         (f" did you mean: {', '.join(cand[:6])}?" if cand else ""))
    span = list(range(i0, i1+1))
    mine = summ(me, blocks, span, nf)
    n = mine[F[PK]]
    if n < 1: raise SystemExit(f"{me['n']} has no {PANAME[kind]} in that span.")

    yearblocks = [i for i,b in enumerate(blocks) if b.startswith(str(year))]
    if base_mode == "season":
        bidx = [i for i in yearblocks if i not in span]
        base_label = f"the rest of {year}"
        base_row = me
    else:
        prior = [r for r in d["rows"] if r["y"] == year-1 and r["id"] == me["id"]]
        base_row = prior[0] if prior else None
        bidx = [i for i,b in enumerate(blocks) if b.startswith(str(year-1))]
        base_label = f"all of {year-1}"
    basev = summ(base_row, blocks, bidx, nf) if base_row else None
    bn = basev[F[PK]] if basev else 0

    peers = [(r, summ(r, blocks, span, nf)) for r in rows]
    peers = [(r,v) for r,v in peers if v[F[PK]] >= min_n]

    out = {
      "player": me["n"], "mlbam_id": me["id"], "kind": kind, "season": year,
      "span": {"from": blocks[i0], "to": blocks[i1],
               "label": f"{blocks[i0]} through {blocks[i1]}",
               "n": round(n), "n_unit": PANAME[kind]},
      "baseline": {"label": base_label, "n": round(bn), "usable": bn >= 60},
      "peer_pool": {"n_players": len(peers),
                    "note": f"players with at least {min_n} {PANAME[kind]} in the same span of {year}"},
      "metrics": []
    }
    for label, num, den, fmt, hib, grp in METRICS[kind]:
        dv = mine[F[den]]
        if not dv:
            out["metrics"].append({"metric":label,"group":grp,"available":False}); continue
        v = mine[F[num]]/dv
        pool = [x[F[num]]/x[F[den]] for _,x in peers if x[F[den]] > 0]
        raw = pct_of(pool, v)
        if not hib and raw is not None: raw = 100-raw
        r = rel_at(rel, label, n) or 0.0
        m = {"metric": label, "group": grp, "available": True,
             **({"confound": CONFOUND[label]} if label in CONFOUND else {}),
             "value": round(v, 5), "display": fmt.format(v),
             "higher_is_better": bool(hib),
             "pct_raw": round(raw,1) if raw is not None else None,
             "reliability": round(r,3),
             "pct_shrunk": round(50 + r*(raw-50),1) if raw is not None else None}
        # --- change vs the player's own baseline, with a noise-only error bar ---
        if basev and basev[F[den]] and bn >= 60:
            bv = basev[F[num]]/basev[F[den]]
            sd_obs = st.pstdev(pool) if len(pool) > 2 else None
            rb = rel_at(rel, label, bn) or 0.0
            if sd_obs and sd_obs > 0:
                # noise sd at each sample size, from var_noise = var_obs * (1 - rho)
                s1 = sd_obs*math.sqrt(max(1e-9, 1-r))
                # rescale observed spread to the baseline's sample size:
                # var_obs(n) = var_true + var_noise(n), var_noise scales as 1/n
                vt = (sd_obs**2)*r
                s2 = math.sqrt(max(1e-12, (sd_obs**2 - vt) * (n/bn)))
                se = math.sqrt(s1*s1 + s2*s2)
                z = (v-bv)/se if se > 0 else 0.0
            else:
                se, z = None, None
            verd = None
            if z is not None:
                a = abs(z)
                verd = "real" if a >= 2.5 else ("weak" if a >= 1.5 else "noise")
            m["change"] = {"base_value": round(bv,5), "base_display": fmt.format(bv),
                           "delta": round(v-bv,5),
                           "delta_display": fmt.format(v-bv).replace("+-","-"),
                           "se_noise": round(se,5) if se else None,
                           "delta_z": round(z,2) if z is not None else None,
                           "verdict": verd,
                           # HOW BIG, as opposed to how distinguishable. delta_z answers
                           # "could noise have done this"; delta_sd answers "would anyone
                           # notice". A metric measured almost without error (arm angle,
                           # velocity) clears the noise bar trivially, so delta_sd is the
                           # one that decides whether the change is worth a sentence.
                           "delta_sd": round((v-bv)/sd_obs,2) if sd_obs else None,
                           "size": (None if not sd_obs else
                                    "large" if abs(v-bv)/sd_obs >= 0.8 else
                                    "moderate" if abs(v-bv)/sd_obs >= 0.4 else "small")}
        else:
            m["change"] = None
        out["metrics"].append(m)
    return out

def resolve_span(kind, year, args):
    d,_ = load(kind); blocks = d["blocks"]
    yb = [i for i,b in enumerate(blocks) if b.startswith(str(year))]
    if args.last:
        return yb[-args.last], yb[-1]
    i0 = blocks.index(args.frm) if args.frm else yb[0]
    i1 = blocks.index(args.to)  if args.to  else yb[-1]
    return i0, i1

def call_api(packet, model="claude-sonnet-4-5", max_tokens=1400):
    import urllib.request
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key: raise SystemExit("set ANTHROPIC_API_KEY (never put it in client-side JS)")
    system = open(PROMPT).read()
    body = json.dumps({
        "model": model, "max_tokens": max_tokens,
        # the guardrail prompt is long and identical on every call -- cache it.
        "system": [{"type":"text","text":system,"cache_control":{"type":"ephemeral"}}],
        "messages":[{"role":"user","content":json.dumps(packet, separators=(",",":"))}],
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
        headers={"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"})
    with urllib.request.urlopen(req) as r:
        j = json.load(r)
    return "".join(c["text"] for c in j["content"] if c["type"]=="text"), j.get("usage",{})

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["bat","pit"], default="bat")
    ap.add_argument("--player", required=True)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--from", dest="frm"); ap.add_argument("--to")
    ap.add_argument("--last", type=int, help="last N half-month blocks of the season")
    ap.add_argument("--base", choices=["season","prior"], default="season")
    ap.add_argument("--dry-run", action="store_true", help="print the packet, call nothing")
    ap.add_argument("--model", default="claude-sonnet-4-5")
    a = ap.parse_args()
    i0, i1 = resolve_span(a.kind, a.year, a)
    pk = build(a.kind, a.player, a.year, i0, i1, a.base)
    if a.dry_run:
        print(json.dumps(pk, indent=1)); sys.exit()
    txt, usage = call_api(pk, a.model)
    print(txt); print("\n---", usage, file=sys.stderr)
