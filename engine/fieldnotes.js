/* ===================== FIELD NOTES EXPLAINER (engine/fieldnotes.js, experimental 2026-10-11) =====================
   studio/cuts.py splices this file in before the build section only for projects with a scene of type "fieldnotes",
   so every other page stays byte-identical. Look: templates-experimental/owner-explainer-field-notes-v1/STYLE.md.
   A fieldnotes scene is data, not code (FIELDNOTES.md): data.header, kicker, headline, objects and actions.
   Times: a number is seconds after the scene starts; a string is one of the scene's cue names (beats.py anchors cues to
   the narration words) with an optional +/- offset, or "start" / "end" (the scene's own start and end).
   Objects carry over to the next fieldnotes scene in their final state (same id = same object), so a house drawn in
   chapter 1 is still there, unchanged, in chapter 2. Callouts, notes and cards stay in their own scene. */
var FN = (function(){
  var p = P.palette || {}, c = function(k, d){ return p[k] || d; };
  return {
    col: { paper: c("paper", "#E7E0D4"), grid: c("grid", "#D6CEC0"), ink: c("ink", "#1B1B15"), inkSoft: c("ink2", "#5A554D"),
      muted: c("muted", "#8A8378"), ochre: c("ochre", "#D58745"), ochreRule: c("ochreRule", "#C3996F"), sage: c("sage", "#698157"),
      sageWipe: c("sageWipe", "#6C8454"), sageTint: c("sageTint", "#B1B799"), blue: c("blue", "#A5BDD5"), blueStroke: c("blueStroke", "#7E9CC0"),
      ground: c("ground", "#E1D5C3"), card: c("card", "#F6F1E8"), wall: c("wall", "#FAF7F1"), annex: c("annex", "#EDE4D6"), track: c("track", "#DCD4C8") },
    L: { mx: 72, hdrY: 150, ruleY: 188, kickY: 246, headY: 290, headSize: 112, headMax: 900 },
    carry: null, fits: [], uid: 0
  };
})();
NOWIPE.fieldnotes = 1; NOCAPS.fieldnotes = 1;   /* fieldnotes draws its own chapter transitions; no generic captions */

(function(){ var k = FN.col, st = document.createElement("style");
  st.textContent = [
    ".fn-bg{position:absolute;inset:0;background:" + k.paper + "}",
    ".fn-grid{position:absolute;inset:0;opacity:.32;background-image:linear-gradient(to right," + k.grid + " 1px,transparent 1px),linear-gradient(to bottom," + k.grid + " 1px,transparent 1px);background-size:54px 54px}",
    ".fn-shade{position:absolute;inset:0;background:radial-gradient(120% 80% at 30% 18%,rgba(255,255,255,.28),rgba(255,255,255,0) 60%),radial-gradient(90% 70% at 85% 95%,rgba(120,100,70,.10),rgba(0,0,0,0) 70%),radial-gradient(70% 50% at 5% 70%,rgba(120,100,70,.07),rgba(0,0,0,0) 70%)}",
    ".fn-hdr{position:absolute;left:72px;right:72px;top:150px;display:flex;justify-content:space-between;align-items:baseline;font:600 21px/1 'Inter',sans-serif;letter-spacing:.18em;text-transform:uppercase;color:" + k.muted + ";white-space:nowrap}",
    ".fn-hdr b{color:" + k.ink + ";font-weight:700}",
    ".fn-rule{position:absolute;left:72px;right:72px;top:188px;height:2px;background:#CFC7BA}",
    ".fn-rule i{position:absolute;left:0;top:-1px;height:4px;background:" + k.ochreRule + "}",
    ".fn-kick{position:absolute;left:72px;top:246px;display:flex;align-items:center;gap:18px;font:700 22px/1 'Inter',sans-serif;letter-spacing:.2em;text-transform:uppercase;color:#3A3630;white-space:nowrap}",
    ".fn-kick i{display:block;width:40px;height:3px;background:" + k.ochre + "}",
    ".fn-head{position:absolute;left:72px;top:290px;font:800 112px/1.0 'Inter Tight',sans-serif;letter-spacing:-.035em;color:" + k.ink + "}",
    ".fn-ln{display:block;white-space:nowrap}",
    ".fn-tx{display:inline-block;padding:0 12px 6px;margin-left:-12px;background-repeat:no-repeat;background-position:0 0;background-size:0% 100%}",
    ".fn-em-ochre{background-image:linear-gradient(" + k.ochre + "," + k.ochre + ")}",
    ".fn-em-blue{background-image:linear-gradient(" + k.blue + "," + k.blue + ");background-position:0 92%;background-size:0% 22%}",
    ".fn-em-sage{background-image:linear-gradient(" + k.sageTint + "," + k.sageTint + ");background-position:0 90%;background-size:0% 46%}",
    ".fn-em-italic{font-family:'Instrument Serif',serif;font-style:italic;font-weight:400;letter-spacing:0;color:" + k.ochre + "}",
    ".fn-lab{position:absolute;left:0;top:0;white-space:nowrap;font:700 20px/1 'Inter',sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#3A3630}",
    ".fn-tag{position:absolute;left:0;top:0;white-space:nowrap;font:700 20px/1 'Inter',sans-serif;letter-spacing:.14em;text-transform:uppercase;color:#fff;background:" + k.ochre + ";padding:10px 14px 9px}",
    ".fn-note{position:absolute;left:0;top:0;white-space:nowrap;font:italic 400 42px/1.1 'Instrument Serif',serif;color:#3A3630}",
    ".fn-card{position:absolute;left:0;top:0;display:flex;align-items:center;gap:22px;background:" + k.card + ";border:3px solid " + k.ink + ";box-shadow:10px 10px 0 " + k.ochre + ";padding:22px 28px;font:700 40px/1.1 'Inter Tight',sans-serif;letter-spacing:-.02em;color:" + k.ink + "}",
    ".fn-card .bx{width:44px;height:44px;border:3px solid " + k.ink + ";border-radius:7px;flex:none;display:flex;align-items:center;justify-content:center}",
    ".fn-step{position:absolute;left:0;top:0;font:700 38px/1.1 'Inter Tight',sans-serif;letter-spacing:-.01em;color:" + k.ink + "}",
    ".fn-bands{position:absolute;left:0;top:0;width:" + W + "px;height:" + H + "px;overflow:hidden;z-index:60;pointer-events:none;visibility:hidden}",
    ".fn-bands i{position:absolute;top:-500px;height:2920px;width:900px;display:block}"
  ].join("\n");
  document.head.appendChild(st); })();

/* ---------- time, fit, small helpers ---------- */
function fnT(s, C, v, dflt){
  if(v == null) return dflt;
  if(typeof v === "number") return s.start + v;
  var m = /^([A-Za-z0-9_]+)([+-]\d+(?:\.\d+)?)?$/.exec(String(v).trim());
  if(!m) throw new Error("fieldnotes " + s.id + ": bad time " + JSON.stringify(v));
  var base = m[1] === "start" ? s.start : m[1] === "end" ? s.end : C(m[1]);
  return base + Number(m[2] || 0); }
function fnFit(f){ f.el.style.fontSize = f.size + "px";
  var w = 0; [].forEach.call(f.el.querySelectorAll(".fn-tx"), function(x){ w = Math.max(w, x.offsetWidth - 24); });
  if(w > f.max) f.el.style.fontSize = Math.max(f.size * 0.7, Math.floor(f.size * f.max / w)) + "px"; }
if(document.fonts && document.fonts.load){
  Promise.all(["800 100px 'Inter Tight'", "700 20px 'Inter'", "italic 400 40px 'Instrument Serif'"].map(function(q){ return document.fonts.load(q); }))
    .then(function(){ FN.fits.forEach(fnFit); }); }
function fnEase(d){ return d == null ? 0.6 : d; }
function fnFade(el, t, d, on){ if(on){ tl.fromTo(el, { autoAlpha: 0 }, { autoAlpha: 1, duration: d || 0.3, ease: "power1.out" }, t); }
  else tl.to(el, { autoAlpha: 0, duration: d || 0.25, ease: "power1.in" }, t); }
/* outlines draw on, then flat fills tint in; [data-fade] parts (text, dashed lines) fade; [data-skip] parts are left alone */
function fnDraw(g, t, d){ d = d || 0.6;
  tl.set(g, { autoAlpha: 1 }, t);
  [].forEach.call(g.querySelectorAll("path,rect,circle,ellipse,line,polyline,polygon,text"), function(e){
    if(e.closest("[data-skip]")) return;
    if(e.tagName === "text" || e.closest("[data-fade]")){ gsap.set(e, { opacity: 0 }); tl.to(e, { opacity: 1, duration: 0.3 }, t + d * 0.6); return; }
    var stroke = e.getAttribute("stroke"), fill = e.getAttribute("fill");
    if(stroke && stroke !== "none" && e.getTotalLength){ var len = Math.ceil(e.getTotalLength()) + 2;
      gsap.set(e, { strokeDasharray: len + " " + len, strokeDashoffset: len });
      tl.to(e, { strokeDashoffset: 0, duration: d, ease: "power2.inOut" }, t); }
    if(fill && fill !== "none"){ var fo = Number(e.getAttribute("fill-opacity") || 1);
      gsap.set(e, { attr: { "fill-opacity": 0 } });
      tl.to(e, { attr: { "fill-opacity": fo }, duration: 0.3, ease: "power1.out" }, t + d * 0.6); } }); }
