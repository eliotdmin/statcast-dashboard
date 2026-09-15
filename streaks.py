#!/usr/bin/env python3
"""
streaks.py -- within-player change tracking, and the "Don't Chase" engine.

Two things live here because they share one object: a panel of consecutive windows
per player, with each window's stats expressed as a change from that player's own
trailing baseline.

  --part changes    the change log: every sustained within-player move in the data
  --part validate   does input corroboration predict next-window wOBA? (fit 23-25,
                    test once on 2026)
  --part wire       today's Don't Chase board

WINDOW GEOMETRY
  A window is W consecutive half-month blocks (default 2, so roughly a month).
  Windows step by 1 block, so they overlap; the PANEL used for validation uses
  non-overlapping, strictly forward pairs (window t -> window t+W) so that no
  plate appearance appears in both the feature and the target.

WHY A TRAILING BASELINE AND NOT THE SEASON
  profile.py compares a stretch to "the rest of the season", which includes the
  future. That is fine for a retrospective profile and fatal for a forecast. Here
  the baseline is strictly PRIOR blocks in the same season, minimum 80 PA.
"""
import json, math, os, sys, argparse, random
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKS = os.path.join(HERE, "output", "blocks_all.json")

# metric, numerator, denominator, higher_is_better -- the INPUT battery.
# Chosen because every one of them has measured half-season reliability >= .8 and
# is something the hitter does rather than something that happens to him.
INPUTS = [("bat speed","sbs","nbs",1), ("swing length","ssl","nbs",1),
          ("attack angle","saa","naa",1), ("whiff%","whf","sw",0),
          ("chase%","ozsw","oz",0), ("exit velo","sev","nev",1),
          ("hard-hit%","hh","nev",1), ("K%","k","pa",0), ("BB%","bb","pa",1)]

def load():
    d = json.load(open(BLOCKS))["bat"]
    F = {f:i for i,f in enumerate(d["fields"])}
    return d, F

def rel_at(rel, label, n):
    r = rel.get(label)
    if not r or n <= 0: return 0.0
    k = n/r["n0"]; p = r["sb"]
    return max(0.0, min(1.0, k*p/(1+(k-1)*p)))

def acc(row, idxs, nf, blocks=None):
    out = [0.0]*nf
    for i in idxs:
        v = row["b"].get(blocks[i]) if blocks else row["b"].get(str(i))
        if v:
            for j,x in enumerate(v): out[j] += x
    return out

def build_panel(W=2, min_now=60, min_base=80, min_next=60):
    """One record per (player, window) with a strictly-prior baseline and a
    strictly-future target. Returns records plus per-season league means."""
    d, F = load(); blocks = d["blocks"]; rel = d["rel"]
    byyear = {}
    for i,b in enumerate(blocks): byyear.setdefault(b[:4], []).append(i)
    nf = len(d["fields"])
    recs = []
    for r in d["rows"]:
        yb = byyear[str(r["y"])]
        for s in range(len(yb)):
            now = yb[s:s+W]
            nxt = yb[s+W:s+2*W]
            base = yb[:s]
            if len(now) < W or len(nxt) < W or len(base) < 1: continue
            vn = acc(r, now, nf, blocks); vb = acc(r, base, nf, blocks); vx = acc(r, nxt, nf, blocks)
            n, bn, xn_ = vn[F["pa"]], vb[F["pa"]], vx[F["pa"]]
            if n < min_now or bn < min_base or xn_ < min_next: continue
            rec = {"id": r["id"], "name": r["n"], "y": r["y"],
                   "from": blocks[now[0]], "to": blocks[now[-1]],
                   "nxt_from": blocks[nxt[0]], "nxt_to": blocks[nxt[-1]],
                   "pa": n, "pa_base": bn, "pa_next": xn_,
                   "w": vn[F["wn"]]/n, "x": vn[F["xn"]]/n,
                   "w_base": vb[F["wn"]]/bn, "x_base": vb[F["xn"]]/bn,
                   "y_next": vx[F["wn"]]/xn_, "raw": vn, "rawb": vb}
            recs.append(rec)
    return recs, d, F

