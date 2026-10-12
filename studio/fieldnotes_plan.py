"""Field-notes planner (experimental): an ordinary-language brief -> a validated scene plan -> fieldnotes scene data.

Flow: brief -> Nano drafts a small semantic plan (studio/fieldnotes_prompt.md; facts, chapters, narration and events
from a fixed vocabulary) -> validate_plan() checks it (facts, claims, text fit, cue words, event order, stage rules) ->
compile_plan() turns it into fieldnotes scenes with positions and timings computed here (the model never writes scene
data or code) -> beats.validate() -> silent preview (--dry-timings build + local render) -> a person approves.
Everything is kept under projects/<name>/fieldnotes/ (brief, plan, report, run settings per version) so a version can be
re-rendered exactly with `fieldnotes rebuild`, and a revision is one ordinary-language instruction (`fieldnotes revise`).

The model is called through the local Claude Code CLI on this server's login (headless, no tools, minimal environment,
throwaway working directory), the same route the platform's video wizard uses. It is not a metered API key."""
import copy, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

from .common import ROOT, Project
from . import beats

STYLE_DIR = ROOT / "templates-experimental" / "owner-explainer-field-notes-v1"
PROMPT = Path(__file__).with_name("fieldnotes_prompt.md")
MODEL = os.environ.get("FIELDNOTES_MODEL", "claude-opus-5-5")
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", str(Path.home() / ".local" / "bin" / "claude"))
NO_TOOLS = ["Bash", "Edit", "Write", "Read", "Glob", "Grep", "WebFetch", "WebSearch", "Agent", "Task", "NotebookEdit", "TodoWrite"]
DEFAULT_VOICE = {"voice_id": "iP95p4xoKVk53GoZ742B", "voice_name": "Chris (ElevenLabs premade)", "model": "eleven_multilingual_v2",
                 "settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True, "speed": 1},
                 "lead_in": 0.4, "tail": 1.8}
DRY_WPS = 2.6   # studio/vo.py dry timings: the silent preview's speaking rate
FACTS = ("business", "audience", "problem", "cause", "solution", "outcome")
LIMITS = {"chapter": 14, "kicker": 28, "headline": 20, "callout": 22, "note": 30, "checklist": 34, "step": 40,
          "window_label": 14, "gauge_label": 30, "left": 22, "right": 22, "window_note": 30, "label": 22}
BANNED = ("guarantee", "guaranteed", "always", "never", "best", "lowest", "cheapest", "save", "saves", "savings", "promise")
STAGE_EVENTS = {
    "home_energy": {"establish", "window", "activity", "ac", "playhead", "cool", "shift_earlier", "raise_setting",
                    "reduce_in_window", "gauge", "callout", "note", "checklist"},
    "process_flow": {"establish", "highlight", "break", "fix", "pulse", "gauge", "callout", "note", "checklist"},
}
LEVEL = {"high": 0.85, "medium": 0.55, "low": 0.3}
TONE = {"problem": "ochre", "fix": "sage", "neutral": "blue"}
WORD_RE = re.compile(r"[A-Za-z0-9'’-]+")


def norm(w):
    return re.sub(r"[^a-z0-9']", "", str(w).lower().replace("’", "'"))


def words(text):
    return WORD_RE.findall(str(text or ""))


def sha(s):
    return hashlib.sha256(s.encode("utf-8") if isinstance(s, str) else s).hexdigest()[:16]


def style_version():
    """Hash of the saved style (template palette and fonts) and the renderer, recorded with every plan."""
    t = json.loads((STYLE_DIR / "template.json").read_text(encoding="utf-8"))
    style = json.dumps({k: t.get(k) for k in ("id", "palette", "fonts", "layout", "motion")}, sort_keys=True)
    return {"template": t.get("id"), "style_sha": sha(style), "renderer_sha": sha((ROOT / "engine" / "fieldnotes.js").read_bytes()),
            "planner_sha": sha(Path(__file__).read_bytes() + PROMPT.read_bytes())}


def git_head():
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() or None


# ---------- the model call (headless Claude Code, no tools) ----------

