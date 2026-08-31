# -*- coding: utf-8 -*-
"""Render the verified boundaries + state metrics into a standalone HTML map.

Self-contained on purpose: geometry and data are inlined, so the page can be
opened directly and inspected before anything is committed. Numeric verification
proved the boundary file is administratively correct; only looking at it proves
the projection, winding and paths are right.

Colour follows the data-viz reference palette: a single-hue sequential RED ramp
(100 -> 700) for magnitude. Red reads as risk/danger; the original blue ramp
tested as "looks like water" in a team review and was replaced. Light and dark
modes carry separate ramps (dark's anchor flips toward the dark surface and
brightens toward the high end, rather than reusing light steps on black).
Blue is freed up entirely as the UI's interaction accent (hover ring,
selection ring, focus ring) now that it no longer encodes data. Both ramps are
computed, not eyeballed: build_red_ramp.mjs matches each step's OKLCH
lightness to the retired blue ramp exactly, rotates hue to the palette's
categorical red (#e34948), and holds chroma to the sRGB gamut ceiling.
"""
import io
import json
import math
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
GEO = os.path.join(HERE, "india_states.simplified.geojson")
MET = os.path.join(HERE, "state_metrics.json")
OUT = os.path.join(HERE, "india_map.html")

geo = json.load(open(GEO, encoding="utf-8"))
met = json.load(open(MET, encoding="utf-8"))
cls = json.load(open(os.path.join(HERE, "state_ut_classification.json"), encoding="utf-8"))
UTS = set(cls["union_territories"])
assert len(cls["states"]) == 28 and len(UTS) == 8, "expected 28 states + 8 UTs"

W, H, PAD = 760, 820, 16


def merc(lon, lat):
    lat = max(min(lat, 85.0), -85.0)
    return math.radians(lon), math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


# world bounds of the whole collection, so every state shares one projection
xs, ys = [], []


def walk(c, fn):
    if isinstance(c, (list, tuple)):
        if c and isinstance(c[0], (int, float)):
            fn(c)
        else:
            for i in c:
                walk(i, fn)


for f in geo["features"]:
    walk(f["geometry"]["coordinates"], lambda p: (xs.append(merc(p[0], p[1])[0]),
                                                  ys.append(merc(p[0], p[1])[1])))
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
sx = (W - 2 * PAD) / (x1 - x0)
sy = (H - 2 * PAD) / (y1 - y0)
K = min(sx, sy)
ox = PAD + ((W - 2 * PAD) - (x1 - x0) * K) / 2
oy = PAD + ((H - 2 * PAD) - (y1 - y0) * K) / 2


def proj(lon, lat):
    mx, my = merc(lon, lat)
    return (ox + (mx - x0) * K, oy + (y1 - my) * K)


def ring_path(ring):
    d = []
    for i, p in enumerate(ring):
        X, Y = proj(p[0], p[1])
        d.append(("M" if i == 0 else "L") + "%.1f %.1f" % (X, Y))
    return "".join(d) + "Z"


paths = {}
centroids = {}
for f in geo["features"]:
    name = f["properties"]["state"]
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    d, ax, ay, an = [], 0.0, 0.0, 0
    best_area, best_c = -1, None
    for poly in polys:
        for ri, ring in enumerate(poly):
            d.append(ring_path(ring))
            if ri == 0:
                pts = [proj(p[0], p[1]) for p in ring]
                a = abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1]
                            for i in range(len(pts)))) / 2
                if a > best_area:
                    best_area = a
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    best_c = (cx, cy)
    paths[name] = "".join(d)
    centroids[name] = best_c or (0, 0)

def poly_area(pts):
    return abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1]
                   for i in range(len(pts)))) / 2


# A choropleth silently hides small geographies. Delhi renders at ~89 px^2 and
# Chandigarh at ~8 px^2 - unreadable and unclickable - so they get inset tiles
# instead of being lost. 9 of 36 fall below the threshold, carrying 96 projects.
areas = {}
for f in geo["features"]:
    nm = f["properties"]["state"]
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    areas[nm] = sum(poly_area([proj(q[0], q[1]) for q in poly[0]]) for poly in polys)
SMALL_PX = 600
small = sorted([n for n, a in areas.items() if a < SMALL_PX], key=lambda n: areas[n])

