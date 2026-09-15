#!/usr/bin/env python3
"""Comp engine prototype, and a test of the design decision behind it.

The obvious way to build "similar players" is to match on results — wOBA, home
runs, batting average. Baseball Reference does this and the results are famously
mediocre. This project has a reason why: results have a month-to-month
reliability of .135 and a within-season split-half of .448. Two players matched
on results are substantially matched on shared luck.

The alternative is to match on the STABLE layer — what a hitter does rather than
what happened to him — with each dimension weighted by how reliable it actually
is, measured here rather than assumed.

Both are built below and printed side by side so the choice can be judged.
"""
import sqlite3, os, math, json
from pathlib import Path
import numpy as np
con=sqlite3.connect(f"file:{os.environ['HOME']}/snap.db?mode=ro",uri=True)
con.execute("PRAGMA cache_size=-500000")
HIT="events IN ('single','double','triple','home_run','walk','hit_by_pitch')"
SW="(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
WH="(description LIKE 'swinging_strike%' OR description='foul_tip')"

AGG=f"""SELECT batter, {{GRP}} grp, SUM(woba_denom) pa,
 SUM(CASE WHEN woba_denom=1 AND {HIT} THEN woba_value ELSE 0 END) wn,
 SUM(CASE WHEN woba_denom=1 THEN estimated_woba_using_speedangle END) xn,
 SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
 SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END) bb,
 SUM(CASE WHEN events='home_run' THEN 1 ELSE 0 END) hr,
 COUNT(*) pit, SUM(CASE WHEN {SW} THEN 1 ELSE 0 END) sw,
 SUM(CASE WHEN {SW} AND {WH} THEN 1 ELSE 0 END) whf,
 SUM(CASE WHEN zone BETWEEN 1 AND 9 THEN 1 ELSE 0 END) iz,
 SUM(CASE WHEN zone BETWEEN 1 AND 9 AND {SW} THEN 1 ELSE 0 END) izsw,
 SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END) oz,
 SUM(CASE WHEN zone>=11 AND {SW} THEN 1 ELSE 0 END) ozsw,
 SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END) nbs,
 SUM(bat_speed) sbs, SUM(swing_length) ssl,
 SUM(CASE WHEN attack_angle IS NOT NULL THEN 1 ELSE 0 END) naa,
 SUM(attack_angle) saa, SUM(attack_direction) sad, SUM(swing_path_tilt) stl,
 SUM(intercept_ball_minus_batter_pos_y_inches) sic,
 SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END) nev,
 SUM(CASE WHEN type='X' THEN launch_speed END) sev,
 SUM(CASE WHEN type='X' THEN launch_angle END) sla,
 SUM(CASE WHEN type='X' AND launch_speed>=95 THEN 1 ELSE 0 END) hh,
 SUM(CASE WHEN bb_type='ground_ball' THEN 1 ELSE 0 END) gb,
 SUM(CASE WHEN bb_type IS NOT NULL THEN 1 ELSE 0 END) nbb,
 SUM(CASE WHEN hc_x IS NOT NULL AND (CASE WHEN stand='L' THEN 1 ELSE -1 END)*
   (180/3.14159265*ATAN2((hc_x-125.42)*2.0,(198.27-hc_y)*2.0))>15 THEN 1 ELSE 0 END) pull,
 SUM(CASE WHEN hc_x IS NOT NULL THEN 1 ELSE 0 END) nsp
FROM pitches WHERE game_year IN (2025,2026) AND game_type='R' {{W}}
GROUP BY 1,2 HAVING pa>={{MIN}}"""

def rates(r):
    (_,_,pa,wn,xn,k,bb,hr,pit,sw,whf,iz,izsw,oz,ozsw,nbs,sbs,ssl,naa,saa,sad,stl,sic,
     nev,sev,sla,hh,gb,nbb,pull,nsp)=r
    d=lambda a,b:(a/b) if b else np.nan
    return dict(pa=pa,
        # STABLE LAYER — what the hitter does
        bat_speed=d(sbs,nbs), swing_len=d(ssl,nbs), attack_angle=d(saa,naa),
        attack_dir=d(sad,naa), tilt=d(stl,naa), contact_depth=d(sic,naa),
        whiff=d(whf,sw), chase=d(ozsw,oz), zswing=d(izsw,iz), swing=d(sw,pit),
        k=d(k,pa), bb=d(bb,pa), ev=d(sev,nev), la=d(sla,nev), hh=d(hh,nev),
        gb=d(gb,nbb), pull=d(pull,nsp),
        # RESULTS LAYER — what happened to him
        woba=d(wn,pa), xwoba=d(xn,pa), hr=d(hr,pa))