function fnG(parent, x, y, s){ var root = sv("g", {}, parent); var inner = sv("g", { transform: "translate(" + (x || 0) + "," + (y || 0) + ") scale(" + (s || 1) + ")" }, root); return { root: root, g: inner }; }
function fnText(parent, x, y, text, o){ o = o || {};
  var e = sv("text", { x: x, y: y, "text-anchor": o.anchor || "start", fill: o.fill || "#3A3630",
    style: "font-family:" + (o.family || "'Inter',sans-serif") + ";font-weight:" + (o.weight || 700) + ";font-size:" + (o.size || 19) + "px;letter-spacing:" + (o.ls == null ? ".14em" : o.ls) + ";text-transform:" + (o.upper === false ? "none" : "uppercase") }, parent);
  e.textContent = text; return e; }
/* a proxy tween that writes an attribute each frame (seek-safe like typeText) */
function fnAttrTween(el, attr, fmt, a0, a1, t, d, ease){ var o = { v: a0 };
  tl.fromTo(o, { v: a0 }, { v: a1, duration: d, ease: ease || "power2.inOut", onUpdate: function(){ el.setAttribute(attr, fmt(o.v)); } }, t); }

/* ---------- object kinds: build(o, ctx) draws the object at its current state (o.st) and returns its actions ---------- */
var FN_KINDS = {};
FN_KINDS.house = function(o, ctx){ var d = o.def, k = FN.col, sw = 4, ink = k.ink;
  var G = fnG(ctx.svg, d.x, d.y, d.scale || 1), g = G.g;
  sv("rect", { x: -150, y: -120, width: 90, height: 120, fill: k.annex, stroke: ink, "stroke-width": sw }, g);
  sv("rect", { x: -128, y: -92, width: 40, height: 38, fill: k.blue, stroke: ink, "stroke-width": sw }, g);
  sv("rect", { x: -60, y: -190, width: 190, height: 190, fill: k.wall }, g);
  var lvl = o.st.fill || 0, cool = sv("rect", { x: -58, y: -2 - 186 * lvl, width: 186, height: 186 * lvl, fill: k.blue, "fill-opacity": 0.6, "data-skip": 1 }, g);
  sv("rect", { x: -60, y: -190, width: 190, height: 190, fill: "none", stroke: ink, "stroke-width": sw }, g);
  sv("path", { d: "M-82,-186 L35,-282 L152,-186 Z", fill: ink, stroke: ink, "stroke-width": sw, "stroke-linejoin": "round" }, g);
  sv("circle", { cx: 35, cy: -222, r: 9, fill: k.wall }, g);
  sv("rect", { x: -28, y: -104, width: 44, height: 104, fill: k.ochre, stroke: ink, "stroke-width": sw }, g);
  sv("rect", { x: 50, y: -150, width: 50, height: 46, fill: k.blue, stroke: ink, "stroke-width": sw }, g);
  sv("path", { d: "M70,-60 L112,-60 L112,0", fill: "none", stroke: ink, "stroke-width": sw }, g);
  sv("line", { x1: -180, y1: 0, x2: 170, y2: 0, stroke: ink, "stroke-width": sw, "stroke-linecap": "round" }, g);
  return { root: G.root,
    fill: function(t, a){ var l0 = o.st.fill || 0, l1 = a.level == null ? 1 : a.level, dd = fnEase(a.dur || 1.0);
      fnAttrTween(cool, "height", String, 186 * l0, 186 * l1, t, dd);
      fnAttrTween(cool, "y", String, -2 - 186 * l0, -2 - 186 * l1, t, dd); o.st.fill = l1; } }; };

FN_KINDS.ac_unit = function(o, ctx){ var d = o.def, k = FN.col, ink = k.ink;
  var G = fnG(ctx.svg, d.x, d.y, d.scale || 1), g = G.g;
  sv("line", { x1: -125, y1: 0, x2: 125, y2: 0, stroke: ink, "stroke-width": 4, "stroke-linecap": "round" }, g);
  sv("rect", { x: -100, y: -150, width: 200, height: 146, rx: 10, fill: k.annex, stroke: ink, "stroke-width": 4 }, g);
  for(var i = 0; i < 8; i++) sv("line", { x1: 50, y1: -128 + i * 14, x2: 84, y2: -128 + i * 14, stroke: ink, "stroke-width": 3, "stroke-linecap": "round" }, g);
  sv("circle", { cx: -22, cy: -77, r: 54, fill: k.wall, stroke: ink, "stroke-width": 4 }, g);
  var hub = sv("g", { transform: "translate(-22,-77)", "data-fade": 1 }, g), rot = sv("g", {}, hub);
  for(var b = 0; b < 3; b++) sv("path", { d: "M0,0 C12,-8 16,-30 5,-42 C-7,-38 -9,-14 0,0 Z", fill: k.inkSoft, transform: "rotate(" + b * 120 + ")" }, rot);
  sv("circle", { cx: 0, cy: 0, r: 7, fill: ink }, hub);
  var air = sv("g", { "data-skip": 1 }, g);
  [-62, -22, 18].forEach(function(x){ sv("path", { d: "M" + x + ",-168 q12,-12 0,-24 q-12,-12 0,-24", fill: "none", stroke: k.blueStroke, "stroke-width": 4, "stroke-linecap": "round" }, air); });
  gsap.set(air, { opacity: Math.min(1, (o.st.speed || 0) / 1.5) });
  var ev = [];   /* speed changes, turned into seek-safe rotation tweens once the scene is built */
  return { root: G.root,
    run: function(t, a){ var sp = a.speed == null ? 1.2 : a.speed; ev.push({ t: t, sp: sp });
      tl.to(air, { opacity: Math.min(1, sp / 1.5), duration: 0.4 }, t); },
    finish: function(s){ var t = s.start, sp = o.st.speed || 0, ang = o.st.angle || 0;
      ev.sort(function(a, b){ return a.t - b.t; }).concat([{ t: s.end, sp: null }]).forEach(function(e){
        var dt = Math.max(0, e.t - t);
        if(dt > 0 && sp > 0){ fnAttrTween(rot, "transform", function(v){ return "rotate(" + v.toFixed(2) + ")"; }, ang, ang + sp * 360 * dt, t, dt, "none"); ang += sp * 360 * dt; }
        t = Math.max(t, e.t); if(e.sp != null) sp = e.sp; });
      rot.setAttribute("transform", "rotate(" + (o.st.angle || 0).toFixed(2) + ")");
      o.st.speed = sp; o.st.angle = ang % 360; } }; };

FN_KINDS.timeline = function(o, ctx){ var d = o.def, k = FN.col, ink = k.ink, x = d.x, y = d.y, w = d.w, bh = d.bandH || 150;
  var st = o.st; st.bands = st.bands || {}; st.segs = st.segs || {}; st.ph = st.ph || { pos: 0, shown: false };
  (d.bands || []).forEach(function(b){ if(!st.bands[b.id]) st.bands[b.id] = { from: b.from, to: b.to, label: b.label || "", shown: !!b.shown }; });
  (d.segs || []).forEach(function(sg){ if(!st.segs[sg.id]) st.segs[sg.id] = { from: sg.from, to: sg.to, level: sg.level == null ? 1 : sg.level, shown: !!sg.shown }; });
  if(d.playhead && d.playhead.pos != null && !o.carried) st.ph.pos = d.playhead.pos;
  var root = sv("g", {}, ctx.svg), base = sv("g", {}, root), X = function(f){ return x + f * w; };
  var subs = {};
  Object.keys(st.bands).forEach(function(id){ var b = st.bands[id], gb = sv("g", {}, root);
    sv("rect", { x: X(b.from), y: y - bh, width: (b.to - b.from) * w, height: bh, fill: k.ochre, "fill-opacity": 0.2 }, gb);
    sv("line", { x1: X(b.from), y1: y - bh, x2: X(b.to), y2: y - bh, stroke: k.ochre, "stroke-width": 5 }, gb);
    fnText(gb, X(b.from), y - bh - 16, b.label, { fill: k.ochre });
    gsap.set(gb, { autoAlpha: b.shown ? 1 : 0 }); subs[id] = { el: gb, kind: "band" }; });
  sv("line", { x1: x, y1: y, x2: x + w, y2: y, stroke: ink, "stroke-width": 4, "stroke-linecap": "round" }, base);
  var ticks = sv("g", { "data-fade": 1 }, base);
  for(var i = 0; i <= 12; i++) sv("line", { x1: X(i / 12), y1: y - 8, x2: X(i / 12), y2: y + 8, stroke: ink, "stroke-width": 2 }, ticks);
  fnText(base, x, y + 44, d.left || "EARLIER", { size: 18, fill: k.inkSoft });
  fnText(base, x + w, y + 44, d.right || "LATER", { size: 18, fill: k.inkSoft, anchor: "end" });
  var segH = function(l){ return 12 + 52 * l; };
  Object.keys(st.segs).forEach(function(id){ var sg = st.segs[id], h = segH(sg.level);
    var r = sv("rect", { x: X(sg.from), y: y - 8 - h, width: (sg.to - sg.from) * w, height: h, rx: 3, fill: k.blue, stroke: ink, "stroke-width": 3 }, root);
    gsap.set(r, { autoAlpha: sg.shown ? 1 : 0 }); subs[id] = { el: r, kind: "seg" }; });
  var ph = sv("g", {}, root), phx = sv("g", { transform: "translate(" + X(st.ph.pos) + ",0)" }, ph);
  sv("line", { x1: 0, y1: y - bh - 30, x2: 0, y2: y + 4, stroke: ink, "stroke-width": 3, "stroke-dasharray": "7 7" }, phx);
  sv("path", { d: "M-11," + (y + 24) + " L0," + (y + 8) + " L11," + (y + 24) + " Z", fill: ink }, phx);
  sv("circle", { cx: 0, cy: y - bh - 36, r: 8, fill: k.ochre, stroke: ink, "stroke-width": 3 }, phx);
  gsap.set(ph, { autoAlpha: st.ph.shown ? 1 : 0 }); subs.playhead = { el: ph, kind: "playhead" };
  return { root: root, drawEl: base,
    sub: function(id){ if(!subs[id]) throw new Error("timeline " + o.id + " has no band, segment or playhead '" + id + "'"); return subs[id]; },
    partShow: function(t, a, id){ var s2 = this.sub(id);
      if(s2.kind === "seg"){ var sg = st.segs[id], w1 = (sg.to - sg.from) * w; tl.set(s2.el, { autoAlpha: 1 }, t);
        fnAttrTween(s2.el, "width", String, 0, w1, t, fnEase(a.dur || 0.5)); sg.shown = true; }
      else { fnFade(s2.el, t, a.dur || 0.35, true); if(s2.kind === "band") st.bands[id].shown = true; else st.ph.shown = true; } },
    partHide: function(t, a, id){ var s2 = this.sub(id); fnFade(s2.el, t, a.dur, false);
      if(s2.kind === "seg") st.segs[id].shown = false; else if(s2.kind === "band") st.bands[id].shown = false; else st.ph.shown = false; },
    seg: function(t, a, id){ var sg = st.segs[id], el = this.sub(id).el, dd = fnEase(a.dur);
      var f1 = a.from == null ? sg.from : a.from, t1 = a.to == null ? sg.to : a.to, l1 = a.level == null ? sg.level : a.level;
      fnAttrTween(el, "x", String, X(sg.from), X(f1), t, dd); fnAttrTween(el, "width", String, (sg.to - sg.from) * w, (t1 - f1) * w, t, dd);
      fnAttrTween(el, "height", String, segH(sg.level), segH(l1), t, dd); fnAttrTween(el, "y", String, y - 8 - segH(sg.level), y - 8 - segH(l1), t, dd);
      sg.from = f1; sg.to = t1; sg.level = l1; },
    playhead: function(t, a){ var p0 = a.from == null ? st.ph.pos : a.from, p1 = a.to == null ? p0 : a.to;
      fnAttrTween(phx, "transform", function(v){ return "translate(" + v.toFixed(1) + ",0)"; }, X(p0), X(p1), t, a.dur || 1.2, "power1.inOut"); st.ph.pos = p1; } }; };

