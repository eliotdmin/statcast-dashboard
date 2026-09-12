#!/usr/bin/env python3
"""Season level, redone. marcel2.py section A leaked: hist_sums(..., thru=99)
included the season being forecast, which is why Marcel 'scored' R^2=0.575 and
why tuning drove the regression constant down to 200 (trust the data — of course,
the data was the answer). Prior seasons only here, and bootstrapped.
"""
import json, math, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("/home/claude/predict.py").read().split("# ======================================================================= 1")[0])
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
rng=np.random.default_rng(11); OUT={}
raw2=raw.sort_values(["batter","game_year","mon"]).reset_index(drop=True)
SEA=raw2.groupby(["batter","game_year"])[SUMS].sum()
AGE=raw2.groupby(["batter","game_year"])["age"].max()
lgs={int(y):float(g.woba_num.sum()/g.pa.sum()) for y,g in raw2.groupby("game_year")}
IX=set(SEA.index)

def derive(s):
    r=lambda a,b:(s[a]/s[b]) if s[b] else np.nan
    return dict(pa=s.pa,woba=r("woba_num","pa"),xwoba=r("xwoba_num","pa"),k=r("k","pa"),
        bb=r("bb","pa"),whiff=r("whiff","sw"),chase=r("ozsw","oz"),zswing=r("izsw","iz"),
        ev=r("sum_ev","n_ev"),la=r("sum_la","n_ev"),hardhit=r("hardhit","n_ev"),
        barrel=r("barrel","n_ev"),bat_speed=r("sum_bs","n_bs"),swing_len=r("sum_sl","n_bs"),
        attack_angle=r("sum_aa","n_aa"),tilt=r("sum_tilt","n_aa"),gb=r("gb","n_bbt"),
        ld=r("ld","n_bbt"),pull=r("pull","n_spray"))

def prior(b,y,w=(5,4,3)):
    """PRIOR SEASONS ONLY. Never touches season y."""
    tot=None
    for k,dy in zip(w,(1,2,3)):
        key=(b,y-dy)
        if key in IX:
            s=SEA.loc[key]*k; tot=s if tot is None else tot+s
    return tot

def am(a): return (1+(29-a)*0.006) if a<29 else (1+(29-a)*0.003)

def marcel(b,y,R,ux=False,age=True):
    t=prior(b,y); lg=lgs.get(y,.325)
    if t is None or not t.pa: return lg
    p=(t["xwoba_num" if ux else "woba_num"]+R*lg)/(t.pa+R)
    return p*am(AGE.get((b,y),29)) if age else p

def boot(y,preds,w,n=4000):
    y,w=np.asarray(y,float),np.asarray(w,float); N=len(y)
    P={k:np.asarray(v,float) for k,v in preds.items()}; out={k:[] for k in preds}
    for _ in range(n):
        ix=rng.integers(0,N,N); yy,ww=y[ix],w[ix]
        mu=np.average(yy,weights=ww); tot=np.sum(ww*(yy-mu)**2)
        for k in P: out[k].append(1-np.sum(ww*(yy-P[k][ix])**2)/tot)
    return {k:np.array(v) for k,v in out.items()}

hr("SEASON LEVEL, NO LEAKAGE — prior seasons only")
FE=["woba","xwoba","k","bb","whiff","chase","zswing","ev","la","hardhit","barrel",
    "bat_speed","swing_len","attack_angle","tilt","gb","ld","pull","pa"]
rows=[]
for (b,y) in IX:
    if y not in (2025,2026): continue
    s=derive(SEA.loc[(b,y)])
    if s["pa"]<250: continue
    t=prior(b,y)
    if t is None or t.pa<250*3: continue
    d=derive(t)
    rows.append(dict(b=b,y=y,act=s["woba"],pa=s["pa"],age=AGE.get((b,y),29),
                     **{f"h_{k}":d[k] for k in FE}))
