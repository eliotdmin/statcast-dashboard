#!/usr/bin/env python3
"""Best individual pitches, 2023-2025: run value, whiff rate, and where they are used."""
import sqlite3, sys, json
from pathlib import Path
con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
con.execute("PRAGMA cache_size=-300000")
NAME={"FF":"4-seam","SI":"sinker","SL":"slider","ST":"sweeper","FC":"cutter","CH":"change",
      "CU":"curve","KC":"knuck-curve","FS":"splitter","SV":"slurve"}
rows=con.execute("""
 SELECT pitcher, player_name, pitch_type, COUNT(*) n,
        -100.0*AVG(delta_run_exp) rv100,
        100.0*SUM(CASE WHEN description LIKE 'swinging_strike%' OR description='foul_tip' THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN description LIKE '%swing%' OR description LIKE 'foul%' OR type='X'
                               THEN 1 ELSE 0 END),0) whiff,
        AVG(release_speed) velo,
        100.0*AVG(CASE WHEN strikes=2 THEN 1.0 ELSE 0.0 END) two_strike_share
 FROM pitches
 WHERE game_year IN (2023,2024,2025) AND game_type='R' AND pitch_type IS NOT NULL
   AND delta_run_exp IS NOT NULL
 GROUP BY 1,3 HAVING n >= 600
 ORDER BY rv100 DESC""").fetchall()
def nm(s):
    return " ".join(x.strip() for x in s.split(",")[::-1]) if "," in s else s
out=[{"name":nm(r[1]),"pitch":r[2],"n":r[3],"rv100":round(r[4],3),
      "whiff":round(r[5],1) if r[5] else None,"velo":round(r[6],1),
      "two_strike":round(r[7],1)} for r in rows]
Path("output/nastiest.json").write_text(json.dumps(out))
print(f"{len(out)} pitcher-pitches with 600+ thrown, 2023-2025\n")
print("=== BEST 15 BY RUN VALUE PER 100 ===")
print(f"{'pitcher':22s} {'pitch':<12} {'n':>6} {'rv/100':>7} {'whiff':>6} {'velo':>6}")
for r in out[:15]:
    print(f"{r['name'][:22]:22s} {NAME.get(r['pitch'],r['pitch']):<12} {r['n']:>6,} "
          f"{r['rv100']:>+7.2f} {str(r['whiff'] or '—'):>6} {r['velo']:>6}")
print("\n=== BEST 15 BY WHIFF PER SWING (min 600) ===")
for r in sorted([x for x in out if x['whiff']], key=lambda x:-x['whiff'])[:15]:
    print(f"{r['name'][:22]:22s} {NAME.get(r['pitch'],r['pitch']):<12} {r['n']:>6,} "
          f"{r['rv100']:>+7.2f} {r['whiff']:>5.1f}% {r['velo']:>6}")
