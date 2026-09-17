/* ===========================================================================
   Statcast Stretch Finder -- client.
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
var PAKEY={bat:"pa",pit:"bf"}, PANAME={bat:"PA",pit:"BF"},
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
  $("#who").innerHTML=opts; $("#c-who").innerHTML=opts;
  var yb=yearBlocks(y);
  $("#from").innerHTML=yb.map(function(i){return '<option value="'+i+'">'+lbl(BL[i])+'</option>';}).join("");
  $("#to").innerHTML=yb.map(function(i){return '<option value="'+i+'">'+lblEnd(BL[i])+'</option>';}).join("");
  $("#from").value=yb[Math.max(0,yb.length-4)]; $("#to").value=yb[yb.length-1];
  // Open on a player the stored-profile fallback can actually write about, so the
  // first thing a visitor without a key clicks does something.
  var pref=K==="bat"?"608324":"656302";
  if(ROWS.some(function(r){return String(r.id)===pref;})) $("#who").value=pref;
  $("#globalnote").textContent=ROWS.length+" qualified "+(K==="bat"?"hitters":"pitchers")+
    " in "+y+" · "+yb.length+" half-month blocks";
  renderAll();
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
function renderStretch(){
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
  $("#warn").innerHTML = myN<1 ? "<b>No appearances in this span.</b>" :
    "At <b>"+myN.toFixed(0)+" "+PALONG[K]+"</b>, a results percentile here is about <b>"+
    Math.round(100*rRes)+"% signal</b> and a "+(K==="bat"?"bat-speed":"velocity")+
    " percentile is about <b>"+Math.round(100*rBody)+"% signal</b>. Compared against "+
    peers.length+" others in the same span.";

  var html="", groups=[];
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
      var rel=relAt(m.k,myN), adj=50+rel*(raw-50), hot=adj>=50,
          col=hot?"var(--hot)":"var(--cold)", wA=Math.abs(adj-50), wR=Math.abs(raw-50),
          side=raw>=50?"left:50%;width:":"right:50%;width:";
      html+='<div class="row"><span class="nm">'+m.k+' <span class="relchip">'+
        Math.round(100*rel)+'% real</span></span><span class="val">'+m.f(v)+
        '</span><span class="bar"><span class="ghost" style="'+side+wR+'%;color:'+
        (raw>=50?"var(--hot)":"var(--cold)")+'"></span><span class="fill" style="'+
        (hot?"left:50%;width:":"right:50%;width:")+wA+'%;background:'+col+
        '"></span><span class="mk"></span></span><span class="pct" style="color:'+col+'">'+
        Math.round(adj)+'<span class="rawpct">'+Math.round(raw)+'</span></span></div>';
    });
    html+='</div>';
  });
  $("#bars").innerHTML=html;
  if(window.aiReset) aiReset();
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
    "Distance is weighted by each dimension's reliability <em>at this sample size</em>, so short "+
    "spans automatically lean on the body and all but ignore results. The closest match is <b>"+
    (med/top[0].d).toFixed(1)+"× closer than the median candidate</b> — searching "+
    scored.length.toLocaleString()+" stretches will always surface something similar, so that "+
    "ratio is the number to judge, not the list."+
    (thin?" "+thin.toLocaleString()+" were dropped for missing too many tracked dimensions; bat "+
     "tracking only begins mid-2023 and a candidate scored on fewer dimensions looks "+
     "artificially close.":"") : "Not enough comparable stretches.";
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
function changeSet(){
  var W=+$("#c-win").value, ZMIN=+$("#c-z").value, y=+yrS.value, yb=yearBlocks(y);
  var minNow=W*25, minBase=Math.max(60,W*40);
  var out=[], sdCache={};
  for(var s=2;s+W<=yb.length;s++){
    var now=yb.slice(s,s+W), base=yb.slice(0,s), nxt=yb.slice(s+W,s+2*W);
    var key=s+"|"+W;
    var sums=ROWS.map(function(r){
      return {r:r, now:sumList(r,now), base:sumList(r,base),
              nxt:nxt.length===W?sumList(r,nxt):null}; });
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
        if(x.nxt && x.nxt[F[m.d]]>=W*10 && Math.abs(v-b0)>1e-9)
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
    '<th>&Delta;</th><th>z</th><th>sd</th><th>% real</th><th>held</th></tr></thead><tbody>';
  rows.slice(0,limit).forEach(function(o){
    var cls=o.z>0?"up":"dn";
    h+='<tr>'+(showPlayer?'<td class="l">'+o.p+'</td>':'')+
      '<td class="l">'+o.m+'</td><td class="l">'+sh(BL[o.a])+'–'+sh(BL[o.b])+'</td>'+
      '<td>'+o.f.f(o.base)+'</td><td>'+o.f.f(o.v)+'</td>'+
      '<td class="'+cls+'">'+(o.v-o.base>0?"+":"")+o.f.f(o.v-o.base)+'</td>'+
      '<td class="'+cls+'">'+o.z.toFixed(1)+'</td>'+
      '<td>'+(o.sdu>0?"+":"")+o.sdu.toFixed(1)+'</td>'+
      '<td>'+Math.round(100*o.rel)+'</td>'+
      '<td>'+(o.held===null?'<span class="chip">no next</span>':
        '<span class="chip '+(o.held>=0.5?"ok":"no")+'">'+Math.round(100*o.held)+'%</span>')+
      '</td></tr>';
  });
  return h+'</tbody></table>';
}
function applyFilters(rows){
  var met=$("#c-metric").value, dir=$("#c-dir").value,
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
    ms.innerHTML='<option value="all">all metrics</option>'+
      INPUTS[K].map(function(l){return '<option value="'+l+'">'+l+'</option>';}).join("");
    ms.dataset.kind=K;
  }
  var all=applyFilters(raw);
  var mine=all.filter(function(o){return String(o.id)===String(pid);});
  $("#c-hits").textContent = all.length.toLocaleString()+" of "+raw.length.toLocaleString()+" moves";
  var me=ROWS.find(function(r){return String(r.id)===String(pid);});
  $("#c-title").textContent=(me?me.n:"—")+" — moves against his own prior blocks";
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
  var testable=all.filter(function(o){return o.held!==null;});
  var confirmed=testable.filter(function(o){return o.held>=0.5;});
  $("#c-boardnote").innerHTML="<b>"+all.length.toLocaleString()+"</b> moves match these filters in "+
    yrS.value+" across "+ROWS.length+" "+(K==="bat"?"hitters":"pitchers")+". Of the "+
    testable.length.toLocaleString()+" with a following window, <b>"+
    (testable.length?Math.round(100*confirmed.length/testable.length):0)+
    "% held at least half the move.</b> A coin would hold about half of nothing; this is the "+
    "out-of-sample check that makes the column worth reading.";
  $("#c-board").innerHTML=moveTable(all,40,true);
}

/* ===================== TAB 3: what carries ===================== */
function renderCarry(){
  var y=+yrS.value, yb=yearBlocks(y);
  if(yb.length<4){ $("#k-board").innerHTML=""; return; }
  var now=yb.slice(-2), base=yb.slice(0,-2), C=CARRY[K], B=C.beta;
  var board=[];
  ROWS.forEach(function(r){
    var vn=sumList(r,now), vb=sumList(r,base);
    var n=vn[F[PK]], bn=vb[F[PK]];
    if(n<50||bn<150) return;
    var w=vn[F.wn]/n, x=vn[F.xn]/n, wb=vb[F.wn]/bn, xb=vb[F.xn]/bn;
    var pred=B[0]+B[1]*w+B[2]*wb+B[3]*x+B[4]*xb;
    var gap=w-wb;
    board.push({r:r,n:n,bn:bn,w:w,x:x,wb:wb,xb:xb,pred:pred,gap:gap,
                carry:Math.abs(gap)>1e-6?(pred-wb)/gap:0});
  });
  board.sort(function(a,b){return Math.abs(b.gap)-Math.abs(a.gap);});
  var wo=K==="bat"?"wOBA":"wOBA allowed";
  $("#k-title").textContent="How much of each streak is expected to survive — "+
    lbl(BL[now[0]])+" to "+lblEnd(BL[now[1]])+" "+y;
  $("#k-lede").innerHTML="Every "+(K==="bat"?"hitter":"pitcher")+" with at least 50 "+PANAME[K]+
    " in the last month and 150 before it, sorted by how far his "+wo+" has moved from his own "+
    "earlier-season rate. <b>Expect</b> is the model's forecast of the next month expressed as a "+
    "gap from that same baseline; <b>carry</b> is the ratio. It is not a prediction that he will "+
    "cool off by a specific amount — it is the fraction of the gap that has historically "+
    "survived a month.";
  $("#k-tiles").innerHTML=
    tile("Out-of-sample R²", C.r2.toFixed(4), "2026 holdout, fit on 2023–2025, "+
         C.ntr.toLocaleString()+" train / "+C.nte.toLocaleString()+" test windows")+
    tile("Ceiling", C.ceil.toFixed(4), "var(true)/var(observed) at this target length — no "+
         "model can beat this")+
    tile("Share of what exists", Math.round(100*C.r2/C.ceil)+"%", "the only honest way to read "+
         "the R² to its left")+
    tile("Recent "+wo+" alone", C.naive.toFixed(4), "R² from last month's results and the "+
         "prior baseline, with no expected stats — "+
         (C.naive<0.01?"indistinguishable from guessing the mean":"barely better than the mean"));
  var h='<table><thead><tr><th class="l">player</th><th>'+PANAME[K]+'</th><th>'+wo+
    '</th><th>x'+(K==="bat"?"wOBA":"wOBA")+'</th><th>prior</th><th>gap</th><th>expect</th>'+
    '<th>carry</th></tr></thead><tbody>';
  board.slice(0,30).forEach(function(b){
    var cls=b.gap>0?"up":"dn";
    h+='<tr><td class="l">'+b.r.n+'</td><td>'+b.n.toFixed(0)+'</td><td>'+D3(b.w)+
      '</td><td>'+D3(b.x)+'</td><td>'+D3(b.wb)+'</td>'+
      '<td class="'+cls+'">'+(b.gap>0?"+":"")+D3(b.gap)+'</td>'+
      '<td class="'+cls+'">'+(b.pred-b.wb>0?"+":"")+D3(b.pred-b.wb)+'</td>'+
      '<td>'+Math.round(100*b.carry)+'%</td></tr>';
  });
  $("#k-board").innerHTML=h+'</tbody></table>';
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
  var L=leagueSD();
  var sel=$("#pl-m");
  if(sel.dataset.kind!==K){
    sel.innerHTML=MET.filter(function(m){return REL[m.k]&&L[m.k];})
      .map(function(m){return '<option value="'+m.k+'">'+m.k+'</option>';}).join("");
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
  $("#pl-tiles").innerHTML=
    tile("Measured reliability", p.toFixed(3), "split-half at n₀ = "+Math.round(n0)+" "+U+
         ", "+L[m.k].n.toLocaleString()+" player-seasons")+
    tile(Math.round(100*t)+"% real at", num(nRel)+" "+U,
         "solve ρ(n) = "+t+" for n; a full hitter season is about 600 PA")+
    (n80===Infinity
      ? tile("Detect "+$("#pl-d").value+" "+m.u, "not possible",
          "against a "+baseline.toLocaleString()+"-"+U+" baseline. The baseline itself must exceed "+
          num(Cknown)+" "+U+" before any follow-up window resolves a difference this small — "+
          "lengthen the baseline, do not watch longer.", true)
      : tile("Detect "+$("#pl-d").value+" "+m.u, num(n80)+" "+U,
          "α = .05 two-sided, power 80%"+(baseline?", against a "+baseline.toLocaleString()+
          "-"+U+" baseline":", baseline treated as known")))+
    (n90===Infinity?"":tile("At 90% power", num(n90)+" "+U, "the same test, less willing to miss"));

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
  var h='<table><thead><tr><th class="l">metric</th><th>reliability at n₀</th>'+
    '<th>'+U+' for 50% real</th><th>70%</th><th>80%</th><th>90%</th></tr></thead><tbody>';
  MET.filter(function(mm){return REL[mm.k];}).forEach(function(mm){
    var rr=REL[mm.k];
    h+='<tr'+(mm.k===m.k?' style="background:var(--sunk)"':'')+'><td class="l">'+mm.k+
      '</td><td>'+rr.sb.toFixed(3)+'</td>'+
      [0.5,0.7,0.8,0.9].map(function(tt){
        return '<td>'+Math.round(nForRel(rr.sb,rr.n0,tt)).toLocaleString()+'</td>';}).join("")+
      '</tr>';
  });
  $("#pl-table").innerHTML=h+'</tbody></table>';
}

/* ===================== wiring ===================== */
var TABS=[["#t-stretch","#p-stretch",renderStretch],
          ["#t-changes","#p-changes",renderChanges],
          ["#t-carry","#p-carry",renderCarry],
          ["#t-planner","#p-planner",renderPlanner]];
var active=0;
function show(i){
  active=i;
  TABS.forEach(function(t,j){
    $(t[0]).setAttribute("aria-selected", j===i?"true":"false");
    $(t[1]).hidden = j!==i;
  });
  // A tab is a place. Rewriting the hash makes any view a link you can send
  // someone, and gives the browser Back button something to do. replaceState
  // throws inside a sandboxed iframe, which is where the artifact build runs,
  // so it is allowed to fail without taking the tab switch with it.
  try{ if(location.hash.slice(1)!==TABS[i][1].slice(1))
         history.replaceState(null,"",TABS[i][1]); }catch(e){}
  // The deployed site has a second copy of this control in its masthead. It
  // subscribes here instead of reaching into TABS, so the two can never disagree
  // about which tab is open regardless of which one you clicked.
  if(window.onTabShow) window.onTabShow(TABS[i][1].slice(1), i);
  TABS[i][2]();
}
function renderAll(){ TABS[active][2](); }
TABS.forEach(function(t,i){ $(t[0]).addEventListener("click",function(){show(i);}); });
kindS.addEventListener("change",function(){setKind();});
yrS.addEventListener("change",function(){setYear();});
["#who","#from","#to","#mode"].forEach(function(s){
  $(s).addEventListener("change",function(){ if(active===0) renderStretch(); }); });
["#c-who","#c-win","#c-z","#c-metric","#c-dir","#c-n","#c-sort","#c-conf"].forEach(function(s){
  $(s).addEventListener("change",function(){ if(active===1) renderChanges(); }); });
["#pl-m","#pl-t","#pl-d","#pl-b"].forEach(function(s){
  $(s).addEventListener("input",function(){ if(active===3) renderPlanner(); }); });
function tabFromHash(){
  for(var i=0;i<TABS.length;i++)
    if(TABS[i][1].slice(1)===location.hash.slice(1)) return i;
  return -1;
}
var h0=tabFromHash();
if(h0>0){ active=h0;                     // set the tab, don't render: no data yet
  TABS.forEach(function(t,j){
    $(t[0]).setAttribute("aria-selected", j===h0?"true":"false");
    $(t[1]).hidden = j!==h0; }); }
window.addEventListener("hashchange",function(){
  var i=tabFromHash(); if(i>=0 && i!==active) show(i); });

/* ===================== the generated profile ===================== */
var PANAME_LONG = {bat:"plate appearances", pit:"batters faced"};
var aiTimer = null, aiCtl = null;

function evTable(rows){
  var h='<table><thead><tr><th class="l">metric</th><th>value</th><th>pct raw</th>'+
    '<th>% real</th><th>pct shrunk</th><th>baseline</th><th>&Delta;</th><th>z</th>'+
    '<th>sd</th><th class="l">verdict</th></tr></thead><tbody>';
  rows.forEach(function(r){
    if(!r.available) return;
    var m=getM(r.metric); if(!m) return; var f=m.f, c=r.change;
    h+='<tr><td class="l">'+r.metric+'</td><td>'+f(r.value)+'</td><td>'+Math.round(r.pct_raw)+
      '</td><td>'+Math.round(100*r.reliability)+'</td><td>'+Math.round(r.pct_shrunk)+'</td>'+
      (!c ? '<td>&mdash;</td><td>&mdash;</td><td>&mdash;</td><td>&mdash;</td><td class="l">&mdash;</td>'
          : '<td>'+f(c.base_value)+'</td><td>'+(c.delta>0?"+":"")+f(c.delta)+'</td><td>'+
            c.delta_z.toFixed(2)+'</td><td>'+(c.delta_sd>0?"+":"")+c.delta_sd.toFixed(2)+'</td>'+
            '<td class="l vd '+c.verdict+'">'+c.verdict+' / '+c.size+'</td>')+'</tr>';
  });
  return h+'</tbody></table>';
}

function currentPacket(){
  var me=ROWS.find(function(r){return String(r.id)===String($("#who").value);});
  if(!me) return null;
  var shard=ALL[shardKey(K,YR)];
  var metrics=MET.map(function(m){return {k:m.k,n:m.n,d:m.d,hi:m.hi,g:m.g};});
  return Packet.build(shard, metrics, PK, me.id, BL[+$("#from").value], BL[+$("#to").value]);
}

function aiReset(){
  if(aiTimer){clearTimeout(aiTimer);aiTimer=null;}
  if(aiCtl){aiCtl.abort();aiCtl=null;}
  var pk=null; try{ pk=currentPacket(); }catch(e){}
  $("#ai-sub").textContent = pk
    ? pk.span.n+" "+PANAME_LONG[K]+" · "+pk.metrics.filter(function(m){return m.available;}).length+
      " metrics · generated server-side"
    : "—";
  $("#ai-again").hidden=true;
  $("#ai-go").disabled=false;
  $("#ai-body").innerHTML='<p class="ai-idle">The button posts this window to '+
    '<code>POST /api/profile</code>. That function rebuilds the packet below with the same '+
    '<code>lib/packet.js</code> the table uses, sends it to the model behind a system prompt '+
    'distilled from this project’s own retractions, and returns prose. '+
    '<code>ANTHROPIC_API_KEY</code> never leaves the server.</p>';
  if(pk) $("#ai-ev").innerHTML=evTable(pk.metrics);
}

function aiRun(){
  var pk; try{ pk=currentPacket(); }catch(e){ return; }
  if(!pk) return;
  $("#ai-go").disabled=true;
  var reduce=window.matchMedia&&window.matchMedia("(prefers-reduced-motion:reduce)").matches;
  var steps=["building the evidence packet …",
             "shrinking "+pk.metrics.length+" percentiles at "+pk.span.n+" "+PANAME[K]+" …",
             "POST /api/profile …"];
  $("#ai-body").innerHTML='<div class="status">'+steps.map(function(s,i){
      return '<span id="st'+i+'">'+(i?"  ":"› ")+s+'</span>';}).join("")+'</div>'+
    '<div class="skel" style="width:96%"></div><div class="skel" style="width:88%"></div>'+
    '<div class="skel" style="width:92%"></div><div class="skel" style="width:54%"></div>';
  var k=0;
  (function step(){ var el=$("#st"+k); if(el) el.className="on"; k++;
    if(k<steps.length) aiTimer=setTimeout(step, reduce?1:380); })();

  aiCtl=new AbortController();
  var t0=performance.now();
  fetch("/api/profile",{method:"POST",headers:{"content-type":"application/json"},
                        body:JSON.stringify({kind:K,packet:pk}),signal:aiCtl.signal})
    .then(function(r){ return r.json().then(function(j){ if(!r.ok) throw new Error(j.error||("HTTP "+r.status)); return j; }); })
    .then(function(j){ render(j, performance.now()-t0); })
    .catch(function(e){
      if(e.name==="AbortError") return;
      $("#ai-body").innerHTML='<p class="ai-idle"><b>The profile call failed.</b> '+e.message+
        '<br><br>Locally this usually means <code>ANTHROPIC_API_KEY</code> is not exported, in which '+
        'case <code>serve.py</code> falls back to a stored profile and only knows four players. '+
        'On Vercel it means the environment variable is not set on the project.</p>';
      $("#ai-go").disabled=false;
    });
}

function render(j, ms){
  var paras=(j.profile||"").trim().split(/\n{2,}/);
  var u=j.usage||{};
  var meter='<div class="meter"><span><b>'+(j.model||"model")+'</b></span>'+
    (u.input_tokens?'<span>'+u.input_tokens.toLocaleString()+' in'+
      (u.cache_read_input_tokens?' ('+u.cache_read_input_tokens.toLocaleString()+' cached at 0.1×)':'')+
      ' · '+(u.output_tokens||0)+' out</span>':'')+
    (j.cost!=null?'<span><b>$'+j.cost.toFixed(4)+'</b></span>':'')+
    '<span>'+(ms/1000).toFixed(1)+'s</span>'+
    (j.source==="stored"?'<span style="color:var(--hot)">stored profile — no API key set</span>'
                        :'<span>key server-side</span>')+'</div>';
  $("#ai-body").innerHTML='<div class="prose">'+paras.map(function(p){return '<p>'+p+'</p>';}).join("")+
    '</div>'+meter;
  $("#ai-again").hidden=false;
  $("#ai-go").disabled=false;
}

$("#ai-go").addEventListener("click",aiRun);
$("#ai-again").addEventListener("click",function(){ aiReset(); aiRun(); });

window.aiReset=aiReset;
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
