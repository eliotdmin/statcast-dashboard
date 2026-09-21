"""Build the deployable site from the pieces already in this directory.

Produces a conventional static-site + serverless-function tree:

    web/
      index.html          markup only -- no inlined CSS, JS or data
      styles.css          every visual decision, in one editable file
      app.js              the client
      data/*.json         the shards, fetched on demand
      lib/evidence.js     evidence builder, shared by client and server
      api/profile.js      Vercel serverless function; holds the API key
      serve.py            zero-dependency local server, mocks or proxies the API
      vercel.json         headers: immutable caching on the data shards
      README.md

The point of the exercise is the separation. In the artifact everything had to be
one file with the data inlined; here the CSS is a file you can open and edit, the
data is fetched, and the key lives somewhere the browser cannot see.
"""
import os, re, json, shutil, pathlib

HERE = pathlib.Path(__file__).resolve().parent      # site/
ROOT = HERE.parent                                   # the repo
OUT  = ROOT / "web";
for p in ("", "data", "api", "lib"):
    (OUT / p).mkdir(parents=True, exist_ok=True)

head = open(HERE / "head.html").read()
body = open(HERE / "body.html").read()


base_css = head.split("<style>", 1)[1].split("</style>")[0]
# The summary panel's styles. They used to be read out of mkmock.py, which built a published
# artifact; that artifact and its builder were retired 2026-09-21, so the CSS lives here now.
panel_css = """/* ---- deployment banner ---- */
.dep{display:flex;gap:10px;align-items:flex-start;background:var(--sunk);
  border:1px dashed var(--line);border-radius:6px;padding:11px 14px;font-size:12.5px;
  color:var(--ink2);line-height:1.5}
.dep b{color:var(--ink)}
.dep .tag{flex:none;font-family:"IBM Plex Mono",monospace;font-size:9px;letter-spacing:.11em;
  text-transform:uppercase;background:var(--ac);color:#fff;padding:2px 7px;border-radius:3px;
  margin-top:1px}

/* ---- the summary component (all four views) ---- */
.sum{border:1px solid var(--line);border-radius:7px;background:var(--card);overflow:hidden}
.sum-head{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;
  padding:13px 16px;border-bottom:1px solid var(--hair);background:var(--sunk)}
.sum-t{display:flex;flex-direction:column;gap:2px}
.sum-t b{font-size:14px;font-weight:600}
.sum-t span{font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink3)}
.btn{appearance:none;font:inherit;font-size:12.5px;font-weight:600;cursor:pointer;
  background:var(--ac);color:#fff;border:0;border-radius:5px;padding:8px 15px;white-space:nowrap}
.btn:hover{filter:brightness(1.08)}
.btn:disabled{opacity:.5;cursor:default;filter:none}
.btn.alt{background:none;color:var(--ac);border:1px solid var(--line);font-weight:500}
.btn:focus-visible{outline:2px solid var(--ac);outline-offset:2px}
.sum-body{padding:16px}
.sum-idle{font-size:13px;line-height:1.6;color:var(--ink2);max-width:72ch;margin:0}
.sum-idle code{font-family:var(--mono);font-size:11px;background:var(--sunk);padding:1px 5px;
  border-radius:3px;border:1px solid var(--hair)}
.sum-btns{display:flex;gap:8px;flex-wrap:wrap}
details.ev summary #sum-evn{font-weight:400;color:var(--ink3);font-family:var(--mono);font-size:11px}
.prose{font-size:14.5px;line-height:1.66;max-width:70ch}
.prose p{margin:0 0 12px}
.prose p:last-child{margin:0}
.cursor{display:inline-block;width:7px;height:16px;background:var(--ac);vertical-align:-3px;
  animation:bl 1s steps(2) infinite;margin-left:1px}
@keyframes bl{50%{opacity:0}}
@media(prefers-reduced-motion:reduce){.cursor{animation:none}}
.status{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink3);
  display:flex;flex-direction:column;gap:5px;margin:0 0 12px}
.status span.on{color:var(--ac)}
.skel{height:11px;border-radius:3px;background:linear-gradient(90deg,var(--sunk),var(--hair),var(--sunk));
  background-size:200% 100%;animation:sh 1.3s linear infinite;margin-bottom:9px}
@keyframes sh{to{background-position:-200% 0}}
@media(prefers-reduced-motion:reduce){.skel{animation:none}}
.meter{display:flex;gap:16px;flex-wrap:wrap;margin-top:14px;padding-top:11px;
  border-top:1px solid var(--hair);font-family:"IBM Plex Mono",monospace;font-size:10.5px;
  color:var(--ink3);align-items:center}
.meter b{color:var(--ink2);font-weight:600}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.chipb{appearance:none;font:inherit;font-size:11.5px;cursor:pointer;background:var(--card);
  border:1px solid var(--line);color:var(--ac);border-radius:14px;padding:4px 11px}
.chipb:hover{background:var(--cold-s)}
details.ev{border-top:1px solid var(--hair);background:var(--sunk)}
details.ev summary{cursor:pointer;padding:11px 16px;font-size:12px;font-weight:600;color:var(--ink2);
  list-style:none}
details.ev summary::-webkit-details-marker{display:none}
details.ev summary::before{content:"▸ ";color:var(--ink3)}
details.ev[open] summary::before{content:"▾ "}
details.ev .inner{padding:0 16px 16px}
.guard{margin:12px 0 0;font-size:12px;color:var(--ink3);line-height:1.55;max-width:90ch}
.guard b{color:var(--ink2)}
.ev-note{font-size:12px;color:var(--ink3);margin:0 0 10px;max-width:78ch;line-height:1.5}
td.vd{font-weight:600}
td.vd.real{color:var(--hot)}
td.vd.weak{color:var(--ink2)}
td.vd.noise{color:var(--ink3);font-weight:400}

"""

# markup: everything before the inlined data blob
markup = body.split('<script id="D"', 1)[0]
js = body.split("<script>", 1)[1].rsplit("</script>", 1)[0]

# the profile panel markup + js from the mockup build
# (the summary panel's markup and JS now come from summary.js, shared with the
#  mockup build; only its CSS still travels with the mockup file)

