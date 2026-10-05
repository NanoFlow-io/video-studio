"""Single source of timing. Every cue in project.json is anchored to a word of its scene's line
(or to the scene start / line end), so one cue list resolves onto both cut clocks.
Writes build/beats-<cut>.json, build/beats-<cut>.js (window.BEATS) and build/sound-sheet-<cut>.md."""
import json, re

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
}
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".mp4"}
VERTICAL_ONLY = {"hook", "broll"}
MEDIA_DIRS = {"media", "images", "brand"}


def validate(p):
    """Checks on scene data that need no voice timings, so they run before anything is bought."""
    problems = []
    for s in p.data["scenes"]:
        t, d, sid = s["type"], s.get("data", {}) or {}, s["id"]
        if t not in REQUIRED:
            problems.append(f"{sid}: unknown scene type '{t}'"); continue
        if t in VERTICAL_ONLY and s["line"].get("vertical", True) is False:
            problems.append(f"{sid} ({t}): this type is vertical only, so line.vertical cannot be false")
        names = {c["name"] for c in s.get("cues", [])}
        for key in ("media", "proof"):
            if t in VERTICAL_ONLY and d.get(key) is not None:
                f = p.dir / d[key]
                if str(d[key]).replace("\\", "/").split("/")[0] not in MEDIA_DIRS:
                    problems.append(f"{sid} ({t}): data.{key} must sit in one of {', '.join(sorted(MEDIA_DIRS))}/ (those are copied into the page): {d[key]}")
                elif not f.is_file():
                    problems.append(f"{sid} ({t}): data.{key} file not found: {d[key]} (paths are relative to {p.dir})")
                elif f.suffix.lower() not in MEDIA_EXT or (key == "proof" and f.suffix.lower() == ".mp4"):
                    problems.append(f"{sid} ({t}): data.{key} must be {'an image' if key == 'proof' else 'an image or an .mp4'}: {d[key]}")
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
        if t == "hook":
            if d.get("proof") and "turn" not in names:
                problems.append(f"{sid} (hook) needs a cue named 'turn' (when data.proof slams in)")
            if not str(d.get("pill", "")).strip():
                problems.append(f"{sid} (hook): data.pill is required")
            elif len(d["pill"].split()) > 6:
                problems.append(f"{sid} (hook): data.pill has more than 6 words: {d['pill']!r}")
            for i, w in enumerate(d.get("words", [])):
                if not isinstance(w, dict) or not str(w.get("text", "")).strip() or w.get("at") in (None, ""):
                    problems.append(f"{sid} (hook): data.words[{i}] needs text and at"); continue
                if len(w["text"].split()) > 3:
                    problems.append(f"{sid} (hook): data.words[{i}] has more than 3 words: {w['text']!r}")
                if w.get("tone") not in (None, "pain", "payoff"):
                    problems.append(f"{sid} (hook): data.words[{i}].tone must be 'pain' or 'payoff', not {w.get('tone')!r}")
    return problems


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
    cues, problems = [], validate(p)
    for s in scenes:
        names = {c["name"] for c in s.get("cues", [])}
        need = REQUIRED.get(s["type"], []) + [x["cue"] for x in s.get("data", {}).get("cards", []) + s.get("data", {}).get("tiles", [])]
        if s["type"] == "recap":
            need += [f"l{i + 1}" for i in range(len(s["data"]["lines"]))]
        problems += [f"{s['id']} ({s['type']}) needs a cue named '{n}'" for n in need if n not in names]
        for c in scene_cues(s):
            a = c["at"]
            if a.startswith("start") or a.startswith("end"):
                base, _, off = a.partition("+")
                t = (sc[s["id"]]["start"] if base == "start" else lines[s["id"]]["end"]) + (float(off) if off else 0.0); word = None
            else:
                ws = [w for w in V["words"] if w["scene"] == s["id"] and norm(w["w"]).startswith(norm(a))]
                occ = c.get("occ", 0)
                if len(ws) <= occ:
                    problems.append(f"{s['id']}.{c['name']}: word '{a}' not found in the line"); continue
                t, word = ws[occ]["s"], ws[occ]["w"]
            cues.append({"id": f"{s['id']}.{c['name']}", "scene": s["id"], "t": round(t + c.get("delta", 0.0), 3), "word": word,
                         "note": c.get("note", ""), "sfx": c.get("sfx"), "gain_db": c.get("gain", -10), "rate": c.get("rate", 1.0)})
    if problems:
        raise SystemExit("project.json cue problems:\n  " + "\n  ".join(problems))
    out = {"cut": cut, "dry": bool(V.get("dry")), "duration": duration, "scenes": out_scenes, "lines": V["lines"], "words": V["words"], "cues": cues}
    (p.build / f"beats-{cut}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (p.build / f"beats-{cut}.js").write_text("window.BEATS = " + json.dumps(out) + ";\n", encoding="utf-8")
    fmt = lambda t: f"{int(t // 60)}:{t % 60:05.2f}"
    md = [f"# Sound sheet: {p.data['name']} ({cut})", "", "| Time | Word | Cue | Visual beat | Sound | Gain dB |", "|---|---|---|---|---|---|"]
    md += [f"| {fmt(c['t'])} | {c['word'] or '(cut or motion)'} | {c['id']} | {c['note']} | {c['sfx'] or ''}{'' if c['rate'] == 1 else ' x' + format(c['rate'], '.2f')} | {c['gain_db']} |"
           for c in sorted(cues, key=lambda c: c["t"])]
    (p.build / f"sound-sheet-{cut}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"  beats {cut}: {duration:.2f} s, {len(out_scenes)} scenes, {len(cues)} cues{' (DRY timings)' if out['dry'] else ''}")
    return out
