import json
D=open("machine.json").read()
HEAD = """<title>The Regression Machine</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root{
  color-scheme:light;
  --ground:#edeeea; --card:#fbfbf9; --sunk:#e3e5df; --line:#cfd2c9; --soft:#e0e2da;
  --ink:#191b18; --ink2:#4f544c; --ink3:#848a7f;
  --cool:#2b6b86; --cool-bg:#dcebf0; --warm:#b5561f; --warm-bg:#f6e6da;
  --mid:#8d9387; --accent:#2b6b86;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --ground:#101210; --card:#181a17; --sunk:#1e211d; --line:#30342d; --soft:#262a23;
  --ink:#eef0eb; --ink2:#a7ada1; --ink3:#767c71;
  --cool:#6bb4d0; --cool-bg:#15303a; --warm:#e0865290; --warm:#e08652; --warm-bg:#3a2417;
  --mid:#79806f; --accent:#6bb4d0;
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --ground:#101210; --card:#181a17; --sunk:#1e211d; --line:#30342d; --soft:#262a23;
  --ink:#eef0eb; --ink2:#a7ada1; --ink3:#767c71;
  --cool:#6bb4d0; --cool-bg:#15303a; --warm:#e08652; --warm-bg:#3a2417;
  --mid:#79806f; --accent:#6bb4d0;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,sans-serif;font-size:15px;line-height:1.6}
.wrap{max-width:960px;margin:0 auto;padding-block:44px 100px;padding-left:20px;padding-right:20px;
  display:flex;flex-direction:column;gap:42px}
.m,code{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}
code{font-size:.88em;background:var(--sunk);padding:1px 5px;color:var(--ink2)}
h1{font-family:Archivo,"IBM Plex Sans",sans-serif;font-weight:700;font-size:clamp(33px,5.4vw,50px);
  letter-spacing:-.032em;margin:0;line-height:1.02;text-wrap:balance}
h2{font-family:Archivo,sans-serif;font-weight:700;font-size:25px;margin:0;letter-spacing:-.018em;text-wrap:balance}
h3{font-family:Archivo,sans-serif;font-weight:600;font-size:17px;margin:0;letter-spacing:-.008em}
p{margin:0;max-width:70ch}
.st{display:flex;flex-direction:column;gap:14px}
.lede{font-size:17.5px;color:var(--ink2);max-width:62ch}
.eb{font-family:"IBM Plex Mono",monospace;font-size:10.5px;font-weight:500;letter-spacing:.15em;
  text-transform:uppercase;color:var(--ink3)}
.note{font-size:13.5px;color:var(--ink2)}
.rule{height:2px;background:var(--ink);opacity:.85}

/* thesis */
.thesis{background:var(--card);border:1px solid var(--line);padding:24px}
.big{display:flex;gap:34px;flex-wrap:wrap;margin-top:6px}
.big div{display:flex;flex-direction:column;gap:1px}
.big .v{font-family:Archivo,sans-serif;font-weight:700;font-size:38px;letter-spacing:-.03em;line-height:1}
.big .l{font-size:12px;color:var(--ink3);max-width:22ch;line-height:1.35}
.big .v.c{color:var(--cool)} .big .v.w{color:var(--warm)}

/* machine */
.machine{background:var(--card);border:1px solid var(--line)}
.mtop{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;padding:18px 22px;
  border-bottom:1px solid var(--soft);background:var(--sunk)}
label.f{display:flex;flex-direction:column;gap:4px;font-size:11px;color:var(--ink3);
  font-family:"IBM Plex Mono",monospace;letter-spacing:.07em;text-transform:uppercase}
select{font-family:"IBM Plex Sans",sans-serif;font-size:14px;padding:7px 9px;background:var(--card);
  color:var(--ink);border:1px solid var(--line);min-width:150px;max-width:100%}
select:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.mbody{padding:22px}
.readout{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--soft);
  border:1px solid var(--soft);margin-bottom:20px}
.readout>div{background:var(--card);padding:14px 15px;display:flex;flex-direction:column;gap:3px}
.readout .k{font-family:"IBM Plex Mono",monospace;font-size:9.5px;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink3)}
.readout .n{font-family:Archivo,sans-serif;font-weight:700;font-size:30px;letter-spacing:-.025em;line-height:1.05}
.readout .s{font-size:11.5px;color:var(--ink3)}
.readout .n.c{color:var(--cool)}.readout .n.w{color:var(--warm)}
.verdict{padding:13px 15px;font-size:14px;border-left:3px solid var(--mid);background:var(--sunk);
  margin-bottom:18px;color:var(--ink2)}
.verdict.c{border-left-color:var(--cool);background:var(--cool-bg)}
.verdict.w{border-left-color:var(--warm);background:var(--warm-bg)}
.verdict b{color:var(--ink)}
.sliders{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;
  padding-top:18px;border-top:1px solid var(--soft)}
.sl{display:flex;flex-direction:column;gap:5px}
.sl .hd{display:flex;justify-content:space-between;font-size:11.5px;color:var(--ink3);
  font-family:"IBM Plex Mono",monospace}
.sl .hd b{color:var(--ink);font-weight:500}
input[type=range]{width:100%;accent-color:var(--accent)}

table{border-collapse:collapse;width:100%;min-width:480px}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--soft);font-size:13.5px}
thead th{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink3);border-bottom:1px solid var(--line);font-weight:500;white-space:nowrap}
td.n,th.n{text-align:right;font-family:"IBM Plex Mono",monospace;font-variant-numeric:tabular-nums}
tbody tr:last-child td{border-bottom:0}
.scroll{overflow-x:auto}
.hl td{background:var(--sunk)}

.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:680px){.two{grid-template-columns:1fr}.readout{grid-template-columns:1fr}}
.box{background:var(--card);border:1px solid var(--soft);padding:17px 19px;display:flex;
  flex-direction:column;gap:9px}
.box h3{margin-bottom:2px}
ul.p{margin:0;padding-left:19px;display:flex;flex-direction:column;gap:8px}
ul.p li{font-size:14px;color:var(--ink2);max-width:70ch}
ul.p li b{color:var(--ink);font-weight:600}
ol.q{margin:0;padding-left:0;list-style:none;counter-reset:q;display:flex;flex-direction:column;gap:13px}
ol.q li{counter-increment:q;position:relative;padding-left:34px;font-size:14.5px;color:var(--ink2);max-width:72ch}
ol.q li::before{content:"Q" counter(q);position:absolute;left:0;top:2px;font-family:"IBM Plex Mono",monospace;
  font-size:10.5px;font-weight:600;color:var(--accent);background:var(--sunk);padding:2px 5px}
ol.q li b{color:var(--ink);font-weight:600}
figure{margin:0;display:flex;flex-direction:column;gap:10px}
figcaption{font-size:12.5px;color:var(--ink3);max-width:70ch}
svg{display:block;max-width:100%;height:auto}
footer{border-top:1px solid var(--line);padding-top:17px;color:var(--ink3);font-size:12.5px;max-width:76ch}
</style>"""