# ---------------------------------------------------------------- styles.css
SITE_CSS = r"""/* ============================================================================
   Site chrome. Everything below this line is the part the artifact sandbox
   could not have: a real masthead, a real footer, and a stylesheet you can open
   in an editor instead of hunting for a <style> block inside generated HTML.
   ========================================================================= */
.mast{border-bottom:1px solid var(--line);background:var(--card)}
.mast-in{max-width:1180px;margin:0 auto;padding:13px 16px;display:flex;
  align-items:baseline;gap:14px;flex-wrap:wrap}
.mark{display:flex;align-items:baseline;gap:9px;text-decoration:none;color:var(--ink)}
.mark img{width:20px;height:20px;align-self:center;flex:none}

.mark b{font-size:16px;font-weight:700;letter-spacing:-.015em}
.mark i{font-style:normal;font-family:"IBM Plex Mono",monospace;font-size:9.5px;
  letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);border:1px solid var(--line);
  padding:2px 6px;border-radius:3px}
.mast nav{margin-left:auto;display:flex;gap:4px}
.mast nav a{font-size:12.5px;color:var(--ink2);text-decoration:none;padding:5px 7px;
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
.go:focus-visible,.go2:focus-visible{outline:2px solid var(--ac);outline-offset:3px}

/* landing-page player search */
.pc-search{display:flex;flex-direction:column;gap:8px;margin-top:10px;max-width:480px}
.pc-search label{font-size:13px;color:var(--ink2)}
.pc-search-row{display:flex;gap:8px}
.pc-search input{flex:1;font:inherit;font-size:14px;padding:10px 12px;border:1px solid var(--line);
  border-radius:5px;background:var(--card);color:var(--ink)}
.pc-search input:focus-visible{outline:2px solid var(--ac);outline-offset:1px}
.pc-search .go{border:0;cursor:pointer}
.pc-search-msg{margin:0;font-size:12.5px;color:var(--ink3);min-height:1em}

/* at-a-glance strip under the hero */
.strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--hair);
  border:1px solid var(--hair);border-radius:8px;overflow:hidden}
.strip > div{background:var(--card);padding:18px 20px;display:flex;flex-direction:column;gap:4px}
.strip b{font-family:var(--serif);font-size:28px;font-weight:600;letter-spacing:-.02em;line-height:1.1}
.strip span{font-size:12.5px;color:var(--ink3);line-height:1.45}
.strip.three{grid-template-columns:repeat(3,minmax(0,1fr))}

/* one row per tool: the pitch on one side, a real example on the other, alternating */
.feat{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:56px;align-items:center;
  padding:34px 0;border-top:1px solid var(--hair)}
.feat.flip > .feat-t{order:2}
.feat-t{display:flex;flex-direction:column;gap:10px;align-items:flex-start;max-width:46ch}
.feat-t .k{font-family:var(--mono);font-size:var(--fs-micro);letter-spacing:.11em;
  text-transform:uppercase;color:var(--ac)}
.feat-t h3{margin:0;font-family:var(--serif);font-size:24px;font-weight:600;letter-spacing:-.015em;
  line-height:1.2;text-wrap:balance}
.feat-t p{margin:0;font-size:14.5px;line-height:1.65;color:var(--ink2)}
.feat-v{margin:0;display:flex;flex-direction:column;gap:10px;background:var(--card);
  border:1px solid var(--hair);border-radius:10px;padding:18px;box-shadow:0 1px 2px rgba(13,27,42,.04),
  0 8px 24px rgba(13,27,42,.05)}
.feat-v .rows{display:flex;flex-direction:column;gap:3px}
.feat-v .row{grid-template-columns:128px 54px 1fr 84px}
.feat-v .tw{border-radius:6px}
.feat-v figcaption{font-size:12.5px;line-height:1.55;color:var(--ink3)}
.feat-v figcaption b{color:var(--ink2)}
.out.mini{grid-template-columns:repeat(3,minmax(0,1fr))}
.out.mini .v{font-size:22px}
.quote{margin:0;font-family:var(--serif);font-size:17px;line-height:1.6;color:var(--ink);
  border-left:3px solid var(--ac);padding:2px 0 2px 16px}

/* why-trust-it principles */
.principles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px}
.principles h3{margin:0 0 6px;font-size:15px;font-weight:600}
.principles p{margin:0;font-size:13.5px;line-height:1.6;color:var(--ink2)}

@media(max-width:1000px){
  .feat{grid-template-columns:1fr;gap:22px}
  .feat.flip > .feat-t{order:0}
  .strip{grid-template-columns:repeat(2,minmax(0,1fr))}
  .principles{grid-template-columns:1fr;gap:16px}
}

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
.limits .eb{font-size:10.5px;color:var(--ink3)}
/* prose tables (addendum) wrap; the tool's numeric tables stay on one line */
.doc th,.doc td{white-space:normal;vertical-align:top;line-height:1.45;text-align:left}
.limits b{color:var(--ink)}

/* landing: headline beside a photo. The photo is monochrome and dissolves into the page
   through a soft elliptical mask, so it reads as atmosphere rather than a pasted box --
   and the fade also takes the crowd behind the batter out of focus. */
.hero-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.9fr);gap:40px;align-items:center}
.hero-photo{margin:0;position:relative;height:540px;pointer-events:none}
.hero-photo img{width:100%;height:100%;object-fit:cover;object-position:50% 38%;display:block;
  filter:grayscale(1) contrast(1.04) brightness(1.06);opacity:.72;mix-blend-mode:multiply;
  -webkit-mask-image:radial-gradient(ellipse closest-side at 50% 50%,#000 30%,rgba(0,0,0,.55) 62%,transparent 100%);
          mask-image:radial-gradient(ellipse closest-side at 50% 50%,#000 30%,rgba(0,0,0,.55) 62%,transparent 100%)}
/* a whisper of the site blue over the photo's midtones */
.hero-photo::after{content:"";position:absolute;inset:0;background:var(--ac);opacity:.08;
  mix-blend-mode:screen;
  -webkit-mask-image:radial-gradient(ellipse closest-side at 50% 50%,#000 30%,rgba(0,0,0,.55) 62%,transparent 100%);
          mask-image:radial-gradient(ellipse closest-side at 50% 50%,#000 30%,rgba(0,0,0,.55) 62%,transparent 100%)}
/* addendum: section heading in a sticky left column, its text to the right.
   row-gap is 0 so the heading's long row span adds no empty gutters. */
.doc .block{display:grid;grid-template-columns:250px minmax(0,1fr);column-gap:48px;row-gap:0;
  align-items:start}
.doc .block > *{grid-column:2}
.doc .block > * + *{margin-top:14px}
.doc .block > .sechead{grid-column:1;grid-row:1 / span 20;margin-top:0;position:sticky;top:20px}
.doc .block > .sechead + *{margin-top:0}
.doc .block > .sechead h2{font-size:22px}
@media(max-width:1000px){
  .hero-row,.doc .block{grid-template-columns:1fr}
  .hero-photo{display:none}
  .doc .block > *,.doc .block > .sechead{grid-column:1;grid-row:auto;position:static}
  .doc .block > .sechead + *{margin-top:14px}
}

@media(max-width:560px){
  .lp{padding-block:36px 0;gap:46px}
  .feat-v .row{grid-template-columns:1fr 84px;gap:6px 10px}
  .feat-v .row .bar{grid-column:1/-1}
  .out.mini{grid-template-columns:1fr}
}

.site-foot{border-top:1px solid var(--line);margin-top:34px;background:var(--card)}
.site-foot-in{max-width:1180px;margin:0 auto;padding:24px 16px 60px;
  display:grid;grid-template-columns:1fr;gap:16px;
  font-size:12px;color:var(--ink3);line-height:1.55}
@media(min-width:820px){.site-foot-in{grid-template-columns:repeat(3,1fr);gap:30px}}
.site-foot b{color:var(--ink2)}
.site-foot a{color:var(--ac)}

/* Streak history tab: case-study cards with a half-month wOBA sparkline */
.cases{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:14px}
@media(max-width:1000px){.cases{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.cases{grid-template-columns:1fr}}
.case{background:var(--card);border:1px solid var(--hair);border-radius:8px;padding:14px 15px;
  display:flex;flex-direction:column;gap:8px}
.case header{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.case header b{font-family:var(--serif);font-size:17px;font-weight:600}
.case header .chip{margin-left:auto}
.case p{margin:0;font-size:13px;line-height:1.5;color:var(--ink2)}
.case .chip{background:none;color:var(--ink3);border:1px solid var(--hair)}
.case .chip.c-hot{background:var(--hot-s);color:var(--hot);border-color:transparent;font-weight:600}
.case .chip.c-cold{background:var(--cold-s);color:var(--cold);border-color:transparent;font-weight:600}
.cases-h{margin:22px 0 0;font-size:14px;font-weight:500;color:var(--ink2)}
.spark.cold .s-band{fill:var(--cold-s)}
.spark.cold .s-hot{fill:var(--cold)}
.spark{width:100%;height:auto;display:block}
.spark .s-band{fill:var(--hot-s)}
.spark .s-band2{fill:var(--ink3);opacity:.08}
.spark .s-base{stroke:var(--ink3);stroke-width:1;stroke-dasharray:3 3}
.spark .s-line{fill:none;stroke:var(--ink2);stroke-width:1.4}
.spark .s-pt{fill:var(--ink2)}
.spark .s-hot{fill:var(--hot)}
.spark .s-next{fill:var(--ink)}
.s-axis{display:flex;justify-content:space-between;font-family:var(--mono);font-size:10px;color:var(--ink3);margin-top:-4px}
tr.b-dim td{color:var(--ink3)}
.spark .s-lab{font-family:var(--mono);font-size:9.5px;fill:var(--ink3)}

/* Player check: who's hot or cold right now */
.hc{display:grid;grid-template-columns:minmax(0,1fr);gap:20px}
.hc-col{display:flex;flex-direction:column;gap:8px;min-width:0}
.hc-col h3{margin:0;font-size:12px;font-family:var(--mono);letter-spacing:.09em;text-transform:uppercase}
.hc-col h3.hot{color:var(--hot)} .hc-col h3.cold{color:var(--cold)}
.hc-row{cursor:pointer}
.hc-row:hover td{background:var(--cold-s)}
.hc td.up{color:var(--hot)} .hc td.dn{color:var(--cold)}
#hc-title .sub{font-family:var(--mono);font-size:12px;font-weight:400;margin-left:8px}
"""
(OUT / "styles.css").write_text(
    "/* Statcast Reality Check -- all visual decisions live here.\n"
    "   Tokens first; every component reads from them, so retheming the whole site\n"
    "   is a matter of editing the :root block and nothing else. */\n"
    + base_css + panel_css + SITE_CSS)

