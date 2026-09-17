#!/usr/bin/env python3
"""Half-month block counts for hitters AND pitchers, 2023-2026.

Same prefix-sum design: store blocks, let the client sum any within-season range.
Reliability for every metric is measured per player type, not assumed.
"""
import sqlite3, os, json, math
from pathlib import Path
import numpy as np
con=sqlite3.connect(f"file:{os.environ['HOME']}/snap.db?mode=ro",uri=True)
con.execute("PRAGMA cache_size=-600000")
HIT="events IN ('single','double','triple','home_run','walk','hit_by_pitch')"
SW="(description LIKE '%swing%' OR description LIKE 'foul%' OR type='X')"
WH="(description LIKE 'swinging_strike%' OR description='foul_tip')"
BLK="substr(game_date,1,7)||'-'||(CASE WHEN CAST(substr(game_date,9,2) AS INT)<=15 THEN 'A' ELSE 'B' END)"
OUTS="""CASE WHEN events IN ('grounded_into_double_play','double_play','strikeout_double_play',
 'sac_fly_double_play','sac_bunt_double_play') THEN 2 WHEN events='triple_play' THEN 3
 WHEN events IN ('field_out','strikeout','force_out','sac_fly','sac_bunt',
 'fielders_choice_out','other_out') THEN 1 ELSE 0 END"""

BAT_F=["pa","wn","xn","k","bb","pit","sw","whf","oz","ozsw","nbs","sbs","ssl","naa","saa","sad",
       "nev","sev","sla","hh","brl","sweet","gb","nbb"]
BAT_Q=f"""SELECT batter, {BLK} blk, SUM(woba_denom),
 SUM(CASE WHEN woba_denom=1 AND {HIT} THEN woba_value ELSE 0 END),
 SUM(CASE WHEN woba_denom=1 THEN estimated_woba_using_speedangle END),
 SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END),
 SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END), COUNT(*),
 SUM(CASE WHEN {SW} THEN 1 ELSE 0 END), SUM(CASE WHEN {SW} AND {WH} THEN 1 ELSE 0 END),
 SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END), SUM(CASE WHEN zone>=11 AND {SW} THEN 1 ELSE 0 END),
 SUM(CASE WHEN bat_speed IS NOT NULL THEN 1 ELSE 0 END), SUM(bat_speed), SUM(swing_length),
 SUM(CASE WHEN attack_angle IS NOT NULL THEN 1 ELSE 0 END), SUM(attack_angle), SUM(attack_direction),
 SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END),
 SUM(CASE WHEN type='X' THEN launch_speed END), SUM(CASE WHEN type='X' THEN launch_angle END),
 SUM(CASE WHEN type='X' AND launch_speed>=95 THEN 1 ELSE 0 END),
 SUM(CASE WHEN type='X' AND launch_speed_angle=6 THEN 1 ELSE 0 END),
 SUM(CASE WHEN type='X' AND launch_angle BETWEEN 8 AND 32 THEN 1 ELSE 0 END),
 SUM(CASE WHEN bb_type='ground_ball' THEN 1 ELSE 0 END),
 SUM(CASE WHEN bb_type IS NOT NULL THEN 1 ELSE 0 END)
FROM pitches WHERE game_year=? AND game_type='R' GROUP BY 1,2"""

PIT_F=["bf","outs","wn","xn","k","bb","pit","sw","whf","iz","zt","oz","ozsw","edge","loct",
       "nv","sv","ssv","nsp","ssp","nex","sex","naa","saa","nev","sev","hh","gb","nbb"]