payload = {
    "paths": paths,
    "small": small,
    "areas": {k: round(v) for k, v in areas.items()},
    "centroids": {k: [round(v[0], 1), round(v[1], 1)] for k, v in centroids.items()},
    "kind": {n: ("UT" if n in UTS else "State") for n in paths},
    "metrics": met["states"],
    "meta": met["meta"],
    "w": W, "h": H,
}

RAMP_LIGHT = ["#fdd5d0", "#ffbeb7", "#f7aba4", "#ea9a93", "#e4857e", "#dd716a",
              "#d75853", "#c74845", "#b13f3c", "#9e3432", "#892b2a", "#762221", "#621b1a"]
RAMP_DARK = ["#391917", "#4a1e1c", "#5d2220", "#702725", "#832a29", "#972e2d",
             "#ab3131", "#c03436", "#cf4040", "#de4e4c", "#ec5b57", "#fa6863", "#fc8079"]

html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PAIMANA - State Risk Map</title>
<style>
:root{
  color-scheme:light;
  --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e;
  --line:#e3e3df; --null:#ececea; --stroke:#fcfcfb;
  --accent:#2a78d6; --accent-wash:rgba(42,120,214,.14);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --surface:#1a1a19; --plane:#0d0d0d; --ink:#fff; --ink2:#c3c2b7;
    --line:#2e2e2c; --null:#232322; --stroke:#1a1a19;
    --accent:#3987e5; --accent-wash:rgba(57,135,229,.22);
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --surface:#1a1a19; --plane:#0d0d0d; --ink:#fff; --ink2:#c3c2b7;
  --line:#2e2e2c; --null:#232322; --stroke:#1a1a19;
  --accent:#3987e5; --accent-wash:rgba(57,135,229,.22);
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
  font:14px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:22px 18px 60px}
