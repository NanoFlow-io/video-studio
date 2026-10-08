/* ===================== HUMOUR TREATMENT (engine/humour.js) =====================
   studio/cuts.py splices this file into scenes.js just before the build section, and only for projects whose
   scenes set data.headline (hook) or data.clean (end_card), so every other page stays byte-identical. It wraps
   TYPES.hook and TYPES.end_card; scenes without those fields go straight to the original types.
   Headline: comic lettering (DM Sans at its heaviest, white, thick black outline, hard black drop shadow) on a
   hand-painted yellow brushstroke, the trailing punctuation (or the last word) pink with a pink swoosh under the last
   word. A finished picture from frame 0; the only motion is a small wobble from 0.4 s, which never hides it.
   Clean end card: the logo pops on `logo`, then a larger two-line tagline; nothing else. */
var HUM = { yellow: "#ffd23f", yellowDeep: "#f2b705", pink: COL.secondary || "#d92677", edge: "#000000" };
var hookBase = TYPES.hook, endBase = TYPES.end_card;
/* humour text is fitted again (then re-laid out) once the title font has really loaded: document.fonts.ready can
   resolve before the page has asked for the font, which leaves a fit made with the fallback font */
var HFIT = [];
function hFit(el, w, big, small, lines, lh, after){ fitText(el, w, big, small, lines, lh);
  HFIT.push({ el: el, w: w, big: big, small: small, lines: lines, lh: lh, after: after }); if(after) after(); }
if(document.fonts && document.fonts.load){
  var hFam = getComputedStyle(document.documentElement).getPropertyValue("--f-title").trim() || "'DM Sans'";
  Promise.all([document.fonts.load("1000 100px " + hFam), document.fonts.load("800 100px " + hFam)]).then(function(){
    HFIT.forEach(function(f){ doFit(f); if(f.after) f.after(); }); }); }

