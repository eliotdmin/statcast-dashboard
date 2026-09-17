import json, os, re
# Where the pipeline writes its JSON. Defaults to the repo's own output/,
# which is what you want when running this from a checkout.
OUTDIR = os.environ.get("STATCAST_OUT", "output") + "/"

UP = OUTDIR + "blocks/"
ALL = {}
for kind in ("bat", "pit"):
    d = json.load(open(UP + f"{kind}-2026.json"))
    bi = {b: i for i, b in enumerate(d["blocks"])}
    for r in d["rows"]:
        r["b"] = {str(bi[b]): [round(x, 1) for x in v] for b, v in r["b"].items()}
    ALL[kind] = d
D = json.dumps(ALL, separators=(",", ":"))
PROF = json.dumps(json.load(open("profiles.json")), separators=(",", ":"))
print("payload bytes:", len(D), "(vs 5,678,053 for all four seasons)")

HEAD = open("head.html").read()
BODY = open("body.html").read()

# ---------------------------------------------------------------- extra CSS
CSS = """
/* ---- deployment banner ---- */
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
.guard{padding:12px 16px;border-top:1px solid var(--hair);font-size:12px;color:var(--ink3);
  line-height:1.55}
.guard b{color:var(--ink2)}
.ev-note{font-size:12px;color:var(--ink3);margin:0 0 10px;max-width:78ch;line-height:1.5}
td.vd{font-weight:600}
td.vd.real{color:var(--hot)}
td.vd.weak{color:var(--ink2)}
td.vd.noise{color:var(--ink3);font-weight:400}
"""
if ".ai-head{" not in HEAD:
    HEAD = HEAD.replace("</style>", CSS + "</style>")
HEAD = HEAD.replace("<title>Stretch Finder</title>",
                    "<title>Stretch Finder Deployed</title>")

# ---------------------------------------------------------------- banner
BANNER = """
<div class="dep">
  <span class="tag">Mockup</span>
  <span>What the app looks like once it leaves the artifact sandbox and runs on its own
  host. Two things are different from the live Stretch Finder: it ships
  <b>one season of one player type</b> (187&nbsp;KB gzipped instead of 1.9&nbsp;MB) and
  loads the rest only when you change the selector; and it has a
  <b>server-generated scouting profile</b>. The four profiles here are pre-generated so the
  mockup needs no key &mdash; in the deployed version the button posts to a serverless
  function that holds the API key and calls the model.</span>
</div>
"""
BODY = BODY.replace('<div class="ctrl">\n  <label class="f"><span>Type</span>',
                    BANNER + '\n<div class="ctrl">\n  <label class="f"><span>Type</span>', 1)

