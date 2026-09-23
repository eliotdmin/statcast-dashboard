#!/usr/bin/env python3
"""Render the Mets change-profile report from profiles.json + calibration.json.

    python3 calibrate.py --db data/statcast.db
    python3 profiles.py  --db data/statcast.db --team NYM
    python3 report_profiles.py            -> output/mets_profiles.html
"""
import json
from pathlib import Path

P = json.loads(Path("output/profiles.json").read_text())
C = json.loads(Path("output/calibration.json").read_text())
try: E = json.loads(Path("output/explore.json").read_text())
except Exception: E = {}

HEAD = """<title>Mets Change Profiles</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Condensed:wght@600;700&display=swap">
<style>
:root{color-scheme:light;--ground:#fbfcfd;--card:#fff;--sunk:#f2f5f8;--line:#dee3e9;--line-soft:#eaeef2;
 --ink:#11151a;--ink-2:#4a535e;--ink-3:#7b8490;--up:#1c5cab;--down:#c9403f;--mid:#e6e9ee;--accent:#1c5cab;
 --warn-bg:#fdf3d8;--warn-ink:#6b4a00;--warn-line:#e8c76a;--bar:#c6cfda}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --ground:#0f1216;--card:#171b21;--sunk:#1b2027;--line:#2b323b;--line-soft:#222831;
 --ink:#f1f4f7;--ink-2:#a9b2bd;--ink-3:#78818d;--up:#6da7ec;--down:#e66767;--mid:#20262e;--accent:#6da7ec;
 --warn-bg:#3a2c05;--warn-ink:#ffe4a3;--warn-line:#6b5312;--bar:#3a434f}}
:root[data-theme="dark"]{color-scheme:dark;
 --ground:#0f1216;--card:#171b21;--sunk:#1b2027;--line:#2b323b;--line-soft:#222831;
 --ink:#f1f4f7;--ink-2:#a9b2bd;--ink-3:#78818d;--up:#6da7ec;--down:#e66767;--mid:#20262e;--accent:#6da7ec;
 --warn-bg:#3a2c05;--warn-ink:#ffe4a3;--warn-line:#6b5312;--bar:#3a434f}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:"IBM Plex Sans",-apple-system,sans-serif;
 font-size:15px;line-height:1.55}
.wrap{max-width:1000px;margin:0 auto;padding-block:42px 90px;padding-left:20px;padding-right:20px;
 display:flex;flex-direction:column;gap:34px}
.mono,code{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
h1{font-family:"IBM Plex Sans Condensed","IBM Plex Sans",sans-serif;font-weight:700;
 font-size:clamp(29px,4.8vw,40px);letter-spacing:-.018em;margin:0}
h2{font-family:"IBM Plex Sans Condensed","IBM Plex Sans",sans-serif;font-weight:700;font-size:21px;margin:0 0 4px}
h3{font-family:"IBM Plex Sans Condensed",sans-serif;font-size:18px;margin:0;font-weight:700}
p{margin:0 0 12px;max-width:74ch}p:last-child{margin-bottom:0}
.lede{font-size:16.5px;color:var(--ink-2)}
.eyebrow{font-size:10.5px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin:0 0 8px}
.note{font-size:13.5px;color:var(--ink-2)}
.warn{background:var(--warn-bg);border:1px solid var(--warn-line);color:var(--warn-ink);padding:15px 18px}
.warn p{color:inherit}
.card{background:var(--card);border:1px solid var(--line-soft);padding:17px 19px;margin-bottom:14px}
.chead{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:4px}
.chead .sub{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--ink-3)}
.story{font-size:14px;color:var(--ink-2);margin:6px 0 12px;max-width:76ch}
.mrow{display:grid;grid-template-columns:118px 92px 74px 1fr;gap:10px;align-items:center;
 padding:4px 8px;font-size:12.5px;border-bottom:1px solid var(--line-soft)}
.mrow:last-child{border-bottom:0}
.mrow.hi{background:var(--sunk)}
.mrow .k{color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mrow .v{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;white-space:nowrap;
 font-size:11.5px;color:var(--ink-3)}
.mrow .d{font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right}
.zwrap{position:relative;height:15px;background:linear-gradient(90deg,transparent 0,transparent calc(50% - .5px),
 var(--line) calc(50% - .5px),var(--line) calc(50% + .5px),transparent calc(50% + .5px));min-width:110px}
.zbar{position:absolute;top:3px;height:9px;background:var(--bar)}
.zbar.up{background:var(--up)}.zbar.dn{background:var(--down)}
.up{color:var(--up)}.dn{color:var(--down)}.flat{color:var(--ink-3)}
.tag{font-family:"IBM Plex Mono",monospace;font-size:9.5px;letter-spacing:.05em;padding:1px 5px;border-radius:2px;
 background:var(--mid);color:var(--ink-2)}
.ars{margin-top:10px;font-size:12.5px;color:var(--ink-2);font-family:"IBM Plex Mono",monospace}
.more{background:none;border:0;color:var(--accent);font:inherit;font-size:12px;cursor:pointer;padding:6px 0 0}
table{border-collapse:collapse;width:100%}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--line-soft);font-size:13px}
thead th{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3);
 border-bottom:1px solid var(--line)}
td.num,th.num{text-align:right;font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}
.v-yes{color:var(--up);font-weight:600}.v-no{color:var(--down);font-weight:600}.v-part{color:var(--ink-3);font-weight:600}
footer{border-top:1px solid var(--line);padding-top:15px;color:var(--ink-3);font-size:12.5px}
@media(max-width:620px){.mrow{grid-template-columns:100px 1fr 64px;}.mrow .v{display:none}}
</style>"""

