"""Field-notes planner (experimental): an ordinary-language brief -> a validated composition plan -> fieldnotes scene data.

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
    return {"template": t.get("id"), "style_sha": sha(style), "renderer_sha": sha((Path(__file__).resolve().parent.parent / "engine" / "fieldnotes.js").read_bytes()),
            "planner_sha": sha(Path(__file__).read_bytes() + PROMPT.read_bytes() + Path(__file__).with_name("fieldnotes_compose.py").read_bytes())}


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


MIGRATION = """## Migration

This approved brief was planned earlier under older rules; that plan no longer passes them. Plan the SAME brief again
under the current rules and catalogue. The brief is approved and must not change: do not return a "brief". Keep the
earlier story, chapter order, headlines, narration and pictures wherever the current rules allow, and change only what
these problems require (fix them honestly; never weaken what the brief says to get round a rule):

{PROBLEMS}

Earlier plan (for continuity; it may use an older format):
```json
{PREVIOUS}
```"""


def build_prompt(brief, revision=None, previous=None, errors=None, migration=None):
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
    if migration:
        rev = MIGRATION.replace("{PROBLEMS}", "\n".join(f"- {p}" for p in migration["problems"])).replace(
            "{PREVIOUS}", json.dumps(migration["previous"], ensure_ascii=False))
    if errors:
        rev += ("\n\n## Fix these problems in your previous reply\n\n" + "\n".join(f"- {e}" for e in errors) +
                "\n\nPrevious reply:\n```json\n" + json.dumps(previous, ensure_ascii=False) + "\n```")
    return PROMPT.read_text(encoding="utf-8").replace("{CATALOG}", catalog_text()).replace("{BRIEF}", brief.strip()).replace("{REVISION}", rev).replace("{WORDS}", str(total))


# ---------- validation and compilation live in studio/fieldnotes_compose.py (the primitive catalogue) ----------
from .fieldnotes_compose import (validate_plan, compile_plan, estimated_seconds, target_seconds, catalog_text, PRIMS,  # noqa: E402
                                 versions, compatibility, storyboard, plan_changes, plan_schema)


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


def _plan_with_repair(brief, revision=None, previous=None, supplied=None, migration=None):
    """One planning call, then at most one repair call if validation finds problems. Returns (plan, problems, usage list).
    A migration keeps the brief exactly as approved (any brief the model returns is ignored)."""
    usage = []
    text, u = ask_model(build_prompt(brief, revision, previous, migration=migration)); usage.append(u)
    plan = parse_reply(text)
    if migration:
        plan["brief"] = brief
    if revision and plan.get("brief"):
        brief = plan["brief"]
    # narration in the (revised) brief wins: a revision that replaces the narration is checked against the NEW words
    # (2026-10-12: the old brief's narration was kept and a correct revision was refused)
    supplied = supplied_narration(brief) or supplied
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
        if migration:
            p2["brief"] = brief
        probs, plan = validate_plan(p2, brief), p2
    return plan, probs, usage, brief, first


def supplied_narration(brief):
    """Narration the owner wrote, if the brief marks it (a line starting 'Narration:' or a quoted script after it)."""
    m = re.search(r"narration(?:\s+timing\s+script|\s+script)?\s*:?\s*\n?\s*[\"“](.+?)[\"”]", brief, re.I | re.S)
    return m.group(1).strip() if m else None


def run_version(name, brief, title=None, revision=None, render=True, migrate_from=None):
    r = Run(name)
    r.fn.mkdir(parents=True, exist_ok=True)
    st = r.state()
    v = len(st["versions"]) + 1
    previous, migration = None, None
    if st["versions"]:
        previous = json.loads((r.fn / f"plan-v{(migrate_from or st.get('current') or v - 1)}.json").read_text(encoding="utf-8"))
    if migrate_from:
        migration = {"problems": migrate_from_problems(r, migrate_from), "previous": previous}
        if plan_schema(previous) != 2:
            previous = None   # an old-format plan is shown only as continuity inside the migration section
    supplied = supplied_narration(brief)
    what = f"migration of v{migrate_from}" if migrate_from else "revision" if revision else "new brief"
    print(f"fieldnotes {name} v{v}: planning ({what}; model {MODEL} via Claude Code login)")
    plan, probs, usage, final_brief, first = _plan_with_repair(brief, revision, previous, supplied, migration)
    (r.fn / f"brief-v{v}.txt").write_text(final_brief.strip() + "\n", encoding="utf-8")
    (r.fn / f"plan-v{v}.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rec = {"version": v, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"), "revision": revision,
           "brief_sha": sha(final_brief), "plan_sha": sha(json.dumps(plan, sort_keys=True)), "style": style_version(),
           "versions": versions(), "studio_commit": git_head(), "model_calls": usage, "first_pass_problems": first, "plan_problems": probs, "status": None,
           "render": {"cut": "vertical", "size": "1080x1920", "fps": 30, "quality": "looks", "timings": f"dry, {DRY_WPS} words/s (silent)"}}
    if migrate_from:
        rec["migrated_from"] = migrate_from
        rec["brief_unchanged"] = sha(final_brief) == sha((r.fn / f"brief-v{migrate_from}.txt").read_text(encoding="utf-8"))
    if probs:
        rec["status"] = "needs-answers" if plan.get("questions") else "unsupported-diagram" if plan.get("gap") else "invalid-plan"
        _finish(r, st, rec)
        print(f"  stopped: {rec['status']}")
        for p in probs:
            print(f"   - {p}")
        return rec
    rec.update(_compile_and_render(r, plan, title or name, v, render))
    (r.fn / f"storyboard-v{v}.md").write_text(storyboard(plan, v, rec.get("duration")) + "\n", encoding="utf-8")
    src = migrate_from or (st.get("current") if st["versions"] else None)
    if src:   # what changed since the version this one was planned from, for the person reviewing it
        rec["changes_from"] = src
        rec["changes"] = plan_changes(json.loads((r.fn / f"plan-v{src}.json").read_text(encoding="utf-8")), plan,
                                      _report(r, src).get("duration"), rec.get("duration"))
    _finish(r, st, rec)
    return rec


def _report(r, v):
    f = r.fn / f"report-v{v}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def check(name, write=True):
    """Compatibility of every saved version with the current schema and validator. Writes fieldnotes/compat.json (a new
    file; plans, briefs, reports and previews are never touched) and returns it."""
    r = Run(name); st = r.state()
    out = {"project": name, "checked": datetime.now(timezone.utc).isoformat(timespec="seconds"), "current": versions(), "versions": {}}
    for e in st["versions"]:
        v = e["version"]
        plan = json.loads((r.fn / f"plan-v{v}.json").read_text(encoding="utf-8"))
        brief = (r.fn / f"brief-v{v}.txt").read_text(encoding="utf-8")
        c = compatibility(plan, brief, _report(r, v))
        c["preview"] = e.get("preview")
        out["versions"][str(v)] = c
    if write and r.fn.exists():
        (r.fn / "compat.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def migrate_from_problems(r, v):
    plan = json.loads((r.fn / f"plan-v{v}.json").read_text(encoding="utf-8"))
    return compatibility(plan, (r.fn / f"brief-v{v}.txt").read_text(encoding="utf-8"), _report(r, v))["problems"]


def migrate(name, version=None, render=True, title=None):
    """Plan an old version's approved brief again under the current rules, as a NEW version. The old brief, plan, report
    and preview stay as they are; the new report lists what changed for a person to review."""
    r = Run(name); st = r.state()
    v = int(version or st.get("current") or 0)
    if not (r.fn / f"plan-v{v}.json").exists():
        raise SystemExit(f"{name} has no v{v}")
    c = check(name)["versions"][str(v)]
    if c["status"] != "needs-migration":
        raise SystemExit(f"{name} v{v} is {c['status']}: nothing to migrate" + ("" if c["status"] != "compatible" else " (use rebuild to re-render it)"))
    brief = (r.fn / f"brief-v{v}.txt").read_text(encoding="utf-8")
    return run_version(name, brief, title=title, render=render, migrate_from=v)


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
    c = compatibility(plan, (r.fn / f"brief-v{v}.txt").read_text(encoding="utf-8"), _report(r, v))
    if c["status"] != "compatible":   # no bypass: a plan the current rules refuse is re-planned, not re-rendered
        raise SystemExit(f"{name} v{v} {c['status']}: " + "; ".join(c["problems"])
                         + f"\n  run `studio.py fieldnotes migrate {name} --version {v}` to plan the same brief again")
    out = _compile_and_render(r, plan, json.loads((r.dir / "project.json").read_text(encoding="utf-8")).get("title", name), f"{v}-rebuild", render)
    out.update(version=v, rebuild=True, versions=versions(), plan_sha=sha(json.dumps(plan, sort_keys=True)), model_calls=[],
               created=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    (r.fn / f"report-v{v}-rebuild.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  rebuild of v{v}: {out['status']}")
    return out