def zscores(recs, d, F):
    """Attach standardized input LEVELS and input DELTAS.

    Level z:  (value - league mean that season) / league sd that season
    Delta z:  (value - own trailing baseline) / sd of that same quantity in the panel
    Both are signed so that POSITIVE = better for the hitter.
    Each is then combined into one composite with weights sqrt(reliability at n),
    the same weighting the comp engine uses: a dimension you can barely measure
    should barely move the composite.
    """
    rel = d["rel"]
    # league moments per season for each input
    pool = {}
    for lab,num,den,hib in INPUTS:
        for y in {r["y"] for r in recs}:
            xs = [r["raw"][F[num]]/r["raw"][F[den]] for r in recs
                  if r["y"]==y and r["raw"][F[den]]>0]
            if len(xs) > 30:
                pool[(lab,y)] = (st.mean(xs), st.pstdev(xs) or 1.0)
    # sd of the within-player delta, pooled across seasons (one scale for all)
    dsd = {}
    for lab,num,den,hib in INPUTS:
        ds = []
        for r in recs:
            if r["raw"][F[den]]>0 and r["rawb"][F[den]]>0:
                ds.append(r["raw"][F[num]]/r["raw"][F[den]] - r["rawb"][F[num]]/r["rawb"][F[den]])
        dsd[lab] = (st.pstdev(ds) if len(ds)>2 else 0) or 1.0

    for r in recs:
        lv, dv, wt = 0.0, 0.0, 0.0
        r["inputs"] = {}
        for lab,num,den,hib in INPUTS:
            if r["raw"][F[den]] <= 0 or r["rawb"][F[den]] <= 0: continue
            m = pool.get((lab, r["y"]))
            if not m: continue
            v  = r["raw"][F[num]]/r["raw"][F[den]]
            b  = r["rawb"][F[num]]/r["rawb"][F[den]]
            sgn = 1 if hib else -1
            zl = sgn*(v-m[0])/m[1]
            zd = sgn*(v-b)/dsd[lab]
            w  = math.sqrt(rel_at(rel, lab, r["pa"]))
            lv += w*zl; dv += w*zd; wt += w
            r["inputs"][lab] = {"z_level": round(zl,3), "z_delta": round(zd,3),
                                "value": round(v,5), "base": round(b,5),
                                "rel": round(rel_at(rel,lab,r["pa"]),3)}
        r["in_level"] = lv/wt if wt else 0.0
        r["in_delta"] = dv/wt if wt else 0.0
    return recs