h1{font-size:19px;margin:0 0 2px;letter-spacing:-.01em}
.sub{color:var(--ink2);font-size:12.5px;margin:0 0 16px}
.controls{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
button.m{padding:6px 11px;border:1px solid var(--line);background:var(--surface);
  color:var(--ink2);border-radius:7px;cursor:pointer;font:inherit;font-size:12.5px}
button.m[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
button.m:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:20px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px}
svg{width:100%;height:auto;display:block}
path.st{stroke:var(--stroke);stroke-width:.6;cursor:pointer;
  transition:stroke .12s,stroke-width .12s,filter .12s,opacity .12s}
path.st:hover{stroke:var(--accent);stroke-width:2;filter:brightness(1.1)}
path.st.sel{stroke:var(--accent);stroke-width:3;
  filter:drop-shadow(0 0 4px var(--accent-wash)) brightness(1.08)}
path.st:focus-visible{outline:none;stroke:var(--accent);stroke-width:2.6}
svg.has-sel path.st:not(.sel):not(:hover){opacity:.5}
.legend{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:11.5px;color:var(--ink2)}
.legend .bar{display:flex;height:11px;flex:1;border-radius:3px;overflow:hidden}
.legend .bar i{flex:1}
.legendCap{font-size:11px;color:var(--ink2);margin-top:5px}
.dtHead{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:12px}
.dtKind{font-size:11px;color:var(--ink2);text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px}
.dtName{font-size:18px;font-weight:700;letter-spacing:-.01em}
.dtClose{border:1px solid var(--line);background:var(--surface);color:var(--ink2);
  border-radius:7px;width:26px;height:26px;cursor:pointer;font:inherit;line-height:1;flex:none}
.dtClose:hover{border-color:var(--accent);color:var(--accent)}
.dtGrid{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.dtStat{border:1px solid var(--line);border-radius:9px;padding:8px 10px}
.dtStat .lb{font-size:10.5px;color:var(--ink2);margin-bottom:3px;display:flex;align-items:center;gap:5px}
.dtStat .vl{font-size:16px;font-weight:700;font-variant-numeric:tabular-nums}
.dtStat .dot{display:inline-block;width:7px;height:7px;border-radius:50%;flex:none}
.hd{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.themeBtn{border:1px solid var(--line);background:var(--surface);color:var(--ink2);
  border-radius:9px;width:34px;height:34px;cursor:pointer;font-size:15px;flex:none;
  display:flex;align-items:center;justify-content:center;margin-top:2px}
.themeBtn:hover{border-color:var(--accent);color:var(--accent)}
.themeBtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.dtTitleRow{display:flex;align-items:flex-start;gap:9px}
.dtBadge{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:12px;flex:none;margin-top:2px}
.dtStatusText{font-size:11px;font-weight:600;color:var(--ink2);margin-top:3px}
#tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);
  border:1px solid var(--line);border-radius:9px;padding:9px 11px;font-size:12.5px;
  box-shadow:0 8px 24px rgba(0,0,0,.16);opacity:0;transition:opacity .1s;max-width:270px;z-index:9}
#tip b{display:block;margin-bottom:4px;font-size:13px}
#tip .r{display:flex;justify-content:space-between;gap:14px;color:var(--ink2)}
#tip .r span:last-child{color:var(--ink);font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:left;padding:5px 6px;border-bottom:1px solid var(--line)}
th{color:var(--ink2);font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums}
tr.sel{background:var(--accent-wash)}
#insetWrap{margin-top:14px;border-top:1px solid var(--line);padding-top:11px}
.inset-hd{font-size:11px;color:var(--ink2);margin-bottom:7px;letter-spacing:.02em}
.inset{display:flex;flex-wrap:wrap;gap:7px}
.tile{display:flex;flex-direction:column;gap:3px;align-items:center;cursor:pointer;
  border:1px solid var(--line);border-radius:8px;padding:6px 8px 5px;background:var(--surface);min-width:64px}
.tile:hover{border-color:var(--accent)}
.tile.sel{border-color:var(--accent);border-width:2px;padding:5px 7px 4px;
  box-shadow:0 0 0 3px var(--accent-wash)}
.tile:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.tile .sw{width:100%;height:15px;border-radius:3px}
.tile .nm{font-size:9.5px;color:var(--ink2);text-align:center;line-height:1.15;max-width:74px}
.tile .vl{font-size:11px;font-variant-numeric:tabular-nums}
.note{font-size:11.5px;color:var(--ink2);margin-top:12px;line-height:1.55}
.scroll{max-height:560px;overflow:auto}
details{margin-top:14px}summary{cursor:pointer;color:var(--ink2);font-size:12.5px}
</style></head><body>
<div class="wrap">
<div class="hd">
  <div><h1>Where the delivery risk sits</h1><p class="sub" id="sub"></p></div>
  <button class="themeBtn" id="themeToggle" type="button" aria-label="Toggle light or dark theme">
    <span id="themeIcon">☀</span></button>
</div>
<div class="controls" id="ctl" role="group" aria-label="Choose metric"></div>
<div class="grid">
  <div class="card">
    <svg id="map" viewBox="0 0 __W__ __H__" role="img" aria-labelledby="mt"></svg>
    <title id="mt">Choropleth of Indian states and union territories</title>
    <div class="legend"><span id="lo"></span><span class="bar" id="lb"></span><span id="lh"></span></div>
    <p class="legendCap">Lighter = lower risk &nbsp;&middot;&nbsp; darker red = higher risk</p>
    <div id="insetWrap"><div class="inset-hd">Too small to see on the map</div>
      <div class="inset" id="inset"></div></div>
  </div>
  <div class="card" id="detailCard" hidden>
    <div class="dtHead">
      <div class="dtTitleRow">
        <span class="dtBadge" id="dtBadge"></span>
        <div><div class="dtKind" id="dtKind"></div><div class="dtName" id="dtName"></div>
          <div class="dtStatusText" id="dtStatusText"></div></div>
      </div>
      <button class="dtClose" id="dtClose" type="button" aria-label="Clear selection">&#10005;</button>
    </div>
    <div class="dtGrid" id="dtGrid"></div>
  </div>
  <div class="card">
    <div style="font-weight:600;margin-bottom:8px;font-size:13px" id="rt">Ranked</div>
    <div class="scroll"><table><thead><tr><th>State / UT</th><th class="n" id="ch">Value</th></tr></thead>
    <tbody id="tb"></tbody></table></div>
  </div>
</div>
<p class="note" id="note"></p>
<details><summary>Method and caveats</summary><p class="note" id="meth"></p></details>
</div>
<div id="tip" role="status" aria-live="polite"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const RAMP_LIGHT=__RAMP_LIGHT__, RAMP_DARK=__RAMP_DARK__;
// Risk is the headline, not raw activity - default view leads with the metric
// that actually answers "what's the main problem", not "where is stuff".
const METRICS=[
 {k:'delayed_pct',    label:'% behind schedule',   fmt:v=>v==null?'-':v.toFixed(1)+'%'},
 {k:'cost_over_pct',  label:'% cost overrun',      fmt:v=>v==null?'-':v.toFixed(1)+'%'},
 {k:'projects',       label:'Projects',            fmt:v=>v.toLocaleString('en-IN')},
 {k:'cost_cr',        label:'Exposure (Rs cr)',    fmt:v=>'\\u20b9'+Math.round(v).toLocaleString('en-IN')},
 {k:'newly_slipped',  label:'Slipped last month',  fmt:v=>v.toLocaleString('en-IN')},
 {k:'median_delay_months',label:'Median delay (mo)',fmt:v=>v==null?'-':v.toFixed(1)}
];
let cur=METRICS[0], sel=null;
const map=document.getElementById('map'), tip=document.getElementById('tip');
const S=D.metrics;
document.getElementById('sub').textContent =
 'Snapshot '+D.meta.snapshot+' \\u00b7 '+D.meta.national_projects.toLocaleString('en-IN')+
 ' monitored projects \\u00b7 28 states + 8 union territories';
document.getElementById('note').textContent = D.meta.overlap_note;
document.getElementById('meth').textContent = D.meta.derivation +
 ' Boundaries: Survey of India state outlines with Jammu & Kashmir split into J&K and Ladakh '+
 'using Census district geometry (Ladakh = Leh + Kargil), and Dadra & Nagar Haveli merged with '+
 'Daman & Diu. Verified: 36 features, 36/36 names matching MoSPI GetStateList, northern extent 37.078N.';

function isDark(){
  const t=document.documentElement.getAttribute('data-theme');
  if(t==='dark')return true;
  if(t==='light')return false;
  return matchMedia('(prefers-color-scheme: dark)').matches;
}
function ramp(){return isDark()?RAMP_DARK:RAMP_LIGHT;}
function statusColor(v,warn,crit){
  if(v==null||isNaN(v))return null;
  return v>=crit?'#d03b3b':v>=warn?'#fab219':'#0ca30c';
}
function vals(){return Object.keys(D.paths).map(s=>S[s]?S[s][cur.k]:null);}
function scale(){
  const v=vals().filter(x=>x!=null&&!isNaN(x)).sort((a,b)=>a-b);
  return {lo:v[0]??0, hi:v[v.length-1]??1};
}
function colorOf(v,sc){
  if(v==null||isNaN(v))return 'var(--null)';
  const R=ramp();
  const t=sc.hi===sc.lo?0.5:(v-sc.lo)/(sc.hi-sc.lo);
  return R[Math.max(0,Math.min(R.length-1,Math.round(t*(R.length-1))))];
}
function draw(){
  const sc=scale();
  map.classList.toggle('has-sel', !!sel);
  map.innerHTML=Object.entries(D.paths).map(([name,d])=>{
    const m=S[name], v=m?m[cur.k]:null;
    return `<path class="st${sel===name?' sel':''}" d="${d}" fill="${colorOf(v,sc)}"
      tabindex="0" role="button" data-s="${name}"
      aria-label="${name}, ${D.kind[name]}: ${m?cur.fmt(v):'no data'}"></path>`;
  }).join('');
  if(sel){
    const p=map.querySelector(`path.st[data-s="${CSS.escape(sel)}"]`);
    if(p)map.appendChild(p);
  }
  document.getElementById('lb').innerHTML=ramp().map(c=>`<i style="background:${c}"></i>`).join('');
  document.getElementById('lo').textContent=cur.fmt(sc.lo);
  document.getElementById('lh').textContent=cur.fmt(sc.hi);
  document.getElementById('ch').textContent=cur.label;
  document.getElementById('rt').textContent='Ranked by '+cur.label.toLowerCase();
  document.getElementById('inset').innerHTML=D.small.map(n=>{
    const m=S[n],v=m?m[cur.k]:null;
    const short=n.replace('Dadra & Nagar Haveli and Daman & Diu','DNH & Daman-Diu')
                 .replace('Andaman & Nicobar','Andaman & Nic.');
    return `<div class="tile${sel===n?' sel':''}" data-s="${n}" tabindex="0" role="button"
      aria-label="${n}: ${m?cur.fmt(v):'no data'}">
      <span class="sw" style="background:${colorOf(v,sc)}"></span>
      <span class="nm">${short}</span><span class="vl">${v==null?'-':cur.fmt(v)}</span></div>`;
  }).join('');
  const rows=Object.keys(D.paths).map(s=>[s,S[s]?S[s][cur.k]:null])
    .sort((a,b)=>(b[1]??-Infinity)-(a[1]??-Infinity));
  document.getElementById('tb').innerHTML=rows.map(([s,v])=>
    `<tr class="${sel===s?'sel':''}" data-s="${s}"><td>${s}</td><td class="n">${v==null?'-':cur.fmt(v)}</td></tr>`).join('');
  renderDetail();
}
function tierOf(v){
  if(v==null||isNaN(v))return null;
  if(v>=66)return{c:'#d03b3b',label:'High risk',icon:'\u26a0'};
  if(v>=40)return{c:'#fab219',label:'Elevated risk',icon:'\u26a0'};
  return{c:'#0ca30c',label:'On track',icon:'\u2713'};
}
function renderDetail(){
  const card=document.getElementById('detailCard');
  if(!sel){card.hidden=true;return;}
  card.hidden=false;
  const m=S[sel];
  document.getElementById('dtKind').textContent=D.kind[sel];
  document.getElementById('dtName').textContent=sel;
  const badge=document.getElementById('dtBadge'), st=document.getElementById('dtStatusText');
  const worst=m?Math.max(m.delayed_pct??-1,m.cost_over_pct??-1):null;
  const tier=tierOf(worst);
  if(tier){
    badge.hidden=false;badge.textContent=tier.icon;
    badge.style.background=tier.c+'26';badge.style.color=tier.c;
    st.textContent=tier.label;
  }else{
    badge.hidden=true;badge.textContent='';st.textContent=m?'':'No data';
  }
  const dot=c=>c?`<span class="dot" style="background:${c}"></span>`:'';
  const stats = !m ? [['No monitored projects','-',null]] : [
    ['Projects monitored', m.projects.toLocaleString('en-IN'), null],
    ['Exposure', '\\u20b9'+Math.round(m.cost_cr).toLocaleString('en-IN')+' cr', null],
    ['% behind schedule', m.delayed_pct==null?'-':m.delayed_pct.toFixed(1)+'%', statusColor(m.delayed_pct,40,66)],
    ['% cost overrun', m.cost_over_pct==null?'-':m.cost_over_pct.toFixed(1)+'%', statusColor(m.cost_over_pct,40,66)],
    ['Median delay', m.median_delay_months==null?'-':m.median_delay_months.toFixed(1)+' mo', null],
    ['Slipped last month', m.newly_slipped.toLocaleString('en-IN'), null],
  ];
  document.getElementById('dtGrid').innerHTML = stats.map(([lb,vl,c])=>
    `<div class="dtStat"><div class="lb">${dot(c)}${lb}</div><div class="vl">${vl}</div></div>`).join('');
}
function show(name,x,y){
  const m=S[name];
  tip.innerHTML=`<b>${name}</b><div class="r"><span>${D.kind[name]}</span><span></span></div>`+(m?
    `<div class="r"><span>Projects</span><span>${m.projects.toLocaleString('en-IN')}</span></div>
     <div class="r"><span>Exposure</span><span>\\u20b9${Math.round(m.cost_cr).toLocaleString('en-IN')} cr</span></div>
     <div class="r"><span>Behind schedule</span><span>${m.delayed_pct==null?'-':m.delayed_pct+'%'}</span></div>
     <div class="r"><span>Median delay</span><span>${m.median_delay_months==null?'-':m.median_delay_months+' mo'}</span></div>
     <div class="r"><span>Slipped last month</span><span>${m.newly_slipped}</span></div>`
    :`<div class="r"><span>No monitored projects</span><span></span></div>`);
  tip.style.opacity=1;
  const w=tip.offsetWidth,h=tip.offsetHeight;
  tip.style.left=Math.min(x+14,innerWidth-w-10)+'px';
  tip.style.top=Math.max(10,y-h-12)+'px';
}
function hide(){tip.style.opacity=0;}
map.addEventListener('mousemove',e=>{const p=e.target.closest('path.st');
  if(p)show(p.dataset.s,e.clientX,e.clientY);else hide();});
map.addEventListener('mouseleave',hide);
map.addEventListener('click',e=>{const p=e.target.closest('path.st');
  if(p){sel=sel===p.dataset.s?null:p.dataset.s;draw();}});
map.addEventListener('focusin',e=>{const p=e.target.closest('path.st');
  if(p){const r=p.getBoundingClientRect();show(p.dataset.s,r.x+r.width/2,r.y+r.height/2);}});
map.addEventListener('focusout',hide);
document.getElementById('tb').addEventListener('click',e=>{const tr=e.target.closest('tr');
  if(tr&&tr.dataset.s){sel=sel===tr.dataset.s?null:tr.dataset.s;draw();}});
document.getElementById('inset').addEventListener('click',e=>{const t=e.target.closest('.tile');
  if(t){sel=sel===t.dataset.s?null:t.dataset.s;draw();}});
document.getElementById('inset').addEventListener('mousemove',e=>{const t=e.target.closest('.tile');
  if(t)show(t.dataset.s,e.clientX,e.clientY);else hide();});
document.getElementById('inset').addEventListener('mouseleave',hide);
document.getElementById('inset').addEventListener('keydown',e=>{
  const t=e.target.closest('.tile');
  if(t&&(e.key==='Enter'||e.key===' ')){e.preventDefault();sel=sel===t.dataset.s?null:t.dataset.s;draw();}});
document.getElementById('dtClose').addEventListener('click',()=>{sel=null;draw();});
document.getElementById('ctl').innerHTML=METRICS.map((m,i)=>
  `<button class="m" aria-pressed="${i===0}" data-i="${i}">${m.label}</button>`).join('');
document.getElementById('ctl').addEventListener('click',e=>{
  const b=e.target.closest('button.m'); if(!b)return;
  cur=METRICS[+b.dataset.i];
  [...document.querySelectorAll('button.m')].forEach(x=>x.setAttribute('aria-pressed',x===b));
  draw();
});
function loadTheme(){try{return localStorage.getItem('paimana_map_theme');}catch(e){return null;}}
function saveTheme(t){try{localStorage.setItem('paimana_map_theme',t);}catch(e){}}
function updateThemeIcon(){document.getElementById('themeIcon').textContent=isDark()?'\u263e':'\u2600';}
(function initTheme(){
  const t=loadTheme();
  if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);
})();
document.getElementById('themeToggle').addEventListener('click',()=>{
  const next=isDark()?'light':'dark';
  saveTheme(next);
  document.documentElement.setAttribute('data-theme',next);
  updateThemeIcon();
  draw();
});
updateThemeIcon();
if(matchMedia)matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{updateThemeIcon();draw();});
draw();
</script></body></html>"""

html = (html.replace("__W__", str(W)).replace("__H__", str(H))
        .replace("__DATA__", json.dumps(payload, separators=(",", ":")))
        .replace("__RAMP_LIGHT__", json.dumps(RAMP_LIGHT))
        .replace("__RAMP_DARK__", json.dumps(RAMP_DARK)))
open(OUT, "w", encoding="utf-8").write(html)
print("wrote", OUT, "(%.2f MB)" % (os.path.getsize(OUT) / 1048576))
print("states with geometry:", len(paths), "| states with metrics:", len(met["states"]))
missing = [s for s in paths if s not in met["states"]]
print("geometry without metrics:", missing if missing else "none")
