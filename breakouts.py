#!/usr/bin/env python3
"""breakouts.py -- do two-week hot streaks "earned" by contact quality stick better than lucky ones?

    python3 breakouts.py            # two-week windows (one half-month block)
    python3 breakouts.py --blocks 2 # ~30-day windows; --blocks 3 for ~45 days
    python3 breakouts.py --career   # vs. career-to-date (2023 on), hot AND cold, |z| >= 2 only
    python3 breakouts.py --export web/data/breakouts.json   # the site's Breakouts tab

The analyst's line: "he's smacking the ball over the last two weeks -- he's earned his results."
This splits every two-week hot streak by whether contact quality (xwOBA) rose with it, then
measures how much of the wOBA gain survived the next two weeks and the rest of the season.

Descriptive only: no model is fit, so nothing here touches the 2026 holdout rule (D28).
2023-2025 is the headline; 2026 is reported separately so it can be compared, not pooled.

Data: web/data/bat-YYYY.json, per-player half-month block sums (corrected wOBA numerator, D24).
"""
import json, random, argparse
from pathlib import Path

ROOT = Path(__file__).parent
W = 1                  # window length in half-month blocks; set from --blocks
MIN_PA_NOW, MIN_PA_BASE, MIN_PA_NEXT, MIN_PA_ROS = 35, 100, 20, 50

# The follow-up every verdict is judged on. It used to be "the next window of the same length",
# which judged each streak against one more noisy sample of the same size -- a two-week streak
# checked against the following two weeks. Averaged over a hundred streaks that noise cancels
# (the aggregate `kept` barely moves when the follow-up is lengthened), but a PER-STREAK verdict
# has nothing to average it against: at 15 days, about two-thirds of the "stuck" calls were luck
# in the follow-up window (hot 20% -> 8% on a two-month horizon; cold 21% -> 7%).
#
# So the yardstick is now a FIXED horizon, the same for every streak length, and a streak is
# scored only if that whole horizon exists in the season. "Rest of season" was the other option
# and was rejected: it mixes horizons (a May streak gets four months, an August one gets one) and
# drops the players who got hurt or benched, who are disproportionately the slumping ones.
H = 4                  # forward horizon in half-month blocks (~2 months); set from --horizon
MIN_PA_FWD = 60        # a horizon this long with fewer PA than this is not a sample
HOT = 0.080            # two-week wOBA at least this far above his own earlier-season rate
EARNED, LUCKY = 0.050, 0.020   # xwOBA rise that counts as "earned" / stays under for "lucky"


def load(season):
    s = json.loads((ROOT / "web" / "data" / f"bat-{season}.json").read_text())
    F = {f: i for i, f in enumerate(s["fields"])}
    return s["blocks"], s["rows"], F


def summed(row, blocks, F):
    out = {"pa": 0.0, "wn": 0.0, "xn": 0.0, "hh": 0.0, "nev": 0.0}
    for b in blocks:
        v = row["b"].get(b)
        if v:
            for k in out:
                out[k] += v[F[k]]
    return out


def forward(r, blocks, F, start, base_w, base_x):
    """The fixed-horizon follow-up for a streak ending just before `start`.

    Returns (gap, xgap, pa, status). status is "ok", "too_late" (the whole horizon is not in
    the season, so the streak cannot be scored on an equal footing) or "few_pa" (it is, but he
    barely played in it -- hurt, benched or optioned)."""
    if start + H > len(blocks):
        return None, None, 0.0, "too_late"
    f = summed(r, blocks[start:start + H], F)
    if f["pa"] < MIN_PA_FWD:
        return None, None, f["pa"], "few_pa"
    return f["wn"] / f["pa"] - base_w, f["xn"] / f["pa"] - base_x, f["pa"], "ok"


