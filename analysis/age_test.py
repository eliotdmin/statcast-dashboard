#!/usr/bin/env python3
"""Is it AGE or is it LACK OF HISTORY?

marcel4.py found the model beats Marcel in the bottom quartile of prior playing
time. That is not the same claim as "it works for young players": a 33-year-old
returning from two lost seasons also has little history, and a 24-year-old who
debuted at 21 has plenty. Age and history correlate but are distinct, so test
both, and then both at once.
"""
import json, warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
exec(open("/home/claude/predict.py").read().split("# ======================================================================= 1")[0])
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
rng=np.random.default_rng(5); OUT={}
raw2=raw.sort_values(["batter","game_year","mon"]).reset_index(drop=True)
CUM=raw2.groupby(["batter","game_year"])[SUMS].cumsum()
cix={(int(r.batter),int(r.game_year),int(r.mon)):i for i,r in enumerate(raw2.itertuples())}
SEA=raw2.groupby(["batter","game_year"])[SUMS].sum(); IX=set(SEA.index)
AGE=raw2.groupby(["batter","game_year"])["age"].max()
lgs={int(y):float(g.woba_num.sum()/g.pa.sum()) for y,g in raw2.groupby("game_year")}
def hs(b,y,thru,w=(5,4,3,2)):
    tot=None;i=cix.get((b,y,thru))
    if i is None:
        for mm in range(thru-1,2,-1):
            i=cix.get((b,y,mm))
            if i is not None:break
    if i is not None: tot=CUM.iloc[i]*w[0]
    for k,dy in zip(w[1:],(1,2,3)):
        if (b,y-dy) in IX:
            s=SEA.loc[(b,y-dy)]*k; tot=s if tot is None else tot+s
    return tot
def ppa(b,y,thru):
    p=0.0;i=cix.get((b,y,thru))
    if i is not None:p+=float(CUM.iloc[i].pa)
    for dy in(1,2,3):
        if (b,y-dy) in IX:p+=float(SEA.loc[(b,y-dy)].pa)
    return p
def am(a):return (1+(29-a)*0.006) if a<29 else (1+(29-a)*0.003)
def marcel(b,y,thru,R=1200):
    t=hs(b,y,thru);lg=lgs.get(y,.325)
    if t is None or not t.pa:return lg
    return (t["xwoba_num"]+R*lg)/(t.pa+R)*am(AGE.get((b,y),29))
def dv(s):
    r=lambda a,b:(s[a]/s[b]) if s[b] else np.nan
    return dict(pa=s.pa,woba=r("woba_num","pa"),xwoba=r("xwoba_num","pa"),k=r("k","pa"),
        bb=r("bb","pa"),whiff=r("whiff","sw"),chase=r("ozsw","oz"),zswing=r("izsw","iz"),
        ev=r("sum_ev","n_ev"),la=r("sum_la","n_ev"),hardhit=r("hardhit","n_ev"),
        barrel=r("barrel","n_ev"),bat_speed=r("sum_bs","n_bs"),swing_len=r("sum_sl","n_bs"),
        attack_angle=r("sum_aa","n_aa"),tilt=r("sum_tilt","n_aa"),gb=r("gb","n_bbt"),
        ld=r("ld","n_bbt"),pull=r("pull","n_spray"))
D=build(1,40)
HF=["woba","xwoba","k","bb","whiff","chase","zswing","ev","la","hardhit","barrel",
    "bat_speed","swing_len","attack_angle","tilt","gb","ld","pull","pa"]
H=[];M=[];P=[]
for r in D.itertuples():
    b,y,st=int(r.batter),int(r.year),int(r.start)
    t=hs(b,y,st);d=dv(t) if t is not None else {}
    H.append({f"h_{k}":d.get(k,np.nan) for k in HF});M.append(marcel(b,y,st));P.append(ppa(b,y,st))
D=pd.concat([D.reset_index(drop=True),pd.DataFrame(H)],axis=1);D["mar"]=M;D["hist_pa"]=P
tr,te=D[D.year<=2025].copy(),D[D.year==2026].copy()
BASE=["x_woba","x_xwoba"];QUAL=["x_ev","x_la","x_hardhit","x_barrel","x_sweet","x_sd_ev","x_sd_la","x_distance"]
DISC=["x_k","x_bb","x_swing","x_zswing","x_chase","x_whiff","x_fpsw","x_tksw"]
BATT=["x_gb","x_fb","x_ld","x_pop","x_pull","x_spray","x_sd_spray","x_bip_rate"]
SWG=["x_bat_speed","x_swing_len","x_attack_angle","x_attack_dir","x_tilt","x_contact_depth",
     "x_contact_x","x_sd_attack_angle","x_sd_bat_speed"]
CTX=["x_pa","x_home_share","x_if_strat","x_if_shade","x_of_strat","x_fb_seen","x_brk_seen","x_pvelo","age","stand"]
SPD=["x_gb_single","x_gidp","x_triple"]
NOW=[c for c in BASE+QUAL+DISC+BATT+SPD+CTX+SWG if c in D.columns];HIST=[f"h_{k}" for k in HF]
cols=[c for c in NOW+HIST+["mar"] if c in D.columns]
imp=SimpleImputer(strategy="median").fit(tr[cols].values.astype(float))
m=HistGradientBoostingRegressor(max_iter=350,learning_rate=.04,max_depth=3,min_samples_leaf=40,
    l2_regularization=1.,random_state=7).fit(imp.transform(tr[cols].values.astype(float)),
    tr.y_woba.values,sample_weight=tr.y_pa.values.astype(float))