# ---------------------------------------------------------------- profile panel markup
# The mockup is a published artifact with no server behind it, so the transport
# is a local lookup. Everything above the transport -- the packet builders, the
# audit table, the state machine -- is the same summary.js the deployed site runs,
# which is the point: this is a mockup of the real component, not a picture of one.
STORED = "{\"changes\": \"Filtered to bat speed, improved, confirmed only, the change log returns 64 rows out of 1,644 \\u2014 and the filter has done something worth noticing before reading any individual name. Every one of these 64 cleared |z| = 2 against the player's own earlier season and then kept at least half the gain in the following window. That second condition is the one doing the work; it is checked after the fact rather than promised.\\n\\nThree rows sit clearly above the rest. Geraldo Perdomo went from 61.2 to 64.9 mph across May 16 \\u2013 Jun 1, a 3.7 mph move at z = 4.3 on 95 swings, and held 101% of it \\u2014 the gain was not merely retained, it extended. Xavier Edwards added 3.8 mph in the first half of May at z = 4.2, and Elly De La Cruz 3.3 mph in early July at z = 4.2. Bat speed is 95\\u201396% real at these sample sizes, so the z scores are close to the whole story and there is very little shrinkage left to apply.\\n\\nPerdomo appears three separate times \\u2014 May 1, May 16 and Jun 1 \\u2014 each against a baseline that includes the previous move. That is a player climbing in steps across two months rather than one window of good luck repeated, and it is the pattern this view exists to surface. Tristan Peters shows the same shape twice in June and July.\\n\\nA caution on what the held column can support. The two highest figures here, Perdomo at 101% and 141%, mean the following window came in above the move, not that the model predicted anything. At 93\\u201396 swings the held figure has its own error, and a single window above 100% is what a real gain plus ordinary variance looks like. The claim these rows support is that the swing changed and stayed changed. How much of it converts into contact quality or results is a different question, and nothing in this table answers it.\", \"carry\": \"The board is sorted by distance from each hitter's own earlier-season rate, and the top row is the one to read carefully. Cal Raleigh is at .501 wOBA over 82 plate appearances against a .255 baseline \\u2014 a gap of +246 points, the largest on the board. His carry is 32%, so the model expects him to hold about +79 points of it a month out rather than the full gap. Both halves of that matter: he is not expected to return to .255, and he is not expected to stay near .501.\\n\\nHis xwOBA of .422 sits close under the wOBA, which is the configuration where a large gap is least suspicious \\u2014 the contact quality is carrying the results rather than trailing them. Compare Rafael Devers at +162 points of gap and only 5% carry: his .500 wOBA against a .434 xwOBA and a .337 prior is a much thinner structure, and the model discounts nearly all of it.\\n\\nThe sell-side of the board is where the asymmetry shows. Julio Rodr\\u00edguez is 160 points below his baseline with 4% carry \\u2014 the model expects essentially none of the slump to persist, which makes him a buy rather than a concern. Nasim Nu\\u00f1ez is the odd row: \\u2212159 points of gap and a negative carry, meaning the projection lands on the other side of his baseline entirely. At 56 plate appearances that is a fitted value doing what fitted values do at small n, and it should not be read as a forecast of overperformance.\\n\\nTwo limits apply to every row. These are 50\\u2013101 plate appearance windows, where wOBA is well under half signal, so the gap column is mostly noise even where the carry ratio is stable. And the coefficients were fit on 2023\\u20132025 and evaluated once on 2026, so 2026 is no longer a clean holdout; the out-of-sample figures above the table describe the first evaluation, not this one.\", \"planner\": \"Bat speed reaches 70% reliability at 13 plate appearances. That is the headline and it is easy to misread, so take the two questions on this page separately.\\n\\nThe first is about ranking. Measured reliability is 0.974 at the half-season split, which is extraordinarily high \\u2014 bat speed is close to a directly observed physical quantity rather than an outcome mediated by a pitcher, a defence and a ballpark. Projecting that down with Spearman\\u2013Brown, a mere 13 plate appearances is enough for a bat-speed leaderboard to be 70% real. The same calculation on wOBA needs 525, and 2,023 for 90%, against a full season of roughly 600. A wOBA ranking never becomes 90% real inside one year.\\n\\nThe second question is about change in one player, and it is much more demanding. Confirming a 1.0 mph gain in bat speed at 80% power takes 369 plate appearances, nearly thirty times the sample that made the ranking trustworthy. Nothing is inconsistent here: separating players who differ by a full league standard deviation is an easier problem than resolving a one-unit move inside a single player, and they happen to share a reliability estimate.\\n\\nThe practical consequence is where the baseline matters. If the \\\"before\\\" window is short, the answer can come back not possible \\u2014 the baseline's own noise swamps the effect at any follow-up length, and the fix is to lengthen the baseline rather than watch longer. Any hitting lab comparing a post-change stretch against three weeks of \\\"before\\\" is in that regime and cannot collect its way out.\", \"stretch\": \"Alex Bregman has hit .407 over his last 226 plate appearances, which is the 98th percentile among hitters in this span, and almost nothing underneath it has moved.\\n\\nHis swing is the same swing. Bat speed 68.1 against 68.2 earlier in the season, swing length identical to two decimal places, swing direction unchanged. Contact quality is unchanged too: exit velocity up six tenths of a mile an hour, hard-hit rate up two points, launch angle up seven tenths \\u2014 every one of them inside what two windows of this size produce on their own. The one thing in his profile that clears the noise bar is his chase rate, which has gone from 21.3% to 27.4%. That is a real change of roughly a full standard deviation, and it is the wrong direction.\\n\\nAgainst that, his expected wOBA moved from .310 to .334, which does not clear the bar either. So the results are up 97 points and the inputs are up 24, and wOBA at 226 plate appearances is 50% signal \\u2014 his shrunk percentile is the 74th, not the 98th. Chase rate is the number to watch, and at this sample it is already telling you something.\"}"