def ask_model(prompt, timeout=900):
    """One headless turn. Returns (reply text, usage dict). Minimal environment, no tools, a throwaway cwd."""
    env = {k: os.environ[k] for k in ("PATH", "HOME", "USER", "LANG") if k in os.environ}
    args = [CLAUDE_BIN, "-p", "--output-format", "json", "--model", MODEL, "--disallowedTools", *NO_TOOLS]
    with tempfile.TemporaryDirectory(prefix="fieldnotes-plan-") as cwd:
        r = subprocess.run(args, input=prompt, capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)
    try:
        env_json = json.loads(r.stdout.strip())
    except ValueError:
        raise SystemExit(f"planner: the model call failed: {(r.stderr or r.stdout).strip().splitlines()[-1:] or r.returncode}")
    if env_json.get("is_error") or not isinstance(env_json.get("result"), str):
        raise SystemExit(f"planner: the model call failed: {str(env_json.get('result') or env_json.get('subtype'))[:300]}")
    u = env_json.get("usage") or {}
    usage = {"model": MODEL, "input_tokens": u.get("input_tokens"), "cache_read_input_tokens": u.get("cache_read_input_tokens"),
             "cache_creation_input_tokens": u.get("cache_creation_input_tokens"), "output_tokens": u.get("output_tokens"),
             "equivalent_api_cost_usd": env_json.get("total_cost_usd"), "billing": "Claude Code login (subscription), not a metered API key",
             "duration_ms": env_json.get("duration_ms")}
    return env_json["result"], usage


def parse_reply(text):
    raw = str(text).strip()
    for cand in (raw, raw[raw.find("{"): raw.rfind("}") + 1] if "{" in raw else ""):
        try:
            v = json.loads(cand)
            if isinstance(v, dict):
                return v
        except ValueError:
            pass
    raise SystemExit("planner: the model did not return a JSON object")


def build_prompt(brief, revision=None, previous=None, errors=None):
    total = 38
    t = target_seconds(brief)
    if t:
        total = max(16, min(80, round((t - 3.4) * DRY_WPS)))
    rev = ""
    if revision:
        rev = ("## Revision\n\nThe owner asked for this change in ordinary language. Apply it to the brief first and return the "
               "full revised brief as \"brief\" in your JSON, then plan from the revised brief. Keep everything else the same "
               f"unless the change needs it.\n\nChange: {revision}\n\nPrevious plan (for continuity):\n```json\n"
               f"{json.dumps(previous, ensure_ascii=False)}\n```")
    if errors:
        rev += ("\n\n## Fix these problems in your previous reply\n\n" + "\n".join(f"- {e}" for e in errors) +
                "\n\nPrevious reply:\n```json\n" + json.dumps(previous, ensure_ascii=False) + "\n```")
    return PROMPT.read_text(encoding="utf-8").replace("{BRIEF}", brief.strip()).replace("{REVISION}", rev).replace("{WORDS}", str(total))


# ---------- plan validation (deterministic) ----------

def _cue_ok(word, narration):
    if word == "start":
        return True
    return any(norm(w).startswith(norm(word)) and norm(word) for w in words(narration))