FN_KINDS.gauge = function(o, ctx){ var d = o.def, k = FN.col, ink = k.ink, x = d.x, y = d.y, w = d.w || 600;
  if(o.st.level == null || !o.st.drawn) o.st.level = d.level == null ? 0.5 : d.level;   /* not drawn yet: take the planned level */
  var root = sv("g", {}, ctx.svg);
  fnText(root, x, y - 16, d.label || "", { size: 19 });
  sv("rect", { x: x, y: y, width: w, height: 26, fill: k.track, stroke: ink, "stroke-width": 3 }, root);
  var bar = sv("rect", { x: x + 1.5, y: y + 1.5, width: o.st.drawn ? (w - 3) * o.st.level : 0, height: 23, fill: d.color ? (FN.col[d.color] || d.color) : k.blueStroke, "data-skip": 1 }, root);
  fnText(root, x, y + 54, d.low || "LESS", { size: 16, fill: k.inkSoft });
  fnText(root, x + w, y + 54, d.high || "MORE", { size: 16, fill: k.inkSoft, anchor: "end" });
  return { root: root,
    afterDraw: function(t){ fnAttrTween(bar, "width", String, 0, (w - 3) * o.st.level, t + 0.4, 0.6); },
    set: function(t, a){ var l1 = a.level; fnAttrTween(bar, "width", String, (w - 3) * o.st.level, (w - 3) * l1, t, fnEase(a.dur || 0.8)); o.st.level = l1; } }; };

FN_KINDS.thermostat = function(o, ctx){ var d = o.def, k = FN.col, ink = k.ink, r = d.r || 64;
  var G = fnG(ctx.svg, d.x, d.y, 1), g = G.g;
  sv("circle", { cx: 0, cy: 0, r: r, fill: k.card, stroke: ink, "stroke-width": 4 }, g);
  sv("circle", { cx: 0, cy: 0, r: r - 14, fill: "none", stroke: k.sageTint, "stroke-width": 8, "data-fade": 1 }, g);
  for(var i = -3; i <= 3; i++){ var a = i * 30 * Math.PI / 180; sv("line", { x1: Math.sin(a) * (r - 28), y1: -Math.cos(a) * (r - 28), x2: Math.sin(a) * (r - 20), y2: -Math.cos(a) * (r - 20), stroke: ink, "stroke-width": 3, "data-fade": 1 }, g); }
  var hand = sv("g", { transform: "rotate(" + (o.st.angle || d.angle || -30) + ")" }, g);
  sv("line", { x1: 0, y1: 0, x2: 0, y2: -(r - 24), stroke: k.ochre, "stroke-width": 6, "stroke-linecap": "round" }, hand);
  sv("circle", { cx: 0, cy: 0, r: 7, fill: ink }, g);
  var cpos = sv("g", { transform: "translate(" + (r + 26) + "," + (-r * 0.35) + ")", "data-skip": 1 }, g);   /* position here, gsap moves the path */
  var chev = sv("path", { d: "M-14,10 L0,-6 L14,10", fill: "none", stroke: k.ochre, "stroke-width": 7, "stroke-linecap": "round", "stroke-linejoin": "round" }, cpos);
  gsap.set(chev, { autoAlpha: 0 });
  if(o.st.angle == null) o.st.angle = d.angle == null ? -30 : d.angle;
  return { root: G.root,
    turn: function(t, a){ var a0 = o.st.angle, a1 = a0 + (a.by == null ? 25 : a.by);
      fnAttrTween(hand, "transform", function(v){ return "rotate(" + v.toFixed(2) + ")"; }, a0, a1, t, fnEase(a.dur || 0.7), "power2.inOut");
      tl.fromTo(chev, { autoAlpha: 0, y: 10 }, { autoAlpha: 1, y: 0, duration: 0.3, ease: "power2.out" }, t + 0.2); o.st.angle = a1; } }; };

FN_KINDS.arrow = function(o, ctx){ var d = o.def, k = FN.col, pts = d.points || [], col = FN.col[d.color] || d.color || k.ink, sw = d.width || 5;
  var dd = "M" + pts[0][0] + "," + pts[0][1];
  if(pts.length === 3) dd += " Q" + pts[1][0] + "," + pts[1][1] + " " + pts[2][0] + "," + pts[2][1];
  else for(var i = 1; i < pts.length; i++) dd += " L" + pts[i][0] + "," + pts[i][1];
  var root = sv("g", {}, ctx.svg), id = "fnm" + (++FN.uid), line, mask = null;
  if(d.dash){ var m = sv("mask", { id: id, maskUnits: "userSpaceOnUse", x: 0, y: 0, width: W, height: H }, ctx.defs);
    mask = sv("path", { d: dd, fill: "none", stroke: "#fff", "stroke-width": sw + 8, "stroke-linecap": "round" }, m);
    line = sv("path", { d: dd, fill: "none", stroke: col, "stroke-width": sw, "stroke-linecap": "round", "stroke-dasharray": "14 12", mask: "url(#" + id + ")", "data-skip": 1 }, root); }
  else line = sv("path", { d: dd, fill: "none", stroke: col, "stroke-width": sw, "stroke-linecap": "round" }, root);
  if(d.head !== false && pts.length > 1){ var a = pts[pts.length - 2], b = pts[pts.length - 1], ang = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
    sv("path", { d: "M-16,-11 L0,0 L-16,11", fill: "none", stroke: col, "stroke-width": sw, "stroke-linecap": "round", "stroke-linejoin": "round", transform: "translate(" + b[0] + "," + b[1] + ") rotate(" + ang.toFixed(1) + ")", "data-fade": 1 }, root); }
  return { root: root,
    draw: function(t, a){ tl.set(root, { autoAlpha: 1 }, t);
      if(mask){ var len = Math.ceil(mask.getTotalLength()) + 2; gsap.set(mask, { strokeDasharray: len + " " + len, strokeDashoffset: len }); tl.to(mask, { strokeDashoffset: 0, duration: a.dur || 0.7, ease: "power2.inOut" }, t); }
      else { var l2 = Math.ceil(line.getTotalLength()) + 2; gsap.set(line, { strokeDasharray: l2 + " " + l2, strokeDashoffset: l2 }); tl.to(line, { strokeDashoffset: 0, duration: a.dur || 0.7, ease: "power2.inOut" }, t); }
      [].forEach.call(root.querySelectorAll("[data-fade]"), function(e){ gsap.set(e, { opacity: 0 }); tl.to(e, { opacity: 1, duration: 0.2 }, t + (a.dur || 0.7) * 0.85); });
      o.st.drawn = true; },
    flow: function(t, a){ if(!mask) return; tl.fromTo(line, { strokeDashoffset: 0 }, { strokeDashoffset: -26 * Math.round((a.dur || 2) * 3), duration: a.dur || 2, ease: "none" }, t); } }; };

/* flow: a process drawn as numbered steps joined by links. Parts: each step by id, links "l1".."l<n-1>" (step i to i+1).
   highlight a step (tone ochre / sage / blue / none), mark a link broken or ok (with a short label), pulse a dot along it */
