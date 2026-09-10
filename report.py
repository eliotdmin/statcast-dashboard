#!/usr/bin/env python3
"""Render output/audit.json as a self-contained HTML report.

    python3 audit.py && python3 report.py

The file it writes opens directly in a browser and is also publishable as an
artifact as-is (no doctype/head/body wrapper, by design).
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "output" / "audit.json"
OUT = ROOT / "output" / "audit_report.html"


def esc(x):
    return html.escape(str(x))


def sev(pct):
    """Severity class for a coverage percentage. Status colour, always labelled."""
    if pct is None:
        return "s-none"
    if pct >= 99.5:
        return "s-full"
    if pct >= 90:
        return "s-high"
    if pct >= 50:
        return "s-mid"
    if pct > 0:
        return "s-low"
    return "s-zero"


def coverage_section(cov, years):
    # Worst-first: the columns that need a decision float to the top.
    def worst(item):
        vals = [v["pct"] for v in item[1]["by_year"].values() if v["pct"] is not None]
        return min(vals) if vals else -1
    items = sorted(cov.items(), key=worst)

    head = "".join(f"<th>{y}</th>" for y in years)
    rows = []
    for name, info in items:
        cells = []
        for y in years:
            v = info["by_year"].get(str(y), {})
            pct, denom = v.get("pct"), v.get("denom")
            label = "—" if pct is None else f"{pct:g}%"
            title = f"{v.get('present',0):,} of {denom:,}" if denom else "no rows"
            cells.append(f'<td class="cell {sev(pct)}" title="{esc(title)}">{label}</td>')
        dead = ' <span class="tag">dead</span>' if info["dead"] else ""
        rows.append(
            f'<tr><th class="colname"><code>{esc(name)}</code>{dead}'
            f'<span class="cond">{esc(info["condition"])}</span></th>{"".join(cells)}</tr>')
    return f"""
<table class="grid">
  <thead><tr><th class="colname">column <span class="cond">measured against</span></th>{head}</tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>"""


def integrity_section(checks):
    out = []
    for c in checks:
        cls = "ok" if c["ok"] else "bad"
        mark = "PASS" if c["ok"] else "FAIL"
        out.append(f"""
<li class="check {cls}">
  <div class="check-head"><span class="chip {cls}">{mark}</span><h3>{esc(c['name'])}</h3></div>
  <p class="detail"><code>{esc(c['detail'])}</code></p>
  <p class="why">{esc(c['why'])}</p>
</li>""")
    return f'<ul class="checks">{"".join(out)}</ul>'


def season_section(by_season):
    rows = []
    for y, s in sorted(by_season.items()):
        pg = s.get("games_vs_2430")
        cls = sev(pg if pg is not None else None)
        rows.append(f"""<tr>
<th>{esc(y)}</th>
<td>{s['pitches']:,}</td>
<td>{s['games']:,}</td>
<td class="cell {cls}">{'—' if pg is None else f'{pg:g}%'}</td>
<td>{s['pitches_per_game'] or '—'}</td>
<td>{s['days_with_games']}</td>
<td>{s['offdays']}</td>
<td>{s['days_logged']}</td>
</tr>""")
    return f"""
<div class="scroll"><table class="tabular">
<thead><tr><th>season</th><th>pitches</th><th>games</th><th>of 2,430</th>
<th>pitches/game</th><th>game days</th><th>off days</th><th>days logged</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""