BODY = r"""
<div class="wrap">

<header class="st">
  <p class="eb">statcast-dashboard &middot; 10,287 hitter-months &middot; 2023&ndash;2026</p>
  <h1>The Regression Machine</h1>
  <p class="lede">What a hitter just hit tells you almost nothing about what he will hit next month.
  This works out how much of a hot month to believe &mdash; and then shows you, case by case,
  whether it was right.</p>
</header>

<section class="thesis">
  <p class="eb">the whole result in one number</p>
  <p style="margin-top:8px">Take every hitter-month in the 2026 holdout, sort it into fifths by some
  signal, and look at what those hitters <em>actually hit the following month</em>. A useful signal
  spreads the fifths apart. A useless one collapses them.</p>
  <div class="big">
    <div><span class="v">.010</span><span class="l">spread when you sort by what he just hit</span></div>
    <div><span class="v">.023</span><span class="l">spread when you sort by xwOBA</span></div>
    <div><span class="v c">.041</span><span class="l">spread when you sort by the machine</span></div>
  </div>
  <p style="margin-top:18px" class="note">Sorting hitters by the month they just had separates next
  month's production by ten points of wOBA &mdash; barely more than nothing. The machine separates it
  by forty-one. None of this was fit on 2026.</p>
</section>

<section class="st">
  <div class="rule"></div>
  <p class="eb">the instrument</p>
  <h2>Run a month through it</h2>
  <p>Pick any hitter with 40+ plate appearances in a month and 40+ in the next. The machine sees only
  the first month. The last column is what he did in the second, which it never saw.</p>

  <div class="machine">
    <div class="mtop">
      <label class="f">Hitter<select id="who"></select></label>
      <label class="f">Month<select id="mo"></select></label>
      <label class="f">Or jump to<select id="jump">
        <option value="">&mdash;</option>
        <option value="hot">a month that looked hot</option>
        <option value="cold">a month that looked cold</option>
        <option value="dis">the machine's biggest disagreements</option>
      </select></label>
    </div>
    <div class="mbody">
      <div class="readout">
        <div><span class="k">what he hit</span><span class="n" id="r-w">&mdash;</span>
          <span class="s" id="r-ws">&mdash;</span></div>
        <div><span class="k">machine's forecast</span><span class="n" id="r-p">&mdash;</span>
          <span class="s" id="r-ps">&mdash;</span></div>
        <div><span class="k">what actually happened</span><span class="n" id="r-a">&mdash;</span>
          <span class="s" id="r-as">&mdash;</span></div>
      </div>
      <div class="verdict" id="verdict">&mdash;</div>
      <figure>
        <svg id="slope" viewBox="0 0 900 150" role="img"
          aria-label="Where the month sits relative to league average, and where the machine expects it to land."></svg>
        <figcaption id="cap"></figcaption>
      </figure>
      <div class="sliders">
        <div class="sl"><div class="hd"><span>exit velocity</span><b id="v-ev"></b></div>
          <input type="range" id="s-ev" min="-4" max="4" step="0.1" value="0"></div>
        <div class="sl"><div class="hd"><span>bat speed</span><b id="v-bs"></b></div>
          <input type="range" id="s-bs" min="-4" max="4" step="0.1" value="0"></div>
        <div class="sl"><div class="hd"><span>strikeout rate</span><b id="v-k"></b></div>
          <input type="range" id="s-k" min="-8" max="8" step="0.5" value="0"></div>
        <div class="sl"><div class="hd"><span>whiff per swing</span><b id="v-wh"></b></div>
          <input type="range" id="s-wh" min="-8" max="8" step="0.5" value="0"></div>
      </div>
      <p class="note" style="margin-top:12px">Move a slider to ask what the forecast would have been
      had that month looked different. These four carry the largest weights in the model.
      <button id="reset" style="background:none;border:0;color:var(--accent);font:inherit;font-size:13.5px;
      cursor:pointer;padding:0;text-decoration:underline">reset</button></p>
    </div>
  </div>
</section>

<section class="st">
  <div class="rule"></div>
  <p class="eb">does it work</p>
  <h2>The calibration, on data the model never saw</h2>
  <p>Each line is one fifth of the 2026 holdout. The left point is what the signal claimed; the right
  point is what those hitters actually hit the next month. Lines that collapse to the middle mean the
  signal was mostly noise. Lines that stay apart mean it was real.</p>
  <figure>
    <svg id="cal" viewBox="0 0 900 300" role="img"
      aria-label="Slope chart: three signals, each sorted into fifths, showing claimed value versus what those hitters actually hit next month."></svg>
    <figcaption>1,085 hitter-months, 2026. Weighted by the following month's plate appearances.
    wOBA is not merely weak here &mdash; it is badly miscalibrated: the bottom fifth of hitters by
    last month's wOBA claimed .247 and then hit .329.</figcaption>
  </figure>
</section>

<section class="st">
  <div class="rule"></div>
  <p class="eb">question 1</p>
  <h2>Is xwOBA better than wOBA at predicting next period's wOBA?</h2>
  <p>Yes, at every horizon, and at one month wOBA is worse than useless. Fit on 2023&ndash;2025,
  evaluated once on 2026, weighted by the target window's plate appearances. R&sup2; is measured
  against the test set's own mean, so a negative number means the signal is worse than assuming
  every hitter is league average.</p>
  <div class="scroll"><table>
    <thead><tr><th>window</th><th class="n">n</th><th class="n">wOBA</th><th class="n">xwOBA</th>
      <th class="n">both</th><th class="n">xwOBA's edge</th></tr></thead>
    <tbody>
    <tr class="hl"><td>1 month</td><td class="n">1,085</td><td class="n">&minus;0.004</td>
      <td class="n">0.015</td><td class="n">0.018</td><td class="n">+0.019</td></tr>
    <tr><td>1 month, 70+ PA</td><td class="n">674</td><td class="n">0.003</td><td class="n">0.022</td>
      <td class="n">0.023</td><td class="n">+0.018</td></tr>
    <tr class="hl"><td>2 months</td><td class="n">856</td><td class="n">0.037</td><td class="n">0.073</td>
      <td class="n">0.072</td><td class="n">+0.037</td></tr>
    <tr><td>3 months</td><td class="n">318</td><td class="n">&minus;0.007</td><td class="n">0.030</td>
      <td class="n">0.036</td><td class="n">+0.037</td></tr>
    <tr class="hl"><td>full season &rarr; next season</td><td class="n">213</td><td class="n">0.119</td>
      <td class="n">0.127</td><td class="n">0.131</td><td class="n">+0.008</td></tr>
    </tbody>
  </table></div>
  <div class="two" style="margin-top:6px">
    <div class="box"><h3>The edge is humped, not declining</h3>
      <p class="note">I predicted xwOBA's advantage would shrink monotonically as the window grew,
      since wOBA's noise falls with sample. It does not. The edge <em>rises</em> from one month to
      two, holds through three, and then nearly vanishes over a full season. At one month even xwOBA
      is too noisy to exploit its own advantage; over a full season wOBA has enough sample that the
      advantage stops mattering. The sweet spot for xwOBA is the middle, which is also where most
      in-season decisions get made.</p></div>
    <div class="box"><h3>Once you know xwOBA, wOBA is negative information</h3>
      <p class="note">Fitting <code>next ~ a + b&#8321;&middot;wOBA + b&#8322;&middot;xwOBA</code> within
      buckets of input playing time, <b>b&#8321; is negative in every bucket above 55 PA</b>
      (&minus;0.02, &minus;0.10, &minus;0.08, &minus;0.04). The part of what actually happened that
      xwOBA cannot explain is not merely uninformative &mdash; it points the wrong way. A hitter who
      beat his xwOBA should be marked <em>down</em>, not up.</p></div>
  </div>
</section>

<section class="st">
  <div class="rule"></div>
  <p class="eb">the honest denominator</p>
  <h2>Why an R&sup2; of 0.06 is most of what is available</h2>
  <p>These numbers look small because the target is mostly coin flips. A month of plate appearances
  contains very little information about anybody. Before grading any forecaster, work out what a
  perfect one could score.</p>
  <p>For two months of the same hitter in the same season,
  <code>E[(w&#8321;&minus;w&#8322;)&sup2;] = &sigma;&sup2;(1/pa&#8321; + 1/pa&#8322;) + var(drift)</code>.
  Regressing 16,228 squared differences on the sample-size term identifies both pieces: the per-plate-appearance
  outcome variance is <b>&sigma;&sup2; = 0.226</b>, and real month-to-month movement in skill has a
  standard deviation of <b>.038</b>. Across 670 hitters, true talent has a spread of just <b>.035</b>.</p>
  <div class="scroll"><table>
    <thead><tr><th>PA in the month</th><th class="n">noise sd</th><th class="n">share of spread that is signal</th>
      <th class="n">best possible R&sup2;</th></tr></thead>
    <tbody>
      <tr><td>40</td><td class="n">.075</td><td class="n">32%</td><td class="n">0.144</td></tr>
      <tr class="hl"><td>60</td><td class="n">.061</td><td class="n">41%</td><td class="n">0.186</td></tr>
      <tr><td>100</td><td class="n">.048</td><td class="n">54%</td><td class="n">0.243</td></tr>
      <tr><td>250</td><td class="n">.030</td><td class="n">75%</td><td class="n">0.336</td></tr>
      <tr><td>600</td><td class="n">.019</td><td class="n">88%</td><td class="n">0.395</td></tr>
    </tbody>
  </table></div>
  <p class="note">At a typical 60-PA month, 59% of the spread between hitters is noise, and an oracle
  knowing every hitter's true talent exactly would score R&sup2; = 0.186. Against that denominator,
  xwOBA's 0.015 captures 8% of what is knowable and the full model's 0.057 captures <b>31%</b>.
  The ceiling, not 1.0, is the right thing to divide by.</p>
</section>

<section class="st">
  <div class="rule"></div>
  <p class="eb">question 2</p>
  <h2>Can we build something more predictive than xwOBA?</h2>
  <p>Yes, and by a wide margin. Three model families, nine nested feature sets, one-month horizon,
  2026 holdout throughout.</p>
  <div class="scroll"><table>
    <thead><tr><th>feature set</th><th class="n">k</th><th class="n">ridge</th><th class="n">boosted trees</th>
      <th class="n">random forest</th></tr></thead>
    <tbody>
      <tr><td>wOBA only</td><td class="n">1</td><td class="n">&minus;0.003</td><td class="n">&minus;0.012</td><td class="n">&minus;0.069</td></tr>
      <tr><td>xwOBA only</td><td class="n">1</td><td class="n">0.015</td><td class="n">0.007</td><td class="n">&minus;0.037</td></tr>
      <tr><td>+ contact quality</td><td class="n">10</td><td class="n">0.024</td><td class="n">0.014</td><td class="n">0.021</td></tr>
      <tr><td>+ plate discipline</td><td class="n">18</td><td class="n">0.030</td><td class="n">0.027</td><td class="n">0.035</td></tr>
      <tr><td>+ batted-ball mix</td><td class="n">26</td><td class="n">0.028</td><td class="n">0.019</td><td class="n">0.035</td></tr>
      <tr><td>+ speed proxies</td><td class="n">29</td><td class="n">0.027</td><td class="n">0.020</td><td class="n">0.035</td></tr>
      <tr><td>+ context &amp; playing time</td><td class="n">39</td><td class="n">0.044</td><td class="n">0.049</td><td class="n">0.055</td></tr>
      <tr class="hl"><td>+ swing geometry</td><td class="n">48</td><td class="n">0.043</td><td class="n">0.057</td><td class="n">0.054</td></tr>
    </tbody>
  </table></div>
  <div class="two" style="margin-top:6px">
    <div class="box"><h3>An uncomfortable control</h3>
      <p class="note">Plate appearances turned up as the second most important feature, so I ran it
      alone. <b>Playing time by itself scores 0.032 &mdash; more than double xwOBA's 0.015.</b>
      How often a manager writes a hitter into the lineup predicts next month better than how hard he
      hit the ball. That is not a hitting statistic; it is the manager's private information about
      health, matchups and what he saw. Stripping it out costs the full model about a fifth of its
      performance (0.057 &rarr; 0.044), and every headline number above keeps it only because a real
      forecaster would know it too.</p></div>
    <div class="box"><h3>Swing geometry earns its place, barely</h3>
      <p class="note">Adding <code>attack_angle</code>, <code>swing_path_tilt</code>, contact depth
      and bat speed moves boosted trees from 0.049 to 0.057 &mdash; the single largest jump after
      context. In the portable linear version, <b>bat speed carries the second-largest coefficient of
      any of the 22 inputs</b>, behind exit velocity and ahead of xwOBA itself. The swing is a better
      forecaster than the result.</p></div>
  </div>
</section>

<section class="st">
  <div class="rule"></div>
  <p class="eb">the trade-off nobody states</p>
  <h2>Describing, repeating and predicting are three different jobs</h2>
  <p>A metric can capture what happened, agree with its own next measurement, or forecast the future.
  These are not the same property, and they trade off against each other almost perfectly.</p>
  <div class="scroll"><table>
    <thead><tr><th>metric</th><th class="n">describes what happened</th><th class="n">repeats itself next month</th>
      <th class="n">predicts next month</th></tr></thead>
    <tbody>
      <tr><td>wOBA</td><td class="n">1.000</td><td class="n">0.135</td><td class="n">0.065</td></tr>
      <tr><td>xwOBA</td><td class="n">0.747</td><td class="n">0.321</td><td class="n">0.136</td></tr>
      <tr class="hl"><td>the machine</td><td class="n">0.485</td><td class="n"><b>0.665</b></td><td class="n"><b>0.205</b></td></tr>
    </tbody>
  </table></div>
  <p class="note">All three columns are correlations. Read down and the pattern is exact: the better
  a metric describes the month that just happened, the worse it forecasts the next one. wOBA is the
  perfect description by construction and the worst forecaster. The machine agrees with the past
  least &mdash; and agrees with itself five times more often than wOBA does. That disagreement with
  the past <em>is</em> the product.</p>
</section>

<section class="st">
  <div class="rule"></div>
  <p class="eb">question 3</p>
  <h2>What explains the gap between wOBA and xwOBA?</h2>
  <p>Two answers that look contradictory and are not. Within a season the gap behaves like pure luck.
  Across seasons it has a small, stubborn, physically sensible component.</p>

  <div class="two">
    <div class="box"><h3>Within a season: luck</h3>
      <p class="note">Split-half reliability, odd months against even months, 1,264 hitter-seasons
      with 100+ PA in each half, Spearman&ndash;Brown corrected:</p>
      <div class="scroll"><table><tbody>
        <tr><td>bat speed</td><td class="n">0.978</td></tr>
        <tr><td>attack angle</td><td class="n">0.971</td></tr>
        <tr><td>whiff rate</td><td class="n">0.924</td></tr>
        <tr><td>exit velocity</td><td class="n">0.879</td></tr>
        <tr><td>spray angle</td><td class="n">0.791</td></tr>
        <tr><td>xwOBA</td><td class="n">0.703</td></tr>
        <tr><td>wOBA</td><td class="n">0.448</td></tr>
        <tr class="hl"><td><b>wOBA &minus; xwOBA</b></td><td class="n"><b>0.164</b></td></tr>
      </tbody></table></div>
    </div>
    <div class="box"><h3>Across seasons: a real, small trait</h3>
      <p class="note">Season-to-season correlation of the same gap, three independent year pairs:
      <b>+0.293</b> (2023&rarr;24), <b>+0.303</b> (2024&rarr;25), <b>+0.274</b> (2025&rarr;26). Stable,
      replicated, and larger than the within-season split-half implies &mdash; which itself is a
      finding, since a purely random quantity cannot correlate with itself across years at all.</p>
      <p class="note">The names resolve it. Hitters with the largest mean season gaps over 3+ seasons:
      <b>Jose Altuve +.048, TJ Friedl +.048, Isaac Paredes +.040, Ernie Clement +.037, Cody Bellinger
      +.033, Geraldo Perdomo +.033, Ceddanne Rafaela +.032, Trea Turner +.030</b>. The other end:
      <b>Salvador Perez &minus;.024, Juan Soto &minus;.021, Michael Conforto &minus;.021, Patrick
      Bailey &minus;.018, Fernando Tatis Jr. &minus;.016, Vladimir Guerrero Jr. &minus;.016</b>.</p>
    </div>
  </div>

  <p style="margin-top:4px">That list is not random. One end is fast contact hitters; the other is
  slow high-power hitters. And the regression agrees: with the window's batted balls described by
  spray angle, launch angle, exit velocity, distance, batted-ball mix, park and fielding alignment,
  <b>exit velocity carries a negative coefficient at every window length</b> (&minus;.006 at one
  month, &minus;.008 at three) while spray angle toward the pull side carries a positive one. xwOBA
  maps exit velocity and launch angle onto a league-average outcome, so it systematically
  over-credits the slow slugger whose hard-hit balls get caught and under-credits the fast hitter who
  beats out the ones that do not leave the infield &mdash; and Isaac Paredes, whose living is made on
  cheap pulled fly balls down the line, is exactly the hitter a direction-blind metric should
  underrate.</p>

  <div class="box">
    <h3>A circularity I nearly published</h3>
    <p class="note">The first version of this regression found ground-ball single rate to be by far
    the strongest explainer of the gap, at R&sup2; = 0.246. That is close to meaningless. A ground
    ball that finds a hole <em>is</em> simultaneously a ground-ball single and a positive gap &mdash;
    it is the same event counted twice, not an explanation of it. Ground-ball single rate has a
    split-half reliability of 0.193, which is to say it is itself mostly luck.</p>
    <p class="note">Splitting the predictors into those knowable before the ball lands and those
    derived from the outcome gives the honest picture, and it also answers the question about short
    versus long stretches:</p>
    <div class="scroll"><table>
      <thead><tr><th>window</th><th class="n">sd of the gap</th><th class="n">explained, ante-hoc only</th>
        <th class="n">explained, outcome-derived</th></tr></thead>
      <tbody>
        <tr><td>1 month</td><td class="n">.042</td><td class="n">0.034</td><td class="n">0.189</td></tr>
        <tr><td>2 months</td><td class="n">.031</td><td class="n">0.065</td><td class="n">0.182</td></tr>
        <tr class="hl"><td>3 months</td><td class="n">.026</td><td class="n"><b>0.137</b></td><td class="n">0.168</td></tr>
      </tbody>
    </table></div>
    <p class="note"><b>The gap shrinks as the window lengthens, and the part that is genuinely
    explainable quadruples.</b> Over one month the gap is .042 wide and almost none of it can be
    accounted for by anything you could have known in advance; over three months it narrows to .026
    and 14% of it is real structure. That is exactly the signature of luck averaging out and a small
    physical residue surviving.</p>
  </div>

  <p class="note">One more, with the obvious confound removed: because the gap and the level of xwOBA
  are mechanically linked, the raw finding that a positive gap predicts a lower future wOBA needed
  the level partialled out. At one month it disappears (&minus;0.038 &plusmn; 0.024, null). At three
  months it survives: <b>&minus;0.107 &plusmn; 0.054</b>. Over a meaningful stretch, beating your
  expected output really does forecast giving it back.</p>
</section>

<section class="st">
  <div class="rule"></div>
  <p class="eb">for the morning</p>
  <h2>Open questions</h2>
  <ol class="q">
    <li><b>The playing-time result deserves its own study.</b> Lineup decisions outpredicting exit
    velocity is either a measure of what managers privately know, or an artifact of injuries and
    platoons. Separating those &mdash; by conditioning on consecutive healthy months, and by checking
    whether the signal survives within a fixed lineup slot &mdash; would say which.</li>

    <li><b>Why is xwOBA's edge humped rather than declining?</b> My prediction was wrong and I do not
    have a mechanism, only a story. The three-month row also has the smallest test sample (318) and
    a negative wOBA R&sup2; that could be noise. Worth re-running at weekly resolution, where there
    are far more windows, to see whether the hump is real or an artifact of having six months in a
    season.</li>

    <li><b>Is the machine's edge just better shrinkage, or better information?</b> A model given only
    xwOBA and sample size, shrunk optimally, should be compared head-to-head against the full
    48-feature version. If most of the gain is shrinkage, the useful deliverable is a formula rather
    than a model, and everything gets simpler.</li>

    <li><b>The persistent gap should be predictable from sprint speed directly.</b> Every name on the
    over-performing list is fast. The <code>sprint_speed</code> table currently holds 552 rows &mdash;
    one season. Backfilling it across 2023&ndash;2026 would turn the best circumstantial finding here
    into a direct measurement, and would also feed the batted-ball program's T5.</li>

    <li><b>Pitchers are completely untouched.</b> Every number on this page is about hitters. The same
    machinery applies to pitcher wOBA-against, where the prior is that the ceiling is far lower and
    xwOBA's edge far larger, because pitchers control batted-ball outcomes much less.</li>

    <li><b>The model is fit to predict next month's wOBA, which is the wrong target for most uses.</b>
    Rest-of-season is what a roster decision actually needs, and it has a higher ceiling because the
    target is less noisy. One line of code; not yet run.</li>

    <li><b>Nothing here has been tested against a public benchmark.</b> Marcel, Steamer and ZiPS all
    forecast the same quantity and are the obvious reference points. A model that beats xwOBA but
    loses to a thirty-year-old three-year-weighted average with an age adjustment has not achieved
    much, and I do not currently know which side of that line this sits on.</li>
  </ol>
</section>

<footer>
  10,287 hitter-months, 2023&ndash;2026 regular seasons, 40+ plate appearances in both the input and
  target window. Models fit on 2023&ndash;2025 and evaluated once on 2026; no 2026 data influenced any
  coefficient. Weighted by target-window plate appearances throughout. The instrument above runs the
  22-feature ridge, whose out-of-sample R&sup2; is 0.030 against xwOBA's 0.015; the boosted-tree
  version reaches 0.057 but does not port to a web page. Forecast intervals use the holdout RMSE of
  .037. Scripts: <code>extract_monthly.py</code>, <code>predict.py</code>, <code>predict2.py</code>,
  <code>gapclean.py</code>.
</footer>

</div>
<script id="D" type="application/json">__DATA__</script>
<script>
(function(){
const D=JSON.parse(document.getElementById("D").textContent);
const $=s=>document.querySelector(s), LG=D.lg, RM=D.rmse;
const MON={3:"March",4:"April",5:"May",6:"June",7:"July",8:"August",9:"September",10:"October"};
const f3=v=>(v<0?"-":"")+Math.abs(v).toFixed(3).replace(/^0/,"");
const idx={}; D.feats.forEach((f,i)=>idx[f]=i);
const K={ev:"ev",bat_speed:"bs",k:"k",whiff:"wh"};
const byName={}; D.rows.forEach((r,i)=>{(byName[r.n]=byName[r.n]||[]).push(i)});
const names=Object.keys(byName).sort();
const who=$("#who"), mo=$("#mo");
names.forEach(n=>{const o=document.createElement("option");o.value=n;o.textContent=n;who.appendChild(o)});
let cur=D.rows.findIndex(r=>r.n==="Nick Kurtz"&&r.y===2025&&r.m===7);
if(cur<0)cur=0;
const SL=[["s-ev","v-ev","ev","ev","mph"],["s-bs","v-bs","bat_speed","bs","mph"],
          ["s-k","v-k","k","k","pp"],["s-wh","v-wh","whiff","wh","pp"]];

function delta(){
  let d=0;
  SL.forEach(([sid,,feat])=>{
    const raw=+$("#"+sid).value; if(!raw) return;
    const step=(feat==="k"||feat==="whiff")?raw/100:raw;
    d += D.coef[idx[feat]]*step/D.sd[idx[feat]];
  });
  return d;
}
function fillMonths(){
  mo.innerHTML="";
  byName[D.rows[cur].n].forEach(i=>{
    const r=D.rows[i], o=document.createElement("option");
    o.value=i; o.textContent=`${MON[r.m]} ${r.y} · ${r.pa} PA`;
    mo.appendChild(o);
  });
  mo.value=cur;
}
function slope(r,p){
  const s=$("#slope"), W=900,H=150, x0=90,x1=810;
  const lo=.18,hi=.58, X=v=>x0+(v-lo)/(hi-lo)*(x1-x0);
  const g=[];
  g.push(`<line x1="${X(LG)}" y1="22" x2="${X(LG)}" y2="118" stroke="var(--line)" stroke-width="1" stroke-dasharray="3 3"/>`);
  g.push(`<text x="${X(LG)}" y="138" font-size="11" fill="var(--ink3)" text-anchor="middle" font-family="IBM Plex Mono,monospace">league ${f3(LG)}</text>`);
  const band=[X(p-1.96*RM),X(p+1.96*RM)];
  g.push(`<rect x="${band[0]}" y="60" width="${band[1]-band[0]}" height="26" fill="var(--accent)" opacity=".13"/>`);
  const pts=[["what he hit",r.w,"var(--ink3)",38],["forecast",p,"var(--accent)",73],
             ["actual next",r.nx,"var(--ink)",108]];
  pts.forEach(([lab,v,c,y])=>{
    g.push(`<line x1="${x0}" y1="${y}" x2="${x1}" y2="${y}" stroke="var(--soft)" stroke-width="1"/>`);
    g.push(`<circle cx="${X(v)}" cy="${y}" r="6" fill="${c}"/>`);
    g.push(`<text x="${x0-10}" y="${y+4}" font-size="11.5" fill="var(--ink3)" text-anchor="end">${lab}</text>`);
    g.push(`<text x="${X(v)}" y="${y-11}" font-size="12" fill="${c}" text-anchor="middle" font-weight="600" font-family="IBM Plex Mono,monospace">${f3(v)}</text>`);
  });
  s.innerHTML=`<g font-family="IBM Plex Sans,sans-serif">${g.join("")}</g>`;
}
function render(){
  const r=D.rows[cur], p=r.p+delta();
  $("#r-w").textContent=f3(r.w);
  $("#r-w").className="n "+(r.w>LG?"w":"c");
  $("#r-ws").textContent=`${r.pa} PA · ${MON[r.m]} ${r.y} · xwOBA ${f3(r.x)}`;
  $("#r-p").textContent=f3(p);
  $("#r-p").className="n";
  $("#r-ps").textContent=`±${(1.96*RM).toFixed(3).replace(/^0/,"")} at 95%`;
  $("#r-a").textContent=f3(r.nx);
  $("#r-a").className="n "+(r.nx>LG?"w":"c");
  $("#r-as").textContent=`${r.npa} PA the next month`;
  const dev=r.w-LG, keep=dev?(p-LG)/dev:0;
  const v=$("#verdict");
  const hot=dev>0;
  v.className="verdict "+(Math.abs(keep)<.4?(hot?"c":"w"):"");
  const pct=Math.round(Math.max(0,Math.min(1,keep))*100);
  v.innerHTML=`He was <b>${f3(Math.abs(dev))} ${hot?"above":"below"}</b> league average.
    The machine keeps <b>${pct}%</b> of that and gives the rest back to the mean, forecasting
    <b>${f3(p)}</b>. He actually hit <b>${f3(r.nx)}</b> —
    ${Math.abs(r.nx-p)<1.96*RM?"inside the forecast interval":"<b>outside</b> the forecast interval"}.`;
  $("#cap").textContent=`The shaded band is the 95% forecast interval. It is ${(2*1.96*RM).toFixed(3)} wide, which is most of the league's range — that width is the honest message of this whole page.`;
  SL.forEach(([sid,vid,feat,key,u])=>{
    const raw=+$("#"+sid).value;
    const base=(feat==="k"||feat==="whiff")?r[key]*100:r[key];
    $("#"+vid).textContent=(base+raw).toFixed(1)+(u==="pp"?"%":" "+u)+(raw?` (${raw>0?"+":""}${raw})`:"");
  });
  slope(r,p);
}
who.addEventListener("change",()=>{cur=byName[who.value][0];fillMonths();reset()});
mo.addEventListener("change",()=>{cur=+mo.value;reset()});
function reset(){SL.forEach(([s])=>$("#"+s).value=0);render()}
$("#reset").addEventListener("click",reset);
SL.forEach(([s])=>$("#"+s).addEventListener("input",render));
$("#jump").addEventListener("change",e=>{
  const v=e.target.value; if(!v) return;
  let pool;
  if(v==="hot") pool=D.rows.map((r,i)=>[i,r]).filter(([,r])=>r.w>LG+.08);
  else if(v==="cold") pool=D.rows.map((r,i)=>[i,r]).filter(([,r])=>r.w<LG-.08);
  else pool=D.rows.map((r,i)=>[i,r]).sort((a,b)=>Math.abs(b[1].p-b[1].w)-Math.abs(a[1].p-a[1].w)).slice(0,40);
  const pick=pool[Math.floor(Math.random()*pool.length)];
  cur=pick[0]; who.value=D.rows[cur].n; fillMonths(); mo.value=cur; reset();
  e.target.value="";
});

// calibration slope chart
(function(){
  const s=$("#cal"), W=900, H=300, pad=54;
  const cols=["var(--ink3)","var(--mid)","var(--accent)"];
  const all=D.cal.flatMap(c=>c.bins.flatMap(b=>[b.pred,b.act]));
  const lo=Math.min(...all)-.01, hi=Math.max(...all)+.01;
  const Y=v=>H-58-(v-lo)/(hi-lo)*(H-100);
  const g=[];
  D.cal.forEach((c,ci)=>{
    const xa=pad+ci*((W-pad*2)/3)+20, xb=xa+((W-pad*2)/3)-110;
    g.push(`<text x="${(xa+xb)/2}" y="24" font-size="12.5" font-weight="600" fill="var(--ink)" text-anchor="middle" font-family="Archivo,sans-serif">sorted by ${c.label}</text>`);
    g.push(`<text x="${xa}" y="${H-30}" font-size="10.5" fill="var(--ink3)" text-anchor="middle" font-family="IBM Plex Mono,monospace">claimed</text>`);
    g.push(`<text x="${xb}" y="${H-30}" font-size="10.5" fill="var(--ink3)" text-anchor="middle" font-family="IBM Plex Mono,monospace">actually hit</text>`);
    g.push(`<text x="${(xa+xb)/2}" y="${H-12}" font-size="11" fill="${cols[ci]}" text-anchor="middle" font-weight="600" font-family="IBM Plex Mono,monospace">spread ${(c.spread).toFixed(3).replace(/^0/,"")}</text>`);
    c.bins.forEach(b=>{
      g.push(`<line x1="${xa}" y1="${Y(b.pred)}" x2="${xb}" y2="${Y(b.act)}" stroke="${cols[ci]}" stroke-width="1.6" opacity=".85"/>`);
      g.push(`<circle cx="${xa}" cy="${Y(b.pred)}" r="3.4" fill="${cols[ci]}"/>`);
      g.push(`<circle cx="${xb}" cy="${Y(b.act)}" r="3.4" fill="${cols[ci]}"/>`);
    });
    if(ci===0) c.bins.forEach(b=>{
      g.push(`<text x="${xa-8}" y="${Y(b.pred)+4}" font-size="10.5" fill="var(--ink3)" text-anchor="end" font-family="IBM Plex Mono,monospace">${f3(b.pred)}</text>`);
    });
  });
  g.push(`<line x1="${pad-6}" y1="${Y(LG)}" x2="${W-14}" y2="${Y(LG)}" stroke="var(--line)" stroke-dasharray="4 4"/>`);
  s.innerHTML=`<g font-family="IBM Plex Sans,sans-serif">${g.join("")}</g>`;
})();

who.value=D.rows[cur].n; fillMonths(); mo.value=cur; render();
})();
</script>
"""
open("regression_machine.html","w").write(HEAD + BODY.replace("__DATA__", D))
import os; print("wrote regression_machine.html", os.path.getsize("regression_machine.html"))