FN_KINDS.flow = function(o, ctx){ var d = o.def, k = FN.col, ink = k.ink, x = d.x, y = d.y, w = d.w || 560;
  var nodes = d.nodes || [], bh = d.boxH || 118, gap = d.gap || 78, st = o.st, lx = x + 46;
  st.nodes = st.nodes || {}; st.links = st.links || {};
  nodes.forEach(function(n){ if(!st.nodes[n.id]) st.nodes[n.id] = { tone: null }; });
  for(var li = 1; li < nodes.length; li++) if(!st.links["l" + li]) st.links["l" + li] = { state: null, label: "" };
  var root = sv("g", {}, ctx.svg), subs = {}, tones = { ochre: k.ochre, sage: k.sageTint, blue: k.blue }, Y = function(i){ return y + i * (bh + gap); };
  nodes.forEach(function(n, i){ var g = sv("g", {}, root), top = Y(i);
    sv("rect", { x: x, y: top, width: w, height: bh, rx: 14, fill: k.card, stroke: ink, "stroke-width": 4 }, g);
    var tint = sv("rect", { x: x + 2, y: top + 2, width: w - 4, height: bh - 4, rx: 12, fill: tones[st.nodes[n.id].tone] || k.card, "fill-opacity": st.nodes[n.id].tone ? 0.5 : 0, "data-skip": 1 }, g);
    sv("circle", { cx: lx, cy: top + bh / 2, r: 28, fill: k.paper, stroke: ink, "stroke-width": 3 }, g);
    fnText(g, lx, top + bh / 2 + 8, String(i + 1), { anchor: "middle", size: 24, ls: "0", fill: ink });
    var lab = mk(ctx.html, "div", "fn-step", esc(n.label));
    gsap.set(lab, { x: x + 100, y: top + bh / 2, yPercent: -50, width: w - 128 });
    gsap.set(lab, { autoAlpha: o.st.drawn ? 1 : 0 });   /* the label arrives with its box */
    subs[n.id] = { el: g, html: lab, tint: tint, kind: "node", i: i }; });
  for(var j = 1; j < nodes.length; j++){ var y0 = Y(j - 1) + bh, y1 = Y(j), gl = sv("g", {}, root), ls = st.links["l" + j];
    var line = sv("line", { x1: lx, y1: y0 + 4, x2: lx, y2: y1 - 6, stroke: ink, "stroke-width": 4 }, gl);
    sv("path", { d: "M" + (lx - 10) + "," + (y1 - 18) + " L" + lx + "," + (y1 - 6) + " L" + (lx + 10) + "," + (y1 - 18), fill: "none", stroke: ink, "stroke-width": 4, "stroke-linecap": "round", "stroke-linejoin": "round", "data-fade": 1 }, gl);
    var mid = (y0 + y1) / 2, bad = sv("g", { "data-skip": 1 }, gl), good = sv("g", { "data-skip": 1 }, gl);
    sv("circle", { cx: lx, cy: mid, r: 18, fill: k.ochre, stroke: ink, "stroke-width": 3 }, bad);
    sv("path", { d: "M" + (lx - 7) + "," + (mid - 7) + " L" + (lx + 7) + "," + (mid + 7) + " M" + (lx + 7) + "," + (mid - 7) + " L" + (lx - 7) + "," + (mid + 7), stroke: "#fff", "stroke-width": 4, "stroke-linecap": "round" }, bad);
    sv("circle", { cx: lx, cy: mid, r: 18, fill: k.sage, stroke: ink, "stroke-width": 3 }, good);
    sv("path", { d: "M" + (lx - 8) + "," + mid + " L" + (lx - 2) + "," + (mid + 6) + " L" + (lx + 9) + "," + (mid - 6), fill: "none", stroke: "#fff", "stroke-width": 4, "stroke-linecap": "round", "stroke-linejoin": "round" }, good);
    var tag = mk(ctx.html, "div", "fn-tag", esc(ls.label || ""), "background:" + (ls.state === "ok" ? k.sage : k.ochre));
    gsap.set(tag, { x: lx + 40, y: mid, yPercent: -50 });
    gsap.set(bad, { autoAlpha: ls.state === "broken" ? 1 : 0 }); gsap.set(good, { autoAlpha: ls.state === "ok" ? 1 : 0 });
    gsap.set(tag, { autoAlpha: ls.state && ls.label ? 1 : 0 });
    if(ls.state === "broken") gsap.set(line, { attr: { stroke: k.ochre, "stroke-dasharray": "10 9" } });
    if(ls.state === "ok") gsap.set(line, { attr: { stroke: k.sage } });
    subs["l" + j] = { el: gl, kind: "link", line: line, bad: bad, good: good, tag: tag, mid: mid }; }
  return { root: root,
    sub: function(id){ if(!subs[id]) throw new Error("flow " + o.id + " has no step or link '" + id + "'"); return subs[id]; },
    draw: function(t, a){ tl.set(root, { autoAlpha: 1 }, t); var step = Math.min(0.35, (a.dur || 1.4) / Math.max(1, nodes.length));
      nodes.forEach(function(n, i){ var s2 = subs[n.id]; fnDraw(s2.el, t + i * step, 0.5); fnFade(s2.html, t + i * step + 0.3, 0.3, true);
        if(i > 0){ fnDraw(subs["l" + i].el, t + i * step - 0.1, 0.3); } });
      o.st.drawn = true; },
    partShow: function(t, a, id){ var s2 = this.sub(id); fnFade(s2.el, t, a.dur, true); if(s2.html) fnFade(s2.html, t, a.dur, true); },
    partHide: function(t, a, id){ var s2 = this.sub(id); fnFade(s2.el, t, a.dur, false); if(s2.html) fnFade(s2.html, t, a.dur, false); },
    highlight: function(t, a, id){ var s2 = this.sub(id), tone = a.tone || "ochre";
      if(s2.kind !== "node") throw new Error("flow: highlight takes a step, not " + id);
      tl.to(s2.tint, { attr: { fill: tones[tone] || k.card, "fill-opacity": tone === "none" ? 0 : 0.5 }, duration: 0.35 }, t); st.nodes[id].tone = tone === "none" ? null : tone; },
    mark: function(t, a, id){ var s2 = this.sub(id), on = a.state === "ok" ? s2.good : s2.bad, off = a.state === "ok" ? s2.bad : s2.good;
      if(s2.kind !== "link") throw new Error("flow: mark takes a link (l1, l2...), not " + id);
      tl.to(off, { autoAlpha: 0, duration: 0.15 }, t);
      tl.to(s2.line, { attr: { stroke: a.state === "ok" ? k.sage : k.ochre }, duration: 0.25 }, t);
      tl.set(s2.line, { attr: { "stroke-dasharray": a.state === "ok" ? "none" : "10 9" } }, t);
      tl.fromTo(on, { autoAlpha: 0, scale: 0.6, transformOrigin: "50% 50%" }, { autoAlpha: 1, scale: 1, duration: 0.3, ease: "back.out(1.6)" }, t + 0.1);
      if(a.label){ s2.tag.textContent = a.label; tl.set(s2.tag, { background: a.state === "ok" ? k.sage : k.ochre }, t);
        tl.fromTo(s2.tag, { autoAlpha: 0, x: lx + 26 }, { autoAlpha: 1, x: lx + 40, duration: 0.3, ease: "power2.out" }, t + 0.25); }
      else tl.to(s2.tag, { autoAlpha: 0, duration: 0.2 }, t);
      st.links[id] = { state: a.state === "ok" ? "ok" : "broken", label: a.label || "" }; },
    pulse: function(t, a){ var from = subs[a.from], to = subs[a.to];
      if(!from || !to || from.kind !== "node" || to.kind !== "node") throw new Error("flow: pulse needs from and to steps");
      var dot = sv("circle", { cx: lx, cy: Y(from.i) + bh / 2, r: 11, fill: k.blueStroke, stroke: ink, "stroke-width": 3 }, root);
      gsap.set(dot, { autoAlpha: 0 }); tl.set(dot, { autoAlpha: 1 }, t);
      fnAttrTween(dot, "cy", String, Y(from.i) + bh / 2, Y(to.i) + bh / 2, t, a.dur || 1.2, "power1.inOut");
      tl.to(dot, { autoAlpha: 0, duration: 0.2 }, t + (a.dur || 1.2)); } }; };

/* ---------- illustration primitives (2026-10-12): each fits its layout box (cx, cy, bw, bh) and has named states ---------- */
function fnBox(o, ctx, natW, natH){ var d = o.def, s = Math.min(d.bw / natW, d.bh / natH);
  var G = fnG(ctx.svg, d.cx, d.cy, s); return { root: G.root, g: G.g, s: s }; }
function fnSwap(t, on, off){ if(off) tl.to(off, { autoAlpha: 0, duration: 0.25 }, t); if(on) tl.fromTo(on, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3, ease: "power1.out" }, t + 0.1); }