STORY = {
 "Juan Soto": "Swinging at more of everything &mdash; in the zone especially &mdash; and striking out six points less. The believable versions are smaller than the raw ones: a 6.6-point jump in zone-swing rate shrinks to 4.3, which is still the single largest decision change on the roster.",
 "Francisco Lindor": "The one genuine power retooling. Bat speed is the change that survives shrinkage nearly intact (+1.76 raw, +1.55 believable) because bat speed is 85% signal year to year. The +7.6 pull rate looks bigger but is mostly noise: believable value +2.4.",
 "Brett Baty": "The ten-point ground-ball drop that headlined the earlier version of this page does not survive. Ground-ball rate is 18% signal year over year, so &minus;10.4 shrinks to &minus;1.7 &mdash; under a standard year's drift. His real change is approach: first-pitch swings up 4.6 believable points.",
 "Mark Vientos": "The only league-extreme change on the team's offense. +2.71 mph of bat speed shrinks barely at all, to +2.33, which is 2.3 true-change standard deviations. Fewer than one hitter in fifty moves this much in a year.",
 "Francisco Alvarez": "Looked like a dramatic pull-side overhaul (+12.7 points) but pull rate is only 29% signal: believable value +2.7. Nothing here is extreme; he is a collection of moderate moves.",
 "Sean Manaea": "Five metrics moved together and all point down &mdash; velocity, zone rate, whiffs, strikeouts, expected results. No single one is extreme, but five aligned moderate moves is itself the finding.",
 "Clay Holmes": "Dropped his arm slot three degrees. Arm angle is ~100% signal, so that change is believed essentially in full, and he rebuilt the arsenal around it: slider out, curve and sinker in.",
 "Nolan McLean": "Raised his slot three and a half degrees and cut the sweeper by fourteen points. The mechanical change is fully believed; the performance changes attached to it are not yet.",
 "Kodai Senga": "+2.15 mph, which at 99% signal is +2.08 believable and 2.8 true-change SDs &mdash; the largest single change anywhere in this report. Results still went the wrong way.",
 "David Peterson": "Nothing mechanical moved. The only change clearing a normal year's drift is wOBA against, and even that is marginal.",
 "Huascar Brazobán": "Leaned hard into the sinker (+14 points) and his expected results improved. The results change is about a normal year's movement, not more."}

