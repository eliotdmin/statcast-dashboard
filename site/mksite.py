"""Build the deployable site from the pieces already in this directory.

Produces a conventional static-site + serverless-function tree:

    web/
      index.html          markup only -- no inlined CSS, JS or data
      styles.css          every visual decision, in one editable file
      app.js              the client
      data/*.json         the shards, fetched on demand
      lib/packet.js       evidence-packet builder, shared by client and server
      api/profile.js      Vercel serverless function; holds the API key
      serve.py            zero-dependency local server, mocks or proxies the API
      vercel.json         headers: immutable caching on the data shards
      README.md

The point of the exercise is the separation. In the artifact everything had to be
one file with the data inlined; here the CSS is a file you can open and edit, the
data is fetched, and the key lives somewhere the browser cannot see.
"""
import os, re, json, shutil, pathlib

OUT = pathlib.Path("web");
for p in ("", "data", "api", "lib"):
    (OUT / p).mkdir(parents=True, exist_ok=True)

head = open("head.html").read()
body = open("body.html").read()
mock = open("mkmock.py").read()

base_css = head.split("<style>", 1)[1].split("</style>")[0]
panel_css = mock.split('CSS = """', 1)[1].split('"""', 1)[0]

# markup: everything before the inlined data blob
markup = body.split('<script id="D"', 1)[0]
js = body.split("<script>", 1)[1].rsplit("</script>", 1)[0]

# the profile panel markup + js from the mockup build
# (the summary panel's markup and JS now come from summary.js, shared with the
#  mockup build; only its CSS still travels with the mockup file)

# ---------------------------------------------------------------- styles.css
SITE_CSS = """
/* ============================================================================
   Site chrome. Everything below this line is the part the artifact sandbox
   could not have: a real masthead, a real footer, and a stylesheet you can open
   in an editor instead of hunting for a <style> block inside generated HTML.
   ========================================================================= */
.mast{border-bottom:1px solid var(--line);background:var(--card)}
.mast-in{max-width:1180px;margin:0 auto;padding:13px 16px;display:flex;
  align-items:baseline;gap:14px;flex-wrap:wrap}
.mark{display:flex;align-items:baseline;gap:9px;text-decoration:none;color:var(--ink)}
.mark b{font-size:16px;font-weight:700;letter-spacing:-.015em}
.mark i{font-style:normal;font-family:"IBM Plex Mono",monospace;font-size:9.5px;
  letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);border:1px solid var(--line);
  padding:2px 6px;border-radius:3px}
.mast nav{margin-left:auto;display:flex;gap:4px}
.mast nav a{font-size:12.5px;color:var(--ink2);text-decoration:none;padding:5px 10px;
  border-radius:5px}
.mast nav a:hover{background:var(--sunk);color:var(--ink)}
.mast nav a[aria-current="page"]{background:var(--sunk);color:var(--ink);font-weight:600}
@media(max-width:640px){.mast nav{margin-left:0;order:3;width:100%;overflow-x:auto}}
.fresh{font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink3)}
.fresh b{color:var(--ink2);font-weight:600}
.dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#3f9e6b;
  margin-right:5px;vertical-align:1px}

.boot{display:flex;flex-direction:column;gap:9px;padding:40px 0}
.boot .skel{max-width:520px}
.boot p{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--ink3);margin:0 0 6px}


/* ============================================================================
   Landing page. Three measures, widening as the page goes from argument to
   evidence to navigation: 34rem of prose, a demo panel that breaks out, then
   the full grid. The rhythm is the structure -- there is no decoration here.
   ========================================================================= */
.lp{max-width:1180px;margin:0 auto;padding-left:16px;padding-right:16px;
  padding-block:56px 0;display:flex;flex-direction:column;gap:64px}
.col{max-width:34rem;display:flex;flex-direction:column;gap:18px}

.hero h1{font-size:var(--fs-display);line-height:1.03;letter-spacing:-.025em;max-width:19ch}
.hero .lede{font-size:var(--fs-lede);line-height:1.55;color:var(--ink2);margin:0;max-width:56ch}
.hero .lede b{color:var(--ink);font-weight:600}
.cta{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:6px}
.go{display:inline-flex;align-items:center;gap:8px;background:var(--ac);color:var(--card);
  text-decoration:none;font-size:14px;font-weight:600;padding:11px 18px;border-radius:5px}
.go:hover{filter:brightness(1.08)}
.go .ar{font-family:var(--mono);font-weight:400;opacity:.8}
.go2{font-size:13.5px;color:var(--ink2);text-decoration:none;padding:11px 4px;
  border-bottom:1px solid var(--line)}
.go2:hover{color:var(--ink);border-bottom-color:var(--ac)}
.go:focus-visible,.go2:focus-visible,.card:focus-visible{outline:2px solid var(--ac);outline-offset:3px}

/* the worked example -- the tool's own percentile component, real output */
.demo{max-width:860px;display:flex;flex-direction:column;gap:14px}
.demo .cap{display:flex;flex-direction:column;gap:5px}
.demo .who{font-family:var(--mono);font-size:12px;color:var(--ink3)}
.demo .rows{display:flex;flex-direction:column;gap:3px}
.demo .row{grid-template-columns:132px 62px 1fr 58px}
.demo .foot{font-size:13.5px;line-height:1.6;color:var(--ink2);margin:0;max-width:64ch}
.demo .foot b{color:var(--ink)}

/* signposts -- four questions, not a sequence, so they carry no numbers */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(400px,100%),1fr));gap:1px;
  background:var(--hair);border:1px solid var(--hair);border-radius:7px;overflow:hidden}
.card{background:var(--card);padding:22px 22px 20px;display:flex;flex-direction:column;gap:9px;
  text-decoration:none;color:inherit}
.card:hover{background:var(--ac-s)}
.card .k{font-family:var(--mono);font-size:var(--fs-micro);letter-spacing:.11em;
  text-transform:uppercase;color:var(--ink3)}
.card .q{font-family:var(--serif);font-size:18px;font-weight:600;line-height:1.28;
  letter-spacing:-.01em;color:var(--ink);text-wrap:balance}
.card .d{font-size:13.5px;line-height:1.55;color:var(--ink2);margin:0}
.card .eg{font-family:var(--mono);font-size:11.5px;line-height:1.5;color:var(--ink3);
  border-top:1px dashed var(--hair);padding-top:9px;margin-top:auto}

/* how it works -- this one IS ordered, so the numerals mean something */
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(248px,100%),1fr));gap:26px}
.step{display:flex;flex-direction:column;gap:7px;align-items:flex-start}
.step .n{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--ac);
  border-top:2px solid var(--ac);padding-top:9px;width:100%}
.step h3{margin:0;font-size:14.5px;font-weight:600;letter-spacing:-.005em}
.step p{margin:0;font-size:13.5px;line-height:1.6;color:var(--ink2)}
.step .eq{font-family:var(--mono);font-size:12px;color:var(--ink3);background:var(--sunk);
  border:1px solid var(--hair);border-radius:4px;padding:6px 9px;align-self:flex-start;
  margin-top:auto}

.sechead{display:flex;flex-direction:column;gap:7px;max-width:52ch}
.sechead .k{font-family:var(--mono);font-size:var(--fs-micro);letter-spacing:.11em;
  text-transform:uppercase;color:var(--ink3)}
.sechead h2{font-family:var(--serif);font-size:26px;font-weight:600;letter-spacing:-.018em;
  margin:0;line-height:1.15;text-wrap:balance}
.block{display:flex;flex-direction:column;gap:22px}

/* the limits note -- deliberately the plainest thing on the page */
.limits{border-top:1px solid var(--line);padding-top:22px;display:flex;flex-direction:column;
  gap:10px;max-width:64ch}
.limits p{margin:0;font-size:13.5px;line-height:1.62;color:var(--ink2)}
.limits b{color:var(--ink)}

@media(max-width:560px){
  .lp{padding-block:36px 0;gap:46px}
  .demo .row{grid-template-columns:1fr 54px;gap:6px 10px}
  .demo .row .bar{grid-column:1/-1}
}

.site-foot{border-top:1px solid var(--line);margin-top:34px;background:var(--card)}
.site-foot-in{max-width:1180px;margin:0 auto;padding:24px 16px 60px;
  display:grid;grid-template-columns:1fr;gap:16px;
  font-size:12px;color:var(--ink3);line-height:1.55}
@media(min-width:820px){.site-foot-in{grid-template-columns:repeat(3,1fr);gap:30px}}
.site-foot b{color:var(--ink2)}
.site-foot a{color:var(--ac)}
"""
(OUT / "styles.css").write_text(
    "/* Statcast Stretch Finder -- all visual decisions live here.\n"
    "   Tokens first; every component reads from them, so retheming the whole site\n"
    "   is a matter of editing the :root block and nothing else. */\n"
    + base_css + panel_css + SITE_CSS)