def validate_plan(plan, brief):
    """Problems with a plan, as plain sentences ([] = fine). Nothing here executes plan content."""
    out, b = [], brief.lower()
    if plan.get("questions"):
        return [f"missing fact: {q}" for q in plan["questions"]]
    if plan.get("gap"):
        return [f"unsupported diagram: {plan['gap']}"]
    facts = plan.get("facts") or {}
    for f in FACTS:
        if not str(facts.get(f) or "").strip():
            out.append(f"facts.{f} is empty: the brief must state it")
    stage = plan.get("stage")
    if stage not in STAGE_EVENTS:
        return out + [f"stage must be one of {', '.join(STAGE_EVENTS)}, not {stage!r}"]
    sp = plan.get("stage_params") or {}
    chapters = plan.get("chapters") or []
    if not 2 <= len(chapters) <= 4:
        out.append("2 to 4 chapters are needed")

    def fit(text, key, where):
        if text is not None and len(str(text)) > LIMITS[key]:
            out.append(f"{where}: {text!r} is {len(str(text))} characters; the limit is {LIMITS[key]}")
        if text and re.search(r"[–—]", str(text)):
            out.append(f"{where}: no em or en dashes")

    texts = []   # every on-screen and spoken string, for the claims check
    steps = []
    if stage == "home_energy":
        for k in ("window_label", "left", "right", "window_note", "gauge_label"):
            fit(sp.get(k), k, f"stage_params.{k}"); texts.append(sp.get(k) or "")
        if not str(sp.get("window_label") or "").strip():
            out.append("stage_params.window_label is required")
    else:
        steps = sp.get("steps") or []
        if not 3 <= len(steps) <= 5 or not all(isinstance(s, dict) and s.get("id") and str(s.get("label") or "").strip() for s in steps):
            out.append("stage_params.steps must be 3 to 5 steps with id and label")
        for s in steps:
            fit(s.get("label"), "step", f"step {s.get('id')}"); texts.append(str(s.get("label") or ""))
        if sp.get("gauge_label") and len(steps) > 4:
            out.append("a gauge fits only with 3 or 4 steps")
        fit(sp.get("gauge_label"), "gauge_label", "stage_params.gauge_label"); texts.append(sp.get("gauge_label") or "")
    ids = [s.get("id") for s in steps]
    state = {"established": False, "window": False, "activity": False, "gauge": False, "thermostat": False}
    spoken = []
    for ci, ch in enumerate(chapters):
        w = f"chapter {ci + 1}"
        fit(ch.get("chapter"), "chapter", f"{w} label"); fit(ch.get("kicker"), "kicker", f"{w} kicker")
        hl = ch.get("headline") or []
        if not isinstance(hl, list) or not 1 <= len(hl) <= 2:
            out.append(f"{w}: headline must be 1 or 2 lines")
        for line in hl if isinstance(hl, list) else []:
            fit(line, "headline", f"{w} headline")
        if ch.get("emphasis") not in (None, "ochre", "blue", "sage", "italic"):
            out.append(f"{w}: emphasis must be ochre, blue, sage or italic")
        nar = str(ch.get("narration") or "").strip()
        if not nar:
            out.append(f"{w}: narration is empty")
        spoken.append(nar)
        if ch.get("emphasis_on") and not _cue_ok(ch["emphasis_on"], nar):
            out.append(f"{w}: emphasis_on {ch['emphasis_on']!r} is not a word of its narration")
        texts += [ch.get("kicker") or "", nar] + [str(x) for x in hl if isinstance(hl, list)]
        evs = ch.get("events") or []
        if not evs:
            out.append(f"{w}: at least one event is needed")
        for ei, e in enumerate(evs):
            we = f"{w} event {ei + 1} ({e.get('do')})"
            do = e.get("do")
            if do not in STAGE_EVENTS[stage]:
                out.append(f"{we}: not an event of the {stage} stage"); continue
            if not _cue_ok(str(e.get("on") or "start"), nar):
                out.append(f"{we}: on {e.get('on')!r} is not a word of this chapter's narration")
            if do != "establish" and not state["established"]:
                out.append(f"{we}: the scene must be established first (chapter 1, first event)")
            if do == "establish":
                if state["established"]:
                    out.append(f"{we}: establish happens once")
                state["established"] = True
            for key in ("text", "label"):
                if key in e:
                    fit(e[key], {"callout": "callout", "note": "note", "checklist": "checklist"}.get(do, "label"), we); texts.append(str(e[key]))
            if stage == "home_energy":
                if do == "window": state["window"] = True
                if do == "activity":
                    state["activity"] = True
                    if not state["window"]: out.append(f"{we}: show the window first")
                if do in ("shift_earlier", "reduce_in_window") and not state["activity"]:
                    out.append(f"{we}: needs activity shown earlier")
                if do == "raise_setting" and not sp.get("thermostat"):
                    out.append(f"{we}: set stage_params.thermostat to true")
                if do == "ac" and e.get("speed") not in ("high", "low", "off"):
                    out.append(f"{we}: speed must be high, low or off")
                if do == "callout" and e.get("target") not in ("ac", "window", "before", "thermostat"):
                    out.append(f"{we}: target must be ac, window, before or thermostat")
                if do == "callout" and e.get("target") == "thermostat" and not sp.get("thermostat"):
                    out.append(f"{we}: no thermostat in this stage")
            else:
                if do == "highlight" and e.get("step") not in ids:
                    out.append(f"{we}: step must be one of {ids}")
                if do in ("break", "fix"):
                    ln = e.get("link")
                    if not (isinstance(ln, list) and len(ln) == 2 and ln[0] in ids and ln[1] in ids and ids.index(ln[1]) == ids.index(ln[0]) + 1):
                        out.append(f"{we}: link must be two adjacent steps in order, like [\"s2\", \"s3\"]")
                if do == "pulse" and not (e.get("from") in ids and e.get("to") in ids and ids.index(e["to"]) > ids.index(e["from"])):
                    out.append(f"{we}: pulse needs from and to steps, from before to")
                if do == "callout" and e.get("target") not in ids + ["gauge"]:
                    out.append(f"{we}: target must be a step id or gauge")
            if do == "gauge":
                if e.get("level") not in LEVEL: out.append(f"{we}: level must be high, medium or low")
                if not sp.get("gauge_label"): out.append(f"{we}: set stage_params.gauge_label")
                state["gauge"] = True
            if do == "callout" and e.get("target") == "gauge" and not state["gauge"]:
                out.append(f"{we}: draw the gauge before calling it out")
    # narration supplied in the brief must be used word for word
    if facts.get("narration_supplied") and plan.get("supplied_narration"):
        if [norm(x) for x in words(" ".join(spoken))] != [norm(x) for x in words(plan["supplied_narration"])]:
            out.append("the chapters' narration must be the supplied narration, word for word and in order")
    # claims: numbers and absolute words only when the brief has them
    for t in texts:
        for d in re.findall(r"\d[\d,.:%]*", str(t)):
            if d.rstrip(".,") not in brief:
                out.append(f"claim check: {d!r} in {t!r} is not in the brief")
        for wd in words(t):
            if norm(wd) in BANNED and norm(wd) not in {norm(x) for x in words(b)}:
                out.append(f"claim check: {wd!r} in {t!r} is not in the brief")
    total = len(words(" ".join(spoken)))
    if not 12 <= total <= 90:
        out.append(f"narration is {total} words; keep it between 12 and 90")
    target = target_seconds(brief)
    if target and not facts.get("narration_supplied") and chapters and not out:
        est = estimated_seconds(compile_plan(plan, "check", "check"))
        if not 0.8 * target <= est <= 1.2 * target:
            want = max(10, round(total * target / est))
            out.append(f"the brief asks for about {target} s but this plan runs about {est} s; use about {want} words in total"
                       + (" or fewer events after the last word of a chapter" if est > target else ""))
    return out


