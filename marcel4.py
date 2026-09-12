#!/usr/bin/env python3
"""Where, if anywhere, does Statcast beat Marcel?

Marcel cannot see a change. A hitter who just added three mph of bat speed looks
identical to a hitter who did not. Averaged over everyone that blind spot is
tiny, because most hitters change little in a month. The steelman is that the
value is concentrated in two segments:

  1. hitters with little or no history, where Marcel has nothing to average
  2. hitters whose underlying measurements just moved a lot

Predicted directions, recorded before the split: the model beats Marcel in both.
"""
import json, math, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("/home/claude/predict.py").read().split("# ======================================================================= 1")[0])
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
rng=np.random.default_rng(3); OUT={}
raw2=raw.sort_values(["batter","game_year","mon"]).reset_index(drop=True)
CUM=raw2.groupby(["batter","game_year"])[SUMS].cumsum()
cum_ix={(int(r.batter),int(r.game_year),int(r.mon)):i for i,r in enumerate(raw2.itertuples())}
SEA=raw2.groupby(["batter","game_year"])[SUMS].sum(); IX=set(SEA.index)
AGE=raw2.groupby(["batter","game_year"])["age"].max()
lgs={int(y):float(g.woba_num.sum()/g.pa.sum()) for y,g in raw2.groupby("game_year")}
def derive(s):
    r=lambda a,b:(s[a]/s[b]) if s[b] else np.nan
    return dict(pa=s.pa,woba=r("woba_num","pa"),xwoba=r("xwoba_num","pa"),k=r("k","pa"),
        bb=r("bb","pa"),whiff=r("whiff","sw"),chase=r("ozsw","oz"),zswing=r("izsw","iz"),
        ev=r("sum_ev","n_ev"),la=r("sum_la","n_ev"),hardhit=r("hardhit","n_ev"),
        barrel=r("barrel","n_ev"),bat_speed=r("sum_bs","n_bs"),swing_len=r("sum_sl","n_bs"),
        attack_angle=r("sum_aa","n_aa"),tilt=r("sum_tilt","n_aa"),gb=r("gb","n_bbt"),
        ld=r("ld","n_bbt"),pull=r("pull","n_spray"))
def hist_sums(b,y,thru,w=(5,4,3,2)):
    tot=None; i=cum_ix.get((b,y,thru))
    if i is None:
        for mm in range(thru-1,2,-1):
            i=cum_ix.get((b,y,mm))
            if i is not None: break
    if i is not None: tot=CUM.iloc[i]*w[0]
    for k,dy in zip(w[1:],(1,2,3)):
        if (b,y-dy) in IX:
            s=SEA.loc[(b,y-dy)]*k; tot=s if tot is None else tot+s
    return tot
def prior_pa(b,y,thru):
    p=0.0
    i=cum_ix.get((b,y,thru))
    if i is not None: p+=float(CUM.iloc[i].pa)
    for dy in (1,2,3):
        if (b,y-dy) in IX: p+=float(SEA.loc[(b,y-dy)].pa)
    return p
def am(a): return (1+(29-a)*0.006) if a<29 else (1+(29-a)*0.003)
def marcel(b,y,thru,R=1200,ux=True):
    t=hist_sums(b,y,thru); lg=lgs.get(y,.325)
    if t is None or not t.pa: return lg
    return (t["xwoba_num" if ux else "woba_num"]+R*lg)/(t.pa+R)*am(AGE.get((b,y),29))

D=build(1,40)
HF=["woba","xwoba","k","bb","whiff","chase","zswing","ev","la","hardhit","barrel",
    "bat_speed","swing_len","attack_angle","tilt","gb","ld","pull","pa"]
H=[];MAR=[];PP=[]
for r in D.itertuples():
    b,y,st=int(r.batter),int(r.year),int(r.start)
    t=hist_sums(b,y,st); d=derive(t) if t is not None else {}
    H.append({f"h_{k}":d.get(k,np.nan) for k in HF})
    MAR.append(marcel(b,y,st)); PP.append(prior_pa(b,y,st))
D=pd.concat([D.reset_index(drop=True),pd.DataFrame(H)],axis=1)
D["mar"]=MAR; D["hist_pa"]=PP
# how much did this month's measurements move off the hitter's own history?
for k in ("bat_speed","ev","whiff","k"):
    D[f"d_{k}"]=D[f"x_{k}"]-D[f"h_{k}"]
D["move"]=(D.d_bat_speed.abs()/1.0).fillna(0)+(D.d_ev.abs()/3.0).fillna(0)
tr,te=D[D.year<=2025].copy(),D[D.year==2026].copy()
BASE=["x_woba","x_xwoba"];QUAL=["x_ev","x_la","x_hardhit","x_barrel","x_sweet","x_sd_ev","x_sd_la","x_distance"]
DISC=["x_k","x_bb","x_swing","x_zswing","x_chase","x_whiff","x_fpsw","x_tksw"]
BATT=["x_gb","x_fb","x_ld","x_pop","x_pull","x_spray","x_sd_spray","x_bip_rate"]
SWG=["x_bat_speed","x_swing_len","x_attack_angle","x_attack_dir","x_tilt","x_contact_depth",
     "x_contact_x","x_sd_attack_angle","x_sd_bat_speed"]