PIT_Q=f"""SELECT pitcher, {BLK} blk, SUM(woba_denom), SUM({OUTS}),
 SUM(CASE WHEN woba_denom=1 AND {HIT} THEN woba_value ELSE 0 END),
 SUM(CASE WHEN woba_denom=1 THEN estimated_woba_using_speedangle END),
 SUM(CASE WHEN events='strikeout' THEN 1 ELSE 0 END),
 SUM(CASE WHEN events='walk' THEN 1 ELSE 0 END), COUNT(*),
 SUM(CASE WHEN {SW} THEN 1 ELSE 0 END), SUM(CASE WHEN {SW} AND {WH} THEN 1 ELSE 0 END),
 SUM(CASE WHEN zone BETWEEN 1 AND 9 THEN 1 ELSE 0 END),
 SUM(CASE WHEN zone IS NOT NULL THEN 1 ELSE 0 END),
 SUM(CASE WHEN zone>=11 THEN 1 ELSE 0 END), SUM(CASE WHEN zone>=11 AND {SW} THEN 1 ELSE 0 END),
 SUM(CASE WHEN ABS(plate_x) BETWEEN 0.6 AND 1.1 THEN 1 ELSE 0 END),
 SUM(CASE WHEN plate_x IS NOT NULL THEN 1 ELSE 0 END),
 SUM(CASE WHEN pitch_type IN ('FF','SI') AND release_speed IS NOT NULL THEN 1 ELSE 0 END),
 SUM(CASE WHEN pitch_type IN ('FF','SI') THEN release_speed END),
 SUM(CASE WHEN pitch_type IN ('FF','SI') THEN release_speed*release_speed END),
 SUM(CASE WHEN release_spin_rate IS NOT NULL THEN 1 ELSE 0 END), SUM(release_spin_rate),
 SUM(CASE WHEN release_extension IS NOT NULL THEN 1 ELSE 0 END), SUM(release_extension),
 SUM(CASE WHEN arm_angle IS NOT NULL THEN 1 ELSE 0 END), SUM(arm_angle),
 SUM(CASE WHEN type='X' AND launch_speed IS NOT NULL THEN 1 ELSE 0 END),
 SUM(CASE WHEN type='X' THEN launch_speed END),
 SUM(CASE WHEN type='X' AND launch_speed>=95 THEN 1 ELSE 0 END),
 SUM(CASE WHEN bb_type='ground_ball' THEN 1 ELSE 0 END),
 SUM(CASE WHEN bb_type IS NOT NULL THEN 1 ELSE 0 END)
FROM pitches WHERE game_year=? AND game_type='R' GROUP BY 1,2"""
# note: PIT_Q selects 29 value cols after id/blk -> matches PIT_F order with ssv/nsp shift
PIT_F=["bf","outs","wn","xn","k","bb","pit","sw","whf","iz","zt","oz","ozsw","edge","loct",
       "nv","sv","ssv","nsp","ssp","nex","sex","naa","saa","nev","sev","hh","gb","nbb"]

names={}
for pid,nm,pt in con.execute("SELECT DISTINCT player_id,player_name,player_type FROM expected_stats"):
    names[(pid,pt)]=nm

OUT={}
for kind,Q,FI,idkey,pakey,minpa in (("bat",BAT_Q,BAT_F,"batter","pa",150),
                                    ("pit",PIT_Q,PIT_F,"pitcher","bf",120)):
    D={}; blocks=set()
    for y in (2023,2024,2025,2026):
        for r in con.execute(Q,(y,)):
            pid,blk=r[0],r[1]
            key=(pid,"batter" if kind=="bat" else "pitcher")
            if key not in names: continue
            blocks.add(blk)
            D.setdefault((pid,y),{})[blk]=[float(v or 0) for v in r[2:]]
    blocks=sorted(blocks)
    rows=[]
    for (pid,y),b in D.items():
        tot=sum(v[0] for v in b.values())
        if tot<minpa: continue
        rows.append({"id":int(pid),"y":y,
                     "n":names[(pid,"batter" if kind=="bat" else "pitcher")],
                     "t":int(tot),"b":{k:[round(x,2) for x in v] for k,v in b.items() if v[0]>0}})
    rows.sort(key=lambda r:(-r["y"],-r["t"]))
    OUT[kind]={"fields":FI,"rows":rows}
    print(f"{kind}: {len(rows)} player-seasons, {len(blocks)} distinct blocks")
    # reliability per metric, odd vs even blocks, pooled across seasons
    F={f:i for i,f in enumerate(FI)}
    MB={"bat":[("xwOBA","xn","pa"),("wOBA","wn","pa"),("K%","k","pa"),("BB%","bb","pa"),
        ("whiff%","whf","sw"),("chase%","ozsw","oz"),("bat speed","sbs","nbs"),
        ("swing length","ssl","nbs"),("attack angle","saa","naa"),("attack direction","sad","naa"),
        ("exit velo","sev","nev"),("launch angle","sla","nev"),("hard-hit%","hh","nev"),
        ("barrel%","brl","nev"),("sweet-spot%","sweet","nev"),("ground-ball%","gb","nbb")],
        "pit":[("xwOBA against","xn","bf"),("wOBA against","wn","bf"),("K%","k","bf"),
        ("BB%","bb","bf"),("whiff%","whf","sw"),("zone%","iz","zt"),("chase induced%","ozsw","oz"),
        ("edge%","edge","loct"),("fastball velo","sv","nv"),("spin rate","ssp","nsp"),
        ("extension","sex","nex"),("arm angle","saa","naa"),("exit velo allowed","sev","nev"),
        ("hard-hit% allowed","hh","nev"),("ground-ball%","gb","nbb")]}[kind]
    A,B=[],[]
    for r in rows:
        ha=[0.0]*len(FI); hb=[0.0]*len(FI)
        for i,blk in enumerate(blocks):
            v=r["b"].get(blk)
            if not v: continue
            t=ha if i%2==0 else hb
            for j in range(len(FI)): t[j]+=v[j]
        if ha[0]>=60 and hb[0]>=60: A.append(ha); B.append(hb)
    A=np.array(A); B=np.array(B)
    REL={}
    print(f"  reliability from {len(A)} player-seasons, mean {A[:,0].mean():.0f} per half")
    for lab,num,den in MB:
        a=np.where(A[:,F[den]]>0,A[:,F[num]]/np.where(A[:,F[den]]==0,1,A[:,F[den]]),np.nan)
        b=np.where(B[:,F[den]]>0,B[:,F[num]]/np.where(B[:,F[den]]==0,1,B[:,F[den]]),np.nan)
        ok=np.isfinite(a)&np.isfinite(b)
        r=float(np.corrcoef(a[ok],b[ok])[0,1]); sb=max(2*r/(1+r),0.02)
        REL[lab]=dict(sb=sb,n0=float(A[:,0].mean()))
        print(f"    {lab:>20} {sb:>7.3f}")
    OUT[kind]["rel"]=REL
    OUT[kind]["blocks"]=blocks