def estimated_seconds(pj):
    """The silent preview's length for a compiled project: the dry-timings maths of studio/vo.py and beats.py."""
    v, t = pj["voice"], pj["voice"].get("lead_in", 0.5)
    for s in pj["scenes"]:
        n = max(1, len(s["line"]["text"].split()))
        t += (n - 1) / DRY_WPS + 0.85 / DRY_WPS + 0.12 + s["line"].get("pause", [0.45, 0.35])[1]
    return round(t + v.get("tail", 2.6), 1)


def target_seconds(brief):
    m = re.search(r"(?:about|approximately|around|roughly)?\s*(\d{1,3})\s*(?:s\b|sec\b|secs\b|seconds?\b)", brief, re.I)
    return int(m.group(1)) if m and 5 <= int(m.group(1)) <= 120 else None


# ---------- compile a plan into fieldnotes scenes (positions and timings decided here) ----------

def _cue_name(word, used):
    base = re.sub(r"[^a-z0-9]", "", norm(word))[:12] or "w"
    name, k = base, 2
    while name in used:
        name = f"{base}{k}"; k += 1
    used.add(name)
    return name


def _est_word_time(nar, word):
    if word == "start":
        return 0.0
    for i, w in enumerate(words(nar)):
        if norm(w).startswith(norm(word)):
            return 0.2 + i / DRY_WPS
    return 0.0


def _gauge(scenes, actions, objects, t, level):
    """The first gauge event draws it straight to its level; later ones move it."""
    drawn = any(a.get("target") == "gauge" and a["do"] == "draw" for sc in scenes for a in sc["data"]["actions"]) or \
        any(a.get("target") == "gauge" and a["do"] == "draw" for a in actions)
    if drawn:
        return [{"at": t, "do": "set", "target": "gauge", "level": level, "dur": 0.9}]
    objects.append({"id": "gauge", "level": level})
    return [{"at": t, "do": "draw", "target": "gauge", "dur": 0.6}]


HOME = {"house": {"x": 400, "y": 1110, "scale": 1.35}, "ac": {"x": 800, "y": 1110, "scale": 1},
        "timeline": {"x": 72, "y": 1400, "w": 936}, "band": (0.56, 0.82), "early": (0.40, 0.56), "atpeak": (0.56, 0.84),
        "moved": (0.62, 0.78), "moved_to": (0.22, 0.38), "gauge": {"x": 72, "y": 1540, "w": 600},
        "thermo": {"x": 170, "y": 700, "r": 62}, "card": {"x": 72, "y": 1622, "w": 860}, "note": {"x": 1008, "y": 1490}}
FLOW = {"x": 72, "y": 640, "w": 640, "right": 744, "bottom": 1500, "card": {"x": 72, "y": 1640, "w": 860}}


def flow_size(n):
    """Step height and gap so 3 to 5 steps fill the illustration band (y 640 to 1500)."""
    bh = 150 if n <= 4 else 128
    return bh, int(min(130, (FLOW["bottom"] - FLOW["y"] - n * bh) / max(1, n - 1)))


