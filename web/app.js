/* ===========================================================================
   Statcast Reality Check -- client.
   Data arrives as per-(type, season) shards fetched on demand. The artifact
   version inlined all four seasons of both player types: 1.9 MB gzipped before
   the first pixel. Here the default view costs 187 KB and the rest never loads
   unless you ask for it.
   ========================================================================= */

(function(){
var $=function(s){return document.querySelector(s);};
var MON={"03":"Mar","04":"Apr","05":"May","06":"Jun","07":"Jul","08":"Aug","09":"Sep","10":"Oct"};
function lbl(b){var m=MON[b.slice(5,7)];return b.slice(8)==="A"?m+" 1":m+" 16";}
function lblEnd(b){var m=MON[b.slice(5,7)];return b.slice(8)==="A"?m+" 15":m+" 30";}
function sh(b){return MON[b.slice(5,7)]+" "+(b.slice(8)==="A"?"1":"16");}

/* Inline definitions for jargon that appears in table headers and chips
   without room to explain itself. A tap/click toggles it (works without
   hover, e.g. on touch or via keyboard); one delegated listener handles every
   instance because tables get replaced wholesale on every render, so binding
   per-element would mean rebinding on every filter change. */
function term(label, def){
  return '<button type="button" class="term">'+label+
    '<span class="tip" role="tooltip">'+def+'</span></button>';
}
function placeTip(t){
  var tip=t.querySelector(".tip"); if(!tip) return;
  var r=t.getBoundingClientRect(), w=Math.min(240, window.innerWidth-16);
  tip.style.left=Math.max(8, Math.min(r.left, window.innerWidth-w-8))+"px";
  tip.style.top=(r.bottom+6)+"px";
}
function closeTips(){
  document.querySelectorAll(".term.open").forEach(function(el){ el.classList.remove("open"); });
}
document.addEventListener("mouseover", function(e){
  var t=e.target.closest && e.target.closest(".term"); if(t) placeTip(t);
});
document.addEventListener("focusin", function(e){
  var t=e.target.closest && e.target.closest(".term"); if(t) placeTip(t);
});
document.addEventListener("click", function(e){
  var t = e.target.closest && e.target.closest(".term");
  document.querySelectorAll(".term.open").forEach(function(el){
    if(el!==t) el.classList.remove("open");
  });
  if(t){ placeTip(t); t.classList.toggle("open"); e.stopPropagation(); }
});
document.addEventListener("keydown", function(e){ if(e.key==="Escape") closeTips(); });
// a fixed popover would otherwise float in place while its term scrolls away
window.addEventListener("scroll", closeTips, {passive:true});

var DEF_REL="The share of this ranking that comes from real differences between players, not "+
    "the luck of which pitches landed in this window.",
  DEF_Z="Could sampling noise alone explain this change? Divided by the standard error two "+
    "windows this size would produce on their own.",
  DEF_SD="How big the change is, in units of how much players differ from each other — "+
    "independent of whether z clears the noise bar.",
  DEF_HELD="The share of this move still present over the following 60 days, checked after the "+
    "fact -- the same follow-up whatever the window length. A track record, not a promise.",
  DEF_CARRY="The fraction of a player's gap from his own baseline that has historically "+
    "survived into the next month.",
  DEF_N0="The reliability actually measured, at a half-season sample. Everything else in this "+
    "row is that number projected to a different sample size.";

var PCT=function(v){return (100*v).toFixed(1)+"%";},
    D3=function(v){return v.toFixed(3).replace(/^(-?)0\./,"$1.");},
    D1=function(v){return v.toFixed(1);},
    D2=function(v){return v.toFixed(2);},
    D0=function(v){return v.toFixed(0);};

// k label | n numerator | d denominator | f formatter | hi higher-is-better | g group | u unit
var METRICS={bat:[
 {k:"bat speed",n:"sbs",d:"nbs",f:D1,hi:1,g:"What he does with the bat",u:"mph",s:1},
 {k:"swing length",n:"ssl",d:"nbs",f:D2,hi:1,g:"What he does with the bat",u:"ft",s:1},
 {k:"attack angle",n:"saa",d:"naa",f:D1,hi:1,g:"What he does with the bat",u:"deg",s:1},
 {k:"attack direction",n:"sad",d:"naa",f:D1,hi:1,g:"What he does with the bat",u:"deg",s:1},
 {k:"K%",n:"k",d:"pa",f:PCT,hi:0,g:"Plate discipline",u:"pp",s:0.01},
 {k:"BB%",n:"bb",d:"pa",f:PCT,hi:1,g:"Plate discipline",u:"pp",s:0.01},
 {k:"whiff%",n:"whf",d:"sw",f:PCT,hi:0,g:"Plate discipline",u:"pp",s:0.01},
 {k:"chase%",n:"ozsw",d:"oz",f:PCT,hi:0,g:"Plate discipline",u:"pp",s:0.01},
 {k:"exit velo",n:"sev",d:"nev",f:D1,hi:1,g:"Contact quality",u:"mph",s:1},
 {k:"hard-hit%",n:"hh",d:"nev",f:PCT,hi:1,g:"Contact quality",u:"pp",s:0.01},
 {k:"barrel%",n:"brl",d:"nev",f:PCT,hi:1,g:"Contact quality",u:"pp",s:0.01},
 {k:"launch angle",n:"sla",d:"nev",f:D1,hi:1,g:"Contact quality",u:"deg",s:1},
 {k:"sweet-spot%",n:"sweet",d:"nev",f:PCT,hi:1,g:"Contact quality",u:"pp",s:0.01},
 {k:"ground-ball%",n:"gb",d:"nbb",f:PCT,hi:0,g:"Contact quality",u:"pp",s:0.01},
 {k:"xwOBA",n:"xn",d:"pa",f:D3,hi:1,g:"Results",u:"pts",s:1},
 {k:"wOBA",n:"wn",d:"pa",f:D3,hi:1,g:"Results",u:"pts",s:1}],
pit:[
 {k:"fastball velo",n:"sv",d:"nv",f:D1,hi:1,g:"The delivery",u:"mph",s:1},
 {k:"spin rate",n:"ssp",d:"nsp",f:D0,hi:1,g:"The delivery",u:"rpm",s:1},
 {k:"extension",n:"sex",d:"nex",f:D2,hi:1,g:"The delivery",u:"ft",s:1},
 {k:"arm angle",n:"saa",d:"naa",f:D1,hi:1,g:"The delivery",u:"deg",s:1},
 {k:"K%",n:"k",d:"bf",f:PCT,hi:1,g:"Command and swing-and-miss",u:"pp",s:0.01},
 {k:"BB%",n:"bb",d:"bf",f:PCT,hi:0,g:"Command and swing-and-miss",u:"pp",s:0.01},
 {k:"whiff%",n:"whf",d:"sw",f:PCT,hi:1,g:"Command and swing-and-miss",u:"pp",s:0.01},
 {k:"zone%",n:"iz",d:"zt",f:PCT,hi:1,g:"Command and swing-and-miss",u:"pp",s:0.01},
 {k:"chase induced%",n:"ozsw",d:"oz",f:PCT,hi:1,g:"Command and swing-and-miss",u:"pp",s:0.01},
 {k:"edge%",n:"edge",d:"loct",f:PCT,hi:1,g:"Command and swing-and-miss",u:"pp",s:0.01},
 {k:"exit velo allowed",n:"sev",d:"nev",f:D1,hi:0,g:"Contact allowed",u:"mph",s:1},
 {k:"hard-hit% allowed",n:"hh",d:"nev",f:PCT,hi:0,g:"Contact allowed",u:"pp",s:0.01},
 {k:"ground-ball%",n:"gb",d:"nbb",f:PCT,hi:1,g:"Contact allowed",u:"pp",s:0.01},
 {k:"xwOBA against",n:"xn",d:"bf",f:D3,hi:0,g:"Results",u:"pts",s:1},
 {k:"wOBA against",n:"wn",d:"bf",f:D3,hi:0,g:"Results",u:"pts",s:1}]};

// the input battery used for change tracking: things the player does, not things done to him
var INPUTS={bat:["bat speed","swing length","attack angle","whiff%","chase%","exit velo",
                 "hard-hit%","K%","BB%"],
            pit:["fastball velo","spin rate","extension","arm angle","whiff%","zone%",
                 "chase induced%","K%","BB%"]};
var PAKEY={bat:"pa",pit:"bf"}, PANAME={bat:"PA",pit:"batters faced"},
    PALONG={bat:"plate appearances",pit:"batters faced"};

// Carry model: OLS on [1, w, w_base, x, x_base], fit 2023-2025, scored once on 2026.
var CARRY={
 bat:{beta:[0.15063,-0.01826,-0.03408,0.22798,0.36089],r2:0.0335,ceil:0.2854,ntr:3884,nte:1044,
      naive:0.0038},
 pit:{beta:[0.16834, 0.01749, 0.06748,0.16928,0.21840],r2:0.0512,ceil:0.3537,ntr:2910,nte:893,
      naive:0.0292}};


var kindS=$("#kind"), yrS=$("#yr");


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

function setKind(){
  K=kindS.value;
  return loadShard(K, +(yrS.value||YEARS[0])).then(function(d){
  F={}; d.fields.forEach(function(f,i){F[f]=i;});
  BL=d.blocks; REL=d.rel; PK=PAKEY[K]; MET=METRICS[K];
  LEAGUE=null;
  $("#panels-boot").hidden=true;
  setYear();
  });
}
function setYear(){
  var y=+yrS.value, d=ALL[shardKey(K,y)];
  if(!d){ $("#panels-boot").hidden=false;
    return loadShard(K,y).then(function(){ $("#panels-boot").hidden=true; setYear(); }); }
  F={}; d.fields.forEach(function(f,i){F[f]=i;});
  BL=d.blocks; REL=d.rel; PK=PAKEY[K]; MET=METRICS[K]; YR=y;
  ROWS=d.rows.slice();
  var opts=ROWS.map(function(r){
    return '<option value="'+r.id+'">'+r.n+'  ('+r.t+' '+PANAME[K]+')</option>';}).join("");
  $("#who").innerHTML=opts; $("#c-who").innerHTML=opts; $("#pc-who").innerHTML=opts;
  var yb=yearBlocks(y);
  $("#from").innerHTML=yb.map(function(i){return '<option value="'+i+'">'+lbl(BL[i])+'</option>';}).join("");
  $("#to").innerHTML=yb.map(function(i){return '<option value="'+i+'">'+lblEnd(BL[i])+'</option>';}).join("");
  $("#from").value=yb[Math.max(0,yb.length-4)]; $("#to").value=yb[yb.length-1];
  // Open on a player the stored-profile fallback can actually write about, so the
  // first thing a visitor without a key clicks does something.
  var pref=K==="bat"?"608324":"656302";
  if(ROWS.some(function(r){return String(r.id)===pref;})){ $("#who").value=pref; $("#pc-who").value=pref; }
  if(HQ.id && ROWS.some(function(r){return String(r.id)===HQ.id;})){ $("#pc-who").value=HQ.id; HQ.id=null; }
  paintGlobalBar(TABS[active][1].slice(1));
  $("#globalnote").textContent=ROWS.length+" qualified "+(K==="bat"?"hitters":"pitchers")+
    " in "+y+" · "+yb.length+" half-month blocks";
  // The first paint goes through show(), so the question line, the hash and any deep-link
  // scroll all happen. After that, a Type or Season change only re-renders the open tab.
  if(!setYear.done){ setYear.done=true; show(active, SCROLL0); if(window.SUM) SUM.reset(); }
  else renderAll();
}
function yearBlocks(y){ var out=[],i; for(i=0;i<BL.length;i++) out.push(i); return out; }
function sum(r,i0,i1){
  var out=new Array(BL.length&&ALL[shardKey(K,YR)].fields.length).fill(0), i, j, v;
  for(i=i0;i<=i1;i++){ v=r.b[BL[i]]; if(!v) continue;
    for(j=0;j<out.length;j++) out[j]+=v[j]; }
  return out;
}
function sumList(r,idxs){
  var out=new Array(ALL[shardKey(K,YR)].fields.length).fill(0), j, v;
  idxs.forEach(function(i){ v=r.b[BL[i]]; if(!v) return;
    for(j=0;j<out.length;j++) out[j]+=v[j]; });
  return out;
}
function relAt(metric,n){
  var r=REL[metric]; if(!r||n<=0) return 0;
  var k=n/r.n0, p=r.sb;
  return Math.max(0,Math.min(1,k*p/(1+(k-1)*p)));
}
function pctOf(a,v){var c=0,i;for(i=0;i<a.length;i++) if(a[i]<v)c++; return 100*c/a.length;}
function sd(a){
  if(a.length<3) return 0;
  var m=0,i; for(i=0;i<a.length;i++) m+=a[i]; m/=a.length;
  var s=0; for(i=0;i<a.length;i++) s+=(a[i]-m)*(a[i]-m);
  return Math.sqrt(s/a.length);
}
function getM(lab){ for(var i=0;i<MET.length;i++) if(MET[i].k===lab) return MET[i]; return null; }

/* ===================== TAB 1: percentiles ===================== */
/* One percentile row: solid bar = shrunk percentile; hatched band out to the raw one when
   shrinking moved it 5+ points (D36). raw and adj are already direction-corrected. */
/* Colour carries meaning at a glance. heat(): red = the better way, blue = the worse way (the
   site's convention), with the fill strengthening as the evidence does. right/wrong colours are a
   separate pair, used only where something is being judged correct (D67). */
function heat(better, strength){
  var a=Math.round(8+34*Math.max(0,Math.min(1,strength)));
  return ' style="background:color-mix(in srgb,var('+(better?"--hot":"--cold")+') '+a+'%,transparent)"';
}
function relStyle(rel){
  var a=Math.round(6+44*Math.max(0,Math.min(1,rel)));
  return ' style="background:color-mix(in srgb,var(--ac) '+a+'%,transparent);color:'+
    (rel>=0.7?"var(--ink)":"var(--ink2)")+'"';
}
function barRow(name, valueStr, rel, raw, adj){
  var hot=adj>=50, col=hot?"var(--hot)":"var(--cold)", wA=Math.abs(adj-50),
      wR=Math.abs(raw-50), edge=hot?"left":"right", shows=Math.abs(raw-adj)>=5;
  var band=shows?'<span class="noise" style="'+edge+':calc(50% + '+wA+'%);width:'+(wR-wA)+
    '%;color:'+col+'"></span>':'';
  return '<div class="row"><span class="nm">'+name+' <span class="relchip"'+relStyle(rel)+' title="'+
    relTitle(name, rel).replace(/"/g,"&quot;")+'">'+
    Math.round(100*rel)+'% real</span></span><span class="val">'+valueStr+
    '</span><span class="bar"><span class="fill" style="'+edge+':50%;width:'+wA+
    '%;background:'+col+'"></span>'+band+'<span class="mk"></span></span>'+
    '<span class="pct" style="color:'+col+'">'+Math.round(adj)+
    (shows?'<span class="rawpct">was '+Math.round(raw)+'</span>':'')+'</span></div>';
}

function renderStretch(){
  loadRelCI(K);
  var i0=+$("#from").value, i1=+$("#to").value;
  if(i1<i0){ i1=i0; $("#to").value=i1; }
  var me=ROWS.find(function(r){return r.id==$("#who").value;});
  if(!me) return;
  var mine=sum(me,i0,i1), myN=mine[F[PK]];
  $("#h-name").textContent=me.n;
  $("#h-span").textContent=lbl(BL[i0])+" – "+lblEnd(BL[i1])+" "+yrS.value;
  $("#h-pa").textContent=myN.toFixed(0)+" "+PALONG[K];
  var peers=ROWS.map(function(r){return {r:r,v:sum(r,i0,i1)};})
                .filter(function(x){return x.v[F[PK]]>=20;});
  var rRes=relAt(K==="bat"?"wOBA":"wOBA against",myN),
      rBody=relAt(K==="bat"?"bat speed":"fastball velo",myN);
  // The two ends of the trust range at this sample: the outcome stat (noisiest) and a
  // physical measurement (steadiest). Every other row falls somewhere between.
  var bat=K==="bat";
  $("#warn").innerHTML = myN<1 ? "<b>No appearances in this span.</b>" :
    "Over these <b>"+myN.toFixed(0)+" "+PALONG[K]+"</b>, "+(bat?"his":"the")+
    " outcome stats like "+(bat?"wOBA":"wOBA allowed")+" are only about <b>"+
    Math.round(100*rRes)+"% real</b> &mdash; the rest is luck. "+
    (bat?"Swing measurements like bat speed":"Pitch measurements like fastball velocity")+
    " are about <b>"+Math.round(100*rBody)+"% real</b>, so lean on those. Percentiles compare "+
    (bat?"him":"this pitcher")+" with the "+peers.length+" other "+(bat?"hitters":"pitchers")+
    " who played over the same dates.";

  var html='<div class="axis"><span>metric</span><span>value</span>'+
    '<span class="ax"><span>&larr; worse than average</span><span>average</span>'+
    '<span>better &rarr;</span></span><span>percentile</span></div>', groups=[];
  MET.forEach(function(m){ if(groups.indexOf(m.g)<0) groups.push(m.g); });
  groups.forEach(function(g){
    html+='<div class="grp"><div class="gh"><span>'+g+'</span><span></span></div>';
    MET.filter(function(m){return m.g===g;}).forEach(function(m){
      var dv=mine[F[m.d]];
      if(!dv){ html+='<div class="row"><span class="nm">'+m.k+
        '</span><span class="val">&mdash;</span><span class="bar"></span><span class="pct">&mdash;</span></div>';
        return; }
      var v=mine[F[m.n]]/dv;
      var pool=peers.filter(function(x){return x.v[F[m.d]]>0;})
                    .map(function(x){return x.v[F[m.n]]/x.v[F[m.d]];});
      var raw=pctOf(pool,v); if(!m.hi) raw=100-raw;
      var rel=relAt(m.k,myN), adj=50+rel*(raw-50);
      html+=barRow(m.k, m.f(v), rel, raw, adj);
    });
    html+='</div>';
  });
  $("#bars").innerHTML=html;
  if(window.SUM) SUM.reset();
  renderComps(me,mine,myN,i0,i1);
}

function renderComps(me,mine,myN,i0,i1){
  var DIMS=MET.filter(function(m){return m.g!=="Results";});
  var len=i1-i0+1, cands=[], anyMode=$("#mode").value==="any";
  var pool=ROWS;
  pool.forEach(function(r){
    var starts;
    if(anyMode){ starts=[]; BL.forEach(function(b,a){ if(a+len-1<BL.length) starts.push(a); }); }
    else starts=[i0];
    starts.forEach(function(a){
      if(r.id===me.id && (anyMode || (r.y===me.y && a===i0))) return;
      var v=sum(r,a,a+len-1);
      if(v[F[PK]] < Math.max(15,myN*0.5)) return;
      cands.push({r:r,a:a,b:a+len-1,v:v});
    });
  });
  var scale=DIMS.map(function(m){
    var xs=cands.map(function(c){return c.v[F[m.d]]>0?c.v[F[m.n]]/c.v[F[m.d]]:NaN;})
                .filter(function(x){return isFinite(x);});
    var mu=0,i; for(i=0;i<xs.length;i++) mu+=xs[i]; mu/=(xs.length||1);
    return {mu:mu, sd:sd(xs)||1, w:Math.sqrt(relAt(m.k,myN)||0.02)};
  });
  var myz=DIMS.map(function(m,k){
    var dv=mine[F[m.d]];
    return dv?((mine[F[m.n]]/dv)-scale[k].mu)/scale[k].sd:null; });
  var WT=0; DIMS.forEach(function(m,k){ if(myz[k]!==null) WT+=scale[k].w; });
  var scored=[], thin=0;
  cands.forEach(function(c){
    var s=0, wt=0;
    DIMS.forEach(function(m,k){
      var dv=c.v[F[m.d]]; if(!dv||myz[k]===null) return;
      var z=((c.v[F[m.n]]/dv)-scale[k].mu)/scale[k].sd;
      s+=scale[k].w*(z-myz[k])*(z-myz[k]); wt+=scale[k].w; });
    if(wt<0.75*WT){ thin++; return; }
    c.d=Math.sqrt(s/wt); scored.push(c);
  });
  scored.sort(function(a,b){return a.d-b.d;});
  var top=scored.slice(0,6), med=scored.length?scored[Math.floor(scored.length/2)].d:1;
  $("#cmp-h").textContent="Most similar stretches — "+
    (anyMode?"anywhere, 2023–2026":"same dates, "+yrS.value);
  $("#cmp-sub").textContent=scored.length.toLocaleString()+" candidates";
  $("#cmp-note").innerHTML= top.length ?
    "Players whose stretch looked most like this one, matched on the numbers that are most "+
    "trustworthy at this sample size (over a short window, mostly the swing). The best match is <b>"+
    (med/top[0].d).toFixed(1)+"× closer than a typical candidate</b> — the higher that number, "+
    "the more meaningful the list."+
    (thin?" "+thin.toLocaleString()+" candidates were left out for missing too much tracking "+
     "data.":"") : "Not enough comparable stretches.";
  $("#comps").innerHTML=top.map(function(c){
    var n=c.v[F[PK]];
    var body=K==="bat"?(c.v[F.nbs]?"bat speed "+(c.v[F.sbs]/c.v[F.nbs]).toFixed(1):"")
                      :(c.v[F.nv]?"velo "+(c.v[F.sv]/c.v[F.nv]).toFixed(1):"");
    var wo=n?D3(c.v[F.wn]/n):"—";
    return '<div class="cc"><span class="t">'+c.r.n+'</span><span class="w">'+
      lbl(BL[c.a])+' – '+lblEnd(BL[c.b])+' '+c.r.y+'  ·  '+n.toFixed(0)+' '+PANAME[K]+
      '</span><span class="s">'+(body?body+'  ·  ':'')+
      (K==="bat"?"wOBA ":"wOBA agst ")+wo+'</span><span class="w">distance '+
      c.d.toFixed(3)+'</span></div>';}).join("");
}

/* ===================== TAB 2: change log ===================== */
/* "held" is judged over one fixed follow-up for every window length -- the next 60 days, four
   half-month blocks -- the same horizon the streak study uses (D70). Judging a move against the
   next window of its own length compared one noisy sample with another: at short lengths the
   follow-up's own noise decided most single-row verdicts. */
var HELD_BLOCKS=4;
function changeSet(){
  var W=+$("#c-win").value, ZMIN=+$("#c-z").value, y=+yrS.value, yb=yearBlocks(y);
  var minNow=W*25, minBase=Math.max(60,W*40);
  var out=[], sdCache={};
  for(var s=2;s+W<=yb.length;s++){
    var now=yb.slice(s,s+W), base=yb.slice(0,s), nxt=yb.slice(s+W,s+W+HELD_BLOCKS);
    var key=s+"|"+W;
    var sums=ROWS.map(function(r){
      return {r:r, now:sumList(r,now), base:sumList(r,base),
              nxt:nxt.length===HELD_BLOCKS?sumList(r,nxt):null}; });
    INPUTS[K].forEach(function(lab){
      var m=getM(lab); if(!m) return;
      var ck=key+"|"+lab;
      if(!(ck in sdCache)){
        sdCache[ck]=sd(sums.filter(function(x){return x.now[F[m.d]]>=20;})
                           .map(function(x){return x.now[F[m.n]]/x.now[F[m.d]];}));
      }
      var SD=sdCache[ck]; if(!SD) return;
      sums.forEach(function(x){
        var dn=x.now[F[m.d]], db=x.base[F[m.d]];
        var nn=x.now[F[PK]], nb=x.base[F[PK]];
        if(dn<W*10||db<W*20||nn<minNow||nb<minBase) return;
        var v=x.now[F[m.n]]/dn, b0=x.base[F[m.n]]/db;
        var rho=relAt(lab,nn), vt=SD*SD*rho;
        var s1=Math.sqrt(Math.max(1e-12,SD*SD-vt));
        var s2=Math.sqrt(Math.max(1e-12,(SD*SD-vt)*(nn/nb)));
        var se=Math.sqrt(s1*s1+s2*s2), z=(v-b0)/se;
        if(Math.abs(z)<ZMIN) return;
        var held=null;
        if(x.nxt && x.nxt[F[m.d]]>=HELD_BLOCKS*10 && Math.abs(v-b0)>1e-9)
          held=(x.nxt[F[m.n]]/x.nxt[F[m.d]]-b0)/(v-b0);
        out.push({p:x.r.n, id:x.r.id, m:lab, f:m, a:now[0], b:now[now.length-1],
                  v:v, base:b0, z:z, sdu:(v-b0)/SD, rel:rho, held:held, n:nn,
                  // "improved" is direction-aware: a FALLING chase rate is an
                  // improvement, a falling bat speed is not. Without m.hi the
                  // direction filter would be meaningless for half the metrics.
                  imp: ((v-b0) > 0) === !!m.hi});
      });
    });
  }
  out.sort(function(a,b){return Math.abs(b.z)-Math.abs(a.z);});
  return out;
}
function moveTable(rows,limit,showPlayer){
  if(!rows.length) return '<table><tbody><tr><td class="l">Nothing past this threshold.</td></tr></tbody></table>';
  var h='<table><thead><tr>'+(showPlayer?'<th class="l">player</th>':'')+
    '<th class="l">metric</th><th class="l">window</th><th>prior</th><th>now</th>'+
    '<th>&Delta;</th><th>'+term("z",DEF_Z)+'</th><th>'+term("sd",DEF_SD)+'</th><th>'+
    term("% real",DEF_REL)+'</th><th>'+term("held",DEF_HELD)+'</th></tr></thead><tbody>';
  rows.slice(0,limit).forEach(function(o){
    // red = moved the better way, blue = the worse way, matching How he ranks (METRICS[].hi)
    var cls=((o.z>0)===!!o.f.hi)?"up":"dn";
    h+='<tr>'+(showPlayer?'<td class="l">'+o.p+'</td>':'')+
      '<td class="l">'+o.m+'</td><td class="l">'+sh(BL[o.a])+'–'+sh(BL[o.b])+'</td>'+
      '<td>'+o.f.f(o.base)+'</td><td>'+o.f.f(o.v)+'</td>'+
      '<td class="'+cls+'"'+heat(cls==="up",(Math.abs(o.z)-2)/3)+'>'+(o.v-o.base>0?"+":"")+o.f.f(o.v-o.base)+'</td>'+
      '<td class="'+cls+'"'+heat(cls==="up",(Math.abs(o.z)-2)/3)+'>'+o.z.toFixed(1)+'</td>'+
      '<td>'+(o.sdu>0?"+":"")+o.sdu.toFixed(1)+'</td>'+
      '<td>'+Math.round(100*o.rel)+'</td>'+
      '<td><span class="chip '+(o.held>=0.5?"right":o.held<0?"wrong":"part")+'">'+Math.round(100*o.held)+'%</span>'+
      '</td></tr>';
  });
  return h+'</tbody></table>';
}
// `over` lets one caller ignore a filter without touching the control: the Player tab shows
// every change a player made, whatever metric the league board is filtered to.
function applyFilters(rows, over){
  over=over||{};
  var met=("metric" in over)?over.metric:$("#c-metric").value, dir=$("#c-dir").value,
      minN=+$("#c-n").value, conf=$("#c-conf").checked, sort=$("#c-sort").value;
  var out=rows.filter(function(o){
    if(met!=="all" && o.m!==met) return false;
    if(dir==="up" && !o.imp) return false;
    if(dir==="down" && o.imp) return false;
    if(o.n < minN) return false;
    if(conf && !(o.held!==null && o.held>=0.5)) return false;
    return true;
  });
  var cmp={
    z:      function(a,c){ return Math.abs(c.z)-Math.abs(a.z); },
    sd:     function(a,c){ return Math.abs(c.sdu)-Math.abs(a.sdu); },
    // rows with no following window sort last rather than pretending to be zero
    held:   function(a,c){ return (c.held===null?-9:c.held)-(a.held===null?-9:a.held); },
    player: function(a,c){ return a.p.localeCompare(c.p) || Math.abs(c.z)-Math.abs(a.z); },
    date:   function(a,c){ return c.a-a.a || Math.abs(c.z)-Math.abs(a.z); }
  }[sort];
  out.sort(cmp);
  return out;
}

function renderChanges(){
  var raw=changeSet(), pid=$("#c-who").value;
  var ms=$("#c-metric");
  if(ms.dataset.kind!==K){
    var keepC=ms.value;
    ms.innerHTML='<option value="all">all metrics</option>'+
      INPUTS[K].map(function(l){return '<option value="'+l+'">'+l+'</option>';}).join("");
    if([].some.call(ms.options,function(o){return o.value===keepC;})) ms.value=keepC;
    ms.dataset.kind=K;
  }
  // Moves from the latest window have no following window yet, so "held" can't be checked.
  // They're kept out of both tables and counted in a footnote under each instead.
  var matched=applyFilters(raw);
  var all=matched.filter(function(o){return o.held!==null;});
  var isMe=function(o){return String(o.id)===String(pid);};
  // His own table is every change he made, whatever the league board is filtered to.
  var mineAll=applyFilters(raw,{metric:"all"});
  var mine=mineAll.filter(function(o){return isMe(o)&&o.held!==null;});
  var pendAll=matched.length-all.length,
      pendMine=mineAll.filter(function(o){return isMe(o)&&o.held===null;}).length;
  $("#c-hits").textContent = all.length.toLocaleString()+" of "+raw.length.toLocaleString()+" moves";
  $("#c-player-foot").innerHTML=pendingNote(pendMine);
  $("#c-board-foot").innerHTML=pendingNote(pendAll);
  var me=ROWS.find(function(r){return String(r.id)===String(pid);});
  $("#c-title").textContent=(me?me.n:"—")+" — what moved against his earlier season";
  var filtered = raw.length !== all.length;
  $("#c-lede").innerHTML= mine.length ?
    "Each row compares a window against <b>everything earlier in the season</b>, never against the "+
    "rest of it — a baseline that contains the future is a description, not a forecast." :
    ("No move matches these filters." + (filtered
      ? " Widen them, or drop the threshold — "+raw.length.toLocaleString()+
        " moves clear |z| alone."
      : " That is the common case and it is the useful answer: most fortnights are the same "+
        "player."));
  $("#c-player").innerHTML=moveTable(mine,20,false);
  var testable=all;
  var confirmed=all.filter(function(o){return o.held>=0.5;});
  var rawT=raw.filter(function(o){return o.held!==null;});
  var rawC=rawT.filter(function(o){return o.held>=0.5;});
  var lead="<b>"+all.length.toLocaleString()+"</b> checkable moves match these filters in "+
    yrS.value+" across "+ROWS.length+" "+(K==="bat"?"hitters":"pitchers")+". ";
  // With "confirmed only" on, the filter selects on held >= 0.5, so reporting the
  // hold rate of the survivors is circular -- it is 100% by construction.
  $("#c-boardnote").innerHTML = lead + ($("#c-conf").checked
    ? "You are looking at the moves that <b>already held</b> at least half of themselves over the "+
      "following 60 days, so the hold rate here is 100% by construction and tells you nothing. "+
      "Across the "+raw.length.toLocaleString()+" moves before this filter, "+
      Math.round(100*rawC.length/Math.max(1,rawT.length))+"% of the testable ones held."
    : "Of these, <b>"+
      (testable.length?Math.round(100*confirmed.length/testable.length):0)+
      "% held at least half the move.</b> A coin would hold about half of nothing; this is the "+
      "out-of-sample check that makes the column worth reading.");
  $("#c-board").innerHTML=moveTable(all,40,true);
  VIEWSTATE.changesMine={player:me?me.n:"", rows:mine, pending:pendMine,
    win:$("#c-win").selectedOptions[0].text, z:$("#c-z").value, season:yrS.value, kind:K};
  VIEWSTATE.changes={rows:all, shown:Math.min(all.length,40), total:raw.length,
    testable:testable.length, confirmed:confirmed.length, too_recent_hidden:pendAll,
    filters:{metric:$("#c-metric").value, dir:$("#c-dir").value, minN:+$("#c-n").value,
             conf:$("#c-conf").checked, sort:$("#c-sort").value,
             win:$("#c-win").selectedOptions[0].text, z:$("#c-z").value},
    season:yrS.value, kind:K};
}

function pendingNote(n){
  if(!n) return "";
  return "* "+n.toLocaleString()+(n===1?" more move is":" more moves are")+" hidden because "+
    (n===1?"it comes":"they come")+" from the last 60 days of data: the 60-day follow-up that "+
    "decides whether a move held hasn&rsquo;t been played yet. They are also the newest signal, so "+
    "check back as the season fills in.";
}

/* ===================== TAB 3: what carries ===================== */
function renderCarry(){
  var y=+yrS.value, yb=yearBlocks(y);
  if(yb.length<4){ $("#k-board").innerHTML=""; return; }
  /* Any 30-day window with at least a month before it can be scored, not only the latest one.
     A past window also has a following month, so the board can show what happened next and
     whether the model's expectation beat "the streak just continues". */
  var ks=$("#k-asof"), sig=K+"|"+y+"|"+yb.length;
  if(ks.dataset.sig!==sig){
    ks.innerHTML=yb.slice(3).map(function(bi,j){
      var e=j+3; return '<option value="'+e+'">'+lbl(BL[yb[e-1]])+"\u2013"+lblEnd(BL[bi])+
        (e===yb.length-1?" (latest)":"")+'</option>'; }).reverse().join("");
    ks.value=String(yb.length-1); ks.dataset.sig=sig;
  }
  var end=+ks.value||yb.length-1;
  var now=yb.slice(end-1,end+1), base=yb.slice(0,end-1), next=yb.slice(end+1,end+3),
      scored=next.length===2, C=CARRY[K], B=C.beta;
  var board=[];
  ROWS.forEach(function(r){
    var vn=sumList(r,now), vb=sumList(r,base);
    var n=vn[F[PK]], bn=vb[F[PK]];
    if(n<50||bn<150) return;
    var w=vn[F.wn]/n, x=vn[F.xn]/n, wb=vb[F.wn]/bn, xb=vb[F.xn]/bn;
    var pred=B[0]+B[1]*w+B[2]*wb+B[3]*x+B[4]*xb;
    var gap=w-wb, act=null;
    if(scored){ var vx=sumList(r,next), nx=vx[F[PK]]; if(nx>=40) act=vx[F.wn]/nx-wb; }
    board.push({r:r,n:n,bn:bn,w:w,x:x,wb:wb,xb:xb,pred:pred,gap:gap,act:act,
                carry:Math.abs(gap)>1e-6?(pred-wb)/gap:0});
  });
  /* Sorting 230 hitters by the raw size of a 50-PA move ranks them mostly on
     their own noise: the biggest gaps are the smallest samples having the
     wildest month, which is the exact error this tab exists to warn about. The
     default is now what the model expects to SURVIVE, which is the quantity the
     page is actually about. `z` divides the gap by the error two windows of
     that size produce on their own, ranking by how surprising a move is rather
     than how large. Raw gap is still offered, and is still the one not to act on. */
  board.forEach(function(b){
    b.z = b.gap / Math.sqrt(HC_S2 * (1 / b.n + 1 / b.bn));
    b.expect = b.pred - b.wb;
  });
  var sortKey = ($("#k-sort") && $("#k-sort").value) || "expect";
  var KEYS = {expect:function(b){return Math.abs(b.expect);},
              z:     function(b){return Math.abs(b.z);},
              gap:   function(b){return Math.abs(b.gap);}};
  board.sort(function(a,b){return (KEYS[sortKey]||KEYS.expect)(b)-(KEYS[sortKey]||KEYS.expect)(a);});
  var SORTNOTE = {
    expect:"Ranked by how far from his usual level the model still expects him to be next "+
           "month \u2014 the actionable column.",
    z:     "Ranked by how far the move goes beyond what two windows of this size produce on "+
           "their own: surprise, not size.",
    gap:   "Ranked by the raw size of the move. Read with care \u2014 over ~50 "+PANAME[K]+
           " the biggest gaps are mostly the smallest samples having the wildest month, so "+
           "this ordering puts the least trustworthy rows on top."};
  if($("#k-sortnote")) $("#k-sortnote").textContent=SORTNOTE[sortKey]||"";
  VIEWSTATE.carry={board:board.slice(0,30), total:board.length, kind:K, season:y,
    span:lbl(BL[now[0]])+" to "+lblEnd(BL[now[1]]),
    model:{r2:C.r2, ceil:C.ceil, naive:C.naive, ntr:C.ntr, nte:C.nte}};
  var wo=K==="bat"?"wOBA":"wOBA allowed";
  $("#k-title").textContent="How much of each streak is expected to survive — "+
    lbl(BL[now[0]])+" to "+lblEnd(BL[now[1]])+" "+y;
  $("#k-lede").innerHTML="Every "+(K==="bat"?"hitter":"pitcher")+" with at least 50 "+PANAME[K]+
    " in this 30-day window and 150 before it. <b>vs. usual</b> is how far his "+wo+" has moved from "+
    "his own earlier-season rate, and <b>z</b> is that move divided by the error two windows of "+
    "this size produce on their own. <b>Expected next month</b> is how far from that same "+
    "usual level the model expects him to be over the next month, and <b>carry</b> is the share of "+
    "the current gap that represents &mdash; e.g. +.079 expected on a +.246 gap is 32%.";
  $("#k-tiles").innerHTML=
    tile("How well it predicts (R²)", C.r2.toFixed(4), "fit on 2023–2025, scored on 2026 — "+
         "which is no longer a clean test, so read this as optimistic")+
    tile("Best possible", C.ceil.toFixed(4), "the most any model could score, because next "+
         "month is mostly noise")+
    tile("Share captured", Math.round(100*C.r2/C.ceil)+"%", "how much of what is predictable "+
         "this model actually gets")+
    tile("Recent "+wo+" alone", C.naive.toFixed(4), "the same score using only last month's "+
         "results — "+
         (C.naive<0.01?"no better than guessing average":"barely better than guessing average"));
  var h='<table><thead><tr><th class="l">player</th><th>'+PANAME[K]+'</th><th>'+wo+
    '</th><th>x'+(K==="bat"?"wOBA":"wOBA")+'</th><th>his usual</th><th>vs. usual</th>'+
    '<th>'+term("z",DEF_Z)+'</th><th>expected next month</th>'+
    '<th>'+term("carry",DEF_CARRY)+'</th>'+(scored?'<th>what happened</th><th></th>':'')+
    '</tr></thead><tbody>';
  board.slice(0,30).forEach(function(b){
    var cls=b.gap>0?"up":"dn";
    h+='<tr><td class="l">'+b.r.n+'</td><td>'+b.n.toFixed(0)+'</td><td>'+D3(b.w)+
      '</td><td>'+D3(b.x)+'</td><td>'+D3(b.wb)+'</td>'+
      '<td class="'+cls+'"'+heat(cls==="up",Math.abs(b.z)/3)+'>'+(b.gap>0?"+":"")+D3(b.gap)+'</td>'+
      '<td>'+(b.z>0?"+":"\u2212")+Math.abs(b.z).toFixed(1)+'</td>'+
      '<td class="'+cls+'"'+heat(cls==="up",Math.abs(b.expect)/0.06)+'><b>'+(b.expect>0?"+":"")+D3(b.expect)+'</b></td>'+
      '<td>'+Math.round(100*b.carry)+'%</td>'+
      (scored?(b.act==null?'<td>&mdash;</td><td></td>':
        '<td class="'+(b.act>0?"up":"dn")+'"'+heat(b.act>0,Math.abs(b.act)/0.06)+'>'+(b.act>0?"+":"")+D3(b.act)+'</td>'+
        '<td><span class="chip '+(Math.abs(b.act-b.expect)<Math.abs(b.act-b.gap)?'right">model closer':'wrong">streak closer')+
        '</span></td>'):'')+'</tr>';
  });
  $("#k-board").innerHTML=h+'</tbody></table>';
  // the scorecard: across every qualifying player, not just the 30 shown
  var sc=board.filter(function(b){return b.act!=null;});
  var kf=$("#k-scored");
  if(kf){
    if(!scored){ kf.innerHTML=""; }
    else if(sc.length){
      var win=sc.filter(function(b){return Math.abs(b.act-b.expect)<Math.abs(b.act-b.gap);}).length,
          mm=sc.reduce(function(t,b){return t+Math.abs(b.act-b.expect);},0)/sc.length,
          ms=sc.reduce(function(t,b){return t+Math.abs(b.act-b.gap);},0)/sc.length,
          ok=win/sc.length>=0.5;
      kf.className="ocome "+(ok?"ok":"miss");
      kf.innerHTML='<p class="scope">What happened the following month &middot; '+lbl(BL[next[0]])+
        '\u2013'+lblEnd(BL[next[1]])+'</p><p class="ocome-h">'+(ok?"&#10003; ":"&#10007; ")+
        'The model was closer for '+win+' of '+sc.length+' players</p>'+
        '<p class="ocome-v">Compared with assuming each streak simply continued. Average miss: <b>'+
        D3(mm).replace(/^0/,"")+'</b> of '+wo+' for the model against <b>'+D3(ms).replace(/^0/,"")+
        '</b> for &ldquo;the streak continues&rdquo;. Players with fewer than 40 '+PANAME[K]+
        ' the next month are left out.'+(y<=2025?' <b>'+y+' is one of the seasons the model was '+
        'fitted on</b>, so this is an in-sample check.':'')+'</p>';
    } else kf.innerHTML="";
  }
}
function tile(k,v,d,warn){
  return '<div class="tile'+(warn?" warn":"")+'"><span class="k">'+k+'</span><span class="v">'+v+
    '</span><span class="d">'+d+'</span></div>';
}

/* ===================== TAB 4: planner ===================== */
var LEAGUE=null;
function leagueSD(){
  // league sd of each rate measured over HALF-seasons -- the same window the split-half
  // reliability was measured on, so the decomposition stays internally consistent.
  if(LEAGUE) return LEAGUE;
  LEAGUE={};
  var half=[],i; for(i=0;i<Math.floor(BL.length/2);i++) half.push(i);
  MET.forEach(function(m){
    var xs=[];
    ROWS.forEach(function(r){
      var tot=sumList(r,half);
      if(tot[F[m.d]]>=40) xs.push(tot[F[m.n]]/tot[F[m.d]]);
    });
    if(xs.length>50) LEAGUE[m.k]={sd:sd(xs), n:xs.length};
  });
  return LEAGUE;
}
var ZT={0.80:0.8416,0.975:1.9600,0.90:1.2816};
function nForRel(p,n0,t){ return t>=1?Infinity : n0*(t*(1-p))/(p*(1-t)); }
function nForDetect(p,n0,sd0,delta,power,baseline){
  var C=n0*(1-p)*sd0*sd0*Math.pow((ZT[0.975]+ZT[power])/Math.abs(delta),2);
  if(!baseline) return C;
  return C>=baseline?Infinity:C/(1-C/baseline);
}
function renderPlanner(){
  loadRelCI(K);
  var L=leagueSD();
  var sel=$("#pl-m");
  if(sel.dataset.kind!==K){
    var keepM=sel.value;
    sel.innerHTML=MET.filter(function(m){return REL[m.k]&&L[m.k];})
      .map(function(m){return '<option value="'+m.k+'">'+m.k+'</option>';}).join("");
    // keep the reader's metric across a type switch when both types have it (K%, whiff%...)
    if([].some.call(sel.options,function(o){return o.value===keepM;})) sel.value=keepM;
    sel.dataset.kind=K;
  }
  var m=getM(sel.value)||MET[0], r=REL[m.k];
  if(!r||!L[m.k]){ $("#pl-tiles").innerHTML=""; return; }
  var p=r.sb, n0=r.n0, sd0=L[m.k].sd, t=+$("#pl-t").value;
  var UN={pp:"percentage points",pts:"points of wOBA",mph:"mph",ft:"feet",deg:"degrees",rpm:"rpm"};
  $("#pl-unit").textContent=UN[m.u]+"  ·  league sd over a half season: "+
    (m.u==="pp"?(100*sd0).toFixed(1)+" pp":m.f(sd0)+" "+m.u);
  var delta=(+$("#pl-d").value||0)*m.s, baseline=+$("#pl-b").value||0;
  var nRel=nForRel(p,n0,t);
  var n80=nForDetect(p,n0,sd0,delta,0.80,baseline), n90=nForDetect(p,n0,sd0,delta,0.90,baseline);
  var Cknown=nForDetect(p,n0,sd0,delta,0.80,0);
  var U=PANAME[K];
  function num(n){ return n===Infinity?"—":Math.round(n).toLocaleString(); }
  function cnt(n){ return num(n)+" "+(K==="pit"&&Math.round(n)===1?"batter faced":U); }
  $("#pl-tiles").innerHTML=
    tile("Measured reliability", p.toFixed(3), "measured at "+Math.round(n0)+" "+U+" across "+
         L[m.k].n.toLocaleString()+" player-seasons")+
    tile(Math.round(100*t)+"% real at", cnt(nRel),
         "the sample it takes for this ranking to be "+Math.round(100*t)+"% genuine"+
         (K==="bat"?"; a full season is about 600 PA":""))+
    (n80===Infinity
      ? tile("Detect "+$("#pl-d").value+" "+m.u, "not possible",
          "against a "+baseline.toLocaleString()+"-"+U+" baseline. The baseline itself must exceed "+
          cnt(Cknown)+" before any follow-up window resolves a difference this small — "+
          "lengthen the baseline, do not watch longer.", true)
      : tile("Detect "+$("#pl-d").value+" "+m.u, cnt(n80),
          "to confirm a change this size 4 times out of 5"+(baseline?", against a "+
          baseline.toLocaleString()+"-"+U+" baseline":"")))+
    (n90===Infinity?"":tile("To be surer (9 in 10)", cnt(n90), "the same check, less "+
          "willing to miss a real change"));

  VIEWSTATE.planner={metric:m.k, unit:m.u, kind:K, unitName:PANAME[K],
    reliability:p, n0:Math.round(n0), leagueSD:sd0, target:t, nRel:nRel,
    delta:+$("#pl-d").value||0, baseline:baseline, n80:n80, n90:n90,
    minBaseline:Cknown, impossible:n80===Infinity};

  // curve: reliability against sample size
  var W=760,H=210,Lm=44,Rm=16,T=12,B=34, XM=Math.max(200,Math.min(1200,nRel*1.6||600));
  function X(n){return Lm+(n/XM)*(W-Lm-Rm);} function Y(v){return T+(1-v)*(H-T-B);}
  var s='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="reliability against sample size">';
  [0,0.25,0.5,0.75,1].forEach(function(v){
    s+='<line x1="'+Lm+'" y1="'+Y(v)+'" x2="'+(W-Rm)+'" y2="'+Y(v)+'" stroke="var(--hair)"/>'+
       '<text x="'+(Lm-7)+'" y="'+(Y(v)+4)+'" text-anchor="end" fill="var(--ink3)" '+
       'font-family="IBM Plex Mono, monospace" font-size="9.5">'+v.toFixed(2)+'</text>';
  });
  var d="",n;
  for(n=2;n<=XM;n+=Math.max(1,XM/400)){
    var k=n/n0, rr=Math.max(0,Math.min(1,k*p/(1+(k-1)*p)));
    d+=(d?"L":"M")+X(n).toFixed(1)+" "+Y(rr).toFixed(1)+" ";
  }
  s+='<path d="'+d+'" fill="none" stroke="var(--ac)" stroke-width="2"/>';
  if(nRel<XM){
    s+='<line x1="'+X(nRel)+'" y1="'+Y(0)+'" x2="'+X(nRel)+'" y2="'+Y(t)+
       '" stroke="var(--hot)" stroke-dasharray="4 3"/>'+
       '<line x1="'+Lm+'" y1="'+Y(t)+'" x2="'+X(nRel)+'" y2="'+Y(t)+
       '" stroke="var(--hot)" stroke-dasharray="4 3"/>'+
       '<circle cx="'+X(nRel)+'" cy="'+Y(t)+'" r="3.4" fill="var(--hot)"/>'+
       '<text x="'+(X(nRel)+7)+'" y="'+(Y(t)-7)+'" fill="var(--hot)" font-size="11" '+
       'font-weight="600">'+Math.round(nRel).toLocaleString()+' '+U+'</text>';
  }
  [0,0.25,0.5,0.75,1].forEach(function(f){
    s+='<text x="'+X(f*XM)+'" y="'+(H-B+16)+'" text-anchor="middle" fill="var(--ink3)" '+
       'font-family="IBM Plex Mono, monospace" font-size="9.5">'+Math.round(f*XM)+'</text>';
  });
  s+='<text x="'+((Lm+W-Rm)/2)+'" y="'+(H-3)+'" text-anchor="middle" fill="var(--ink3)" '+
     'font-size="10">'+PALONG[K]+'</text></svg>';
  $("#pl-curve").innerHTML='<div class="tile" style="padding:12px 10px 4px">'+s+'</div>';

  // the whole table, which is the actual artifact
  var h='<table><thead><tr><th class="l">metric</th><th>'+term("reliability at n₀",DEF_N0)+
    '</th><th>95% CI</th><th>'+U+' for 50% real</th><th>70%</th><th>80%</th><th>90%</th>'+
    '</tr></thead><tbody>';
  MET.filter(function(mm){return REL[mm.k];}).forEach(function(mm){
    var rr=REL[mm.k], ci=relCI(mm.k);
    h+='<tr'+(mm.k===m.k?' style="background:var(--sunk)"':'')+'><td class="l">'+mm.k+
      '</td><td>'+rr.sb.toFixed(3)+'</td>'+
      '<td class="sub">'+(ci?ci.lo.toFixed(3)+"&ndash;"+ci.hi.toFixed(3):"&mdash;")+'</td>'+
      [0.5,0.7,0.8,0.9].map(function(tt){
        return '<td>'+Math.round(nForRel(rr.sb,rr.n0,tt)).toLocaleString()+'</td>';}).join("")+
      '</tr>';
  });
  $("#pl-table").innerHTML=h+'</tbody></table>';
}

/* ===================== TAB 5: player check ===================== */
/* Share of a hot streak's wOBA gain kept over the next window of the same length, hitters
   2023-2025 (breakouts.py; FINDINGS 2026-09-18). Hitters only -- pitchers were not run. */
var LADDER={1:0.14,2:0.27,3:0.43}, WINNAME={1:"two weeks",2:"30 days",3:"45 days"};
function cardPlayer(){
  return ROWS.find(function(r){return String(r.id)===String($("#pc-who").value);});
}
function cardEvidence(){
  var me=cardPlayer(); if(!me||!BL.length) return null;
  var W=+$("#pc-win").value, last=BL.length-1, first=Math.max(0,last-W+1);
  var metrics=MET.map(function(m){return {k:m.k,n:m.n,d:m.d,hi:m.hi,g:m.g};});
  try{ return Evidence.build(ALL[shardKey(K,YR)], metrics, PK, me.id, BL[first], BL[last]); }
  catch(e){ return null; }
}
// The What-carries model, always on the 30-day window it was fit on.
function cardCarry(r){
  var n=BL.length; if(n<4) return null;
  var base=[]; for(var i=0;i<n-2;i++) base.push(i);
  var vn=sumList(r,[n-2,n-1]), vb=sumList(r,base), pa=vn[F[PK]], bpa=vb[F[PK]];
  if(pa<50||bpa<150) return null;
  var B=CARRY[K].beta, w=vn[F.wn]/pa, x=vn[F.xn]/pa, wb=vb[F.wn]/bpa, xb=vb[F.xn]/bpa;
  var pred=B[0]+B[1]*w+B[2]*wb+B[3]*x+B[4]*xb, gap=w-wb;
  return {gap:gap, expect:pred-wb, carry:Math.abs(gap)>1e-6?(pred-wb)/gap:0};
}
/* The verdict. Deliberately conservative: it never says buy or sell, a swing change never
   moves it (D27), and "how much will stick" comes from the carry model or the measured
   streak ladder, never from the size of the streak itself. */
/* Two tests, both required for "hot" or "cold": the recent stretch must differ from earlier this
   season (cardVerdictSeason) AND from his usual level from prior seasons (usualLevel). A move
   that only passes the first is a return toward normal, and says so. */
function cardVerdict(pk, carry, W){
  var v=cardVerdictSeason(pk, carry, W); if(v.cls==="early") return v;
  var bat=K==="bat", R=bat?"wOBA":"wOBA against", res=null, me=cardPlayer();
  pk.metrics.forEach(function(m){ if(m.metric===R) res=m; });
  var u=me&&usualLevel(me.id); if(!u||!res||res.value==null) return v;
  var zu=zUsual(res.value, pk.span.n, u), gu=bat?zu:-zu;
  v.usual={level:+u.mean.toFixed(3), seasons:u.span, z:+zu.toFixed(1), no_prior_seasons:u.fresh};
  var zt="z = "+(zu>0?"+":"&minus;")+Math.abs(zu).toFixed(1);
  var lvl=u.fresh ? "the league average of "+D3(u.mean)+" (he has no prior MLB seasons in the data; "+zt+")"
                  : "his usual level of "+D3(u.mean)+" from "+u.span+" ("+zt+")", zs="";
  if(v.cls==="flat"){
    if(Math.abs(gu)>=2) v.p+=" His whole season is running well "+(gu>0?"above":"below")+" "+lvl+
      zs+", though &mdash; the change came before this stretch.";
    return v;
  }
  var isHot=v.cls==="hot";
  if((isHot?gu:-gu)>=2){ v.p+=" It&rsquo;s also well "+(isHot?"above":"below")+" "+lvl+zs+"."; return v; }
  var d=res.change.delta, mag=Math.abs(d).toFixed(3).replace(/^0/,"");
  return {cls:"flat", usual:v.usual,
    h:isHot?"Better than earlier this season &mdash; but not beyond his usual level"
           :"Worse than earlier this season &mdash; but not below his usual level",
    p:R+" is "+((d>0)===true?"up ":"down ")+mag+" on "+(bat?"his":"the")+" earlier-season rate over the last "+
      WINNAME[W]+", but at "+D3(res.value)+" it&rsquo;s within normal range of "+lvl+zs+". That reads as "+
      (isHot?"a return to form more than a hot streak.":"a return to normal more than a slump.")+
      (u.fresh?" With no prior seasons to go on, it takes a bigger move to call either way.":"")};
}
function cardVerdictSeason(pk, carry, W){
  var bat=K==="bat", R=bat?"wOBA":"wOBA against", res=null;
  pk.metrics.forEach(function(m){ if(m.metric===R) res=m; });
  var who=bat?"his":"the";
  if(pk.span.n < 25*W) return {cls:"early", h:"Too early to read",
    p:"Only "+pk.span.n+" "+PALONG[K]+" in the last "+WINNAME[W]+" &mdash; not enough to say anything."};
  if(!res || !res.change) return {cls:"early", h:"No earlier-season baseline yet",
    p:"There isn&rsquo;t enough playing time earlier this season to compare against."};
  var d=res.change.delta, good=bat?d:-d, mag=Math.abs(d).toFixed(3).replace(/^0/,"");
  if(Math.abs(good)<0.040) return {cls:"flat", h:"Steady",
    p:(bat?"His":"The")+" "+R+" over the last "+WINNAME[W]+" is within ."+
      Math.round(Math.abs(d)*1000).toString().padStart(3,"0")+" of "+who+" earlier-season rate. Nothing to react to."};
  var keep=(W===2&&carry)?carry.carry:(carry?carry.carry:(bat&&good>0?LADDER[W]:null));
  var src=carry?"the carry model (last 30 days)":"how similar streaks have gone";
  var pct=keep===null?null:Math.round(100*Math.max(0,Math.min(1,keep)));
  var stick=pct===null?"":(pct<5?" Going by "+src+", expect essentially none of it to stick.":
    " Going by "+src+", expect about "+pct+"% of that to stick.");
  if(good>0){
    var lowK=keep===null||keep<0.35;
    return {cls:"hot", h:lowK?"Hot &mdash; but most of it is likely noise":"Hot &mdash; and more of it looks real than usual",
      p:R+" is "+(bat?"up ":"down ")+mag+" on "+who+" earlier-season rate over the last "+WINNAME[W]+"."+
        stick};
  }
  var lowK2=keep===null||keep<0.35;
  return {cls:"cold", h:lowK2?"Cold &mdash; expect most of it to come back":"Cold &mdash; and more of it may stick than usual",
    p:R+" is "+(bat?"down ":"up ")+mag+" on "+who+" earlier-season rate over the last "+WINNAME[W]+"."+
      stick};
}
/* His usual level: what his prior seasons say his wOBA is, before this season started.
   Marcel-style: the three most recent prior seasons, weighted 5/4/3 by recency, then pulled
   toward that season's league average by k plate appearances of average play, where
   k = sigma^2 / tau^2 is measured in history.py (tau = spread of true talent). The returned sd is
   how uncertain that level still is: a star with 1,800 PA has a tight usual level; a player with
   no prior seasons gets the league average with the full talent spread as his uncertainty --
   so a newcomer and an established hitter are held to different evidence. */
var HIST=null;
function usualLevel(id){
  if(!HIST||!HIST[K]) return null;
  var H=HIST[K], seasons=(H.players[String(id)]||[]).filter(function(x){
    return x[0]<YR && x[0]>=YR-3 && x[2]!=null; });
  var lgYear=String(Math.min(YR-1, H.years[H.years.length-1]));
  var lg=H.league[lgYear]; if(lg==null) return null;
  var n=0, t=0, used=[];
  seasons.forEach(function(x){ var wt=(5-(YR-1-x[0]))/5;       // 1, .8, .6
    n+=wt*x[1]; t+=wt*x[1]*x[2]; used.push(x[0]); });
  var k=H.k, mean=(t+k*lg)/(n+k), sd=H.tau*Math.sqrt(k/(n+k));
  var pa=seasons.reduce(function(a,x){return a+x[1];},0);
  return {mean:mean, sd:sd, lg:lg, pa:pa, years:used, fresh:!seasons.length,
          span:used.length?(Math.min.apply(null,used)===Math.max.apply(null,used)?String(used[0])
            :Math.min.apply(null,used)+"–"+Math.max.apply(null,used)):"no prior seasons"};
}
// z of a window's wOBA against his usual level: window noise plus the level's own uncertainty
function zUsual(w, pa, u){ return (w-u.mean)/Math.sqrt(HC_S2/pa + u.sd*u.sd); }

/* Who's hot or cold right now: every player whose last W half-months sit clearly above or
   below his own earlier-season rate -- the same comparison the card's verdict makes, so a name
   on the list and the card it opens never disagree. z counts sampling noise in both the
   window and the baseline (per-PA variance 0.2258, measured on hitters). */
var HC_S2=0.2258;
function hotCold(W){
  var last=BL.length-1, first=last-W+1; if(first<1) return [];
  var win=[], base=[]; for(var i=0;i<BL.length;i++) (i>=first?win:base).push(i);
  var bat=K==="bat", out=[];
  ROWS.forEach(function(r){
    var vn=sumList(r,win), vb=sumList(r,base), pa=vn[F[PK]], bpa=vb[F[PK]];
    if(pa<25*W || bpa<100) return;
    var w=vn[F.wn]/pa, wb=vb[F.wn]/bpa, gap=w-wb, good=bat?gap:-gap;
    var u=usualLevel(r.id), zu=u?zUsual(w,pa,u):null;
    out.push({id:r.id, n:r.n, pa:pa, w:w, wb:wb, gap:gap, good:good,
              xgap:vn[F.xn]/pa-vb[F.xn]/bpa,
              z:gap/Math.sqrt(HC_S2*(1/pa+1/bpa)),
              u:u, zu:zu, goodU:zu==null?null:(bat?zu:-zu)});
  });
  return out;
}
function renderHotCold(){
  var W=+$("#pc-win").value, bat=K==="bat", R=bat?"wOBA":"wOBA against";
  var dir=$("#hc-dir").value, mode=$("#hc-min").value, all=hotCold(W);
  var last=BL.length-1, first=Math.max(0,last-W+1), haveU=!!(HIST&&HIST[K]);
  if(mode==="both"&&!haveU) mode="z";                     // history still loading
  var sgn=function(p){ return p.good>0?1:-1; };
  var seasonOK=function(p){ return mode==="gap" ? Math.abs(p.gap)>=0.040 : Math.abs(p.z)>=2; };
  var keep=function(p){ return seasonOK(p) && (mode!=="both" || (p.goodU!=null && sgn(p)*p.goodU>=2)); };
  var hot=all.filter(function(p){return p.good>0&&keep(p);}).sort(function(a,b){return b.good-a.good;});
  var cold=all.filter(function(p){return p.good<0&&keep(p);}).sort(function(a,b){return a.good-b.good;});
  // the names the second test removed: moved against this season, not against his usual level
  var back=mode==="both" ? all.filter(function(p){ return seasonOK(p) && !keep(p); }) : [];
  $("#hc-title").innerHTML="Who&rsquo;s hot or cold right now <span class=\"sub\">"+lbl(BL[first])+
    " &ndash; "+lblEnd(BL[last])+" "+YR+"</span>";
  $("#hc-lede").innerHTML="Every "+(bat?"hitter":"pitcher")+" whose "+R+" over the "+WINNAME[W]+
    " to "+lblEnd(BL[last])+" is "+(mode==="both"
      ? "clearly different from <b>both</b> his rate earlier this season <b>and</b> his "+
        term("usual level",DEF_USUAL)+" from prior seasons"
      : mode==="z" ? "further from his own earlier-season rate than normal noise explains"
      : "at least .040 from his own earlier-season rate")+
    " &mdash; "+hot.length+" hot, "+cold.length+" cold, of "+all.length+" with enough playing time. "+
    "Click a name for his full card.";
  function f3(x){ return (x>0?"+":"&minus;")+D3(Math.abs(x)); }
  function f1(x){ return (x>0?"+":"&minus;")+Math.abs(x).toFixed(1); }
  function tbl(list, kind){
    var CAP=12, open=$("#hc-board")["_all_"+kind], shown=open?list:list.slice(0,CAP);
    var head='<h3 class="'+kind+'">'+(kind==="hot"?"Hot":"Cold")+' <span class="sub">'+list.length+'</span></h3>';
    if(!list.length) return '<div class="hc-col">'+head+'<p class="pc-note">Nobody right now.</p></div>';
    return '<div class="hc-col">'+head+'<div class="tw"><table><thead>'+
      '<tr><th class="l">'+(bat?"hitter":"pitcher")+'</th><th>'+R+'</th>'+
      '<th>earlier this season</th><th>vs. earlier</th><th>'+term("z",DEF_HCZ)+'</th>'+
      (haveU?'<th>'+term("usual level",DEF_USUAL)+'</th><th>vs. usual</th><th>'+term("z",DEF_HCZ)+'</th>':'')+
      '<th>'+term("contact",DEF_HCX)+'</th></tr></thead><tbody>'+
      shown.map(function(p){
        var u=p.u, uc=u?(u.fresh?' <span class="sub" title="No prior seasons in the data: '+
          'his usual level is the league average, with wide uncertainty">new</span>':''):'';
        return '<tr class="hc-row" data-id="'+p.id+'"><td class="l"><a href="#p-card?k='+K+'&id='+p.id+'">'+p.n+
          '</a> <span class="sub">'+Math.round(p.pa)+'</span></td><td>'+D3(p.w)+'</td>'+
          '<td>'+D3(p.wb)+'</td><td class="'+(p.good>0?"up":"dn")+'"'+heat(p.good>0,(Math.abs(p.z)-2)/2)+'><b>'+f3(p.gap)+'</b></td><td>'+f1(p.z)+'</td>'+
          (haveU?(u?'<td title="'+u.span+'">'+D3(u.mean)+uc+'</td><td class="'+(p.goodU>0?"up":"dn")+'"'+heat(p.goodU>0,(Math.abs(p.zu)-2)/2)+'>'+
            f3(p.w-u.mean)+'</td><td>'+f1(p.zu)+'</td>':'<td></td><td></td><td></td>'):'')+
          '<td>'+f3(p.xgap)+'</td></tr>';
      }).join("")+'</tbody></table></div>'+
      (list.length>CAP?'<p class="pc-note"><a href="#" class="hc-more" data-kind="'+kind+'">'+
        (open?"Show top "+CAP:"Show all "+list.length)+'</a></p>':'')+'</div>';
  }
  $("#hc-board").innerHTML=(dir!=="cold"?tbl(hot,"hot"):"")+(dir!=="hot"?tbl(cold,"cold"):"");
  var backTxt="";
  if(back.length){
    var names=back.sort(function(a,b){return Math.abs(b.z)-Math.abs(a.z);}).slice(0,8)
      .map(function(p){ return '<a href="#p-card?k='+K+'&id='+p.id+'" class="hc-back" data-id="'+p.id+'">'+
        p.n+'</a> ('+(p.good>0?"up":"down")+')'; });
    backTxt="<b>Not listed, though they moved against earlier this season:</b> "+names.join(", ")+
      (back.length>8?" and "+(back.length-8)+" more":"")+" &mdash; the move takes them back toward "+
      "their usual level rather than away from it, so it reads as a return to form, not a streak. ";
  }
  $("#hc-foot").innerHTML=backTxt+"The small number after each name is "+PALONG[K]+" in the stretch. "+
    (bat?"For scale: across 2023&ndash;2025, hot streaks lasting "+WINNAME[W]+" kept about "+
      Math.round(100*LADDER[W])+"% of their gain over the next "+WINNAME[W]+" &mdash; see "+
      "<a href=\"#p-break\">Streak history study</a>. ":"")+
    "Being on this list says the move is real <i>so far</i>, not that it will last.";
}
var DEF_USUAL="What his prior seasons say his level is: up to his last three seasons, the most "+
  "recent weighted most, then pulled toward league average by an amount set by how much he has "+
  "played. A player with no prior seasons in the data gets the league average with wide "+
  "uncertainty, so it takes more to call him hot or cold than an established player.";
var DEF_HCZ="How many times larger the move is than normal game-to-game noise would produce at "+
  "these sample sizes. 2 or more is unusual for chance alone; with hundreds of players, a few "+
  "will clear it by luck anyway.";
var DEF_HCX="The same comparison for expected wOBA, which rates the quality of contact and "+
  "ignores where the ball landed. It tells you whether the contact moved with the results.";

function renderCard(){
  renderHotCold();
  var pk=cardEvidence(), me=cardPlayer(), out=$("#pc-body");
  if(!pk||!me){ out.innerHTML='<p class="note">Pick a player.</p>'; return; }
  var W=+$("#pc-win").value, bat=K==="bat";
  var R=bat?"wOBA":"wOBA against", X=bat?"xwOBA":"xwOBA against";
  var steady=bat?["bat speed","exit velo"]:["fastball velo","whiff%"];
  var by={}; pk.metrics.forEach(function(m){ by[m.metric]=m; });
  var carry=cardCarry(me), v=cardVerdict(pk, carry, W);
  var real=pk.metrics.filter(function(m){ var g=getM(m.metric);
    return g&&g.g!=="Results"&&m.change&&m.change.verdict==="real"; });
  if(real.length && v.cls!=="early"){
    var top=real.reduce(function(a,b){ return Math.abs(b.change.delta_z)>Math.abs(a.change.delta_z)?b:a; });
    v.p+=" Separately, his "+top.metric+" really did change &mdash; see below.";
  }
  function row(k){ var m=by[k], g=getM(k); if(!m||!m.available) return '';
    return barRow(k, g.f(m.value), m.reliability, m.pct_raw, m.pct_shrunk); }

  // 1. how real is the recent line
  var s1='<h3>How real is the recent line</h3>'+
    '<div class="rows">'+row(R)+row(X)+row(steady[0])+row(steady[1])+'</div>'+
    '<p class="pc-note">Results ('+R+') against the steadier measurements underneath them. '+
    'Percentiles are against the '+pk.peer_pool.n_players+' others who played over the same dates.</p>';

  // 2. did anything change
  var moved=real.slice().sort(function(a,b){ return Math.abs(b.change.delta_z)-Math.abs(a.change.delta_z); })
    .slice(0,4);
  var s2='<h3>Did anything actually change</h3>'+(moved.length?
    '<ul class="pc-list">'+moved.map(function(m){ var g=getM(m.metric), c=m.change;
      return '<li><b>'+m.metric+'</b> '+g.f(c.base_value)+' &rarr; '+g.f(m.value)+
        ' <span class="sub">('+(c.delta>0?"+":"")+g.f(c.delta)+', a '+c.size+' change)</span></li>'; }).join("")+'</ul>'+
    '<p class="pc-note">These moved further than noise allows. Worth watching &mdash; but on this '+
    'site&rsquo;s evidence a real change in '+(bat?"swing or approach":"stuff or command")+
    ' does not predict next month&rsquo;s results, so it doesn&rsquo;t change the verdict.</p>'
    : '<p class="pc-note">Nothing in '+(bat?"his swing, approach or contact":"his stuff or command")+
    ' moved beyond what normal noise produces over this stretch.</p>');

  // 3. what to expect
  var s3='<h3>What to expect</h3>'+(carry?
    '<div class="out two pc-tiles"><div class="tile"><span class="k">Last 30 days vs. before</span><span class="v">'+
      (carry.gap>0?"+":"")+D3(carry.gap)+'</span><span class="d">'+R+'</span></div>'+
    '<div class="tile"><span class="k">Model&rsquo;s next month vs. before</span><span class="v">'+(carry.expect>0?"+":"")+D3(carry.expect)+
      '</span><span class="d">'+(Math.abs(carry.gap)>=0.040?Math.round(100*carry.carry)+'% '+term("carry",DEF_CARRY)+
      ' of the gap':'gap too small for a meaningful carry rate')+'</span></div></div>'
    : '<p class="pc-note">Not enough playing time for the carry model, which needs 50 '+PANAME[K]+
      ' in the last 30 days and 150 before that.</p>')+
    (bat?'<p class="pc-note">For scale: across 2023&ndash;2025, hot streaks lasting '+WINNAME[W]+' kept about '+
      Math.round(100*LADDER[W])+'% of their gain over the following '+WINNAME[W]+'. Longer streaks '+
      'keep more &mdash; contact quality alongside them doesn&rsquo;t change that.</p>':'');

  // 4. when you'll know
  var rr=REL[R], n70=rr?nForRel(rr.sb,rr.n0,0.7):null, relNow=relAt(R,pk.span.n), relSzn=relAt(R,me.t);
  var s4='<h3>When you&rsquo;ll know</h3>'+
    '<p class="pc-big"><b>'+Math.round(100*relNow)+'%</b> real over this stretch &middot; <b>'+
    Math.round(100*relSzn)+'%</b> over his full season</p>'+
    '<p class="pc-note">'+R+' becomes 70% trustworthy at about '+(n70?Math.round(n70).toLocaleString():"&mdash;")+
    ' '+PALONG[K]+'. He has '+me.t+' this season'+(n70&&me.t<n70?' &mdash; about '+
    Math.round(n70-me.t).toLocaleString()+' to go':' &mdash; already past it')+'.</p>';

  var span=lbl(pk.span.from)+" &ndash; "+lblEnd(pk.span.to)+" "+YR;
  out.innerHTML='<div class="hdr"><span class="big">'+me.n+'</span><span class="sub">'+span+
    '</span><span class="sub">'+pk.span.n+' '+PALONG[K]+' &middot; '+pk.baseline.n+' before that</span></div>'+
    '<div class="verdict '+v.cls+'"><b>'+v.h+'</b><p>'+v.p+'</p></div>'+
    '<div class="pc-grid"><section>'+s1+'</section><section>'+s2+'</section><section>'+s3+
    '</section><section>'+s4+'</section></div>'+
    '<p class="pc-links"><a href="#" id="pc-to-stretch">All his percentiles &rarr;</a>'+
    '<a href="#" id="pc-to-changes">His change log &rarr;</a></p>';
  $("#pc-to-stretch").addEventListener("click",function(e){ e.preventDefault();
    $("#who").value=me.id; var last=BL.length-1;
    $("#from").value=Math.max(0,last-W+1); $("#to").value=last; show(0,"p-stretch"); scrollToSubs(); });
  $("#pc-to-changes").addEventListener("click",function(e){ e.preventDefault();
    $("#c-who").value=me.id; show(0,"p-changes-mine"); scrollToSubs(); });
}

/* ===================== breakouts ===================== */
/* Static study, not a live view: breakouts.py --export writes data/breakouts.json with two
   views -- "career" (vs. career-to-date since 2023, hot and cold, |z| >= 2 only) and "season"
   (vs. earlier-season rate, every hot streak 80+ points up). Each has a stick-rate ladder and
   case studies chosen by rule. Hitters only and independent of the Type/Season menus. */
var BRK=null, BRKLOAD=null;
// [label, chip colour, hover text], by streak direction
var OUTCOME={hot:{stuck:["Stuck","c-hot","kept at least half the gain"],
                  faded:["Faded","","kept some, but under half"],
                  kaput:["Gone","c-cold","back at or below his baseline"],
                  no_next:["Missed time","","too few plate appearances afterwards to tell"],
                  too_late:["Too late to score","","the season ended before the horizon had passed"]},
             cold:{stuck:["Slump held","c-cold","still at least half as far below"],
                   faded:["Partly back","","some of the slump stayed"],
                   kaput:["Recovered","c-hot","back at or above his baseline"],
                   no_next:["Missed time","","too few plate appearances afterwards to tell"],
                   too_late:["Too late to score","","the season ended before the horizon had passed"]}};
function pct0(x){ var v=Math.round(100*x); return (v<0?"−":"")+Math.abs(v)+"%"; }
function w3(x){ return (x<0?"−":"")+Math.abs(x).toFixed(3).replace(/^0/,""); }
function sw3(x){ return (x>=0?"+":"−")+Math.abs(x).toFixed(3).replace(/^0/,""); }
function bView(){ return $("#b-base").value==="season" ? "season" : "career"; }
function bLadder(v, seasons, dir, w){
  return BRK.views[v].ladder.filter(function(r){ return r.seasons===seasons &&
    (r.dir||"hot")===dir && (w==null || r.blocks===w); })
    .sort(function(a,b){ return a.blocks-b.blocks; });
}
function renderBreakouts(){
  if(!BRK){
    if(!BRKLOAD) BRKLOAD=fetch("/data/breakouts.json").then(function(r){
        if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); })
      .then(function(j){ BRK=j; if(isShown("p-break")){ renderBreakouts();
        if(window.SUM) SUM.reset(); } })
      .catch(function(e){ $("#b-lede").textContent="Couldn't load the breakout study ("+e.message+")."; });
    return;
  }
  var v=bView(), career=v==="career", head=career?"2024-2025":"2023-2025";
  /* Every verdict on this tab is judged over one fixed horizon after the streak, the same for
     every streak length. It used to be "the next window of the same length" -- a two-week streak
     checked against the next two weeks, one noisy sample against another. */
  var HZ=(BRK.horizon_days||60)>=60?"two months":BRK.horizon_days+" days";
  var DEF_EARNED="xwOBA moved at least 50 points with the streak (up for a hot one, down for a "+
    "slump): the contact itself changed, not just where the balls landed.";
  var DEF_LUCKY="xwOBA moved less than 20 points: the results changed but the quality of "+
    "contact barely did.";
  if(career){
    var h=bLadder(v,head,"hot"), c=bLadder(v,head,"cold");
    $("#b-strip").innerHTML=
      '<div><b>'+pct0(h[0].all.kept)+'</b><span>of a significant two-week hot streak was still there '+
        'over the following '+HZ+' ('+h[0].all.n+' streaks)</span></div>'+
      '<div><b>'+pct0(c[0].all.kept)+'</b><span>of a significant two-week slump carried on over the '+
        'following '+HZ+' ('+c[0].all.n+' slumps)</span></div>'+
      '<div><b>'+pct0(h[2].all.kept)+' vs '+pct0(c[2].all.kept)+'</b><span>kept after a 45-day hot '+
        'streak vs. a 45-day slump &mdash; slumps last longer</span></div>';
    $("#b-lede").innerHTML="Only windows at least two standard errors above or below the "+
      "hitter&rsquo;s own career rate since 2023 &mdash; the streaks nobody could call noise at the "+
      "time. <b>Even these mostly evaporate</b>: a significant hot streak lasting two weeks / 30 days / "+
      "45 days kept "+h.map(function(r){return pct0(r.all.kept);}).join(" / ")+" of its gap over the "+
      "following "+HZ+". <b>Slumps hold up better at every length</b> ("+
      c.map(function(r){return pct0(r.all.kept);}).join(" / ")+"), plausibly because some are injury "+
      "or age, which are real. And contact still doesn&rsquo;t sort them: almost every significant "+
      "streak comes with a matching "+term("earned",DEF_EARNED)+" xwOBA move, which leaves the "+
      term("lucky",DEF_LUCKY)+" groups too small to compare.";
  } else {
    var two=bLadder(v,head,"hot",1)[0];
    $("#b-strip").innerHTML=
      '<div><b>'+pct0(two.all.kept)+'</b><span>of a two-week hot streak&rsquo;s gain was still there '+
        'over the following '+HZ+' ('+two.all.n.toLocaleString()+' streaks)</span></div>'+
      '<div><b>'+pct0(two.all.kaput)+'</b><span>were back at or below the hitter&rsquo;s own baseline '+
        'over the following '+HZ+'</span></div>'+
      '<div><b>'+pct0(two.earned.kept)+' vs '+pct0(two.lucky.kept)+'</b><span>kept by streaks backed by '+
        'better contact vs. by luck &mdash; no difference</span></div>';
    $("#b-lede").innerHTML="Every hitter who ran at least 80 points of wOBA above his own earlier-season "+
      "rate. Reading down the table, <b>length is what makes a streak believable</b>: the share kept "+
      "over the following "+HZ+" goes from "+pct0(bLadder(v,head,"hot",1)[0].all.kept)+" after a "+
      "two-week streak to "+pct0(bLadder(v,head,"hot",3)[0].all.kept)+" after a six-week one. Reading "+
      "across, <b>better contact adds nothing</b> "+
      "&mdash; at no length do "+term("earned",DEF_EARNED)+" streaks hold up better than "+
      term("lucky",DEF_LUCKY)+" ones.";
  }
  // under 10 streaks a share is mostly one or two players: show the count, not a percentage
  function grp(g){ return !g ? '&mdash;' : g.n<10 ? '<span class="sub">too few ('+g.n+')</span>'
    : pct0(g.kept)+' <span class="sub">('+g.n+')</span>'; }
  function row(r, dim){
    var ci=r.earned_minus_lucky_ci;
    return '<tr'+(dim?' class="b-dim"':'')+'><td class="l">'+(dim?'2026 &middot; ':'')+
      (r.dir||"hot")+' for '+WINNAME[r.blocks]+'</td><td>'+r.all.n+'</td><td><b>'+pct0(r.all.kept)+'</b></td>'+
      '<td class="sub">'+(r.all.kept_next==null?'&mdash;':pct0(r.all.kept_next))+'</td>'+
      '<td>'+pct0(r.all.kaput)+'</td><td>'+grp(r.earned)+'</td><td>'+grp(r.lucky)+'</td>'+
      '<td>'+(ci?'['+(ci[0]>=0?'+':'−')+pct0(Math.abs(ci[0]))+', '+(ci[1]>=0?'+':'−')+pct0(Math.abs(ci[1]))+']':'&mdash;')+'</td></tr>';
  }
  var dirs=career?["hot","cold"]:["hot"], rows="";
  [head,"2026"].forEach(function(sn){ dirs.forEach(function(d){
    rows+=bLadder(v,sn,d).map(function(r){ return row(r, sn==="2026"); }).join(""); }); });
  $("#b-ladder").innerHTML='<table><thead><tr><th class="l">streak</th><th>streaks</th>'+
    '<th>'+term("kept","Share of the gap still there over the following "+HZ+", weighted by "+
      "playing time. The same horizon for every streak length. For a slump, the share that carried on.")+'</th>'+
    '<th>'+term("old: next window","The measure this used before: the share kept over the NEXT window of "+
      "the SAME length, so a two-week streak was checked against the following two weeks. Averaged "+
      "over many streaks it lands close to the new figure; judged one streak at a time it was mostly "+
      "noise, which is why every verdict now uses the longer horizon.")+'</th>'+
    '<th>'+term("back to baseline","Share that were back at (or past) the hitter's own baseline over "+
      "the following "+HZ+": below it after a hot streak, above it after a slump.")+'</th>'+
    '<th>earned kept</th><th>lucky kept</th><th>'+term("difference, 95% CI","Earned minus lucky, "+
      "share kept. Resampled by player, since one hitter can have several streaks. Shown only when "+
      "both groups have at least 10 streaks; every range includes zero.")+'</th></tr></thead><tbody>'+
    rows+'</tbody></table>';
  $("#b-ladder-foot").innerHTML="Grey rows are 2026, shown for comparison and not pooled: this "+
    "season has been queried too often to count as a clean test. "+
    (career ? "The 2023 season has no earlier season to measure against, so it is left out of this "+
      "view. &ldquo;Career&rdquo; is capped by the data at three prior seasons; a longer history "+
      "needs the 2015&ndash;2022 backfill. " : "Its 45-day row rests on 15 lucky streaks. ")+
    "Streaks overlap within a season, so the three lengths are not independent samples. "+
    (function(){ var L=0,N=0; bLadder(v,head,"hot").concat(career?bLadder(v,head,"cold"):[])
       .forEach(function(r){ if(r.all){ L+=r.all.too_late||0; N+=(r.all.n||0)+(r.all.too_late||0); } });
       return N ? "<b>Streaks too late in the season to have a full "+HZ+" after them are not scored</b> "+
         "&mdash; "+L.toLocaleString()+" of "+N.toLocaleString()+" here. That tilts every figure toward "+
         "early- and mid-season streaks. Late-season streaks <i>mostly</i> keep less &mdash; at every "+
         "length on the season view, and at two weeks and 30 days on this one, while the 45-day rows "+
         "rest on too few late streaks to say &mdash; so for a streak happening now, the shares above "+
         "probably run a little high." : ""; })();

  var C=BRK.views[v].cases;
  function held(list){ return list.filter(function(c){return c.outcome==="stuck";}).length; }
  // a case too late in the season for the full horizon has no verdict, so it is not in the count
  function scored(list){ return list.filter(function(c){return c.outcome!=="too_late"&&c.outcome!=="no_next";}).length; }
  if(career){
    var hot=C.filter(function(c){return c.dir==="hot";}), cold=C.filter(function(c){return c.dir==="cold";});
    $("#b-cases-lede").innerHTML="Picked by rule, not by story: in each of 2024 and 2025, the three "+
      "hitters with a significant two-week streak whose contact quality moved the most in the same "+
      "direction &mdash; the most convincing cases the data has. The chart shows each half-month "+
      "of his season against the dashed line of his career rate before the streak.";
    $("#b-cases").innerHTML=
      '<h3 class="cases-h">Hot, with the contact to back it &mdash; <b>'+held(hot)+' of '+scored(hot)+
        '</b> kept even half the gain over the following '+HZ+'</h3><div class="cases">'+hot.map(caseCard).join("")+'</div>'+
      '<h3 class="cases-h">Cold, with the contact to match &mdash; <b>'+held(cold)+' of '+scored(cold)+
        '</b> were still half as far down over the following '+HZ+'</h3><div class="cases">'+cold.map(caseCard).join("")+'</div>';
  } else {
    $("#b-cases-lede").innerHTML="Picked by rule, not by story: in each of 2023, 2024 and 2025, the "+
      "three hitters whose contact quality jumped the most during a two-week hot streak &mdash; the "+
      "most convincing &ldquo;he&rsquo;s earned it&rdquo; cases the data has. <b>"+held(C)+" of "+
      scored(C)+" kept even half the gain</b> over the following "+HZ+". The chart shows each half-month of "+
      "his season, against the dashed line of his rate before the streak.";
    $("#b-cases").innerHTML='<div class="cases">'+C.map(caseCard).join("")+'</div>';
  }
}
function caseSpark(c){
  var W=300,H=96,px=6,py=10, P=c.path, n=P.length, t=0;
  P.forEach(function(p,i){ if(p.b===c.block) t=i; });
  var vals=P.map(function(p){return p.w;}).filter(function(v){return v!=null;}).concat([c.baseline]);
  var lo=Math.min.apply(null,vals)-.02, hi=Math.max.apply(null,vals)+.02;
  var step=(W-2*px)/n;
  function X(i){ return px+step*(i+.5); } function Y(v){ return py+(H-2*py)*(hi-v)/(hi-lo); }
  var d="", pen=false;
  P.forEach(function(p,i){ if(p.w==null){pen=false;return;}
    d+=(pen?"L":"M")+X(i).toFixed(1)+" "+Y(p.w).toFixed(1); pen=true; });
  var dots=P.map(function(p,i){ return p.w==null?"":'<circle cx="'+X(i).toFixed(1)+'" cy="'+
    Y(p.w).toFixed(1)+'" r="'+(i===t?3.6:2)+'" class="'+(i===t?"s-hot":i===t+1?"s-next":"s-pt")+'"/>'; }).join("");
  return '<svg class="spark'+(c.dir==="cold"?" cold":"")+'" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+c.player+
    ' wOBA by half-month, '+c.season+'">'+
    '<rect class="s-band" x="'+(px+step*t).toFixed(1)+'" y="0" width="'+step.toFixed(1)+'" height="'+H+'"/>'+
    (t+1<n?'<rect class="s-band2" x="'+(px+step*(t+1)).toFixed(1)+'" y="0" width="'+step.toFixed(1)+'" height="'+H+'"/>':'')+
    '<line class="s-base" x1="'+px+'" x2="'+(W-px)+'" y1="'+Y(c.baseline).toFixed(1)+'" y2="'+Y(c.baseline).toFixed(1)+'"/>'+
    '<path class="s-line" d="'+d+'"/>'+dots+'</svg>'+
    '<div class="s-axis"><span>'+sh(P[0].b)+'</span><span>- - - '+w3(c.baseline)+
      (c.base_pa?' career before':' before the streak')+'</span>'+
    '<span>'+sh(P[n-1].b)+'</span></div>';
}
function caseCard(c){
  var dir=c.dir||"hot", sg=dir==="cold"?-1:1, o=OUTCOME[dir][c.outcome];
  // Judged over the fixed horizon (BRK.horizon_days), not the next equal-length window.
  var HZ=(BRK&&BRK.horizon_days||60)>=60?"two months":(BRK.horizon_days+" days");
  var fg=c.fwd_gap, kept=fg==null?null:fg/c.gap, what=dir==="cold"?"the slump":"the gain";
  var nextTxt = c.outcome==="too_late"
      ? "Came too late in the season to have a full "+HZ+" after it, so it isn't scored."
    : fg==null ? "Didn't get enough plate appearances over the following "+HZ+" to tell."
    : sg*fg<=0 ? "Following "+HZ+": "+sw3(fg)+" &mdash; <b>back "+(dir==="cold"?"at or above":
        "at or below")+" his baseline</b>."
    : "Following "+HZ+": "+sw3(fg)+" &mdash; <b>kept "+pct0(kept)+"</b> of "+what+".";
  var rosTxt = c.ros_gap==null ? "" : " Rest of season: "+sw3(c.ros_gap)+" vs. baseline.";
  var luck = sg*(c.xgap-c.gap)>.05 ? (dir==="cold"
      ? " His contact was even worse than his results."
      : " His results actually trailed his contact &mdash; the rare streak the numbers said was, if "+
        "anything, <i>under</i>-rewarded.") : "";
  var before = c.base_pa
    ? "Career since 2023: "+w3(c.baseline)+" wOBA over "+Math.round(c.base_pa).toLocaleString()+" PA. Then "
    : "Had been a "+w3(c.baseline)+" wOBA hitter; then ";
  return '<article class="case">'+
    '<header><b>'+c.player+'</b><span class="sub">'+c.season+' &middot; '+lbl(c.block)+'&ndash;'+
      lblEnd(c.block).split(" ")[1]+'</span><span class="chip '+o[1]+'" title="'+o[2]+'">'+o[0]+'</span></header>'+
    caseSpark(c)+
    '<p>'+before+'<b>'+sw3(c.gap)+'</b> over '+c.pa+' PA'+(c.z!=null?' (z = '+(c.z<0?'−':'+')+Math.abs(c.z).toFixed(1)+')':'')+
      ', with xwOBA '+(c.xgap<0?'down ':'up ')+w3(Math.abs(c.xgap))+'.'+luck+'</p>'+
    '<p>'+nextTxt+rosTxt+'</p></article>';
}

/* ===================== head to head =====================
   P(A outperforms B) over a window the reader picks.

   The site deliberately does not publish a projected line: FINDINGS 2026-09-12
   measured a one-month point forecast at R2 ~0.06 against a 0.264 ceiling, with
   Marcel and a 48-feature model tied. Ordering a PAIR is a different and easier
   question -- only the sign of the gap has to clear the noise -- so this view
   asks that one and reports a probability, scored publicly below.

   Talent is the D42 usual level updated by this season, combined by precision.
   The three variances are kept separate all the way to the screen because the
   split (sampling ~63%, talent <5%) is the actual finding.                     */
/* Normal CDF via Abramowitz & Stegun 7.1.26 on erf. Nothing else on the page
   needed one -- every other view compares z against a fixed threshold rather
   than turning it into a probability. Max error ~1.5e-7, far below anything
   that survives being rounded to a whole percent. */
function cdf(z){
  var s=z<0?-1:1, x=Math.abs(z)/Math.SQRT2,
      t=1/(1+0.3275911*x),
      y=1-((((1.061405429*t-1.453152027)*t+1.421413741)*t-0.284496736)*t+0.254829592)*t*Math.exp(-x*x);
  return 0.5*(1+s*y);
}

var VS_DRIFT=0.0381;          // month-to-month sd of true talent, FINDINGS 2026-09-12
/* One scoring record PER PLAYER TYPE. This used to be a single global CAL holding whichever
   type loaded last, with a per-type promise cache in front of it -- so switching Pitchers back to
   Hitters found the hitters' promise already resolved, never re-assigned CAL, and left the
   pitchers' record (and its verdict text) on screen under the hitters' matchup. */
var CALS={}, CALLOAD={};

/* Bootstrapped 95% intervals on every reliability figure (reliability.py).
   Not on the critical path: without it the site behaves exactly as before, and
   with it every rho can say how well it is known. Merged into REL by metric. */
var RELCI={}, RELCILOAD={};
function loadRelCI(kind){
  if(RELCI[kind]||RELCILOAD[kind]) return;
  RELCILOAD[kind]=fetch("/data/reliability-"+kind+".json")
    .then(function(r){ return r.ok?r.json():null; })
    .then(function(j){ if(j){ RELCI[kind]=j.metrics; if(TABS[active]) TABS[active][2](); } })
    .catch(function(){});
}
function relCI(metric){ return (RELCI[K]||{})[metric]||null; }
/* "93% real, and that figure is itself known to +/-2 points" -- the same
   question the site asks of every other number, asked of its own constant. */
function relTitle(metric, rel){
  var c=relCI(metric);
  if(!c) return "share of the spread in this column that is real at this sample size";
  return "Measured "+(100*c.sb).toFixed(1)+"% real at "+
    Math.round(REL[metric]?REL[metric].n0:0)+" "+PANAME[K]+
    ", 95% CI "+(100*c.lo).toFixed(1)+"-"+(100*c.hi).toFixed(1)+"% across "+
    c.n.toLocaleString()+" player-seasons. Projected to this sample size it is at least "+
    "this uncertain.";
}

function vsTalent(r,through){
  var u=usualLevel(r.id); if(!u) return null;
  // Everything strictly up to and including `through`. Nothing after it may
  // touch the estimate, or standing on a past date would be cheating.
  var all=[]; for(var i=0;i<=through;i++) all.push(i);
  var v=sumList(r,all), pa=v[F[PK]];
  var pp=1/(u.sd*u.sd), op=pa>0?pa/HC_S2:0, va=1/(pp+op);
  return {mean:va*(u.mean*pp+(pa>0?v[F.wn]/pa:0)*op), va:va, pa:pa,
          season:pa>0?v[F.wn]/pa:null, usual:u,
          // how much of the estimate each source actually supplied
          wSeason:op/(pp+op), wUsual:pp/(pp+op)};
}

/* Playing time, projected forward, and then handed to the reader to override.

   Averaged over the blocks he actually appeared in rather than the last few:
   reading only recent blocks projected Aaron Judge at 2 PA a fortnight, because
   his last blocks of a part-finished season are empty. A player who is hurt or
   benched is exactly the case the model cannot see, so the honest move is a
   sane default in an editable box, not a cleverer guess. It matters more than
   it looks: FINDINGS 2026-09-12 found playing time alone outpredicts xwOBA. */
function vsRate(r,through){
  var played=0, tot=0;
  for(var i=0;i<=through;i++){
    var v=sumList(r,[i]), pa=v[F[PK]];
    if(pa>0){ played++; tot+=pa; }
  }
  return played?tot/(played*0.5):0;     // per month (a block is half a month)
}

/* Blank every output this view owns.

   Called once at the top of renderVs, because the alternative -- remembering to
   clear the right subset on each early return -- has now failed three separate
   times: a resolved warning left sitting above a good answer, and a season
   change leaving the previous season's headline, claim and date note on screen
   under a fresh error. Clear everything, then fill what applies. */
function vsBlank(){
  ["#vs-claim","#vs-sub","#vs-warn","#vs-split","#vs-tiles","#vs-players",
   "#vs-outcome","#vs-asof-note"].forEach(function(id){
     var el=$(id); if(el) el.innerHTML="";
   });
  $("#vs-head").textContent="\u2014";
}

function renderVs(){
  vsBlank();
  var sa=$("#vs-a"), sb=$("#vs-b");
  if(sa.dataset.kind!==K+YR){
    var opts=ROWS.slice().sort(function(a,b){return a.n<b.n?-1:1;})
      .map(function(r){return '<option value="'+r.id+'">'+r.n+'</option>';}).join("");
    sa.innerHTML=opts; sb.innerHTML=opts;
    sa.dataset.kind=K+YR; sb.dataset.kind=K+YR;
    if(ROWS.length>1){ sa.value=ROWS[0].id; sb.value=ROWS[1].id; }
  }
  // A is always the Player tab's player. When A changes and lands on B, move B to someone
  // else rather than open on "pick two different players".
  var gw=$("#g-who");
  if(gw && [].some.call(sa.options,function(o){return o.value===gw.value;})) sa.value=gw.value;
  if(sa.dataset.last!==sa.value){
    sa.dataset.last=sa.value;
    if(sb.value===sa.value){ var alt=ROWS.find(function(r){return String(r.id)!==sa.value;});
      if(alt) sb.value=alt.id; }
  }
  var months=+$("#vs-h").value, bat=K==="bat";
  var hb=Math.round(months*2);                 // horizon in half-month blocks

  /* "Standing on" = the last block the estimate is allowed to see.

     A season ends in September, so the last dates have no full window after
     them. Deleting them is the blunt fix and it throws away both the freshest
     data and the question a reader in-season actually has ("who is better from
     here?"). Instead every date stays, each one labelled with what can be done
     with it, and the DEFAULT lands on the newest fully-scoreable date so the
     outcome panel is populated on first paint rather than never.

       full     the whole window has been played -> forecast and outcome
       partial  some of it has  -> forecast and an interim outcome, marked
       live     nothing after it -> a real forecast with nothing to score yet

     Blocks 0 and 1 are still dropped: under a fortnight into a season there is
     nothing to stand on and the estimate is just the prior-season level. */
  var as=$("#vs-asof"), lastBlock=BL.length-1, lastFull=BL.length-1-hb;
  function asOfState(i){ return i<=lastFull ? "full" : (i<lastBlock ? "partial" : "live"); }
  if(as.dataset.sig!==K+YR+"|"+hb){
    var keep=+as.value, o="";
    for(var bi=1;bi<=lastBlock;bi++){
      var st=asOfState(bi);
      o+='<option value="'+bi+'">'+lblEnd(BL[bi])+
         (st==="full"?"":st==="partial"?" \u00b7 partly played":" \u00b7 live")+'</option>';
    }
    as.innerHTML=o;
    var dflt=lastFull>=1?lastFull:lastBlock;
    as.value=(keep>=1&&keep<=lastBlock)?keep:dflt;      // hold the date across a horizon change
    as.dataset.sig=K+YR+"|"+hb;
  }
  var through=Math.min(lastBlock,Math.max(1,+as.value||lastBlock));
  var asState=asOfState(through);

  var A=ROWS.find(function(r){return String(r.id)===sa.value;});
  var B=ROWS.find(function(r){return String(r.id)===sb.value;});
  if(!A||!B){ $("#vs-head").textContent="—"; return; }

  if(String(A.id)===String(B.id)){
    $("#vs-head").textContent="Pick two different players";
    $("#vs-sub").textContent=""; $("#vs-warn").innerHTML="";
    $("#vs-claim").textContent="";
    $("#vs-split").innerHTML=""; $("#vs-tiles").innerHTML="";
    $("#vs-players").innerHTML=""; $("#vs-outcome").innerHTML="";
    VIEWSTATE.vs=null; return;
  }
  var ta=vsTalent(A,through), tb=vsTalent(B,through);
  if(!ta||!tb){
    $("#vs-head").textContent="—";
    // Two very different reasons to be here, and saying the wrong one sends the
    // reader looking for missing data when the fetch simply has not landed.
    var earliest=HIST&&HIST[K]&&HIST[K].years?HIST[K].years[0]:null;
    $("#vs-warn").innerHTML = !HIST
      ? '<b>Loading prior seasons&hellip;</b> the usual-level baseline comes from '+
        'data/history.json, which is fetched after the page paints. This will fill in '+
        'by itself.'
      : (earliest!=null && YR<=earliest)
      ? '<b>'+YR+' has no prior seasons loaded</b>, so no estimate on this tab can be '+
        'built for it \u2014 every player would be pure league average. History currently '+
        'starts at '+earliest+'. Running <code>fetch_history.py</code> pulls season totals '+
        'back to 2015 and makes this season usable. Pick '+(earliest+1)+' or later meanwhile.'
      : '<b>No prior-season baseline</b> for '+
        ((!vsTalent(A,through)?A.n:B.n))+', so there is nothing to regress his estimate '+
        'toward. He has no qualifying season in data/history.json before '+YR+'.';
    $("#vs-split").innerHTML=""; $("#vs-tiles").innerHTML="";
    $("#vs-players").innerHTML=""; $("#vs-outcome").innerHTML="";
    VIEWSTATE.vs=null; return;
  }
  // Defaults follow the matchup; a value the reader typed survives until the
  // matchup changes under it, which is what the sig key tracks.
  var sig=A.id+"|"+B.id+"|"+months+"|"+through+"|"+K+"|"+YR, ia=$("#vs-pa-a"), ib=$("#vs-pa-b");
  var surname=function(n){ return n.split(" ").slice(-1)[0]; }, unit=K==="bat"?"PA":"batters";
  $("#vs-pa-a-l").textContent=surname(A.n)+"\u2019s "+unit; $("#vs-pa-b-l").textContent=surname(B.n)+"\u2019s "+unit;
  if(ia.dataset.sig!==sig){
    ia.value=Math.max(1,Math.round(vsRate(A,through)*months));
    ib.value=Math.max(1,Math.round(vsRate(B,through)*months));
    ia.dataset.sig=sig; ib.dataset.sig=sig;
  }
  var paA=Math.max(1,+ia.value||1), paB=Math.max(1,+ib.value||1);
  var vT=ta.va+tb.va, vD=2*VS_DRIFT*VS_DRIFT*months, vS=HC_S2/paA+HC_S2/paB, tot=vT+vD+vS;
  var delta=(bat?1:-1)*(ta.mean-tb.mean);
  var pr=cdf(delta/Math.sqrt(tot));
  var win=pr>=0.5?A:B, lose=pr>=0.5?B:A, shown=Math.max(pr,1-pr);

  // The warn bar is only ever written by the two failure paths above, so it has
  // to be cleared here or a banner from a previous render (most often "loading
  // prior seasons", which resolves by itself) sits above a perfectly good answer.
  $("#vs-warn").innerHTML="";
  var hz=$("#vs-h").selectedOptions[0].textContent;
  var metric=bat?"the higher wOBA":"the lower wOBA allowed";
  $("#vs-head").innerHTML='<span class="vsp" style="color:color-mix(in srgb,var(--ac) '+
    Math.round(30+140*Math.min(0.5,Math.abs(shown-0.5)))+'%,var(--ink3))">'+Math.round(100*shown)+
    '%</span><span class="unit"> '+win.n+'</span>';
  /* The claim was implicit until now: "outperforms" is decided on wOBA over the
     window, and for pitchers the better number is the smaller one. Saying it on
     screen costs one line and removes the only genuinely ambiguous thing here. */
  $("#vs-claim").innerHTML='<b>'+win.n+'</b> finishes '+hz.replace(/^next /,"the next ")+
    ' with '+metric+' of the two. <b>'+lose.n+'</b> does in the other '+
    Math.round(100*(1-shown))+'%. An exact tie counts for neither and is too rare to matter.';
  var standing="Standing on "+YR+" through "+lblEnd(BL[through])+" only \u2014 nothing after "+
    "that date touches the estimate";
  $("#vs-sub").textContent=standing+". Assuming about "+paA.toLocaleString()+" "+PANAME[K]+
    " for "+A.n+" and "+paB.toLocaleString()+" for "+B.n+" over the window.";
  // Which of the three kinds of date this is, and in the live case what the
  // honest forward question in September actually is.
  var endsIn=BL[lastBlock].slice(5,7)==="10"?"October":"September";
  $("#vs-asof-note").innerHTML =
    asState==="full"
      ? "This window has been played in full, so the forecast below is scored against what "+
        "actually happened. Dates after <b>"+lblEnd(BL[Math.max(1,lastFull)])+"</b> are marked "+
        "<i>partly played</i> or <i>live</i>: the "+YR+" season ends in "+endsIn+"."
    : asState==="partial"
      ? "<b>Only part of this window was ever played</b> \u2014 the "+YR+" season ends in "+
        endsIn+". The forecast stands as made; the outcome below is an interim one and is "+
        "labelled as such."
      : "<b>Nothing follows this date</b>, so this is a live forecast with nothing to score it "+
        "against \u2014 the "+YR+" season ends here. That is the honest state of a question "+
        "asked in "+endsIn+": the real forward window is <i>next season</i>, and whether the "+
        "end of one season says anything about the next is an open question this project has "+
        "not answered (backlog S34). Pick an earlier date to see the estimator scored.";


  /* If the window has already happened, the answer is sitting in the shard.
     Showing prediction against outcome turns the tab into the prediction
     ledger of PRODUCT.md #1, one matchup at a time and at no extra cost --
     and it is a far better teacher than the aggregate table, because you
     watch a 62% lose. */
  (function(){
    var end=Math.min(BL.length-1, through+hb), have=end-through;
    if(have<=0){ $("#vs-outcome").innerHTML=""; return; }
    var idx=[]; for(var i=through+1;i<=end;i++) idx.push(i);
    var va=sumList(A,idx), vb=sumList(B,idx);
    var pa1=va[F[PK]], pb1=vb[F[PK]];
    if(pa1<10||pb1<10){
      $("#vs-outcome").innerHTML='<p class="note">This window has partly happened, but one of '+
        'them barely played in it, so there is nothing to score against.</p>'; return; }
    var wa=va[F.wn]/pa1, wb=vb[F.wn]/pb1;
    var aAhead=bat?(wa>wb):(wa<wb);
    var winnerWas=aAhead?A.n:B.n;
    var hit=(winnerWas===win.n);
    var partial=have<hb;
    $("#vs-outcome").innerHTML=
      '<div class="ocome '+(hit?"ok":"miss")+'">'+
        '<p class="scope">What actually happened'+(partial?" &mdash; so far":"")+'</p>'+
        '<p class="ocome-h">'+(hit?"&#10003; Called it":"&#10007; Missed")+'</p>'+
        '<p class="ocome-l"><b>'+winnerWas+'</b> finished ahead, '+
          (aAhead ? w3(wa)+' to '+w3(wb) : w3(wb)+' to '+w3(wa))+
          ' over '+sh(BL[through+1])+'&ndash;'+lblEnd(BL[end])+
          ' ('+Math.round(pa1)+' and '+Math.round(pb1)+' '+PANAME[K]+').</p>'+
        '<p class="ocome-v">'+(hit
          ? 'The '+Math.round(100*shown)+'% call came in. <span class="chip right">right</span>'
          : 'The '+Math.round(100*shown)+'% call missed. <span class="chip wrong">wrong</span>')+
          ' <span class="sub">One matchup proves nothing either way &mdash; a '+
          Math.round(100*shown)+'% call is meant to be wrong about '+
          Math.round(100*(1-shown))+' times in 100. The table below is where that gets judged.</span></p>'+
        (partial?'<p class="note">Only '+have+' of '+hb+' half-months of this window have been '+
          'played, so this is an interim result, not the one the forecast was for.</p>':'')+
      '</div>';
  })();

  /* Show where each estimate came from. The number on its own is oracular; the
     split between "what he has done this year" and "what he usually is" is the
     shrinkage, which is the thing this whole site is about. Same move the
     Percentiles tab makes by drawing the bar twice. */
  function who(r,t){
    var u=t.usual, thin=u.fresh||u.pa<300;
    return '<div class="pest">'+
      '<p class="pest-h"><b>'+r.n+'</b><span class="pest-v">'+w3(t.mean)+'</span></p>'+
      '<p class="pest-l">estimated true '+(bat?"wOBA":"wOBA allowed")+'</p>'+
      '<div class="pest-rows">'+
        '<div class="pest-row"><span class="pl">this season</span>'+
          '<span class="pv">'+(t.season==null?"—":w3(t.season))+'</span>'+
          '<span class="pn">'+Math.round(t.pa).toLocaleString()+' '+PANAME[K]+'</span>'+
          '<span class="pw"><i style="width:'+(100*t.wSeason).toFixed(0)+'%"></i></span>'+
          '<span class="pp">'+Math.round(100*t.wSeason)+'%</span></div>'+
        '<div class="pest-row"><span class="pl">usual level</span>'+
          '<span class="pv">'+w3(u.mean)+'</span>'+
          '<span class="pn">'+(u.fresh?"no prior seasons":u.span)+'</span>'+
          '<span class="pw"><i style="width:'+(100*t.wUsual).toFixed(0)+'%"></i></span>'+
          '<span class="pp">'+Math.round(100*t.wUsual)+'%</span></div>'+
      '</div>'+
      (thin?'<p class="pest-warn">'+(u.fresh
        ? 'No prior season to lean on, so his usual level is just the league average. '+
          'That makes the estimate wide and pulls it toward the middle.'
        : 'Only '+Math.round(u.pa).toLocaleString()+' '+PANAME[K]+' of prior-season history, '+
          'so his usual level is itself shaky.')+'</p>':'')+
    '</div>';
  }
  $("#vs-players").innerHTML='<p class="scope">How each estimate was reached</p>'+
    '<div class="pests">'+who(A,ta)+who(B,tb)+'</div>'+
    '<p class="note">Neither column is the man&rsquo;s real talent; the estimate is a '+
    'weighted blend of the two, and the weights are what the bars show. A short season '+
    'counts for little: it takes roughly <b>330 '+PANAME[K]+'</b> before this season and his '+
    'prior form carry equal weight.</p>';

  var pct=function(x){return 100*x/tot;};
  /* Shares alone invite "60% of what?", so the bar is captioned with the actual
     spread it divides up: the middle-80% range of the wOBA difference. */
  // delta is A-minus-B (already flipped for pitchers). State the range in the
  // FAVOURITE's direction, or it reads backwards whenever B is the favourite.
  var sd=Math.sqrt(tot), dFav=(pr>=0.5?delta:-delta),
      lo=dFav-1.2816*sd, hi=dFav+1.2816*sd;
  $("#vs-split").innerHTML=
    '<p class="scope">Why the odds are this close to 50%</p>'+
    '<p class="note">Most of what will decide this matchup hasn&rsquo;t happened yet. The bar splits '+
      'the remaining uncertainty into its three sources; the bigger the purple share, the more it comes '+
      'down to luck.</p>'+
    '<div class="vsbar"><span style="width:'+pct(vT)+'%;background:var(--ink3)"></span>'+
      '<span style="width:'+pct(vD)+'%;background:var(--warn,#c98a00)"></span>'+
      '<span style="width:'+pct(vS)+'%;background:var(--luck)"></span></div>'+
    '<div class="lg"><span><i style="background:var(--ink3)"></i><b>'+Math.round(pct(vT))+
      '%</b> not knowing their true talent</span>'+
      '<span><i style="background:var(--warn,#c98a00)"></i><b>'+Math.round(pct(vD))+
      '%</b> talent shifting over the window</span>'+
      '<span><i style="background:var(--luck)"></i><b>'+Math.round(pct(vS))+
      '%</b> ordinary luck over the next ~'+Math.round((+$("#vs-pa-a").value||0)+(+$("#vs-pa-b").value||0))+' '+PANAME[K]+'</span></div>'+
    '<p class="note">Together they say the gap between them over this window should land '+
      'somewhere around <b>'+sw3(lo)+' to '+sw3(hi)+'</b> of wOBA, 8 times in 10 — in '+
      win.n+'&rsquo;s favour when positive. That spread is what the bar divides up, and it '+
      'is wider than the '+Math.round(1000*Math.abs(ta.mean-tb.mean))+'-point talent gap by '+
      'a long way, which is the whole reason the answer is not 99%.</p>';

  var sep=2*HC_S2*Math.pow((1.96+0.8416)/Math.abs(ta.mean-tb.mean),2);
  var gap=Math.abs(ta.mean-tb.mean), gapPts=Math.round(1000*gap);
  var season=K==="bat"?600:750;        // a full season of PA / batters faced
  $("#vs-tiles").innerHTML=
    tile("Estimated talent gap", w3(gap),
      "of wOBA — "+gapPts+(gapPts===1?" point":" points")+". What we think separates them <i>underneath</i> the "+
      "results, after each man&rsquo;s numbers are pulled toward the league by however "+
      "much of them is noise. <b>Neither player has actually hit this</b>, and it is not a "+
      "prediction of the margin: "+A.n+" "+w3(ta.mean)+" against "+B.n+" "+w3(tb.mean)+".")+
    tile("Enough to prove it", (sep>200000?"Never":Math.round(sep).toLocaleString()+" "+PANAME[K]),
      (sep>200000?"No realistic sample would tell these two apart":"<b>each</b>, side by side")+
      ", before a gap this size would register as a real "+
      "difference rather than noise (a two-sided 95% test, with a 4-in-5 chance of "+
      "catching it if it is there). "+
      (sep>200000?"The two estimates are near-identical, so no sample settles it."
       : sep>season?"That is more than "+(sep/season<2?"a full season":
          (sep/season).toFixed(1)+" seasons")+" apiece — no window you can pick here "+
          "will settle this one."
       : "Inside a single season, so this is one of the rarer matchups that a real "+
         "sample could actually decide."));

  VIEWSTATE.vs={a:{id:A.id,name:A.n,talent:ta.mean,season:ta.season,usual:ta.usual.mean,
                   var:ta.va,pa:ta.pa,expPA:paA},
                b:{id:B.id,name:B.n,talent:tb.mean,season:tb.season,usual:tb.usual.mean,
                   var:tb.va,pa:tb.pa,expPA:paB},
                p:pr, favourite:win.n, shown:shown, months:months, kind:K, season:YR,
                asOf:lblEnd(BL[through]), through:through, hblocks:hb,
                vTalent:vT, vDrift:vD, vSample:vS, gap:Math.abs(ta.mean-tb.mean),
                paToSeparate:sep, cal:CALS[K]&&CALS[K].calibration};
  renderVsCal();
}

/* The honest comparison is not against "always say 50%" -- any ranking clears that. It is against
   the simplest calibrated rule: slice matchups by one raw gap and predict the win rate that slice
   actually had, fitted on other seasons (matchup.py slice_baseline). Three cases, and the tab says
   which one this horizon is in rather than quoting a Brier score that flatters it. */
function skillLine(H){
  var sk=H.skill, nv=H.naive;
  if(!sk||!nv) return 'Brier <b>'+H.scores.full.brier.toFixed(4)+'</b> against .2500 for a coin.';
  var best=nv[sk.best_naive], pct=function(x){return Math.round(100*x)+"%";};
  if(!sk.vs_coin.significant)
    return '<b>At this horizon it has no demonstrable skill</b>: across matchups in general it does '+
      'no better than a coin flip &mdash; or than the simplest rule, '+best.desc+'. Read the number '+
      'above as a lean, not a forecast.';
  if(best.verdict!=="estimator better")
    return 'It beats a coin flip, but <b>not a much simpler rule</b> &mdash; '+best.desc+
      ' &mdash; which does as well at this horizon.';
  return 'It beats a coin flip and <b>beats the best simple rule</b> ('+best.desc+'). That rule '+
    'alone gets <b>'+pct(sk.naive_share)+'</b> of the way; the rest is what combining prior form '+
    'with this season, weighted by how much of each to trust, adds.';
}

/* The receipt: how this estimator has scored on every pair in the backtest.

   Conditioned on the horizon, because calibration is NOT stable across it --
   at 15 days the estimator is overconfident (says 57%, delivers 51%) and at 90
   days underconfident (says 74%, delivers 87%). Showing one table for all four
   horizons, which this tab did until the as-of control went in, quietly
   mislabels three of them. Not conditioned on the as-of date: splitting the
   30-day panel at the season midpoint moves mean(actual - said) by under a
   percentage point, so slicing on it would only thin the buckets. */
/* Every naive prior on the identical pairs: rank by one raw gap, predict the win rate that slice
   actually had (fitted leave-one-season-out). Green = the estimator beat it, red = it beat the
   estimator, pale = no difference either way. */
var NAIVE_LBL={const:"Last season's better player wins a fixed share", usual:"Usual level (last three seasons, regressed)",
  season:"Season to date", last:"Last season only", career:"Career before this season",
  marcel:"Marcel (5/4/3, regressed, age-adjusted)"};
function renderNaive(H, league){
  var el=$("#vs-naive"); if(!el) return;
  if(!league||!H.naive){ el.innerHTML=""; $("#vs-naive-foot").innerHTML=""; return; }
  var est=H.scores.full.brier;
  var list=Object.keys(NAIVE_LBL).filter(function(k){return H.naive[k];})
    .map(function(k){ return {k:k, v:H.naive[k]}; })
    .sort(function(a,b){ return a.v.brier-b.v.brier; });
  var f4=function(x){ return x.toFixed(4).replace(/^0/,""); },
      sg=function(x){ return (x>=0?"+":"\u2212")+Math.abs(x).toFixed(4).replace(/^0/,""); };
  var h='<table class="t"><thead><tr><th class="l">forecaster</th><th>Brier</th>'+
        '<th>estimator&rsquo;s edge</th><th>95% CI</th><th></th></tr></thead><tbody>'+
        '<tr class="hl"><td class="l"><b>The estimator</b> (prior seasons + this season, shrunk)</td>'+
        '<td><b>'+f4(est)+'</b></td><td></td><td></td><td></td></tr>';
  list.forEach(function(o){
    var v=o.v, cls=v.verdict==="estimator better"?"right":v.verdict==="baseline better"?"wrong":"part",
        lab=v.verdict==="estimator better"?"estimator better":v.verdict==="baseline better"?"rule better":"tie";
    h+='<tr><td class="l">'+NAIVE_LBL[o.k]+'</td><td>'+f4(v.brier)+'</td><td>'+sg(v.diff)+'</td>'+
       '<td>['+sg(v.lo)+', '+sg(v.hi)+']</td><td><span class="chip '+cls+'">'+lab+'</span></td></tr>';
  });
  el.innerHTML=h+'<tr><td class="l">Always 50%</td><td>.2500</td><td>'+sg(.25-est)+'</td><td></td><td></td></tr></tbody></table>';
  $("#vs-naive-foot").innerHTML="Lower Brier is better. Each rule ranks the pair by one raw gap and "+
    "predicts the win rate that slice of matchups actually had, fitted leave-one-season-out so no "+
    "season is scored by rates learned from itself; the interval resamples block boundaries. Last "+
    "season, career and Marcel use official MLB season lines back to each player&rsquo;s debut, "+
    "with wOBA rebuilt from counting stats using one fixed set of weights.";
}
function renderVsCal(){
  var key=K, CAL=CALS[key];
  if(!CAL){
    if(!CALLOAD[key]) CALLOAD[key]=fetch("/data/matchup-"+key+".json")
      .then(function(r){ if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); })
      .then(function(j){ CALS[key]=j; if(K===key){ if(isShown("p-vs")) renderVs(); else renderVsCal();
        if(window.SUM) SUM.reset(); } })
      .catch(function(e){ $("#vs-calnote").textContent=
        "Couldn't load the scoring record ("+e.message+") — run matchup.py."; });
    // clear BOTH, or the other type's verdict sits under this type's matchup while it loads
    $("#vs-cal").innerHTML=""; $("#vs-calnote").innerHTML=""; return;
  }
  // On the League tab this is a record in its own right, read at its own horizon; on the
  // Player tab it is the receipt for the matchup on screen.
  var league=isShown("p-vs-scored");
  var v=league?null:VIEWSTATE.vs;
  var hb=league?Math.round(2*(+$("#vsc-h").value||1)):(v?v.hblocks:2);
  var H=CAL.horizons&&CAL.horizons[String(hb)];
  if(!H){ $("#vs-cal").innerHTML="";
    $("#vs-calnote").textContent="No scoring record for this horizon yet — re-run matchup.py.";
    return; }
  /* The table itself. Buckets are shown as the ranges they are, the margin of
     error is named rather than left as a bare +/-, and the row containing the
     probability now on screen is marked so the receipt attaches to the claim. */
  var here=v?v.shown:null;
  var h='<table class="t"><thead><tr><th>when it said</th><th>the favourite actually won</th>'+
        '<th>matchups</th><th>margin of error</th><th></th></tr></thead><tbody>';
  H.calibration.forEach(function(b){
    var bad=Math.abs(b.hit-b.said)>2*b.se;
    var mine=here!=null && here>=b.lo && here<b.hi;
    h+='<tr'+(mine?' class="hl"':'')+'><td>'+Math.round(100*b.lo)+'–'+Math.round(100*b.hi)+
       '%</td><td class="'+(bad?"cal-wrong":"cal-right")+'" title="'+(bad?"Outside its margin of error":"Within its margin of error")+'">'+Math.round(100*b.hit)+'%</td><td>'+
       b.n.toLocaleString()+'</td><td>&plusmn;'+Math.round(100*b.se)+' pts</td><td>'+
       (mine?'<b>this matchup</b>':'')+(bad?' <span class="chip wrong">off</span>':' <span class="chip right">on target</span>')+'</td></tr>';
  });
  $("#vs-cal").innerHTML=h+'</tbody></table>';
  renderNaive(H, league);

  var sc=H.scores;
  /* If this matchup lands in a band the backtest says the estimator got wrong,
     say so here rather than leaving the reader to cross-reference the table. A
     tool called Reality Check should run one on itself. */
  var warn="";
  if(v){
    var band=H.calibration.filter(function(b){ return v.shown>=b.lo && v.shown<b.hi; })[0];
    if(band && Math.abs(band.hit-band.said)>2*band.se)
      warn='<p class="note wrong"><b>Treat the number above with extra caution.</b> In this '+
        'range the estimator has been <b>'+(band.hit<band.said?"over":"under")+'confident</b>: '+
        'it said about '+Math.round(100*band.said)+'% and was right '+Math.round(100*band.hit)+
        '% of the time, across '+band.n.toLocaleString()+' matchups. Every other band on the '+
        'table lands within its margin of error; this one does not.</p>';
  }
  /* Was three paragraphs restating the method. The method now lives in the
     addendum; what stays here is only what a reader needs to judge the number
     immediately above it. */
  if($("#vs-verdict")) $("#vs-verdict").innerHTML=skillLine(H)+
    ' <a href="#p-vs-scored">The full record</a> is under Head-to-head track record on the League tab.';
  $("#vs-calnote").innerHTML=warn+
    '<b>'+H.n_pairs.toLocaleString()+' matchups</b> at '+(league?'a ':'this same ')+H.days+'-day horizon, '+
    CAL.seasons[0]+'\u2013'+CAL.seasons[1]+', each predicted before the window and graded after. '+
    skillLine(H)+(league?' ':' <b>This is the estimator\u2019s record on other matchups, not a '+
    'margin of error on this one.</b> ')+
    '<a href="/addendum.html#matchup">How this is worked out and where it is known to be off</a>.';
}


/* ===================== season line =====================
   The surface numbers, before any of the analysis: games, hits, homers, the slash line. Summed
   from the same half-month blocks as everything else, so the season and the recent stretch come
   from one source. Two rows on purpose -- a season set against a hot or cold stretch is the
   comparison this whole site exists to make. */
var POSNAME={C:"catcher","1B":"first base","2B":"second base","3B":"third base",SS:"shortstop",
             LF:"left field",CF:"center field",RF:"right field",DH:"designated hitter",P:"pitcher"};
function surfaceCalc(g){
  if(K==="bat"){
    var h=g("h1")+g("h2")+g("h3")+g("hr"), ab=g("ab"), bb=g("bb")+g("ibb");
    var pa=ab+bb+g("hbp")+g("sf")+g("sh")+g("ci"), obpD=ab+bb+g("hbp")+g("sf");
    var tb=g("h1")+2*g("h2")+3*g("h3")+4*g("hr");
    var obp=obpD?(h+bb+g("hbp"))/obpD:null, slg=ab?tb/ab:null;
    return {G:g("g"), PA:pa, AB:ab, H:h, "2B":g("h2"), "3B":g("h3"), HR:g("hr"), BB:bb, SO:g("k"),
            AVG:ab?h/ab:null, OBP:obp, SLG:slg, OPS:(obp!=null&&slg!=null)?obp+slg:null,
            wOBA:g("pa")?g("wn")/g("pa"):null};
  }
  var ip=g("outs")/3, bbp=g("bb")+g("ibb");
  return {G:g("g"), IP:ip, H:g("h"), HR:g("hr"), BB:bbp, SO:g("k"), HBP:g("hbp"),
          WHIP:ip?(bbp+g("h"))/ip:null, "K%":g("bf")?g("k")/g("bf"):null,
          "BB%":g("bf")?bbp/g("bf"):null, "wOBA against":g("bf")?g("wn")/g("bf"):null};
}
function shardGetter(r, idxs){
  var v=sumList(r,idxs); return function(k){ return F[k]!=null ? v[F[k]] : 0; };
}
function surfaceOf(r, idxs){ return surfaceCalc(shardGetter(r, idxs)); }
// Every season a player has, from lines.py's per-season summary. The open season is always
// summed live from its shard instead, so it can never lag the rest of the page.
var LINES={}, LINELOAD={};
function linesFor(id){
  var key=K;
  if(!LINES[key] && !LINELOAD[key]){
    LINELOAD[key]=fetch("/data/lines-"+key+".json")
      .then(function(x){ return x.ok?x.json():null; })
      .then(function(j){ LINES[key]=j||{fields:[],players:{}}; if(K===key && isShown("p-line")) renderLine(); })
      .catch(function(){ LINES[key]={fields:[],players:{}}; });
  }
  var L=LINES[key]; if(!L) return null;
  return (L.players[String(id)]||[]).map(function(s){
    var m={}; L.fields.forEach(function(f,i){ m[f]=s[3][i]; });
    return {y:s[0], tm:s[1], pos:s[2], get:function(k){ return m[k]||0; }};
  });
}
function fmtIP(ip){ var w=Math.floor(ip+1e-9); return w+"."+Math.round((ip-w)*3); }
/* ===================== key-numbers summary =====================
   A second, independent summary for the Season line. The main summary panel is one shared node
   that resets on every redraw, which would cut this one off mid-stream, so it has its own
   request and its own abort. Same endpoint, same rules, its own prompt ("line"). */
var LINE_EV=null, LINE_SUMS={}, LINE_CTL=null;
function setLineEvidence(r, cols, rows, cell, official){
  var sig=K+"|"+YR+"|"+r.id;
  LINE_EV={sig:sig, view:"line", title:"His key numbers",
    sub:r.n+(r.tm?" · "+r.tm:"")+" · "+rows.length+" rows",
    cols:[{k:"season"},{k:"team"}].concat(cols.map(function(c){return {k:c};})),
    rows:rows.map(function(rw){ var o={season:rw.lab, team:rw.tm};
      cols.forEach(function(c){ o[c]=cell(c,rw.v[c]).replace(/&mdash;/g,"—"); }); return o; }),
    context:{player:r.n, kind:K, selected_season:YR, source:official?"official MLB season lines":"pitch-tracking blocks"}};
  paintLineSum();
}
function paintLineSum(){
  var out=$("#line-sum-out"), go=$("#line-sum-go"); if(!out||!go) return;
  var done=LINE_EV && LINE_SUMS[LINE_EV.sig];
  out.innerHTML=done?done:""; out.hidden=!done;
  go.textContent=done?"Rewrite":"Summarize his key numbers";
  go.disabled=!LINE_EV;
}
function paras(t){
  return t.split(/\n{2,}/).map(function(x){ return '<p>'+x.replace(/&/g,"&amp;").replace(/</g,"&lt;")+'</p>'; }).join("");
}
function runLineSum(){
  if(!LINE_EV) return;
  var pk=LINE_EV, out=$("#line-sum-out"), go=$("#line-sum-go"), text="";
  if(LINE_CTL) LINE_CTL.abort();
  LINE_CTL=new AbortController();
  out.hidden=false; out.innerHTML='<p class="sub">Writing&hellip;</p>'; go.disabled=true;
  fetch("/api/summary",{method:"POST",headers:{"content-type":"application/json"},
    body:JSON.stringify({view:"line", kind:K, evidence:pk}), signal:LINE_CTL.signal})
    .then(function(res){
      if(!res.ok) return res.json().catch(function(){return {};}).then(function(j){ throw new Error(j.error||("HTTP "+res.status)); });
      var rd=res.body.getReader(), dec=new TextDecoder(), buf="";
      function line(l){ l=l.trim(); if(!l) return; var e; try{ e=JSON.parse(l); }catch(x){ return; }
        if(e.type==="delta"){ text+=e.text||""; if(LINE_EV===pk) out.innerHTML=paras(text); }
        else if(e.type==="error") throw new Error(e.error||"stream error"); }
      return (function pump(){ return rd.read().then(function(st){
        if(st.done){ buf+=dec.decode(); if(buf) line(buf); return; }
        buf+=dec.decode(st.value,{stream:true}); var i;
        while((i=buf.indexOf("\n"))!==-1){ line(buf.slice(0,i)); buf=buf.slice(i+1); }
        return pump(); }); })();
    })
    .then(function(){ if(text){ LINE_SUMS[pk.sig]=paras(text); } if(LINE_EV===pk) paintLineSum(); })
    .catch(function(e){ if(e.name==="AbortError") return;
      if(LINE_EV===pk){ out.innerHTML='<p class="sub">Couldn&rsquo;t write a summary: '+
        String(e.message).replace(/</g,"&lt;")+'</p>'; go.disabled=false; } });
}

/* Official season lines for a whole career, from the MLB Stats API (fetch_careers.py). They
   replace the block-summed line whenever they exist: they go back to a player's debut, and they
   are the published numbers, strikeout double plays included. */
var CAREERS={}, CAREERLOAD={};
function careerFor(id){
  var key=K;
  if(!CAREERS[key] && !CAREERLOAD[key]){
    CAREERLOAD[key]=fetch("/data/careers-"+key+".json")
      .then(function(x){ return x.ok?x.json():null; })
      .then(function(j){ CAREERS[key]=j||{fields:[],players:{}}; if(K===key && isShown("p-line")) renderLine(); })
      .catch(function(){ CAREERS[key]={fields:[],players:{}}; });
  }
  var C=CAREERS[key], p=C&&C.players[String(id)];
  if(!p||!p.s.length) return null;
  return p.s.map(function(s){ var m={}; C.fields.forEach(function(f,i){ m[f]=s[i]; }); return m; });
}
function officialCalc(g){
  if(K==="bat"){
    var ab=g("atBats"), h=g("hits"), bb=g("baseOnBalls"), hbp=g("hitByPitch"), sf=g("sacFlies");
    var tb=h+g("doubles")+2*g("triples")+3*g("homeRuns"), obpD=ab+bb+hbp+sf;
    var obp=obpD?(h+bb+hbp)/obpD:null, slg=ab?tb/ab:null;
    return {G:g("gamesPlayed"), PA:g("plateAppearances"), AB:ab, R:g("runs"), H:h, "2B":g("doubles"),
            "3B":g("triples"), HR:g("homeRuns"), RBI:g("rbi"), BB:bb, SO:g("strikeOuts"),
            SB:g("stolenBases"), AVG:ab?h/ab:null, OBP:obp, SLG:slg,
            OPS:(obp!=null&&slg!=null)?obp+slg:null};
  }
  var ip=g("outs")/3, bf=g("battersFaced");
  return {G:g("gamesPlayed"), GS:g("gamesStarted"), W:g("wins"), L:g("losses"), SV:g("saves"),
          IP:ip, H:g("hits"), HR:g("homeRuns"), BB:g("baseOnBalls"), SO:g("strikeOuts"),
          ERA:ip?9*g("earnedRuns")/ip:null, WHIP:ip?(g("baseOnBalls")+g("hits"))/ip:null,
          "K%":bf?g("strikeOuts")/bf:null, "BB%":bf?g("baseOnBalls")/bf:null};
}
function renderOfficialLine(r, seasons){
  var rows=seasons.map(function(s){
    return {lab:String(s.year), tm:s.team||"", v:officialCalc(function(k){ return s[k]||0; }),
            cls:s.year===YR?"hl":""}; });
  if(seasons.length>1){
    var tot=function(k){ return seasons.reduce(function(t,s){ return t+(s[k]||0); },0); };
    rows.push({lab:"Career ("+seasons.length+" seasons)", tm:"", v:officialCalc(tot), cls:"tot"});
  }
  var cols=Object.keys(rows[0].v), RATE={AVG:1,OBP:1,SLG:1,OPS:1}, PCT={"K%":1,"BB%":1};
  function cell(k,v){
    if(v==null) return "&mdash;";
    if(k==="IP") return fmtIP(v);
    if(RATE[k]) return D3(v);
    if(PCT[k]) return (100*v).toFixed(1)+"%";
    if(k==="WHIP"||k==="ERA") return v.toFixed(2);
    return Math.round(v).toLocaleString();
  }
  var h='<table class="line"><thead><tr><th class="l">season</th><th class="l">team</th>'+
        cols.map(function(c){return '<th>'+c+'</th>';}).join("")+'</tr></thead><tbody>';
  rows.forEach(function(rw){
    h+='<tr class="'+rw.cls+'"><td class="l">'+rw.lab+'</td><td class="l">'+rw.tm+'</td>'+
       cols.map(function(c){return '<td>'+cell(c,rw.v[c])+'</td>';}).join("")+'</tr>';
  });
  $("#line-table").innerHTML=h+'</tbody></table>';
  setLineEvidence(r, cols, rows, cell, true);
  $("#line-foot").innerHTML="Official MLB season lines (MLB Stats API), every season of his career"+
    (CAREERS[K]&&CAREERS[K].fetched?", fetched "+CAREERS[K].fetched:"")+". The current season "+
    "is as of that date. "+(K==="bat"
    ? "Position is the one he played in the most games in the pitch-tracking data; a hitter who "+
      "never took the field is listed as designated hitter."
    : "ERA and WHIP are per nine and per inning pitched.");
}
function renderLine(){
  var r=ROWS.find(function(x){return String(x.id)===String($("#g-who").value);});
  if(!r){ $("#line-meta").textContent="";
    $("#line-table").innerHTML=""; return; }
  // an old shard without the surface fields: say so rather than print zeros
  if(F.g==null){ $("#line-meta").textContent="";
    $("#line-table").innerHTML='<p class="note">This season\u2019s data predates the surface stats; '+
      're-run blocks_all.py to add them.</p>'; return; }
  var pos=r.pos?(POSNAME[r.pos]||r.pos):"";
  $("#line-meta").innerHTML=[r.tm, pos].filter(Boolean).join(" &middot; ");
  var all=[], i; for(i=0;i<BL.length;i++) all.push(i);

  var off=careerFor(r.id);
  if(off){ renderOfficialLine(r, off); return; }
  var hist=linesFor(r.id)||[];
  var seasons=hist.filter(function(s){ return s.y!==YR; })
    .concat([{y:YR, tm:r.tm, get:shardGetter(r,all)}])
    .sort(function(a,b){ return a.y-b.y; });
  var rows=seasons.map(function(s){
    return {lab:String(s.y), tm:s.tm||"", v:surfaceCalc(s.get), cls:s.y===YR?"hl":""}; });
  if(seasons.length>1){
    var tot=function(k){ return seasons.reduce(function(t,s){ return t+s.get(k); },0); };
    rows.push({lab:seasons.length+" seasons", tm:"", v:surfaceCalc(tot), cls:"tot"});
  }

  var cols=Object.keys(rows[0].v);
  var RATE={AVG:1,OBP:1,SLG:1,OPS:1,wOBA:1,"wOBA against":1};
  var PCT={"K%":1,"BB%":1};
  function cell(k,v){
    if(v==null) return "&mdash;";
    if(k==="IP") return fmtIP(v);
    if(RATE[k]) return D3(v);
    if(PCT[k]) return (100*v).toFixed(1)+"%";
    if(k==="WHIP") return v.toFixed(2);
    return Math.round(v).toLocaleString();
  }
  var h='<table class="line"><thead><tr><th class="l">season</th><th class="l">team</th>'+
        cols.map(function(c){return '<th>'+c+'</th>';}).join("")+'</tr></thead><tbody>';
  rows.forEach(function(rw){
    h+='<tr class="'+rw.cls+'"><td class="l">'+rw.lab+'</td><td class="l">'+rw.tm+'</td>'+
       cols.map(function(c){return '<td>'+cell(c,rw.v[c])+'</td>';}).join("")+'</tr>';
  });
  $("#line-table").innerHTML=h+'</tbody></table>';
  setLineEvidence(r, cols, rows, cell, false);
  $("#line-foot").innerHTML=(LINES[K]?"":"Loading earlier seasons&hellip; ")+
    "Seasons from 2023, when this data starts; a season below the site&rsquo;s playing-time floor "+
    "isn&rsquo;t listed. "+(K==="bat"
    ? "Position is the one he played in the most games; a hitter who never took the field is listed as designated hitter. "
    : "Innings can run a few outs short, because outs made on the bases aren&rsquo;t tied to a batter. ")+
    "Strikeouts can run one or two short of the official count.";
}

/* ===================== wiring ===================== */
var VIEWSTATE={};

/* Two tabs, each holding several sections (docs/SPEC-restructure.md). Every section kept the id
   its old tab had -- p-card, p-stretch, p-vs... -- so the renderers, which address their own
   elements by id, did not have to change. What changed is only what counts as "shown". */
var TABS=[["#t-player","#p-player",renderPlayer],
          ["#t-metric","#p-metric",renderMetric]];
var active=0;

// Which tab each section lives on. Also how an old per-tool link (#p-vs, #p-carry...) finds
// its new home: they are in the wild -- shared links, bookmarks, the landing page -- and must
// keep working.
var SECTION_TAB={"p-player":0,"p-line":0,"p-card":0,"p-stretch":0,"p-changes-mine":0,"p-vs":0,
                 "p-metric":1,"p-planner":1,"p-changes":1,"p-card-league":1,"p-carry":1,
                 "p-break":1,"p-vs-scored":1};

/* Each tab shows one analysis at a time, picked from a button row (D62). The Season line is not
   one of them: it heads the Player tab whatever analysis is open. RENDER is the only place that
   knows which function draws which analysis, so rendering a tab means rendering what's open. */
var SUBS=[["p-card","p-stretch","p-changes-mine","p-vs"],
          ["p-planner","p-changes","p-card-league","p-carry","p-break","p-vs-scored"]];
var RENDER={"p-card":function(){renderCard();}, "p-stretch":function(){renderStretch();},
            "p-changes-mine":function(){renderChanges();}, "p-vs":function(){renderVs();},
            "p-planner":function(){renderPlanner();}, "p-changes":function(){renderChanges();},
            "p-card-league":function(){renderHotCold();}, "p-carry":function(){renderCarry();},
            "p-break":function(){renderBreakouts();}, "p-vs-scored":function(){renderVsCal();}};
var sub=[SUBS[0][0], SUBS[1][0]];
function isShown(sid){
  if(SECTION_TAB[sid]!==active) return false;
  return sid===TABS[active][1].slice(1) || sid==="p-line" || sub[active]===sid;
}
// The summary follows the open analysis, where it has a builder; elsewhere it stands down.
function sumSection(i){ return window.SUM && SUM.build[sub[i]] ? sub[i] : null; }

var QUESTIONS={
  "p-player":"One player: how good he really is, what changed, and how much of it is luck.",
  "p-metric":"The whole league: who moved, who is streaking, and how much data it takes to know."
};

function initSubs(){
  [].forEach.call(document.querySelectorAll(".subtabs"),function(row){
    var t=+row.dataset.tab;
    row.innerHTML=SUBS[t].map(function(sid){
      var k=document.querySelector("#"+sid+" > .psec-k");
      document.getElementById(sid).classList.add("psec-pick");
      return '<button type="button" role="tab" data-sec="'+sid+'" aria-controls="'+sid+'">'+
             (k?k.innerHTML:sid)+'</button>';
    }).join("");
    row.addEventListener("click",function(e){
      var btn=e.target.closest("button[data-sec]"); if(!btn) return;
      pickSub(t, btn.dataset.sec);
    });
  });
  paintSubs();
}
function paintSubs(){
  SUBS.forEach(function(list,t){
    list.forEach(function(sid){ document.getElementById(sid).hidden = sub[t]!==sid; });
    var row=document.querySelector('.subtabs[data-tab="'+t+'"]'); if(!row) return;
    [].forEach.call(row.querySelectorAll("button"),function(b){
      b.setAttribute("aria-selected", b.dataset.sec===sub[t]?"true":"false"); });
  });
}
function writeHash(){
  try{ var want=sub[active];
       if(location.hash.slice(1).split("?")[0]!==want) history.replaceState(null,"","#"+want); }catch(e){}
}
// bring the analysis row to the top of the screen after a jump from inside another analysis
function scrollToSubs(){
  var row=document.querySelector('.subtabs[data-tab="'+active+'"]');
  if(row) window.scrollTo({top:row.getBoundingClientRect().top+window.scrollY-12});
}
function pickSub(t, sid){
  sub[t]=sid; paintSubs();
  if(t!==active) return show(t);
  writeHash();
  TABS[active][2]();
  if(window.SUM) SUM.mount(sumSection(active));
}

function fillGlobalPickers(){
  // the shared player picker carries the same list, and the same default, as the old ones
  var gw=$("#g-who"), src=$("#pc-who");
  if(gw && src && gw.dataset.sig!==K+"|"+YR+"|"+src.options.length){
    var keepW=gw.value;
    gw.innerHTML=src.innerHTML;
    [].forEach.call(gw.options,function(o){ o.textContent=o.textContent.replace(/\s*\([\d,]+ (?:PA|BF|batters faced)\)\s*$/,""); });
    gw.value=[].some.call(gw.options,function(o){return o.value===keepW;})?keepW:src.value;
    gw.dataset.sig=K+"|"+YR+"|"+src.options.length;
  }
}
function syncPlayer(){
  var id=$("#g-who").value;
  ["#who","#pc-who","#c-who","#vs-a"].forEach(function(s){
    var e=$(s); if(e && [].some.call(e.options,function(o){return o.value===id;})) e.value=id; });
  if($("#pc-win")) $("#pc-win").value=$("#g-win").value;
}

function renderPlayer(){
  fillGlobalPickers(); syncPlayer();
  var me=ROWS.find(function(r){return String(r.id)===String($("#g-who").value);});
  $("#g-note").textContent=me?"":"Pick a player";
  renderLine(); RENDER[sub[0]]();
}
function renderMetric(){ fillGlobalPickers(); RENDER[sub[1]](); }

/* The global bar is Type and Season only; every analysis that needs a metric carries its own
   picker. Streak history -- the one fixed study -- says so in its own section. */
function paintGlobalBar(){
  $("#gbar-says").textContent="applies to both tabs";
  var gn=$("#globalnote"); if(gn) gn.hidden=false;
}

function show(i, sid){
  active=i;
  document.body.setAttribute("data-tab", i===0?"player":"league");
  if(sid && SUBS[i].indexOf(sid)>=0) sub[i]=sid;
  paintSubs();
  TABS.forEach(function(t,j){
    $(t[0]).setAttribute("aria-selected", j===i?"true":"false");
    $(t[1]).hidden = j!==i;
  });
  writeHash();
  if(window.onTabShow) window.onTabShow(TABS[i][1].slice(1), i);
  var q=$("#view-q"); if(q) q.textContent=QUESTIONS[TABS[i][1].slice(1)]||"";
  paintGlobalBar();
  TABS[i][2]();
  if(sid==="p-line"){ var el=document.getElementById(sid); if(el) el.scrollIntoView({block:"start"}); }
  // after the renderer, not before: listeners read VIEWSTATE, and the renderer writes it
  try{ document.dispatchEvent(new CustomEvent("tabshow",
        {detail:{panel:sumSection(i), index:i}})); }catch(e){}
}
function renderAll(){ TABS[active][2](); if(window.SUM) SUM.reset(); }
function rerender(sid, fn){ return function(){ if(isShown(sid)){ fn(); if(window.SUM) SUM.reset(); } }; }

TABS.forEach(function(t,i){ $(t[0]).addEventListener("click",function(){show(i);}); });
kindS.addEventListener("change",function(){setKind();});
yrS.addEventListener("change",function(){setYear();});
$("#g-who").addEventListener("change",function(){ if(active===0) renderAll(); });
$("#g-win").addEventListener("change", rerender("p-card", function(){
  $("#pc-win").value=$("#g-win").value; renderCard(); }));

["#who","#from","#to","#mode"].forEach(function(s){
  $(s).addEventListener("change", rerender("p-stretch", renderStretch)); });
["#c-who","#c-win","#c-z","#c-metric","#c-dir","#c-n","#c-sort","#c-conf"].forEach(function(s){
  $(s).addEventListener("change", function(){ renderChanges(); if(window.SUM) SUM.reset(); }); });
$("#b-base").addEventListener("change", rerender("p-break", renderBreakouts));
["#hc-dir","#hc-min"].forEach(function(s){
  $(s).addEventListener("change", rerender("p-card-league", renderHotCold)); });
$("#pc-win").addEventListener("change", function(){
  $("#g-win").value=$("#pc-win").value; renderHotCold(); if(isShown("p-card")) renderCard(); });

// a name on the League tab's hot/cold board opens that player on the Player tab
function openPlayer(id){
  var g=$("#g-who"); if(g && [].some.call(g.options,function(o){return o.value===String(id);})) g.value=id;
  show(0, "p-card");
}
$("#hc-foot").addEventListener("click",function(e){
  var a=e.target.closest(".hc-back"); if(!a) return; e.preventDefault(); openPlayer(a.dataset.id); });
$("#hc-board").addEventListener("click",function(e){
  var more=e.target.closest(".hc-more");
  if(more){ e.preventDefault(); var k="_all_"+more.dataset.kind;
    $("#hc-board")[k]=!$("#hc-board")[k]; renderHotCold(); return; }
  var tr=e.target.closest(".hc-row"); if(!tr) return;
  e.preventDefault(); openPlayer(tr.dataset.id);
});
["#pl-m","#pl-t","#pl-d","#pl-b"].forEach(function(s){
  $(s).addEventListener("input", rerender("p-planner", renderPlanner)); });
$("#k-sort").addEventListener("input", rerender("p-carry", renderCarry));
$("#k-asof").addEventListener("input", rerender("p-carry", renderCarry));
$("#vsc-h").addEventListener("input", rerender("p-vs-scored", renderVsCal));
["#vs-a","#vs-b","#vs-h","#vs-asof","#vs-pa-a","#vs-pa-b"].forEach(function(s){
  $(s).addEventListener("input", rerender("p-vs", renderVs)); });

// "#p-vs", "#p-metric", "#p-card?k=bat&id=608324" -> {tab, section}
function fromHash(){
  var h=location.hash.slice(1).split("?")[0];
  return h in SECTION_TAB ? {tab:SECTION_TAB[h], section:h} : null;
}
// An old landing-page link arrives as #p-card?k=bat&id=608324. Read it once, before boot, so
// the right player type loads first; setYear() consumes the id when the list is filled.
function readHQ(){
  var o={}; (location.hash.split("?")[1]||"").split("&").forEach(function(kv){
    var p=kv.split("="); if(p[0]) o[p[0]]=decodeURIComponent(p[1]||""); });
  return o;
}
var HQ=readHQ();
if(HQ.k==="bat"||HQ.k==="pit") kindS.value=HQ.k;
var h0=fromHash(), SCROLL0=h0&&h0.section!==TABS[h0.tab][1].slice(1)?h0.section:null;
if(h0 && SUBS[h0.tab].indexOf(h0.section)>=0) sub[h0.tab]=h0.section;
initSubs();
document.body.setAttribute("data-tab", (h0&&h0.tab>0)?"league":"player");
$("#line-sum-go").addEventListener("click", runLineSum);
if(h0&&h0.tab>0){ active=h0.tab;            // set the tab, don't render: no data yet
  TABS.forEach(function(t,j){
    $(t[0]).setAttribute("aria-selected", j===h0.tab?"true":"false");
    $(t[1]).hidden = j!==h0.tab; }); }
window.addEventListener("hashchange",function(){
  var q=readHQ(), where=fromHash();
  if(q.id){
    // a player link opens the Player tab even when it also switches the player type
    if((q.k==="bat"||q.k==="pit") && q.k!==K){ HQ=q; kindS.value=q.k; show(0,"p-card"); setKind(); return; }
    openPlayer(q.id); return;
  }
  if(where && (where.tab!==active || (SUBS[where.tab].indexOf(where.section)>=0 && where.section!==sub[where.tab])))
    show(where.tab, where.section);
});

var ENDPOINT = "/api/summary";
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

SUM.mount(sumSection(active));
boot();
})();


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