FN_KINDS.person = function(o, ctx){ var k = FN.col, ink = k.ink, B = fnBox(o, ctx, 190, 250), g = B.g;
  var solid = sv("g", {}, g), ghost = sv("g", { "data-skip": 1 }, g), smile = sv("path", { d: "M-14,-50 Q0,-38 14,-50", fill: "none", stroke: ink, "stroke-width": 4, "stroke-linecap": "round", "data-skip": 1 }, g);
  sv("path", { d: "M-74,118 L-74,68 C-74,18 -42,-8 0,-8 C42,-8 74,18 74,68 L74,118 Z", fill: k.blue, stroke: ink, "stroke-width": 4, "stroke-linejoin": "round" }, solid);
  sv("circle", { cx: 0, cy: -62, r: 40, fill: k.annex, stroke: ink, "stroke-width": 4 }, solid);
  sv("path", { d: "M-74,118 L-74,68 C-74,18 -42,-8 0,-8 C42,-8 74,18 74,68 L74,118", fill: "none", stroke: k.ochre, "stroke-width": 4, "stroke-dasharray": "10 9" }, ghost);
  sv("circle", { cx: 0, cy: -62, r: 40, fill: "none", stroke: k.ochre, "stroke-width": 4, "stroke-dasharray": "10 9" }, ghost);
  var st = o.st.state || o.def.state || "present"; o.st.state = st;
  gsap.set(solid, { autoAlpha: st === "away" ? 0 : 1 }); gsap.set(ghost, { autoAlpha: st === "away" ? 1 : 0 }); gsap.set(smile, { autoAlpha: st === "happy" ? 1 : 0 });
  return { root: B.root,
    state: function(t, a){ var to = a.state;
      if(to === "away"){ fnSwap(t, ghost, solid); tl.to(smile, { autoAlpha: 0, duration: 0.2 }, t); }
      else { fnSwap(t, solid, ghost); tl.to(smile, { autoAlpha: to === "happy" ? 1 : 0, duration: 0.25 }, t + 0.2); }
      o.st.state = to; } }; };

FN_KINDS.chair = function(o, ctx){ var k = FN.col, ink = k.ink, B = fnBox(o, ctx, 270, 250), g = B.g;
  sv("ellipse", { cx: 0, cy: 112, rx: 92, ry: 12, fill: k.ground }, g);
  sv("rect", { x: -14, y: 54, width: 28, height: 56, fill: k.inkSoft, stroke: ink, "stroke-width": 3 }, g);
  sv("path", { d: "M-118,40 L70,40 L70,62 L-110,62 Z", fill: k.blue, stroke: ink, "stroke-width": 4, "stroke-linejoin": "round" }, g);
  sv("path", { d: "M60,40 L92,-92 L124,-86 L98,46 Z", fill: k.blue, stroke: ink, "stroke-width": 4, "stroke-linejoin": "round" }, g);
  sv("rect", { x: 84, y: -122, width: 44, height: 28, rx: 10, fill: k.blue, stroke: ink, "stroke-width": 4 }, g);
  sv("path", { d: "M-40,22 L30,22", fill: "none", stroke: ink, "stroke-width": 6, "stroke-linecap": "round" }, g);
  var who = sv("g", { "data-skip": 1 }, g), ghost = sv("g", { "data-skip": 1 }, g);
  var body = "M78,-60 C60,-20 50,10 30,36 L-96,36 L-100,22 C-60,14 -10,10 10,-10 C26,-30 40,-66 56,-78 Z";
  sv("path", { d: body, fill: k.sageTint, stroke: ink, "stroke-width": 4, "stroke-linejoin": "round" }, who);
  sv("circle", { cx: 84, cy: -98, r: 26, fill: k.annex, stroke: ink, "stroke-width": 4 }, who);
  sv("path", { d: body, fill: "none", stroke: k.ochre, "stroke-width": 4, "stroke-dasharray": "10 9" }, ghost);
  sv("circle", { cx: 84, cy: -98, r: 26, fill: "none", stroke: k.ochre, "stroke-width": 4, "stroke-dasharray": "10 9" }, ghost);
  var st = o.st.state || o.def.state || "empty"; o.st.state = st;
  gsap.set(who, { autoAlpha: st === "occupied" ? 1 : 0 }); gsap.set(ghost, { autoAlpha: st === "empty" ? 1 : 0 });
  return { root: B.root,
    state: function(t, a){ if(a.state === "occupied") fnSwap(t, who, ghost); else fnSwap(t, ghost, who); o.st.state = a.state; } }; };

FN_KINDS.calendar = function(o, ctx){ var k = FN.col, ink = k.ink, B = fnBox(o, ctx, 300, 260), g = B.g;
  var cols = 5, cw = 50, gap = 6, x0 = -((cols * cw + (cols - 1) * gap) / 2), y0 = -50, ap = { r: 1, c: 4 };
  sv("rect", { x: -150, y: -116, width: 300, height: 236, rx: 14, fill: k.card, stroke: ink, "stroke-width": 4 }, g);
  sv("path", { d: "M-150,-70 L-150,-102 Q-150,-116 -136,-116 L136,-116 Q150,-116 150,-102 L150,-70 Z", fill: ink }, g);
  [-90, 90].forEach(function(x){ sv("rect", { x: x - 6, y: -132, width: 12, height: 30, rx: 6, fill: k.paper, stroke: ink, "stroke-width": 3 }, g); });
  var cell = function(r, c){ return { x: x0 + c * (cw + gap), y: y0 + r * (cw + gap) }; };
  for(var r = 0; r < 3; r++) for(var c = 0; c < cols; c++){ var p = cell(r, c);
    sv("rect", { x: p.x, y: p.y, width: cw, height: cw, rx: 6, fill: k.paper, stroke: k.inkSoft, "stroke-width": 2, "data-fade": 1 }, g); }
  var A = cell(ap.r, ap.c), mk2 = function(fill, stroke, dash){ return sv("rect", { x: A.x, y: A.y, width: cw, height: cw, rx: 6, fill: fill, stroke: stroke, "stroke-width": 4, "stroke-dasharray": dash || "none", "data-skip": 1 }, g); };
  var states = { booked: mk2(k.blue, ink), empty: mk2(k.paper, k.ochre, "8 7"), rebooked: mk2(k.sageTint, k.sage) };
  var check = sv("path", { d: "M" + (A.x + 13) + "," + (A.y + 26) + " L" + (A.x + 22) + "," + (A.y + 35) + " L" + (A.x + 38) + "," + (A.y + 16), fill: "none", stroke: k.sage, "stroke-width": 5, "stroke-linecap": "round", "stroke-linejoin": "round", "data-skip": 1 }, g);
  var cross = sv("path", { d: "M" + (A.x + 16) + "," + (A.y + 16) + " L" + (A.x + 34) + "," + (A.y + 34) + " M" + (A.x + 34) + "," + (A.y + 16) + " L" + (A.x + 16) + "," + (A.y + 34), stroke: k.ochre, "stroke-width": 5, "stroke-linecap": "round", "data-skip": 1 }, g);
  var rem = sv("g", { "data-skip": 1 }, g);
  var st = o.st.state || o.def.state || "booked"; o.st.state = st;
  var show = function(name){ Object.keys(states).forEach(function(n){ gsap.set(states[n], { autoAlpha: n === name ? 1 : 0 }); });
    gsap.set(check, { autoAlpha: name === "rebooked" ? 1 : 0 }); gsap.set(cross, { autoAlpha: name === "empty" ? 1 : 0 }); };
  show(st);
  var drawRem = function(days, medium){ while(rem.firstChild) rem.removeChild(rem.firstChild);
    var R = cell(ap.r, ap.c - days), cx1 = R.x + cw / 2, cx2 = A.x + cw / 2, top = y0 + ap.r * (cw + gap) - 6;
    sv("rect", { x: R.x, y: R.y, width: cw, height: cw, rx: 6, fill: medium === "email" ? k.track : k.blue, stroke: ink, "stroke-width": 3 }, rem);
    if(medium === "email") sv("path", { d: "M" + (R.x + 12) + "," + (R.y + 16) + " h26 v18 h-26 Z M" + (R.x + 12) + "," + (R.y + 16) + " l13,10 l13,-10", fill: "none", stroke: ink, "stroke-width": 2.5, "stroke-linejoin": "round" }, rem);
    else sv("path", { d: "M" + (R.x + 11) + "," + (R.y + 14) + " h28 v16 h-16 l-7,7 v-7 h-5 Z", fill: k.wall, stroke: ink, "stroke-width": 2.5, "stroke-linejoin": "round" }, rem);
    var arc = sv("path", { d: "M" + cx1 + "," + top + " Q" + ((cx1 + cx2) / 2) + "," + (top - 44) + " " + cx2 + "," + top, fill: "none", stroke: k.ochre, "stroke-width": 4, "stroke-dasharray": "8 6" }, rem);
    sv("path", { d: "M" + (cx2 - 9) + "," + (top - 12) + " L" + cx2 + "," + top + " L" + (cx2 + 8) + "," + (top - 13), fill: "none", stroke: k.ochre, "stroke-width": 4, "stroke-linecap": "round" }, rem);
    return arc; };
  if(o.st.remind) drawRem(o.st.remind.days, o.st.remind.medium); else gsap.set(rem, { autoAlpha: 0 });
  return { root: B.root,
    state: function(t, a){ var to = a.state, from = o.st.state;
      tl.to([states[from], check, cross], { autoAlpha: 0, duration: 0.2 }, t);
      tl.fromTo(states[to], { autoAlpha: 0, scale: 0.7, transformOrigin: "50% 50%" }, { autoAlpha: 1, scale: 1, duration: 0.35, ease: "back.out(1.6)" }, t + 0.15);
      if(to === "rebooked") tl.fromTo(check, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.25 }, t + 0.4);
      if(to === "empty") tl.fromTo(cross, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.25 }, t + 0.4);
      o.st.state = to; },
    remind: function(t, a){ var days = Math.max(1, Math.min(3, a.days_before || 1)), arc = drawRem(days, a.medium || "text");
      tl.set(rem, { autoAlpha: 1 }, t); gsap.set(rem.firstChild, { opacity: 0 }); tl.to(rem.firstChild, { opacity: 1, duration: 0.3 }, t);
      var len = Math.ceil(arc.getTotalLength()) + 2; gsap.set(arc, { strokeDasharray: len + " " + len, strokeDashoffset: len });
      tl.to(arc, { strokeDashoffset: 0, duration: 0.6, ease: "power2.inOut" }, t + 0.25);
      tl.set(arc, { strokeDasharray: "8 6", strokeDashoffset: 0 }, t + 0.9);
      o.st.remind = { days: days, medium: a.medium || "text" }; } }; };