def compile_plan(plan, name, title):
    """The plan -> a project.json dict with fieldnotes scenes. Deterministic: the same plan gives the same project."""
    t = json.loads((STYLE_DIR / "template.json").read_text(encoding="utf-8"))
    pal = t["palette"]
    palette = {"primary": pal["sage"], "accent": pal["ochre"], "ink": pal["ink"], "paper": pal["paper"], "ink2": pal["inkSoft"],
               "grid": pal["grid"], "muted": "#8A8378", "ochre": pal["ochre"], "ochreRule": pal["ochreRule"], "sage": pal["sage"],
               "sageWipe": pal["sageWipe"], "sageTint": pal["sageTint"], "blue": pal["dustyBlue"], "blueStroke": pal["blueStroke"],
               "ground": pal["groundTint"], "card": "#F6F1E8"}
    stage, sp, chs = plan["stage"], plan.get("stage_params") or {}, plan["chapters"]
    business = (plan.get("facts") or {}).get("business") or ""
    brand = re.sub(r"[^A-Za-z0-9 &'.]", "", re.sub(r"\(.*?\)", "", business)).strip().upper()[:28]
    scenes, n = [], len(chs)
    for ci, ch in enumerate(chs):
        sid, nar, used = f"F{ci + 1:02d}", ch["narration"].strip(), set()
        cues, actions, objects = [], [], []
        cue_of = {}

        def at(word, off=0.0):
            if word in (None, "start"):
                return round(0.35 + off, 2)
            if word not in cue_of:
                cue_of[word] = _cue_name(word, used)
                cues.append({"name": cue_of[word], "at": word, "sfx": None})
            return f"{cue_of[word]}{off:+.2f}" if off else cue_of[word]

        last_est = 0.0
        hl = [{"text": x} for x in ch["headline"]]
        if len(hl) == 2 and ch.get("emphasis"):
            hl[1]["em"] = ch["emphasis"]
            if ch.get("emphasis_on"):
                hl[1]["at"] = at(ch["emphasis_on"], 0.15)
        seq = 0.0   # extra offset for events sharing a word, so they unfold rather than land at once
        prev_on = None
        for e in ch["events"]:
            on = e.get("on") or "start"
            seq = seq + 0.45 if on == prev_on else 0.0
            prev_on = on
            when = (lambda off=0.0: at(on, seq + off))
            est = _est_word_time(nar, on) + seq
            last_est = max(last_est, est + 1.2)
            do = e["do"]
            if stage == "home_energy":
                H = HOME
                if do == "establish":
                    objects += [
                        {"id": "house", "kind": "house", **H["house"]},
                        {"id": "ac", "kind": "ac_unit", **H["ac"]},
                        {"id": "timeline", "kind": "timeline", **H["timeline"], "left": sp.get("left") or "EARLIER", "right": sp.get("right") or "LATER",
                         "bands": [{"id": "peak", "from": H["band"][0], "to": H["band"][1], "label": sp.get("window_label") or "PEAK"}],
                         "segs": [{"id": "early", "from": H["early"][0], "to": H["early"][1], "level": 0.9},
                                  {"id": "atpeak", "from": H["atpeak"][0], "to": H["atpeak"][1], "level": 0.9}],
                         "playhead": {"pos": 0.3}}]
                    if sp.get("gauge_label"):
                        objects.append({"id": "gauge", "kind": "gauge", **H["gauge"], "label": sp["gauge_label"], "level": 0.85, "color": "blueStroke"})
                    if sp.get("window_note"):
                        objects.append({"id": "wnote", "kind": "note", **H["note"], "align": "right", "size": 34, "text": sp["window_note"], "carry": True})
                    actions += [{"at": when(0.0), "do": "draw", "target": "house", "dur": 0.7},
                                {"at": when(0.25), "do": "draw", "target": "ac", "dur": 0.6},
                                {"at": when(0.5), "do": "draw", "target": "timeline", "dur": 0.6}]
                elif do == "window":
                    actions.append({"at": when(), "do": "show", "target": "timeline.peak"})
                    if sp.get("window_note"):
                        actions.append({"at": when(0.6), "do": "show", "target": "wnote"})
                elif do == "activity":
                    actions += [{"at": when(), "do": "show", "target": "timeline.early", "dur": 0.4},
                                {"at": when(0.3), "do": "show", "target": "timeline.atpeak", "dur": 0.5}]
                elif do == "ac":
                    actions.append({"at": when(), "do": "run", "target": "ac", "speed": {"high": 1.6, "low": 0.45, "off": 0}[e.get("speed", "high")]})
                elif do == "playhead":
                    a, b2 = (0.56, 0.82) if e.get("through") == "window" else (0.2, 0.5)
                    actions += [{"at": when(), "do": "show", "target": "timeline.playhead"},
                                {"at": when(0.05), "do": "playhead", "target": "timeline.playhead", "from": a, "to": b2, "dur": 2.0},
                                {"at": "end-0.45", "do": "hide", "target": "timeline.playhead"}]
                elif do == "cool":
                    if not any(o["id"] == "coolair" for o in objects):
                        objects.append({"id": "coolair", "kind": "arrow", "points": [[712, 975], [670, 870], [590, 925]], "color": "blueStroke", "dash": True, "width": 6})
                    actions += [{"at": when(), "do": "draw", "target": "coolair", "dur": 0.6},
                                {"at": when(0.5), "do": "flow", "target": "coolair", "dur": 2.4},
                                {"at": when(0.2), "do": "fill", "target": "house", "level": 1 if e.get("level") != "partial" else 0.6, "dur": 1.4}]
                elif do == "shift_earlier":
                    objects.append({"id": "timeline", "segs": [{"id": "moved", "from": H["moved"][0], "to": H["moved"][1], "level": 0.45}]})
                    actions += [{"at": when(), "do": "show", "target": "timeline.moved", "dur": 0.3},
                                {"at": when(0.3), "do": "seg", "target": "timeline.moved", "from": H["moved_to"][0], "to": H["moved_to"][1], "level": 0.9, "dur": 0.9},
                                {"at": when(0.3), "do": "seg", "target": "timeline.atpeak", "level": 0.55, "dur": 0.9}]
                elif do == "raise_setting":
                    objects += [{"id": "thermo", "kind": "thermostat", **H["thermo"], "angle": -30},
                                {"id": "thermlink", "kind": "arrow", "points": [[170, 762], [170, 1000], [262, 1000]], "color": "ink", "dash": True, "head": False, "width": 3}]
                    actions += [{"at": round(0.45 if on == "start" else 0.3, 2), "do": "draw", "target": "thermo", "dur": 0.6},
                                {"at": round(0.6 if on == "start" else 0.45, 2), "do": "draw", "target": "thermlink", "dur": 0.5},
                                {"at": when(), "do": "turn", "target": "thermo", "by": 28, "dur": 0.8}]
                    if e.get("label"):
                        objects.append({"id": "higher", "kind": "callout", "x": 248, "y": 680, "lx": 300, "ly": 640, "style": "tag", "text": e["label"]})
                        actions.append({"at": when(0.45), "do": "show", "target": "higher"})
                elif do == "reduce_in_window":
                    actions.append({"at": when(), "do": "seg", "target": "timeline.atpeak", "level": 0.2 if e.get("level", "low") == "low" else 0.5, "dur": 0.9})
                elif do == "gauge":
                    actions += _gauge(scenes, actions, objects, when(), LEVEL[e["level"]])
                elif do == "callout":
                    pos = {"ac": {"x": 862, "y": 962, "ly": 870}, "window": {"x": 72 + 0.69 * 936, "y": 1252, "ly": 1205},
                           "before": {"x": 72 + 0.30 * 936, "y": 1328, "ly": 1236}, "thermostat": {"x": 248, "y": 680, "lx": 300, "ly": 640}}[e["target"]]
                    cid = f"c{ci + 1}{len(objects)}"
                    objects.append({"id": cid, "kind": "callout", **pos, "style": "tag" if e["target"] != "before" else "label", "text": e["text"]})
                    actions.append({"at": when(0.2), "do": "show", "target": cid})
                elif do == "note":
                    nid = f"n{ci + 1}{len(objects)}"
                    objects.append({"id": nid, "kind": "note", **H["note"], "align": "right", "size": 34, "text": e["text"]})
                    actions.append({"at": when(0.2), "do": "show", "target": nid})
                elif do == "checklist":
                    objects.append({"id": "card", "kind": "card", **H["card"], "text": e["text"]})
                    actions.append({"at": when(), "do": "show", "target": "card"})
            else:
                F, steps = FLOW, sp["steps"]
                ids = [s["id"] for s in steps]
                bh, gap = flow_size(len(steps))
                mid = lambda sid_: F["y"] + ids.index(sid_) * (bh + gap) + bh / 2
                gy = F["y"] + len(steps) * (bh + gap) - gap + 50
                link = lambda pair: f"l{ids.index(pair[0]) + 1}"
                if do == "establish":
                    objects.append({"id": "flow", "kind": "flow", "x": F["x"], "y": F["y"], "w": F["w"], "boxH": bh, "gap": gap,
                                    "nodes": [{"id": s["id"], "label": s["label"]} for s in steps]})
                    if sp.get("gauge_label"):
                        objects.append({"id": "gauge", "kind": "gauge", "x": 72, "y": gy, "w": 600, "label": sp["gauge_label"], "level": 0.8, "color": "blueStroke"})
                    actions.append({"at": when(), "do": "draw", "target": "flow", "dur": 1.6})
                    last_est = max(last_est, est + 2.0)
                elif do == "highlight":
                    actions.append({"at": when(), "do": "highlight", "target": f"flow.{e['step']}", "tone": TONE.get(e.get("tone"), "ochre")})
                elif do in ("break", "fix"):
                    actions.append({"at": when(), "do": "mark", "target": f"flow.{link(e['link'])}", "state": "broken" if do == "break" else "ok", "label": e.get("label") or ""})
                elif do == "pulse":
                    actions.append({"at": when(), "do": "pulse", "target": "flow", "from": e["from"], "to": e["to"], "dur": 1.6})
                    last_est = max(last_est, est + 1.8)
                elif do == "gauge":
                    actions += _gauge(scenes, actions, objects, when(), LEVEL[e["level"]])
                elif do == "callout":
                    cid = f"c{ci + 1}{len(objects)}"
                    if e["target"] == "gauge":
                        pos = {"x": 672, "y": gy + 13, "lx": 700, "ly": gy + 13}
                    else:
                        pos = {"x": F["x"] + F["w"], "y": mid(e["target"]), "lx": F["right"], "ly": mid(e["target"]), "maxw": 1008 - F["right"] - 12}
                    objects.append({"id": cid, "kind": "callout", **pos, "style": "tag", "text": e["text"]})
                    actions.append({"at": when(0.2), "do": "show", "target": cid})
                elif do == "note":
                    nid = f"n{ci + 1}{len(objects)}"
                    objects.append({"id": nid, "kind": "note", "x": 1008, "y": 1560, "align": "right", "size": 34, "text": e["text"]})
                    actions.append({"at": when(0.2), "do": "show", "target": nid})
                elif do == "checklist":
                    objects.append({"id": "card", "kind": "card", **F["card"], "text": e["text"]})
                    actions.append({"at": when(), "do": "show", "target": "card"})
        speech = 0.2 + max(1, len(words(nar))) / DRY_WPS
        hold = round(min(1.6, max(0.4, last_est - speech + 0.5)), 2) if ci < n - 1 else 0
        scenes.append({"id": sid, "type": "fieldnotes", "line": {"text": nar, "pause": [0, hold]}, "cues": cues, "data": {
            **({"transition": "bands"} if ci == n - 1 and n > 2 else {}),
            "header": {"brand": brand, "label": "FIELD NOTES", "chapter": ch["chapter"].upper(), "index": ci + 1, "total": n},
            "kicker": (ch.get("kicker") or "").upper(),
            "headline": {"lines": hl}, "objects": objects, "actions": actions}})
    return {"name": name, "title": title, "style": "entertainment",
            "_note": "Generated by `studio.py fieldnotes` from fieldnotes/brief-v*.txt; do not hand-edit (revise the brief instead).",
            "palette": palette, "fonts": {"title": "Inter Tight", "body": "Inter", "note": "Instrument Serif"},
            "voice": copy.deepcopy(DEFAULT_VOICE), "audio": {}, "music": {}, "sfx": {}, "scenes": scenes}


