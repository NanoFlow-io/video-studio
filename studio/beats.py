"""Single source of timing. Every cue in project.json is anchored to a word of its scene's line
(or to the scene start / line end), so one cue list resolves onto both cut clocks.
Writes build/beats-<cut>.json, build/beats-<cut>.js (window.BEATS) and build/sound-sheet-<cut>.md."""
import json, re
from pathlib import Path

# cue names each scene type reads (the engine throws on a missing one; checked here first)
REQUIRED = {
    "incoming_call": ["tiles", "ring"], "missed_to_competitor": ["missed", "list", "next", "booked"],
    "problem_stack": ["inbox", "full", "review", "social", "stale"], "night_admin": ["tick", "word", "off"],
    "reveal": ["logo", "tag", "jump"], "call_answered": ["busy", "closed", "answer", "qual", "transcript", "next"],
    "inbox_sort": ["sort", "priority", "drafts"], "rank_list": ["rank", "first"], "review_split": ["done", "sms", "stars", "happy", "good", "unhappy", "bad"],
    "chat_booking": ["site", "chat", "reply", "book", "clock"], "content_reels": ["reels", "carousel", "a", "b"],
    "integrations_hub": ["hub", "ok"], "phone_approve": ["phone", "tap", "approve", "lock"], "recap": [], "end_card": ["logo", "button", "url", "chord"],
    # entertainment style (Brand Kit reel). hook also needs `turn` when it has a `proof`; `zoom` and `handoff` are optional
    "hook": [], "broll": [],
    # field-notes explainer (engine/fieldnotes.js, experimental): cues are whatever its actions name, checked below
    "fieldnotes": [],
}
HEADLINE_ACCENTS = ("pink",)


def required(s):
    """Cue names a scene needs. A clean end card (data.clean: true) shows only the logo and the tagline, so it needs
    only `logo`; cues it does not use are allowed."""
    if s["type"] == "end_card" and (s.get("data") or {}).get("clean") is True:
        return ["logo"]
    return REQUIRED.get(s["type"], [])


def headline_problems(sid, h, layout):
    """Checks for a hook's data.headline (comic headline, footage layout)."""
    if not isinstance(h, dict):
        return [f"{sid} (hook): data.headline must be an object with at least text, not {h!r}"]
    out, num = [], lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if not isinstance(h.get("text"), str) or not h["text"].strip():
        out.append(f"{sid} (hook): data.headline.text is required (a short line)")
    elif len(h["text"].split()) > 6:
        out.append(f"{sid} (hook): data.headline.text has more than 6 words: {h['text']!r}")
    pos = h.get("pos")
    if pos is not None and not (isinstance(pos, list) and len(pos) == 2 and all(num(v) and 0 <= v <= 1 for v in pos)):
        out.append(f"{sid} (hook): data.headline.pos must be [x, y] with both between 0 and 1, not {pos!r}")
    if h.get("width") is not None and not (num(h["width"]) and 0.2 <= h["width"] <= 1):
        out.append(f"{sid} (hook): data.headline.width must be a fraction of the frame width from 0.2 to 1, not {h['width']!r}")
    if h.get("size") is not None and not (num(h["size"]) and 40 <= h["size"] <= 300):
        out.append(f"{sid} (hook): data.headline.size must be a font size from 40 to 300 px, not {h['size']!r}")
    if h.get("accent") is not None and h["accent"] not in HEADLINE_ACCENTS:
        out.append(f"{sid} (hook): data.headline.accent must be one of {', '.join(HEADLINE_ACCENTS)}, not {h['accent']!r}")
    if layout != "footage":
        out.append(f"{sid} (hook): data.headline only shows in the footage layout (set \"layout\": \"footage\" in project.json)")
    return out


# field-notes scene data (engine/fieldnotes.js). Kinds and the actions each accepts; "draw", "show" and "hide" work on any
# object, and timeline parts ("timeline.peak") take show / hide / seg; the playhead also takes playhead.
FN_KINDS = {"house": {"fill"}, "ac_unit": {"run"}, "timeline": {"seg", "playhead"}, "gauge": {"set"},
            "thermostat": {"turn"}, "arrow": {"flow"}, "callout": set(), "note": set(), "card": set(), "flow": {"pulse"},
            # illustration primitives (2026-10-12)
            "person": {"state"}, "chair": {"state"}, "calendar": {"state", "remind"}, "phone": {"message", "bury"},
            "envelope": {"state"}, "building": set(), "link": {"mark", "pulse"}}
