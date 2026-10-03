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
}


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
    cues, problems = [], []
    for s in scenes:
        names = {c["name"] for c in s.get("cues", [])}
        need = REQUIRED.get(s["type"], []) + [x["cue"] for x in s.get("data", {}).get("cards", []) + s.get("data", {}).get("tiles", [])]
        if s["type"] == "recap":
            need += [f"l{i + 1}" for i in range(len(s["data"]["lines"]))]
        problems += [f"{s['id']} ({s['type']}) needs a cue named '{n}'" for n in need if n not in names]
        for c in s.get("cues", []):
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
    out = {"cut": cut, "duration": duration, "scenes": out_scenes, "lines": V["lines"], "words": V["words"], "cues": cues}
    (p.build / f"beats-{cut}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (p.build / f"beats-{cut}.js").write_text("window.BEATS = " + json.dumps(out) + ";\n", encoding="utf-8")
    fmt = lambda t: f"{int(t // 60)}:{t % 60:05.2f}"
    md = [f"# Sound sheet: {p.data['name']} ({cut})", "", "| Time | Word | Cue | Visual beat | Sound | Gain dB |", "|---|---|---|---|---|---|"]
    md += [f"| {fmt(c['t'])} | {c['word'] or '(cut or motion)'} | {c['id']} | {c['note']} | {c['sfx'] or ''}{'' if c['rate'] == 1 else ' x' + format(c['rate'], '.2f')} | {c['gain_db']} |"
           for c in sorted(cues, key=lambda c: c["t"])]
    (p.build / f"sound-sheet-{cut}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"  beats {cut}: {duration:.2f} s, {len(out_scenes)} scenes, {len(cues)} cues")
    return out