te["model"]=m.predict(imp.transform(te[cols].values.astype(float)))
# xwOBA alone, calibrated on train
px,_=fit_ols(tr[["x_xwoba"]].values,tr.y_woba.values,tr.y_pa.values,te[["x_xwoba"]].values)
te["xw"]=px
def R2(d,c):
    y,w,p=d.y_woba.values,d.y_pa.values.astype(float),d[c].values
    mu=np.average(y,weights=w);return 1-np.sum(w*(y-p)**2)/np.sum(w*(y-mu)**2)
def gap(d,a,b,n=3000):
    y,w=d.y_woba.values,d.y_pa.values.astype(float);A=d[a].values;B=d[b].values;N=len(y);g=[]
    for _ in range(n):
        ix=rng.integers(0,N,N);yy,ww=y[ix],w[ix];mu=np.average(yy,weights=ww);t=np.sum(ww*(yy-mu)**2)
        g.append((1-np.sum(ww*(yy-A[ix])**2)/t)-(1-np.sum(ww*(yy-B[ix])**2)/t))
    g=np.array(g);return g.mean(),np.percentile(g,2.5),np.percentile(g,97.5),(g>0).mean()

print("  correlation between age and prior playing time:",
      f"{np.corrcoef(te.age,te.hist_pa)[0,1]:+.3f}")
hr("BY AGE")
print(f"  {'age':>14} {'n':>5} {'MARCEL':>8} {'xwOBA':>8} {'model':>8} {'model-Marcel':>13} {'95%':>20} {'P':>5}")
for lab,m_ in (("22-25",te.age<=25),("26-28",(te.age>25)&(te.age<=28)),
               ("29-31",(te.age>28)&(te.age<=31)),("32+",te.age>31)):
    d=te[m_]
    if len(d)<70: continue
    g=gap(d,"model","mar")
    print(f"  {lab:>14} {len(d):>5} {R2(d,'mar'):>8.4f} {R2(d,'xw'):>8.4f} {R2(d,'model'):>8.4f} "
          f"{g[0]:>+13.4f} [{g[1]:>+8.4f},{g[2]:>+8.4f}] {g[3]:>5.2f}")
    OUT.setdefault("age",{})[lab]=dict(n=len(d),marcel=R2(d,'mar'),xwoba=R2(d,'xw'),
        model=R2(d,'model'),gap=g[0],lo=g[1],hi=g[2],p=g[3])
hr("BY PRIOR PLAYING TIME (the original split, for reference)")
q=np.quantile(te.hist_pa,[.25,.5,.75])
print(f"  {'prior PA':>14} {'n':>5} {'MARCEL':>8} {'xwOBA':>8} {'model':>8} {'model-Marcel':>13} {'95%':>20} {'P':>5}")
for lab,m_ in (("Q1 least",te.hist_pa<=q[0]),("Q2",(te.hist_pa>q[0])&(te.hist_pa<=q[1])),
               ("Q3",(te.hist_pa>q[1])&(te.hist_pa<=q[2])),("Q4 most",te.hist_pa>q[2])):
    d=te[m_];g=gap(d,"model","mar")
    print(f"  {lab:>14} {len(d):>5} {R2(d,'mar'):>8.4f} {R2(d,'xw'):>8.4f} {R2(d,'model'):>8.4f} "
          f"{g[0]:>+13.4f} [{g[1]:>+8.4f},{g[2]:>+8.4f}] {g[3]:>5.2f}")
    OUT.setdefault("hist",{})[lab]=dict(n=len(d),marcel=R2(d,'mar'),xwoba=R2(d,'xw'),
        model=R2(d,'model'),gap=g[0],lo=g[1],hi=g[2],p=g[3])
hr("BOTH AT ONCE — which one is actually driving it")
print(f"  {'cell':>26} {'n':>5} {'MARCEL':>8} {'model':>8} {'gap':>9}")
med=np.median(te.hist_pa)
for alab,am_ in (("young (<=27)",te.age<=27),("older (>27)",te.age>27)):
    for hlab,hm in (("thin history",te.hist_pa<=med),("thick history",te.hist_pa>med)):
        d=te[am_&hm]
        if len(d)<60: continue
        print(f"  {alab+', '+hlab:>26} {len(d):>5} {R2(d,'mar'):>8.4f} {R2(d,'model'):>8.4f} "
              f"{R2(d,'model')-R2(d,'mar'):>+9.4f}")
        OUT.setdefault("cross",{})[f"{alab}|{hlab}"]=dict(n=len(d),marcel=R2(d,'mar'),
            model=R2(d,'model'),gap=R2(d,'model')-R2(d,'mar'))
Path("/home/claude/out/age_test.json").write_text(json.dumps(OUT,indent=1,default=float))
print("\nwrote age_test.json")