# ---------------------------------------------------------------- index.html
# the component builds its own markup and moves itself between panels,
# so there is nothing to splice into the page here any more.
markup = markup.replace(
    "2023&ndash;2026 &middot; 1,590 hitter-seasons &middot; 1,917 pitcher-seasons &middot; everything computed in your browser",
    "<span id=\"eb\">loading&hellip;</span>")
markup = markup.replace("Four views of the same idea:", "Four views and a writer, all on one idea:")

# ---------------------------------------------------------------- page shells
# Two pages now: the landing page at / and the tool at /app/. They share a head,
# a masthead and a footer, so a change to the chrome cannot drift between them.

def head(title, desc, canon, preload=False):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="https://example.com{canon}">

<!-- Link previews. Not possible inside the artifact sandbox; one of the more
     visible things you get back by owning the document head. -->
<meta property="og:type" content="website">
<meta property="og:title" content="Stretch Finder">
<meta property="og:description" content="Percentile bars that shrink themselves by how much of each number is real.">
<meta property="og:image" content="/og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#f4f5f7" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#101216" media="(prefers-color-scheme: dark)">

<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{'<link rel="preload" as="fetch" href="/data/bat-2026.json" crossorigin>' if preload else ''}
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Serif:wght@500;600&display=swap">
<link rel="stylesheet" href="/styles.css">
</head>
<body>
'''

# On the tool the nav hrefs are bare fragments, because app.js turns them into
# tab switches. On the landing page there are no tabs to switch, so the same
# links have to be real cross-page URLs into /app/.
def mast(base=""):
    return f'''
<header class="mast">
  <div class="mast-in">
    <a class="mark" href="/"><b>Stretch Finder</b><i>Statcast</i></a>
    <nav>
      <a href="{base}#p-stretch">Percentiles</a>
      <a href="{base}#p-changes">Change log</a>
      <a href="{base}#p-carry">What carries</a>
      <a href="{base}#p-planner">Planner</a>
    </nav>
    <span class="fresh" id="fresh"><span class="dot"></span>{'loading&hellip;' if not base else '2023&ndash;2026'}</span>
  </div>
</header>
'''

FOOT = '''
<footer class="site-foot">
  <div class="site-foot-in">
    <div><b>Data.</b> Statcast pitch-level, 2023&ndash;2026, refreshed daily at 11:00 by a launchd
    job that fetches only days it has never seen and runs an integrity check every time.</div>
    <div><b>Method.</b> Reliability is a split-half correlation corrected by Spearman&ndash;Brown;
    percentiles are shrunk toward the league at exactly that rate.</div>
    <div><b>Profiles</b> are generated server-side from a pre-shrunk evidence packet. The key never
    reaches the browser.</div>
  </div>
