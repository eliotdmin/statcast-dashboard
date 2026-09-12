#!/usr/bin/env python3
"""Marcel+ : a concrete, tested answer to "how do we project better".

Four changes, each one earned by a finding from this project rather than guessed:

  1. Build the weighted history on xwOBA, not wOBA.        (xwOBA is 0.703
     reliable against wOBA's 0.448, and won every horse race)
  2. Regress harder than classic Marcel.                   (the tuner picks
     R = 3000, not 1200; past-to-future correlation is only 0.40)
  3. Add back the structural gap xwOBA cannot see.         (TODAY: xwOBA
     under-rates ground balls by .023, over-rates popups by .015, and a
     hitter's ground-ball rate is 78% reliable, so the gap is forecastable
     even though the gap itself is not)
  4. Keep the age adjustment.                              (removing it costs
     0.062 of R^2 — it is load-bearing)

Fitted on training years only, evaluated once on the 2026 holdout, bootstrapped.
"""
import json, math, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("/home/claude/predict.py").read().split("# ======================================================================= 1")[0])
rng=np.random.default_rng(23); OUT={}
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
def rate(s,a,b): return float(s[a]/s[b]) if s[b] else np.nan

def marcel(t,y,b,R,ux,age=True):
    lg=lgs.get(y,.325)
    if t is None or not t.pa: return lg
    p=(t["xwoba_num" if ux else "woba_num"]+R*lg)/(t.pa+R)
    return p*am(AGE.get((b,y),29)) if age else p

def boot(y,P,w,n=4000):
    y,w=np.asarray(y,float),np.asarray(w,float);N=len(y)
    Q={k:np.asarray(v,float) for k,v in P.items()};out={k:[] for k in P}
    for _ in range(n):
        ix=rng.integers(0,N,N);yy,ww=y[ix],w[ix];mu=np.average(yy,weights=ww)
        t=np.sum(ww*(yy-mu)**2)
        for k in Q: out[k].append(1-np.sum(ww*(yy-Q[k][ix])**2)/t)
    return {k:np.array(v) for k,v in out.items()}

# ---------------- build season-level frame
rows=[]
for (b,y) in IX:
    if y not in (2025,2026): continue
    s=SEA.loc[(b,y)]
    if s.pa<250: continue
    t=prior(b,y)
    if t is None or t.pa<750: continue
    rows.append(dict(b=b,y=y,pa=float(s.pa),
        act=float(s.woba_num/s.pa),
        h_gb=rate(t,"gb","n_bbt"), h_pop=rate(t,"pop","n_bbt"),
        h_ld=rate(t,"ld","n_bbt"), h_bip=rate(t,"bip","pa"),
        h_tr=rate(t,"triple","n_bbt"),
        h_gap=float((t.woba_num-t.xwoba_num)/t.pa),
        h_woba=float(t.woba_num/t.pa), h_xwoba=float(t.xwoba_num/t.pa),
        hist_pa=float(t.pa), age=float(AGE.get((b,y),29)),
        m_w=marcel(t,y,b,1200,False), t_obj=None))
D=pd.DataFrame(rows)
T,S=D[D.y==2025].copy(),D[D.y==2026].copy()
print(f"train {len(T)} hitters entering 2025 | test {len(S)} entering 2026")

# tune R and basis on training only
best=None
for R in (600,1000,1500,2000,2500,3000,4000,5000):
    for ux in (False,True):
        p=[marcel(prior(r.b,r.y),r.y,r.b,R,ux) for r in T.itertuples()]
        sc=wr2(T.act,p,T.pa)
        if best is None or sc>best[0]: best=(sc,R,ux)
_,R_,UX=best
print(f"tuned on training: R={R_}, basis={'xwOBA' if UX else 'wOBA'}")