Path("output").mkdir(exist_ok=True)
p=Path("output/blocks_all.json"); p.write_text(json.dumps(OUT,separators=(",",":")))
print("\nbytes:",p.stat().st_size)

# ---------------------------------------------------------------- split shards
# The combined file is what a local script wants. A web client wants the opposite:
# one visit looks at one player type in one season, so shipping all four seasons
# of both types makes the first paint wait on ~1.8 MB of gzip that nobody reads.
# Splitting by (kind, season) cuts the default payload about 10x; the rest load
# on demand when the user changes the selector.
#
# Every shard repeats `fields`, `blocks` and `rel`, which is a few KB of duplication
# and worth it -- a shard that cannot be interpreted without fetching a second file
# is not really a shard.
SPLIT = Path("output/blocks")
SPLIT.mkdir(parents=True, exist_ok=True)
index = {"generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
         "shards": {}}
for kind in OUT:
    years = sorted({r["y"] for r in OUT[kind]["rows"]})
    for y in years:
        shard = {"fields": OUT[kind]["fields"],
                 "blocks": [b for b in OUT[kind]["blocks"] if b.startswith(str(y))],
                 "rel":    OUT[kind]["rel"],
                 "rows":   [r for r in OUT[kind]["rows"] if r["y"] == y]}
        # Re-key each row's blocks to the shard's own index space, so a shard is
        # self-contained rather than carrying offsets into the full block list.
        bi = {b: i for i, b in enumerate(shard["blocks"])}
        full = OUT[kind]["blocks"]
        for r in shard["rows"]:
            r = dict(r)
            shard["rows"][shard["rows"].index(r)] = r
        shard["rows"] = [{**r, "b": {b: v for b, v in r["b"].items() if b in bi}}
                         for r in shard["rows"]]
        f = SPLIT / f"{kind}-{y}.json"
        f.write_text(json.dumps(shard, separators=(",", ":")))
        index["shards"][f"{kind}-{y}"] = {"path": f"blocks/{f.name}",
                                          "bytes": f.stat().st_size,
                                          "players": len(shard["rows"]),
                                          "blocks": len(shard["blocks"])}
        print(f"  shard {kind}-{y}: {f.stat().st_size/1024:>6.0f} KB  {len(shard['rows'])} players")
(SPLIT.parent / "blocks_index.json").write_text(json.dumps(index, indent=1))
print("wrote output/blocks_index.json")