# kinds with named parts ("timeline.peak", "flow.l2") and the actions a part takes
FN_PART_VERBS = {"timeline": {"show", "hide", "seg", "playhead"}, "flow": {"show", "hide", "highlight", "mark"}}
FN_LOCAL = {"callout", "note", "card"}
FN_EMPHASIS = {None, "ochre", "blue", "sage", "italic"}
FN_TIME_RE = re.compile(r"^([A-Za-z0-9_]+)([+-]\d+(?:\.\d+)?)?$")


def fieldnotes_problems(sid, d, cue_names, carried):
    """Checks for one fieldnotes scene. `carried` maps object id -> kind for objects that continue from earlier
    fieldnotes scenes; it is updated with this scene's objects that carry on."""
    out, num = [], lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    pre = f"{sid} (fieldnotes)"
    hd = d.get("headline") or {}
    lines = hd.get("lines")
    if not isinstance(lines, list) or not lines or not all(isinstance(x, dict) and str(x.get("text", "")).strip() for x in lines):
        out.append(f"{pre}: data.headline.lines must be a list of {{text, em?, at?}} with text")
    else:
        if len(lines) > 3:
            out.append(f"{pre}: data.headline has more than 3 lines")
        for x in lines:
            if x.get("em") not in FN_EMPHASIS:
                out.append(f"{pre}: headline emphasis must be one of ochre, blue, sage, italic, not {x.get('em')!r}")

    def time_ok(v, where):
        if v is None or (num(v) and v >= 0):
            return
        m = FN_TIME_RE.match(str(v).strip()) if isinstance(v, str) else None
        if not m:
            out.append(f"{pre}: {where}: time must be seconds after the scene start or a cue name with an optional +/- offset, not {v!r}")
        elif m.group(1) not in ("start", "end") and m.group(1) not in cue_names:
            out.append(f"{pre}: {where}: '{m.group(1)}' is not one of this scene's cues ({', '.join(sorted(cue_names)) or 'none'})")
    time_ok(hd.get("at"), "headline.at")
    for x in lines if isinstance(lines, list) else []:
        if isinstance(x, dict):
            time_ok(x.get("at"), f"headline line {x.get('text')!r}")
    kinds = {} if d.get("continue") is False else dict(carried)
    parts = {}
    for i, o in enumerate(d.get("objects") or []):
        if not isinstance(o, dict) or not str(o.get("id", "")).strip():
            out.append(f"{pre}: objects[{i}] needs an id"); continue
        kind = o.get("kind") or kinds.get(o["id"])
        if kind not in FN_KINDS:
            out.append(f"{pre}: object {o['id']}: kind must be one of {', '.join(sorted(FN_KINDS))}, not {o.get('kind')!r}"); continue
        kinds[o["id"]] = kind
        if kind == "timeline":
            parts.setdefault(o["id"], {"playhead"}).update(x.get("id") for x in (o.get("bands") or []) + (o.get("segs") or []) if isinstance(x, dict))
        if kind == "flow":
            ns = [x.get("id") for x in (o.get("nodes") or []) if isinstance(x, dict)]
            parts.setdefault(o["id"], set()).update(ns + [f"l{i}" for i in range(1, len(ns))])
    for i, a in enumerate(d.get("actions") or []):
        if not isinstance(a, dict):
            out.append(f"{pre}: actions[{i}] must be an object"); continue
        verb, target = a.get("do"), str(a.get("target", ""))
        oid, _, part = target.partition(".")
        where = f"action {i + 1} ({verb} {target})"
        time_ok(a.get("at"), where)
        if oid not in kinds:
            out.append(f"{pre}: {where}: no object '{oid}' in this scene or carried from the previous one"); continue
        kind = kinds[oid]
        if part:
            if kind not in FN_PART_VERBS:
                out.append(f"{pre}: {where}: only a timeline or a flow has parts")
            elif verb not in FN_PART_VERBS[kind]:
                out.append(f"{pre}: {where}: a {kind} part takes {', '.join(sorted(FN_PART_VERBS[kind]))}")
            elif part not in parts.get(oid, {"playhead"} if kind == "timeline" else set()) and oid not in carried:
                out.append(f"{pre}: {where}: the {kind} has no part '{part}'")
        elif verb not in {"draw", "show", "hide"} | FN_KINDS[kind]:
            out.append(f"{pre}: {where}: a {kind} takes {', '.join(sorted({'draw', 'show', 'hide'} | FN_KINDS[kind]))}")
    if d.get("transition") not in (None, "bands"):
        out.append(f"{pre}: data.transition must be 'bands' or absent, not {d.get('transition')!r}")
    carried.clear()
    carried.update({k: v for k, v in kinds.items() if v not in FN_LOCAL})
    return out