SCORE = [
 ("H1", "Vientos's bat-speed gain is a step change", "partial",
  "Strongest split at 2026-06-16. That t-statistic is the maximum over ~57 candidate dates and is not a valid test. The <em>size</em> of the gain is now confirmed as league-extreme (z +2.30); its <em>shape</em> is not established."),
 ("H2", "Swing length moved with bat speed", "yes",
  "Lindor +0.124 believable (z +1.03). Swing length is 87% signal, the highest of any hitting metric, so these are trustworthy."),
 ("H3", "Soto's decline is situational, not global", "yes",
  "&minus;2.50 mph at 0 strikes, &minus;0.31 at 1, &minus;1.38 at 2. Softest in the count where he is normally most aggressive."),
 ("H6", "Soto sees fewer fastballs", "no",
  "53.7 / 50.8 / 52.6 / 51.9% across 2023&ndash;2026. Flat."),
 ("H7", "Team-wide fastball share shifted", "no",
  "57.2 &rarr; 54.6% over four years, a league-wide drift rather than a response to the Mets."),
 ("H8", "The league adjusted to Vientos's added bat speed", "no",
  "48.9 &rarr; 48.5% fastballs after the largest bat-speed gain on the team. No detectable response."),
 ("H9", "Lindor sees more edge pitches", "no",
  "Edge rate is 6% signal year over year &mdash; almost entirely noise &mdash; so this hypothesis is close to untestable at one season of data, and the observed move is inside noise either way."),
 ("H10", "Mets are pitched differently with runners on", "partial",
  "Fastball share with runners on 52.4 &rarr; 54.1% while bases-empty held flat. Suggestive, never formally tested."),
 ("H14", "Chase rate is a fast-moving <em>leading</em> discipline signal", "no",
  "<strong>Corrected.</strong> The earlier version scored this yes because chase changes were detectable. That is not what the hypothesis claimed. Within-hitter, across 1,119 month-triples, this month's change in chase rate predicts next month's change in wOBA at +0.046 &plusmn; 0.036 &mdash; indistinguishable from zero. Chase moves <em>with</em> production in the same month (&minus;0.37 &plusmn; 0.041) but does not lead it. It is a coincident indicator, not an early warning."),
 ("H16", "The biggest luck gaps belong to hitters whose swing did not change", "no",
  "<strong>Previously skipped.</strong> Across 222 qualified hitters, the correlation between 2025&ndash;26 bat-speed change and the 2026 wOBA&minus;xwOBA gap is &minus;0.036, 95% CI [&minus;0.167, +0.096]. The luck gap is not a disguised mechanical change."),
 ("H17", "A Mets pitcher changed arm slot", "yes",
  "Holmes &minus;3.00&deg;, McLean +3.45&deg;. Arm angle is ~100% signal, so these survive shrinkage untouched. The best-supported hypothesis of the set."),
 ("H18", "Velocity moved meaningfully", "yes",
  "Senga +2.08 believable (z +2.81), Manaea &minus;0.75 (z &minus;1.01). Senga's is the largest change in the report."),
 ("H19", "A pitcher added or dropped a pitch", "yes",
  "Manaea FF &minus;23pp / SI +19pp, McLean ST &minus;14pp, Holmes SL &minus;11pp. Three substantial rebuilds.")]


def cal_table(kind, title):
    d = C[kind]
    rows = sorted(d.items(), key=lambda x: -x[1]["share"])
    tr = "".join(
        f'<tr><td>{k}</td><td class="num">{v["sd_obs"]:.4f}</td>'
        f'<td class="num">{v["sd_noise"]:.4f}</td><td class="num"><strong>{v["sd_true"]:.4f}</strong></td>'
        f'<td class="num">{100*v["share"]:.0f}%</td></tr>' for k, v in rows)
    return (f'<h3 style="margin-bottom:6px">{title}</h3><div class="scroll"><table>'
            '<thead><tr><th>metric</th><th class="num">spread of<br>observed change</th>'
            '<th class="num">spread from<br>sampling noise</th><th class="num">spread of<br>TRUE change</th>'
            '<th class="num">believable<br>share</th></tr></thead><tbody>'
            + tr + "</tbody></table></div>")