PANEL = ""   # summary.js builds its own markup

JS = r"""
var ENDPOINT = "a stored response";
var IDLE = 'On the deployed site this button posts the table below to '+
  '<code>POST /api/summary</code>, which holds the key server-side. This is a published '+
  'artifact with no server behind it, so it returns a stored response written against real '+
  'output from this dataset. The packet, the table and the state machine are the real ones.';

var STORED = {"changes": "Filtered to bat speed, improved, confirmed only, the change log returns 64 rows out of 1,644 \u2014 and the filter has done something worth noticing before reading any individual name. Every one of these 64 cleared |z| = 2 against the player's own earlier season and then kept at least half the gain in the following window. That second condition is the one doing the work; it is checked after the fact rather than promised.\n\nThree rows sit clearly above the rest. Geraldo Perdomo went from 61.2 to 64.9 mph across May 16 \u2013 Jun 1, a 3.7 mph move at z = 4.3 on 95 swings, and held 101% of it \u2014 the gain was not merely retained, it extended. Xavier Edwards added 3.8 mph in the first half of May at z = 4.2, and Elly De La Cruz 3.3 mph in early July at z = 4.2. Bat speed is 95\u201396% real at these sample sizes, so the z scores are close to the whole story and there is very little shrinkage left to apply.\n\nPerdomo appears three separate times \u2014 May 1, May 16 and Jun 1 \u2014 each against a baseline that includes the previous move. That is a player climbing in steps across two months rather than one window of good luck repeated, and it is the pattern this view exists to surface. Tristan Peters shows the same shape twice in June and July.\n\nA caution on what the held column can support. The two highest figures here, Perdomo at 101% and 141%, mean the following window came in above the move, not that the model predicted anything. At 93\u201396 swings the held figure has its own error, and a single window above 100% is what a real gain plus ordinary variance looks like. The claim these rows support is that the swing changed and stayed changed. How much of it converts into contact quality or results is a different question, and nothing in this table answers it.", "carry": "The board is sorted by distance from each hitter's own earlier-season rate, and the top row is the one to read carefully. Cal Raleigh is at .501 wOBA over 82 plate appearances against a .255 baseline \u2014 a gap of +246 points, the largest on the board. His carry is 32%, so the model expects him to hold about +79 points of it a month out rather than the full gap. Both halves of that matter: he is not expected to return to .255, and he is not expected to stay near .501.\n\nHis xwOBA of .422 sits close under the wOBA, which is the configuration where a large gap is least suspicious \u2014 the contact quality is carrying the results rather than trailing them. Compare Rafael Devers at +162 points of gap and only 5% carry: his .500 wOBA against a .434 xwOBA and a .337 prior is a much thinner structure, and the model discounts nearly all of it.\n\nThe sell-side of the board is where the asymmetry shows. Julio Rodr\u00edguez is 160 points below his baseline with 4% carry \u2014 the model expects essentially none of the slump to persist, which makes him a buy rather than a concern. Nasim Nu\u00f1ez is the odd row: \u2212159 points of gap and a negative carry, meaning the projection lands on the other side of his baseline entirely. At 56 plate appearances that is a fitted value doing what fitted values do at small n, and it should not be read as a forecast of overperformance.\n\nTwo limits apply to every row. These are 50\u2013101 plate appearance windows, where wOBA is well under half signal, so the gap column is mostly noise even where the carry ratio is stable. And the coefficients were fit on 2023\u20132025 and evaluated once on 2026, so 2026 is no longer a clean holdout; the out-of-sample figures above the table describe the first evaluation, not this one.", "planner": "Bat speed reaches 70% reliability at 13 plate appearances. That is the headline and it is easy to misread, so take the two questions on this page separately.\n\nThe first is about ranking. Measured reliability is 0.974 at the half-season split, which is extraordinarily high \u2014 bat speed is close to a directly observed physical quantity rather than an outcome mediated by a pitcher, a defence and a ballpark. Projecting that down with Spearman\u2013Brown, a mere 13 plate appearances is enough for a bat-speed leaderboard to be 70% real. The same calculation on wOBA needs 525, and 2,023 for 90%, against a full season of roughly 600. A wOBA ranking never becomes 90% real inside one year.\n\nThe second question is about change in one player, and it is much more demanding. Confirming a 1.0 mph gain in bat speed at 80% power takes 369 plate appearances, nearly thirty times the sample that made the ranking trustworthy. Nothing is inconsistent here: separating players who differ by a full league standard deviation is an easier problem than resolving a one-unit move inside a single player, and they happen to share a reliability estimate.\n\nThe practical consequence is where the baseline matters. If the \"before\" window is short, the answer can come back not possible \u2014 the baseline's own noise swamps the effect at any follow-up length, and the fix is to lengthen the baseline rather than watch longer. Any hitting lab comparing a post-change stretch against three weeks of \"before\" is in that regime and cannot collect its way out.", "stretch": "Alex Bregman has hit .407 over his last 226 plate appearances, which is the 98th percentile among hitters in this span, and almost nothing underneath it has moved.\n\nHis swing is the same swing. Bat speed 68.1 against 68.2 earlier in the season, swing length identical to two decimal places, swing direction unchanged. Contact quality is unchanged too: exit velocity up six tenths of a mile an hour, hard-hit rate up two points, launch angle up seven tenths \u2014 every one of them inside what two windows of this size produce on their own. The one thing in his profile that clears the noise bar is his chase rate, which has gone from 21.3% to 27.4%. That is a real change of roughly a full standard deviation, and it is the wrong direction.\n\nAgainst that, his expected wOBA moved from .310 to .334, which does not clear the bar either. So the results are up 97 points and the inputs are up 24, and wOBA at 226 plate appearances is 50% signal \u2014 his shrunk percentile is the 74th, not the 98th. Chase rate is the number to watch, and at this sample it is already telling you something."};

function send(pk){
  // Same shape and the same latency the network path has, so the loading states
  // are exercised rather than skipped.
  return new Promise(function(resolve, reject){
    setTimeout(function(){
      var text = STORED[pk.view];
      if(!text) return reject(new Error("No stored response for the " + pk.view + " view."));
      var words = text.split(/\s+/).length;
      resolve({summary:text, model:"claude-sonnet-4-5", source:"stored",
               usage:{input_tokens:1800 + 40*pk.rows.length,
                      cache_read_input_tokens:1650,
                      output_tokens:Math.round(words*1.35)},
               cost:0});
    }, 900);
  });
}
""" + open("summary.js").read() + r"""

function currentPacket(){
  var me=ROWS.find(function(r){return String(r.id)===String($("#who").value);});
  if(!me) return null;
  var shard=ALL[shardKey(K,YR)];
  var metrics=MET.map(function(m){return {k:m.k,n:m.n,d:m.d,hi:m.hi,g:m.g};});
  return Packet.build(shard, metrics, PK, me.id, BL[+$("#from").value], BL[+$("#to").value]);
}
"""