ANCHOR_RE = re.compile(r"^(start|end|cut)([+-]\d+(?:\.\d+)?)?$")
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".mp4"}
VERTICAL_ONLY = {"hook", "broll"}
MEDIA_DIRS = {"media", "images", "brand"}


def validate(p):
    """Checks on scene data that need no voice timings, so they run before anything is bought."""
    problems, fn_carried = [], {}
    for s in p.data["scenes"]:
        t, d, sid = s["type"], s.get("data", {}) or {}, s["id"]
        if t not in REQUIRED:
            problems.append(f"{sid}: unknown scene type '{t}'"); continue
        if t == "fieldnotes":
            problems += fieldnotes_problems(sid, d, {c.get("name") for c in s.get("cues", [])}, fn_carried)
        if t in VERTICAL_ONLY and s["line"].get("vertical", True) is False:
            problems.append(f"{sid} ({t}): this type is vertical only, so line.vertical cannot be false")
        names = {c["name"] for c in s.get("cues", [])}
        for c in s.get("cues", []):
            problems += [f"{sid}.{c.get('name')}: {m}" for m in cue_problems(c)]
        for key in ("media", "proof"):
            if t in VERTICAL_ONLY and d.get(key) is not None:
                f = p.dir / d[key]
                if str(d[key]).replace("\\", "/").split("/")[0] not in MEDIA_DIRS:
                    problems.append(f"{sid} ({t}): data.{key} must sit in one of {', '.join(sorted(MEDIA_DIRS))}/ (those are copied into the page): {d[key]}")
                elif not f.is_file():
                    problems.append(f"{sid} ({t}): data.{key} file not found: {d[key]} (paths are relative to {p.dir})")
                elif f.suffix.lower() not in MEDIA_EXT or (key == "proof" and f.suffix.lower() == ".mp4"):
                    problems.append(f"{sid} ({t}): data.{key} must be {'an image' if key == 'proof' else 'an image or an .mp4'}: {d[key]}")
        if t in VERTICAL_ONLY and d.get("media_in") is not None:   # playback offset into an .mp4 source (seconds)
            mi = d["media_in"]
            if not isinstance(mi, (int, float)) or isinstance(mi, bool) or mi < 0:
                problems.append(f"{sid} ({t}): data.media_in must be a number of seconds, 0 or more, not {mi!r}")
            elif not str(d.get("media") or "").lower().endswith(".mp4"):
                problems.append(f"{sid} ({t}): data.media_in only applies when data.media is an .mp4")
        if t in VERTICAL_ONLY and d.get("replay") is not None and not isinstance(d["replay"], bool):
            problems.append(f"{sid} ({t}): data.replay must be true or false, not {d['replay']!r}")
        if t in VERTICAL_ONLY and d.get("side") not in (None, "left", "right"):
            problems.append(f"{sid} ({t}): data.side must be 'left' or 'right', not {d.get('side')!r}")
        if t == "broll":
            if not d.get("media"):
                problems.append(f"{sid} (broll): data.media is required (an image or .mp4 in the project)")
            if not str(d.get("caption", "")).strip():
                problems.append(f"{sid} (broll): data.caption is required (one short line)")
            f = d.get("focus")
            if f is not None and not (isinstance(f, list) and len(f) == 2 and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in f)):
                problems.append(f"{sid} (broll): data.focus must be [x, y] with both between 0 and 1, not {f!r}")
        if d.get("headline") is not None and t not in ("hook", "fieldnotes"):   # fieldnotes checks its own headline
            problems.append(f"{sid} ({t}): data.headline only applies to a hook scene")
        if d.get("clean") is not None and (t != "end_card" or not isinstance(d["clean"], bool)):
            problems.append(f"{sid} ({t}): data.clean must be true or false, on an end_card scene only, not {d['clean']!r}")
        if t == "hook":
            if d.get("proof") and "turn" not in names:
                problems.append(f"{sid} (hook) needs a cue named 'turn' (when data.proof slams in)")
            if d.get("headline") is not None:   # the headline replaces the pill, so the pill is optional
                problems += headline_problems(sid, d["headline"], p.data.get("layout"))
            elif not str(d.get("pill", "")).strip():
                problems.append(f"{sid} (hook): data.pill is required")
            elif len(d["pill"].split()) > 6:
                problems.append(f"{sid} (hook): data.pill has more than 6 words: {d['pill']!r}")
            if str(d.get("caption") or "").strip():   # the narration subtitle sits where the pill would
                if p.data.get("layout") != "footage":
                    problems.append(f"{sid} (hook): data.caption needs the footage layout (other layouts use captions: true)")
                elif str(d.get("pill") or "").strip():
                    problems.append(f"{sid} (hook): use data.pill or data.caption, not both (they share the lower caption spot)")
                elif s.get("captions") is True:
                    problems.append(f"{sid} (hook): remove \"captions\": true; data.caption is the subtitle and the generic captions would draw dark chips over it")
            for i, w in enumerate(d.get("words", [])):
                if not isinstance(w, dict) or not str(w.get("text", "")).strip() or w.get("at") in (None, ""):
                    problems.append(f"{sid} (hook): data.words[{i}] needs text and at"); continue
                if len(w["text"].split()) > 3:
                    problems.append(f"{sid} (hook): data.words[{i}] has more than 3 words: {w['text']!r}")
                if w.get("tone") not in (None, "pain", "payoff"):
                    problems.append(f"{sid} (hook): data.words[{i}].tone must be 'pain' or 'payoff', not {w.get('tone')!r}")
    return problems