def dist_section(dists, years):
    if not dists:
        return "<p class='why'>Run <code>audit.py</code> without <code>--quick</code> to include distributions.</p>"
    blocks = []
    for col, per_year in dists.items():
        bounds = next(iter(per_year.values()))["bounds"]
        rows = []
        for y in years:
            s = per_year.get(str(y))
            if not s:
                continue
            bad = s["implausible_pct"]
            badcls = "s-full" if bad == 0 else ("s-mid" if bad < 0.1 else "s-low")
            rows.append(f"""<tr><th>{y}</th><td>{s['n']:,}</td><td>{s['mean']:g}</td>
<td>{s['sd']:g}</td><td>{s['min']:g}</td><td>{s['p1']:g}</td><td>{s['p25']:g}</td>
<td>{s['p50']:g}</td><td>{s['p75']:g}</td><td>{s['p99']:g}</td><td>{s['max']:g}</td>
<td class="cell {badcls}">{bad:g}%</td></tr>""")
        blocks.append(f"""
<section class="dist">
  <h3><code>{esc(col)}</code><span class="cond">plausible range {bounds[0]} to {bounds[1]}</span></h3>
  <div class="scroll"><table class="tabular">
  <thead><tr><th>season</th><th>n</th><th>mean</th><th>sd</th><th>min</th><th>p1</th>
  <th>p25</th><th>median</th><th>p75</th><th>p99</th><th>max</th><th>outside range</th></tr></thead>
  <tbody>{''.join(rows)}</tbody></table></div>
</section>""")
    return "".join(blocks)


def recon_section(rec):
    if isinstance(rec, dict):
        return f"<p class='why'>Not available: {esc(rec.get('error'))}</p>"
    if not rec:
        return "<p class='why'>No leaderboard snapshots to reconcile yet.</p>"
    rows = []
    for r in rec:
        cov = r["median_pa_coverage"]
        cls = sev(cov * 100)
        rows.append(f"""<tr><th>{r['year']}</th><td>{esc(r['snapshot'])}</td>
<td>{r['n_players']}</td><td>{r['median_woba_diff']:+.4f}</td>
<td class="cell {cls}">{cov*100:.1f}%</td></tr>""")
    return f"""
<div class="scroll"><table class="tabular">
<thead><tr><th>season</th><th>snapshot</th><th>players</th>
<th>median wOBA difference</th><th>PA found in pitch table</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>"""


