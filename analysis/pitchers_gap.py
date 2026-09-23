#!/usr/bin/env python3
"""Two things.

A. The gap by count came out almost constant (+.0047 to +.0085) and always
   positive. A constant offset is not a count effect — it is either a calibration
   property of xwOBA or a bug in how I fold non-contact events in. Check directly
   on contact only, by season.

B. xERA is not in the archive (expected_stats holds only est_ba/est_slg/est_woba).
   The honest pitcher analogue is wOBA-against vs xwOBA-against, which is what
   Savant's xERA is derived from anyway, plus actual runs allowed computed from
   the score columns. Run the same battery as the hitter study.
"""
import sqlite3, os, math, json
from pathlib import Path
import numpy as np
con=sqlite3.connect(f"file:{os.environ['HOME']}/snap.db?mode=ro",uri=True)
con.execute("PRAGMA cache_size=-500000"); OUT={}
def hr(t): print("\n"+"="*78); print(t); print("="*78)

hr("A  IS THE +.006 GAP A CALIBRATION OFFSET IN xwOBA?")
print("  On BATTED BALLS ONLY, where xwOBA actually does something.\n")
print(f"  {'season':>8} {'BIP':>10} {'wOBA on contact':>17} {'xwOBA on contact':>18} {'gap':>9}")
G=[]
for y in (2023,2024,2025,2026):
    n,w,x=con.execute("""SELECT COUNT(*), AVG(woba_value), AVG(estimated_woba_using_speedangle)
      FROM pitches WHERE game_year=? AND game_type='R' AND type='X' AND woba_denom=1
      AND estimated_woba_using_speedangle IS NOT NULL""",(y,)).fetchone()
    print(f"  {y:>8} {n:>10,} {w:>17.4f} {x:>18.4f} {w-x:>+9.4f}")
    G.append((y,n,w,x,w-x))
OUT["calib"]=[dict(year=y,n=n,woba=w,xwoba=x,gap=g) for y,n,w,x,g in G]
print("\n  Same thing split by batted-ball type, 2023-2026 pooled:")
print(f"  {'type':>14} {'n':>10} {'wOBA':>9} {'xwOBA':>9} {'gap':>9}")
for bt,n,w,x in con.execute("""SELECT bb_type, COUNT(*), AVG(woba_value),
  AVG(estimated_woba_using_speedangle) FROM pitches
  WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R' AND type='X' AND woba_denom=1
  AND estimated_woba_using_speedangle IS NOT NULL AND bb_type IS NOT NULL
  GROUP BY 1 ORDER BY 2 DESC"""):
    print(f"  {bt:>14} {n:>10,} {w:>9.4f} {x:>9.4f} {w-x:>+9.4f}")

hr("B  PITCHERS — wOBA against vs xwOBA against (the available xERA analogue)")
OUTS="""CASE WHEN events IN ('grounded_into_double_play','double_play','strikeout_double_play',
 'sac_fly_double_play','sac_bunt_double_play') THEN 2 WHEN events='triple_play' THEN 3
 WHEN events IN ('field_out','strikeout','force_out','sac_fly','sac_bunt',
 'fielders_choice_out','other_out') THEN 1 ELSE 0 END"""
Q=f"""SELECT pitcher, game_year, SUM({OUTS}) outs, SUM(woba_denom) bf,
 SUM(CASE WHEN woba_denom=1 THEN woba_value END) wn,
 SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END) xn,
 SUM(CASE WHEN woba_denom=1 THEN (post_bat_score-bat_score) END) runs,
 SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
 SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END) bb,
 SUM(CASE WHEN events='home_run' THEN 1 ELSE 0 END) hr,
 SUM(CASE WHEN bb_type='ground_ball' THEN 1 ELSE 0 END) gb,
 SUM(CASE WHEN bb_type IS NOT NULL THEN 1 ELSE 0 END) nbb,
 SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END) nev,
 SUM(CASE WHEN type='X' THEN launch_speed END) sev,
 SUM(CASE WHEN type='X' AND launch_speed>=95 THEN 1 ELSE 0 END) hh,
 SUM(CASE WHEN type='X' AND launch_speed_angle=6 THEN 1 ELSE 0 END) brl,
 SUM(CASE WHEN on_1b IS NOT NULL OR on_2b IS NOT NULL OR on_3b IS NOT NULL THEN 1 ELSE 0 END) runners,
 COUNT(*) pit,
 SUM(CASE WHEN inning_topbot='Bot' THEN 1 ELSE 0 END) away_pit
FROM pitches WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R'
GROUP BY 1,2 HAVING outs>=150"""
R={}
for r in con.execute(Q):
    pid,y=r[0],r[1]
    outs,bf,wn,xn,runs,k,bb,hr_,gb,nbb,nev,sev,hh,brl,runners,pit,ap=r[2:]
    R[(pid,y)]=dict(ip=outs/3,bf=bf,woba=(wn or 0)/bf,xwoba=(xn or 0)/bf,
        ra9=(runs or 0)/outs*27, k=k/bf, bb=bb/bf, hr=hr_/bf,
        gb=gb/nbb if nbb else np.nan, ev=sev/nev if nev else np.nan,
        hh=hh/nev if nev else np.nan, brl=brl/nev if nev else np.nan,
        runners=runners/pit, road=ap/pit)
