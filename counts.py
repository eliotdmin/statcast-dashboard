#!/usr/bin/env python3
"""wOBA and xwOBA by count REACHED.

Not "outcomes on contact in that count" — the question is: given that a plate
appearance arrived at count (b,s), what did that plate appearance eventually
produce, counting everything that happened afterwards. A PA that reaches 3-0 has
also reached 2-0, 1-0 and 0-0, so the counts are nested by construction. That is
the standard count-value table and it is the right shape for "what is this count
worth".
"""
import sqlite3, os, math, json
from pathlib import Path
con=sqlite3.connect(f"file:{os.environ['HOME']}/snap.db?mode=ro",uri=True)
con.execute("PRAGMA cache_size=-500000")
OUT={}
Q="""
WITH pa AS (
  SELECT game_pk, at_bat_number,
    MAX(woba_denom) wd, MAX(woba_value) wv,
    MAX(COALESCE(estimated_woba_using_speedangle, woba_value)) xv,
    MAX(CASE WHEN events='strikeout' THEN 1 ELSE 0 END) k,
    MAX(CASE WHEN events='walk' THEN 1 ELSE 0 END) bb,
    MAX(CASE WHEN type='X' THEN 1 ELSE 0 END) bip,
    MAX(CASE WHEN type='X' THEN launch_speed END) ev
  FROM pitches WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R'
  GROUP BY 1,2),
reached AS (
  SELECT DISTINCT game_pk, at_bat_number, balls, strikes FROM pitches
  WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R' AND balls<=3 AND strikes<=2)
SELECT r.balls, r.strikes, COUNT(*) n, SUM(p.wd) den,
  SUM(CASE WHEN p.wd=1 THEN p.wv END) wnum,
  SUM(CASE WHEN p.wd=1 THEN p.xv END) xnum,
  SUM(p.k) k, SUM(p.bb) bb, SUM(p.bip) bip,
  SUM(CASE WHEN p.bip=1 THEN p.ev END) sev,
  SUM(CASE WHEN p.bip=1 AND p.ev IS NOT NULL THEN 1 ELSE 0 END) nev
FROM reached r JOIN pa p ON r.game_pk=p.game_pk AND r.at_bat_number=p.at_bat_number
GROUP BY 1,2 ORDER BY 1,2"""
rows=list(con.execute(Q))
print("="*78)
print("wOBA AND xwOBA BY COUNT REACHED — 2023-2026 regular season")
print("="*78)
print(f"\n  {'count':>7} {'PA reached':>12} {'wOBA':>8} {'xwOBA':>8} {'gap':>8} "
      f"{'K%':>7} {'BB%':>7} {'BIP%':>7} {'exit velo':>10}")
T={}
for b,s,n,den,wn,xn,k,bb,bip,sev,nev in rows:
    w=wn/den; x=xn/den
    T[(b,s)]=dict(n=n,den=den,woba=w,xwoba=x,gap=w-x,k=k/den,bb=bb/den,bip=bip/den,
                  ev=(sev/nev) if nev else None)
    print(f"  {b}-{s:<5} {den:>12,.0f} {w:>8.4f} {x:>8.4f} {w-x:>+8.4f} "
          f"{100*k/den:>6.1f}% {100*bb/den:>6.1f}% {100*bip/den:>6.1f}% "
          f"{(sev/nev if nev else 0):>10.2f}")
OUT["counts"]={f"{b}-{s}":v for (b,s),v in T.items()}

print("\n" + "="*78)
print("HOW BIG IS THE COUNT EFFECT, RELATIVE TO THE HITTER?")
print("="*78)
ws=[v["woba"] for v in T.values()]
print(f"  wOBA across the 12 counts:  min {min(ws):.4f} ({min(T,key=lambda c:T[c]['woba'])})  "
      f"max {max(ws):.4f} ({max(T,key=lambda c:T[c]['woba'])})")
print(f"  range = {max(ws)-min(ws):.4f}   sd across counts = {(sum((x-sum(ws)/len(ws))**2 for x in ws)/len(ws))**.5:.4f}")
h=con.execute("""SELECT batter, SUM(woba_denom) pa, SUM(CASE WHEN woba_denom=1 THEN woba_value END) wn
 FROM pitches WHERE game_year BETWEEN 2023 AND 2026 AND game_type='R'
 GROUP BY 1 HAVING pa>=1000""").fetchall()
import statistics as st
hv=[r[2]/r[1] for r in h]
print(f"  wOBA across {len(hv)} hitters with 1000+ PA: min {min(hv):.4f} max {max(hv):.4f} "
      f"range {max(hv)-min(hv):.4f}  sd {st.pstdev(hv):.4f}")
print(f"\n  -> the count you arrive at swings expected production by "
      f"{max(ws)-min(ws):.3f} of wOBA.")
print(f"     the difference between the best and worst everyday hitter in four seasons is "
      f"{max(hv)-min(hv):.3f}.")
print(f"     ratio of spreads (count : hitter) = {(max(ws)-min(ws))/(max(hv)-min(hv)):.2f}x")
OUT["spread"]=dict(count_range=max(ws)-min(ws),hitter_range=max(hv)-min(hv),
                   count_sd=st.pstdev(ws),hitter_sd=st.pstdev(hv),n_hitters=len(hv))

print("\n" + "="*78)
print("WHERE IS xwOBA MOST WRONG? gap by count, ordered")
print("="*78)
srt=sorted(T.items(),key=lambda kv:-kv[1]["gap"])
print(f"  {'count':>7} {'gap':>9} {'BIP share':>11} {'walk share':>11}  interpretation")
for (b,s),v in srt:
    note=""
    if v["bb"]>.25: note="walk-heavy: xwOBA=wOBA by construction on walks"
    elif v["k"]>.4: note="strikeout-heavy: same, K has no batted ball"
    elif v["bip"]>.65: note="contact-heavy: the gap is all batted-ball luck"
    print(f"  {b}-{s:<5} {v['gap']:>+9.4f} {100*v['bip']:>10.1f}% {100*v['bb']:>10.1f}%  {note}")
Path("output").mkdir(exist_ok=True)
Path("output/counts.json").write_text(json.dumps(OUT,indent=1,default=float))
print("\nwrote output/counts.json")