# ---------------------------------------------------------------- index.html
# the component builds its own markup and moves itself between panels,
# so there is nothing to splice into the page here any more.
markup = markup.replace(
    "2023&ndash;2026 &middot; 1,590 hitter-seasons &middot; 1,917 pitcher-seasons &middot; everything computed in your browser",
    "<span id=\"eb\">loading&hellip;</span>")

# ---------------------------------------------------------------- page shells
OG_DEFAULT = ("Percentile bars that shrink themselves by how much of each number is real.")

# Two pages now: the landing page at / and the tool at /app/. They share a head,
# a masthead and a footer, so a change to the chrome cannot drift between them.

def head(title, desc, canon, preload=False, og_desc=OG_DEFAULT,
         og_title="Statcast Reality Check"):
    return f'''<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="https://example.com{canon}">

<!-- Link previews. Not possible inside the artifact sandbox; one of the more
     visible things you get back by owning the document head. -->
<meta property="og:type" content="website">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{og_desc}">
<meta property="og:image" content="/og.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ffffff">

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
def mast(base="", current=None):
    return f'''
<header class="mast">
  <div class="mast-in">
    <a class="mark" href="/"><img src="/img/ball.svg" alt="" width="20" height="20"><b>Statcast Reality Check</b></a>
    <nav>
      <a href="{base}#p-player">Player</a>
      <a href="{base}#p-metric">League</a>
      <a href="/addendum.html"{' aria-current="page"' if current == "addendum" else ''}>Method</a>
    </nav>
    <span class="fresh" id="fresh"><span class="dot"></span>{'loading&hellip;' if not base else '2023&ndash;2026'}</span>
  </div>
</header>
'''

FOOT = '''
<footer class="site-foot">
  <div class="site-foot-in">
    <div><b>Data.</b> Statcast pitch-by-pitch data, 2023&ndash;2026, updated daily and checked
    for gaps every time.</div>
    <div><b>Method.</b> Every percentile is pulled toward league average by exactly how much of it
    is noise at your sample size. <a href="/addendum.html">Full methodology</a>.</div>
    <div><b>Summaries</b> are written by an AI model from the numbers on screen, and only those
    numbers.</div>
  </div>