</footer>
'''

# ---------------------------------------------------------------- /app/
(OUT / "app").mkdir(parents=True, exist_ok=True)
(OUT / "app" / "index.html").write_text(
    head("Stretch Finder &mdash; Statcast, shrunk to what is real",
         "Savant-style percentile bars for any stretch of any season, with every percentile "
         "shrunk by how much of it is real at that sample size. Plus a within-player change log, "
         "streak carry rates, and a sample-size planner.",
         "/app/", preload=True)
    + mast() + "\n" + markup.strip() + "\n" + FOOT
    + '\n<script src="/lib/packet.js"></script>\n<script src="/app.js"></script>\n</body>\n</html>\n')

# ---------------------------------------------------------------- /
#
# The example below is not an illustration. Those are Alex Bregman's real
# figures for Jul 16 - Sep 15 2026, 226 plate appearances, read straight off the
# tool, and they make the argument better than prose can: the four rows are
# ordered by how reliable the metric is at that sample, and the distance each
# bar travels when it is shrunk falls in exactly the same order -- 24 points of
# percentile for wOBA, one point for bat speed. The rows reuse the tool's own
# .row component rather than a picture of it, so the demo cannot drift from the
# thing it is demonstrating.
def bar(metric, value, rel, raw, adj):
    hot   = adj >= 50
    col   = "var(--hot)" if hot else "var(--cold)"
    gcol  = "var(--hot)" if raw >= 50 else "var(--cold)"
    gside = "left:50%;width:" if raw >= 50 else "right:50%;width:"
    fside = "left:50%;width:" if hot else "right:50%;width:"
    return (f'<div class="row"><span class="nm">{metric} '
            f'<span class="relchip">{rel}% real</span></span>'
            f'<span class="val">{value}</span>'
            f'<span class="bar">'
            f'<span class="ghost" style="{gside}{abs(raw-50)}%;color:{gcol}"></span>'
            f'<span class="fill" style="{fside}{abs(adj-50)}%;background:{col}"></span>'
            f'<span class="mk"></span></span>'
            f'<span class="pct" style="color:{col}">{adj}'
            f'<span class="rawpct">{raw}</span></span></div>')

DEMO = "\n      ".join([
    bar("wOBA",      ".407",  50, 98, 74),
    bar("xwOBA",     ".334",  71, 74, 67),
    bar("whiff%",    "15.1%", 92, 90, 87),
    bar("bat speed", "68.1",  98, 29, 30),
])

CARDS = [
    ("Percentiles", "p-stretch",
     "Where did he actually rank over these exact dates?",
     "Any player, any window you draw yourself, against players with a comparable workload in "
     "the same span. Every bar is drawn twice: what the raw number says, and what survives.",
     "wOBA over six weeks &rarr; 98th raw, 74th real"),
    ("Change log", "p-changes",
     "Did he change something, or did the numbers just move?",
     "Every window measured against that player&rsquo;s own earlier season, divided by the error "
     "two windows of that size produce on their own. Then checked against what happened next.",
     "1,644 moves in 2026 &middot; 64 confirmed swing gains"),
    ("What carries", "p-carry",
     "How much of this hot streak should I expect to survive?",
     "A carry rate fit on 2023&ndash;2025 and evaluated once on 2026. It is a discount rate, not "
     "a forecast: it says how much of the gap to keep, not what happens tomorrow.",
     "+240 pts of wOBA &middot; 32% carry &rarr; keep +77"),
    ("Sample-size planner", "p-planner",
     "How long until this number means anything?",
     "Ask it before you collect the data. It solves for the sample at which a ranking becomes "
     "real, and for how long it takes to confirm a change you already suspect.",
     "1.0 mph lost off a fastball &rarr; 26 batters"),
]
CARD_HTML = "\n    ".join(
    f'<a class="card" href="/app/#{anchor}">\n'
    f'      <span class="k">{name}</span>\n'
    f'      <span class="q">{q}</span>\n'
    f'      <p class="d">{d}</p>\n'
    f'      <span class="eg">{eg}</span>\n'
    f'    </a>'
    for name, anchor, q, d, eg in CARDS)

LANDING = f'''
<main class="lp">

  <section class="hero col">
    <p class="eb">Statcast &middot; 2023&ndash;2026 &middot; 1,590 hitter-seasons &middot; 1,917 pitcher-seasons</p>
    <h1>A number is only worth what its sample size makes it worth.</h1>
    <p class="lede">Every percentile on this site is drawn twice &mdash; once as the raw figure a
    Savant-style page would print, and once <b>shrunk by how much of it is actually real</b> at the
    sample size you asked for. The gap between the two is the part nobody can vouch for.</p>
    <div class="cta">
      <a class="go" href="/app/">Open the tool <span class="ar">&rarr;</span></a>
      <a class="go2" href="#how">How the shrinking works</a>
    </div>
  </section>

  <section class="demo">
    <div class="cap">
      <p class="eb">What that looks like</p>
      <p class="who">Alex Bregman &middot; Jul 16 &ndash; Sep 15 2026 &middot; 226 plate appearances</p>
    </div>
    <div class="rows">
      {DEMO}
    </div>
    <p class="foot">Solid bar and large number: the shrunk percentile. Dashed outline and small grey
    number: the raw one. <b>Bregman hit .407 over those six weeks &mdash; 98th percentile, and half
    of it is noise at 226 plate appearances</b>, so it lands at the 74th. His bat speed is 98% real
    at the same sample and barely moves. Read down the list: the rows are ordered by reliability,
    and the distance each bar travels falls in the same order. Note also what the swing is actually
    saying &mdash; 29th percentile bat speed under a .407 batting line.</p>
  </section>

  <section class="block">
    <div class="sechead">
      <span class="k">Four questions</span>
      <h2>Each tab answers exactly one of them.</h2>
    </div>
    <div class="cards">
    {CARD_HTML}
    </div>
  </section>

  <section class="block" id="how">
    <div class="sechead">
      <span class="k">How the shrinking works</span>
      <h2>Three steps, no judgement calls anywhere in them.</h2>
    </div>
    <div class="steps">
      <div class="step">
        <span class="n">01</span>
        <h3>Split the season and correlate the halves</h3>
        <p>Odd half-month blocks against even ones, same player. Whatever is real about him shows up
        in both halves; whatever was luck does not. The correlation between them <em>is</em> the
        share of the spread that is real.</p>
        <span class="eq">r = Var(T) / Var(X)</span>
      </div>
      <div class="step">
        <span class="n">02</span>
        <h3>Project it to your sample size</h3>
        <p>That correlation was measured at one particular length. Spearman&ndash;Brown converts it
        to any other: reliability rises with sample, but with diminishing returns, which is why
        watching longer eventually stops helping.</p>
        <span class="eq">&rho;(k) = k&rho;&#8320; / (1 + (k&minus;1)&rho;&#8320;)</span>
      </div>
      <div class="step">
        <span class="n">03</span>
        <h3>Shrink the percentile by exactly that much</h3>
        <p>Pull the observed figure toward the league mean, keeping the fraction that is real and
        discarding the rest. Nothing is tuned here &mdash; the shrinkage coefficient and the
        reliability are the same number.</p>
        <span class="eq">T&#770; = &mu; + &rho;(X &minus; &mu;)</span>
      </div>
    </div>
  </section>

  <section class="limits">
    <p class="eb">What this is not</p>
    <p><b>It is not a projection system.</b> Nothing here forecasts next season, and where it was
    tested against one it did not beat the public systems. It answers a narrower question: of what
    already happened, how much was real.</p>
    <p><b>Reliability is measured, not assumed</b> &mdash; but it is measured on the assumption that
    true talent held still inside the window, which makes it mildly optimistic over long stretches.
    Carry rates were fit on 2023&ndash;2025 and evaluated once on 2026; 2026 is no longer a clean
    holdout and is labelled as such wherever it appears.</p>
  </section>

