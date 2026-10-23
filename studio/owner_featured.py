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
RATES = {"keyframe_credits": 2, "kling_5s_credits": 8.75, "elevenlabs_credits_per_char": 0.5, "argil_usd": 0.30, "argil_usd_cap": 0.40,
         "elevenlabs_usd_per_credit": 22 / 100000,                  # Creator plan, $22 per 100k credits (invoice)
         "higgsfield_usd_per_credit": (0.05, 0.08),                 # 0.05 = verified extra-credit price; Pro plan price unverified
         "planner_calls": (1, 2), "planner_api_equiv_usd_per_call": (0.30, 0.40),   # observed Field Notes planner calls
         "nano_turns": (8, 12), "nano_api_equiv_usd_per_turn": (0.35, 0.50),        # observed Nano turns, Claude subscription
         "middle_narration_chars": (200, 260)}                     # typical 15 to 17 s Field Notes narration
PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def quoted(text):
    m = re.search(r"[\"“](.+?)[\"”]", text, re.S)
    return m.group(1).strip() if m else None


def parse_prompt(text):
    """The numbered items of PROMPT.md. Returns a dict; missing items are None. Item 3 is a NEW Field Notes brief unless
    it explicitly says 'reuse project <name>' (the optional variant)."""
    items = {}
    for n in ("1", "2", "3", "4"):
        m = re.search(rf"^\s*{n}\.\s*(.+?)(?=^\s*[1-4]\.\s|\Z)", text, re.M | re.S)
        items[n] = m.group(1).strip() if m else None
    title = re.search(r"^\s*Title:\s*(.+)$", text, re.M) or re.search(r"Owner Featured reel for [^:\n]+:\s*(.+?)\.?\s*$", text, re.M)
    reuse = re.search(r"reuse project\s+([a-z0-9][a-z0-9-]{1,39})", items["3"] or "", re.I)
    return {"title": title.group(1).strip() if title else None,
            "hook_scene": re.sub(r"\s*Owner voiceover.*", "", items["1"] or "", flags=re.S | re.I).strip() or None,
            "hook_line": quoted(items["1"] or ""), "intro_line": quoted(items["2"] or ""),
            "explainer_reuse": reuse.group(1) if reuse else None,
            "explainer_brief": None if reuse else (re.sub(r"^\s*(Field Notes )?explainer:\s*", "", items["3"] or "", flags=re.I).strip() or None),
            "close": (items["4"] or "standard").strip()}


def explainer_render(name):
    p = Path("/home/adam/video-studio/projects") / name / "build" / "out" / f"{name}-9x16" / "renders" / f"{name}-9x16.mp4"
    return p if p.exists() else None