/* phone: messages in order (email notification, the business's text, the customer's reply); the screen clips and
   scrolls like a real one. "bury" stacks other notifications above the messages so they sink out of sight. */
FN_KINDS.phone = function(o, ctx){ var k = FN.col, ink = k.ink, B = fnBox(o, ctx, 200, 380), g = B.g, st = o.st, cid = "fnc" + (++FN.uid);
  sv("rect", { x: -92, y: -182, width: 184, height: 364, rx: 30, fill: ink }, g);
  sv("rect", { x: -78, y: -160, width: 156, height: 318, rx: 14, fill: k.wall }, g);
  sv("rect", { x: -24, y: -174, width: 48, height: 6, rx: 3, fill: k.inkSoft }, g);
  var cp = sv("clipPath", { id: cid }, ctx.defs); sv("rect", { x: -78, y: -160, width: 156, height: 318, rx: 14 }, cp);
  var area = sv("g", { "clip-path": "url(#" + cid + ")", "data-skip": 1 }, g), inner = sv("g", {}, area);
  st.msgs = st.msgs || []; st.scroll = st.scroll || 0;
  var TOP = -150, BOTTOM = 150;
  var wrap = function(text, n, max){ var out = [], line = ""; String(text).split(/\s+/).forEach(function(w){ if((line + " " + w).trim().length > n){ if(line) out.push(line); line = w; } else line = (line + " " + w).trim(); }); if(line) out.push(line); return out.slice(0, max); };
  var rowH = function(m){ return m.type === "email" ? 70 : 28 + 22 * wrap(m.text, 13, 3).length; };
  /* each row: an outer group positioned by attribute (scroll and bury move it) and an inner one gsap animates */
  var build = function(m){ var pos = sv("g", {}, inner), r = sv("g", {}, pos), h = rowH(m); r.pos = pos;
    if(m.type === "email"){ sv("rect", { x: -68, y: 0, width: 136, height: h - 8, rx: 8, fill: k.card, stroke: k.inkSoft, "stroke-width": 2 }, r);
      sv("path", { d: "M-58,12 h26 v19 h-26 Z M-58,12 l13,10 l13,-10", fill: "none", stroke: ink, "stroke-width": 2.5, "stroke-linejoin": "round" }, r);
      wrap(m.text || "Email", 11, 2).forEach(function(l, i){ fnText(r, -24, 24 + i * 18, l, { size: 14, ls: "0", upper: false, fill: ink, weight: 700 }); }); }
    else { var me = m.type === "reply", bx = me ? -50 : -68;
      sv("rect", { x: bx, y: 0, width: 118, height: h - 8, rx: 12, fill: me ? k.sageTint : k.blue, stroke: ink, "stroke-width": 2.5 }, r);
      wrap(m.text, 13, 3).forEach(function(l, i){ fnText(r, bx + 10, 24 + i * 22, l, { size: 16, ls: "0", upper: false, fill: ink, weight: 700 }); }); }
    return r; };
  var fillers = function(y){ var f = sv("g", { transform: "translate(0," + y + ")" }, inner); for(var i = 0; i < 3; i++){ sv("rect", { x: -68, y: i * 46, width: 136, height: 38, rx: 8, fill: k.track }, f); sv("rect", { x: -56, y: i * 46 + 14, width: 60, height: 6, rx: 3, fill: k.paper }, f); } return f; };
  var FH = 3 * 46 + 4, rows = [], y = TOP;
  if(st.buried){ fillers(TOP); y += FH; }
  st.msgs.forEach(function(m){ var r = build(m); r.pos.setAttribute("transform", "translate(0," + y + ")"); if(m.faded) gsap.set(r, { opacity: 0.38 }); rows.push({ el: r, y: y }); y += rowH(m); });
  inner.setAttribute("transform", "translate(0," + (-st.scroll) + ")");
  var scrollTo = function(bottom, t){ var want = Math.max(0, bottom - BOTTOM);
    if(want !== st.scroll){ fnAttrTween(inner, "transform", function(v){ return "translate(0," + (-v).toFixed(1) + ")"; }, st.scroll, want, t, 0.45, "power2.inOut"); st.scroll = want; } };
  return { root: B.root,
    message: function(t, a){ var m = { type: a.type || "text", text: a.text || "" }, r = build(m);
      r.pos.setAttribute("transform", "translate(0," + y + ")"); gsap.set(r, { autoAlpha: 0 });
      scrollTo(y + rowH(m), t);
      tl.fromTo(r, { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: 0.35, ease: "power2.out" }, t + 0.15);
      st.msgs.push(m); rows.push({ el: r, y: y }); y += rowH(m); },
    bury: function(t){ var f = fillers(TOP); gsap.set(f, { autoAlpha: 0 });
      tl.fromTo(f, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.4 }, t);
      rows.forEach(function(rw){ var y1 = rw.y + FH;
        fnAttrTween(rw.el.pos, "transform", function(v){ return "translate(0," + v.toFixed(1) + ")"; }, rw.y, y1, t, 0.45, "power2.inOut");
        tl.to(rw.el, { opacity: 0.38, duration: 0.4 }, t + 0.2); rw.y = y1; });
      y += FH; st.buried = true; st.msgs.forEach(function(m){ m.faded = true; }); } }; };

FN_KINDS.envelope = function(o, ctx){ var k = FN.col, ink = k.ink, B = fnBox(o, ctx, 220, 160), g = B.g;
  var body = sv("g", {}, g);
  sv("rect", { x: -96, y: -62, width: 192, height: 126, rx: 8, fill: k.card, stroke: ink, "stroke-width": 4 }, body);
  var flap = sv("path", { d: "M-96,-62 L0,12 L96,-62", fill: "none", stroke: ink, "stroke-width": 4, "stroke-linejoin": "round" }, body);
  var open = sv("path", { d: "M-96,-62 L0,-128 L96,-62", fill: k.card, stroke: ink, "stroke-width": 4, "stroke-linejoin": "round", "data-skip": 1 }, g);
  var dot = sv("circle", { cx: 92, cy: -62, r: 16, fill: k.ochre, stroke: ink, "stroke-width": 3, "data-skip": 1 }, g);
  var st = o.st.state || o.def.state || "sent"; o.st.state = st;
  var apply = function(to, t){ var op = to === "missed" ? 0.35 : 1;
    if(t == null){ gsap.set(body, { opacity: op }); gsap.set(dot, { autoAlpha: to === "unread" ? 1 : 0 }); gsap.set(open, { autoAlpha: to === "opened" ? 1 : 0 }); return; }
    tl.to(body, { opacity: op, duration: 0.4 }, t); tl.to(dot, { autoAlpha: to === "unread" ? 1 : 0, duration: 0.25 }, t); tl.to(open, { autoAlpha: to === "opened" ? 1 : 0, duration: 0.3 }, t); };
  apply(st);
  return { root: B.root, state: function(t, a){ apply(a.state, t); o.st.state = a.state; } }; };

FN_KINDS.building = function(o, ctx){ var k = FN.col, ink = k.ink, B = fnBox(o, ctx, 280, 260), g = B.g;
  sv("line", { x1: -140, y1: 110, x2: 140, y2: 110, stroke: ink, "stroke-width": 4, "stroke-linecap": "round" }, g);
  sv("rect", { x: -112, y: -40, width: 224, height: 150, fill: k.wall, stroke: ink, "stroke-width": 4 }, g);
  for(var i = 0; i < 7; i++) sv("rect", { x: -126 + i * 36, y: -78, width: 36, height: 38, fill: i % 2 ? k.paper : k.ochre, stroke: ink, "stroke-width": 3 }, g);
  sv("rect", { x: -78, y: -128, width: 156, height: 42, rx: 6, fill: ink }, g);
  if(o.def.sign) fnText(g, 0, -100, o.def.sign, { anchor: "middle", size: 18, fill: "#fff" });
  sv("rect", { x: -26, y: 30, width: 52, height: 80, fill: k.ochre, stroke: ink, "stroke-width": 4 }, g);
  [-92, 48].forEach(function(x){ sv("rect", { x: x, y: -16, width: 44, height: 40, fill: k.blue, stroke: ink, "stroke-width": 4 }, g); });
  return { root: B.root }; };