# ---------------------------------------------------------------- linear algebra
def ols(X, y, lam=0.0):
    p = len(X[0]); n = len(X)
    A = [[sum(X[i][a]*X[i][b] for i in range(n)) + (lam if a==b and a>0 else 0.0)
          for b in range(p)] for a in range(p)]
    bvec = [sum(X[i][a]*y[i] for i in range(n)) for a in range(p)]
    # gaussian elimination
    M = [row[:]+[bvec[k]] for k,row in enumerate(A)]
    for c in range(p):
        piv = max(range(c,p), key=lambda rr: abs(M[rr][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12: continue
        for rr in range(p):
            if rr==c: continue
            f = M[rr][c]/M[c][c]
            for cc in range(c, p+1): M[rr][cc] -= f*M[c][cc]
    return [M[i][p]/M[i][i] if abs(M[i][i])>1e-12 else 0.0 for i in range(p)]

def r2(pred, y):
    m = sum(y)/len(y)
    ss = sum((a-b)**2 for a,b in zip(pred,y))
    tt = sum((b-m)**2 for b in y)
    return 1 - ss/tt

def paired_boot(pred_a, pred_b, y, B=3000, seed=7):
    """Percentile CI on R2(b) - R2(a), resampling the SAME rows for both models."""
    rnd = random.Random(seed); n = len(y); out = []
    for _ in range(B):
        idx = [rnd.randrange(n) for _ in range(n)]
        ys = [y[i] for i in idx]
        a = [pred_a[i] for i in idx]; b = [pred_b[i] for i in idx]
        out.append(r2(b,ys) - r2(a,ys))
    out.sort()
    return out[int(.025*B)], out[int(.5*B)], out[int(.975*B)]

# ---------------------------------------------------------------- validation
FEATSETS = [
 ("M1  recent wOBA + prior wOBA",            ["w","w_base"]),
 ("M2  + xwOBA (recent and prior)",          ["w","w_base","x","x_base"]),
 ("M3  + input LEVELS (how good the body is)",["w","w_base","x","x_base","in_level"]),
 ("M4  + input DELTA (did the body change)", ["w","w_base","x","x_base","in_level","in_delta"]),
]

def design(recs, cols):
    return [[1.0]+[r[c] for c in cols] for r in recs]

def validate(W=2):
    recs, d, F = build_panel(W)
    recs = zscores(recs, d, F)
    tr = [r for r in recs if r["y"] <= 2025]
    te = [r for r in recs if r["y"] == 2026]
    ytr = [r["y_next"] for r in tr]; yte = [r["y_next"] for r in te]
    print(f"window = {W} half-months (~{15*W} days)")
    print(f"train {len(tr)} player-windows (2023-2025) | test {len(te)} (2026, touched once)")
    print(f"target = wOBA in the NEXT {15*W} days, min 60 PA\n")
    preds = {}
    base_pred = None
    for name, cols in FEATSETS:
        beta = ols(design(tr, cols), ytr)
        p = [sum(b*xx for b,xx in zip(beta, row)) for row in design(te, cols)]
        preds[name] = p
        line = f"{name:<44} R2 = {r2(p,yte):+.4f}"
        if base_pred is not None:
            lo, md, hi = paired_boot(base_pred, p, yte)
            line += f"   delta vs M1 = {md:+.4f}  [{lo:+.4f}, {hi:+.4f}]"
        else:
            base_pred = p
        print(line)
        print("     " + "  ".join(f"{c}={b:+.3f}" for c,b in zip(["int"]+cols, beta)))
    # the actual Don't Chase claim, tested where it is made:
    print("\n--- restricted to STREAKS: |recent wOBA - own prior wOBA| in the top quintile ---")
    gaps = sorted(abs(r["w"]-r["w_base"]) for r in te)
    cut = gaps[int(.8*len(gaps))]
    sub = [i for i,r in enumerate(te) if abs(r["w"]-r["w_base"]) >= cut]
    ys = [yte[i] for i in sub]
    print(f"{len(sub)} of {len(te)} windows, gap >= {cut:.3f}")
    a = [preds[FEATSETS[1][0]][i] for i in sub]   # M2, the expected-stats model
    b = [preds[FEATSETS[3][0]][i] for i in sub]   # M4, + input change
    lo, md, hi = paired_boot(a, b, ys)
    print(f"M2 R2 = {r2(a,ys):+.4f}   M4 R2 = {r2(b,ys):+.4f}   "
          f"delta = {md:+.4f}  [{lo:+.4f}, {hi:+.4f}]")
    # how much of a streak carries: the empirical shrinkage
    hot = [r for i,r in enumerate(te) if r["w"]-r["w_base"] >= cut]
    cold= [r for i,r in enumerate(te) if r["w"]-r["w_base"] <= -cut]
    for lab, g in (("HOT", hot), ("COLD", cold)):
        if not g: continue
        dnow = st.mean(r["w"]-r["w_base"] for r in g)
        dnxt = st.mean(r["y_next"]-r["w_base"] for r in g)
        print(f"{lab:<5} n={len(g):>4}  gap now {dnow:+.3f}  -> next window {dnxt:+.3f}  "
              f"carry = {dnxt/dnow:.1%}")
    return recs, te, preds


def probe():
    """Three follow-ups to the main validation, all pre-specified here in code:
    (a) does the window length change the answer?
    (b) do INPUT changes persist, even though they do not predict wOBA?
    (c) among hot streaks, does body corroboration change how much carries?"""
    print("=== (a) window sweep: R2 predicting the NEXT window's wOBA, 2026 holdout ===")
    for W in (1,2,3,4):
        recs,d,F = build_panel(W); recs = zscores(recs,d,F)
        tr=[r for r in recs if r["y"]<=2025]; te=[r for r in recs if r["y"]==2026]
        if len(te)<80: print(f"W={W}: too few"); continue
        ytr=[r["y_next"] for r in tr]; yte=[r["y_next"] for r in te]
        row=[]
        for name,cols in FEATSETS:
            b=ols(design(tr,cols),ytr)
            p=[sum(bb*xx for bb,xx in zip(b,rr)) for rr in design(te,cols)]
            row.append(r2(p,yte))
        print(f"W={W} (~{15*W}d)  n_test={len(te):>5}  " +
              "  ".join(f"{n.split()[0]}={v:+.4f}" for (n,_),v in zip(FEATSETS,row)))

    print("\n=== (b) do input CHANGES persist into the next window? ===")
    print("    (correlation of delta_t with delta_{t+1} for the same player, 2026)")
    W=2; recs,d,F = build_panel(W); blocks=d["blocks"]; nf=len(d["fields"])
    byyear={}
    for i,b in enumerate(blocks): byyear.setdefault(b[:4],[]).append(i)
    rows={(r["id"],r["y"]):r for r in d["rows"]}
    for lab,num,den,hib in INPUTS:
        xs,ys=[],[]
        for r in d["rows"]:
            if r["y"]!=2026: continue
            yb=byyear["2026"]
            for s in range(1,len(yb)-2*W+1):
                base=yb[:s]; now=yb[s:s+W]; nxt=yb[s+W:s+2*W]
                if len(now)<W or len(nxt)<W: continue
                vb=acc(r,base,nf,blocks); vn=acc(r,now,nf,blocks); vx=acc(r,nxt,nf,blocks)
                if min(vb[F[den]],vn[F[den]],vx[F[den]])<25: continue
                b0=vb[F[num]]/vb[F[den]]
                xs.append(vn[F[num]]/vn[F[den]]-b0); ys.append(vx[F[num]]/vx[F[den]]-b0)
        if len(xs)<100: continue
        mx,my=st.mean(xs),st.mean(ys)
        num_=sum((a-mx)*(b-my) for a,b in zip(xs,ys))
        den_=math.sqrt(sum((a-mx)**2 for a in xs)*sum((b-my)**2 for b in ys))
        print(f"    {lab:<14} r = {num_/den_:+.3f}   (n={len(xs)})")

    print("\n=== (c) hot streaks split by whether the body corroborates ===")
    recs,d,F = build_panel(2); recs=zscores(recs,d,F)
    te=[r for r in recs if r["y"]==2026]
    gaps=sorted(r["w"]-r["w_base"] for r in te); cut=gaps[int(.8*len(gaps))]
    hot=[r for r in te if r["w"]-r["w_base"]>=cut]
    hot.sort(key=lambda r:r["in_delta"])
    half=len(hot)//2
    for lab,g in (("body did NOT corroborate", hot[:half]), ("body DID corroborate", hot[half:])):
        dnow=st.mean(r["w"]-r["w_base"] for r in g); dnxt=st.mean(r["y_next"]-r["w_base"] for r in g)
        print(f"    {lab:<26} n={len(g):>3}  in_delta {st.mean(r['in_delta'] for r in g):+.2f}  "
              f"now {dnow:+.3f} -> next {dnxt:+.3f}  carry {dnxt/dnow:.0%}")


def probe2():
    """How big IS the input-change effect, and is the (c) split real?"""
    recs,d,F = build_panel(2); recs=zscores(recs,d,F)
    tr=[r for r in recs if r["y"]<=2025]; te=[r for r in recs if r["y"]==2026]
    # (d) effect size: wOBA points of next-window performance per 1 sd of input change,
    #     controlling for what the results already said.
    for cols in (["in_delta"], ["w","w_base","x","x_base","in_delta"]):
        b=ols(design(tr,cols),[r["y_next"] for r in tr])
        sd=st.pstdev([r["in_delta"] for r in tr])
        k=cols.index("in_delta")+1
        print(f"    next wOBA ~ {'+'.join(cols):<34} slope on in_delta = {b[k]:+.4f} "
              f"per unit; 1 sd ({sd:.2f}) = {b[k]*sd:+.4f} wOBA")
    # (e) bootstrap the corroborate / don't-corroborate carry gap
    gaps=sorted(r["w"]-r["w_base"] for r in te); cut=gaps[int(.8*len(gaps))]
    hot=sorted([r for r in te if r["w"]-r["w_base"]>=cut], key=lambda r:r["in_delta"])
    half=len(hot)//2; lo_g, hi_g = hot[:half], hot[half:]
    def carry(g):
        dn=sum(r["w"]-r["w_base"] for r in g); dx=sum(r["y_next"]-r["w_base"] for r in g)
        return dx/dn if dn else 0.0
    obs = carry(hi_g)-carry(lo_g)
    rnd=random.Random(11); out=[]
    for _ in range(4000):
        a=[lo_g[rnd.randrange(len(lo_g))] for _ in lo_g]
        b_=[hi_g[rnd.randrange(len(hi_g))] for _ in hi_g]
        out.append(carry(b_)-carry(a))
    out.sort()
    print(f"    carry gap (corroborated - not) = {obs:+.1%}  "
          f"95% CI [{out[100]:+.1%}, {out[3899]:+.1%}]  "
          f"P(gap>0) = {sum(1 for v in out if v>0)/len(out):.2f}")


SIGMA2_WOBA = 0.2258      # per-PA variance of wOBA outcomes (measured in calibrate.py)

def ceiling():
    """The most R2 ANY model could get at this target length, given that the target
    itself is a noisy measurement of the thing being predicted.

        var(observed_next) = var(true talent) + E[sigma^2 / pa_next]
        R2_max             = var(true) / var(observed)

    Without this number, 'R2 = 0.034' is unreadable."""
    recs,d,F = build_panel(2)
    te=[r for r in recs if r["y"]==2026]
    vo = st.pvariance([r["y_next"] for r in te])
    vn = st.mean(SIGMA2_WOBA/r["pa_next"] for r in te)
    vt = max(vo-vn, 0)
    print(f"    target windows: mean {st.mean(r['pa_next'] for r in te):.0f} PA")
    print(f"    var(observed next wOBA) = {vo:.5f}")
    print(f"    var(noise) = E[sigma^2/PA] = {vn:.5f}   (sigma^2 = {SIGMA2_WOBA})")
    print(f"    var(true talent)          = {vt:.5f}")
    print(f"    CEILING R2 = {vt/vo:.4f}  -- no model can beat this")
    print(f"    M2 achieved 0.0335 = {0.0335/(vt/vo):.0%} of everything available")

def wire(topn=12):
    """Today's board. Every streak, with how much of it the model expects to carry."""
    recs,d,F = build_panel(2); recs=zscores(recs,d,F)
    tr=[r for r in recs if r["y"]<=2025]
    cols=["w","w_base","x","x_base"]
    beta=ols(design(tr,cols),[r["y_next"] for r in tr])

    # the most recent window that exists for 2026, per player, with no future needed
    blocks=d["blocks"]; nf=len(d["fields"])
    yb=[i for i,b in enumerate(blocks) if b.startswith("2026")]
    now=yb[-2:]; base=yb[:-2]
    board=[]
    rel=d["rel"]
    for r in d["rows"]:
        if r["y"]!=2026: continue
        vn=acc(r,now,nf,blocks); vb=acc(r,base,nf,blocks)
        n,bn=vn[F["pa"]],vb[F["pa"]]
        if n<50 or bn<150: continue
        rec={"w":vn[F["wn"]]/n,"x":vn[F["xn"]]/n,
             "w_base":vb[F["wn"]]/bn,"x_base":vb[F["xn"]]/bn,
             "pa":n,"pa_base":bn,"raw":vn,"rawb":vb,"y":2026,
             "id":r["id"],"name":r["n"]}
        board.append(rec)
    board=zscores(board,d,F)
    for b in board:
        pred=sum(bb*xx for bb,xx in zip(beta,[1.0]+[b[c] for c in cols]))
        b["pred_next"]=pred
        gap=b["w"]-b["w_base"]
        b["gap"]=gap
        b["carry"]=(pred-b["w_base"])/gap if abs(gap)>1e-6 else 0.0
    board.sort(key=lambda b:-abs(b["gap"]))
    print(f"    window {blocks[now[0]]}..{blocks[now[-1]]}, {len(board)} qualified hitters\n")
    print(f"    {'player':<22}{'PA':>4}{'wOBA':>7}{'prior':>7}{'gap':>8}"
          f"{'expect':>8}{'carry':>7}  body change (|z|>1, persists)")
    for b in board[:topn]:
        moves=[f"{k} {v['z_delta']:+.1f}" for k,v in sorted(b["inputs"].items(),
               key=lambda kv:-abs(kv[1]['z_delta'])) if abs(v["z_delta"])>=1.0][:3]
        print(f"    {b['name']:<22}{b['pa']:>4.0f}{b['w']:>7.3f}{b['w_base']:>7.3f}"
              f"{b['gap']:>+8.3f}{b['pred_next']-b['w_base']:>+8.3f}{b['carry']:>6.0%}  "
              + ", ".join(moves))
    json.dump([{k:(round(v,4) if isinstance(v,float) else v)
                for k,v in b.items() if k not in ("raw","rawb")} for b in board],
              open(os.path.join(HERE,"output","dontchase.json"),"w"))
    print(f"\n    wrote output/dontchase.json ({len(board)} rows)")


def changes(year=2026, W=2, zmin=2.0, topn=25):
    """The change log. For every player, every window, every input metric:
    the move against that player's own PRIOR blocks, in units of the noise the
    two sample sizes would produce on their own.

        delta   = rate(now) - rate(prior)
        se      = sqrt( var_noise(n_now) + var_noise(n_prior) )
        z       = delta / se

    var_noise at sample n comes from the reliability decomposition:
        var_noise(n) = var_observed_league(n) * (1 - rho(n))
    and is rescaled between sample sizes as 1/n, which is what makes it noise.

    A move is CONFIRMED when the next window holds at least half of it -- the
    empirical persistence of these deltas is r ~ 0.4-0.58 (streaks.py --part probe),
    so a one-window spike is real information but a held move is much stronger.
    """
    d,F = load(); blocks=d["blocks"]; rel=d["rel"]; nf=len(d["fields"])
    yb=[i for i,b in enumerate(blocks) if b.startswith(str(year))]
    # league spread of each rate at a reference window, for the noise scale
    out=[]
    for r in d["rows"]:
        if r["y"]!=year: continue
        for s in range(2, len(yb)-W+1):
            now=yb[s:s+W]; base=yb[:s]; nxt=yb[s+W:s+2*W]
            vn=acc(r,now,nf,blocks); vb=acc(r,base,nf,blocks)
            vx=acc(r,nxt,nf,blocks) if len(nxt)==W else None
            if vn[F["pa"]]<50 or vb[F["pa"]]<120: continue
            for lab,num,den,hib in INPUTS:
                dn,db=vn[F[den]],vb[F[den]]
                if dn<20 or db<50: continue
                v=vn[F[num]]/dn; b0=vb[F[num]]/db
                # league sd of this rate at the CURRENT window size
                peers=[]
                for q in d["rows"]:
                    if q["y"]!=year: continue
                    pv=acc(q,now,nf,blocks)
                    if pv[F[den]]>=20: peers.append(pv[F[num]]/pv[F[den]])
                if len(peers)<40: continue
                sd=st.pstdev(peers) or 1e-9
                rho=rel_at(rel,lab,vn[F["pa"]]); rho_b=rel_at(rel,lab,vb[F["pa"]])
                vt=(sd**2)*rho
                s1=math.sqrt(max(1e-12,(sd**2)-vt))
                s2=math.sqrt(max(1e-12,((sd**2)-vt)*(vn[F["pa"]]/vb[F["pa"]])))
                se=math.sqrt(s1*s1+s2*s2)
                z=(v-b0)/se
                if abs(z)<zmin: continue
                held=None
                if vx and vx[F[den]]>=20:
                    held=(vx[F[num]]/vx[F[den]]-b0)/(v-b0) if abs(v-b0)>1e-9 else None
                out.append({"player":r["n"],"id":r["id"],"metric":lab,
                    "from":blocks[now[0]],"to":blocks[now[-1]],
                    "value":round(v,4),"base":round(b0,4),"delta":round(v-b0,4),
                    "z":round(z,2),"sd_units":round((v-b0)/sd,2),
                    "rel_now":round(rho,3),"held":round(held,2) if held is not None else None,
                    "confirmed": bool(held is not None and held>=0.5)})
    out.sort(key=lambda o:-abs(o["z"]))
    json.dump(out, open(os.path.join(HERE,"output","changes.json"),"w"))
    conf=[o for o in out if o["confirmed"]]
    print(f"    {len(out)} moves past |z| >= {zmin} in {year}; "
          f"{len(conf)} confirmed by the following window ({len(conf)/max(1,len([o for o in out if o['held'] is not None])):.0%} of those testable)")
    print(f"\n    {'player':<22}{'metric':<14}{'window':<20}{'base':>9}{'now':>9}{'z':>7}{'sd':>6}{'held':>7}")
    for o in out[:topn]:
        win=f"{o['from'][5:]}..{o['to'][5:]}"
        print(f"    {o['player']:<22}{o['metric']:<14}{win:<20}"
              f"{o['base']:>9.3f}{o['value']:>9.3f}{o['z']:>7.1f}{o['sd_units']:>6.1f}"
              f"{(f'{o[chr(39)+chr(39)] if False else o[chr(104)+chr(101)+chr(108)+chr(100)]:.0%}' if o['held'] is not None else '   --'):>7}")
    print(f"\n    wrote output/changes.json")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="validate")
    ap.add_argument("--window", type=int, default=2)
    a = ap.parse_args()
    if a.part == "validate": validate(a.window)
    elif a.part == "probe": probe()
    elif a.part == "probe2": probe2()
    elif a.part == "ceiling": ceiling()
    elif a.part == "wire": wire()
    elif a.part == "changes": changes()