print(f"  {len(R)} pitcher-seasons with 50+ IP, 2023-2026")
w=np.array([v["woba"] for v in R.values()]); x=np.array([v["xwoba"] for v in R.values()])
ra=np.array([v["ra9"] for v in R.values()])
print(f"  mean wOBA against {w.mean():.4f}   xwOBA against {x.mean():.4f}   gap {(w-x).mean():+.4f}")
print(f"  mean runs allowed per 9 innings (not earned): {ra.mean():.2f}")
print(f"\n  correlation with actual runs allowed per 9:")
print(f"     wOBA against   r = {np.corrcoef(w,ra)[0,1]:+.3f}")
print(f"     xwOBA against  r = {np.corrcoef(x,ra)[0,1]:+.3f}")
print("  (wOBA-against should win here by construction: it contains the hits that scored")
print("   the runs. The question is by how much, and that margin is the sequencing term.)")

# reliability of the pitcher gap, odd/even months
hr("B2  IS THE PITCHER GAP A SKILL? split-half, odd vs even months")
QH=f"""SELECT pitcher, game_year, CAST(substr(game_date,6,2) AS INT)%2 half,
 SUM(woba_denom) bf, SUM(CASE WHEN woba_denom=1 THEN woba_value END) wn,
 SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END) xn,
 SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
 SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END) nev,
 SUM(CASE WHEN type='X' THEN launch_speed END) sev,
 SUM(CASE WHEN bb_type='ground_ball' THEN 1 ELSE 0 END) gb,
 SUM(CASE WHEN bb_type IS NOT NULL THEN 1 ELSE 0 END) nbb
FROM pitches WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R'
GROUP BY 1,2,3 HAVING bf>=120"""
H={}
for pid,y,h,bf,wn,xn,k,nev,sev,gb,nbb in con.execute(QH):
    H.setdefault((pid,y),{})[h]=dict(bf=bf,woba=(wn or 0)/bf,xwoba=(xn or 0)/bf,
        gap=((wn or 0)-(xn or 0))/bf,k=k/bf,ev=sev/nev if nev else np.nan,
        gb=gb/nbb if nbb else np.nan)
A=[v[0] for v in H.values() if 0 in v and 1 in v]; B=[v[1] for v in H.values() if 0 in v and 1 in v]
print(f"  n = {len(A)} pitcher-seasons with 120+ batters faced in both halves")
print(f"  {'metric':>16} {'split-half r':>13} {'Spearman-Brown':>16}")
for key in ("k","ev","gb","xwoba","woba","gap"):
    a=np.array([d[key] for d in A]); b=np.array([d[key] for d in B])
    ok=np.isfinite(a)&np.isfinite(b); r=np.corrcoef(a[ok],b[ok])[0,1]
    print(f"  {key:>16} {r:>13.3f} {2*r/(1+r):>16.3f}")
    OUT.setdefault("pit_rel",{})[key]=dict(r=float(r),sb=float(2*r/(1+r)))

hr("B3  DOES xwOBA-AGAINST PREDICT NEXT SEASON BETTER THAN wOBA-AGAINST?")
pairs=[]
for (pid,y),v in R.items():
    n=R.get((pid,y+1))
    if n and v["bf"]>=200 and n["bf"]>=200:
        pairs.append((v["woba"],v["xwoba"],v["k"],v["bb"],v["ev"],n["woba"],n["bf"],y))
P=np.array([p[:7] for p in pairs],float); yrs=np.array([p[7] for p in pairs])
tr,te=yrs<=2024,yrs==2025
print(f"  {tr.sum()} training pairs (23->24, 24->25), {te.sum()} test pairs (25->26)")
def wr2(y,p,w):
    mu=np.average(y,weights=w); return 1-np.sum(w*(y-p)**2)/np.sum(w*(y-mu)**2)
def fit(cols):
    X=np.c_[np.ones(tr.sum()),P[tr][:,cols]]; s=np.sqrt(P[tr][:,6])
    b,*_=np.linalg.lstsq(X*s[:,None],P[tr][:,5]*s,rcond=None)
    return (np.c_[np.ones(te.sum()),P[te][:,cols]])@b
print(f"\n  {'predictor':>34} {'test R^2':>10}")
for lab,cols in (("this season's wOBA against",[0]),("this season's xwOBA against",[1]),
                 ("both",[0,1]),("xwOBA + K% + BB%",[1,2,3]),("K% and BB% only",[2,3])):
    p=fit(cols); r2=wr2(P[te][:,5],p,P[te][:,6])
    print(f"  {lab:>34} {r2:>10.4f}")
    OUT.setdefault("pit_pred",{})[lab]=float(r2)
gp=P[:,0]-P[:,1]
print(f"\n  pitcher gap: mean {gp.mean():+.4f}  sd {gp.std():.4f}")
piv={}
for (pid,y),v in R.items(): piv.setdefault(pid,{})[y]=v["woba"]-v["xwoba"]
cors=[]
for a,b in ((2023,2024),(2024,2025),(2025,2026)):
    d=[(piv[p][a],piv[p][b]) for p in piv if a in piv[p] and b in piv[p]]
    if len(d)>40:
        d=np.array(d); cors.append((a,b,float(np.corrcoef(d[:,0],d[:,1])[0,1]),len(d)))
print("  season-to-season correlation of the pitcher gap:")
for a,b,r,n in cors: print(f"     {a} -> {b}: r = {r:+.3f} (n={n})")
OUT["pit_gap_cor"]=cors
Path("output/pitchers_gap.json").write_text(json.dumps(OUT,indent=1,default=float))
print("\nwrote output/pitchers_gap.json")
