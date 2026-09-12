#!/usr/bin/env python3
"""Step 3, specified correctly.

The first attempt regressed (actual wOBA - Marcel prediction) on batted-ball
profile. That residual contains the hitter's overall quality, not just the gap,
so ground-ball rate loaded NEGATIVE — it was picking up "ground-ball hitters are
worse hitters", the opposite of the mechanism. It also used three of the four
batted-ball shares plus BIP rate, which are near-collinear by construction.

Correct version: model the actual wOBA-minus-xwOBA gap on prior ground-ball rate
alone, then add the projection to a Marcel built on xwOBA.
"""
import json, warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
exec(open("/home/claude/predict.py").read().split("# ======================================================================= 1")[0])
rng=np.random.default_rng(23)
raw2=raw.sort_values(["batter","game_year","mon"]).reset_index(drop=True)
SEA=raw2.groupby(["batter","game_year"])[SUMS].sum(); IX=set(SEA.index)
AGE=raw2.groupby(["batter","game_year"])["age"].max()
lgs={int(y):float(g.woba_num.sum()/g.pa.sum()) for y,g in raw2.groupby("game_year")}
def prior(b,y,w=(5,4,3)):
    tot=None
    for k,dy in zip(w,(1,2,3)):
        if (b,y-dy) in IX:
            s=SEA.loc[(b,y-dy)]*k; tot=s if tot is None else tot+s
    return tot
def am(a): return (1+(29-a)*0.006) if a<29 else (1+(29-a)*0.003)
def marcel(t,y,b,R,ux):
    lg=lgs.get(y,.325)
    if t is None or not t.pa: return lg
    return (t["xwoba_num" if ux else "woba_num"]+R*lg)/(t.pa+R)*am(AGE.get((b,y),29))
rows=[]
for (b,y) in IX:
    if y not in (2025,2026): continue
    s=SEA.loc[(b,y)]
    if s.pa<250: continue
    t=prior(b,y)
    if t is None or t.pa<750: continue
    rows.append(dict(b=b,y=y,pa=float(s.pa),act=float(s.woba_num/s.pa),
        own_gap=float((s.woba_num-s.xwoba_num)/s.pa),
        h_gb=float(t.gb/t.n_bbt) if t.n_bbt else np.nan,
        h_gap=float((t.woba_num-t.xwoba_num)/t.pa),
        m_x=marcel(t,y,b,3000,True)))
D=pd.DataFrame(rows); T,S=D[D.y==2025],D[D.y==2026]

print("First: does prior ground-ball rate actually predict this season's gap?")
ok=np.isfinite(T.h_gb)&np.isfinite(T.own_gap)
r=np.corrcoef(T.h_gb[ok],T.own_gap[ok])[0,1]
ok2=np.isfinite(S.h_gb)&np.isfinite(S.own_gap)
r2=np.corrcoef(S.h_gb[ok2],S.own_gap[ok2])[0,1]
rp=np.corrcoef(T.h_gap[np.isfinite(T.h_gap)],T.own_gap[np.isfinite(T.h_gap)])[0,1]
print(f"   corr(prior GB rate, this season's gap):  train {r:+.3f} (n={ok.sum()})   test {r2:+.3f}")
print(f"   corr(prior GAP,     this season's gap):  train {rp:+.3f}   <- the direct version")
print(f"   mean gap {T.own_gap.mean():+.4f}, sd {T.own_gap.std():.4f}")

A=np.c_[np.ones(int(ok.sum())),T.h_gb.values[ok.values]]; w=np.sqrt(T.pa.values[ok.values])
bg,*_=np.linalg.lstsq(A*w[:,None],T.own_gap.values[ok.values]*w,rcond=None)
print(f"\n   gap = {bg[0]:+.5f} {bg[1]:+.5f} * GB_rate")
print(f"   at GB 35% -> {bg[0]+bg[1]*.35:+.4f} ; at GB 55% -> {bg[0]+bg[1]*.55:+.4f}"
      f"  (spread {abs(bg[1])*.20:.4f})")

def wr2_(y,p,ww):
    mu=np.average(y,weights=ww); return 1-np.sum(ww*(y-p)**2)/np.sum(ww*(y-mu)**2)
gb=np.where(np.isfinite(S.h_gb),S.h_gb,np.nanmedian(T.h_gb))
P={"Marcel on xwOBA, R=3000 (step 2)":S.m_x.values,
   "+ gap from prior GB rate":S.m_x.values+(bg[0]+bg[1]*gb),
   "+ gap from prior OWN gap":S.m_x.values+np.where(np.isfinite(S.h_gap),S.h_gap,T.own_gap.mean()),
   "+ league-average gap only":S.m_x.values+T.own_gap.mean()}
def boot(y,P,w,n=4000):
    y,w=np.asarray(y,float),np.asarray(w,float);N=len(y)
    Q={k:np.asarray(v,float) for k,v in P.items()};o={k:[] for k in P}
    for _ in range(n):
        ix=rng.integers(0,N,N);yy,ww=y[ix],w[ix];mu=np.average(yy,weights=ww)
        t=np.sum(ww*(yy-mu)**2)
        for k in Q:o[k].append(1-np.sum(ww*(yy-Q[k][ix])**2)/t)
    return {k:np.array(v) for k,v in o.items()}
B=boot(S.act.values,P,S.pa.values); base=B["Marcel on xwOBA, R=3000 (step 2)"]
print(f"\n{'variant':>36} {'R^2':>8} {'95% CI':>20} {'vs step 2':>11} {'P':>5}")
for k in P:
    v=B[k];d=v-base
    print(f"  {k:>34} {wr2_(S.act,P[k],S.pa):>8.4f} "
          f"[{np.percentile(v,2.5):>+6.3f},{np.percentile(v,97.5):>+6.3f}] {d.mean():>+11.4f} {(d>0).mean():>5.2f}")
Path("/home/claude/out/gapfix.json").write_text(json.dumps(
    {k:dict(r2=float(wr2_(S.act,P[k],S.pa)),vs=float((B[k]-base).mean()),
            p=float(((B[k]-base)>0).mean())) for k in P},indent=1))
print("\nwrote gapfix.json")