CTX=["x_pa","x_home_share","x_if_strat","x_if_shade","x_of_strat","x_fb_seen","x_brk_seen","x_pvelo","age","stand"]
SPD=["x_gb_single","x_gidp","x_triple"]
NOW=[c for c in BASE+QUAL+DISC+BATT+SPD+CTX+SWG if c in D.columns]
HIST=[f"h_{k}" for k in HF]
def gbm(cols):
    cols=[c for c in cols if c in D.columns]
    imp=SimpleImputer(strategy="median").fit(tr[cols].values.astype(float))
    m=HistGradientBoostingRegressor(max_iter=350,learning_rate=.04,max_depth=3,
        min_samples_leaf=40,l2_regularization=1.,random_state=7)
    m.fit(imp.transform(tr[cols].values.astype(float)),tr.y_woba.values,
          sample_weight=tr.y_pa.values.astype(float))
    return m.predict(imp.transform(te[cols].values.astype(float)))
te["model"]=gbm(NOW+HIST+["mar"])
def R2(d,col):
    y,w,p=d.y_woba.values,d.y_pa.values.astype(float),d[col].values
    mu=np.average(y,weights=w)
    return 1-np.sum(w*(y-p)**2)/np.sum(w*(y-mu)**2)
def bootgap(d,a,b,n=3000):
    y,w=d.y_woba.values,d.y_pa.values.astype(float);A=d[a].values;B=d[b].values;N=len(y);g=[]
    for _ in range(n):
        ix=rng.integers(0,N,N);yy,ww=y[ix],w[ix];mu=np.average(yy,weights=ww)
        tot=np.sum(ww*(yy-mu)**2)
        g.append((1-np.sum(ww*(yy-A[ix])**2)/tot)-(1-np.sum(ww*(yy-B[ix])**2)/tot))
    g=np.array(g);return g.mean(),np.percentile(g,2.5),np.percentile(g,97.5),(g>0).mean()

hr("SEGMENT 1 — how much prior history does the hitter have?")
print(f"  {'prior PA (weighted)':>22} {'n':>6} {'MARCEL':>9} {'model':>9} {'gap':>9} {'95% interval':>20} {'P(>0)':>7}")
qs=np.quantile(te.hist_pa,[.25,.5,.75])
segs=[("bottom quarter",te.hist_pa<=qs[0]),("second",(te.hist_pa>qs[0])&(te.hist_pa<=qs[1])),
      ("third",(te.hist_pa>qs[1])&(te.hist_pa<=qs[2])),("most history",te.hist_pa>qs[2])]
for lab,m in segs:
    d=te[m]
    if len(d)<80: continue
    g=bootgap(d,"model","mar")
    print(f"  {lab:>22} {len(d):>6} {R2(d,'mar'):>9.4f} {R2(d,'model'):>9.4f} {g[0]:>+9.4f} "
          f"[{g[1]:>+8.4f},{g[2]:>+8.4f}] {g[3]:>7.2f}")
    OUT.setdefault("history",{})[lab]=dict(n=len(d),marcel=float(R2(d,'mar')),
        model=float(R2(d,'model')),gap=float(g[0]),lo=float(g[1]),hi=float(g[2]),p=float(g[3]))

hr("SEGMENT 2 — did the hitter's measurements just move?")
print("  move score = |bat speed off his own history|/1mph + |exit velo off history|/3mph")
print(f"\n  {'movement':>22} {'n':>6} {'MARCEL':>9} {'model':>9} {'gap':>9} {'95% interval':>20} {'P(>0)':>7}")
qm=np.quantile(te.move,[.5,.75,.9])
for lab,m in (("bottom half (steady)",te.move<=qm[0]),("3rd quarter",(te.move>qm[0])&(te.move<=qm[1])),
              ("top decile (big movers)",te.move>qm[2])):
    d=te[m]
    if len(d)<80: continue
    g=bootgap(d,"model","mar")
    print(f"  {lab:>22} {len(d):>6} {R2(d,'mar'):>9.4f} {R2(d,'model'):>9.4f} {g[0]:>+9.4f} "
          f"[{g[1]:>+8.4f},{g[2]:>+8.4f}] {g[3]:>7.2f}")
    OUT.setdefault("movement",{})[lab]=dict(n=len(d),marcel=float(R2(d,'mar')),
        model=float(R2(d,'model')),gap=float(g[0]),lo=float(g[1]),hi=float(g[2]),p=float(g[3]))

hr("OVERALL, for reference")
g=bootgap(te,"model","mar")
print(f"  all {len(te)} test months: Marcel {R2(te,'mar'):.4f}  model {R2(te,'model'):.4f}  "
      f"gap {g[0]:+.4f} [{g[1]:+.4f},{g[2]:+.4f}] P(>0)={g[3]:.2f}")
OUT["overall"]=dict(n=len(te),marcel=float(R2(te,'mar')),model=float(R2(te,'model')),
                    gap=float(g[0]),lo=float(g[1]),hi=float(g[2]),p=float(g[3]))
Path("/home/claude/out/marcel4.json").write_text(json.dumps(OUT,indent=1,default=float))
print("\nwrote /home/claude/out/marcel4.json")