def streaks(season):
    blocks, rows, F = load(season)
    found = []
    for r in rows:
        for t in range(1, len(blocks) - 2 * W + 1):
            base = summed(r, blocks[:t], F)
            now = summed(r, blocks[t:t + W], F)
            if base["pa"] < MIN_PA_BASE or now["pa"] < MIN_PA_NOW * W:
                continue
            wb, xb = base["wn"] / base["pa"], base["xn"] / base["pa"]
            gap = now["wn"] / now["pa"] - wb
            if gap < HOT:
                continue
            xgap = now["xn"] / now["pa"] - xb
            hhb = base["hh"] / base["nev"] if base["nev"] else None
            hhn = now["hh"] / now["nev"] if now["nev"] else None
            nxt = summed(r, blocks[t + W:t + 2 * W], F)
            ros = summed(r, blocks[t + W:], F)
            found.append({
                "player": r["n"], "id": r["id"], "block": blocks[t], "pa": now["pa"],
                "gap": gap, "xgap": xgap,
                "hh_up": (hhn - hhb) if (hhb is not None and hhn is not None) else None,
                "next_pa": nxt["pa"],
                "next_gap": (nxt["wn"] / nxt["pa"] - wb) if nxt["pa"] >= MIN_PA_NEXT * W else None,
                "next_xgap": (nxt["xn"] / nxt["pa"] - xb) if nxt["pa"] >= MIN_PA_NEXT * W else None,
                "ros_pa": ros["pa"],
                "ros_gap": (ros["wn"] / ros["pa"] - wb) if ros["pa"] >= MIN_PA_ROS else None,
            })
            fg, fx, fpa, fst = forward(r, blocks, F, t + W, wb, xb)
            found[-1].update({"fwd_gap": fg, "fwd_xgap": fx, "fwd_pa": fpa, "fwd_status": fst})
    return found


S2 = 0.2258            # per-PA variance of wOBA outcomes (FINDINGS: noise-ceiling decomposition)
Z_MIN, MIN_PA_CAREER = 2.0, 300


def prior_totals(season):
    """Per-player sums over every season in the shards before this one (the data starts in 2023)."""
    tot = {}
    for y in range(2023, season):
        blocks, rows, F = load(y)
        for r in rows:
            t = tot.setdefault(r["id"], {"pa": 0.0, "wn": 0.0, "xn": 0.0, "hh": 0.0, "nev": 0.0})
            for k, v in summed(r, blocks, F).items():
                t[k] += v
    return tot


def flip(s):
    """A cold streak with every gap sign-reversed, so summarize()/boot_diff() read it like a hot one:
    'kept' is the share of the slump that persisted, 'earned' means contact fell with it."""
    o = dict(s)
    for k in ("gap", "xgap", "next_gap", "next_xgap", "ros_gap", "fwd_gap", "fwd_xgap", "hh_up"):
        if o.get(k) is not None:
            o[k] = -o[k]
    return o


def streaks_career(season):
    """Hot and cold windows measured against career-to-date (every earlier block in the shards,
    prior seasons included), kept only when |z| >= Z_MIN against sampling noise in BOTH the window
    and the baseline. Cold streaks are returned flipped (see flip); s["dir"] says which."""
    blocks, rows, F = load(season)
    prior = prior_totals(season)
    found = []
    for r in rows:
        pr = prior.get(r["id"], {"pa": 0.0, "wn": 0.0, "xn": 0.0, "hh": 0.0, "nev": 0.0})
        for t in range(0, len(blocks) - 2 * W + 1):
            here = summed(r, blocks[:t], F)
            base = {k: pr[k] + here[k] for k in pr}
            now = summed(r, blocks[t:t + W], F)
            if base["pa"] < MIN_PA_CAREER or now["pa"] < MIN_PA_NOW * W:
                continue
            wb, xb = base["wn"] / base["pa"], base["xn"] / base["pa"]
            gap = now["wn"] / now["pa"] - wb
            z = gap / (S2 * (1 / now["pa"] + 1 / base["pa"])) ** 0.5
            if abs(z) < Z_MIN:
                continue
            nxt = summed(r, blocks[t + W:t + 2 * W], F)
            ros = summed(r, blocks[t + W:], F)
            hhb = base["hh"] / base["nev"] if base["nev"] else None
            hhn = now["hh"] / now["nev"] if now["nev"] else None
            s = {"player": r["n"], "id": r["id"], "block": blocks[t], "pa": now["pa"],
                 "base_pa": base["pa"], "baseline": wb, "z": z, "dir": "hot" if z > 0 else "cold",
                 "gap": gap, "xgap": now["xn"] / now["pa"] - xb,
                 "hh_up": (hhn - hhb) if (hhb is not None and hhn is not None) else None,
                 "next_pa": nxt["pa"],
                 "next_gap": (nxt["wn"] / nxt["pa"] - wb) if nxt["pa"] >= MIN_PA_NEXT * W else None,
                 "next_xgap": (nxt["xn"] / nxt["pa"] - xb) if nxt["pa"] >= MIN_PA_NEXT * W else None,
                 "ros_pa": ros["pa"],
                 "ros_gap": (ros["wn"] / ros["pa"] - wb) if ros["pa"] >= MIN_PA_ROS else None}
            fg, fx, fpa, fst = forward(r, blocks, F, t + W, wb, xb)
            s.update({"fwd_gap": fg, "fwd_xgap": fx, "fwd_pa": fpa, "fwd_status": fst})
            found.append(s if z > 0 else flip(s))
    return found