KIT = Path(__file__).resolve().parent.parent / "assets" / "sfx-kit"


def cue_problems(c):
    """Field checks for one cue (sound reference and the held-sound controls)."""
    out, sfx = [], c.get("sfx")
    if sfx:   # null or "" is silence
        src, _, name = str(sfx).partition(":")
        if src not in ("el", "kit") or not re.fullmatch(r"[a-z0-9_]+", name or ""):
            out.append(f"sfx must be el:<name>, kit:<name> or null, not {sfx!r}")
        elif src == "kit" and not (KIT / f"{name}.wav").is_file():
            out.append(f"sfx {sfx}: no {name}.wav in assets/sfx-kit")
    num = lambda k: isinstance(c.get(k), (int, float)) and not isinstance(c.get(k), bool)
    if c.get("loop") is not None and not isinstance(c["loop"], bool):
        out.append("loop must be true or false")
    if c.get("fade") is not None and not (num("fade") and 0 <= c["fade"] <= 3):
        out.append("fade must be 0 to 3 seconds")
    if c.get("duck") is not None and not (num("duck") and -40 <= c["duck"] <= 0):
        out.append("duck must be 0 to -40 dB")
    if c.get("until") is not None and not (isinstance(c["until"], str) and c["until"].strip()):
        out.append("until must be an anchor string, e.g. \"cut\", \"end+0.3\", a word, or \"R02:cut\"")
    if any(c.get(k) is not None for k in ("loop", "fade", "duck")) and c.get("until") is None and c.get("dur") is None:
        out.append("loop, fade and duck only apply to a held sound: add until or dur")
    return out


def scene_cues(s):
    """The scene's cues plus implicit silent cues for hook keywords (kw0, kw1, ...) from data.words[].at."""
    cs = list(s.get("cues", []))
    if s["type"] == "hook":
        for i, w in enumerate((s.get("data") or {}).get("words", [])):
            at = w["at"]
            cs.append({"name": f"kw{i}", "at": f"start+{at}" if isinstance(at, (int, float)) else at, "occ": w.get("occ", 0),
                       "sfx": None, "note": f"big word {w['text']}"})
    return cs