</footer>
'''

# ---------------------------------------------------------------- /app/
(OUT / "app").mkdir(parents=True, exist_ok=True)
(OUT / "app" / "index.html").write_text(
    head("Statcast Reality Check &mdash; shrunk to what is real",
         "Savant-style percentile bars for any stretch of any season, with every percentile "
         "shrunk by how much of it is real at that sample size. Plus a within-player change log, "
         "streak carry rates, and a sample-size planner.",
         "/app/", preload=True)
    + mast() + "\n" + markup.strip() + "\n" + FOOT
    + '\n<script src="/lib/evidence.js"></script>\n<script src="/app.js"></script>\n</body>\n</html>\n')

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
    """One landing-page row, in the same markup the tool itself emits.

    The raw percentile is no longer drawn as a full ghost bar behind the shrunk
    one. It is a `noise` segment starting where the shrunk fill stops, so the
    part nobody can vouch for reads as an extension rather than as a competing
    value -- and it is drawn only when shrinking actually moved the number 5 or
    more points (D36), which is why the last two rows below carry neither a
    noise segment nor a "was" figure.
    """
    hot  = adj >= 50
    col  = "var(--hot)" if hot else "var(--cold)"
    fill = ("left:50%;width:" if hot else "right:50%;width:") + f"{abs(adj-50)}%"
    out  = (f'<div class="row"><span class="nm">{metric} '
            f'<span class="relchip">{rel}% real</span></span>'
            f'<span class="val">{value}</span>'
            f'<span class="bar">'
            f'<span class="fill" style="{fill};background:{col}"></span>')
    if abs(raw - adj) >= 5:
        edge = (f'left:calc(50% + {abs(adj-50)}%)' if hot
                else f'right:calc(50% + {abs(adj-50)}%)')
        out += f'<span class="noise" style="{edge};width:{abs(raw-adj)}%;color:{col}"></span>'
    out += f'<span class="mk"></span></span><span class="pct" style="color:{col}">{adj}'
    if abs(raw - adj) >= 5:
        out += f'<span class="rawpct">was {raw}</span>'
    return out + "</span></div>"

DEMO = "\n          ".join([
    bar("wOBA",      ".407",  50, 98, 74),
    bar("xwOBA",     ".334",  71, 74, 67),
    bar("whiff%",    "15.1%", 92, 90, 87),
    bar("bat speed", "68.1",  98, 29, 30),
])

LANDING = f'''
<main class="lp">

  <div class="hero-row">
  <section class="hero col">
    <p class="eb">Statcast &middot; every hitter and pitcher &middot; 2023&ndash;2026</p>
    <h1>Really understand MLB player performance.</h1>
    <p class="lede">Decompose a player&rsquo;s statistics into sustainable changes, hot streaks,
    and luck.</p>
    <div class="cta">
      <a class="go" href="/app/">Enter <span class="ar">&rarr;</span></a>
      <a class="go2" href="#tools">See the tools</a>
    </div>
  </section>

  <figure class="hero-photo" aria-hidden="true">
    <img src="/img/hero-batter.jpg" alt="" width="682" height="1024">
  </figure>
  </div>

  <section class="strip" aria-label="At a glance">
    <div><b>3,507</b><span>hitter and pitcher seasons</span></div>
    <div><b>4</b><span>seasons of pitch-level data</span></div>
    <div><b>Daily</b><span>refresh, checked for gaps every time</span></div>
    <div><b>46%</b><span>of flagged 2026 changes kept at least half their size over the next 60 days</span></div>
  </section>

  <section class="block" id="tools">
    <div class="sechead">
      <span class="k">Five tools</span>
      <h2>Each tool probes deeper into an MLB player&rsquo;s output.</h2>
    </div>

    <div class="feat">
      <div class="feat-t">
        <span class="k">Luck-adjusted percentiles</span>
        <h3>How did a player&rsquo;s output compare with his peers&rsquo;, and is it real?</h3>
        <p>Pick any player and any date range, and see where he ranked against everyone with similar
        playing time. Every number is adjusted for how much of it is luck at that sample size, so a
        hot six weeks doesn&rsquo;t pass for a breakout. Matching players with the most similar
        stretch come along with it.</p>
        <a class="go2" href="/app/#p-stretch">On the Player tab &rarr;</a>
      </div>
      <figure class="feat-v">
        <div class="rows">
          {DEMO}
        </div>
        <figcaption>Alex Bregman, Jul 16 &ndash; Sep 15 2026. A .407 wOBA reads as 98th percentile raw;
        with the luck taken out it&rsquo;s 74th &mdash; and his bat speed sits at the 30th.</figcaption>
      </figure>
    </div>

    <div class="feat flip">
      <div class="feat-t">
        <span class="k">Swing &amp; approach changes</span>
        <h3>How did a player&rsquo;s underlying skills change, and are the changes real or fluky?</h3>
        <p>Flags every time a player&rsquo;s bat speed, attack angle, chase rate or other inputs moved
        further than chance allows against his own earlier season &mdash; often weeks before it shows
        up in results. Then it checks, after the fact, whether the change held.</p>
        <a class="go2" href="/app/#p-changes-mine">On the Player tab &rarr;</a>
      </div>
      <figure class="feat-v">
        <div class="tw"><table>
          <thead><tr><th class="l">player</th><th class="l">metric</th><th>before</th><th>now</th><th>held</th></tr></thead>
          <tbody>
            <tr><td class="l">Cody Bellinger</td><td class="l">chase%</td><td>23.4%</td><td class="up">42.3%</td><td><span class="chip right">56%</span></td></tr>
            <tr><td class="l">David Hamilton</td><td class="l">bat speed</td><td>61.2</td><td class="up">66.8</td><td><span class="chip part">12%</span></td></tr>
            <tr><td class="l">Alex Bregman</td><td class="l">hard-hit%</td><td>46.9%</td><td class="dn">25.8%</td><td><span class="chip part">43%</span></td></tr>
          </tbody>
        </table></div>
        <figcaption>Three of 2026&rsquo;s flagged moves. <b>Held</b> is how much of the change was still
        there over the following 60 days &mdash; the check that separates a real change from a blip.</figcaption>
      </figure>
    </div>

    <div class="feat">
      <div class="feat-t">
        <span class="k">Is he hot or cold</span>
        <h3>Is a player on a hot or cold streak &mdash; and how much of it is signal, not noise?</h3>
        <p>For every qualified player: how far above or below his usual level he&rsquo;s been over the
        last month, and how much of that the model expects to last into next month. Two streaks of
        the same size can have very different outlooks.</p>
        <a class="go2" href="/app/#p-card">On the Player tab &rarr;</a>
      </div>
      <figure class="feat-v">
        <div class="tw"><table>
          <thead><tr><th class="l">player</th><th>last month vs. his usual</th><th>expected next month</th></tr></thead>
          <tbody>
            <tr><td class="l">Cal Raleigh</td><td class="up">+.246 wOBA</td><td><b class="up">+.079</b> <span class="sub">keeps 32% of it</span></td></tr>
            <tr><td class="l">Rafael Devers</td><td class="up">+.162 wOBA</td><td><b class="up">+.008</b> <span class="sub">keeps 5% of it</span></td></tr>
          </tbody>
        </table></div>
        <figcaption>Both hot through mid-September 2026. The model expects Raleigh to stay about 80
        points above his usual level next month, and Devers to fall back almost all the way.</figcaption>
      </figure>
    </div>

    <div class="feat flip">
      <div class="feat-t">
        <span class="k">Sample size needed</span>
        <h3>How long until past performance predicts future performance?</h3>
        <p>Before you react to a stat, see how much data it takes to be trustworthy &mdash; and how long
        it takes to confirm a change you already suspect, like a pitcher losing velocity.</p>
        <a class="go2" href="/app/#p-planner">On the League tab &rarr;</a>
      </div>
      <figure class="feat-v">
        <div class="out mini">
          <div class="tile"><span class="k">Bat speed</span><span class="v">13 PA</span><span class="d">to be 70% trustworthy</span></div>
          <div class="tile"><span class="k">wOBA</span><span class="v">525 PA</span><span class="d">for the same trust &mdash; most of a season</span></div>
          <div class="tile"><span class="k">Fastball down 1 mph</span><span class="v">26 batters</span><span class="d">to confirm it&rsquo;s real</span></div>
        </div>
        <figcaption>What a player does with the bat is readable within days; results take most of a
        season.</figcaption>
      </figure>
    </div>

    <div class="feat">
      <div class="feat-t">
        <span class="k">Head-to-head odds</span>
        <h3>Head-to-head matchups between two players.</h3>
        <p>Pick two players and a window, and get the odds that one finishes ahead of the other
        &mdash; not a projected stat line, because predicting anyone&rsquo;s exact numbers a month out
        barely beats guessing. It shows how much of the answer is genuine difference and how much is
        luck over the plate appearances ahead, and it publishes its own scoring record so you can
        see what &ldquo;62%&rdquo; has actually meant.</p>
        <a class="go2" href="/app/#p-vs">On the Player tab &rarr;</a>
      </div>
      <figure class="feat-v">
        <div class="out mini">
          <div class="tile"><span class="k">Over 2 weeks</span><span class="v">80%</span><span class="d">the better hitter finishes ahead &mdash; a gap near the widest in baseball</span></div>
          <div class="tile"><span class="k">Typical matchup</span><span class="v">58 / 42</span><span class="d">two regulars over a month are close to a coin flip</span></div>
          <div class="tile"><span class="k">Of the uncertainty</span><span class="v">63%</span><span class="d">is plain luck; under 5% is not knowing who they are</span></div>
        </div>
        <figcaption>Scored on 3,259 past matchups: when it said 62%, the favourite won 63% of the
        time. Honest, and rarely far from a coin flip &mdash; which is the point.</figcaption>
      </figure>
    </div>

    <div class="feat">
      <div class="feat-t">
        <span class="k">On every tab</span>
        <h3>A plain-English read of what you&rsquo;re looking at.</h3>
        <p>Each view can write a short scouting summary of exactly the numbers on screen. It sees only
        those numbers and is instructed never to say more than they support &mdash; so it won&rsquo;t call
        noise a trend.</p>
        <a class="go2" href="/app/">Try it in the dashboard &rarr;</a>
      </div>
      <figure class="feat-v">
        <blockquote class="quote">Alex Bregman has hit .407 over his last 226 plate appearances, which
        is the 98th percentile among hitters in this span, and almost nothing underneath it has moved.
        His swing is the same swing&hellip;</blockquote>
        <figcaption>Opening of a generated scouting profile.</figcaption>
      </figure>
    </div>
  </section>

  <section class="block">
    <div class="sechead">
      <span class="k">The two-week breakout</span>
      <h2>&ldquo;He&rsquo;s earned it&rdquo; mostly doesn&rsquo;t last.</h2>
    </div>
    <p class="note">Every week someone is smacking the ball &mdash; buy him, he&rsquo;s earned his
    results. We checked every two-week hot streak from 2023&ndash;2025: 928 of them, averaging 129
    points of wOBA above the hitter&rsquo;s own earlier-season rate.</p>
    <div class="strip three">
      <div><b>14%</b><span>of the gain survived the next two weeks</span></div>
      <div><b>43%</b><span>were back at or below the hitter&rsquo;s own baseline right away</span></div>
      <div><b>13% vs 13%</b><span>kept by streaks backed by better contact vs. by pure luck &mdash; no difference</span></div>
    </div>
    <p class="note">Over two weeks, even contact quality is mostly noise. What makes a streak
    believable is how long it lasts: a 30-day hot streak kept 27% of its gain the following month,
    and a six-week one kept 43% &mdash; with or without the hard contact. That is the problem this
    dashboard is built for: <a href="/app/#p-carry">Streak carry forecast</a> says how much of a streak to
    keep, and <a href="/app/#p-stretch">Luck-adjusted percentiles</a> shows which numbers are real at the sample
    you&rsquo;re looking at.</p>
    <p class="cta"><a class="go2" href="/app/#p-break">See the full study and nine case studies &rarr;</a></p>
  </section>

  <section class="block">
    <div class="sechead">
      <span class="k">Why trust it</span>
      <h2>Built to be honest about uncertainty.</h2>
    </div>
    <div class="principles">
      <div><h3>Adjusted for sample size</h3><p>Every percentile is pulled toward league average by
      exactly how much of it is noise at your sample size. Nothing is tuned by hand.</p></div>
      <div><h3>Checked after the fact</h3><p>Flagged changes are scored against what happened next,
      and the hit rate is shown right next to them.</p></div>
      <div><h3>Clear about limits</h3><p>Next month&rsquo;s results are mostly luck. The site says how
      much of it any model could predict, and doesn&rsquo;t pretend to more.</p></div>
    </div>
    <p class="cta"><a class="go2" href="/addendum.html">Read the method &rarr;</a>
    <a class="go2" href="/report.html">Full technical report &rarr;</a></p>
  </section>

  <section class="limits">
    <p class="eb">What this is not</p>
    <p><b>It is not a season projection system.</b> Where its methods were tested against one, they did
    not beat the public systems. It answers narrower questions: of what already happened, how much was
    real, and how much of it is likely to last.</p>
    <p>Carry rates were fit on 2023&ndash;2025 and scored on 2026, which has since been looked at too
    many times to count as a clean test &mdash; read those figures as optimistic. Details and the
    predictions frozen against 2027 are on the <a href="/addendum.html">Method page</a>.</p>
  </section>