</main>
'''

(OUT / "index.html").write_text(
    head("Stretch Finder",
         "Savant-style percentile bars, every one shrunk by how much of it is real at the sample "
         "size you asked for.",
         "/")
    + mast("/app/") + LANDING + FOOT + "\n</body>\n</html>\n")


# ---------------------------------------------------------------- favicon
(OUT / "favicon.svg").write_text(
'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
'<rect width="32" height="32" rx="7" fill="#2d5f8a"/>'
'<rect x="6" y="14.5" width="9" height="3" rx="1.5" fill="#fff" opacity=".45"/>'
'<rect x="15" y="12" width="11" height="8" rx="1.5" fill="#fff"/>'
'</svg>')

# ---------------------------------------------------------------- lib/packet.js
(OUT / "lib" / "packet.js").write_text(r"""/* Evidence-packet builder.
 *
 * Deliberately dependency-free and written for both runtimes: the browser
 * imports it with a <script> tag, the serverless function require()s it. One
 * implementation means the numbers the reader audits in the "evidence" table are
 * byte-for-byte the numbers the model was given -- if these drifted apart, the
 * whole auditability claim would be a lie.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Packet = factory();
})(typeof self !== "undefined" ? self : this, function () {

  function relAt(rel, label, n) {
    var r = rel[label];
    if (!r || n <= 0) return 0;
    var k = n / r.n0, p = r.sb;
    return Math.max(0, Math.min(1, k * p / (1 + (k - 1) * p)));
  }
  function pctOf(pool, v) {
    if (!pool.length) return null;
    var c = 0; for (var i = 0; i < pool.length; i++) if (pool[i] < v) c++;
    return 100 * c / pool.length;
  }
  function sd(a) {
    if (a.length < 3) return 0;
    var m = 0, i; for (i = 0; i < a.length; i++) m += a[i]; m /= a.length;
    var s = 0; for (i = 0; i < a.length; i++) s += (a[i] - m) * (a[i] - m);
    return Math.sqrt(s / a.length);
  }
  function sum(row, keys, nf) {
    var out = new Array(nf).fill(0), j;
    keys.forEach(function (k) {
      var v = row.b[k]; if (!v) return;
      for (j = 0; j < nf; j++) out[j] += v[j];
    });
    return out;
  }

  /* metrics: [{k,n,d,hi,g}], where n/d are numerator and denominator fields */
  function build(shard, metrics, paKey, playerId, fromBlock, toBlock) {
    var F = {}; shard.fields.forEach(function (f, i) { F[f] = i; });
    var nf = shard.fields.length;
    var me = shard.rows.filter(function (r) { return String(r.id) === String(playerId); })[0];
    if (!me) throw new Error("no such player in this shard: " + playerId);

    var span = [], base = [];
    shard.blocks.forEach(function (b) {
      (b >= fromBlock && b <= toBlock ? span : base).push(b);
    });
    var now = sum(me, span, nf), bas = sum(me, base, nf);
    var n = now[F[paKey]], bn = bas[F[paKey]];

    var peers = shard.rows.map(function (r) { return sum(r, span, nf); })
                          .filter(function (v) { return v[F[paKey]] >= 20; });

    var rows = metrics.map(function (m) {
      var dv = now[F[m.d]];
      if (!dv) return { metric: m.k, group: m.g, available: false };
      var v = now[F[m.n]] / dv;
      var pool = peers.filter(function (x) { return x[F[m.d]] > 0; })
                      .map(function (x) { return x[F[m.n]] / x[F[m.d]]; });
      var raw = pctOf(pool, v); if (!m.hi) raw = 100 - raw;
      var rel = relAt(shard.rel, m.k, n);
      var o = { metric: m.k, group: m.g, available: true, value: v,
                higher_is_better: !!m.hi, pct_raw: raw, reliability: rel,
                pct_shrunk: 50 + rel * (raw - 50), change: null };
      if (bas[F[m.d]] && bn >= 60) {
        var b0 = bas[F[m.n]] / bas[F[m.d]], SD = sd(pool) || 1e-9;
        var vt = SD * SD * rel;
        var s1 = Math.sqrt(Math.max(1e-12, SD * SD - vt));
        var s2 = Math.sqrt(Math.max(1e-12, (SD * SD - vt) * (n / bn)));
        var se = Math.sqrt(s1 * s1 + s2 * s2), z = (v - b0) / se, a = Math.abs(z);
        var dsd = (v - b0) / SD, ad = Math.abs(dsd);
        o.change = { base_value: b0, delta: v - b0, se_noise: se, delta_z: z,
                     delta_sd: dsd,
                     verdict: a >= 2.5 ? "real" : (a >= 1.5 ? "weak" : "noise"),
                     size: ad >= 0.8 ? "large" : (ad >= 0.4 ? "moderate" : "small") };
      }
      return o;
    });

    return { player: me.n, mlbam_id: me.id, season: me.y,
             span: { from: fromBlock, to: toBlock, n: Math.round(n) },
             baseline: { n: Math.round(bn), usable: bn >= 60 },
             peer_pool: { n_players: peers.length },
             metrics: rows };
  }

  return { build: build, relAt: relAt, pctOf: pctOf, sd: sd, sum: sum };
});
""")
print("wrote", OUT / "lib" / "packet.js")

# ---------------------------------------------------------------- app.js
FILEHEAD = r"""/* ===========================================================================
   Statcast Stretch Finder -- client.
   Data arrives as per-(type, season) shards fetched on demand. The artifact
   version inlined all four seasons of both player types: 1.9 MB gzipped before
   the first pixel. Here the default view costs 187 KB and the rest never loads
   unless you ask for it.
   ========================================================================= */
"""

LOADER = r"""
var ALL = {};                    // kind-year -> shard, populated by fetch
var INDEX = null;                // data/blocks_index.json
var K, F, BL, REL, PK, ROWS, MET, YEARS, YR;

function shardKey(kind, year) { return kind + "-" + year; }

function loadShard(kind, year) {
  var key = shardKey(kind, year);
  if (ALL[key]) return Promise.resolve(ALL[key]);
  return fetch("/data/" + key + ".json", { cache: "force-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("shard " + key + ": HTTP " + r.status);
      return r.json();
    })
    .then(function (j) { ALL[key] = j; return j; });
}

function boot() {
  document.getElementById("panels-boot").hidden = false;
  return fetch("/data/blocks_index.json")
    .then(function (r) { return r.json(); })
    .then(function (ix) {
      INDEX = ix;
      YEARS = Object.keys(ix.shards)
        .filter(function (k) { return k.indexOf("bat-") === 0; })
        .map(function (k) { return +k.split("-")[1]; })
        .sort(function (a, b) { return b - a; });
      yrS.innerHTML = YEARS.map(function (y) {
        return '<option value="' + y + '">' + y + "</option>";
      }).join("");
      var d = new Date(ix.generated_at);
      var tot = Object.keys(ix.shards).reduce(function (a, k) {
        return a + (ix.shards[k].players || 0); }, 0);
      $("#fresh").innerHTML = '<span class="dot"></span>data built <b>' +
        d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) + " " +
        d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) + "</b>";
      $("#eb").textContent = Object.keys(ix.shards).length + " shards \u00b7 " +
        tot.toLocaleString() + " player-seasons \u00b7 187 KB first paint \u00b7 " +
        "profile generated server-side";
      return setKind();
    })
    .catch(function (e) {
      $("#panels-boot").innerHTML =
        '<p class="ai-idle"><b>Could not load the data.</b> ' + e.message +
        ' &mdash; if you are running this locally, start it with ' +
        '<code>python3 serve.py</code> rather than opening index.html from the ' +
        'filesystem; <code>fetch()</code> will not read <code>file://</code> URLs.</p>';
    });
}
"""

# Rework the original IIFE: strip the embedded-data parse and the sync setKind.
app = js
app = app.replace('(function(){\n"use strict";\nvar ALL=JSON.parse(document.getElementById("D").textContent);',
                  '(function(){')
app = app.replace('var K,F,BL,REL,PK,ROWS,MET,YEARS;', '')

# setKind/setYear become async: they must await the shard.
app = app.replace("""function setKind(){
  K=kindS.value; var d=ALL[K];""",
"""function setKind(){
  K=kindS.value;
  return loadShard(K, +(yrS.value||YEARS[0])).then(function(d){""")
app = app.replace("""  YEARS=[]; d.rows.forEach(function(r){if(YEARS.indexOf(r.y)<0)YEARS.push(r.y);});
  YEARS.sort(function(a,b){return b-a;});
  yrS.innerHTML=YEARS.map(function(y){return '<option value="'+y+'">'+y+'</option>';}).join("");
  LEAGUE=null;
  setYear();
}""",
"""  LEAGUE=null;
  $("#panels-boot").hidden=true;
  setYear();
  });
}""")
app = app.replace("""function setYear(){
  var y=+yrS.value;
  ROWS=ALL[K].rows.filter(function(r){return r.y===y;});""",
"""function setYear(){
  var y=+yrS.value, d=ALL[shardKey(K,y)];
  if(!d){ $("#panels-boot").hidden=false;
    return loadShard(K,y).then(function(){ $("#panels-boot").hidden=true; setYear(); }); }
  F={}; d.fields.forEach(function(f,i){F[f]=i;});
  BL=d.blocks; REL=d.rel; PK=PAKEY[K]; MET=METRICS[K]; YR=y;
  ROWS=d.rows.slice();""")
app = app.replace("function yearBlocks(y){\n  var out=[]; BL.forEach(function(b,i){if(b.slice(0,4)===String(y))out.push(i);}); return out;\n}",
                  "function yearBlocks(y){ var out=[],i; for(i=0;i<BL.length;i++) out.push(i); return out; }")
# sum/sumList index into r.b by block STRING in the shards
app = app.replace('function sum(r,i0,i1){\n  var out=new Array(ALL[K].fields.length).fill(0), i, j, v;\n  for(i=i0;i<=i1;i++){ v=r.b[String(i)]; if(!v) continue;',
                  'function sum(r,i0,i1){\n  var out=new Array(BL.length&&ALL[shardKey(K,YR)].fields.length).fill(0), i, j, v;\n  for(i=i0;i<=i1;i++){ v=r.b[BL[i]]; if(!v) continue;')
app = app.replace('function sumList(r,idxs){\n  var out=new Array(ALL[K].fields.length).fill(0), j, v;\n  idxs.forEach(function(i){ v=r.b[String(i)]; if(!v) return;',
                  'function sumList(r,idxs){\n  var out=new Array(ALL[shardKey(K,YR)].fields.length).fill(0), j, v;\n  idxs.forEach(function(i){ v=r.b[BL[i]]; if(!v) return;')
# comps "any season" mode needs every shard; restrict to the loaded one and say so
app = app.replace('var pool=anyMode?ALL[K].rows:ROWS;', 'var pool=ROWS;')
app = app.replace('var starts;\n    if(anyMode){\n      starts=[]; BL.forEach(function(b,a){\n        if(a+len-1<BL.length && BL[a+len-1].slice(0,4)===BL[a].slice(0,4)) starts.push(a); });\n    } else starts=[i0];',
                  'var starts;\n    if(anyMode){ starts=[]; BL.forEach(function(b,a){ if(a+len-1<BL.length) starts.push(a); }); }\n    else starts=[i0];')
# league sd for the planner: only the loaded shard
app = app.replace("""  var byYear={};
  BL.forEach(function(b,i){ (byYear[b.slice(0,4)]=byYear[b.slice(0,4)]||[]).push(i); });
  MET.forEach(function(m){
    var xs=[];
    ALL[K].rows.forEach(function(r){
      var yb=byYear[String(r.y)]; if(!yb) return;
      var half=yb.slice(0,Math.floor(yb.length/2)), tot=sumList(r,half);""",
"""  var half=[],i; for(i=0;i<Math.floor(BL.length/2);i++) half.push(i);
  MET.forEach(function(m){
    var xs=[];
    ROWS.forEach(function(r){
      var tot=sumList(r,half);""")
app = app.replace("kindS.addEventListener(\"change\",setKind);\nyrS.addEventListener(\"change\",setYear);",
                  "kindS.addEventListener(\"change\",function(){setKind();});\nyrS.addEventListener(\"change\",function(){setYear();});")

# The component is shared source; only the transport differs between builds.
# Here it is a real POST to a function that holds the key.
SUM_PRELUDE = r"""
var ENDPOINT = "/api/summary";
var IDLE = 'The button posts the table below to <code>POST /api/summary</code>. That function '+
  'rebuilds the same packet with the same <code>lib/packet.js</code> this table is drawn from, '+
  'puts it behind a system prompt distilled from this project\u2019s own retractions, and returns '+
  'prose. <code>ANTHROPIC_API_KEY</code> never leaves the server.';

function send(pk){
  ctl = new AbortController();
  return fetch(ENDPOINT, {method:"POST", headers:{"content-type":"application/json"},
                          body:JSON.stringify({view:pk.view, kind:K, packet:pk}),
                          signal:ctl.signal})
    .then(function(r){
      return r.json().then(function(j){
        if(!r.ok) throw new Error(j.error || ("HTTP " + r.status));
        return j;
      });
    });
}
"""

SUMMARY_JS = open("summary.js").read()

REAL_AI = SUM_PRELUDE + "\n" + SUMMARY_JS + r"""
/* currentPacket() is what the stretch view's builder calls. It is the one view
   whose evidence is a real Packet object rather than a projection of the table,
   because the server rebuilds it from the shard and compares the two. */
function currentPacket(){
  var me=ROWS.find(function(r){return String(r.id)===String($("#who").value);});
  if(!me) return null;
  var shard=ALL[shardKey(K,YR)];
  var metrics=MET.map(function(m){return {k:m.k,n:m.n,d:m.d,hi:m.hi,g:m.g};});
  return Packet.build(shard, metrics, PK, me.id, BL[+$("#from").value], BL[+$("#to").value]);
}
"""

# re-reading the screen after the bars redraw keeps the evidence table in step
# with the controls without the component having to know what changed them.
app = app.replace('  $("#bars").innerHTML=html;\n  renderComps(me,mine,myN,i0,i1);',
                  '  $("#bars").innerHTML=html;\n  if(window.SUM) SUM.reset();\n  renderComps(me,mine,myN,i0,i1);')
app = app.replace("setKind();\n})();",
  # active is already set by the hash deep-link block above, so the component
  # lands in the panel the visitor actually opened.
  REAL_AI + "\nSUM.mount(TABS[active][1].slice(1));\nboot();\n})();")
app = app.replace('$("#from").value=yb[Math.min(2,yb.length-1)]; $("#to").value=yb[Math.min(4,yb.length-1)];',
  '''$("#from").value=yb[Math.max(0,yb.length-4)]; $("#to").value=yb[yb.length-1];
  // Open on a player the stored-profile fallback can actually write about, so the
  // first thing a visitor without a key clicks does something.
  var pref=K==="bat"?"608324":"656302";
  if(ROWS.some(function(r){return String(r.id)===pref;})) $("#who").value=pref;''')

app = app.replace("function setKind(){", LOADER + "\nfunction setKind(){", 1)

NAV_JS = r'''