def draft(tenant, project, prompt_text, work=WORK):
    if not PROJECT_RE.match(project):
        raise SystemExit("project: 2 to 40 lower-case letters, digits or dashes")
    fmt = json.loads((FORMAT_DIR / "format.json").read_text(encoding="utf-8"))
    tpath = FORMAT_DIR / "tenants" / f"{tenant}.json"
    if not tpath.exists():
        from .owner_profile import find
        match, _ = find(tenant)
        if match:
            tenant, tpath = match["tenant"], FORMAT_DIR / "tenants" / f"{match['tenant']}.json"
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
    mus = tn.get("music") or fmt["music"]["default_bed"]      # the shared NanoFlow bed unless the business overrides it
    music = Path(mus["file"])
    reuse["music"] = {"file": str(music), "sha256_ok": music.exists() and sha256(music) == mus["sha256"],
                      "source": "business override" if tn.get("music") else "template default"}
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
    new_middle = not b["explainer_reuse"]
    hf = RATES["keyframe_credits"] + RATES["kling_5s_credits"]
    el_owner = round(chars * RATES["elevenlabs_credits_per_char"], 1)
    el_mid = tuple(round(c * RATES["elevenlabs_credits_per_char"]) for c in RATES["middle_narration_chars"]) if new_middle else (0, 0)
    usd = lambda credits: round(credits * RATES["elevenlabs_usd_per_credit"], 3)
    generate = []
    if new_middle:
        generate += [
            {"step": "Field Notes story and storyboard (new topic)", "how": "studio.fieldnotes_agent quote/new", "funding": "Claude subscription",
             "calls": RATES["planner_calls"], "gate": "quote, then the person reviews the storyboard"},
            {"step": "Field Notes animation design and silent preview", "how": "fieldnotes compiler + local HyperFrames render", "funding": "local compute, no API charge",
             "gate": "the person approves the silent preview (revisions in plain words, quoted)"},
            {"step": "Field Notes owner narration", "how": f"studio.fieldnotes_agent narrate --pace brisk; Studio Approve Script; one take", "funding": "ElevenLabs prepaid",
             "credits": el_mid, "gate": "Approve Script in the Studio, then listen"}]
    generate += [
        {"step": "customer reaction keyframe", "how": "higgsfield nano_banana_2", "funding": "Higgsfield prepaid", "credits": RATES["keyframe_credits"], "gate": "the person approves the still"},
        {"step": "customer reaction animation", "how": "higgsfield kling3_0 5 s from the approved keyframe", "funding": "Higgsfield prepaid", "credits": RATES["kling_5s_credits"]},
        {"step": "owner voice: hook + intro", "how": f"elevenlabs {voice['model']} ({voice['name']}, speed {voice['settings'].get('speed', 1)}), one take each, no time-stretch",
         "funding": "ElevenLabs prepaid", "characters": chars, "credits": el_owner, "gate": "listen before the Argil render"},
        {"step": "owner intro talking head", "how": f"argil {tn['argil']['look']} ({tn['argil']['avatar_id']}), one-off run on the business server", "funding": "Argil prepaid",
         "usd": RATES["argil_usd"], "usd_cap": RATES["argil_usd_cap"]},
        {"step": "assembly, music, checks, review copy", "how": "format.json assembly + music rules", "funding": "local compute, no API charge", "gate": "final review"}]
    lo_hi = lambda f: (round(f(0), 2), round(f(1), 2))
    prepaid = lo_hi(lambda i: hf * RATES["higgsfield_usd_per_credit"][i] + usd(el_owner + el_mid[i]) + RATES["argil_usd"])
    quote = {"provider_charges_usd": 0.0,
             "prepaid_usage": {"higgsfield_credits": hf, "elevenlabs_credits": (el_owner + el_mid[0], el_owner + el_mid[1]), "argil_clips": 1, "usd": prepaid},
             "subscription_funded": {"planner_calls": RATES["planner_calls"] if new_middle else (0, 0), "nano_turns": RATES["nano_turns"],
                                     "api_equivalent_usd": lo_hi(lambda i: (RATES["planner_calls"][i] * RATES["planner_api_equiv_usd_per_call"][i] if new_middle else 0)
                                                                 + RATES["nano_turns"][i] * RATES["nano_api_equiv_usd_per_turn"][i])},
             "excludes": "retakes (only on request: +8.75 Higgsfield credits per animation, +0.5 ElevenLabs credit per character, +$0.30 per Argil clip)",
             "variant": "new Field Notes middle (default)" if new_middle else "reused middle (optional variant)"}
    plan = {"schema": "owner-featured-draft.v1", "format": fmt["format"], "tenant": tenant, "project": project,
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "draft (nothing generated)",
            "title": b["title"], "parts": [
                {"part": 1, "role": "customer_reaction_hook", "scene": b["hook_scene"], "voiceover": b["hook_line"], "make": ["hook keyframe", "hook animation", "owner voice"]},
                {"part": 2, "role": "owner_intro", "line": b["intro_line"], "look": tn["argil"]["look"], "make": ["owner voice", "owner intro talking head"]},
                {"part": 3, "role": "field_notes_explanation", "reuse": reuse.get("explainer"), "brief": b["explainer_brief"]},
                {"part": 4, "role": "branded_owner_close", "reuse": reuse["close"], "number": tn["contact_number"]["display"]}],
            "music": {**{k: v for k, v in fmt["music"].items() if k != "default_bed"}, "file": reuse["music"]["file"], "sha256_ok": reuse["music"]["sha256_ok"], "source": reuse["music"]["source"]},
            "rules": fmt["rules"], "generate": generate, "quote": quote,
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