def norm(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def build(p, cut):
    V = json.loads((p.build / f"words-{cut}.json").read_text(encoding="utf-8"))
    lines = {l["scene"]: l for l in V["lines"]}
    duration = round(V["duration"] + p.data["voice"].get("tail", 2.6), 3)
    scenes = p.scenes(cut); out_scenes = []
    for k, s in enumerate(scenes):
        start = 0.0 if k == 0 else round(lines[s["id"]]["start"] - (0.12 if s.get("turn") else 0.2), 3)
        out_scenes.append({"id": s["id"], "type": s["type"], "start": start})
    for k, s in enumerate(out_scenes):
        s["end"] = out_scenes[k + 1]["start"] if k + 1 < len(out_scenes) else duration
    sc = {s["id"]: s for s in out_scenes}

    def anchor(sid, a, occ=0):
        """(time, word) for an anchor in scene sid, or an error string. Anchors: a word of the line, `start` (scene
        start), `end` (last word of the line), `cut` (the scene's cut to the next one), each with an optional +/- s."""
        m = ANCHOR_RE.match(str(a))
        if m:
            base = {"start": sc[sid]["start"], "end": lines[sid]["end"], "cut": sc[sid]["end"]}[m.group(1)]
            return base + float(m.group(2) or 0), None
        ws = [w for w in V["words"] if w["scene"] == sid and norm(w["w"]).startswith(norm(str(a)))]
        if len(ws) <= occ:
            return f"word '{a}' not found in the {sid} line"
        return ws[occ]["s"], ws[occ]["w"]

    def sustain(sid, c, t):
        """Stop time for a held sound (`until` and/or `dur`), clamped to the video; (None, None) for a one-shot."""
        if c.get("until") is None and c.get("dur") is None:
            return None, None
        ends = []
        if c.get("until") is not None:
            u = str(c["until"]); usid, _, ua = u.rpartition(":")
            usid = usid or sid
            if usid not in sc:
                return None, f"until '{u}': scene {usid} is not in this cut"
            hit = anchor(usid, ua, c.get("until_occ", 0))
            if isinstance(hit, str):
                return None, f"until '{u}': {hit}"
            ends.append(hit[0])
        if c.get("dur") is not None:
            if not isinstance(c["dur"], (int, float)) or c["dur"] <= 0:
                return None, f"dur must be a positive number of seconds, not {c['dur']!r}"
            ends.append(t + c["dur"])
        stop = round(min(min(ends), duration), 3)
        if stop <= t:
            return None, f"stops at {stop:.2f} s, which is not after its start ({t:.2f} s)"
        return stop, None

    cues, problems = [], validate(p)
    for s in scenes:
        names = {c["name"] for c in s.get("cues", [])}
        need = required(s) + [x["cue"] for x in s.get("data", {}).get("cards", []) + s.get("data", {}).get("tiles", [])]
        if s["type"] == "recap":
            need += [f"l{i + 1}" for i in range(len(s["data"]["lines"]))]
        problems += [f"{s['id']} ({s['type']}) needs a cue named '{n}'" for n in need if n not in names]
        for c in scene_cues(s):
            cid = f"{s['id']}.{c['name']}"
            hit = anchor(s["id"], c["at"], c.get("occ", 0))
            if isinstance(hit, str):
                problems.append(f"{cid}: {hit}"); continue
            t, word = hit
            t = round(t + c.get("delta", 0.0), 3)
            cue = {"id": cid, "scene": s["id"], "t": t, "word": word,
                   "note": c.get("note", ""), "sfx": c.get("sfx"), "gain_db": c.get("gain", -10), "rate": c.get("rate", 1.0)}
            stop, why = sustain(s["id"], c, t)
            if why:
                problems.append(f"{cid}: {why}"); continue
            if stop is not None:
                cue.update(stop=stop, loop=c.get("loop", True), fade=float(c.get("fade", 0.08)), duck_db=float(c.get("duck", 0.0)))
            cues.append(cue)
    if problems:
        raise SystemExit("project.json cue problems:\n  " + "\n  ".join(problems))
    out = {"cut": cut, "dry": bool(V.get("dry")), "duration": duration, "scenes": out_scenes, "lines": V["lines"], "words": V["words"], "cues": cues}
    (p.build / f"beats-{cut}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (p.build / f"beats-{cut}.js").write_text("window.BEATS = " + json.dumps(out) + ";\n", encoding="utf-8")
    fmt = lambda t: f"{int(t // 60)}:{t % 60:05.2f}"
    md = [f"# Sound sheet: {p.data['name']} ({cut})", "", "| Time | Word | Cue | Visual beat | Sound | Gain dB |", "|---|---|---|---|---|---|"]
    held = lambda c: f" until {fmt(c['stop'])}{' (loop' if c['loop'] else ' (once'}{', duck ' + format(c['duck_db'], 'g') + ' dB' if c['duck_db'] else ''})" if c.get("stop") is not None else ""
    md += [f"| {fmt(c['t'])} | {c['word'] or '(cut or motion)'} | {c['id']} | {c['note']} | {c['sfx'] or ''}{'' if c['rate'] == 1 else ' x' + format(c['rate'], '.2f')}{held(c)} | {c['gain_db']} |"
           for c in sorted(cues, key=lambda c: c["t"])]
    (p.build / f"sound-sheet-{cut}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"  beats {cut}: {duration:.2f} s, {len(out_scenes)} scenes, {len(cues)} cues{' (DRY timings)' if out['dry'] else ''}")
    return out