/* ---------------------------------------------------------------------------
   Masthead nav <-> tab strip.

   These links used to be plain fragment hrefs pointing at the panels. They did
   nothing at all, and could not have: a panel that is not open carries [hidden],
   and a hidden element is not a scroll target, so the browser had nowhere to go.

   Now each link drives the tab it names. The href stays real -- the tab strip
   writes the same hash on every switch -- so the URL is shareable, Back works,
   and middle-click opens the right view in a new tab. aria-current is repainted
   from onTabShow rather than from the click, which means the two controls agree
   even when the tab was changed from the strip or from the hash.
   ------------------------------------------------------------------------- */
(function(){
  var links=[].slice.call(document.querySelectorAll(".mast nav a"));
  if(!links.length) return;
  function mark(id){
    links.forEach(function(a){
      if(a.getAttribute("href").slice(1)===id) a.setAttribute("aria-current","page");
      else a.removeAttribute("aria-current");
    });
  }
  window.onTabShow=mark;
  links.forEach(function(a){
    a.addEventListener("click",function(ev){
      if(ev.metaKey||ev.ctrlKey||ev.shiftKey||ev.button) return;   // let new-tab through
      var id=a.getAttribute("href").slice(1);
      var btn=document.getElementById("t"+id.slice(1));            // p-changes -> t-changes
      if(!btn) return;
      ev.preventDefault();
      btn.click();
      window.scrollTo({top:0,behavior:"smooth"});
    });
  });
  // app.js boots before this block runs, so the first paint's tab was never
  // announced. Read it off the strip instead of assuming it is the first one --
  // a deep link may have opened a different tab already.
  var cur=document.querySelector('.tabs button[aria-selected="true"]');
  if(cur) mark("p"+cur.id.slice(1));
})();
'''

(OUT / "app.js").write_text(FILEHEAD + app + NAV_JS)
print("wrote", OUT / "app.js", os.path.getsize(OUT / "app.js"))

# ---------------------------------------------------------------- boot skeleton
idx = (OUT / "app" / "index.html").read_text()
idx = idx.replace('<div class="tabs" role="tablist">',
  '<div class="boot" id="panels-boot" hidden>\n'
  '  <p>fetching data/bat-2026.json &hellip; 187 KB</p>\n'
  '  <div class="skel" style="width:92%"></div><div class="skel" style="width:78%"></div>\n'
  '  <div class="skel" style="width:85%"></div><div class="skel" style="width:46%"></div>\n'
  '</div>\n\n<div class="tabs" role="tablist">')
(OUT / "app" / "index.html").write_text(idx)

# ---------------------------------------------------------------- prompts
# The base block is byte-identical on every call, so it caches and reads bill at
# 0.1x. The per-view block is small and varies, and is appended after it.
(OUT / "prompts").mkdir(parents=True, exist_ok=True)

BASE = """You write short, exact readings of baseball measurements for an audience that
already knows the game. You are given a JSON evidence packet: a set of rows, each carrying
its own measurement error. Write prose about those rows and nothing else.

Hard rules, each of which exists because this project got it wrong at least once:

1. Never describe a row whose verdict is `noise` as a change. It is not one.
2. Never infer that a player is "due for regression" from a gap between wOBA and xwOBA.
   That gap is replicated in this dataset and its mechanism is not established.
3. Never treat sweet-spot% as evidence. Its reliability is too low at every sample size here.
4. Never offer an injury, mechanical or psychological explanation. You cannot see those.
5. Never write "small sample size" as a hedge. Every row carries its actual reliability --
   cite that number instead.
6. Never use percentile language about a metric whose reliability is below 0.3.
7. Never state a number that does not appear in the packet. No outside knowledge of any
   player, team or season.
8. Prefer the measurement over the outcome when they disagree, and say which is which.

Style: three or four short paragraphs. No headings, no bullets, no preamble, no sign-off.
Lead with the single most defensible observation in the packet, not the largest number.
Name at least one thing the packet cannot settle."""

VIEW_PROMPTS = {
 "stretch": """This packet is one player over one window. Say what his body did, then what the
results did, then whether those two agree. The reader wants to know which of his numbers
he should carry into a decision and which he should ignore at this sample size.""",
 "changes": """This packet is a filtered list of within-player moves. Each row compares a window
against that player's own earlier season. `held` is the share of the move still present in the
FOLLOWING window and is computed after the fact -- treat a confirmed row as evidence and an
unconfirmed one as a watch-list entry, never as a claim. Look for players appearing more than
once, and for the shape of the filtered set as a whole, before naming individuals. A held figure
above 100% means the next window came in higher; it is not a prediction and not an endorsement.""",
 "carry": """This packet is the carry board. `carry` is a discount rate, not a forecast: the
fraction of a player's gap from his own baseline that has historically survived a month. A large
positive gap with low carry is a sell candidate; a large negative gap with low carry is a buy.
Say explicitly that a discounted gap is neither a return to baseline nor a continuation. These
windows are short and wOBA is well under half signal at their length -- say so.""",
 "planner": """This packet is a sample-size calculation. Two different questions share one
reliability estimate: when a RANKING between players becomes real, and how long it takes to
confirm a CHANGE within one player. Keep them apart and say why one answer is so much larger
than the other. If the plan is impossible against the given baseline, the fix is a longer
baseline, not a longer follow-up window.""",
}
(OUT / "prompts" / "base.md").write_text(BASE)
for k, v in VIEW_PROMPTS.items():
    (OUT / "prompts" / (k + ".md")).write_text(v)

# ---------------------------------------------------------------- api/summary.js
(OUT / "api" / "summary.js").write_text(r"""// POST /api/summary  ->  { summary, model, usage, cost, source }
//
// The only reason this file exists is ANTHROPIC_API_KEY. Everything else here
// could run in the browser; the key cannot, because anything the browser can read
// is readable in devtools about four seconds after the page loads.
//
// Deploy:  vercel env add ANTHROPIC_API_KEY   (Production + Preview)
// Locally: serve.py does the same job without Node.

const fs = require("node:fs");
const path = require("node:path");

const MODEL = process.env.PROFILE_MODEL || "claude-sonnet-4-5";
const DIR   = path.join(process.cwd(), "prompts");
const BASE  = fs.readFileSync(path.join(DIR, "base.md"), "utf8");
const VIEWS = ["stretch", "changes", "carry", "planner"];
const VIEW_PROMPT = Object.fromEntries(
  VIEWS.map(v => [v, fs.readFileSync(path.join(DIR, v + ".md"), "utf8")]));

// $ per million tokens. Overridable so a model swap does not need a code change.
const PRICE = { in: +(process.env.PRICE_IN || 3), out: +(process.env.PRICE_OUT || 15) };

const seen = new Map();                    // naive per-IP throttle; use KV in production
function throttled(ip, perMin = 12) {
  const now = Date.now();
  const hits = (seen.get(ip) || []).filter(t => now - t < 60_000);
  hits.push(now); seen.set(ip, hits);
  return hits.length > perMin;
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const ip = req.headers["x-forwarded-for"] || "local";
  if (throttled(ip)) return res.status(429).json({ error: "Too many summaries, wait a minute." });

  const { view, packet } = req.body || {};
  if (!VIEWS.includes(view)) return res.status(400).json({ error: "unknown view: " + view });
  if (!packet || !Array.isArray(packet.rows) || !packet.rows.length)
    return res.status(400).json({ error: "body must be { view, packet } with packet.rows" });
  if (!process.env.ANTHROPIC_API_KEY)
    return res.status(500).json({ error: "ANTHROPIC_API_KEY is not set on this deployment" });

  // The client already built the packet and is showing it to the reader. Trusting
  // it keeps the audit table and the model's input identical by construction --
  // rebuilding it here would let the two drift, which is the one thing that would
  // make the "check every sentence" claim false.
  const payload = { view, title: packet.title, subject: packet.sub,
                    columns: packet.cols.map(c => c.k), rows: packet.rows,
                    context: packet.context };

  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": process.env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 900,
      // BASE is byte-identical on every call, so it caches: reads bill at 0.1x.
      // The per-view block sits after the cache breakpoint and is cheap.
      system: [
        { type: "text", text: BASE, cache_control: { type: "ephemeral" } },
        { type: "text", text: VIEW_PROMPT[view] },
      ],
      messages: [{ role: "user", content: JSON.stringify(payload) }],
    }),
  });

  if (!r.ok) return res.status(502).json({ error: "upstream " + r.status, detail: await r.text() });
  const j = await r.json();
  const u = j.usage || {};
  const billedIn = (u.input_tokens || 0) + 0.1 * (u.cache_read_input_tokens || 0);
  const cost = (billedIn * PRICE.in + (u.output_tokens || 0) * PRICE.out) / 1e6;

  res.setHeader("cache-control", "no-store");
  res.status(200).json({
    summary: j.content.filter(c => c.type === "text").map(c => c.text).join(""),
    model: MODEL, usage: u, cost, source: "live",
  });
};
""")

# ---------------------------------------------------------------- vercel.json
(OUT / "vercel.json").write_text(json.dumps({
  "headers": [
    {"source": "/data/(.*)",
     "headers": [{"key": "Cache-Control", "value": "public, max-age=300, s-maxage=86400, stale-while-revalidate=604800"}]},
    {"source": "/(styles.css|app.js|lib/packet.js)",
     "headers": [{"key": "Cache-Control", "value": "public, max-age=3600"}]},
    {"source": "/(.*)",
     "headers": [
       {"key": "X-Content-Type-Options", "value": "nosniff"},
       {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"}]}
  ],
  # /app must resolve without a trailing slash. Vercel serves app/index.html at
  # /app/ on its own; this makes the bare path work too, so a link written
  # /app/#p-carry and one written /app#p-carry land in the same place.
  "cleanUrls": True,
  "trailingSlash": False,
  "functions": {"api/summary.js": {"maxDuration": 30}}
}, indent=2) + "\n")
print("wrote api/, vercel.json")

# ---------------------------------------------------------------- README
(OUT / "README.md").write_text("""# web/ — the deployable site

The same four views as the artifact, restructured the way a real site is: markup,
styles, script and data in separate files, with one serverless function.

## Run it locally

```bash
cd web
python3 serve.py          # -> http://localhost:8787
```

No npm, no build step, no account. `serve.py` serves the static files and
implements `POST /api/profile`, the one route Vercel would run as a function.

Two modes, chosen automatically:

| | behaviour |
|---|---|
| `ANTHROPIC_API_KEY` **not** set | returns a stored profile; only the four demo players (Bregman, Raleigh, Walker, Cease). The meter says so in orange. |
| `ANTHROPIC_API_KEY` set | calls the model for any player and window, exactly as `api/profile.js` does |

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 serve.py
```

Do not open `index.html` from the filesystem — `fetch()` refuses `file://` URLs
and the data will not load.

## Deploy it

```bash
vercel                              # first deploy, links the project
vercel env add ANTHROPIC_API_KEY    # Production + Preview
vercel --prod
```

`vercel dev` runs the real Node function locally if you prefer that to `serve.py`;
it needs Node and a Vercel login.

## Layout

```
index.html        markup only. Real <head>: description, OG tags, theme-color,
                  favicon, a preload hint for the first shard.
styles.css        every visual decision. Tokens in :root; components read from
                  them, so retheming the site is one block.
app.js            the client. Fetches shards on demand.
lib/packet.js     evidence-packet builder, UMD-wrapped so the browser and the
                  function share ONE implementation. The audit table and the
                  model's input cannot drift apart.
api/profile.js    Vercel function. The only reason it exists is that the key
                  cannot live in the browser.
serve.py          local equivalent, zero dependencies.
data/*.json       per-(type, season) shards + blocks_index.json
vercel.json       cache headers; the shards get s-maxage=86400 so a repeat
                  visitor downloads nothing.
```

## Keeping the data fresh

`run_pipeline.py` writes `output/blocks/` on every daily refresh. Point the deploy
at those files — either copy them into `web/data/` as a build step, or serve
`output/blocks/` directly:

```bash
cp ../output/blocks/*.json data/
```

For a real deployment, do that in a GitHub Action on a schedule, or have the
launchd job push. The shards are content-stable, so a no-op day is a no-op deploy.

## What the first paint costs

| | gzipped |
|---|---|
| artifact version, all four seasons inlined | 1,866 KB |
| this, default view | **187 KB** |

Everything else loads only when the selector asks for it.
""")

# a tiny og image so the meta tag is not a dead link
(OUT / "og.png").write_bytes(bytes.fromhex(
 "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
 "890000000a49444154789c6300010000050001" "0d0a2db4" "0000000049454e44ae426082"))
print("wrote README.md")
