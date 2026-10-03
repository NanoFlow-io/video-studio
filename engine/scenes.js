/* Video Studio engine: one scene library, two cuts (window.CUT = landscape | vertical).
   Scenes come from window.PROJECT.scenes (project.json); each has a `type` below, its own `data`,
   a mascot `pose` and a background. Every timed action reads its time from window.BEATS (built by
   studio/beats.py from the voiceover word timings), so picture and sound share one clock.
   Pure function of timeline time: seeded random only, no clocks. */
(function(){
"use strict";
var B = window.BEATS, P = window.PROJECT, CUT = window.CUT, V = CUT === "vertical";
var W = V ? 1080 : 1920, H = V ? 1920 : 1080;
var COL = P.palette, FT = "var(--f-title)", ASSET = "assets/project/";
var CUE = {}, SCN = {};
B.cues.forEach(function(c){ CUE[c.id] = c.t; });
B.scenes.forEach(function(s){ SCN[s.id] = s; });
var tl = gsap.timeline({ paused: true, defaults: { immediateRender: false } });

/* ---------- layout ---------- */
var L = V ? {
  title: { x: 540, y: 250, ax: -50, size: 104 },
  panel: { cx: 540, cy: 740, s: 1.0 },
  bot: { cx: 540, by: 1810, h: 540 },
  cap: { cx: 540, cy: 1150 }
} : {
  title: { x: 110, y: 100, ax: 0, size: 100 },
  panel: { cx: 1250, cy: 620, s: 1.12 },
  bot: { cx: 400, by: 1020, h: 620 },
  cap: null
};

/* ---------- helpers ---------- */
function rng(seed){ return function(){ seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
var SVGNS = "http://www.w3.org/2000/svg";
function $(id){ return document.getElementById(id); }
function mk(parent, tag, cls, html, css){ var e = document.createElement(tag); if(cls) e.className = cls; if(html != null) e.innerHTML = html; if(css) e.style.cssText = css; parent.appendChild(e); return e; }
function sv(tag, attrs, parent){ var e = document.createElementNS(SVGNS, tag); for(var k in attrs) e.setAttribute(k, attrs[k]); if(parent) parent.appendChild(e); return e; }
function at(el, x, y, ax, ay){ gsap.set(el, { x: x, y: y, xPercent: ax == null ? -50 : ax, yPercent: ay == null ? -50 : ay }); return el; }
function box(parent, x, y, w, h, cls, html, css){ return mk(parent, "div", cls || "card", html, "left:" + x + "px;top:" + y + "px;width:" + w + "px;height:" + h + "px;" + (css || "")); }
function esc(s){ return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

/* motion vocabulary: 0.4 s expo.inOut entrances with moving blur that settles to zero */
function pop(el, t, o){ o = o || {}; gsap.set(el, { autoAlpha: 0 });
  tl.fromTo(el, { autoAlpha: 0, scale: o.from || 0.4, rotation: o.rot == null ? -5 : o.rot }, { autoAlpha: 1, scale: 1, rotation: 0, duration: o.d || 0.42, ease: o.ease || "back.out(2.2)" }, t); }
function enter(el, t, from, d){ d = d || 0.4; gsap.set(el, { autoAlpha: 0 });
  var f = { autoAlpha: 0 }, to = { autoAlpha: 1, duration: d, ease: "expo.inOut" };
  for(var k in from){ var cur = Number(gsap.getProperty(el, k)) || 0;
    if(k === "scale"){ f[k] = from[k]; to[k] = cur || 1; continue; }
    f[k] = cur + from[k]; to[k] = cur; }
  tl.fromTo(el, f, to, t);
  tl.fromTo(el, { filter: "blur(0px)" }, { filter: "blur(16px)", duration: d / 2, ease: "power1.in" }, t);
  tl.to(el, { filter: "blur(0px)", duration: d / 2, ease: "power1.out" }, t + d / 2); }
function slam(el, t, s){ gsap.set(el, { autoAlpha: 0 });
  tl.fromTo(el, { autoAlpha: 0, scale: s || 2.0, filter: "blur(14px)" }, { autoAlpha: 1, scale: 1, filter: "blur(0px)", duration: 0.26, ease: "power4.in" }, t - 0.2);
  tl.to(el, { scale: 1.05, duration: 0.08, yoyo: true, repeat: 1, ease: "power1.out" }, t + 0.06); }
function shake(el, t, amp){ amp = amp || 14; tl.to(el, { keyframes: [{ x: "+=" + amp, duration: 0.04 }, { x: "-=" + amp * 2, duration: 0.05 }, { x: "+=" + amp * 1.5, duration: 0.05 }, { x: "-=" + amp * 0.5, duration: 0.05 }] }, t); }
function drawPath(p, t, d){ var len = Math.ceil(p.getTotalLength()) + 2; gsap.set(p, { strokeDasharray: len + "px " + len + "px", strokeDashoffset: len }); tl.to(p, { strokeDashoffset: 0, duration: d || 0.4, ease: "power2.inOut" }, t); }
function typeText(el, text, t, d){ var o = { n: 0 }; el.textContent = "";
  tl.fromTo(o, { n: 0 }, { n: text.length, duration: d, ease: "none", onUpdate: function(){ el.textContent = text.slice(0, Math.round(o.n)); } }, t); }
function confetti(parent, cx, cy, n, t, seed){
  var R = rng(seed), cols = [COL.primary, COL.secondary, COL.accent, COL.primary2, "#ffd84d", COL.good];
  for(var i = 0; i < n; i++){ var w = 12 + R() * 14, h = 8 + R() * 16;
    var e = mk(parent, "div", "abs", null, "width:" + w + "px;height:" + h + "px;border-radius:3px;background:" + cols[i % cols.length]);
    gsap.set(e, { x: cx, y: cy, autoAlpha: 0 });
    var ang = -Math.PI / 2 + (R() - 0.5) * Math.PI * 1.3, sp = 380 + R() * 520;
    tl.set(e, { autoAlpha: 1 }, t);
    tl.to(e, { x: cx + Math.cos(ang) * sp, duration: 2.2, ease: "power2.out" }, t);
    tl.to(e, { y: cy + Math.sin(ang) * sp * 0.75, duration: 0.6, ease: "power2.out" }, t);
    tl.to(e, { y: cy + 1100, duration: 1.7, ease: "power1.in" }, t + 0.6);
    tl.to(e, { rotation: (R() - 0.5) * 1080, rotationX: R() * 720, duration: 2.3, ease: "none" }, t); } }
function floats(parent, seed, n, colors, t0, t1){
  var R = rng(seed);
  for(var i = 0; i < n; i++){ var s = 14 + R() * 30;
    var e = mk(parent, "div", "abs", null, "width:" + s + "px;height:" + s + "px;background:" + colors[i % colors.length] + ";border-radius:" + (R() < 0.5 ? "50%" : Math.round(s * 0.3) + "px") + ";opacity:" + (0.25 + R() * 0.35));
    gsap.set(e, { x: R() * W, y: R() * H, rotation: R() * 90 });
    tl.to(e, { x: "+=" + (R() - 0.5) * 160, y: "-=" + (40 + R() * 120), rotation: "+=" + (R() - 0.5) * 120, duration: t1 - t0, ease: "none" }, t0); } }

var ICON = {
  phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.9.6 2.8.7a2 2 0 0 1 1.7 2z"/></svg>',
  mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
  msg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="currentColor"><polygon points="12 2 15.1 8.3 22 9.3 17 14.1 18.2 21 12 17.8 5.8 21 7 14.1 2 9.3 8.9 8.3 12 2"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/></svg>',
  lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><polygon points="7 4 20 12 7 20 7 4"/></svg>',
  cal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>',
  person: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>'
};
function ic(name, bg, size){ return '<span class="ic" style="background:' + bg + (size ? ";width:" + size + "px;height:" + size + "px" : "") + '">' + (ICON[name] || ICON.check) + '</span>'; }

/* scene scaffolding */
function bgOf(key){ return (P.backgrounds && P.backgrounds[key]) || key; }
function bg(sc, key){ return mk(sc, "div", "bg", null, "background:" + bgOf(key)); }
function panel(sc, pw, ph){
  var p = mk(sc, "div", "panel", null, "width:" + pw + "px;height:" + ph + "px");
  var c = L.panel, s = V ? Math.min(1.2, 1010 / pw, 720 / ph) : c.s;
  gsap.set(p, { x: c.cx - pw / 2, y: c.cy - ph / 2, scale: s }); return p; }
function bot(sc, pose, o){ o = o || {};
  var b = L.bot, h = o.h || b.h, w = h * (P.pose_aspect || 0.7466);
  var d = mk(sc, "div", "bot", '<div class="sh"></div><img src="' + ASSET + "poses/" + pose + '.webp" alt="">', "width:" + w + "px;height:" + h + "px");
  gsap.set(d, { x: (o.cx || b.cx) - w / 2, y: (o.by || b.by) - h }); return d; }
function botIn(d, s, from){ enter(d, s.start + 0.12, from || (V ? { y: 260 } : { x: -320 }));
  var img = d.querySelector("img"), t0 = s.start + 0.7, n = Math.max(1, Math.floor((s.end - 0.3 - t0) / 1.1));
  tl.to(img, { y: -12, duration: 0.55, ease: "sine.inOut", yoyo: true, repeat: n * 2 - 1 }, t0); }
function title(sc, html, t, o){ o = o || {};
  var c = L.title;
  var el = mk(sc, "div", "title", html, "font-size:" + (o.size || c.size) + "px;color:" + (o.color || "var(--ink)") + (V ? ";text-align:center" : ""));
  at(el, c.x, c.y, c.ax, 0); enter(el, t, { y: 60 }); return el; }
function chip(parent, html, x, y, cls){ var c = mk(parent, "div", "chip " + (cls || ""), html); gsap.set(c, { x: x, y: y }); return c; }
function grad(a, b){ return esc(a) + (b ? ' <span class="grad">' + esc(b) + '</span>' : ""); }

/* scene switching + wipe */
B.scenes.forEach(function(s){ tl.set("#" + s.id, { autoAlpha: 1 }, s.start); if(s.end < B.duration) tl.set("#" + s.id, { autoAlpha: 0 }, s.end); });
var wipeEl = $("wipe"), WW = Math.round(W * 1.7), wipeDir = 1;
function wipe(t, color, lead){
  var dir = wipeDir; wipeDir = -wipeDir;
  tl.set(wipeEl, { autoAlpha: 1, background: color, skewX: -12 * dir }, t - 0.25);
  tl.set(wipeEl.firstChild, { background: lead, left: dir > 0 ? -90 : WW }, t - 0.25);
  tl.fromTo(wipeEl, { x: dir > 0 ? W + 200 : -WW - 200 }, { x: dir > 0 ? -WW - 200 : W + 200, duration: 0.5, ease: "expo.inOut" }, t - 0.25);
  tl.fromTo(wipeEl, { filter: "blur(0px)" }, { filter: "blur(10px)", duration: 0.25, ease: "power1.in" }, t - 0.25);
  tl.to(wipeEl, { filter: "blur(0px)", duration: 0.25, ease: "power1.out" }, t);
  tl.set(wipeEl, { autoAlpha: 0 }, t + 0.26); }

/* iso floor (isometric clay tiles that build in on a diagonal wave) */
function isoFloor(sc, cx, cy, cols, rows, s, a, b, t0){
  var svg = sv("svg", { "class": "abs", width: W, height: H, viewBox: "0 0 " + W + " " + H, style: "overflow:visible" }, sc);
  function Pt(x, y, z){ return [cx + (x - y) * s * 0.866, cy + (x + y) * s * 0.5 - (z || 0) * s]; }
  function pts(arr){ return arr.map(function(p){ var q = Pt(p[0], p[1], p[2]); return q[0].toFixed(1) + "," + q[1].toFixed(1); }).join(" "); }
  function shade(hex, k){ var c = [1, 3, 5].map(function(i){ return parseInt(hex.substr(i, 2), 16); }); return "rgb(" + c.map(function(v){ return Math.round(k > 0 ? v + (255 - v) * k : v * (1 + k)); }).join(",") + ")"; }
  var order = []; for(var i = 0; i < cols; i++) for(var j = 0; j < rows; j++) order.push([i - cols / 2, j - rows / 2, i + j]);
  order.sort(function(p, q){ return p[2] - q[2]; });
  order.forEach(function(p){ var x = p[0] + 0.05, y = p[1] + 0.05, w = 0.9, h = 0.16, base = (p[2] % 2) ? a : b;
    var g = sv("g", {}, svg);
    sv("polygon", { points: pts([[x, y + w, 0], [x + w, y + w, 0], [x + w, y + w, h], [x, y + w, h]]), fill: shade(base, -0.06), stroke: shade(base, -0.06), "stroke-width": 3, "stroke-linejoin": "round" }, g);
    sv("polygon", { points: pts([[x + w, y, 0], [x + w, y + w, 0], [x + w, y + w, h], [x + w, y, h]]), fill: shade(base, -0.16), stroke: shade(base, -0.16), "stroke-width": 3, "stroke-linejoin": "round" }, g);
    sv("polygon", { points: pts([[x, y, h], [x + w, y, h], [x + w, y + w, h], [x, y + w, h]]), fill: shade(base, 0.14), stroke: shade(base, 0.14), "stroke-width": 3, "stroke-linejoin": "round" }, g);
    gsap.set(g, { autoAlpha: 0 });
    tl.fromTo(g, { autoAlpha: 0, y: -40 }, { autoAlpha: 1, y: 0, duration: 0.35, ease: "back.out(2)" }, t0 + p[2] * 0.03); });
  return svg; }

function featureBase(sc, s, d){
  bg(sc, s.bg);
  floats(sc, s.seed, 10, d.floats || [COL.primary2, COL.accent, "#ffffff"], s.start, s.end);
  var r = bot(sc, s.pose, {}); botIn(r, s);
  title(sc, grad(d.title, d.title_accent), s.start + 0.2, { color: d.title_color });
  return r; }

/* ============================ SCENE TYPES ============================
   Each type documents its cue names; project.json supplies one cue per name. */
var TYPES = {};

/* cues: tiles, bot, ring */
TYPES.incoming_call = function(sc, s, d, C){
  bg(sc, s.bg);
  floats(sc, s.seed, 10, [COL.accent, COL.primary2, "#ffd84d"], s.start, s.end);
  isoFloor(sc, V ? 540 : 400, V ? 1600 : 880, 5, 5, V ? 70 : 64, d.floor_a || "#f6dcc2", d.floor_b || "#f1d1b2", C("tiles"));
  var r = bot(sc, s.pose, { h: 640, by: V ? 1720 : 1000 }); botIn(r, s, { y: 300 });
  var p = panel(sc, 620, 340);
  var rings = sv("svg", { "class": "abs", width: 620, height: 340, viewBox: "0 0 620 340", style: "overflow:visible" }, p);
  var card = box(p, 50, 20, 520, 300, "card", '<div style="position:absolute;left:34px;top:28px;right:34px"><div class="sub" style="letter-spacing:.14em">' + esc(d.label) + '</div><h4 style="font-size:46px;line-height:1.1;margin-top:8px">' + esc(d.name) + '</h4><div class="sub" style="margin-top:6px">' + esc(d.sub) + '</div></div>' +
    '<span style="position:absolute;left:34px;bottom:30px;width:200px;height:64px;border-radius:32px;background:' + COL.bad + ';color:#fff;display:grid;place-items:center"><span style="width:32px;height:32px;display:block;transform:rotate(135deg)">' + ICON.phone + '</span></span><span style="position:absolute;right:34px;bottom:30px;width:200px;height:64px;border-radius:32px;background:' + COL.good + ';color:#fff;display:grid;place-items:center"><span style="width:32px;height:32px;display:block">' + ICON.phone + '</span></span>');
  enter(card, s.start + 0.5, { y: 80 });
  for(var i = 0; i < 3; i++){ var c = sv("circle", { cx: 310, cy: 170, r: 170, fill: "none", stroke: COL.accent, "stroke-width": 6 }, rings);
    gsap.set(c, { autoAlpha: 0, transformOrigin: "310px 170px" });
    tl.fromTo(c, { autoAlpha: 0.8, scale: 0.9 }, { autoAlpha: 0, scale: 1.6, duration: 0.9, ease: "power1.out" }, C("ring") + i * 0.3); }
  shake(card, C("ring"), 10); shake(card, C("ring") + 0.45, 10);
};

/* cues: missed, list, next, booked */
TYPES.missed_to_competitor = function(sc, s, d, C){
  bg(sc, s.bg);
  floats(sc, s.seed, 10, [COL.accent, COL.primary2, "#ffd84d"], s.start, s.end);
  var r = bot(sc, s.pose, { h: 640, by: V ? 1720 : 1000 }); botIn(r, s, { y: 200 });
  var p = panel(sc, 820, 620);
  var call = box(p, 160, 0, 500, 130, "card", '<span style="position:absolute;left:30px;top:42px">' + ic("phone", COL.good) + '</span><h4 style="position:absolute;left:100px;top:44px">' + esc(d.incoming) + '</h4>');
  enter(call, s.start + 0.1, { y: -60 });
  var red = box(p, 160, 0, 500, 130, "card", '<span style="position:absolute;left:30px;top:42px">' + ic("x", COL.bad) + '</span><h4 style="position:absolute;left:100px;top:44px;color:' + COL.bad + '">' + esc(d.missed) + '</h4>', "background:#fff5f5");
  gsap.set(red, { autoAlpha: 0 }); tl.fromTo(red, { autoAlpha: 0, rotationX: -90 }, { autoAlpha: 1, rotationX: 0, duration: 0.35, ease: "back.out(2)" }, C("missed"));
  var list = box(p, 60, 190, 700, 410, "card", '<div style="position:absolute;left:24px;right:24px;top:22px;height:60px;border-radius:30px;background:#f1eef6;display:flex;align-items:center;gap:12px;padding:0 20px;font-weight:800;font-size:24px;color:var(--ink2)"><span style="width:28px;height:28px">' + ICON.search + '</span>' + esc(d.search) + '</div>');
  var win = d.winner == null ? 1 : d.winner;
  var rowEls = d.results.map(function(rw, k){ return mk(list, "div", "row", '<span class="dot" style="background:' + (k ? COL.primary2 : "#c9c2d6") + '"></span><div>' + esc(rw[0]) + '<small>' + esc(rw[1]) + '</small></div>', "top:" + (104 + k * 96) + "px;opacity:" + (k ? 1 : 0.45)); });
  enter(list, C("list"), { y: 120 });
  var fly = mk(p, "div", "abs", ic("phone", COL.good), ""); gsap.set(fly, { x: 390, y: 40, autoAlpha: 0 });
  tl.set(fly, { autoAlpha: 1 }, C("next") - 0.15);
  tl.to(fly, { x: 600, y: 300 + 96 * win + 10, duration: 0.5, ease: "power2.inOut" }, C("next") - 0.15);
  tl.to(fly, { autoAlpha: 0, duration: 0.1 }, C("next") + 0.4);
  var st = chip(list, esc(d.stamp), 520, 118 + 96 * win, "good"); pop(st, C("booked"), { rot: -10 });
  tl.to(rowEls[win], { background: "#e6f7ec", duration: 0.2 }, C("booked"));
  if(d.note){ var note = mk(sc, "div", "note", esc(d.note), "color:" + COL.secondary); at(note, V ? 540 : 1250, V ? 1110 : 1000, -50, 0); enter(note, C("booked") + 0.3, { y: 30 }); }
};

/* cues: inbox, full, review, social, stale */
TYPES.problem_stack = function(sc, s, d, C){
  bg(sc, s.bg);
  floats(sc, s.seed, 12, ["#c4b5fd", "#f9a8d4", "#ffffff"], s.start, s.end);
  var r = bot(sc, s.pose, {}); botIn(r, s);
  title(sc, esc(d.title), s.start + 0.25, { color: d.title_color || "#fff" });
  var p = panel(sc, 900, 640);
  var inbox = box(p, 0, 0, 900, 190, "card", ic("mail", COL.primary) + '<h4 style="position:absolute;left:100px;top:28px">' + esc(d.inbox) + '</h4><div class="sub" style="position:absolute;left:100px;top:84px">' + esc(d.inbox_sub) + '</div><div class="num" style="position:absolute;right:40px;top:30px;font-family:' + FT + ';font-weight:700;font-size:72px">0</div>', "padding:34px 30px;box-sizing:border-box");
  enter(inbox, C("inbox") - 0.15, { x: 300 });
  var num = inbox.querySelector(".num"), o = { n: 0 }, target = d.inbox_count || 64;
  tl.fromTo(o, { n: 0 }, { n: target, duration: 1.0, ease: "power2.in", onUpdate: function(){ num.textContent = Math.round(o.n); } }, C("inbox"));
  var R = rng(31);
  for(var i = 0; i < 9; i++){ var e = mk(p, "div", "abs", ic("mail", "#ffffff")); e.firstChild.style.color = COL.primary;
    gsap.set(e, { x: 120 + R() * 640, y: -260, rotation: (R() - 0.5) * 60, autoAlpha: 0 });
    tl.set(e, { autoAlpha: 1 }, C("inbox") + i * 0.07);
    tl.to(e, { y: 110 + R() * 50, rotation: (R() - 0.5) * 40, duration: 0.5, ease: "bounce.out" }, C("inbox") + i * 0.07); }
  var full = chip(p, esc(d.full), 760, 150, "accent"); pop(full, C("full"));
  var stars = [1, 2, 3, 4, 5].map(function(){ return '<span style="width:34px;height:34px;display:block">' + ICON.star + '</span>'; }).join("");
  var rev = box(p, 0, 230, 430, 230, "card", '<div style="color:#f5b700;width:200px;display:flex;gap:4px">' + stars + '</div><h4 style="margin-top:18px">' + esc(d.review_title) + '</h4><div class="sub" style="margin-top:6px">' + esc(d.review_sub) + '</div>', "padding:30px;box-sizing:border-box");
  enter(rev, C("review"), { y: 120 });
  var soc = box(p, 470, 230, 430, 230, "card", '<div class="sub" style="letter-spacing:.12em">' + esc(d.social_label) + '</div><h4 style="margin-top:8px">' + esc(d.social_title) + '</h4><div style="font-family:' + FT + ';font-weight:700;font-size:40px;line-height:1.1;margin-top:2px">' + esc(d.social_value) + '</div>', "padding:26px 30px;box-sizing:border-box");
  enter(soc, C("social"), { y: 120 });
  tl.to(soc, { filter: "grayscale(1)", opacity: 0.7, duration: 0.5 }, C("stale"));
  var web = sv("svg", { "class": "abs", width: 120, height: 120, viewBox: "0 0 120 120", style: "left:780px;top:240px;overflow:visible" }, p);
  ["M120 0 L10 0", "M120 0 L120 110", "M120 0 L30 90", "M120 0 L75 105", "M120 0 L15 45"].forEach(function(dd){ drawPath(sv("path", { d: dd, stroke: "#9b93a8", "stroke-width": 2, fill: "none" }, web), C("stale"), 0.4); });
  [30, 55, 80].forEach(function(rr){ drawPath(sv("path", { d: "M" + (120 - rr) + " 0 Q " + (120 - rr * 0.8) + " " + rr * 0.6 + " 120 " + rr, stroke: "#9b93a8", "stroke-width": 2, fill: "none" }, web), C("stale") + 0.15, 0.4); });
};

/* cues: tick, word, off (the held beat before the turn) */
TYPES.night_admin = function(sc, s, d, C){
  bg(sc, s.bg);
  var R = rng(41); for(var i = 0; i < 40; i++){ var st = mk(sc, "div", "abs", null, "width:4px;height:4px;border-radius:50%;background:#fff;opacity:" + (0.2 + R() * 0.6)); gsap.set(st, { x: R() * W, y: R() * H * 0.6 }); }
  var moon = mk(sc, "div", "abs", null, "width:120px;height:120px;border-radius:50%;background:#f7e9c6;box-shadow:0 0 60px 10px rgba(247,233,198,.25)"); gsap.set(moon, { x: V ? 820 : 1660, y: V ? 140 : 110 });
  var glow = mk(sc, "div", "abs", null, "width:900px;height:900px;border-radius:50%;background:radial-gradient(closest-side,rgba(255,200,120,.32),transparent)");
  gsap.set(glow, { x: L.bot.cx - 450, y: L.bot.by - 760 });
  var r = bot(sc, s.pose, {}); botIn(r, s);
  var p = panel(sc, 520, 520);
  var face = mk(p, "div", "abs", null, "width:420px;height:420px;left:50px;top:20px;border-radius:50%;background:#fcfbf8;border:14px solid " + COL.primary + ";box-sizing:border-box;box-shadow:0 40px 80px -30px rgba(0,0,0,.6)");
  for(var k = 0; k < 12; k++) mk(face, "div", "abs", null, "width:8px;height:" + (k % 3 ? 18 : 30) + "px;background:#211d2b;border-radius:4px;left:198px;top:12px;transform-origin:4px 184px;transform:rotate(" + k * 30 + "deg)");
  var hh = mk(face, "div", "abs", null, "width:14px;height:110px;background:#211d2b;border-radius:7px;left:189px;top:86px;transform-origin:7px 110px");
  var mh = mk(face, "div", "abs", null, "width:10px;height:160px;background:" + COL.secondary + ";border-radius:5px;left:191px;top:36px;transform-origin:5px 160px");
  enter(face, s.start + 0.25, { y: 80 });
  gsap.set(hh, { rotation: 180 }); gsap.set(mh, { rotation: 0 });
  tl.to(hh, { rotation: 330, duration: s.end - C("tick"), ease: "power1.inOut" }, C("tick"));
  tl.to(mh, { rotation: 360 * 5, duration: s.end - C("tick"), ease: "power1.inOut" }, C("tick"));
  var tag = chip(sc, esc(d.chip), 0, 0, "primary"); at(tag, V ? 540 : 1250, V ? 970 : 960, -50, 0); pop(tag, C("tick"));
  var kw = mk(sc, "div", "title", esc(d.word), "font-size:" + (V ? 150 : 170) + "px;color:#fcfbf8"); at(kw, V ? 540 : 1250, V ? 110 : 60, -50, 0); slam(kw, C("word"));
  var dark = mk(sc, "div", "bg", null, "background:#0b0812"); gsap.set(dark, { autoAlpha: 0 });
  tl.to(dark, { autoAlpha: 0.78, duration: 0.08, ease: "power1.out" }, C("off"));
  tl.to(glow, { autoAlpha: 0, duration: 0.15 }, C("off"));
};

/* cues: logo, tag, jump  (the turn: logo reveal, sunburst, confetti) */
TYPES.reveal = function(sc, s, d, C){
  bg(sc, s.bg);
  var rays = sv("svg", { "class": "abs", width: W, height: H, viewBox: "0 0 " + W + " " + H }, sc);
  var g = sv("g", {}, rays), cx = W / 2, cy = V ? 760 : 470, RR = 2400;
  for(var i = 0; i < 24; i++){ var a0 = i * Math.PI / 12, a1 = a0 + Math.PI / 24;
    sv("polygon", { points: cx + "," + cy + " " + (cx + Math.cos(a0) * RR) + "," + (cy + Math.sin(a0) * RR) + " " + (cx + Math.cos(a1) * RR) + "," + (cy + Math.sin(a1) * RR), fill: i % 2 ? (d.ray_a || "rgba(240,138,36,.10)") : (d.ray_b || "rgba(139,92,246,.10)") }, g); }
  gsap.set(g, { transformOrigin: cx + "px " + cy + "px" });
  tl.fromTo(g, { rotation: 0 }, { rotation: 40, duration: s.end - s.start, ease: "none" }, s.start);
  tl.fromTo(rays, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.5 }, s.start);
  var logo = mk(sc, "div", "abs", '<img src="' + ASSET + P.brand.logo + '" style="width:100%;display:block">', "width:" + (V ? 860 : 900) + "px");
  at(logo, cx, V ? 520 : 220); pop(logo, C("logo"), { from: 0.5, rot: -3 });
  var tag = mk(sc, "div", "title", V ? esc(d.tagline) + "<br>" + (d.tagline_accent ? '<span class="grad">' + esc(d.tagline_accent) + "</span>" : "") : grad(d.tagline, d.tagline_accent), "font-size:" + (V ? 84 : 72) + "px;text-align:center");
  at(tag, cx, V ? 680 : 360, -50, 0); enter(tag, C("tag"), { y: 50 });
  isoFloor(sc, cx, V ? 1680 : 930, 4, 4, V ? 70 : 52, d.floor_a || "#efe7ff", d.floor_b || "#e4d9ff", s.start + 0.2);
  var r = bot(sc, s.pose, { cx: cx, by: V ? 1760 : 1030, h: V ? 580 : 440 });
  enter(r, s.start + 0.2, { y: 400 });
  tl.to(r, { y: "-=110", duration: 0.25, ease: "power2.out" }, C("jump"));
  tl.to(r, { y: "+=110", duration: 0.3, ease: "bounce.out" }, C("jump") + 0.25);
  confetti(sc, cx, V ? 520 : 220, 70, C("logo"), 5);
  var fl = mk(sc, "div", "bg", null, "background:#fff"); gsap.set(fl, { autoAlpha: 0 });
  tl.fromTo(fl, { autoAlpha: 1 }, { autoAlpha: 0, duration: 0.6, ease: "power2.out" }, s.start);
};

/* cues: busy, closed, answer, qual, transcript, next */
TYPES.call_answered = function(sc, s, d, C){
  featureBase(sc, s, d);
  var p = panel(sc, 900, 640);
  var call = box(p, 0, 0, 900, 150, "card", '<span style="position:absolute;left:30px;top:52px">' + ic("phone", COL.primary2) + '</span><div style="position:absolute;left:100px;top:36px"><h4>' + esc(d.incoming) + '</h4><div class="sub">' + esc(d.caller) + '</div></div>');
  enter(call, s.start + 0.3, { y: -80 });
  var busy = chip(p, esc(d.busy), 560, 48, "light"); pop(busy, C("busy"));
  var closed = chip(p, esc(d.closed), 400, 48, ""); pop(closed, C("closed"), { rot: 8 });
  var ok = box(p, 0, 0, 900, 150, "card", '<span style="position:absolute;left:30px;top:52px">' + ic("check", COL.good) + '</span><div style="position:absolute;left:100px;top:36px"><h4 style="color:#15803d">' + esc(d.answered) + '</h4><div class="sub">' + esc(d.answered_sub) + '</div></div>', "background:#effaf3");
  gsap.set(ok, { autoAlpha: 0 }); tl.fromTo(ok, { autoAlpha: 0, rotationX: -90 }, { autoAlpha: 1, rotationX: 0, duration: 0.35, ease: "back.out(2)" }, C("answer"));
  tl.to([busy, closed], { autoAlpha: 0, duration: 0.15 }, C("answer"));
  var q = box(p, 0, 180, 420, 330, "card", '<h4 style="margin:26px 26px 6px">' + esc(d.details_title) + '</h4>');
  d.details.forEach(function(f, k){
    var rr = mk(q, "div", "abs", '<span style="color:var(--ink2);font-weight:700">' + esc(f[0]) + '</span><b style="margin-left:12px">' + esc(f[1]) + '</b>', "left:26px;top:" + (98 + k * 56) + "px;font-size:25px;white-space:nowrap");
    var tick = mk(q, "div", "abs", ic("check", COL.good), "left:350px;top:" + (84 + k * 56) + "px;transform:scale(.8)");
    gsap.set(rr, { autoAlpha: 0.25 }); tl.to(rr, { autoAlpha: 1, duration: 0.2 }, C("qual") + k * 0.14); pop(tick, C("qual") + k * 0.14); });
  enter(q, C("answer") + 0.15, { y: 100 });
  var tr = box(p, 450, 180, 450, 330, "card", '<h4 style="margin:26px 26px 6px">' + esc(d.transcript_title) + '</h4><div class="tx" style="position:absolute;left:26px;right:26px;top:90px;font-size:23px;font-weight:700;line-height:1.4;color:#3c3647;white-space:pre-wrap"></div>');
  enter(tr, C("transcript") - 0.25, { y: 100 });
  typeText(tr.querySelector(".tx"), d.transcript, C("transcript"), d.type_seconds || 1.25);
  var nx = chip(p, esc(d.next), 450, 540, "accent"); pop(nx, C("next"));
};

/* cues: sort, priority, drafts, ok */
TYPES.inbox_sort = function(sc, s, d, C){
  featureBase(sc, s, d);
  var p = panel(sc, 900, 600);
  var card = box(p, 0, 0, 900, 600, "card", '<h4 style="margin:26px 30px">' + esc(d.card_title) + '</h4>');
  enter(card, s.start + 0.3, { y: 120 });
  d.items.forEach(function(it, k){
    var rw = mk(card, "div", "row", ic("mail", COL.primary2) + '<div>' + esc(it[0]) + '<small>' + esc(it[1]) + '</small></div><span class="tag" style="background:' + it[3] + ';color:' + it[4] + '">' + esc(it[2]) + '</span>', "top:" + (86 + k * 100) + "px");
    pop(rw.querySelector(".tag"), C("priority") + d.order.indexOf(k) * 0.08);
    tl.to(rw, { top: 86 + d.order.indexOf(k) * 100, duration: 0.5, ease: "expo.inOut" }, C("sort") - 0.1); });
  d.drafts.forEach(function(k, j){ var c = chip(card, esc(d.draft_label), 560, 0, "good"); gsap.set(c, { y: 86 + d.order.indexOf(k) * 100 + 18, scale: 0.8 }); c.style.fontSize = "20px"; c.style.padding = "10px 16px"; pop(c, C("drafts") + j * 0.2); });
};

/* cues: one per card (card.cue), rank, first.  cards[0] is the one ranked first; cards arrive in reverse. */
TYPES.rank_list = function(sc, s, d, C){
  featureBase(sc, s, d);
  var p = panel(sc, 860, 560), slot = [40, 220, 400], n = d.cards.length;
  var cards = d.cards.map(function(cd, k){
    var c = box(p, 0, 0, 860, 150, "card", '<span class="rk" style="position:absolute;left:26px;top:37px;width:76px;height:76px;border-radius:22px;background:#b8b1c6;color:#fff;display:grid;place-items:center;font-family:' + FT + ';font-weight:700;font-size:40px">#</span>' +
      '<div style="position:absolute;left:126px;top:36px"><h4 style="font-size:34px">' + esc(cd.title) + '</h4><div class="sub" style="font-size:22px;margin-top:4px">' + esc(cd.sub) + '</div></div><span style="position:absolute;right:30px;top:46px">' + ic(cd.icon, cd.color || COL.primary2) + '</span>');
    gsap.set(c, { y: slot[n - 1 - k] });
    enter(c, C(cd.cue) - 0.1, { x: 500 }); return c; });
  cards.forEach(function(c, k){ tl.to(c, { y: slot[k], scale: k ? 1 : 1.03, duration: 0.5, ease: "expo.inOut" }, C("rank") - 0.1); tl.set(c.querySelector(".rk"), { textContent: String(k + 1) }, C("rank") + 0.25); });
  tl.to(cards[0].querySelector(".rk"), { background: COL.accent, duration: 0.2 }, C("rank") + 0.25);
  tl.to(cards[0], { borderColor: COL.accent, duration: 0.2 }, C("rank") + 0.25);
  var take = chip(p, esc(d.take), 660, 0, "good"); gsap.set(take, { y: slot[0] - 28 }); pop(take, C("first"), { rot: -8 });
};

/* cues: done, sms, stars, happy, good, unhappy, bad */
TYPES.review_split = function(sc, s, d, C){
  featureBase(sc, s, d);
  var p = panel(sc, 900, 620);
  var done = chip(p, ic("check", COL.good, 34) + esc(d.done), 0, 0, "light"); pop(done, C("done"));
  var sms = box(p, 0, 90, 400, 250, "card", '<div class="sub">' + esc(d.sms_label) + '</div><div style="margin-top:12px;font-weight:800;font-size:25px;line-height:1.35">' + esc(d.sms) + '</div><div class="stars" style="display:flex;gap:8px;margin-top:18px"></div>', "padding:28px;box-sizing:border-box;background:#f3efff");
  enter(sms, C("sms") - 0.1, { y: 100 });
  var stars = sms.querySelector(".stars");
  for(var i = 0; i < 5; i++){ var st = mk(stars, "span", null, ICON.star, "width:40px;height:40px;display:block;color:#d6d0e0"); tl.to(st, { color: "#f5b700", duration: 0.1 }, C("stars") + i * 0.1); pop(st, C("stars") + i * 0.1, { from: 0.6 }); }
  var arrows = sv("svg", { "class": "abs", width: 900, height: 620, viewBox: "0 0 900 620", style: "overflow:visible" }, p);
  drawPath(sv("path", { d: "M405 190 C 470 190, 470 110, 520 110", stroke: COL.good, "stroke-width": 6, fill: "none", "stroke-linecap": "round" }, arrows), C("happy"), 0.35);
  drawPath(sv("path", { d: "M405 260 C 470 260, 470 420, 520 420", stroke: COL.secondary, "stroke-width": 6, fill: "none", "stroke-linecap": "round" }, arrows), C("unhappy"), 0.35);
  function starRow(n){ return '<div style="display:flex;gap:4px">' + [1, 2, 3, 4, 5].map(function(k){ return '<span style="width:30px;height:30px;display:block;color:' + (k <= n ? "#f5b700" : "#d6d0e0") + '">' + ICON.star + '</span>'; }).join("") + '</div>'; }
  var g = box(p, 530, 10, 370, 205, "card", starRow(5) + '<h4 style="margin-top:12px">' + esc(d.good_title) + '</h4><div class="sub">' + esc(d.good_sub) + '</div>', "padding:26px;box-sizing:border-box;border-color:rgba(22,163,74,.5)");
  enter(g, C("good") - 0.15, { x: 200 });
  var u = box(p, 530, 330, 370, 205, "card", starRow(2) + '<h4 style="margin-top:12px">' + esc(d.bad_title) + '</h4><div class="sub">' + esc(d.bad_sub) + '</div>', "padding:26px;box-sizing:border-box;border-color:rgba(217,38,119,.4)");
  enter(u, C("bad") - 0.2, { x: 200 });
};

/* cues: site, chat, reply, book, clock */
TYPES.chat_booking = function(sc, s, d, C){
  featureBase(sc, s, d);
  var p = panel(sc, 900, 600);
  var win = box(p, 0, 0, 900, 600, "card", '<div style="height:56px;background:#f1eef6;display:flex;align-items:center;gap:10px;padding:0 22px"><span class="dot" style="background:#ff6058"></span><span class="dot" style="background:#ffbd2e"></span><span class="dot" style="background:#28c840"></span><span style="margin-left:18px;padding:8px 22px;border-radius:18px;background:#fff;font-weight:800;font-size:19px;color:var(--ink2)">' + esc(d.site) + '</span></div>' +
    '<div style="position:absolute;left:34px;top:96px;width:380px;height:40px;border-radius:12px;background:#e9e5f2"></div><div style="position:absolute;left:34px;top:156px;width:300px;height:22px;border-radius:11px;background:#efecf5"></div><div style="position:absolute;left:34px;top:192px;width:340px;height:22px;border-radius:11px;background:#efecf5"></div><div style="position:absolute;left:34px;top:250px;width:380px;height:300px;border-radius:20px;background:#ece6ff"></div>');
  enter(win, C("site") - 0.1, { y: 140 });
  var cw = box(win, 450, 80, 420, 490, "card", '<div style="height:64px;background:' + COL.primary + ';color:#fff;display:flex;align-items:center;padding:0 22px;font-weight:800;font-size:22px">' + esc(d.header) + '</div>', "box-shadow:0 30px 60px -30px rgba(33,29,43,.5)");
  var b1 = mk(cw, "div", "abs", esc(d.question), "left:20px;top:86px;width:300px;padding:16px 18px;border-radius:20px 20px 20px 6px;background:#f1eef6;font-weight:800;font-size:20px;line-height:1.35");
  var b2 = mk(cw, "div", "abs", esc(d.answer), "left:96px;top:196px;width:300px;padding:16px 18px;border-radius:20px 20px 6px 20px;background:" + COL.primary + ";color:#fff;font-weight:800;font-size:20px;line-height:1.35");
  pop(b1, C("chat"), { from: 0.6, rot: 0 }); pop(b2, C("reply"), { from: 0.6, rot: 0 });
  var bk = mk(cw, "div", "abs", ic("cal", COL.good) + '<div><b style="font-size:22px">' + esc(d.booked) + '</b><div style="font-weight:700;color:var(--ink2);font-size:18px">' + esc(d.booked_sub) + '</div></div>', "left:20px;top:340px;width:380px;padding:16px;border-radius:20px;background:#effaf3;border:2px solid rgba(22,163,74,.4);display:flex;gap:14px;align-items:center;box-sizing:border-box");
  pop(bk, C("book"), { rot: 0 });
  var clk = chip(p, '<span style="font-size:30px">&#9728;</span> ' + esc(d.clock) + ' <span style="font-size:28px">&#9790;</span>', 300, 548, "primary"); pop(clk, C("clock"));
};

/* cues: reels, carousel, a, b */
TYPES.content_reels = function(sc, s, d, C){
  featureBase(sc, s, d);
  var p = panel(sc, 900, 640);
  d.images.slice(0, 3).forEach(function(im, k){
    var r = box(p, k * 175, 40 + (k === 1 ? -20 : 20), 240, 426, "card", '<img src="' + ASSET + im + '" style="width:100%;height:100%;object-fit:cover;display:block"><span style="position:absolute;left:12px;top:14px;padding:6px 12px;border-radius:999px;background:rgba(27,21,38,.8);color:#fff;font-weight:800;font-size:15px">' + esc(d.reel_label) + '</span><span style="position:absolute;left:50%;top:50%;width:70px;height:70px;margin:-35px;border-radius:50%;background:rgba(255,255,255,.85);display:grid;place-items:center;color:' + COL.primary + '"><span style="width:30px;height:30px;display:block">' + ICON.play + '</span></span>', "border:8px solid #1b1526");
    gsap.set(r, { rotation: (k - 1) * 7 });
    enter(r, C("reels") + k * 0.12, { y: 300 }); });
  var car = box(p, 640, 120, 260, 260, "card", '<div class="slides" style="position:absolute;inset:0"></div><div style="position:absolute;bottom:14px;left:0;right:0;display:flex;gap:8px;justify-content:center"><span class="dot" style="background:' + COL.primary + '"></span><span class="dot" style="background:#d6d0e0"></span><span class="dot" style="background:#d6d0e0"></span></div>');
  var slides = car.querySelector(".slides");
  d.slides.forEach(function(lbl, k){ var sl = mk(slides, "div", "abs", '<div style="position:absolute;inset:0;background:' + ["#ede9fe", "#fde68a", "#bbf7d0"][k % 3] + '"></div><b style="position:absolute;left:22px;top:20px;font-family:' + FT + ';font-size:34px">' + esc(lbl) + '</b>', "width:260px;height:260px"); gsap.set(sl, { x: k * 260 }); });
  enter(car, C("carousel") - 0.1, { x: 260 });
  for(var k = 1; k < d.slides.length; k++) tl.to(slides, { x: -260 * k, duration: 0.4, ease: "expo.inOut" }, C("carousel") + 0.5 + (k - 1) * 0.6);
  var c1 = chip(p, ic("person", COL.primary, 34) + esc(d.chip_a), 20, 540, "light"); pop(c1, C("a"));
  var c2 = chip(p, esc(d.chip_b), 330, 540, "primary"); pop(c2, C("b"));
};

/* cues: hub, one per tile (tile.cue), ok */
TYPES.integrations_hub = function(sc, s, d, C){
  featureBase(sc, s, d);
  var p = panel(sc, 900, 620), cx = 450, cy = 310;
  var lines = sv("svg", { "class": "abs", width: 900, height: 620, viewBox: "0 0 900 620", style: "overflow:visible" }, p);
  var hub = mk(p, "div", "abs", '<img src="' + ASSET + P.brand.mark + '" style="width:120px;display:block">', "width:200px;height:200px;border-radius:50%;background:#fff;display:grid;place-items:center;box-shadow:0 30px 60px -24px rgba(109,40,217,.6);border:6px solid #ece6ff");
  at(hub, cx, cy); pop(hub, C("hub"));
  var spots = [[140, 110], [760, 110], [140, 510], [760, 510]];
  d.tiles.slice(0, 4).forEach(function(tt, k){
    var x = spots[k][0], y = spots[k][1];
    var dd = "M" + x + " " + y + " C " + (x + cx) / 2 + " " + y + ", " + (x + cx) / 2 + " " + cy + ", " + cx + " " + cy;
    var dash = sv("path", { d: dd, stroke: COL.primary2, "stroke-width": 6, fill: "none", "stroke-linecap": "round", "stroke-dasharray": "2 14" }, lines);
    var solid = sv("path", { d: dd, stroke: COL.good, "stroke-width": 6, fill: "none", "stroke-linecap": "round" }, lines);
    gsap.set(dash, { autoAlpha: 0 }); tl.to(dash, { autoAlpha: 1, duration: 0.3 }, C("hub"));
    drawPath(solid, C(tt.cue) - 0.15, 0.3);
    var el = mk(p, "div", "chip light", ic("check", "#d6d0e0") + esc(tt.label), "font-size:28px;padding:16px 26px");
    at(el, x, y); enter(el, C(tt.cue) - 0.3, { x: x < cx ? -200 : 200 });
    tl.to(el.querySelector(".ic"), { background: COL.good, duration: 0.15 }, C(tt.cue)); });
  tl.to(hub, { borderColor: COL.good, boxShadow: "0 0 0 18px rgba(22,163,74,.18), 0 30px 60px -24px rgba(22,163,74,.6)", duration: 0.3 }, C("ok"));
  var ok = chip(p, esc(d.ok), 0, 0, "good"); at(ok, cx, cy + 150); pop(ok, C("ok"));
};

/* cues: phone, tap, approve, lock */
TYPES.phone_approve = function(sc, s, d, C){
  featureBase(sc, s, d);
  var p = panel(sc, 900, 660);
  var ph = box(p, 230, 0, 440, 660, "card", '<div style="position:absolute;left:50%;top:14px;width:110px;height:26px;margin-left:-55px;border-radius:13px;background:#1b1526"></div><h4 style="position:absolute;left:28px;top:64px;font-size:34px">' + esc(d.screen_title) + '</h4><div class="sub" style="position:absolute;left:28px;top:116px">' + esc(d.screen_sub) + '</div>', "border:12px solid #1b1526;border-radius:56px;background:#fcfbf8");
  enter(ph, C("phone") - 0.1, { y: 200 });
  d.items.slice(0, 3).forEach(function(it, k){
    var rw = mk(ph, "div", "abs", '<b style="font-size:22px">' + esc(it[0]) + '</b><div style="font-weight:700;color:var(--ink2);font-size:17px">' + esc(it[1]) + '</div><span class="ap" style="position:absolute;right:14px;top:22px;padding:10px 16px;border-radius:999px;background:' + COL.primary + ';color:#fff;font-weight:800;font-size:17px">' + esc(d.approve) + '</span>', "left:18px;right:18px;top:" + (172 + k * 118) + "px;height:100px;padding:18px;border-radius:20px;background:#fff;border:2px solid rgba(33,29,43,.08);box-sizing:border-box");
    tl.to(rw.querySelector(".ap"), { background: COL.good, duration: 0.15 }, C("approve") + k * 0.12);
    tl.set(rw.querySelector(".ap"), { textContent: d.approved }, C("approve") + k * 0.12); });
  var finger = mk(ph, "div", "abs", null, "width:70px;height:70px;border-radius:50%;background:rgba(240,138,36,.45);border:4px solid " + COL.accent);
  gsap.set(finger, { x: 300, y: 560, autoAlpha: 0 });
  tl.set(finger, { autoAlpha: 1 }, C("tap") - 0.4);
  tl.to(finger, { x: 300, y: 180, duration: 0.35, ease: "power2.inOut" }, C("tap") - 0.4);
  tl.to(finger, { scale: 0.7, duration: 0.08, yoyo: true, repeat: 1 }, C("tap"));
  tl.to(finger, { autoAlpha: 0, duration: 0.2 }, C("approve") + 0.4);
  var lock = chip(p, ic("lock", COL.accent, 36) + esc(d.lock), 0, 0, ""); at(lock, 450, 585); pop(lock, C("lock"));
};

/* cues: l1, l2, l3 (one per line) */
TYPES.recap = function(sc, s, d, C){
  bg(sc, s.bg);
  floats(sc, s.seed, 14, ["#c4b5fd", "#f9a8d4", "#fdba74"], s.start, s.end);
  var r = bot(sc, s.pose, V ? { cx: 540, by: 1800, h: 520 } : { cx: 1650, by: 1040, h: 480 }); botIn(r, s, { y: 300 });
  d.lines.forEach(function(l, k){
    var last = k === d.lines.length - 1;
    var el = mk(sc, "div", "title", last ? '<span style="background:' + (d.last_gradient || "linear-gradient(100deg,#fdba74,#f9a8d4)") + ';-webkit-background-clip:text;background-clip:text;color:transparent">' + esc(l) + '</span>' : esc(l), "font-size:" + (V ? 108 : 130) + "px;color:#fcfbf8");
    at(el, V ? 540 : 860, (V ? 430 : 210) + k * (V ? 190 : 230), -50, 0); slam(el, C("l" + (k + 1)), 1.8); });
};

/* cues: logo, button, url, chord */
TYPES.end_card = function(sc, s, d, C){
  bg(sc, s.bg);
  floats(sc, s.seed, 14, [COL.primary2, COL.accent, COL.secondary], s.start, s.end);
  var cx = V ? 540 : 860;
  var logo = mk(sc, "div", "abs", '<img src="' + ASSET + P.brand.logo + '" style="width:100%;display:block">', "width:860px");
  at(logo, cx, V ? 420 : 250); pop(logo, C("logo"), { from: 0.6, rot: -2 });
  var tag = mk(sc, "div", "title", esc(d.tagline).replace(" | ", V ? "<br>" : " "), "font-size:" + (V ? 66 : 58) + "px;text-align:center;color:var(--ink2)");
  at(tag, cx, V ? 580 : 400, -50, 0); enter(tag, C("logo") + 0.25, { y: 40 });
  var btn = mk(sc, "div", "abs", esc(d.button), "padding:30px 70px;border-radius:999px;background:" + COL.primary + ";color:#fff;font-family:" + FT + ";font-weight:700;font-size:" + (V ? 70 : 64) + "px;box-shadow:0 12px 0 rgba(0,0,0,.25),0 40px 60px -24px rgba(109,40,217,.7);white-space:nowrap");
  at(btn, cx, V ? 860 : 600); pop(btn, C("button"));
  var url = mk(sc, "div", "title", "", "font-size:" + (V ? 84 : 76) + "px");
  at(url, cx, V ? 1010 : 720, -50, 0); typeText(url, d.url, C("url"), 0.5);
  if(d.note){ var note = mk(sc, "div", "note", esc(d.note), "color:" + COL.secondary + ";font-size:" + (V ? 56 : 52) + "px"); at(note, cx, V ? 1150 : 860, -50, 0); enter(note, C("chord") - 0.6, { y: 30 }); }
  var r = bot(sc, s.pose, V ? { cx: 540, by: 1800, h: 560 } : { cx: 1640, by: 1040, h: 620 }); botIn(r, s, V ? { y: 300 } : { x: 400 });
  confetti(sc, cx, V ? 420 : 250, 60, C("logo"), 9);
  tl.to(btn, { scale: 1.05, duration: 0.3, yoyo: true, repeat: 1, ease: "sine.inOut" }, C("chord"));
};

/* ============================ BUILD ============================ */
var defs = {}; P.scenes.forEach(function(s){ defs[s.id] = s; });
B.scenes.forEach(function(s, k){
  var def = defs[s.id], sc = $(s.id);
  if(!def || !sc) throw new Error("scene " + s.id + " missing from project or page");
  if(!TYPES[def.type]) throw new Error("unknown scene type " + def.type + " in " + s.id);
  var S = { id: s.id, start: s.start, end: s.end, pose: def.pose, bg: def.bg, seed: 11 + k * 10 };
  var C = function(name){ var id = s.id + "." + name; if(!(id in CUE)) throw new Error("missing cue " + id + " (type " + def.type + ")"); return CUE[id]; };
  TYPES[def.type](sc, S, def.data || {}, C);
  if(k > 0 && def.wipe !== false) wipe(s.start, (P.solids && P.solids[def.bg]) || "#ffffff", k % 2 ? COL.accent : COL.primary);
});

/* vertical captions, two words at a time; scenes with "captions": false are skipped */
if(V && L.cap){
  var skip = {}; P.scenes.forEach(function(s){ if(s.captions === false) skip[s.id] = 1; });
  var caps = $("caps"), words = B.words.filter(function(w){ return !skip[w.scene]; }), groups = [];
  for(var i = 0; i < words.length; ){ var g = [words[i]];
    if(i + 1 < words.length && words[i + 1].scene === words[i].scene && !/[.,]$/.test(words[i].w)) g.push(words[i + 1]);
    groups.push(g); i += g.length; }
  groups.forEach(function(g, k){
    var nxt = groups[k + 1], t0 = g[0].s, t1 = nxt && nxt[0].scene === g[0].scene ? nxt[0].s : g[g.length - 1].e + 0.15;
    var el = mk(caps, "div", "cap", esc(g.map(function(w){ return w.w.replace(/,$/, ""); }).join(" ")));
    at(el, L.cap.cx, L.cap.cy); gsap.set(el, { autoAlpha: 0 });
    tl.fromTo(el, { autoAlpha: 1, scale: 0.85 }, { scale: 1, duration: 0.12, ease: "back.out(2)" }, t0);
    tl.set(el, { autoAlpha: 0 }, t1); });
}

tl.set({}, {}, B.duration);
window.__timelines = window.__timelines || {};
window.__timelines["main"] = tl;
})();
