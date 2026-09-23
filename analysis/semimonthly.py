#!/usr/bin/env python3
"""Per-player, per-half-month block counts for 2026.

Fixed cutoffs on the 1st and 16th of each month give ~14 blocks a season and
C(14,2)=91 possible within-season ranges. Storing BLOCKS rather than ranges means
the browser can sum any range on demand — the prefix-sum idea, client side — so
the universe of ranges explodes for free while the payload stays small.
"""
import sqlite3, os, json, math
from pathlib import Path
con=sqlite3.connect(f"file:{os.environ['HOME']}/snap.db?mode=ro",uri=True)
con.execute("PRAGMA cache_size=-500000")
HIT="events IN ('single','double','triple','home_run','walk','hit_by_pitch')"
SW="(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
WH="(description LIKE 'swinging_strike%' OR description='foul_tip')"
BLK="substr(game_date,1,7)||'-'||(CASE WHEN CAST(substr(game_date,9,2) AS INT)<=15 THEN 'A' ELSE 'B' END)"
Q=f"""SELECT batter, {BLK} blk, SUM(woba_denom) pa,
 SUM(CASE WHEN woba_denom=1 AND {HIT} THEN woba_value ELSE 0 END) wn,
 SUM(CASE WHEN woba_denom=1 THEN estimated_woba_using_speedangle END) xn,
 SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
 SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END) bb,
 COUNT(*) pit, SUM(CASE WHEN {SW} THEN 1 ELSE 0 END) sw,
 SUM(CASE WHEN {SW} AND {WH} THEN 1 ELSE 0 END) whf,
 SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END) oz,
 SUM(CASE WHEN zone>=11 AND {SW} THEN 1 ELSE 0 END) ozsw,
 SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END) nbs,
 SUM(bat_speed) sbs, SUM(swing_length) ssl,
 SUM(CASE WHEN attack_angle IS NOT NULL THEN 1 ELSE 0 END) naa, SUM(attack_angle) saa,
 SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END) nev,
 SUM(CASE WHEN type='X' THEN launch_speed END) sev,
 SUM(CASE WHEN type='X' AND launch_speed>=95 THEN 1 ELSE 0 END) hh,
 SUM(CASE WHEN type='X' AND launch_speed_angle=6 THEN 1 ELSE 0 END) brl,
 SUM(CASE WHEN type='X' AND launch_angle BETWEEN 8 AND 32 THEN 1 ELSE 0 END) sweet
FROM pitches WHERE game_year=2026 AND game_type='R' GROUP BY 1,2"""
names={}
for pid,nm in con.execute("SELECT DISTINCT player_id,player_name FROM expected_stats WHERE player_type='batter'"):
    names[pid]=nm
FIELDS=["pa","wn","xn","k","bb","pit","sw","whf","oz","ozsw","nbs","sbs","ssl",
        "naa","saa","nev","sev","hh","brl","sweet"]
D={}; blocks=set()
for r in con.execute(Q):
    pid,blk=r[0],r[1]
    if pid not in names: continue
    blocks.add(blk)
    D.setdefault(pid,{})[blk]=[float(v or 0) for v in r[2:]]
blocks=sorted(blocks)
# season totals to pick the universe
tot={p:sum(v[0] for v in b.values()) for p,b in D.items()}
keep=[p for p,t in tot.items() if t>=200]
print(f"blocks: {len(blocks)}  ->  {blocks}")
print(f"players with 200+ PA in 2026: {len(keep)}")
out={"blocks":blocks,"fields":FIELDS,
     "players":[{"id":int(p),"n":names[p],"pa":int(tot[p]),
                 "b":{blk:[round(x,2) for x in D[p][blk]] for blk in D[p] if D[p][blk][0]>0}}
                for p in sorted(keep,key=lambda x:-tot[x])]}
Path("output").mkdir(exist_ok=True)
Path("output/semimonthly_2026.json").write_text(json.dumps(out,separators=(",",":")))
print("bytes:",Path("output/semimonthly_2026.json").stat().st_size)

# reliability at half-season, to project down to short windows in the UI
print("\nsplit-half reliability at ~half a season (odd vs even blocks), 2026:")
import numpy as np
A,B=[],[]
for p in keep:
    ha=[0.0]*len(FIELDS); hb=[0.0]*len(FIELDS)
    for i,blk in enumerate(blocks):
        v=D[p].get(blk)
        if not v: continue
        tgt=ha if i%2==0 else hb
        for j in range(len(FIELDS)): tgt[j]+=v[j]
    if ha[0]>=80 and hb[0]>=80: A.append(ha); B.append(hb)
A=np.array(A); B=np.array(B); F={f:i for i,f in enumerate(FIELDS)}
def rate(M,num,den): 
    d=M[:,F[den]]; return np.where(d>0,M[:,F[num]]/np.where(d==0,1,d),np.nan)
METRICS=[("xwOBA","xn","pa"),("wOBA","wn","pa"),("K%","k","pa"),("BB%","bb","pa"),
         ("whiff%","whf","sw"),("chase%","ozsw","oz"),("bat speed","sbs","nbs"),
         ("swing length","ssl","nbs"),("attack angle","saa","naa"),
         ("exit velo","sev","nev"),("hard-hit%","hh","nev"),("barrel%","brl","nev"),
         ("sweet-spot%","sweet","nev")]
REL={}
print(f"  n={len(A)} players, mean {A[:,0].mean():.0f} PA per half")
print(f"  {'metric':>14} {'split-half r':>13} {'Spearman-Brown':>15}")
for lab,num,den in METRICS:
    a,b=rate(A,num,den),rate(B,num,den); ok=np.isfinite(a)&np.isfinite(b)
    r=float(np.corrcoef(a[ok],b[ok])[0,1]); sb=max(2*r/(1+r),0.02)
    REL[lab]=dict(r=r,sb=sb,n0=float(A[:,0].mean()))
    print(f"  {lab:>14} {r:>13.3f} {sb:>15.3f}")
Path("output/semimonthly_rel.json").write_text(json.dumps(REL,indent=1))
print("\nwrote output/semimonthly_2026.json and semimonthly_rel.json")