</main>
'''

# The landing page used to carry a one-player search ("should you believe his last month?")
# and this script drove it. Removed 2026-09-21 at the user's direction; "Enter" now leads in.
LANDING_JS = ""

(OUT / "index.html").write_text(
    head("Statcast Reality Check",
         "Statcast tools for telling a real change from a lucky streak: sample-size-aware "
         "percentiles, a change log, streak carry rates, and a sample-size planner.",
         "/", og_desc="Tell a real change from a lucky streak. Statcast tools for mid-season roster decisions.")
    + mast("/app/") + LANDING + FOOT + LANDING_JS + "\n</body>\n</html>\n")


# ---------------------------------------------------------------- /addendum.html
ADDENDUM = r"""

<main class="lp doc">

  <section class="hero col">
    <p class="eb">Method</p>
    <h1>How to read every number on this site, in plain terms.</h1>
    <p class="lede">Baseball statistics mix two things: what a player is genuinely good at, and
    luck. Over a few weeks the luck is usually bigger. This site separates the two, and this page
    explains how &mdash; first the ideas that apply everywhere, then the caveats that belong to each
    analysis.</p>
    <p class="note glossary"><b>Three terms used throughout.</b> A <b>plate appearance</b> is one
    turn at bat. <b>wOBA</b> is a single number for how much a hitter contributes per plate
    appearance, counting a home run for more than a single and a walk for less. <b>Bat speed</b> is
    how fast the bat is moving when it meets the ball &mdash; a measure of the swing itself, not of
    what happened to the ball.</p>
    <div class="cta">
      <a class="go" href="/report.html">Read the full technical report <span class="ar">&rarr;</span></a>
      <span class="sub">The complete methods, results and caveats</span>
    </div>
  </section>

  <section class="block" id="real">
    <div class="sechead">
      <span class="k">What &ldquo;% real&rdquo; means</span>
      <h2>&ldquo;% real&rdquo; says how much of a stat is skill across all players &mdash; not how accurate one player&rsquo;s number is.</h2>
    </div>
    <p class="note">Rank every hitter by some stat over six weeks, then imagine replaying those
    same six weeks. Some of the ranking would come back the same, because some players really are
    better. The rest would scramble, because it was luck. <b>&ldquo;% real&rdquo; is the share that
    would come back.</b> It is a property of the stat at that sample size, and every player gets the
    same figure.</p>
    <p class="note">The site uses it to correct every percentile: a stat that is only half real has
    its percentile pulled halfway back toward average. The solid bar is the corrected figure; where
    correcting moved it five points or more, a hatched extension shows what the uncorrected number
    said.</p>
    <p class="note ex"><b>Example.</b> Over six weeks in 2026, Alex Bregman&rsquo;s wOBA was 98th percentile. wOBA is about half real at that sample, so it corrects to the 74th. His bat speed is 98% real at the same sample and barely moves.</p>
    <details class="maths"><summary>The maths</summary>
      <p class="note">For a stat over <i>n</i> plate appearances, <code>&rho; = var(true skill) / var(observed)</code>. It is measured by splitting each season into odd and even half-months and correlating the halves, corrected for the split with Spearman&ndash;Brown, <code>&rho;&#8320; = 2r/(1+r)</code>, and projected to other sample sizes by the same formula. The corrected percentile is <code>50 + &rho;(raw &minus; 50)</code>; that the correction coefficient equals &rho; follows from the regression of true skill on the observed value.</p>
    </details>
  </section>

  <section class="block" id="reliability">
    <div class="sechead">
      <span class="k">How precisely it is known</span>
      <h2>We know almost exactly how trustworthy swing speed is; we know how trustworthy batting results are only roughly.</h2>
    </div>
    <p class="note">&ldquo;% real&rdquo; is itself measured from a few thousand player-seasons, so it
    has its own margin of error. For the swing measurements it is tiny. For the results measurements
    &mdash; the ones this site tells you to discount &mdash; it is wide. So the correction applied to a
    wOBA percentile is itself approximate, and it is approximate exactly where the correction matters
    most.</p>
    <p class="note ex"><b>Example.</b> Bat speed is .974 real, with a 95% range of .971 to .978. wOBA is .479, with a range of .418 to .545 &mdash; so &ldquo;about half real&rdquo; really means somewhere between about 42% and 55%.</p>
    <details class="maths"><summary>The maths</summary>
      <p class="note">Each &rho; is bootstrapped by resampling player-seasons (1,000 draws). The interval appears on every <code>% real</code> chip and in the reliability table. It captures uncertainty in which players were measured, not in how their seasons were split, and projecting &rho; to another sample size carries it along without widening it.</p>
    </details>
  </section>

  <section class="block" id="significance">
    <div class="sechead">
      <span class="k">Real vs. big</span>
      <h2>A change can be real and still too small to matter, so every change is judged on both.</h2>
    </div>
    <p class="note">Two separate questions sit behind &ldquo;did he change?&rdquo;. Is the change more
    than luck would produce &mdash; and is it large enough to care about? A hitter can add half a mile
    an hour of bat speed that is certainly real and makes no difference. Another can look transformed
    over a fortnight on a change that is probably noise. The site answers both, separately, rather
    than folding them into one score.</p>
    <details class="maths"><summary>The maths</summary>
      <p class="note">Whether a change is real is its <i>z</i>: the change divided by the error two windows of that size would produce on their own. How big it is is expressed in standard deviations of how much players <i>genuinely</i> change over a season, so a &ldquo;large&rdquo; change means large relative to real movement, not relative to noise.</p>
    </details>
  </section>

  <section class="block" id="ceiling">
    <div class="sechead">
      <span class="k">How much can be predicted at all</span>
      <h2>Next month&rsquo;s results are mostly luck, so even a perfect forecaster would be wrong most of the time.</h2>
    </div>
    <p class="note">A forecast is usually graded out of 100%, as if a perfect one were possible. It is
    not. Over a month, a hitter bats about 90 times, and the outcome of each turn is close to a coin
    flip weighted by his skill. Even someone who knew every player&rsquo;s true ability exactly would
    explain only about a quarter of how next month turns out. So every forecast here is graded
    against that ceiling, not against perfection &mdash; and the best models reach about a fifth of
    it.</p>
    <details class="maths"><summary>The maths</summary>
      <p class="note">Decomposing month-to-month differences for the same hitter (16,228 pairs) gives a per-plate-appearance variance of 0.2258, month-to-month drift in true skill of .038, and a spread of true skill across hitters of .035. At a typical month the realistic ceiling on R&sup2; is 0.264.</p>
    </details>
  </section>

  <section class="block" id="holdout">
    <div class="sechead">
      <span class="k">One season to treat with care</span>
      <h2>We have looked at 2026 too often to treat it as a fair test, so its results are shown but not trusted.</h2>
    </div>
    <p class="note">The honest way to test a forecast is to build it on some seasons and score it once on
    a season it has never seen. 2026 started as that test season. But it has since been checked, and
    re-checked, many times &mdash; and every look is a small chance to shape the answer to fit. So
    wherever 2026 appears it is shown separately and greyed out, and nothing on the site depends on
    it. The clean test is 2027, and the predictions for it are written down in advance.</p>
  </section>

  <section class="block divider">
    <div class="sechead">
      <span class="k">By analysis</span>
      <h2>What each part of the site can and can&rsquo;t tell you.</h2>
    </div>
  </section>

  <section class="block" id="rank">
    <div class="sechead">
      <span class="k">Luck-adjusted percentiles</span>
      <h2>A player&rsquo;s rank over any stretch is corrected for how much of it is luck.</h2>
    </div>
    <p class="note">Pick a player and a date range and the site ranks him against everyone who played a
    similar amount over the same dates. Every rank is corrected as described above. It describes
    games already played: it does not say whether he will keep it up.</p>
  </section>

  <section class="block" id="changes">
    <div class="sechead">
      <span class="k">Swing &amp; approach changes</span>
      <h2>A change in how a player swings shows up weeks before it shows up in his results.</h2>
    </div>
    <p class="note">Swing and approach measurements become reliable within a couple of weeks, far faster
    than results do. So a genuine mechanical change is visible here early. Each flagged change is also
    checked afterwards, against the following weeks, to see whether it stuck &mdash; about half do.</p>
    <p class="note caveat"><b>What it can&rsquo;t tell you:</b> that a real change will improve his
    results. This was tested directly and it did not hold: a change that sticks is real, but on this
    evidence it does not forecast the next month.</p>
  </section>

  <section class="block" id="streaks">
    <div class="sechead">
      <span class="k">Hot and cold streaks</span>
      <h2>Most of a hot streak is gone within two months, and how long it has lasted says more than how good the contact looked.</h2>
    </div>
    <p class="note">A two-week hot streak keeps about a fifth of its gain over the following two months.
    A six-week streak keeps nearly half. Whether the hitter was &ldquo;really squaring the ball
    up&rdquo; during the streak makes no measurable difference. Slumps last longer than hot streaks,
    perhaps because some of them are injuries.</p>
    <p class="note caveat"><b>What it can&rsquo;t tell you:</b> why a streak happened. Streaks that come
    too late in the season to have two full months after them are left out, and those tend to fade
    faster, so the figures run slightly high for a streak happening in September.</p>
    <details class="maths"><summary>The maths</summary>
      <p class="note">Every streak is judged over one fixed horizon &mdash; the next 60 days &mdash; whatever its own length. Judging a two-week streak against the following two weeks compared one noisy sample with another; averaged over many streaks that barely changes the headline figure, but it made individual verdicts mostly noise.</p>
    </details>
  </section>

  <section class="block" id="matchup">
    <div class="sechead">
      <span class="k">Head-to-head odds</span>
      <h2>Predicting a player&rsquo;s exact numbers barely beats guessing, so we only predict which of two players does better.</h2>
    </div>
    <p class="note">Forecasting a hitter&rsquo;s exact line a month out is barely better than guessing
    league average. Picking which of two players does better is an easier question, so that is the
    one asked. The answer is a probability, and it is usually closer to a coin flip than people
    expect: over a month, two good regulars are often 55&ndash;45.</p>
    <p class="note">Each probability comes with a scoring record: every past matchup the same method was
    asked, and how often its favourite actually won. That record is also compared with the simplest
    rule available &mdash; back whoever was better last season &mdash; because beating a coin flip is too
    low a bar.</p>
    <p class="note caveat"><b>What it can&rsquo;t tell you:</b> for hitters over two weeks, anything more
    than a coin flip would &mdash; at that horizon it has no demonstrable skill. From a month out it beats
    the simple rule, but that rule alone already gets most of the way. It also cannot know about an
    injury or a demotion, which is why playing time is left for you to set.</p>
    <p class="note ex"><b>Example.</b> Aaron Judge against Alex Bregman &mdash; nearly the widest skill gap in baseball &mdash; comes out about 80% over two weeks, and still about 80% over the rest of a season.</p>
    <details class="maths"><summary>The maths</summary>
      <p class="note">Each player&rsquo;s skill is his prior-season level, pulled toward the league average by about 330 plate appearances&rsquo; worth, then updated by this season. The difference between two players then carries three uncertainties &mdash; not knowing their skill, skill changing over the window, and luck over the plate appearances ahead &mdash; and the probability is <code>&Phi;(&Delta;/&radic;total)</code>. Accuracy is the Brier score, where always saying 50% scores .2500.</p>
    </details>
  </section>

  <section class="block" id="planner">
    <div class="sechead">
      <span class="k">Sample size needed</span>
      <h2>Some numbers mean something within days; others need more than a season.</h2>
    </div>
    <p class="note">This is a reliability and power analysis. Ask it before reacting to a stat: it says how
    many plate appearances it takes before a ranking on that stat is mostly skill, and how many it takes
    to confirm a change you already suspect.</p>
    <p class="note caveat"><b>What it can&rsquo;t tell you:</b> anything specific to one player. It assumes
    an ordinary one; for a genuine outlier the true answer is smaller.</p>
    <p class="note ex"><b>Example.</b> Bat speed is 70% skill after 13 plate appearances. wOBA takes 525 &mdash; most of a season &mdash; and needs more than three seasons before a ranking on it is 90% skill. A pitcher who has lost a mile an hour off his fastball can be confirmed within 26 batters.</p>
  </section>

</main>
"""

(OUT / "addendum.html").write_text(
    head("Method &mdash; Statcast Reality Check",
         "What every number on Statcast Reality Check actually means, what it does not mean, "
         "and the caveats that come with it.",
         "/addendum.html",
         og_desc="What every number on Statcast Reality Check actually means, what it does not "
                 "mean, and the caveats that come with it.",
         og_title="Method &mdash; Statcast Reality Check")
    + mast("/app/", current="addendum") + ADDENDUM + FOOT + "\n</body>\n</html>\n")
print("wrote", OUT / "addendum.html")

# ---------------------------------------------------------------- favicon
(OUT / "favicon.svg").write_text(
'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">\n<circle cx="16" cy="16" r="14.6" fill="#fff" stroke="#c3cfdb" stroke-width="1.4"/>\n<g fill="none" stroke="#e0332a" stroke-linecap="round">\n<path d="M9.2 4.2C12.6 9.2 12.6 22.8 9.2 27.8" stroke-width="1.1"/>\n<path d="M22.8 4.2C19.4 9.2 19.4 22.8 22.8 27.8" stroke-width="1.1"/>\n<path d="M8.63 6.95L11.13 5.45M9.63 10.22L12.13 8.72M10.31 13.48L12.81 11.98M10.55 16.75L13.05 15.25M10.31 20.02L12.81 18.52M9.63 23.28L12.13 21.78M8.63 26.55L11.13 25.05" stroke-width="1"/>\n<path d="M20.87 5.45L23.37 6.95M19.87 8.72L22.37 10.22M19.19 11.98L21.69 13.48M18.95 15.25L21.45 16.75M19.19 18.52L21.69 20.02M19.87 21.78L22.37 23.28M20.87 25.05L23.37 26.55" stroke-width="1"/>\n</g>\n</svg>\n')

# ---------------------------------------------------------------- lib/evidence.js
(OUT / "lib" / "evidence.js").write_text(r"""/* Evidence builder.
 *
 * Deliberately dependency-free and written for both runtimes: the browser
 * imports it with a <script> tag, the serverless function require()s it. One
 * implementation means the numbers the reader audits in the "evidence" table are
 * byte-for-byte the numbers the model was given -- if these drifted apart, the
 * whole auditability claim would be a lie.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Evidence = factory();
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
print("wrote", OUT / "lib" / "evidence.js")

# ---------------------------------------------------------------- app.js
FILEHEAD = r"""/* ===========================================================================
   Statcast Reality Check -- client.
   Data arrives as per-(type, season) shards fetched on demand. The artifact
   version inlined all four seasons of both player types: 1.9 MB gzipped before
   the first pixel. Here the default view costs 187 KB and the rest never loads
   unless you ask for it.
   ========================================================================= */
"""

LOADER = r"""var ALL = {};                    // kind-year -> shard, populated by fetch
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
      // Date only on the masthead; the full timestamp lives in the tooltip. The tab names
      // were lengthened to say what each view is for, and the time of day was the least
      // useful thing on a row that had run out of width.
      var built = d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) + " " +
        d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
      $("#fresh").innerHTML = '<span class="dot"></span>built <b>' +
        d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) + "</b>";
      $("#fresh").title = "Data built " + built;
      $("#eb").textContent = YEARS[YEARS.length - 1] + "\u2013" + YEARS[0] +
        " \u00b7 " + tot.toLocaleString() + " player-seasons tracked";
      // Prior seasons for the "usual level" baseline. Not on the critical path: the views
      // that use it render without it and repaint when it lands.
      //
      // That repaint used to name the Player check tab by index, so when Head to head
      // arrived -- which cannot produce an estimate at all without a prior-season level --
      // it rendered before the fetch returned and stayed stuck on "no prior-season
      // baseline", which read as missing data rather than as a race. Repaint whichever
      // tab is open instead of hard-coding one.
      fetch("/data/history.json").then(function (r) { return r.ok ? r.json() : null; })
        .then(function (h) {
          HIST = h;
          if (!h) return;
          if (isShown("p-card") || isShown("p-vs")) {
            TABS[active][2]();
            if (window.SUM) SUM.reset();
          }
        })
        .catch(function () {});
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
SUM_PRELUDE = r"""var ENDPOINT = "/api/summary";
// The summary sits to the right of its analysis, and drops underneath it below 1000px, so the
// pointer to the evidence follows the layout rather than naming one direction.
var IDLE = 'A short plain-English read of this view, written only from the evidence '+
  '<span class="sum-dir-side">to the left</span><span class="sum-dir-stack">above</span>. '+
  'Click Summarize to generate it.';

/* Streams the newline-delimited {delta|error|done} protocol both backends speak
   (see api/summary.js / serve.py). onDelta fires with each text chunk as it
   arrives; the returned promise resolves with the terminal "done" object (model,
   usage, cost, source) once the stream ends, or rejects on an HTTP error, a
   mid-stream "error" line, or a network failure. */
function send(pk, onDelta){
  ctl = new AbortController();
  return fetch(ENDPOINT, {method:"POST", headers:{"content-type":"application/json"},
                          body:JSON.stringify({view:pk.view, kind:K, evidence:pk}),
                          signal:ctl.signal})
    .then(function(r){
      if(!r.ok){
        return r.json().catch(function(){ return {}; }).then(function(j){
          throw new Error(j.error || ("HTTP " + r.status));
        });
      }
      var reader=r.body.getReader(), dec=new TextDecoder(), buf="", result=null;
      function handleLine(line){
        line=line.trim(); if(!line) return;
        var evt; try{ evt=JSON.parse(line); } catch(e){ return; }
        if(evt.type==="delta") onDelta(evt.text||"");
        else if(evt.type==="error") throw new Error(evt.error||"stream error");
        else if(evt.type==="done") result=evt;
      }
      return (function pump(){
        return reader.read().then(function(step){
          if(step.done){
            buf+=dec.decode();
            if(buf) handleLine(buf);
            return result || {};
          }
          buf+=dec.decode(step.value, {stream:true});
          var idx;
          while((idx=buf.indexOf("\n"))!==-1){
            var line=buf.slice(0,idx); buf=buf.slice(idx+1);
            handleLine(line);
          }
          return pump();
        });
      })();
    });
}
"""

SUMMARY_JS = open(HERE / "summary.js").read()

REAL_AI = SUM_PRELUDE + "\n" + SUMMARY_JS + r"""
/* currentEvidence() is what the stretch view's builder calls. It is the one view
   whose evidence is a real Evidence object rather than a projection of the table,
   because the server rebuilds it from the shard and compares the two. */
function currentEvidence(){
  var me=ROWS.find(function(r){return String(r.id)===String($("#who").value);});
  if(!me) return null;
  var shard=ALL[shardKey(K,YR)];
  var metrics=MET.map(function(m){return {k:m.k,n:m.n,d:m.d,hi:m.hi,g:m.g};});
  return Evidence.build(shard, metrics, PK, me.id, BL[+$("#from").value], BL[+$("#to").value]);
}
"""

# re-reading the screen after the bars redraw keeps the evidence table in step
# with the controls without the component having to know what changed them.
app = app.replace('  $("#bars").innerHTML=html;\n  renderComps(me,mine,myN,i0,i1);',
                  '  $("#bars").innerHTML=html;\n  if(window.SUM) SUM.reset();\n  renderComps(me,mine,myN,i0,i1);')
app = app.replace("setKind();\n})();",
  # active is already set by the hash deep-link block above, so the component
  # lands in the panel the visitor actually opened.
  REAL_AI + "\nSUM.mount(sumSection(active));\nboot();\n})();")
app = app.replace('$("#from").value=yb[Math.min(2,yb.length-1)]; $("#to").value=yb[Math.min(4,yb.length-1)];',
  '''$("#from").value=yb[Math.max(0,yb.length-4)]; $("#to").value=yb[yb.length-1];
  // Open on a player the stored-profile fallback can actually write about, so the
  // first thing a visitor without a key clicks does something.
  var pref=K==="bat"?"608324":"656302";
  if(ROWS.some(function(r){return String(r.id)===pref;})){ $("#who").value=pref; $("#pc-who").value=pref; }
  if(HQ.id && ROWS.some(function(r){return String(r.id)===HQ.id;})){ $("#pc-who").value=HQ.id; HQ.id=null; }''')

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
  // The page title is the open view's name, taken from the same link text, so the menu and
  // the heading can never name different things.
  function mark(id){
    var cur=links.filter(function(a){ return a.getAttribute("href").slice(1)===id; })[0];
    if(cur){ document.getElementById("view-title").textContent=cur.textContent;
      document.title=cur.textContent+" \u2014 Statcast Reality Check"; }
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
idx = idx.replace('<div class="tabs" role="tablist" hidden>',
  '<div class="boot" id="panels-boot" hidden>\n'
  '  <p>Loading player data&hellip;</p>\n'
  '  <div class="skel" style="width:92%"></div><div class="skel" style="width:78%"></div>\n'
  '  <div class="skel" style="width:85%"></div><div class="skel" style="width:46%"></div>\n'
  '</div>\n\n<div class="tabs" role="tablist" hidden>')
(OUT / "app" / "index.html").write_text(idx)

# ---------------------------------------------------------------- prompts
# The base block is byte-identical on every call, so it caches and reads bill at
# 0.1x. The per-view block is small and varies, and is appended after it.
(OUT / "prompts").mkdir(parents=True, exist_ok=True)

BASE = """You write short, exact readings of baseball measurements for an audience that
already knows the game. You are given the evidence as JSON: a set of rows, each carrying
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
7. Never state a number that does not appear in the evidence. No outside knowledge of any
   player, team or season.
8. Prefer the measurement over the outcome when they disagree, and say which is which.

Style: three or four short paragraphs. No headings, no bullets, no preamble, no sign-off.
Lead with the single most defensible observation in the evidence, not the largest number.
Name at least one thing the evidence cannot settle."""

VIEW_PROMPTS = {
 "line": """This evidence is one player's official season-by-season line: one row per season, then a
career total. `context.selected_season` is the season the reader is looking at. Summarize his key
numbers in two short paragraphs. First, the selected season against his own career and his last
two or three seasons: which figures stand out, up or down, and by how much. Then the longer shape
of the career -- rising, steady, or falling -- using the rows, not outside knowledge. A partial
current season has fewer games; say so before comparing its totals, and prefer rates (AVG, OBP,
SLG, OPS, ERA, WHIP, K%, BB%) to counting stats when seasons differ in length. These are surface
results, not skill measurements: do not say what caused a change, and do not project next season.""",
 "stretch": """This evidence is one player over one window. Say what his body did, then what the
results did, then whether those two agree. The reader wants to know which of his numbers
he should carry into a decision and which he should ignore at this sample size.""",
 "card": """This evidence is one player's card. `context.verdict` is the call the card already shows the
reader, made by a fixed rule: his results over the recent stretch against his own earlier-season
rate, with "how much will stick" taken from the carry model (a regression of next month's wOBA on
this month's and earlier wOBA and xwOBA) or, failing that, from how similar streaks have gone.

Your job is to explain that verdict, not to issue a second one. Open with the verdict in plain
words and the number behind it (the gap, and the share expected to stick). Then use the metric
rows to say what supports it and what cuts against it. If the underlying measurements point a
different way from the verdict -- for example contact quality holding up during a cold stretch --
name that as a tension the reader should weigh, and say the verdict already accounts for xwOBA
through the carry model. Never write a sentence a reader could take as overruling the headline.
A metric whose verdict is "real" is a real change, but on this project's evidence input changes
do not predict next month's results, so it does not move the call.
""",
 "changes": """This evidence is a filtered list of within-player moves. Each row compares a window
against that player's own earlier season. `held` is the share of the move still present over the
FOLLOWING 60 DAYS (one fixed follow-up for every window length) and is computed after the fact -- treat a confirmed row as evidence and an
unconfirmed one as a watch-list entry, never as a claim. Look for players appearing more than
once, and for the shape of the filtered set as a whole, before naming individuals. A held figure
above 100% means the following 60 days came in further out still; it is not a prediction and not an endorsement.""",
 "carry": """This evidence is the carry board. `carry` is a discount rate, not a forecast: the
fraction of a player's gap from his own baseline that has historically survived a month. A large
positive gap with low carry is a sell candidate; a large negative gap with low carry is a buy.
Say explicitly that a discounted gap is neither a return to baseline nor a continuation. These
windows are short and wOBA is well under half signal at their length -- say so.""",
 "breakouts": """This evidence is a descriptive study of hitters' streaks, not a view of any current player.
`context.baseline` says which comparison is on screen:
- "career": each window against the hitter's career-to-date wOBA since 2023, hot AND cold, kept
  only when at least two standard errors from it. For cold rows `kept` is the share of the slump
  that persisted and "back to baseline" means he recovered.
- "season": hot streaks at least 80 points above his own earlier-season rate.
`kept` is the share of the gap still there over one fixed horizon after the streak -- the next two
months, the same for every streak length. It is NOT the next window of the same length; that older
measure appears in the packet only for comparison. Streaks too late in the season to have the full
horizon after them are not scored, which tilts the figures toward early- and mid-season streaks.
A case marked "too late to score" has no verdict; do not describe it as having faded or held. The
rest of the rows are case studies chosen by rule (the biggest contact-quality moves in each season), not
hand-picked for their outcome. Lead with what the ladder supports: length makes a streak more
believable; in the career view slumps persist more than hot streaks; and contact quality (earned
vs lucky) shows no detectable difference -- every interval includes zero, and in the career view
the lucky groups are mostly too small to compare. Never say "proven identical". Use one or two
case studies as illustration only. 2026 rows are a development set: mention them only as a
comparison. "Career" here means at most three prior seasons, since the data starts in 2023.
""",
 "vs": """This evidence is one head-to-head matchup. The headline is a PROBABILITY that one
player outperforms the other over a stated window, not a projection of either player's line.
Lead with it, attached to the window, and never name a winner without it. The estimated gap is
a difference in estimated true talent; it is not a prediction of the margin and must not be
described as one. Say where the uncertainty comes from -- sampling noise is usually most of it,
which is why two clearly different players land near a coin flip over a short window. If the
probability is under about 60%, say plainly that this is close to a coin flip. Do not advise a
trade, a start or a sit.""",
 "planner": """This evidence is a sample-size calculation. Two different questions share one
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

const MODEL = process.env.PROFILE_MODEL || "claude-haiku-4-5-20251001";
const DIR   = path.join(process.cwd(), "prompts");
const BASE  = fs.readFileSync(path.join(DIR, "base.md"), "utf8");
const VIEWS = ["stretch", "changes", "carry", "planner", "breakouts", "card", "vs", "line"];
const VIEW_PROMPT = Object.fromEntries(
  VIEWS.map(v => [v, fs.readFileSync(path.join(DIR, v + ".md"), "utf8")]));

// $ per million tokens. Overridable so a model swap does not need a code change.
const PRICE = { in: +(process.env.PRICE_IN || 1), out: +(process.env.PRICE_OUT || 5) };   // Haiku 4.5

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

  const { view, evidence } = req.body || {};
  if (!VIEWS.includes(view)) return res.status(400).json({ error: "unknown view: " + view });
  if (!evidence || !Array.isArray(evidence.rows) || !evidence.rows.length)
    return res.status(400).json({ error: "body must be { view, evidence } with evidence.rows" });
  if (!process.env.ANTHROPIC_API_KEY)
    return res.status(500).json({ error: "ANTHROPIC_API_KEY is not set on this deployment" });

  // The client already built the evidence and is showing it to the reader. Trusting
  // it keeps the audit table and the model's input identical by construction --
  // rebuilding it here would let the two drift, which is the one thing that would
  // make the "check every sentence" claim false.
  const payload = { view, title: evidence.title, subject: evidence.sub,
                    columns: evidence.cols.map(c => c.k), rows: evidence.rows,
                    context: evidence.context };

  const upstream = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": process.env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 500,
      stream: true,
      // BASE is byte-identical on every call, so it caches: reads bill at 0.1x.
      // The per-view block sits after the cache breakpoint and is cheap.
      system: [
        { type: "text", text: BASE, cache_control: { type: "ephemeral" } },
        { type: "text", text: VIEW_PROMPT[view] },
      ],
      messages: [{ role: "user", content: JSON.stringify(payload) }],
    }),
  });

  if (!upstream.ok || !upstream.body) {
    return res.status(502).json({ error: "upstream " + upstream.status, detail: await upstream.text() });
  }

  // Relayed as newline-delimited JSON, not raw SSE: the browser gets exactly the
  // three event shapes it needs (delta / error / done) instead of having to
  // understand Anthropic's event framing too. usage arrives split across
  // message_start (input + cache) and message_delta (output, cumulative), so it
  // is accumulated here and only reported once, in the final "done" line.
  res.writeHead(200, {
    "content-type": "application/x-ndjson",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });

  const usage = { input_tokens: 0, cache_read_input_tokens: 0, output_tokens: 0 };
  const reader = upstream.body.getReader();
  const dec = new TextDecoder();
  let buf = "", sawError = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const dataLine = raw.split("\n").find(l => l.startsWith("data:"));
        if (!dataLine) continue;
        let evt;
        try { evt = JSON.parse(dataLine.slice(5).trim()); } catch { continue; }

        if (evt.type === "message_start") {
          Object.assign(usage, evt.message.usage);
        } else if (evt.type === "content_block_delta" && evt.delta && evt.delta.type === "text_delta") {
          res.write(JSON.stringify({ type: "delta", text: evt.delta.text }) + "\n");
        } else if (evt.type === "message_delta" && evt.usage) {
          Object.assign(usage, evt.usage);
        } else if (evt.type === "error") {
          sawError = true;
          res.write(JSON.stringify({ type: "error", error: (evt.error && evt.error.message) || "stream error" }) + "\n");
        }
      }
    }
  } catch (e) {
    res.write(JSON.stringify({ type: "error", error: "stream failed: " + e.message }) + "\n");
    return res.end();
  }

  if (!sawError) {
    const billedIn = (usage.input_tokens || 0) + 0.1 * (usage.cache_read_input_tokens || 0);
    const cost = (billedIn * PRICE.in + (usage.output_tokens || 0) * PRICE.out) / 1e6;
    res.write(JSON.stringify({ type: "done", model: MODEL, usage, cost, source: "live" }) + "\n");
  }
  res.end();
};
""")

# ---------------------------------------------------------------- vercel.json
(OUT / "vercel.json").write_text(json.dumps({
    "framework": None,
  "headers": [
    {"source": "/data/(.*)",
     "headers": [{"key": "Cache-Control", "value": "public, max-age=300, s-maxage=86400, stale-while-revalidate=604800"}]},
    {"source": "/(styles.css|app.js|lib/evidence.js)",
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
implements `POST /api/summary`, the one route Vercel would run as a function.

Two modes, chosen automatically:

| | behaviour |
|---|---|
| `ANTHROPIC_API_KEY` **not** set | returns a stored profile; only the four demo players (Bregman, Raleigh, Walker, Cease). The meter says so in orange. |
| `ANTHROPIC_API_KEY` set | calls the model for any player and window, exactly as `api/summary.js` does |

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
lib/evidence.js   evidence builder, UMD-wrapped so the browser and the
                  function share ONE implementation. The audit table and the
                  model's input cannot drift apart.
api/summary.js    Vercel function. The only reason it exists is that the key
                  cannot live in the browser.
serve.py          local equivalent, zero dependencies.
report.html       GENERATED from ../output/full_report.html by ../publish_report.py.
                  Edit the source report and re-run the script; never edit this copy.
img/ball.svg      the small baseball icon in the masthead (also the favicon).
img/hero-batter.jpg  landing-page photo. CC0 1.0 (public domain dedication) by
                  joshchristiane, https://www.flickr.com/photos/200661331@N05/53858412166
                  CC0 covers copyright only: he is an identifiable minor-league player
                  and team/brand logos are visible. Fine for this non-commercial site;
                  replace it before any commercial use.
og.png            1200x630 link-preview image (og:image on all three pages).
                  Built by `python3 make_og.py` from img/og-batter.jpg -- edit the
                  script, never the PNG.
img/og-batter.jpg CC0 1.0, rawpixel.com/image/6112394 (found via Openverse).
                  Public domain: no attribution required, commercial use fine.
data/*.json       per-(type, season) shards + blocks_index.json
data/breakouts.json  Streak history tab: two views (career-to-date |z|>=2 hot+cold, and
                  earlier-season hot streaks), each a ladder + case studies, written by
                  `python3 breakouts.py --export web/data/breakouts.json` (not refreshed
                  by the pipeline; re-run it by hand).
prompts/breakouts.md  summary prompt for the Streak history tab
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

# A tiny placeholder so a fresh clone has no dead og:image. The real 1200x630
# image is built by make_og.py, so this must never overwrite an existing file.
if not (OUT / "og.png").exists():
    (OUT / "og.png").write_bytes(bytes.fromhex(
     "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
     "890000000a49444154789c6300010000050001" "0d0a2db4" "0000000049454e44ae426082"))
print("wrote README.md")