def summarize(group):
    """Retention and per-streak verdicts, judged on the fixed forward horizon.

    `keep_next` -- the old equal-length measure -- is still computed so the two can be compared,
    but every headline figure and every verdict now comes from the fixed horizon."""
    fwd = [x for x in group if x.get("fwd_status") == "ok"]
    nxt = [x for x in group if x["next_gap"] is not None]
    if not fwd:
        return None
    def wmean(xs, key, w):
        tw = sum(x[w] for x in xs)
        return sum(x[key] * x[w] for x in xs) / tw
    keep = wmean(fwd, "fwd_gap", "fwd_pa") / wmean(fwd, "gap", "fwd_pa")
    keep_next = (wmean(nxt, "next_gap", "next_pa") / wmean(nxt, "gap", "next_pa")) if nxt else None
    return {
        "n": len(fwd),                                           # streaks actually scored
        "too_late": sum(x.get("fwd_status") == "too_late" for x in group),
        "dropped": sum(x.get("fwd_status") == "few_pa" for x in group),  # hurt / benched / optioned
        "gap": wmean(fwd, "gap", "fwd_pa"),
        "fwd_gap": wmean(fwd, "fwd_gap", "fwd_pa"),
        "keep": keep,
        "keep_next": keep_next,
        "stuck": sum(x["fwd_gap"] >= 0.5 * x["gap"] for x in fwd) / len(fwd),
        "kaput": sum(x["fwd_gap"] <= 0 for x in fwd) / len(fwd),
        "xkeep": (wmean(fwd, "fwd_xgap", "fwd_pa") / wmean(fwd, "xgap", "fwd_pa"))
                 if abs(wmean(fwd, "xgap", "fwd_pa")) > 0.01 else None,
    }


def boot_diff(a, b, reps=2000, seed=7):
    """95% CI for keep(a) - keep(b), resampling players (streaks cluster by player)."""
    rnd = random.Random(seed)
    def by_player(g):
        d = {}
        for s in g:
            if s.get("fwd_status") == "ok":
                d.setdefault(s["id"], []).append(s)
        return list(d.values())
    pa, pb = by_player(a), by_player(b)
    diffs = []
    for _ in range(reps):
        sa = [s for p in (rnd.choice(pa) for _ in pa) for s in p]
        sb = [s for p in (rnd.choice(pb) for _ in pb) for s in p]
        ra, rb = summarize(sa), summarize(sb)
        if ra and rb:
            diffs.append(ra["keep"] - rb["keep"])
    diffs.sort()
    return diffs[int(.025 * reps)], diffs[int(.975 * reps)]