# ---------- the workflow ----------

class Run:
    def __init__(self, name):
        self.name = name
        self.dir = ROOT / "projects" / name
        self.fn = self.dir / "fieldnotes"

    def state(self):
        f = self.fn / "run.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"name": self.name, "versions": []}

    def save_state(self, st):
        (self.fn / "run.json").write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _plan_with_repair(brief, revision=None, previous=None, supplied=None):
    """One planning call, then at most one repair call if validation finds problems. Returns (plan, problems, usage list)."""
    usage = []
    text, u = ask_model(build_prompt(brief, revision, previous)); usage.append(u)
    plan = parse_reply(text)
    if revision and plan.get("brief"):
        brief = plan["brief"]
    if supplied:
        plan["supplied_narration"] = supplied
    probs = validate_plan(plan, brief)
    first = list(probs)
    fixable = probs and not plan.get("questions") and not plan.get("gap")
    if fixable:
        text, u = ask_model(build_prompt(brief, None, plan, probs)); usage.append(u)
        p2 = parse_reply(text)
        if supplied:
            p2["supplied_narration"] = supplied
        p2.setdefault("brief", plan.get("brief"))
        probs, plan = validate_plan(p2, brief), p2
    return plan, probs, usage, brief, first


def supplied_narration(brief):
    """Narration the owner wrote, if the brief marks it (a line starting 'Narration:' or a quoted script after it)."""
    m = re.search(r"narration(?:\s+timing\s+script|\s+script)?\s*:?\s*\n?\s*[\"“](.+?)[\"”]", brief, re.I | re.S)
    return m.group(1).strip() if m else None