# hook the panel into the existing render cycle
BODY = BODY.replace("  $(\"#bars\").innerHTML=html;\n  renderComps(me,mine,myN,i0,i1);",
                    "  $(\"#bars\").innerHTML=html;\n  if(window.SUM) SUM.reset();\n"
                    "  renderComps(me,mine,myN,i0,i1);")
BODY = BODY.replace("setKind();\n})();",
                    JS + "\nSUM.mount(TABS[active][1].slice(1));\nsetKind();\n})();")

# open on a realistic working state: Bregman, the last four blocks
BODY = BODY.replace('$("#from").value=yb[Math.min(2,yb.length-1)]; $("#to").value=yb[Math.min(4,yb.length-1)];',
 '''$("#from").value=yb[Math.max(0,yb.length-4)]; $("#to").value=yb[yb.length-1];
  var pref=K==="bat"?"608324":"656302";
  if(ROWS.some(function(r){return String(r.id)===pref;})) $("#who").value=pref;''')

# the header line: this build ships one season
BODY = BODY.replace("2023&ndash;2026 &middot; 1,590 hitter-seasons &middot; 1,917 pitcher-seasons &middot; everything computed in your browser",
                    "2026 season &middot; 386 hitters &middot; 458 pitchers &middot; 187 KB first paint &middot; profile generated server-side")
BODY = BODY.replace("Four views of the same idea, and a writer that reads the evidence packet",
                    "Four views of the same idea, and a writer that reads the evidence packet")

out = HEAD + BODY.replace("__DATA__", D)
open("mockup.html", "w").write(out)
print("wrote mockup.html", os.path.getsize("mockup.html"))