page = f"""{HEAD}
<div class="wrap">
<header>
  <p class="eyebrow">statcast-dashboard &middot; New York Mets &middot; 2025 vs 2026</p>
  <h1>Mets Change Profiles</h1>
  <p class="lede">Every hitter with 600+ combined plate appearances and every pitcher with 100+
  combined innings, profiled across decisions, mechanics, results and how they are pitched &mdash;
  with every change shrunk toward zero by how much of that metric's year-to-year movement is real,
  and scored against how far a major leaguer actually moves in a year.</p>
</header>

<section class="warn">
  <p><strong>This page was rebuilt. The earlier version overstated most of these changes.</strong>
  It reported raw differences and called a change notable if it cleared its own error bar and passed
  a practical-size floor I chose by hand. Both tests are wrong for this question. Clearing an error
  bar only says a change is not zero; with 400 plate appearances almost nothing clears it, and with
  4,000 pitches almost everything does. And a hand-picked floor is an opinion.</p>
  <p style="margin-top:10px">The replacement is measured, not asserted. For each metric, the spread
  of year-over-year changes across all 222 qualified hitters and 193 qualified pitchers is split into
  the part that is real movement and the part that is sampling noise. That gives two things: a
  shrinkage factor, so an observed change is discounted by how much of that metric is usually noise,
  and a yardstick, so the discounted change can be expressed in units of how far players really move.</p>
  <p style="margin-top:10px"><strong>What changed most: Brett Baty.</strong> His &minus;10.4 point
  ground-ball drop led the old page. Ground-ball rate is 18% signal year to year, so the believable
  change is &minus;1.7 points &mdash; less than an ordinary season's drift. It was never a swing
  overhaul.</p>
</section>

<section>
  <p class="eyebrow">the yardstick</p>
  <h2>How far does a major leaguer actually move in a year?</h2>
  <p>Every observed change is a true change plus sampling noise, and those two add in variance:
  var(observed) = var(true) + var(noise). The noise part is computable from sample sizes alone, so
  subtracting it from the observed spread leaves the spread of real movement. The ratio is both the
  fraction of an observed change worth believing and the scale against which it should be judged.</p>
  <p>Read the right-hand column as a warning label. Arm angle at ~100% means what you see is what
  happened. Ground-ball rate at 18% means four-fifths of any single season's apparent change is
  an accident of which balls happened to be hit on the ground.</p>
  {cal_table("hitters", "Hitters &mdash; 222 with 250+ PA in both 2025 and 2026")}
  <div style="height:20px"></div>
  {cal_table("pitchers", "Pitchers &mdash; 193 with 50+ IP in both seasons")}
</section>

<section>
  <p class="eyebrow">hitters</p>
  <h2>Five hitters, 600+ PA combined</h2>
  <p class="note">Bars show the believable change in true-change standard deviations. The
  centre line is no change; the edges are &plusmn;2.5, which essentially no one reaches.</p>
  <div id="hitters"></div>
</section>

<section>
  <p class="eyebrow">pitchers</p>
  <h2>Six pitchers, 100+ IP combined</h2>
  <div id="pitchers"></div>
</section>

<section>
  <p class="eyebrow">scorecard</p>
  <h2>The hypotheses, rescored</h2>
  <p class="note">Every well-powered hypothesis from the earlier list. Two verdicts changed:
  H14 was scored yes on the wrong evidence and is now no; H16 was never run and now is.</p>
  <div class="scroll"><table id="score"></table></div>
  <p style="margin-top:14px"><strong>The pattern survives the rescoring, and gets stronger.</strong>
  Every hypothesis about <em>mechanical change</em> holds up &mdash; arm slots moved, arsenals were
  rebuilt, bat speed shifted, and these are exactly the metrics with the highest signal share, so
  shrinkage barely touches them. Every hypothesis about <em>the league responding</em> fails. And
  the two hypotheses about batted-ball profile that looked strongest on raw numbers were the ones
  shrinkage destroyed. Mechanics are measurable in one season. Batted-ball tendencies are not.</p>
</section>

<footer id="foot"></footer>
</div>
<script>const P={json.dumps(P)},C={json.dumps(C)};</script>
<script>
(function(){{
  const $=s=>document.querySelector(s);
  const STORY={json.dumps(STORY)};
  const SCORE={json.dumps(SCORE)};
  const fmt=(v)=>Math.abs(v)>=100?v.toFixed(0):Math.abs(v)>=1.5?v.toFixed(2):v.toFixed(4);
  const lab=z=>Math.abs(z)>=2?"league-extreme":Math.abs(z)>=1.25?"clearly moved"
             :Math.abs(z)>=.75?"moved a little":"ordinary drift";

  function card(pl,isPit){{
    const ms=Object.entries(pl.metrics).filter(([k,v])=>v.z!==undefined)
             .sort((a,b)=>Math.abs(b[1].z)-Math.abs(a[1].z));
    const top=ms.filter(([k,v])=>Math.abs(v.z)>=0.75);
    const row=([k,v])=>{{
      const cls=Math.abs(v.z)<0.75?"":(v.d>0?"up":"dn");
      const w=Math.min(Math.abs(v.z)/2.5,1)*50;
      return `<div class="mrow${{Math.abs(v.z)>=1.25?" hi":""}}">
        <span class="k">${{k}}</span>
        <span class="v">${{fmt(v.y25)}}&rarr;${{fmt(v.y26)}}</span>
        <span class="d"><span class="flat">${{v.d>0?"+":""}}${{fmt(v.d)}}</span><br>
          <b class="${{cls||"flat"}}">${{v.shrunk>0?"+":""}}${{fmt(v.shrunk)}}</b></span>
        <span class="zwrap" title="z ${{v.z.toFixed(2)}} — ${{lab(v.z)}}">
          <span class="zbar ${{cls}}" style="${{v.z>0?"left:50%":"right:50%"}};width:${{w}}%"></span></span>
      </div>`;}};
    const ars=isPit&&pl.arsenal?Object.entries(pl.arsenal).filter(([p,v])=>Math.abs(v.d)>=5)
      .sort((a,b)=>Math.abs(b[1].d)-Math.abs(a[1].d))
      .map(([p,v])=>`${{p}} ${{v.y25.toFixed(0)}}&rarr;${{v.y26.toFixed(0)}}% (${{v.d>0?"+":""}}${{v.d.toFixed(0)}}pp)`)
      .join(" &middot; "):"";
    const load=isPit?`${{pl.ip[0].toFixed(0)}} + ${{pl.ip[1].toFixed(0)}} IP`
                    :`${{pl.pa[0].toFixed(0)}} + ${{pl.pa[1].toFixed(0)}} PA`;
    const id="c"+pl.pid;
    return `<div class="card">
      <div class="chead"><h3>${{pl.name}}</h3>
        <span class="sub">${{load}} &middot; ${{top.length}} of ${{ms.length}} metrics beyond a normal year's drift</span></div>
      ${{STORY[pl.name]?`<p class="story">${{STORY[pl.name]}}</p>`:""}}
      <div class="mrow" style="border-bottom:1px solid var(--line)">
        <span class="k" style="font-size:10px;letter-spacing:.06em;text-transform:uppercase">metric</span>
        <span class="v" style="font-size:10px">2025&rarr;2026</span>
        <span class="d" style="font-size:10px;color:var(--ink-3)">raw<br>believable</span>
        <span class="zwrap" style="font-size:10px;color:var(--ink-3);background:none;line-height:15px">vs a normal year</span></div>
      <div>${{top.map(row).join("")}}</div>
      <div id="${{id}}" hidden>${{ms.filter(m=>Math.abs(m[1].z)<0.75).map(row).join("")}}</div>
      <button class="more" data-t="${{id}}">show the ${{ms.length-top.length}} metrics that did not move &darr;</button>
      ${{ars?`<div class="ars">arsenal: ${{ars}}</div>`:""}}</div>`;
  }}
  $("#hitters").innerHTML=P.hitters.map(h=>card(h,false)).join("");
  $("#pitchers").innerHTML=P.pitchers.map(p=>card(p,true)).join("");
  document.querySelectorAll(".more").forEach(b=>b.addEventListener("click",()=>{{
    const el=document.getElementById(b.dataset.t);
    el.hidden=!el.hidden;
    b.textContent=el.hidden?b.textContent.replace("\\u2191","\\u2193")
                           :b.textContent.replace("\\u2193","\\u2191");
  }}));
  $("#score").innerHTML='<thead><tr><th>#</th><th>hypothesis</th><th>verdict</th><th>evidence</th></tr></thead><tbody>'+
    SCORE.map(([n,h,v,e])=>`<tr><td class="mono">${{n}}</td><td>${{h}}</td>
      <td class="v-${{v==="yes"?"yes":v==="no"?"no":"part"}}">${{v}}</td>
      <td class="note" style="max-width:none">${{e}}</td></tr>`).join("")+'</tbody>';
  $("#foot").textContent="Regular season only. Hitters 600+ PA combined 2025-2026, pitchers 100+ IP. "+
    "Shrinkage factor var(true)/(var(true)+var(noise)) per metric, from calibrate.py over all "+
    "qualified major leaguers. 2026 is a partial season, which widens standard errors and therefore "+
    "shrinks its changes harder - correctly so. Generated by profiles.py and report_profiles.py.";
}})();
</script>"""

Path("output/mets_profiles.html").write_text(page)
print("wrote output/mets_profiles.html", len(page), "bytes")