def report(label, found, what=None):
    earned = [s for s in found if s["xgap"] >= EARNED]
    lucky = [s for s in found if s["xgap"] < LUCKY]
    middle = [s for s in found if LUCKY <= s["xgap"] < EARNED]
    hh_earned = [s for s in found if s["hh_up"] is not None and s["hh_up"] >= 0.08]
    hh_lucky = [s for s in found if s["hh_up"] is not None and s["hh_up"] < 0.0]
    what = what or f"hot streaks (wOBA >= +{HOT:.3f} over his own earlier-season rate)"
    print(f"\n=== {label}: {len(found)} ~{15 * W}-day {what}")
    print(f"    judged on the next {H} half-months (~{15 * H} days); "
          f"'next win' is the old equal-length measure, for comparison")
    print(f"{'group':<34}{'n':>5}{'late':>5}{'drop':>5}{'gap':>8}{'after':>8}{'kept':>7}"
          f"{'next win':>9}{'stuck':>7}{'kaput':>7}{'xwOBA kept':>11}")
    rows = [("all hot streaks", found),
            (f"earned  (xwOBA up >= {EARNED:.3f})", earned),
            (f"partial (xwOBA up {LUCKY:.3f}-{EARNED:.3f})", middle),
            (f"lucky   (xwOBA up < {LUCKY:.3f})", lucky),
            ("robustness: hard-hit% up >= 8 pts", hh_earned),
            ("robustness: hard-hit% down", hh_lucky)]
    for name, g in rows:
        r = summarize(g)
        if not r:
            continue
        kn = f"{r['keep_next']:.0%}" if r["keep_next"] is not None else "--"
        xk = f"{r['xkeep']:.0%}" if r["xkeep"] is not None else "--"
        print(f"{name:<34}{r['n']:>5}{r['too_late']:>5}{r['dropped']:>5}{r['gap']:>+8.3f}"
              f"{r['fwd_gap']:>+8.3f}{r['keep']:>7.0%}{kn:>9}{r['stuck']:>7.0%}{r['kaput']:>7.0%}{xk:>11}")
    if min(len(earned), len(lucky), len(hh_earned), len(hh_lucky)) < 10:
        print("(a group has fewer than 10 streaks: no bootstrap)")
        return
    lo, hi = boot_diff(earned, lucky)
    print(f"earned minus lucky, share of gain kept over {15*H} days: 95% CI [{lo:+.0%}, {hi:+.0%}]"
          f" (bootstrap over players)")
    lo, hi = boot_diff(hh_earned, hh_lucky)
    print(f"hard-hit up minus hard-hit down, same measure:      95% CI [{lo:+.0%}, {hi:+.0%}]")


def ladder_row(found, w, label, ci):
    row = {"blocks": w, "seasons": label}
    groups = (("all", found), ("earned", [s for s in found if s["xgap"] >= EARNED]),
              ("lucky", [s for s in found if s["xgap"] < LUCKY]))
    for name, g in groups:
        r = summarize(g)
        row[name] = None if r is None else {
            "n": r["n"], "kept": round(r["keep"], 3),
            "kept_next": None if r["keep_next"] is None else round(r["keep_next"], 3),
            "stuck": round(r["stuck"], 3), "kaput": round(r["kaput"], 3),
            "too_late": r["too_late"], "dropped": r["dropped"]}
    if ci and row["earned"] and row["lucky"] and row["earned"]["n"] >= 10 and row["lucky"]["n"] >= 10:
        lo, hi = boot_diff(groups[1][1], groups[2][1])
        row["earned_minus_lucky_ci"] = [round(lo, 3), round(hi, 3)]
    return row


def case(s, season, sign=1):
    """One case-study card. Gaps are written back in their real sign (cold ones were flipped)."""
    blocks, rows, F = load(season)
    r = next(x for x in rows if x["id"] == s["id"])
    path = []
    for b in blocks:
        v = r["b"].get(b)
        pa = v[F["pa"]] if v else 0
        path.append({"b": b, "pa": pa, "w": round(v[F["wn"]] / pa, 3) if pa >= 15 else None})
    if "baseline" in s:
        base = s["baseline"]
    else:
        t = blocks.index(s["block"])
        b = summed(r, blocks[:t], F)
        base = b["wn"] / b["pa"]
    nxt = s["next_gap"]
    fg = s.get("fwd_gap")
    outcome = ({"too_late": "too_late", "few_pa": "no_next"}.get(s.get("fwd_status"))
               or ("stuck" if fg >= 0.5 * s["gap"] else "kaput" if fg <= 0 else "faded"))
    rd = lambda x: None if x is None else round(sign * x, 3)
    return {"player": s["player"], "season": season, "block": s["block"], "pa": s["pa"],
            "dir": s.get("dir", "hot"), "z": None if "z" not in s else round(s["z"], 1),
            "base_pa": s.get("base_pa"), "baseline": round(base, 3),
            "gap": rd(s["gap"]), "xgap": rd(s["xgap"]), "next_gap": rd(nxt),
            "fwd_gap": rd(fg), "ros_gap": rd(s["ros_gap"]), "outcome": outcome, "path": path}


