#!/usr/bin/env python3
"""CORRECTION. The stored woba_value column is not wOBA.

It credits any plate appearance in which the batter reached base, including
reached-on-error, fielder's choice and dropped third strikes. Real wOBA — like
OBP — treats all three as outs. Consequence: every wOBA computed in this repo is
inflated by roughly 9 points, and the ground-ball "gap" finding was measuring my
own numerator against a correctly-specified xwOBA.

Corrected numerator keeps Savant's weights but credits only hits, unintentional
walks and hit-by-pitch.
"""
import sqlite3, os, math, json
from pathlib import Path
import numpy as np
con=sqlite3.connect(f"file:{os.environ['HOME']}/snap.db?mode=ro",uri=True)
con.execute("PRAGMA cache_size=-500000"); OUT={}
HIT="events IN ('single','double','triple','home_run','walk','hit_by_pitch')"
GOOD=f"CASE WHEN {HIT} THEN woba_value ELSE 0 END"

print("0) what events exist that look like a 'reach' but are not hits?")
for ev,n,v in con.execute(f"""SELECT events, COUNT(*), AVG(woba_value) FROM pitches
  WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R' AND woba_denom=1
  AND NOT ({HIT}) AND woba_value>0 GROUP BY 1 ORDER BY 2 DESC"""):
    print(f"     {str(ev):>26} {n:>8,}  avg stored woba_value {v:.3f}")

print("\n1) ACCEPTANCE TEST — corrected wOBA vs Savant's published wOBA")
print(f"   {'year':>6} {'n':>5} {'Savant':>9} {'stored':>9} {'CORRECTED':>11} {'diff vs Savant':>16}")
for y in (2023,2024,2025,2026):
    rows=con.execute(f"""SELECT e.woba,
       (SELECT SUM(CASE WHEN p.woba_denom=1 THEN p.woba_value END)*1.0/SUM(p.woba_denom)
        FROM pitches p WHERE p.batter=e.player_id AND p.game_year=e.year AND p.game_type='R'),
       (SELECT SUM(CASE WHEN p.woba_denom=1 THEN {GOOD.replace('woba_value','p.woba_value').replace('events','p.events')} END)*1.0/SUM(p.woba_denom)
        FROM pitches p WHERE p.batter=e.player_id AND p.game_year=e.year AND p.game_type='R')
       FROM expected_stats e WHERE e.year=? AND e.player_type='batter' AND e.pa>=300""",(y,)).fetchall()
    a=np.array([r for r in rows if r[1] is not None and r[2] is not None],float)
    print(f"   {y:>6} {len(a):>5} {a[:,0].mean():>9.4f} {a[:,1].mean():>9.4f} {a[:,2].mean():>11.4f} "
          f"{(a[:,2]-a[:,0]).mean():>+16.5f}")
    OUT.setdefault("acceptance",{})[y]=dict(n=len(a),savant=float(a[:,0].mean()),
        stored=float(a[:,1].mean()),corrected=float(a[:,2].mean()),
        diff=float((a[:,2]-a[:,0]).mean()))

print("\n2) THE GAP BY BATTED-BALL TYPE — stored vs corrected")
print(f"   {'type':>14} {'n':>9} {'xwOBA':>8} {'stored wOBA':>12} {'stored gap':>11} "
      f"{'CORRECT wOBA':>13} {'CORRECT gap':>12}")
for bt,n,w,g,x in con.execute(f"""SELECT bb_type, COUNT(*), AVG(woba_value),
   AVG({GOOD}), AVG(estimated_woba_using_speedangle) FROM pitches
   WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R' AND type='X' AND woba_denom=1
   AND estimated_woba_using_speedangle IS NOT NULL AND bb_type IS NOT NULL
   GROUP BY 1 ORDER BY 2 DESC"""):
    print(f"   {bt:>14} {n:>9,} {x:>8.4f} {w:>12.4f} {w-x:>+11.4f} {g:>13.4f} {g-x:>+12.4f}")
    OUT.setdefault("bbtype",{})[bt]=dict(n=n,xwoba=x,stored=w,corrected=g,
                                         stored_gap=w-x,correct_gap=g-x)

print("\n3) LEAGUE-WIDE, on contact, by season")
print(f"   {'year':>6} {'BIP':>9} {'xwOBA':>8} {'stored gap':>11} {'CORRECT gap':>12}")
for y in (2023,2024,2025,2026):
    n,w,g,x=con.execute(f"""SELECT COUNT(*), AVG(woba_value), AVG({GOOD}),
      AVG(estimated_woba_using_speedangle) FROM pitches WHERE game_year=? AND game_type='R'
      AND type='X' AND woba_denom=1 AND estimated_woba_using_speedangle IS NOT NULL""",(y,)).fetchone()
    print(f"   {y:>6} {n:>9,} {x:>8.4f} {w-x:>+11.4f} {g-x:>+12.4f}")
    OUT.setdefault("byyear",{})[y]=dict(n=n,xwoba=x,stored_gap=w-x,correct_gap=g-x)

print("\n4) DOES THE PERSISTENT HITTER GAP SURVIVE THE CORRECTION?")
S={}
for pid,y,pa,w,g,x in con.execute(f"""SELECT batter, game_year, SUM(woba_denom),
   SUM(CASE WHEN woba_denom=1 THEN woba_value END),
   SUM(CASE WHEN woba_denom=1 THEN {GOOD} END),
   SUM(CASE WHEN woba_denom=1 THEN COALESCE(estimated_woba_using_speedangle,woba_value) END)
   FROM pitches WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R'
   GROUP BY 1,2 HAVING SUM(woba_denom)>=300"""):
    # xwOBA fallback must use the CORRECTED value on non-contact events too
    S[(pid,y)]=dict(pa=pa,stored_gap=(w-x)/pa,corr_gap=(g-x)/pa)
for key in ("stored_gap","corr_gap"):
    piv={}
    for (p,y),v in S.items(): piv.setdefault(p,{})[y]=v[key]
    out=[]
    for a,b in ((2023,2024),(2024,2025),(2025,2026)):
        d=[(piv[p][a],piv[p][b]) for p in piv if a in piv[p] and b in piv[p]]
        if len(d)>40:
            d=np.array(d); out.append(f"{a}->{b}: {np.corrcoef(d[:,0],d[:,1])[0,1]:+.3f} (n={len(d)})")
    lab="stored (inflated)" if key=="stored_gap" else "CORRECTED"
    print(f"   {lab:>20}  " + "   ".join(out))
    OUT.setdefault("persist",{})[key]=out
Path("output/woba_fix.json").write_text(json.dumps(OUT,indent=1,default=float))
print("\nwrote output/woba_fix.json")
