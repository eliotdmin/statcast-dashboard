import sqlite3, os, math
con = sqlite3.connect(f"file:{os.environ['HOME']}/snap.db?mode=ro", uri=True)
print("Is the REFERENCE zone itself stable? sz_top / sz_bot by year.")
print(f"{'yr':>5} {'n':>10} {'sz_top':>8} {'sd':>6} {'sz_bot':>8} {'sd':>6} {'height':>8}")
for y in (2023,2024,2025,2026):
    r = con.execute("""SELECT COUNT(*), AVG(sz_top), AVG(sz_top*sz_top), AVG(sz_bot),
        AVG(sz_bot*sz_bot) FROM pitches WHERE game_year=? AND game_type='R'
        AND sz_top IS NOT NULL""",(y,)).fetchone()
    n,a,aa,b,bb = r
    print(f"{y:>5} {n:>10,} {a:>8.4f} {math.sqrt(aa-a*a):>6.4f} {b:>8.4f} {math.sqrt(bb-b*b):>6.4f} {a-b:>8.4f}")
print("\nHow many DISTINCT sz_top values per year (operator estimate vs formula)?")
for y in (2024,2025,2026):
    n = con.execute("SELECT COUNT(DISTINCT sz_top) FROM pitches WHERE game_year=? AND game_type='R'",(y,)).fetchone()[0]
    v = con.execute("""SELECT COUNT(DISTINCT sz_top) FROM (SELECT sz_top FROM pitches
        WHERE game_year=? AND game_type='R' AND batter=(SELECT batter FROM pitches
        WHERE game_year=? AND game_type='R' LIMIT 1))""",(y,y)).fetchone()[0]
    print(f"  {y}: {n:>7,} distinct league-wide   {v:>6,} distinct for one single batter")
print("\nCalled-strike rate vs a FIXED geometric top (2.9 ft), immune to sz_top drift:")
print(f"{'yr':>5} " + " ".join(f"{b:>14}" for b in ['2.6-2.8','2.8-3.0','3.0-3.2','3.2-3.4']))
for y in (2024,2025,2026):
    cells=[]
    for lo,hi in ((2.6,2.8),(2.8,3.0),(3.0,3.2),(3.2,3.4)):
        cs,n = con.execute("""SELECT SUM(CASE WHEN description='called_strike' THEN 1 ELSE 0 END),
          COUNT(*) FROM pitches WHERE game_year=? AND game_type='R'
          AND description IN ('called_strike','ball','blocked_ball')
          AND ABS(plate_x)<=0.7 AND plate_z>=? AND plate_z<?""",(y,lo,hi)).fetchone()
        cells.append(f"{100*cs/n:>6.1f}% ({n//1000:>3}k)")
    print(f"{y:>5} " + " ".join(cells))
print("\nChallenge-era check: is there a 'challenge' event or overturn flag anywhere?")
cols=[r[1] for r in con.execute("PRAGMA table_info(pitches)")]
print("  candidates:", [c for c in cols if any(k in c.lower() for k in ('chal','review','overturn','abs'))] or "none")