/* link: an arrow between two objects (points from the compiler); mark it broken or ok with a short label; pulse along it */
FN_KINDS.link = function(o, ctx){ var d = o.def, k = FN.col, ink = k.ink, a = d.from, b = d.to;
  var mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, dx = b[0] - a[0], dy = b[1] - a[1], len = Math.sqrt(dx * dx + dy * dy) || 1;
  var cx = mx - dy / len * len * (d.bend == null ? 0.18 : d.bend), cy = my + dx / len * len * (d.bend == null ? 0.18 : d.bend);
  var path = "M" + a[0] + "," + a[1] + " Q" + cx.toFixed(1) + "," + cy.toFixed(1) + " " + b[0] + "," + b[1];
  var root = sv("g", {}, ctx.svg), id = "fnm" + (++FN.uid);
  var m = sv("mask", { id: id, maskUnits: "userSpaceOnUse", x: 0, y: 0, width: W, height: H }, ctx.defs);
  var mp = sv("path", { d: path, fill: "none", stroke: "#fff", "stroke-width": 16, "stroke-linecap": "round" }, m);
  var line = sv("path", { d: path, fill: "none", stroke: d.style === "dashed" ? k.blueStroke : ink, "stroke-width": 5, "stroke-linecap": "round", "stroke-dasharray": d.style === "dashed" ? "14 11" : "none", mask: "url(#" + id + ")", "data-skip": 1 }, root);
  var mid = { x: 0.25 * a[0] + 0.5 * cx + 0.25 * b[0], y: 0.25 * a[1] + 0.5 * cy + 0.25 * b[1] };
  var ang = Math.atan2(b[1] - cy, b[0] - cx) * 180 / Math.PI;
  var head = sv("path", { d: "M-16,-11 L0,0 L-16,11", fill: "none", stroke: d.style === "dashed" ? k.blueStroke : ink, "stroke-width": 5, "stroke-linecap": "round", "stroke-linejoin": "round", transform: "translate(" + b[0] + "," + b[1] + ") rotate(" + ang.toFixed(1) + ")", "data-skip": 1 }, root);
  var bad = sv("g", { "data-skip": 1 }, root), good = sv("g", { "data-skip": 1 }, root);
  sv("circle", { cx: mid.x, cy: mid.y, r: 20, fill: k.ochre, stroke: ink, "stroke-width": 3 }, bad);
  sv("path", { d: "M" + (mid.x - 8) + "," + (mid.y - 8) + " L" + (mid.x + 8) + "," + (mid.y + 8) + " M" + (mid.x + 8) + "," + (mid.y - 8) + " L" + (mid.x - 8) + "," + (mid.y + 8), stroke: "#fff", "stroke-width": 4, "stroke-linecap": "round" }, bad);
  sv("circle", { cx: mid.x, cy: mid.y, r: 20, fill: k.sage, stroke: ink, "stroke-width": 3 }, good);
  sv("path", { d: "M" + (mid.x - 9) + "," + mid.y + " L" + (mid.x - 2) + "," + (mid.y + 7) + " L" + (mid.x + 10) + "," + (mid.y - 7), fill: "none", stroke: "#fff", "stroke-width": 4, "stroke-linecap": "round", "stroke-linejoin": "round" }, good);
  var st = o.st, tag = mk(ctx.html, "div", "fn-tag", esc(st.label || d.label || ""), "background:" + (st.mark === "ok" ? k.sage : k.ochre));
  /* label beside the midpoint, or centred above it for a mostly horizontal link */
  var above = d.labelSide === "above", lx = above ? mid.x : mid.x + (d.labelSide === "left" ? -30 : 30), ly = above ? mid.y - 34 : mid.y;
  var place = function(el){ gsap.set(el, { x: lx, y: ly, xPercent: above ? -50 : d.labelSide === "left" ? -100 : 0, yPercent: above ? -100 : -50 }); };
  place(tag);
  gsap.set(bad, { autoAlpha: st.mark === "broken" ? 1 : 0 }); gsap.set(good, { autoAlpha: st.mark === "ok" ? 1 : 0 });
  gsap.set(tag, { autoAlpha: (st.drawn && (st.label || d.label)) ? 1 : 0 });
  if(st.mark === "broken") gsap.set(line, { attr: { stroke: k.ochre, "stroke-dasharray": "10 9" } });
  if(st.mark === "ok") gsap.set(line, { attr: { stroke: k.sage, "stroke-dasharray": "none" } });
  return { root: root, html: null,
    draw: function(t, a){ tl.set(root, { autoAlpha: 1 }, t); var L = Math.ceil(mp.getTotalLength()) + 2;
      gsap.set(mp, { strokeDasharray: L + " " + L, strokeDashoffset: L }); tl.to(mp, { strokeDashoffset: 0, duration: a.dur || 0.6, ease: "power2.inOut" }, t);
      gsap.set(head, { opacity: 0 }); tl.to(head, { opacity: 1, duration: 0.2 }, t + (a.dur || 0.6) * 0.85);
      if(d.label && !st.mark){ tl.fromTo(tag, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 }, t + 0.4); st.label = d.label; }
      st.drawn = true; },
    mark: function(t, a){ var ok = a.state === "ok", on = ok ? good : bad, off = ok ? bad : good;
      tl.to(off, { autoAlpha: 0, duration: 0.15 }, t);
      tl.to(line, { attr: { stroke: ok ? k.sage : k.ochre }, duration: 0.25 }, t); tl.set(line, { attr: { "stroke-dasharray": ok ? "none" : "10 9" } }, t);
      tl.to(head, { attr: { stroke: ok ? k.sage : k.ochre }, duration: 0.25 }, t);
      tl.fromTo(on, { autoAlpha: 0, scale: 0.6, transformOrigin: "50% 50%" }, { autoAlpha: 1, scale: 1, duration: 0.3, ease: "back.out(1.6)" }, t + 0.1);
      if(a.label){ tl.to(tag, { autoAlpha: 0, duration: 0.15 }, t);
        var nt = mk(ctx.html, "div", "fn-tag", esc(a.label), "background:" + (ok ? k.sage : k.ochre));
        place(nt); gsap.set(nt, { autoAlpha: 0 });
        tl.to(nt, { autoAlpha: 1, duration: 0.3 }, t + 0.25); }
      st.mark = ok ? "ok" : "broken"; st.label = a.label || st.label; },
    pulse: function(t, a){ var dot = sv("circle", { cx: 0, cy: 0, r: 12, fill: k.blueStroke, stroke: ink, "stroke-width": 3 }, root);
      var p = sv("path", { d: path, fill: "none", stroke: "none" }, root), L = p.getTotalLength(), q = { v: 0 }, dd = a.dur || 1.2;
      var s0 = p.getPointAtLength(0); dot.setAttribute("cx", s0.x); dot.setAttribute("cy", s0.y);
      gsap.set(dot, { autoAlpha: 0 }); tl.set(dot, { autoAlpha: 1 }, t);
      tl.fromTo(q, { v: 0 }, { v: 1, duration: dd, ease: "power1.inOut", onUpdate: function(){ var pt = p.getPointAtLength(q.v * L); dot.setAttribute("cx", pt.x.toFixed(1)); dot.setAttribute("cy", pt.y.toFixed(1)); } }, t);
      tl.to(dot, { autoAlpha: 0, duration: 0.2 }, t + dd); } }; };

/* html kinds (text wraps and sizes itself): callout leader in the svg, label / tag / note / card as html */
function fnPlace(el, x, y, align){ gsap.set(el, { x: x, y: y, xPercent: align === "right" ? -100 : align === "center" ? -50 : 0, yPercent: -50 }); }
FN_KINDS.callout = function(o, ctx){ var d = o.def, k = FN.col, ink = k.ink;
  /* leader from the anchor (x, y): with lx it bends to (lx, ly) and the label sits beyond that end, away from the
     anchor; without lx it rises straight to ly and the label sits centred above it */
  var root = sv("g", {}, ctx.svg), up = d.lx == null, ly = d.ly, right = !up && d.lx >= d.x;
  var path = up ? "M" + d.x + "," + d.y + " L" + d.x + "," + ly : "M" + d.x + "," + d.y + " L" + d.x + "," + ly + " L" + d.lx + "," + ly;
  var lead = sv("path", { d: path, fill: "none", stroke: ink, "stroke-width": 3, "stroke-linejoin": "round" }, root);
  var dot = sv("circle", { cx: d.x, cy: d.y, r: 7, fill: ink }, root);
  var lab = mk(ctx.html, "div", d.style === "tag" ? "fn-tag" : d.style === "note" ? "fn-note" : "fn-lab", esc(d.text),
    d.maxw ? "white-space:normal;max-width:" + d.maxw + "px;line-height:1.25" : "");
  var px = up ? d.x : right ? d.lx + 12 : d.lx - 12, py = up ? ly - 10 : ly;
  gsap.set(lab, { x: px, y: py, xPercent: up ? -50 : right ? 0 : -100, yPercent: up ? -100 : -50 });
  gsap.set([root, lab], { autoAlpha: 0 });
  return { root: root, html: lab,
    show: function(t, a){ tl.set(root, { autoAlpha: 1 }, t); tl.fromTo(dot, { attr: { r: 0 } }, { attr: { r: 7 }, duration: 0.2 }, t);
      var len = Math.ceil(lead.getTotalLength()) + 2; gsap.set(lead, { strokeDasharray: len + " " + len, strokeDashoffset: len });
      tl.to(lead, { strokeDashoffset: 0, duration: 0.3, ease: "power2.inOut" }, t);
      tl.fromTo(lab, { autoAlpha: 0, y: py + (up ? 12 : 0), x: px + (up ? 0 : right ? -14 : 14) }, { autoAlpha: 1, y: py, x: px, duration: 0.3, ease: "power2.out" }, t + 0.25); } }; };
FN_KINDS.note = function(o, ctx){ var d = o.def;
  var el = mk(ctx.html, "div", "fn-note", esc(d.text), d.size ? "font-size:" + d.size + "px" : "");
  if(d.color) el.style.color = FN.col[d.color] || d.color;
  fnPlace(el, d.x, d.y, d.align); gsap.set(el, { autoAlpha: o.st.shown ? 1 : 0 });
  return { html: el, show: function(t, a){ tl.fromTo(el, { autoAlpha: 0, y: d.y + 10 }, { autoAlpha: 1, y: d.y, duration: a.dur || 0.35, ease: "power2.out" }, t); } }; };
