/* ===========================================================================
   "Read this view" -- one summary component for all four tabs.

   The design constraint that shapes everything here: the model must never see a
   number without its error bar. That is why there is no free-text question box
   and no chat. Each view builds a typed evidence packet from what is actually on
   screen, the packet is rendered as a table the reader can open, and the same
   object is what gets posted. If the prose says something the table does not
   support, that is visible in one click rather than plausible-sounding forever.

   The component is a single node that moves into whichever panel is open, so
   there is one state machine and one set of ids rather than four of each.
   =========================================================================== */
var SUM = (function(){
  "use strict";
  var node = null, ctl = null, timer = null, current = null;

  /* ---------------------------------------------------------- packet builders
     One per view. Each returns {view, title, sub, note, cols, rows, context}.
     cols/rows are what the audit table renders AND what the model receives --
     the same array, not two constructions of it, so they cannot disagree. */
  var BUILD = {
    "p-stretch": function(){
      var pk = (typeof currentPacket === "function") ? currentPacket() : null;
      if(!pk) return null;
      var avail = pk.metrics.filter(function(m){ return m.available; });
      return {
        view:"stretch",
        title:"Scouting profile",
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
        context:{packet:pk}
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
             "<b>held</b> is out of sample: the share of the move still present in the following "+
             "window, computed after the fact. The model is told to treat an unconfirmed row as a "+
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
                  held:o.held===null?"no next":Math.round(100*o.held)+"%"};
        }),
        context:{filters:f, matched:v.rows.length, total:v.total,
                 testable:v.testable, confirmed:v.confirmed,
                 season:v.season, kind:v.kind}
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
                 caveat:"Coefficients were fit on 2023-2025 and evaluated once on 2026; 2026 is "+
                        "no longer a clean holdout."}
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
  };

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
    '<div class="sum-body" id="sum-body"></div>'+
    '<details class="ev" id="sum-evwrap">'+
      '<summary>Show the evidence the model is given <span id="sum-evn"></span></summary>'+
      '<div class="inner"><p class="ev-note" id="sum-evnote"></p><div class="tw" id="sum-ev"></div></div>'+
    '</details>'+
    '<div class="guard">'+
      '<b>What the system prompt forbids.</b> Calling a <code>noise</code> verdict a change &middot; '+
      '&ldquo;due for regression&rdquo; from a wOBA&minus;xwOBA gap &middot; treating sweet-spot% '+
      'as evidence &middot; any injury, mechanical or psychological explanation &middot; '+
      '&ldquo;small sample size&rdquo; as a hedge instead of the actual reliability &middot; '+
      'percentile language about anything under 0.3 reliability &middot; '+
      'any number that is not in the table above.'+
    '</div>';
  }

  function mount(panelId){
    if(!node){
      node=document.createElement("section");
      node.className="sum"; node.id="sum";
      node.innerHTML=shell();
      node.querySelector("#sum-go").addEventListener("click",run);
      node.querySelector("#sum-again").addEventListener("click",function(){ reset(); run(); });
    }
    var panel=document.getElementById(panelId);
    if(panel && node.parentNode!==panel) panel.appendChild(node);
    current=panelId;
    reset();
  }

  function q(sel){ return node ? node.querySelector(sel) : null; }

  function reset(){
    if(!node) return;
    if(timer){ clearTimeout(timer); timer=null; }
    if(ctl){ ctl.abort(); ctl=null; }
    var pk=null;
    try{ pk=BUILD[current] && BUILD[current](); }
    catch(e){ pk=null; if(window.console) console.warn("summary: "+current+" builder threw", e); }
    node._pk=pk;
    q("#sum-title").textContent = pk ? pk.title : "Read this view";
    q("#sum-sub").textContent   = pk ? pk.sub : "—";
    q("#sum-again").hidden=true;
    q("#sum-go").disabled=!pk;
    q("#sum-evwrap").hidden=!pk;
    if(pk){
      q("#sum-evn").textContent="("+pk.rows.length+" row"+(pk.rows.length===1?"":"s")+")";
      q("#sum-evnote").innerHTML=pk.note;
      q("#sum-ev").innerHTML=table(pk);
      q("#sum-body").innerHTML='<p class="sum-idle">'+IDLE+'</p>';
    } else {
      q("#sum-evn").textContent="";
      q("#sum-ev").innerHTML="";          // never leave the last view's evidence up
      q("#sum-body").innerHTML='<p class="sum-idle">Nothing to summarize yet — '+
        'widen the filters or pick a player.</p>';
    }
  }

  function run(){
    var pk=node && node._pk; if(!pk) return;
    q("#sum-go").disabled=true;
    var reduce=window.matchMedia&&window.matchMedia("(prefers-reduced-motion:reduce)").matches;
    var steps=["building the evidence packet …",
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
    send(pk).then(function(j){
      draw(j, ((window.performance&&performance.now)?performance.now():Date.now())-t0);
    }).catch(function(e){
      if(e && e.name==="AbortError") return;
      q("#sum-body").innerHTML='<p class="sum-idle"><b>The summary call failed.</b> '+
        esc(e.message||e)+'</p>';
      q("#sum-go").disabled=false;
    });
  }

  function draw(j, ms){
    var paras=(j.summary||"").trim().split(/\n{2,}/);
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
    q("#sum-body").innerHTML='<div class="prose">'+
      paras.map(function(p){ return '<p>'+esc(p)+'</p>'; }).join("")+'</div>'+
      '<div class="meter">'+bits.join("")+'</div>';
    q("#sum-again").hidden=false;
    q("#sum-go").disabled=false;
  }

  document.addEventListener("tabshow", function(e){ mount(e.detail.panel); });
  return {mount:mount, reset:reset, build:BUILD, packet:function(){ return node&&node._pk; }};
})();

window.SUM = SUM;   // the bars hook and the boot mount both reach it this way