# ---- the new piece: forecast the structural gap from prior batted-ball profile
GX=["h_gb","h_pop","h_ld","h_bip","h_tr"]
Xtr=T[GX].values.astype(float); ok=np.isfinite(Xtr).all(1)
A=np.c_[np.ones(ok.sum()),Xtr[ok]]; sw=np.sqrt(T.pa.values[ok])
# target: the gap the hitter ACTUALLY ran in the training season
gtr=(T.act.values-np.array([marcel(prior(r.b,r.y),r.y,r.b,R_,True,age=True) for r in T.itertuples()]))[ok]
bg,*_=np.linalg.lstsq(A*sw[:,None],gtr*sw,rcond=None)
print("\ngap model, fitted on training years only:")
for nm,c in zip(["intercept"]+GX,bg): print(f"   {nm:>10} {c:>+9.5f}")
r2g=1-np.sum(sw**2*(gtr-A@bg)**2)/np.sum(sw**2*(gtr-np.average(gtr,weights=sw**2))**2)
print(f"   in-sample R^2 of the gap model: {r2g:.4f}")

def gapadj(df):
    X=df[GX].values.astype(float)
    X=np.where(np.isfinite(X),X,np.nanmedian(Xtr[ok],axis=0))
    return np.c_[np.ones(len(df)),X]@bg

P={}
P["Marcel, classic (wOBA, R=1200, age)"]=[marcel(prior(r.b,r.y),r.y,r.b,1200,False) for r in S.itertuples()]
P["1. built on xwOBA"]=[marcel(prior(r.b,r.y),r.y,r.b,1200,True) for r in S.itertuples()]
P["2. + regress harder (tuned R)"]=[marcel(prior(r.b,r.y),r.y,r.b,R_,UX) for r in S.itertuples()]
base=np.array(P["2. + regress harder (tuned R)"],float)
P["3. + structural gap adjustment"]=base+gapadj(S)
B=boot(S.act.values,P,S.pa.values)
print(f"\n{'forecaster':>40} {'R^2':>8} {'95% CI':>20} {'vs classic':>12} {'P':>5}")
base_b=B["Marcel, classic (wOBA, R=1200, age)"]
for k in P:
    v=B[k]; d=v-base_b
    print(f"  {k:>38} {wr2(S.act,P[k],S.pa):>8.4f} "
          f"[{np.percentile(v,2.5):>+6.3f},{np.percentile(v,97.5):>+6.3f}] "
          f"{d.mean():>+12.4f} {(d>0).mean():>5.2f}")
    OUT.setdefault("season",{})[k]=dict(r2=float(wr2(S.act,P[k],S.pa)),
        lo=float(np.percentile(v,2.5)),hi=float(np.percentile(v,97.5)),
        vs=float(d.mean()),p=float((d>0).mean()))
d=B["3. + structural gap adjustment"]-B["2. + regress harder (tuned R)"]
print(f"\n  step 3 alone (the new finding) adds {d.mean():+.4f} "
      f"[{np.percentile(d,2.5):+.4f},{np.percentile(d,97.5):+.4f}]  P={(d>0).mean():.2f}")
OUT["step3"]=dict(mean=float(d.mean()),lo=float(np.percentile(d,2.5)),
                  hi=float(np.percentile(d,97.5)),p=float((d>0).mean()))

# sorting test
print(f"\n{'sorted by':>40} {'bottom fifth':>13} {'top fifth':>11} {'spread':>9}")
S2=S.copy()
for k,v in P.items(): S2[k]=v
for k in P:
    s=S2.sort_values(k);n=len(s);lo,hi=s.iloc[:n//5],s.iloc[-(n//5):]
    a=float(np.average(lo.act,weights=lo.pa));b2=float(np.average(hi.act,weights=hi.pa))
    print(f"  {k:>38} {a:>13.4f} {b2:>11.4f} {b2-a:>+9.4f}")
    OUT.setdefault("sort",{})[k]=dict(spread=b2-a)
Path("/home/claude/out/marcel_plus.json").write_text(json.dumps(OUT,indent=1,default=float))
print("\nwrote marcel_plus.json")