def main():
    d = json.loads(SRC.read_text())
    years = d["seasons"]
    n_fail = sum(1 for c in d["integrity"] if not c["ok"])
    gb = d["db_bytes"] / 1e9

    body = f"""<title>Statcast Data Audit</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Condensed:wght@600;700&display=swap">
<style>
:root {{
  color-scheme: light;
  --ground:#fbfcfd; --panel:#ffffff; --line:#dfe4ea; --line-soft:#eef1f5;
  --ink:#10141a; --ink-2:#4d5765; --ink-3:#78828f;
  --accent:#1c5cab;
  --full-bg:#eef1f5; --full-ink:#4d5765;
  --high-bg:#cde2fb; --high-ink:#0d366b;
  --mid-bg:#fdefc9;  --mid-ink:#6b4a00;
  --low-bg:#fadedd;  --low-ink:#8c1f1e;
  --zero-bg:#e6e9ee; --zero-ink:#78828f;
  --ok:#0a6b33; --ok-bg:#e2f2e8; --bad:#b3231f; --bad-bg:#fbe7e6;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --ground:#0f1216; --panel:#171b21; --line:#2b323b; --line-soft:#222831;
    --ink:#f2f5f8; --ink-2:#aab4c0; --ink-3:#7c8794;
    --accent:#6da7ec;
    --full-bg:#222831; --full-ink:#aab4c0;
    --high-bg:#184f95; --high-ink:#dbeafd;
    --mid-bg:#5a3f00;  --mid-ink:#ffe4a3;
    --low-bg:#6b1b19;  --low-ink:#ffd9d7;
    --zero-bg:#1d222a; --zero-ink:#6b7583;
    --ok:#5ec98a; --ok-bg:#12321f; --bad:#f28b87; --bad-bg:#3a1513;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --ground:#0f1216; --panel:#171b21; --line:#2b323b; --line-soft:#222831;
  --ink:#f2f5f8; --ink-2:#aab4c0; --ink-3:#7c8794;
  --accent:#6da7ec;
  --full-bg:#222831; --full-ink:#aab4c0;
  --high-bg:#184f95; --high-ink:#dbeafd;
  --mid-bg:#5a3f00;  --mid-ink:#ffe4a3;
  --low-bg:#6b1b19;  --low-ink:#ffd9d7;
  --zero-bg:#1d222a; --zero-ink:#6b7583;
  --ok:#5ec98a; --ok-bg:#12321f; --bad:#f28b87; --bad-bg:#3a1513;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:1080px; margin:0 auto; padding-block:48px 96px; padding-left:20px; padding-right:20px; display:flex; flex-direction:column; gap:56px; }}
code {{ font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:0.92em; }}
h1 {{ font-family:"IBM Plex Sans Condensed","IBM Plex Sans",sans-serif; font-weight:700;
     font-size:clamp(30px,5vw,42px); letter-spacing:-0.015em; margin:0; text-wrap:balance; }}
h2 {{ font-family:"IBM Plex Sans Condensed","IBM Plex Sans",sans-serif; font-weight:700;
     font-size:21px; margin:0 0 4px; letter-spacing:-0.01em; }}
h3 {{ font-size:15px; font-weight:600; margin:0; }}
.eyebrow {{ font-size:11px; font-weight:600; letter-spacing:0.11em; text-transform:uppercase;
           color:var(--ink-3); margin:0 0 10px; }}
.lede {{ color:var(--ink-2); max-width:64ch; margin:10px 0 0; }}
.figures {{ display:flex; flex-wrap:wrap; gap:28px 44px; margin-top:28px;
           padding-top:24px; border-top:1px solid var(--line); }}
.fig .k {{ font-family:"IBM Plex Mono",monospace; font-size:26px; font-weight:500;
          font-variant-numeric:tabular-nums; letter-spacing:-0.02em; display:block; }}
.fig .l {{ font-size:11px; letter-spacing:0.09em; text-transform:uppercase; color:var(--ink-3); }}
section > .why {{ color:var(--ink-2); max-width:66ch; margin:0 0 18px; }}
.checks {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:2px; }}
.check {{ background:var(--panel); border:1px solid var(--line-soft); border-left:3px solid var(--ok);
         padding:14px 18px; }}
.check.bad {{ border-left-color:var(--bad); }}
.check-head {{ display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }}
.chip {{ font-family:"IBM Plex Mono",monospace; font-size:10px; font-weight:500; letter-spacing:0.07em;
        padding:2px 7px; border-radius:3px; background:var(--ok-bg); color:var(--ok); }}
.chip.bad {{ background:var(--bad-bg); color:var(--bad); }}
.detail {{ margin:8px 0 4px; color:var(--ink); word-break:break-word; }}
.why {{ margin:0; color:var(--ink-2); font-size:13.5px; max-width:74ch; }}
.scroll {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }}
.tabular th, .tabular td {{ text-align:right; padding:7px 12px; border-bottom:1px solid var(--line-soft);
                           font-family:"IBM Plex Mono",monospace; font-size:13px; white-space:nowrap; }}
.tabular thead th {{ text-align:right; font-family:"IBM Plex Sans",sans-serif; font-size:11px;
                    letter-spacing:0.06em; text-transform:uppercase; color:var(--ink-3); font-weight:600;
                    border-bottom:1px solid var(--line); }}
.tabular tbody th {{ text-align:left; font-weight:600; }}
.grid {{ font-size:13px; }}
.grid th, .grid td {{ border-bottom:1px solid var(--line-soft); padding:5px 10px; }}
.grid thead th {{ font-family:"IBM Plex Sans",sans-serif; font-size:11px; letter-spacing:0.06em;
                 text-transform:uppercase; color:var(--ink-3); font-weight:600; text-align:center;
                 border-bottom:1px solid var(--line); }}
.grid thead th.colname {{ text-align:left; }}
.colname {{ text-align:left; font-weight:400; white-space:nowrap; }}
.cond {{ display:block; font-size:11px; color:var(--ink-3); font-family:"IBM Plex Sans",sans-serif;
        letter-spacing:0.01em; text-transform:none; }}
.cell {{ text-align:center; font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums;
        white-space:nowrap; }}
.s-full {{ background:var(--full-bg); color:var(--full-ink); }}
.s-high {{ background:var(--high-bg); color:var(--high-ink); }}
.s-mid  {{ background:var(--mid-bg);  color:var(--mid-ink); font-weight:600; }}
.s-low  {{ background:var(--low-bg);  color:var(--low-ink); font-weight:600; }}
.s-zero {{ background:var(--zero-bg); color:var(--zero-ink); }}
.s-none {{ color:var(--ink-3); text-align:center; }}
.tag {{ font-size:10px; letter-spacing:0.06em; text-transform:uppercase; color:var(--ink-3);
       border:1px solid var(--line); padding:0 4px; border-radius:2px; }}
.dist {{ margin-bottom:26px; }}
.dist h3 {{ margin-bottom:6px; }}
.legend {{ display:flex; flex-wrap:wrap; gap:8px; margin:0 0 16px; font-size:11.5px;
          font-family:"IBM Plex Mono",monospace; }}
.legend span {{ padding:2px 8px; }}
footer {{ border-top:1px solid var(--line); padding-top:18px; color:var(--ink-3); font-size:13px; }}
@media (max-width:640px) {{ .figures {{ gap:20px 28px; }} .fig .k {{ font-size:21px; }} }}
</style>

<div class="wrap">
<header>
  <p class="eyebrow">statcast-dashboard &middot; data integrity</p>
  <h1>Statcast Data Audit</h1>
  <p class="lede">Coverage, distributions and integrity for the pitch-level database.
  Nulls are measured against what each column is actually <em>supposed</em> to be
  populated on, so structural absence and real tracking gaps are never mixed together.</p>
  <div class="figures">
    <div class="fig"><span class="k">{d['total_pitches']:,}</span><span class="l">pitches</span></div>
    <div class="fig"><span class="k">{len(years)}</span><span class="l">season{'s' if len(years)!=1 else ''}</span></div>
    <div class="fig"><span class="k">{d['n_columns']}</span><span class="l">columns</span></div>
    <div class="fig"><span class="k">{gb:.2f} GB</span><span class="l">database</span></div>
    <div class="fig"><span class="k">{n_fail}</span><span class="l">checks failing</span></div>
    <div class="fig"><span class="k">{esc(d['date_range'][0])} &rarr; {esc(d['date_range'][1])}</span><span class="l">date range</span></div>
  </div>
</header>

<section>
  <p class="eyebrow">01</p><h2>Integrity</h2>
  <p class="why">Each check is an assertion about how the data is supposed to behave.
  A failure means either the data is wrong or the assumption is — and the assumption
  is the more likely culprit.</p>
  {integrity_section(d['integrity'])}
</section>

<section>
  <p class="eyebrow">02</p><h2>Season coverage</h2>
  <p class="why">A complete regular season is 2,430 games and roughly 700,000 pitches.
  Off days are logged deliberately so they are never re-requested; a day that appears
  in neither column was never fetched.</p>
  {season_section(d['by_season'])}
</section>

<section>
  <p class="eyebrow">03</p><h2>Column coverage</h2>
  <p class="why">Worst first. Each row states the population it was measured against —
  <code>launch_speed</code> is scored on balls in play, not on every pitch, because a
  called strike has no exit velocity to be missing.</p>
  <div class="legend">
    <span class="s-full">≥99.5% complete</span><span class="s-high">90–99%</span>
    <span class="s-mid">50–90%</span><span class="s-low">under 50%</span><span class="s-zero">absent</span>
  </div>
  <div class="scroll">{coverage_section(d['coverage'], years)}</div>
</section>

<section>
  <p class="eyebrow">04</p><h2>Distributions</h2>
  <p class="why">Percentiles per season, with a count of values outside the physically
  plausible range. Comparing the same row across seasons is how a silent calibration
  change shows up.</p>
  {dist_section(d.get('distributions', {}), years)}
</section>

<section>
  <p class="eyebrow">05</p><h2>Leaderboard reconciliation</h2>
  <p class="why">Savant's season leaderboard is its own aggregate, not a sum over the
  pitch table, so a small wOBA difference is expected. What matters is the PA column:
  it is the share of each player's plate appearances the pitch table actually contains,
  and it is the fastest way to catch a backfill that quietly stopped early.</p>
  {recon_section(d.get('reconciliation', []))}
</section>

<footer>Generated {esc(d['generated_at'])} by <code>audit.py</code> · definitions in <code>DATA_DICTIONARY.md</code></footer>
</div>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body)
    print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
