"""Owner Featured: Field Notes v1 drafts (free; no network, no generation).

    python -m studio.owner_featured draft <tenant> <project> < filled-prompt.txt

Reads templates-experimental/owner-featured-field-notes-v1/{format.json, tenants/<tenant>.json} and the filled prompt
(PROMPT.md), verifies every reused asset by sha256, and writes owner-featured/<project>/draft.json: the four parts,
what is reused, what must be generated (each a separate, person-approved paid step), the music treatment and a quote.
Nothing is generated here."""
import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

from .common import ROOT

FORMAT_DIR = ROOT / "templates-experimental" / "owner-featured-field-notes-v1"
WORK = Path("/home/adam/video-studio/owner-featured")
# Rates used for quotes (2026-10-12 account records): Higgsfield nano_banana_2 keyframe 2 credits, kling3_0 5 s 8.75;
# ElevenLabs turbo bills 0.5 credit per character; Argil talking head $0.30 logged per clip (rate card cap $0.40).
RATES = {"keyframe_credits": 2, "kling_5s_credits": 8.75, "elevenlabs_credits_per_char": 0.5, "argil_usd": 0.30, "argil_usd_cap": 0.40}
PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def quoted(text):
    m = re.search(r"[\"“](.+?)[\"”]", text, re.S)
    return m.group(1).strip() if m else None


def parse_prompt(text):
    """The four numbered items of PROMPT.md. Returns a dict; missing items are None."""
    items = {}
    for n in ("1", "2", "3", "4"):
        m = re.search(rf"^\s*{n}\.\s*(.+?)(?=^\s*[1-4]\.\s|\Z)", text, re.M | re.S)
        items[n] = m.group(1).strip() if m else None
    title = re.search(r"^\s*Title:\s*(.+)$", text, re.M)
    reuse = re.search(r"reuse project\s+([a-z0-9][a-z0-9-]{1,39})", items["3"] or "", re.I)
    return {"title": title.group(1).strip() if title else None,
            "hook_scene": re.sub(r"\s*Owner voiceover.*", "", items["1"] or "", flags=re.S | re.I).strip() or None,
            "hook_line": quoted(items["1"] or ""), "intro_line": quoted(items["2"] or ""),
            "explainer_reuse": reuse.group(1) if reuse else None,
            "explainer_brief": None if reuse else (items["3"] or None), "close": (items["4"] or "standard").strip()}


def explainer_render(name):
    p = Path("/home/adam/video-studio/projects") / name / "build" / "out" / f"{name}-9x16" / "renders" / f"{name}-9x16.mp4"
    return p if p.exists() else None


def draft(tenant, project, prompt_text, work=WORK):
    if not PROJECT_RE.match(project):
        raise SystemExit("project: 2 to 40 lower-case letters, digits or dashes")
    fmt = json.loads((FORMAT_DIR / "format.json").read_text(encoding="utf-8"))
    tpath = FORMAT_DIR / "tenants" / f"{tenant}.json"
    if not tpath.exists():
        raise SystemExit(f"no business profile {tpath.name}: add tenants/{tenant}.json (voice, Argil look, logo, number, close, music)")
    tn = json.loads(tpath.read_text(encoding="utf-8"))
    b = parse_prompt(prompt_text)
    problems = [f"missing {k.replace('_', ' ')}" for k in ("hook_scene", "hook_line", "intro_line") if not b[k]]
    if not (b["explainer_reuse"] or b["explainer_brief"]):
        problems.append("missing explainer (reuse a project or give a brief)")
    reuse = {}
    close = Path(tn["close"]["dir"]) / tn["close"]["clip"]
    reuse["close"] = {"file": str(close), "sha256_ok": close.exists() and sha256(close) == tn["close"]["sha256"], "id": tn["close"]["id"]}
    music = Path(tn["music"]["file"])
    reuse["music"] = {"file": str(music), "sha256_ok": music.exists() and sha256(music) == tn["music"]["sha256"]}
    if b["explainer_reuse"]:
        r = explainer_render(b["explainer_reuse"])
        reuse["explainer"] = {"project": b["explainer_reuse"], "file": str(r) if r else None, "sha256": sha256(r) if r else None}
        if not r:
            problems.append(f"explainer {b['explainer_reuse']} has no render")
    for k, v in reuse.items():
        if v.get("sha256_ok") is False:
            problems.append(f"reused {k} failed its checksum: {v['file']}")
    voice = tn["voice"]
    chars = len(b["hook_line"] or "") + len(b["intro_line"] or "")
    generate = [
        {"step": "hook keyframe", "provider": "higgsfield nano_banana_2", "credits": RATES["keyframe_credits"], "review": "person approves the still before animation"},
        {"step": "hook animation", "provider": "higgsfield kling3_0 5 s from the approved keyframe", "credits": RATES["kling_5s_credits"]},
        {"step": "owner voice: hook + intro", "provider": f"elevenlabs {voice['model']} ({voice['name']}, speed {voice['settings'].get('speed', 1)})",
         "characters": chars, "credits": round(chars * RATES["elevenlabs_credits_per_char"], 1), "review": "listen before the Argil render; no time-stretching"},
        {"step": "owner intro talking head", "provider": f"argil look {tn['argil']['look']} ({tn['argil']['avatar_id']})", "usd": RATES["argil_usd"], "usd_cap": RATES["argil_usd_cap"]}]
    if b["explainer_brief"]:
        generate.append({"step": "new Field Notes explainer", "provider": "studio.fieldnotes_agent new + narrate (owner voice)",
                         "note": "planner calls on the Claude login (not billed per call) and about 0.5 credit per narration character; quoted by that workflow"})
    plan = {"schema": "owner-featured-draft.v1", "format": fmt["format"], "tenant": tenant, "project": project,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "draft (nothing generated)",
            "title": b["title"], "parts": [
                {"part": 1, "role": "customer_reaction_hook", "scene": b["hook_scene"], "voiceover": b["hook_line"], "make": ["hook keyframe", "hook animation", "owner voice"]},
                {"part": 2, "role": "owner_intro", "line": b["intro_line"], "look": tn["argil"]["look"], "make": ["owner voice", "owner intro talking head"]},
                {"part": 3, "role": "field_notes_explanation", "reuse": reuse.get("explainer"), "brief": b["explainer_brief"]},
                {"part": 4, "role": "branded_owner_close", "reuse": reuse["close"], "number": tn["contact_number"]["display"]}],
            "music": {**fmt["music"], "file": reuse["music"]["file"], "sha256_ok": reuse["music"]["sha256_ok"]},
            "rules": fmt["rules"], "generate": generate,
            "quote": {"higgsfield_credits": RATES["keyframe_credits"] + RATES["kling_5s_credits"],
                      "elevenlabs_credits": round(chars * RATES["elevenlabs_credits_per_char"], 1),
                      "argil_usd": RATES["argil_usd"], "argil_usd_cap": RATES["argil_usd_cap"],
                      "excludes": "a new explainer (quoted by the fieldnotes workflow), retakes (only on request)"},
            "problems": problems}
    out = Path(work) / project
    out.mkdir(parents=True, exist_ok=True)
    (out / "draft.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return plan


def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    if len(a) != 3 or a[0] != "draft":
        raise SystemExit(__doc__)
    plan = draft(a[1], a[2], sys.stdin.read())
    print(json.dumps({k: plan[k] for k in ("project", "status", "problems", "quote")}, indent=1))


if __name__ == "__main__":
    main()
