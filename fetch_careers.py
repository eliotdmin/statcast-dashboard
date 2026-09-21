#!/usr/bin/env python3
"""Official MLB season lines, every season of every player on the site, from the MLB Stats API.

    python3 fetch_careers.py            # -> web/data/careers-bat.json, careers-pit.json
    python3 fetch_careers.py --only bat

Run on the Mac: it fetches (statsapi.mlb.com), and the sandbox has no egress (CLAUDE.md).

Why this exists
---------------
The Season line on the Player tab could only show 2023 on, because that is where the pitch-level
archive starts. The Stats API publishes every MLB season a player has, with official counting
stats, so the line can show a whole career. It also carries birth dates, which Marcel's age
adjustment needs (matchup.py's naive baselines).

Only MLB rows are kept (sport id 1). A season split across teams is taken from the API's combined
row, labelled with every team he played for that year.
"""
import argparse, json, pathlib, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "web" / "data"
API = "https://statsapi.mlb.com/api/v1"
GROUP = {"bat": "hitting", "pit": "pitching"}
KEEP = {
    "bat": ["gamesPlayed", "plateAppearances", "atBats", "runs", "hits", "doubles", "triples",
            "homeRuns", "rbi", "baseOnBalls", "intentionalWalks", "strikeOuts", "hitByPitch",
            "sacFlies", "sacBunts", "stolenBases", "caughtStealing", "catchersInterference"],
    "pit": ["gamesPlayed", "gamesStarted", "wins", "losses", "saves", "inningsPitched",
            "battersFaced", "hits", "doubles", "triples", "homeRuns", "baseOnBalls",
            "intentionalWalks", "strikeOuts", "hitByPitch", "earnedRuns", "runs"],
}


def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.load(r)
        except Exception as e:                       # the API rate-limits bursts; back off
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def teams():
    """team id -> abbreviation, including franchises that have since moved or been renamed."""
    out = {}
    for season in range(2008, 2027, 3):
        for t in get(f"{API}/teams?sportId=1&season={season}")["teams"]:
            out[t["id"]] = t.get("abbreviation", t.get("teamName", ""))
    return out


def num(v):
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


def ip_outs(ip):
    """'190.2' innings -> 572 outs (the decimal is thirds, not tenths)."""
    whole, _, frac = str(ip).partition(".")
    return int(whole or 0) * 3 + int(frac or 0)


def career(kind, pid, abbr):
    d = get(f"{API}/people/{pid}/stats?stats=yearByYear&group={GROUP[kind]}")
    by_year = {}
    for s in d["stats"][0]["splits"] if d.get("stats") else []:
        if s.get("sport", {}).get("id") != 1:
            continue
        y = int(s["season"])
        e = by_year.setdefault(y, {"teams": [], "combined": None, "rows": []})
        if s.get("team"):
            e["teams"].append(abbr.get(s["team"]["id"], s["team"].get("name", "")))
            e["rows"].append(s["stat"])
        else:
            e["combined"] = s["stat"]
    seasons = []
    for y in sorted(by_year):
        e = by_year[y]
        st = e["combined"] or (e["rows"][0] if len(e["rows"]) == 1 else None)
        if st is None:                               # several teams and no combined row: sum them
            st = {k: sum(num(r.get(k, 0)) for r in e["rows"]) for k in KEEP[kind]}
            if kind == "pit":
                st["_outs"] = sum(ip_outs(r.get("inningsPitched", 0)) for r in e["rows"])
        row = [y, "/".join(e["teams"])]
        for k in KEEP[kind]:
            v = st.get(k, 0)
            if k == "inningsPitched":
                row.append(st["_outs"] if "_outs" in st else ip_outs(v))
            else:
                row.append(num(v))
        seasons.append(row)
    return seasons


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(GROUP))
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    abbr = teams()
    for kind in ([a.only] if a.only else list(GROUP)):
        lines = json.loads((DATA / f"lines-{kind}.json").read_text())
        ids = sorted(lines["players"], key=int)
        born = {}
        for i in range(0, len(ids), 150):            # birth dates, 150 players a request
            chunk = ",".join(ids[i:i + 150])
            for p in get(f"{API}/people?personIds={chunk}&fields=people,id,birthDate")["people"]:
                born[str(p["id"])] = p.get("birthDate", "")
        t0, out, failed = time.time(), {}, []
        with ThreadPoolExecutor(a.workers) as ex:
            for pid, res in zip(ids, ex.map(lambda p: _safe(kind, p, abbr), ids)):
                if res is None:
                    failed.append(pid)
                else:
                    out[pid] = {"born": born.get(pid, ""), "s": res}
        fields = ["year", "team"] + KEEP[kind]
        if kind == "pit":
            fields[fields.index("inningsPitched")] = "outs"
        path = DATA / f"careers-{kind}.json"
        path.write_text(json.dumps({"generated_by": "fetch_careers.py", "source": "statsapi.mlb.com",
                                    "fetched": time.strftime("%Y-%m-%d"), "fields": fields,
                                    "players": out}, separators=(",", ":")))
        print(f"{kind}: {len(out)} players, {sum(len(v['s']) for v in out.values())} seasons, "
              f"{path.stat().st_size/1024:.0f} KB, {time.time()-t0:.0f}s"
              + (f"; FAILED {len(failed)}: {failed[:10]}" if failed else ""))
        if failed:
            sys.exit(1)


def _safe(kind, pid, abbr):
    try:
        return career(kind, pid, abbr)
    except Exception as e:
        print(f"  {kind} {pid}: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    main()
