#!/usr/bin/env python3
"""Season-by-season surface lines for the Player tab's Season line.

    python3 lines.py        # reads web/data/{bat,pit}-*.json, writes web/data/lines-{bat,pit}.json

The Player tab loads one season's shard at a time, so on its own it cannot show a player's
earlier seasons. This sums each player's blocks per season into the handful of counters the
surface line needs -- a few hundred KB instead of every shard. It reads only the published shards,
so it needs no database and blocks_all.py runs it as its last step.
"""
import json, pathlib, sys

DATA = pathlib.Path(__file__).resolve().parent / "web" / "data"
KEEP = {"bat": ["g", "pa", "ab", "h1", "h2", "h3", "hr", "bb", "ibb", "hbp", "sf", "sh", "ci", "k", "wn"],
        "pit": ["g", "bf", "outs", "h", "hr", "bb", "ibb", "hbp", "k", "wn"]}


def build(kind):
    players, years = {}, []
    for p in sorted(DATA.glob(f"{kind}-*.json")):
        d = json.loads(p.read_text())
        F = {f: i for i, f in enumerate(d["fields"])}
        missing = [k for k in KEEP[kind] if k not in F]
        if missing:
            sys.exit(f"{p.name} lacks {missing}; re-run blocks_all.py")
        y = int(p.stem.split("-")[1]); years.append(y)
        for r in d["rows"]:
            tot = [0.0] * len(KEEP[kind])
            for v in r["b"].values():
                for j, k in enumerate(KEEP[kind]):
                    tot[j] += v[F[k]]
            players.setdefault(str(r["id"]), []).append(
                [y, r.get("tm", ""), r.get("pos", ""), [round(x, 3) for x in tot]])
    out = DATA / f"lines-{kind}.json"
    out.write_text(json.dumps({"generated_by": "lines.py", "fields": KEEP[kind],
                               "seasons": years, "players": players}, separators=(",", ":")))
    print(f"wrote {out.name}: {len(players)} players, {years[0]}-{years[-1]}, "
          f"{out.stat().st_size/1024:.0f} KB")


def main():
    for kind in KEEP:
        build(kind)


if __name__ == "__main__":
    main()