/* a rough brushstroke as one closed path in a w x h box: ragged top and bottom edges, narrower bristle-tip ends */
function brushPath(R, w, h, rough){
  var n = 28, top = [], low = [], i, pts = [];
  for(i = 0; i <= n; i++){ var x = i / n * w, k = Math.min(1, i / 3, (n - i) / 3), half = h * 0.5 * (0.62 + 0.38 * k);
    top.push([x, h / 2 - half + (R() - 0.5) * rough]); low.push([x, h / 2 + half + (R() - 0.5) * rough]); }
  pts = pts.concat(top);
  for(i = 1; i < 6; i++) pts.push([w + (i % 2 ? 6 + R() * 26 : -R() * 12), top[n][1] + (low[n][1] - top[n][1]) * i / 6]);
  pts = pts.concat(low.reverse());
  for(i = 1; i < 6; i++) pts.push([(i % 2 ? -6 - R() * 18 : R() * 10), low[n][1] + (top[0][1] - low[n][1]) * i / 6]);
  return "M" + pts.map(function(p){ return p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" L") + " Z"; }

function headline(sc, s, hd){
  var pos = hd.pos || [0.5, 0.2], wt = Math.round((hd.width || 0.86) * W), size = hd.size || 150, R = rng(s.seed + 7);
  var words = String(hd.text).trim().split(/\s+/), last = words.pop(), m = /^(.*?)([?!.,]+)$/.exec(last);
  var tail = m && m[1] ? esc(m[1]) + '<span style="color:' + HUM.pink + '">' + esc(m[2]) + '</span>' : '<span style="color:' + HUM.pink + '">' + esc(last) + '</span>';
  var hl = mk(sc, "div", "abs", null, "width:" + wt + "px");
  var brush = sv("svg", { "class": "abs", viewBox: "0 0 1000 300", preserveAspectRatio: "none", style: "overflow:visible" }, hl);
  sv("path", { d: brushPath(R, 1000, 300, 26), fill: HUM.yellow }, brush);
  for(var k = 0; k < 3; k++){ var y = 60 + k * 85 + R() * 30, x0 = 30 + R() * 160, x1 = x0 + 220 + R() * 260;   /* dry-brush streaks */
    sv("path", { d: "M" + x0.toFixed(1) + " " + y.toFixed(1) + " L" + x1.toFixed(1) + " " + (y + (R() - 0.5) * 10).toFixed(1), stroke: HUM.yellowDeep, "stroke-width": 4 + R() * 5, "stroke-linecap": "round", opacity: 0.3, fill: "none" }, brush); }
  var swoosh = sv("svg", { "class": "abs", viewBox: "0 0 300 40", preserveAspectRatio: "none", style: "overflow:visible" }, hl);
  sv("path", { d: "M4 27 C 70 10, 190 2, 296 9 C 214 13, 112 22, 12 37 Z", fill: HUM.pink, stroke: HUM.edge, "stroke-width": 3, "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round" }, swoosh);
  var txt = mk(hl, "div", null, words.map(function(w){ return "<span>" + esc(w) + "</span>"; }).concat(["<span>" + tail + "</span>"]).join(" "),
    "position:relative;width:" + wt + "px;text-align:center;white-space:normal;font-family:" + FT + ";font-weight:1000;letter-spacing:-.02em;line-height:.95;color:#fff;" +
    "-webkit-text-stroke:.14em " + HUM.edge + ";paint-order:stroke fill;filter:drop-shadow(.045em .065em 0 " + HUM.edge + ")");
  /* brush, swoosh and the frame clamp follow the fitted lines (again once the web fonts have loaded) */
  function place(){
    var fs = parseFloat(txt.style.fontSize) || size, sp = txt.children, lines = [];
    for(var i = 0; i < sp.length; i++){ var e = sp[i], t = e.offsetTop, ln = lines[lines.length - 1];
      if(!ln || Math.abs(ln.top - t) > 2) lines.push(ln = { top: t, l: e.offsetLeft, r: e.offsetLeft + e.offsetWidth, b: t + e.offsetHeight });
      else { ln.l = Math.min(ln.l, e.offsetLeft); ln.r = Math.max(ln.r, e.offsetLeft + e.offsetWidth); ln.b = Math.max(ln.b, t + e.offsetHeight); } }
    var bl = Math.min.apply(null, lines.map(function(q){ return q.l; })), br = Math.max.apply(null, lines.map(function(q){ return q.r; }));
    var bt = lines[0].top, bb = lines[lines.length - 1].b, px = fs * 0.32, py = fs * 0.1;
    brush.style.cssText = "overflow:visible;left:" + (bl - px) + "px;top:" + (bt - py) + "px;width:" + (br - bl + 2 * px) + "px;height:" + (bb - bt + 2 * py) + "px";
    var lw = sp[sp.length - 1];
    swoosh.style.cssText = "overflow:visible;left:" + (lw.offsetLeft - fs * 0.06) + "px;top:" + (lw.offsetTop + lw.offsetHeight - fs * 0.16) + "px;width:" + (lw.offsetWidth + fs * 0.16) + "px;height:" + fs * 0.3 + "px";
    /* centre on pos, kept inside the frame */
    var hw = (br - bl) / 2 + px + 24, hh = hl.offsetHeight / 2 + py + 24;
    gsap.set(hl, { x: clamp(pos[0] * W, hw, W - hw), y: clamp(pos[1] * H, hh, H - hh), xPercent: -50, yPercent: -50 }); }
  gsap.set(hl, { rotation: -2.5 });
  hFit(txt, wt, size, Math.max(36, Math.round(size * 0.4)), 2, 0.95, place);
  var t0 = s.start + 0.4, n = Math.floor((s.end - 0.1 - t0) / 0.9);
  if(n >= 2) tl.to(hl, { rotation: -1, scale: 1.03, duration: 0.9, ease: "sine.inOut", yoyo: true, repeat: n - 1 }, t0);
  return hl; }

/* data.headline replaces the pill (footage layout only); everything else in the hook is unchanged */
TYPES.hook = function(sc, s, d, C){
  if(!(FOOTAGE && d.headline && d.headline.text)) return hookBase(sc, s, d, C);
  var dd = {}; for(var k in d) dd[k] = d[k]; dd.pill = "";
  hookBase(sc, s, dd, C);
  headline(sc, s, d.headline); };

/* data.clean: logo and tagline only (no button, web address, confetti, floating shapes or note). Cue: logo */
TYPES.end_card = function(sc, s, d, C){
  if(d.clean !== true) return endBase(sc, s, d, C);
  bg(sc, s.bg);
  var cx = V ? 540 : 860, tw = V ? 980 : 1500;
  var logo = mk(sc, "div", "abs", '<img src="' + ASSET + P.brand.logo + '" style="width:100%;display:block">', "width:" + (V ? 860 : 900) + "px");
  at(logo, cx, V ? 700 : 330); pop(logo, C("logo"), { from: 0.6, rot: -2 });
  var tag = mk(sc, "div", "title", String(d.tagline || "").split(" | ").map(esc).join("<br>"),
    "width:" + tw + "px;font-weight:800;text-align:center;line-height:1.12;color:var(--ink)");
  hFit(tag, tw, V ? 96 : 84, 48, 2, 1.12);
  at(tag, cx, V ? 880 : 500, -50, 0); enter(tag, C("logo") + 0.35, { y: 40 });
  if(!FOOTAGE){ var r = bot(sc, s.pose, V ? { cx: 540, by: 1800, h: 560 } : { cx: 1640, by: 1040, h: 620 }); botIn(r, s, V ? { y: 300 } : { x: 400 }); }
};