def top_cases(found, season, k=3, sign=1):
    """Chosen by rule, not by story: the k distinct hitters with the largest contact-quality move
    in the streak's own direction, whatever happened next."""
    out, seen = [], set()
    for s in sorted((s for s in found if s["xgap"] >= EARNED), key=lambda s: -s["xgap"]):
        if s["id"] not in seen:
            seen.add(s["id"])
            out.append(case(s, season, sign))
        if len(out) == k:
            break
    return out


def export(dest):
    """Write the site's Breakouts tab data: both baselines, each with its ladder and case studies."""
    global W
    season_view = {"ladder": [], "cases": []}
    career_view = {"ladder": [], "cases": []}
    for w in (1, 2, 3):
        W = w
        for label, seasons in (("2023-2025", (2023, 2024, 2025)), ("2026", (2026,))):
            found = [s for y in seasons for s in streaks(y)]
            season_view["ladder"].append(ladder_row(found, w, label, label != "2026"))
        # career-to-date: 2023 has no prior season in the data, so the headline is 2024-2025
        by_year = {y: streaks_career(y) for y in (2024, 2025, 2026)}
        for label, seasons in (("2024-2025", (2024, 2025)), ("2026", (2026,))):
            found = [s for y in seasons for s in by_year[y]]
            for d in ("hot", "cold"):
                row = ladder_row([s for s in found if s["dir"] == d], w, label, label != "2026")
                row["dir"] = d
                career_view["ladder"].append(row)
        if w == 1:
            for y in (2024, 2025):
                career_view["cases"] += top_cases([s for s in by_year[y] if s["dir"] == "hot"], y)
            for y in (2024, 2025):
                career_view["cases"] += top_cases([s for s in by_year[y] if s["dir"] == "cold"], y, sign=-1)
    W = 1
    for y in (2023, 2024, 2025):
        season_view["cases"] += top_cases(streaks(y), y)
    out = {"generated_by": "breakouts.py --export", "hot": HOT, "earned": EARNED, "lucky": LUCKY,
           "horizon_blocks": H, "horizon_days": 15 * H,
           "z_min": Z_MIN, "min_pa_career": MIN_PA_CAREER,
           "views": {"season": season_view, "career": career_view}}
    Path(dest).write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {dest}: season {len(season_view['cases'])} cases, career {len(career_view['cases'])} cases")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=1, help="window length in half-month blocks")
    ap.add_argument("--horizon", type=int, default=H,
                    help="forward horizon every verdict is judged on, in half-month blocks")
    ap.add_argument("--career", action="store_true",
                    help="baseline = career-to-date (2023 on); hot and cold; |z| >= 2 only")
    ap.add_argument("--export", metavar="PATH", help="write the site's breakouts JSON and exit")
    args = ap.parse_args()
    if args.export:
        export(args.export)
        raise SystemExit
    W = args.blocks
    H = args.horizon
    if args.career:
        print(f"window = {W} half-month block(s) vs. career-to-date (2023 on), |z| >= {Z_MIN}, "
              f"career PA >= {MIN_PA_CAREER}; cold streaks sign-flipped")
        for label, ys in (("2024-2025 (headline)", (2024, 2025)), ("2026 (separately, D28)", (2026,))):
            found = [s for y in ys for s in streaks_career(y)]
            for d in ("hot", "cold"):
                report(f"{label}, {d}", [s for s in found if s["dir"] == d],
                       f"{d} streaks, |z| >= {Z_MIN} vs. career-to-date (cold sign-flipped)")
        raise SystemExit
    print(f"window = {W} half-month block(s), ~{15 * W} days; judged on the next {H} (~{15*H} days)")
    clean = [s for y in (2023, 2024, 2025) for s in streaks(y)]
    report("2023-2025 (headline)", clean)
    report("2026 (reported separately, D28)", streaks(2026))
    print(f"\nkept = PA-weighted gain over the next {15*H} days / the streak's gain. stuck = still at"
          "\nleast half as far above baseline over that horizon. kaput = at or below his own baseline."
          f"\nlate = too late in the season for the full {15*H}-day horizon: not scored. drop = the horizon"
          "\nexists but he barely played in it (hurt, benched, optioned) -- also not scored, which biases"
          "\nthe verdicts slightly toward players who kept playing.")
