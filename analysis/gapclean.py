import json, math, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
exec(open("/home/claude/predict.py").read().split("# ======================================================================= 1")[0])
OUTJ={}
hr("THE GAP, WITH THE CIRCULARITY REMOVED")
print("""  gb_single (ground-ball single rate) and triple rate were the top 'explainers'
  of wOBA minus xwOBA. But both are OUTCOMES: a ground ball that finds a hole is
  simultaneously a gb_single and a positive gap. Explaining luck with a second
  measurement of the same luck is not an explanation.

  Split the predictors into two classes and report them apart:
    ANTE  - properties of the batted balls and the context, knowable before the
            ball lands: spray, pull, launch angle, exit velocity, distance,
            batted-ball mix, park, fielding alignment, age
    POST  - outcome-derived rates: gb_single, triple rate, GIDP rate""")
ANTE=["x_spray","x_pull","x_gb","x_ld","x_fb","x_pop","x_la","x_ev","x_sd_spray",
      "x_home_share","x_if_strat","x_if_shade","x_of_strat","x_distance","age","x_sd_la"]
POST=["x_gb_single","x_gidp","x_triple"]
def wols(X,y,w):
    A=np.c_[np.ones(len(X)),X]; s=np.sqrt(w)
    b,*_=np.linalg.lstsq(A*s[:,None],y*s,rcond=None); p=A@b
    r2=1-np.sum(w*(y-p)**2)/np.sum(w*(y-np.average(y,weights=w))**2)
    return b,r2
ROWS=[]
for W,mp,lab in ((1,40,"1 month"),(2,80,"2 months"),(3,110,"3 months")):
    D=build(W,mp); t=D[D.year<=2025]
    y=(t.x_woba-t.x_xwoba).values; w=t.x_pa.values.astype(float)
    res={}
    for nm,cols in (("ANTE only",ANTE),("POST only",POST),("both",ANTE+POST)):
        X=t[cols].values.astype(float)
        ok=np.isfinite(X).all(1)&np.isfinite(y)
        Xs=X[ok]; mu,sg=Xs.mean(0),Xs.std(0); Z=(Xs-mu)/np.where(sg==0,1,sg)
        b,r2=wols(Z,y[ok],w[ok]); res[nm]=(r2,b,cols,ok.sum())
    print(f"\n  window {lab}:  n={res['both'][3]:,}  sd(gap)={np.nanstd(y):.4f}")
    for nm in ("ANTE only","POST only","both"):
        print(f"      {nm:>12}  R^2 = {res[nm][0]:.4f}")
    b,cols=res["ANTE only"][1],ANTE
    order=np.argsort(-np.abs(b[1:]))[:7]
    print("      strongest ante-hoc terms (per 1 sd):")
    for i in order:
        print(f"          {cols[i]:>16} {b[i+1]:>+9.5f}")
    ROWS.append(dict(window=lab,n=int(res['both'][3]),sd=float(np.nanstd(y)),
                     ante=float(res["ANTE only"][0]),post=float(res["POST only"][0]),
                     both=float(res["both"][0]),
                     top={cols[i]:float(b[i+1]) for i in order}))
OUTJ["gap_clean"]=ROWS

hr("IS THE GAP'S BEST EXPLAINER ITSELF A SKILL?")
print("  If gb_single barely repeats, it is luck; using it to explain the gap is circular.")
rowsA,rowsB=[],[]
for (b_,y_),g in raw.groupby(["batter","game_year"]):
    o,e=g[g.mon%2==1],g[g.mon%2==0]
    if not len(o) or not len(e): continue
    A_,B_=agg(o),agg(e)
    if A_["pa"]<100 or B_["pa"]<100: continue
    rowsA.append(A_); rowsB.append(B_)
A_=pd.DataFrame(rowsA); B_=pd.DataFrame(rowsB)
print(f"\n  {'metric':>18} {'split-half r':>13} {'Spearman-Brown':>16} {'verdict':>22}")
REL={}
for k in ("bat_speed","ev","attack_angle","pull","spray","xwoba","la","gb","whiff","k",
          "woba","gb_single","gap","triple"):
    ok=np.isfinite(A_[k])&np.isfinite(B_[k])
    r=np.corrcoef(A_[k][ok],B_[k][ok])[0,1]; sb=2*r/(1+r)
    v=("a real trait" if sb>=.6 else "partly real" if sb>=.35 else
       "mostly luck" if sb>=.15 else "essentially pure luck")
    print(f"  {k:>18} {r:>13.3f} {sb:>16.3f} {v:>22}")
    REL[k]=dict(r=float(r),sb=float(sb))
OUTJ["reliability"]=REL

hr("WHO ACTUALLY BEATS THEIR xwOBA, REPEATEDLY")
names=pd.read_csv(UP/"batter_names.csv").set_index("player_id")["name"].to_dict()
S=[]
for (b_,y_),g in raw.groupby(["batter","game_year"]):
    a=agg(g)
    if a["pa"]>=300: S.append(dict(b=b_,y=y_,gap=a["gap"],pa=a["pa"],sp=a["gb_single"],woba=a["woba"]))
S=pd.DataFrame(S)
agg2=S.groupby("b").agg(n=("gap","size"),mg=("gap","mean"),pa=("pa","sum")).query("n>=3")
agg2["name"]=[names.get(int(i),str(i)) for i in agg2.index]
print("  hitters with 3+ qualified seasons, mean season gap (wOBA minus xwOBA):")
print(f"\n  {'over-performers':>22} {'seasons':>8} {'mean gap':>10}    {'under-performers':>22} {'seasons':>8} {'mean gap':>10}")
top=agg2.nlargest(8,"mg"); bot=agg2.nsmallest(8,"mg")
for (i1,r1),(i2,r2) in zip(top.iterrows(),bot.iterrows()):
    print(f"  {r1['name']:>22} {r1['n']:>8} {r1['mg']:>+10.4f}    {r2['name']:>22} {r2['n']:>8} {r2['mg']:>+10.4f}")
# is season-to-season gap correlated?
piv=S.pivot_table(index="b",columns="y",values="gap")
cors=[]
for a,b2 in ((2023,2024),(2024,2025),(2025,2026)):
    if a in piv and b2 in piv:
        ok=piv[a].notna()&piv[b2].notna()
        if ok.sum()>40: cors.append((a,b2,float(np.corrcoef(piv[a][ok],piv[b2][ok])[0,1]),int(ok.sum())))
print("\n  season-to-season correlation of the gap:")
for a,b2,r,n in cors: print(f"      {a} -> {b2}:  r = {r:+.3f}  (n={n})")
OUTJ["gap_season_cor"]=cors
OUTJ["gap_leaders"]=dict(over=[[r['name'],int(r['n']),float(r['mg'])] for _,r in top.iterrows()],
                         under=[[r['name'],int(r['n']),float(r['mg'])] for _,r in bot.iterrows()])
Path("/home/claude/out/gapclean.json").write_text(json.dumps(OUTJ,indent=1,default=float))
print("\nwrote /home/claude/out/gapclean.json")