def run_version(name, brief, title=None, revision=None, render=True):
    r = Run(name)
    r.fn.mkdir(parents=True, exist_ok=True)
    st = r.state()
    v = len(st["versions"]) + 1
    previous = None
    if st["versions"]:
        previous = json.loads((r.fn / f"plan-v{v - 1}.json").read_text(encoding="utf-8"))
    supplied = supplied_narration(brief)
    print(f"fieldnotes {name} v{v}: planning ({'revision' if revision else 'new brief'}; model {MODEL} via Claude Code login)")
    plan, probs, usage, final_brief, first = _plan_with_repair(brief, revision, previous, supplied)
    (r.fn / f"brief-v{v}.txt").write_text(final_brief.strip() + "\n", encoding="utf-8")
    (r.fn / f"plan-v{v}.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rec = {"version": v, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "revision": revision,
           "brief_sha": sha(final_brief), "plan_sha": sha(json.dumps(plan, sort_keys=True)), "style": style_version(),
           "studio_commit": git_head(), "model_calls": usage, "first_pass_problems": first, "plan_problems": probs, "status": None,
           "render": {"cut": "vertical", "size": "1080x1920", "fps": 30, "quality": "looks", "timings": f"dry, {DRY_WPS} words/s (silent)"}}
    if probs:
        rec["status"] = "needs-answers" if plan.get("questions") else "unsupported-diagram" if plan.get("gap") else "invalid-plan"
        _finish(r, st, rec)
        print(f"  stopped: {rec['status']}")
        for p in probs:
            print(f"   - {p}")
        return rec
    rec.update(_compile_and_render(r, plan, title or name, v, render))
    _finish(r, st, rec)
    return rec


