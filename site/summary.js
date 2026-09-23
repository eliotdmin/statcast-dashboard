/* ===========================================================================
   "Read this view" -- one summary component for all four tabs.

   The design constraint that shapes everything here: the model must never see a
   number without its error bar. That is why there is no free-text question box
   and no chat. Each view builds a typed evidence object from what is actually on
   screen, that evidence is rendered as a table the reader can open, and the same
   object is what gets posted. If the prose says something the table does not
   support, that is visible in one click rather than plausible-sounding forever.

   The component is a single node that moves into whichever panel is open, so
   there is one state machine and one set of ids rather than four of each.
   =========================================================================== */
var SUM = (function(){
  "use strict";
  var node = null, ctl = null, timer = null, current = null;

  /* ---------------------------------------------------------- evidence builders
     One per view. Each returns {view, title, sub, note, cols, rows, context}.
     cols/rows are what the audit table renders AND what the model receives --
     the same array, not two constructions of it, so they cannot disagree. */
  var BUILD = {
    "p-stretch": function(){ return stretchPacket(currentEvidence(), "Scouting profile"); },
    // The card's summary must explain the card's verdict, not re-derive its own: it gets the
    // same metric rows as the Percentiles read, plus the verdict and the carry numbers that
    // produced it. Without them it answered a different question and could contradict the card.
    "p-card": function(){
      var ev=cardEvidence(), pk=stretchPacket(ev, "Player check"), me=cardPlayer();
      if(!pk||!me) return null;
      var W=+$("#pc-win").value, carry=cardCarry(me), v=cardVerdict(ev, carry, W);
      var txt=function(h){ var d=document.createElement("div"); d.innerHTML=h; return d.textContent; };
      var verdict={headline:txt(v.h), explanation:txt(v.p),
        carry_model_30d:carry?{gap:+carry.gap.toFixed(3), expected_next_month:+carry.expect.toFixed(3),
          share_expected_to_stick:+carry.carry.toFixed(2)}:null,
        hot_streak_history_share_kept:K==="bat"?LADDER[W]:null,
        usual_level_from_prior_seasons:v.usual||null};
      pk.view="card";
      pk.sub=pk.sub+" · verdict: "+verdict.headline;
      pk.note="<b>Card verdict:</b> "+v.h+". "+v.p+" "+pk.note;
      pk.context.verdict=verdict;
      return pk;
    },
  };
  function stretchPacket(pk, title){
      if(!pk) return null;
      var avail = pk.metrics.filter(function(m){ return m.available; });
      if(!avail.length) return null;
      return {
        view:"stretch",
        title:title,
        sub:pk.player+" · "+lbl(pk.span.from)+"–"+lblEnd(pk.span.to)+
            " · "+pk.span.n+" "+PANAME[K]+" · vs "+pk.peer_pool.n_players+" peers",
        note:"Every metric arrives pre-shrunk, with the reliability of its percentile at this "+
             "sample size and, where a baseline exists, the change against the player's own "+
             "earlier-season rate divided by the standard error sampling noise alone would produce.",
        cols:[{k:"metric",l:"metric",a:"l"},{k:"value",l:"value"},{k:"pct_raw",l:"pct raw"},
              {k:"rel",l:"% real"},{k:"pct_shrunk",l:"pct shrunk"},{k:"base",l:"baseline"},
              {k:"delta",l:"Δ"},{k:"z",l:"z"},{k:"sd",l:"sd"},{k:"verdict",l:"verdict",a:"l"}],
        rows:avail.map(function(r){
          var m=getM(r.metric), f=m?m.f:String, c=r.change;
          return {metric:r.metric, value:f(r.value), pct_raw:Math.round(r.pct_raw),
                  rel:Math.round(100*r.reliability), pct_shrunk:Math.round(r.pct_shrunk),
                  base:c?f(c.base_value):"—",
                  delta:c?(c.delta>0?"+":"")+f(c.delta):"—",
                  z:c?c.delta_z.toFixed(2):"—",
                  sd:c?(c.delta_sd>0?"+":"")+c.delta_sd.toFixed(2):"—",
                  verdict:c?c.verdict+" / "+c.size:"—",
                  _cls:c?("vd "+c.verdict):""};
        }),
        context:{evidence:pk}
      };
  }
  Object.assign(BUILD, {
    "p-break": function(){
      if(!BRK) return null;
      var v=bView(), V=BRK.views[v], career=v==="career";
      return {
        view:"breakouts",
        title:"Read the streak study",
        sub:career ? "Hitters, 2024–2025 · hot and cold streaks vs. career-to-date, |z| ≥ 2 · "+V.cases.length+" case studies"
                   : "Hitters, 2023–2025 · hot streaks vs. earlier-season rate · "+V.cases.length+" case studies",
        note:(career ? "Baseline: the hitter's career-to-date wOBA since 2023 (at least 300 PA). Only windows "+
               "at least 2 standard errors above (hot) or below (cold) it. For cold rows, kept = the share "+
               "of the slump that persisted. "
             : "Baseline: the hitter's wOBA earlier the same season; streaks are 80+ points above it. ")+
             "kept = share of the gap still there over the following "+(BRK.horizon_days||60)+" days — "+
             "one fixed horizon for every streak length, not the next window of equal length. Streaks too "+
             "late in the season to have that full horizon are not scored. Case studies are "+
             "the biggest contact-quality moves in each season, chosen by rule. 2026 rows are a "+
             "development set, not a clean test.",
        cols:[{k:"row",l:"row",a:"l"},{k:"a",l:"streaks / gap"},{k:"b",l:"kept / xwOBA move"},
              {k:"c",l:"back to baseline / after the streak"},{k:"d",l:"earned vs lucky kept / rest of season"},
              {k:"e",l:"CI / outcome",a:"l"}],
        rows:V.ladder.map(function(r){
          var ci=r.earned_minus_lucky_ci;
          return {row:r.seasons+" · "+(r.dir||"hot")+" "+WINNAME[r.blocks], a:"n="+r.all.n,
                  b:pct0(r.all.kept), c:pct0(r.all.kaput),
                  d:(r.earned?pct0(r.earned.kept)+" (n="+r.earned.n+")":"—")+" vs "+
                    (r.lucky?pct0(r.lucky.kept)+" (n="+r.lucky.n+")":"—"),
                  e:ci?"earned−lucky 95% CI ["+pct0(ci[0])+", "+pct0(ci[1])+"]":"—"};
        }).concat(V.cases.map(function(c){
          return {row:c.player+" "+c.season+" "+lbl(c.block)+" "+(c.dir||"hot")+" (baseline "+w3(c.baseline)+")",
                  a:sw3(c.gap), b:sw3(c.xgap), c:c.fwd_gap==null?"—":sw3(c.fwd_gap),
                  d:c.ros_gap==null?"—":sw3(c.ros_gap), e:OUTCOME[c.dir||"hot"][c.outcome][0]};
        })),
        context:{baseline:v, thresholds:{hot:BRK.hot, earned:BRK.earned, lucky:BRK.lucky, z_min:BRK.z_min}}
      };
    },
    "p-changes": function(){
      var v = VIEWSTATE.changes; if(!v || !v.rows.length) return null;
      var f = v.filters;
      var desc = [f.metric==="all"?"all metrics":f.metric,
                  f.dir==="any"?null:(f.dir==="up"?"improved":"declined"),
                  f.minN?("min "+f.minN):null,
                  f.conf?"confirmed only":null,
                  f.win, "|z| ≥ "+f.z].filter(Boolean).join(" · ");
      return {
        view:"changes",
        title:"Read the change log",
        sub:v.rows.length.toLocaleString()+" of "+v.total.toLocaleString()+" moves · "+desc,
        note:"These are the rows your filters produced, in the order the board shows them. "+
             "<b>held</b> is out of sample: the share of the move still present over the following "+
             "60 days, computed after the fact. The model is told to treat an unconfirmed row as a "+
             "watch-list entry and not as a claim.",
        cols:[{k:"player",l:"player",a:"l"},{k:"metric",l:"metric",a:"l"},{k:"window",l:"window",a:"l"},
              {k:"prior",l:"prior"},{k:"now",l:"now"},{k:"delta",l:"Δ"},{k:"z",l:"z"},
              {k:"sd",l:"sd"},{k:"rel",l:"% real"},{k:"n",l:"n"},{k:"held",l:"held"}],
        rows:v.rows.slice(0,40).map(function(o){
          var f2=o.f.f;                       // o.f is the metric object itself
          return {player:o.p, metric:o.m, window:sh(BL[o.a])+"–"+sh(BL[o.b]),
                  prior:f2(o.base), now:f2(o.v),
                  delta:(o.v-o.base>0?"+":"")+f2(o.v-o.base),
                  z:o.z.toFixed(1), sd:(o.sdu>0?"+":"")+o.sdu.toFixed(1),
                  rel:Math.round(100*o.rel), n:Math.round(o.n),
                  held:Math.round(100*o.held)+"%"};
        }),
        context:{filters:f, matched:v.rows.length, total:v.total,
                 testable:v.testable, confirmed:v.confirmed,
                 season:v.season, kind:v.kind}
      };
    },

    // One player's own moves (Player tab). Same prompt as the league board: the rows have the same
    // shape, and the rules about `held` apply to one player exactly as to many.
    "p-changes-mine": function(){
      var v = VIEWSTATE.changesMine; if(!v || !v.rows.length) return null;
      return {
        view:"changes",
        title:"Read his changes",
        sub:v.player+" · "+v.rows.length+" move"+(v.rows.length===1?"":"s")+" · "+v.win+" · |z| ≥ "+v.z,
        note:"Every move this player made against his own earlier season, in the order the table "+
             "shows them. <b>held</b> is out of sample: the share still present over the following "+
             "60 days. The model is told to treat an unconfirmed row as a watch-list entry, not a claim.",
        cols:[{k:"metric",l:"metric",a:"l"},{k:"window",l:"window",a:"l"},
              {k:"prior",l:"prior"},{k:"now",l:"now"},{k:"delta",l:"Δ"},{k:"z",l:"z"},
              {k:"sd",l:"sd"},{k:"rel",l:"% real"},{k:"n",l:"n"},{k:"held",l:"held"}],
        rows:v.rows.slice(0,40).map(function(o){
          var f2=o.f.f;
          return {player:o.p, metric:o.m, window:sh(BL[o.a])+"–"+sh(BL[o.b]),
                  prior:f2(o.base), now:f2(o.v), delta:(o.v-o.base>0?"+":"")+f2(o.v-o.base),
                  z:o.z.toFixed(1), sd:(o.sdu>0?"+":"")+o.sdu.toFixed(1),
                  rel:Math.round(100*o.rel), n:Math.round(o.n), held:Math.round(100*o.held)+"%"};
        }),
        context:{player:v.player, pending_hidden:v.pending, season:v.season, kind:v.kind}
      };
    },

    "p-card-league": function(){
      var v = VIEWSTATE.hc; if(!v || !(v.hot.length + v.cold.length)) return null;
      var row=function(p,side){ return {player:p.n, side:side, pa:Math.round(p.pa),
        recent:D3(p.w), earlier:D3(p.wb), vs_earlier:(p.gap>0?"+":"\u2212")+D3(Math.abs(p.gap)),
        z:p.z.toFixed(1),
        usual:p.u?D3(p.u.mean):"—",
        vs_usual:(p.u?((p.w-p.u.mean>0?"+":"\u2212")+D3(Math.abs(p.w-p.u.mean))):"—"),
        contact:(p.xgap>0?"+":"\u2212")+D3(Math.abs(p.xgap))}; };
      return {
        view:"hotcold",
        title:"Read the hot and cold board",
        sub:v.nhot+" hot, "+v.ncold+" cold of "+v.pool+" · "+v.span+" "+v.season,
        note:"The players the board lists, in its order (at most twelve a side). <b>vs. earlier</b> "+
             "is against his own rate earlier this season and <b>vs. usual</b> against his prior "+
             "seasons; <b>contact</b> is the same move measured on xwOBA, which is steadier than "+
             "results at this sample size.",
        cols:[{k:"player",l:"player",a:"l"},{k:"side",l:"side",a:"l"},{k:"pa",l:"PA"},
              {k:"recent",l:"recent"},{k:"earlier",l:"earlier"},{k:"vs_earlier",l:"vs. earlier"},
              {k:"z",l:"z"},{k:"usual",l:"usual"},{k:"vs_usual",l:"vs. usual"},
              {k:"contact",l:"contact"}],
        rows:v.hot.map(function(p){return row(p,"hot");})
              .concat(v.cold.map(function(p){return row(p,"cold");})),
        context:{window:v.window, span:v.span, test:v.mode, hot:v.nhot, cold:v.ncold,
                 pool:v.pool, metric:v.metric, kind:v.kind, season:v.season}
      };
    },

    "p-carry": function(){
      var v = VIEWSTATE.carry; if(!v || !v.board.length) return null;
      var wo = v.kind==="bat" ? "wOBA" : "wOBA allowed";
      return {
        view:"carry",
        title:"Read the carry board",
        sub:v.board.length+" of "+v.total+" qualifying "+(v.kind==="bat"?"hitters":"pitchers")+
            " · "+v.span+" "+v.season,
        note:"<b>carry</b> is a discount rate, not a forecast: the fraction of the gap from a "+
             "player's own baseline that has historically survived a month. The model is told "+
             "that a large gap with low carry is a sell candidate and the mirror is a buy, and "+
             "that it may not explain any gap by injury, mechanics or luck.",
        cols:[{k:"player",l:"player",a:"l"},{k:"n",l:"n"},{k:"woba",l:wo},{k:"xwoba",l:"x"+wo},
              {k:"prior",l:"prior"},{k:"gap",l:"gap"},{k:"expect",l:"expect"},{k:"carry",l:"carry"}],
        rows:v.board.map(function(b){
          return {player:b.r.n, n:b.n.toFixed(0), woba:D3(b.w), xwoba:D3(b.x), prior:D3(b.wb),
                  gap:(b.gap>0?"+":"")+D3(b.gap),
                  expect:(b.pred-b.wb>0?"+":"")+D3(b.pred-b.wb),
                  carry:Math.round(100*b.carry)+"%",
                  _cls:b.gap>0?"up":"dn"};
        }),
        context:{model:v.model, kind:v.kind, season:v.season, span:v.span,
                 caveat:"Coefficients were fit on 2023-2025 and scored on 2026; 2026 has been "+
                        "queried many times and is no longer a clean holdout, so its R2 is optimistic."}
      };
    },

    "p-vs": function(){
      var v = VIEWSTATE.vs; if(!v) return null;
      var wo = v.kind==="bat" ? "wOBA" : "wOBA allowed";
      var pct = function(x){ return Math.round(100*x/(v.vTalent+v.vDrift+v.vSample))+"%"; };
      var horizon = v.months===0.5 ? "the next 2 weeks"
                  : v.months===1 ? "the next month"
                  : "the next "+v.months+" months";
      return {
        view:"vs",
        title:"Read this matchup",
        sub:v.a.name+" vs "+v.b.name+" · standing on "+v.asOf+" "+v.season+", looking "+
            horizon+" · "+(v.kind==="bat"?"hitters":"pitchers"),
        note:"The headline is <b>P("+v.favourite+" outperforms the other over "+horizon+
             ") = "+Math.round(100*v.shown)+"%</b>. It is a probability, not a projection: this "+
             "project measured a one-month point forecast at R&sup2; ~0.06 against a 0.264 "+
             "ceiling, so the ordering is the only claim the evidence supports. The model must "+
             "not name a winner without the probability attached, must not read the estimated "+
             "gap as a prediction of the margin, and must say plainly that sampling noise is "+
             pct(v.vSample)+" of the uncertainty here.",
        cols:[{k:"what",l:"",a:"l"},{k:"a",l:v.a.name},{k:"b",l:v.b.name}],
        rows:[
          {what:"estimated true "+wo, a:D3(v.a.talent),  b:D3(v.b.talent)},
          {what:"this season",        a:v.a.season==null?"—":D3(v.a.season),
                                      b:v.b.season==null?"—":D3(v.b.season)},
          {what:"usual level (prior seasons)", a:D3(v.a.usual), b:D3(v.b.usual)},
          {what:"this season, "+(v.kind==="bat"?"PA":"BF"), a:Math.round(v.a.pa).toLocaleString(),
                                      b:Math.round(v.b.pa).toLocaleString()},
          {what:"assumed ahead",      a:v.a.expPA.toLocaleString(), b:v.b.expPA.toLocaleString()}
        ],
        context:{
          probability:v.p, favourite:v.favourite, horizon:horizon,
          as_of:v.asOf+" "+v.season,
          gap_points:Math.round(1000*v.gap),
          uncertainty:{talent:pct(v.vTalent), drift:pct(v.vDrift), sampling:pct(v.vSample)},
          pa_to_separate:Math.round(v.paToSeparate),
          calibration:v.cal,
          caveat:"The drift term is a league-average constant: it knows nothing about injury, "+
                 "a swing change or a demotion. Playing time is the reader's input, not a "+
                 "forecast. Prior seasons reach back at most three years."
        }
      };
    },

    "p-planner": function(){
      var v = VIEWSTATE.planner; if(!v) return null;
      var inf = function(n){ return n===Infinity ? "not possible" : Math.round(n).toLocaleString(); };
      return {
        view:"planner",
        title:"Read the plan",
        sub:v.metric+" · target "+Math.round(100*v.target)+"% real · detect "+
            v.delta+" "+v.unit,
        note:"Two different questions share one reliability estimate. The first asks when a "+
             "<b>ranking</b> becomes real; the second asks how long it takes to confirm a "+
             "<b>change</b> in one player. The model is told not to conflate them.",
        cols:[{k:"q",l:"quantity",a:"l"},{k:"v",l:"value"},{k:"how",l:"where it comes from",a:"l"}],
        rows:[
          {q:"measured reliability", v:v.reliability.toFixed(3),
           how:"split-half at n₀ = "+v.n0+" "+v.unitName+", Spearman-Brown corrected"},
          {q:"league sd", v:(v.unit==="pp"?(100*v.leagueSD).toFixed(1)+" pp":v.leagueSD.toFixed(2)+" "+v.unit),
           how:"spread across qualified players over a half season"},
          {q:"sample for "+Math.round(100*v.target)+"% real", v:inf(v.nRel)+" "+v.unitName,
           how:"solve ρ(n) = "+v.target+" for n"},
          {q:"detect "+v.delta+" "+v.unit+" at 80% power", v:inf(v.n80)+" "+v.unitName,
           how:"α = .05 two-sided"+(v.baseline?", against a "+v.baseline.toLocaleString()+
               "-"+v.unitName+" baseline":", baseline treated as known")},
          {q:"detect the same at 90% power", v:inf(v.n90)+" "+v.unitName,
           how:"the same test, less willing to miss"}
        ].concat(v.impossible ? [{q:"minimum workable baseline",
           v:Math.round(v.minBaseline).toLocaleString()+" "+v.unitName,
           how:"below this the baseline's own noise swamps the effect at any follow-up length",
           _cls:"up"}] : []),
        context:{metric:v.metric, kind:v.kind, reliability:v.reliability, n0:v.n0,
                 target:v.target, nRel:v.nRel===Infinity?null:Math.round(v.nRel),
                 delta:v.delta, unit:v.unit, baseline:v.baseline,
                 n80:v.n80===Infinity?null:Math.round(v.n80),
                 n90:v.n90===Infinity?null:Math.round(v.n90),
                 impossible:v.impossible}
      };
    }
  });

  /* ------------------------------------------------------------------ render */
  function esc(x){ return String(x).replace(/&/g,"&amp;").replace(/</g,"&lt;"); }

  function table(pk){
    var h='<table><thead><tr>'+pk.cols.map(function(c){
      return '<th'+(c.a==="l"?' class="l"':'')+'>'+c.l+'</th>'; }).join("")+'</tr></thead><tbody>';
    pk.rows.forEach(function(r){
      h+='<tr>'+pk.cols.map(function(c,i){
        var cls=[]; if(c.a==="l") cls.push("l");
        if(i===pk.cols.length-1 && r._cls) cls.push(r._cls);
        return '<td'+(cls.length?' class="'+cls.join(" ")+'"':'')+'>'+esc(r[c.k])+'</td>';
      }).join("")+'</tr>';
    });
    return h+'</tbody></table>';
  }

  function shell(){
    return ''+
    '<div class="sum-head">'+
      '<div class="sum-t"><b id="sum-title">Read this view</b><span id="sum-sub">&mdash;</span></div>'+
      '<div class="sum-btns">'+
        '<button class="btn alt" id="sum-again" hidden>Regenerate</button>'+
        '<button class="btn" id="sum-go">Summarize</button>'+
      '</div>'+
    '</div>'+
    '<div class="warnbar" id="sum-stale" hidden>The filters changed since this read was '+
      'generated, so it no longer matches what&rsquo;s on screen. Click Regenerate for a fresh '+
      'one.</div>'+
    '<div class="sum-body" id="sum-body"></div>'+
    '<details class="ev" id="sum-evwrap">'+
      '<summary>Show the evidence the model is given <span id="sum-evn"></span></summary>'+
      '<div class="inner"><p class="ev-note" id="sum-evnote"></p><div class="tw" id="sum-ev"></div>'+
      '<p class="guard"><b>What the model is forbidden to say.</b> Calling a <code>noise</code> '+
      'verdict a change &middot; &ldquo;due for regression&rdquo; from a wOBA&minus;xwOBA gap &middot; '+
      'treating sweet-spot% as evidence &middot; any injury, mechanical or psychological explanation '+
      '&middot; &ldquo;small sample size&rdquo; as a hedge instead of the actual reliability &middot; '+
      'percentile language about anything under 0.3 reliability &middot; any number that is not in '+
      'the table above.</p></div>'+
    '</details>';
  }

  function mount(panelId){
    if(!node){
      node=document.createElement("section");
      node.className="sum"; node.id="sum";
      node.innerHTML=shell();
      node.querySelector("#sum-go").addEventListener("click",run);
      node.querySelector("#sum-again").addEventListener("click",function(){ reset(); run(); });
    }
    // an analysis with no builder (or none at all) gets no summary rather than an empty one
    if(!panelId || !BUILD[panelId]){ node.hidden=true; current=null; return; }
    node.hidden=false;
    var panel=document.getElementById(panelId);
    var slot=panel && panel.querySelector(".sum-slot");
    if(slot && node.nextSibling!==slot) slot.parentNode.insertBefore(node, slot);
    else if(panel && !slot && node.parentNode!==panel) panel.appendChild(node);
    current=panelId;
    reset();
  }

  function q(sel){ return node ? node.querySelector(sel) : null; }

  /* Never auto-fires a call -- every generation costs real tokens. Instead this
     tracks, per tab, the {title,sub} signature of whatever evidence the last
     completed generation actually described (node._genKeys, written by draw()).
     A filter change updates the evidence table live (always ground truth) but
     leaves any existing prose on screen untouched, flagged stale if its
     signature no longer matches -- so a reader never sees unflagged text that
     quietly stopped describing what's on screen, without every tweak costing a
     call the way unconditional auto-regeneration would. */
  function reset(){
    if(!node) return;
    if(timer){ clearTimeout(timer); timer=null; }
    if(ctl){ ctl.abort(); ctl=null; }
    var pk=null;
    try{ pk=BUILD[current] && BUILD[current](); }
    catch(e){ pk=null; if(window.console) console.warn("summary: "+current+" builder threw", e); }
    node._pk=pk;
    node._genKeys = node._genKeys || {};
    var key = pk ? (pk.title+"|"+pk.sub) : null;
    var genKey = node._genKeys[current];

    q("#sum-title").textContent = pk ? pk.title : "Read this view";
    q("#sum-sub").textContent   = pk ? pk.sub : "—";
    q("#sum-evwrap").hidden=!pk;
    if(pk){
      q("#sum-evn").textContent="("+pk.rows.length+" row"+(pk.rows.length===1?"":"s")+")";
      q("#sum-evnote").innerHTML=pk.note;
      q("#sum-ev").innerHTML=table(pk);
    } else {
      q("#sum-evn").textContent="";
      q("#sum-ev").innerHTML="";          // never leave the last view's evidence up
    }

    if(pk && genKey){
      // Already generated at least once for this tab -- leave the existing
      // prose and meter alone either way; only the staleness banner differs.
      q("#sum-stale").hidden = (genKey===key);
      q("#sum-again").hidden=false;
      q("#sum-go").disabled=false; q("#sum-go").hidden=true;
    } else if(pk){
      q("#sum-stale").hidden=true;
      q("#sum-again").hidden=true;
      q("#sum-go").disabled=false; q("#sum-go").hidden=false;
      q("#sum-body").innerHTML='<p class="sum-idle">'+IDLE+'</p>';
    } else {
      q("#sum-stale").hidden=true;
      q("#sum-again").hidden=true;
      q("#sum-go").disabled=true; q("#sum-go").hidden=false;
      q("#sum-body").innerHTML='<p class="sum-idle">Nothing to summarize yet — '+
        'widen the filters or pick a player.</p>';
    }
  }

  function run(){
    var pk=node && node._pk; if(!pk) return;
    q("#sum-stale").hidden=true;
    q("#sum-go").disabled=true;
    var reduce=window.matchMedia&&window.matchMedia("(prefers-reduced-motion:reduce)").matches;
    var steps=["building the evidence …",
               "checking "+pk.rows.length+" row"+(pk.rows.length===1?"":"s")+" against their error bars …",
               "POST "+ENDPOINT+" …"];
    q("#sum-body").innerHTML='<div class="status">'+steps.map(function(s,i){
        return '<span id="st'+i+'">'+(i?"  ":"› ")+s+'</span>'; }).join("")+'</div>'+
      '<div class="skel" style="width:96%"></div><div class="skel" style="width:88%"></div>'+
      '<div class="skel" style="width:92%"></div><div class="skel" style="width:54%"></div>';
    var k=0;
    (function step(){ var el=q("#st"+k); if(el) el.className="on"; k++;
      if(k<steps.length) timer=setTimeout(step, reduce?1:380); })();

    var t0=(window.performance&&performance.now)?performance.now():Date.now();
    var buf="", started=false;
    send(pk, function(chunk){
      if(timer){ clearTimeout(timer); timer=null; }
      if(!started){ started=true; q("#sum-body").innerHTML='<div class="prose"></div>'; }
      buf+=chunk;
      var paras=buf.split(/\n{2,}/);
      q("#sum-body .prose").innerHTML=paras.map(function(p){ return '<p>'+esc(p)+'</p>'; }).join("");
    }).then(function(j){
      draw(j, ((window.performance&&performance.now)?performance.now():Date.now())-t0);
    }).catch(function(e){
      if(e && e.name==="AbortError") return;
      q("#sum-body").innerHTML='<p class="sum-idle"><b>The summary call failed.</b> '+
        esc(e.message||e)+'</p>';
      q("#sum-go").disabled=false;
    });
  }

  /* By the time draw() runs, the prose is already on screen -- it streamed in
     via the onDelta callback above. This only appends the meter (which needs the
     terminal usage/cost, unavailable until the "done" line) and re-arms the UI. */
  function draw(j, ms){
    if(!q("#sum-body .prose")) q("#sum-body").innerHTML='<div class="prose"></div>';
    // node._pk is guaranteed to still be the evidence this generation actually
    // described: any filter change in the meantime would have reset() -> abort()'d
    // this call before draw() ever ran.
    var pk=node._pk;
    node._genKeys = node._genKeys || {};
    node._genKeys[current] = pk ? (pk.title+"|"+pk.sub) : null;
    q("#sum-stale").hidden=true;
    var u=j.usage||{};
    var bits=['<span><b>'+esc(j.model||"model")+'</b></span>'];
    if(u.input_tokens) bits.push('<span>'+u.input_tokens.toLocaleString()+' in'+
      (u.cache_read_input_tokens?' ('+u.cache_read_input_tokens.toLocaleString()+' cached at 0.1×)':'')+
      ' · '+(u.output_tokens||0)+' out</span>');
    // A stored response costs nothing, and printing $0.0000 next to a token
    // count invites the reading that the real call is free. Show the cost only
    // when something was actually billed.
    if(j.cost) bits.push('<span><b>$'+j.cost.toFixed(4)+'</b></span>');
    bits.push('<span>'+(ms/1000).toFixed(1)+'s</span>');
    bits.push(j.source==="stored"
      ? '<span style="color:var(--hot)">stored response — no API key set</span>'
      : '<span>key server-side</span>');
    q("#sum-body").insertAdjacentHTML("beforeend", '<div class="meter">'+bits.join("")+'</div>');
    q("#sum-again").hidden=false;
    q("#sum-go").disabled=false; q("#sum-go").hidden=true;
  }

  document.addEventListener("tabshow", function(e){ mount(e.detail.panel); });
  return {mount:mount, reset:reset, build:BUILD, evidence:function(){ return node&&node._pk; }};
})();

window.SUM = SUM;   // the bars hook and the boot mount both reach it this way