A=pd.DataFrame(rows); T,S=A[A.y==2025],A[A.y==2026]
print(f"  tune/train on {len(T)} hitters entering 2025, test on {len(S)} entering 2026")
best=None
for R in (200,400,600,900,1200,1600,2200,3000):
    for ux in (False,True):
        sc=wr2(T.act,[marcel(r.b,r.y,R,ux) for r in T.itertuples()],T.pa)
        if best is None or sc>best[0]: best=(sc,R,ux)
print(f"  tuned on training year: R={best[1]}, {'xwOBA' if best[2] else 'wOBA'} history (train R^2 {best[0]:.4f})")
P={}
P["MARCEL, classic R=1200"]=[marcel(r.b,r.y,1200) for r in S.itertuples()]
P["MARCEL, tuned"]=[marcel(r.b,r.y,best[1],best[2]) for r in S.itertuples()]
P["MARCEL, no age bump"]=[marcel(r.b,r.y,best[1],best[2],age=False) for r in S.itertuples()]
for lab,col in (("weighted past wOBA, shrunk","h_woba"),("weighted past xwOBA, shrunk","h_xwoba")):
    pr,_=fit_ols(T[[col]].values,T.act.values,T.pa.values,S[[col]].values); P[lab]=pr
HC=[f"h_{k}" for k in FE]+["age"]
imp=SimpleImputer(strategy="median").fit(T[HC].values.astype(float))
m=HistGradientBoostingRegressor(max_iter=300,learning_rate=.04,max_depth=3,
    min_samples_leaf=15,l2_regularization=1.,random_state=7).fit(
    imp.transform(T[HC].values.astype(float)),T.act.values,sample_weight=T.pa.values.astype(float))
P["Statcast history, 20 features (GBM)"]=m.predict(imp.transform(S[HC].values.astype(float)))
B=boot(S.act.values,P,S.pa.values)
print(f"\n  {'forecaster':>38} {'R^2':>8} {'95% interval':>20}")
for k in P:
    v=B[k]; print(f"  {k:>38} {wr2(S.act,P[k],S.pa):>8.4f} [{np.percentile(v,2.5):>+7.3f},{np.percentile(v,97.5):>+7.3f}]")
print("\n  gaps vs tuned Marcel:")
for k in P:
    if k=="MARCEL, tuned": continue
    d=B[k]-B["MARCEL, tuned"]
    print(f"    {k:>38} {d.mean():+.4f} [{np.percentile(d,2.5):+.4f},{np.percentile(d,97.5):+.4f}] P(>0)={(d>0).mean():.2f}")
OUT["season"]={k:dict(r2=float(wr2(S.act,P[k],S.pa)),lo=float(np.percentile(B[k],2.5)),
                      hi=float(np.percentile(B[k],97.5))) for k in P}
OUT["season_gaps"]={k:dict(mean=float((B[k]-B["MARCEL, tuned"]).mean()),
    lo=float(np.percentile(B[k]-B["MARCEL, tuned"],2.5)),
    hi=float(np.percentile(B[k]-B["MARCEL, tuned"],97.5)),
    p=float(((B[k]-B["MARCEL, tuned"])>0).mean())) for k in P if k!="MARCEL, tuned"}
print(f"\n  {'sorted by':>38} {'bottom fifth':>13} {'top fifth':>11} {'spread':>9}")
S2=S.copy()
for k,v in P.items(): S2[k]=v
for k in P:
    s=S2.sort_values(k); n=len(s); lo,hi=s.iloc[:n//5],s.iloc[-(n//5):]
    a=float(np.average(lo.act,weights=lo.pa)); b2=float(np.average(hi.act,weights=hi.pa))
    print(f"  {k:>38} {a:>13.4f} {b2:>11.4f} {b2-a:>+9.4f}")
    OUT.setdefault("sort",{})[k]=dict(lo=a,hi=b2,spread=b2-a)
Path("/home/claude/out/marcel3.json").write_text(json.dumps(OUT,indent=1,default=float))
print("\nwrote /home/claude/out/marcel3.json")