def _compile_and_render(r, plan, title, v, render):
    pj = compile_plan(plan, r.name, title)
    if (r.dir / "project.json").exists():
        shutil.copy(r.dir / "project.json", r.fn / f"project-before-v{v}.json")
    (r.dir / "project.json").write_text(json.dumps(pj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    fonts = r.dir / "fonts"
    if not fonts.exists():
        shutil.copytree(STYLE_DIR / "fonts", fonts)
    scene_probs = beats.validate(Project(r.name))
    out = {"scene_problems": scene_probs, "project_sha": sha(json.dumps(pj, sort_keys=True))}
    if scene_probs:
        out["status"] = "invalid-scenes"
        return out
    out["status"] = "planned"
    if not render:
        return out
    py = sys.executable
    b = subprocess.run([py, "studio.py", "build", r.name, "--dry-timings"], cwd=ROOT, capture_output=True, text=True)
    if b.returncode:
        out.update(status="build-failed", log=(b.stdout + b.stderr)[-1500:]); return out
    rr = subprocess.run([py, "studio.py", "render", r.name, "--cut", "vertical"], cwd=ROOT, capture_output=True, text=True)
    mp4 = Project(r.name).render_path("vertical")
    if rr.returncode or not mp4.exists():
        out.update(status="render-failed", log=(rr.stdout + rr.stderr)[-1500:]); return out
    keep = r.fn / f"preview-v{v}.mp4"
    shutil.copy(mp4, keep)
    out.update(status="awaiting-approval", preview=str(keep.relative_to(ROOT)), preview_sha=sha(keep.read_bytes()))
    beats_j = json.loads((r.dir / "build" / "beats-vertical.json").read_text(encoding="utf-8"))
    out["duration"] = beats_j["duration"]
    print(f"  preview: {keep} ({beats_j['duration']} s, silent) -> awaiting a person's approval")
    return out


def _finish(r, st, rec):
    (r.fn / f"report-v{rec['version']}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    st["versions"].append({k: rec.get(k) for k in ("version", "created", "status", "revision", "brief_sha", "plan_sha", "preview")})
    st["current"] = rec["version"]
    r.save_state(st)


def rebuild(name, version=None, render=True):
    """Re-compile a saved plan (no model call) and re-render it: the same plan gives the same scenes."""
    r = Run(name); st = r.state()
    v = version or st.get("current")
    plan = json.loads((r.fn / f"plan-v{v}.json").read_text(encoding="utf-8"))
    out = _compile_and_render(r, plan, json.loads((r.dir / "project.json").read_text(encoding="utf-8")).get("title", name), f"{v}-rebuild", render)
    print(f"  rebuild of v{v}: {out['status']}")
    return out