names={}
for pid,nm in con.execute("SELECT DISTINCT player_id,player_name FROM expected_stats WHERE player_type='batter'"):
    names[pid]=nm

# ---------- reliability of every dimension, measured not assumed
print("Measuring split-half reliability of each candidate dimension")
print("(odd vs even calendar months, Spearman-Brown corrected)\n")
H={}
for half in (1,0):
    q=AGG.format(GRP="game_year",W=f"AND CAST(substr(game_date,6,2) AS INT)%2={half}",MIN=120)
    for r in con.execute(q): H.setdefault((r[0],r[1]),{})[half]=rates(r)
both=[v for v in H.values() if 0 in v and 1 in v]
DIMS=["bat_speed","swing_len","attack_angle","attack_dir","tilt","contact_depth",
      "whiff","chase","zswing","swing","k","bb","ev","la","hh","gb","pull",
      "woba","xwoba","hr"]
REL={}
for dm in DIMS:
    a=np.array([v[1][dm] for v in both]); b=np.array([v[0][dm] for v in both])
    ok=np.isfinite(a)&np.isfinite(b)
    r=np.corrcoef(a[ok],b[ok])[0,1]; REL[dm]=max(2*r/(1+r),0.01)
print(f"  {'dimension':>15} {'reliability':>12}   {'':<10}{'dimension':>12} {'reliability':>12}")
stable=[d for d in DIMS if d not in ("woba","xwoba","hr")]
res=["woba","xwoba","hr"]
for i in range(0,len(stable),2):
    row=""
    for dm in stable[i:i+2]:
        row+=f"  {dm:>15} {REL[dm]:>12.3f}   "
    print(row)
print("\n  results layer, for contrast:")
for dm in res: print(f"  {dm:>15} {REL[dm]:>12.3f}")

# ---------- season vectors
S={}
for r in con.execute(AGG.format(GRP="game_year",W="AND game_year=2026",MIN=250)):
    S[r[0]]=rates(r)
print(f"\n{len(S)} hitters with 250+ PA in 2026\n")

def build(dims, weight_by_reliability):
    ids=[p for p in S if all(np.isfinite(S[p][d]) for d in dims)]
    X=np.array([[S[p][d] for d in dims] for p in ids],float)
    mu,sd=X.mean(0),X.std(0)
    Z=(X-mu)/np.where(sd==0,1,sd)
    if weight_by_reliability:
        # a dimension counts in proportion to how much of its spread is real
        w=np.array([REL[d] for d in dims]); Z=Z*np.sqrt(w)
    return ids,Z

def comps(ids,Z,who,n=5):
    if who not in ids: return None
    i=ids.index(who)
    dist=np.sqrt(((Z-Z[i])**2).sum(1))
    order=np.argsort(dist)[1:n+1]
    return [(names.get(ids[j],str(ids[j])),dist[j]) for j in order]

ids_s,Z_s=build(stable,True)
ids_r,Z_r=build(res,False)
TARGETS=["Aaron Judge","Juan Soto","Francisco Lindor","Jose Altuve","Luis Arraez",
         "Bobby Witt Jr.","Kyle Schwarber"]
print("="*78)
print("SIDE BY SIDE — comps on the stable layer vs comps on results")
print("="*78)
for t in TARGETS:
    pid=next((p for p,n_ in names.items() if n_==t and p in S),None)
    if pid is None: continue
    a=comps(ids_s,Z_s,pid); b=comps(ids_r,Z_r,pid)
    if not a or not b: continue
    print(f"\n  {t}")
    print(f"     {'STABLE SKILLS (17 dims, reliability-weighted)':<46}{'RESULTS ONLY (wOBA, xwOBA, HR rate)'}")
    for (na,da),(nb,db) in zip(a,b):
        print(f"       {na:<38}{nb}")
Path("output").mkdir(exist_ok=True)
Path("output/comps_reliability.json").write_text(json.dumps(REL,indent=1))
print("\nwrote output/comps_reliability.json")