FN_KINDS.card = function(o, ctx){ var d = o.def, k = FN.col;
  var el = mk(ctx.html, "div", "fn-card", (d.check === false ? "" : '<span class="bx"><svg width="26" height="22"><path d="M3,12 L10,19 L23,3" fill="none" stroke="' + k.ink + '" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg></span>') + "<span>" + esc(d.text) + "</span>",
    "width:" + (d.w || 860) + "px");
  gsap.set(el, { x: d.x, y: d.y, yPercent: 0 }); gsap.set(el, { autoAlpha: o.st.shown ? 1 : 0 });
  return { html: el, show: function(t, a){ tl.fromTo(el, { autoAlpha: 0, y: d.y + 26 }, { autoAlpha: 1, y: d.y, duration: a.dur || 0.4, ease: "power3.out" }, t); } }; };
var FN_LOCAL = { callout: 1, note: 1, card: 1 };   /* these stay in their own scene unless "carry": true */

/* ---------- actions ---------- */
function fnAct(objs, a, t){
  var parts = String(a.target || "").split("."), o = objs.byId[parts[0]], sub = parts[1];
  if(!o) throw new Error("fieldnotes: action " + a["do"] + " targets unknown object '" + a.target + "'");
  var api = o.api, verb = a["do"];
  if(sub){ var pv = verb === "show" ? "partShow" : verb === "hide" ? "partHide" : verb;
    if(!api[pv]) throw new Error("fieldnotes: " + o.kind + " cannot '" + verb + "' a part"); api[pv](t, a, sub); return; }
  if(verb === "draw" || verb === "show"){
    if(api.draw) api.draw(t, a);
    else if(api.show) api.show(t, a);
    else if(verb === "draw" && api.root){ tl.set(api.root, { autoAlpha: 1 }, t); fnDraw(api.drawEl || api.root, t, a.dur); if(api.afterDraw) api.afterDraw(t); }
    else { if(api.root) fnFade(api.root, t, a.dur, true); if(api.html) fnFade(api.html, t, a.dur, true); if(api.afterDraw) api.afterDraw(t); }
    o.st.drawn = true; o.st.shown = true; return; }
  if(verb === "hide"){ if(api.root) fnFade(api.root, t, a.dur, false); if(api.html) fnFade(api.html, t, a.dur, false); o.st.shown = false; o.st.drawn = false; return; }
  if(!api[verb]) throw new Error("fieldnotes: " + o.kind + " " + o.id + " has no action '" + verb + "'");
  api[verb](t, a); }

/* ---------- chapter furniture ---------- */
function fnPaper(sc){ mk(sc, "div", "fn-bg"); mk(sc, "div", "fn-grid"); mk(sc, "div", "fn-shade");
  var g = sv("svg", { "class": "abs", width: W, height: H, style: "mix-blend-mode:multiply;opacity:.55" }, sc);
  var f = sv("filter", { id: "fng" + (++FN.uid) }, g);
  sv("feTurbulence", { type: "fractalNoise", baseFrequency: ".85", numOctaves: 2, seed: 7 }, f);
  sv("feColorMatrix", { values: "0 0 0 0 .45  0 0 0 0 .40  0 0 0 0 .33  0 0 0 .09 0" }, f);
  sv("rect", { width: W, height: H, filter: "url(#" + f.id + ")" }, g); }
function fnBands(t){ var k = FN.col, box = mk($("root"), "div", "fn-bands");
  [k.sageWipe, k.ink, k.ochre].forEach(function(c, i){ var b = mk(box, "i", null, null, "background:" + c + ";left:0");
    gsap.set(b, { rotation: 16, x: W + 500 + i * 220 });
    tl.to(b, { x: -1500 + i * 220, duration: 0.74, ease: "power2.inOut" }, t - 0.4 + i * 0.04); });
  tl.set(box, { autoAlpha: 1 }, t - 0.37); tl.set(box, { autoAlpha: 0 }, t + 0.45); }

TYPES.fieldnotes = function(sc, s, d, C){
  if(!V) throw new Error("fieldnotes (" + s.id + ") is vertical only");
  var T = function(v, dflt){ return fnT(s, C, v, dflt); }, k = FN.col, Lh = FN.L;
  fnPaper(sc);
  var svg = sv("svg", { "class": "abs", width: W, height: H, viewBox: "0 0 " + W + " " + H, style: "overflow:visible" }, sc);
  var ctx = { svg: svg, defs: sv("defs", {}, svg), html: mk(sc, "div", "abs", null, "width:" + W + "px;height:" + H + "px") };
  /* header with the chapter progress rule */
  var h = d.header || {}, idx = h.index || 1, tot = h.total || 1;
  mk(sc, "div", "fn-hdr", "<span><b>" + esc(h.brand || "") + "</b> " + esc(h.label || "FIELD NOTES") + "</span><span>" + esc(h.chapter || "") + ' <b style="margin-left:.5em">' + String(idx).padStart(2, "0") + "/" + String(tot).padStart(2, "0") + "</b></span>");
  var rule = mk(sc, "div", "fn-rule"), prog = mk(rule, "i");
  gsap.set(prog, { width: ((idx - 1) / tot * 100) + "%" });
  tl.to(prog, { width: (idx / tot * 100) + "%", duration: 0.6, ease: "power2.inOut" }, s.start + 0.1);
  /* kicker + headline: rise line by line, the emphasis wipes in on its word */
  var hd = d.headline || {}, t0 = T(hd.at, s.start + (d.transition === "bands" ? 0.35 : 0.15)), hide = [];
  if(d.kicker){ var kk = mk(sc, "div", "fn-kick", "<i></i><span>" + esc(d.kicker) + "</span>"); gsap.set(kk, { autoAlpha: 0 }); fnFade(kk, t0 - 0.05, 0.3, true); hide.push(kk); }
  var head = mk(sc, "div", "fn-head");
  var f = { el: head, size: hd.size || Lh.headSize, max: hd.max || Lh.headMax }; FN.fits.push(f);
  (hd.lines || []).forEach(function(ln, i){ var L1 = mk(head, "div", "fn-ln"), tx = mk(L1, "span", "fn-tx" + (ln.em ? " fn-em-" + ln.em : ""), esc(ln.text));
    var tl0 = t0 + i * 0.25; gsap.set(L1, { autoAlpha: 0, y: 24 }); tl.fromTo(L1, { autoAlpha: 0, y: 24 }, { autoAlpha: 1, y: 0, duration: 0.35, ease: "power3.out" }, tl0);
    var te = T(ln.at, tl0 + 0.3);
    if(ln.em === "ochre"){ tl.to(tx, { backgroundSize: "100% 100%", duration: 0.3, ease: "power2.inOut" }, te); tl.to(tx, { color: "#ffffff", duration: 0.15 }, te + 0.15); }
    else if(ln.em === "blue") tl.to(tx, { backgroundSize: "100% 22%", duration: 0.35, ease: "power2.inOut" }, te);
    else if(ln.em === "sage") tl.to(tx, { backgroundSize: "100% 46%", duration: 0.35, ease: "power2.inOut" }, te); });
  fnFit(f); hide.push(head);
  /* objects: the previous chapter's objects in their final state, then this scene's own (same id = same object) */
  var list = [], byId = {}, prev = d.continue === false ? null : FN.carry;
  if(prev) Object.keys(prev).forEach(function(id){ var c = prev[id]; byId[id] = { id: id, kind: c.kind, def: c.def, st: JSON.parse(JSON.stringify(c.st)), carried: true }; list.push(byId[id]); });
  (d.objects || []).forEach(function(od){
    if(!FN_KINDS[od.kind] && !(byId[od.id] && !od.kind)) throw new Error("fieldnotes " + s.id + ": unknown object kind " + od.kind);
    if(byId[od.id]){ var o0 = byId[od.id]; o0.def = Object.assign({}, o0.def, od); }
    else { byId[od.id] = { id: od.id, kind: od.kind, def: od, st: { drawn: !!od.drawn, shown: !!od.shown } }; list.push(byId[od.id]); } });
  list.forEach(function(o){ o.api = FN_KINDS[o.kind](o, ctx);
    var vis = o.st.drawn || o.st.shown;
    if(o.api.root) gsap.set(o.api.root, { autoAlpha: vis ? 1 : 0 });
    if(o.api.html) gsap.set(o.api.html, { autoAlpha: vis ? 1 : 0 }); });
  /* actions, in time order */
  (d.actions || []).map(function(a, i){ return { a: a, t: T(a.at, s.start), i: i }; })
    .sort(function(x, y){ return x.t - y.t || x.i - y.i; })
    .forEach(function(x){ fnAct({ byId: byId }, x.a, x.t); });
  list.forEach(function(o){ if(o.api.finish) o.api.finish(s); });
  FN.carry = {};
  list.forEach(function(o){ var keep = o.def.carry == null ? !FN_LOCAL[o.kind] : !!o.def.carry;
    if(keep) FN.carry[o.id] = { kind: o.kind, def: o.def, st: o.st }; });
  if(d.transition === "bands") fnBands(s.start);
  /* the headline leaves before the next chapter's arrives */
  var nx = s.next && P.scenes.filter(function(q){ return q.id === s.next; })[0];
  if(nx && nx.type === "fieldnotes") tl.to(hide, { autoAlpha: 0, y: "-=40", duration: 0.28, ease: "power2.in" }, s.end - 0.34);
};
