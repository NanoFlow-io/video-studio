"""Nano's draft-only entry point for Owner Explainer Field Notes v1 (experimental, 2026-10-12).

A person talks to Nano in plain English; Nano runs ONE command per step and relays the result. Nobody edits JSON.

    python -m studio.fieldnotes_agent quote   <new|revise|migrate|rebuild|deliver|status> [project]
    python -m studio.fieldnotes_agent new     <project> --quote ID [--title T] < brief.txt   (brief text on stdin)
    python -m studio.fieldnotes_agent revise  <project> --quote ID --change "make it shorter and end on ..."
    python -m studio.fieldnotes_agent replan  <project> --quote ID              (plan the same brief again, e.g. after a stop)
    python -m studio.fieldnotes_agent migrate <project> --quote ID [--version N]
    python -m studio.fieldnotes_agent rebuild <project> [--version N]     (renderer-only fixes; no model call)
    python -m studio.fieldnotes_agent deliver <project> [--version N]     (review link again; no model call)
    python -m studio.fieldnotes_agent status  <project>

Every command prints one JSON object: status, the storyboard (markdown), what changed, questions, missing illustrations,
model usage, the silent preview's path and a review link that has been checked against the running Studio.

Draft only, by construction: the planner builds with --dry-timings (silent, no narration API) and renders locally; this
module has no approve, narrate, render-remote or publish action. Model-call actions need the id of a quote produced the
same day, so the cost is shown to the person before anything runs. Review delivery copies the draft into the Studio's
projects folder as a separate review project (<project>-v<N>) with a marker file; it never overwrites a project it did
not create and never deletes anything."""
import argparse, hashlib, json, re, os, shutil, subprocess, sys, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .common import ROOT
from . import fieldnotes_plan as fp
from .fieldnotes_compose import compile_plan, storyboard, compatibility

REVIEW_ROOT = Path(os.environ.get("FIELDNOTES_REVIEW_ROOT", "/home/adam/video-studio"))   # the Studio the admin panel reads
REVIEW_BASE = os.environ.get("FIELDNOTES_REVIEW_BASE", "https://techbots.io")
PLATFORM_DIR = Path(os.environ.get("TECHBOTS_DIR", "/home/adam/techbots-platform"))
MODEL_ACTIONS = {"new": (1, 2), "revise": (1, 2), "replan": (1, 2), "migrate": (1, 2)}
NAME_OK = __import__("re").compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
MARKER = "review-of.json"


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def quote_id(action, project):
    return hashlib.sha256(f"fieldnotes|{action}|{project or ''}|{today()}".encode()).hexdigest()[:10]


def _history():
    """Per-call API-equivalent costs from every saved field-notes report (the basis of a quote)."""
    costs = []
    for f in (ROOT / "projects").glob("*/fieldnotes/report-v*.json"):
        try:
            for c in json.loads(f.read_text(encoding="utf-8")).get("model_calls") or []:
                if isinstance(c.get("equivalent_api_cost_usd"), (int, float)):
                    costs.append(c["equivalent_api_cost_usd"])
        except ValueError:
            pass
    return costs


def quote(action, project=None):
    lo, hi = MODEL_ACTIONS.get(action, (0, 0))
    costs = _history() or [0.4]
    avg, top = sum(costs) / len(costs), max(costs)
    out = {"action": action, "project": project, "model_calls": f"{lo} to {hi}" if hi else "none",
           "other_spend": "none: silent preview (dry timings), local render, no narration, nothing published"}
    if hi:
        out.update(model=fp.MODEL, billing="Claude Code login (subscription), not billed per call",
                   api_equivalent_usd=[round(lo * avg, 2), round(hi * top, 2)], based_on_calls=len(costs),
                   quote_id=quote_id(action, project), valid=f"today ({today()} UTC)")
    return out


def _need_quote(action, project, given):
    if action in MODEL_ACTIONS and given != quote_id(action, project):
        raise SystemExit(json.dumps({"ok": False, "error": f"quote first: run `quote {action} {project}` and show it to the person; "
                                     "then pass its quote_id with --quote"}))


def review_name(project, v):
    suffix = f"-v{v}"
    return (project[: 40 - len(suffix)].rstrip("-") + suffix)


def _sha_full(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _http_status(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "nano-fieldnotes-check"}), timeout=20) as r:
            return r.status, r.headers.get("content-type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", "")
    except Exception as e:   # network trouble: reported, not raised
        return None, str(e)[:120]


def prove_link(name, preview):
    """Evidence that the review link plays this preview: the running Studio's own service code (the module behind the
    admin route) finds the project and resolves the same bytes, the media route is mounted behind the admin login
    (401 without a session, not 404), and the page itself loads."""
    proof, want = {}, _sha_full(preview)
    js = ("const vs = await import(process.argv[1]); const n = process.argv[2];"
          "const p = await vs.getProject(n); const f = vs.mediaFile(n, 'video', 'vertical');"
          "const h = (await import('node:crypto')).createHash('sha256').update((await import('node:fs')).readFileSync(f)).digest('hex');"
          "console.log(JSON.stringify({scenes: p.scenes.length, file: f, sha256: h})); process.exit(0);")
    dist = PLATFORM_DIR / "dist" / "services" / "video-studio.js"
    try:
        r = subprocess.run(["node", "--input-type=module", "-e", js, str(dist), name], capture_output=True, text=True, timeout=90,
                           cwd=PLATFORM_DIR, env={**os.environ, "VIDEO_STUDIO_DIR": str(REVIEW_ROOT)})
        svc = json.loads(r.stdout.strip().splitlines()[-1])
        proof["studio_service"] = {"ok": svc["sha256"] == want, "file": svc["file"], "scenes": svc["scenes"]}
    except Exception as e:
        proof["studio_service"] = {"ok": False, "error": str(e)[:200]}
    code, ctype = _http_status(f"{REVIEW_BASE}/api/admin/gtm/video/projects/{name}/media/vertical/video")
    proof["media_route"] = {"ok": code == 401, "status_without_login": code, "means": "mounted and behind the admin login"}
    page = f"{REVIEW_BASE}/admin/gtm/video-studio/{name}?step=publish"
    code, ctype = _http_status(page)
    proof["page"] = {"ok": code == 200 and "html" in ctype, "status": code}
    return all(v.get("ok") for v in proof.values()), proof


def deliver(project, version=None, rebuild=False):
    """Copy one previewed version (or its latest renderer-only rebuild) into the Studio as its own review project and
    prove the link. A rebuild is delivered as <project>-v<N>-r<renderer version>."""
    r = fp.Run(project); st = r.state()
    v = int(version or st.get("current") or 0)
    rep = fp._report(r, f"{v}-rebuild" if rebuild else v)
    preview = ROOT / rep["preview"] if rep.get("preview") else None
    if not preview or not preview.exists():
        return {"delivered": False, "why": f"v{v} has no preview ({rep.get('status')})"}
    name = review_name(project, f"{v}-r{(rep.get('versions') or {}).get('renderer')}" if rebuild else v)
    if not NAME_OK.match(name):
        return {"delivered": False, "why": f"{name!r} is not a valid Studio project name"}
    dst = REVIEW_ROOT / "projects" / name
    marker = dst / "fieldnotes" / MARKER
    want = _sha_full(preview)
    if dst.exists() and not marker.exists():
        return {"delivered": False, "why": f"projects/{name} already exists and was not created by this tool; not touched"}
    if not (marker.exists() and json.loads(marker.read_text(encoding="utf-8")).get("preview_sha256") == want):
        plan = json.loads((r.fn / f"plan-v{v}.json").read_text(encoding="utf-8"))
        title = json.loads((r.dir / "project.json").read_text(encoding="utf-8")).get("title", project)
        pj = compile_plan(plan, name, f"{title} (Field Notes draft v{v}{', re-rendered' if rebuild else ''})")
        (dst / "fieldnotes").mkdir(parents=True, exist_ok=True)
        (dst / "project.json").write_text(json.dumps(pj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        if not (dst / "fonts").exists():
            shutil.copytree(fp.STYLE_DIR / "fonts", dst / "fonts")
        for f in (f"brief-v{v}.txt", f"plan-v{v}.json", f"report-v{v}.json", f"storyboard-v{v}.md", f"report-v{v}-rebuild.json"):
            if (r.fn / f).exists():
                shutil.copy(r.fn / f, dst / "fieldnotes" / f)
        out = dst / "build" / "out" / f"{name}-9x16" / "renders"
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy(preview, out / f"{name}-9x16.mp4")
        marker.write_text(json.dumps({"project": project, "version": v, "rebuild": rebuild, "source": str(r.dir), "preview": str(preview),
                                      "preview_sha256": want, "draft_only": True,
                                      "delivered": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=1) + "\n", encoding="utf-8")
    ok, proof = prove_link(name, preview)
    return {"delivered": True, "name": name, "url": f"{REVIEW_BASE}/admin/gtm/video-studio/{name}?step=publish",
            "verified": ok, "proof": proof, "copy": str(dst)}


ACCENT_HOLD = 0.7   # seconds a last-word headline accent stays before the next chapter
PACES = {   # narration delivery for an owner-voiced copy: voice speed and the gaps around the words
    "natural": {"speed": None, "lead_in": 0.4, "hold": None, "tail": 1.8},
    "brisk": {"speed": 1.12, "lead_in": 0.25, "hold": 0.25, "tail": 1.5},   # Bob 2026-10-12: brisk, energetic, not instructional
}


def narrated_copy(project, version, voice_file, pace="natural", name=None):
    """A separate narrated Studio project compiled from a saved plan: same scenes and cues, the owner's voice (a voice
    contract JSON with voice_id, model_id and settings) and a delivery pace. The silent versions are never touched.
    Free: nothing is generated; the paid narration needs a person's Approve Script in the Studio."""
    r = fp.Run(project)
    plan = json.loads((r.fn / f"plan-v{version}.json").read_text(encoding="utf-8"))
    contract = json.loads(Path(voice_file).read_text(encoding="utf-8"))
    vc = contract.get("voice", contract)
    pc = PACES[pace]
    name = name or review_name(project, f"{version}-voiced")
    dst = REVIEW_ROOT / "projects" / name
    marker = dst / "fieldnotes" / "narrated-from.json"
    if dst.exists() and not marker.exists():
        raise SystemExit(json.dumps({"ok": False, "error": f"projects/{name} exists and was not made by narrate; not touched"}))
    paid = marker.exists() and (dst / "generated" / "vo").exists() and any((dst / "generated" / "vo").iterdir())
    before = json.loads((dst / "project.json").read_text(encoding="utf-8")) if paid else None
    title = json.loads((r.dir / "project.json").read_text(encoding="utf-8")).get("title", project)
    pj = compile_plan(plan, name, f"{title} (narrated draft v{version}, owner voice, {pace})")
    settings = dict(vc.get("settings") or {})
    if pc["speed"]:
        settings["speed"] = pc["speed"]
    pj["voice"] = {"voice_id": vc["voice_id"], "voice_name": contract.get("voice_name") or vc.get("voice_name") or vc["voice_id"],
                   "model": vc.get("model_id") or vc.get("model"), "settings": settings, "lead_in": pc["lead_in"], "tail": pc["tail"]}
    if pc["hold"] is not None:
        for i, sc in enumerate(pj["scenes"]):
            a, h = sc["line"].get("pause", [0, 0])
            hold = min(h, pc["hold"])
            # a headline accent on the chapter's LAST word needs time to read before the next chapter (2026-10-12:
            # "hit your bill hard" showed for about 0.2 s at the brisk pace)
            last = re.sub(r"[^a-z0-9']", "", sc["line"]["text"].split()[-1].lower())
            accents = [str(l.get("at") or "").split("+")[0].lower() for l in sc["data"]["headline"]["lines"]]
            cue_word = {c["name"]: re.sub(r"[^a-z0-9']", "", str(c.get("at", "")).lower()) for c in sc.get("cues", [])}
            if i < len(pj["scenes"]) - 1 and any(cue_word.get(x, x) == last for x in accents if x):
                hold = max(hold, ACCENT_HOLD)
            sc["line"]["pause"] = [a, hold]
    if before is not None:   # paid narration exists: only pacing may change (same words, voice and settings)
        same = [(x["id"], x["line"]["text"]) for x in before["scenes"]] == [(x["id"], x["line"]["text"]) for x in pj["scenes"]] \
            and {k: before["voice"].get(k) for k in ("voice_id", "model", "settings")} == {k: pj["voice"].get(k) for k in ("voice_id", "model", "settings")}
        if not same:
            raise SystemExit(json.dumps({"ok": False, "error": f"{name} already has paid narration for other words or another voice; make a new copy"}))
    (dst / "fieldnotes").mkdir(parents=True, exist_ok=True)
    (dst / "project.json").write_text(json.dumps(pj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if not (dst / "fonts").exists():
        shutil.copytree(fp.STYLE_DIR / "fonts", dst / "fonts")
    for f in (f"brief-v{version}.txt", f"plan-v{version}.json", f"report-v{version}.json", f"storyboard-v{version}.md"):
        if (r.fn / f).exists():
            shutil.copy(r.fn / f, dst / "fieldnotes" / f)
    marker.write_text(json.dumps({"project": project, "version": version, "voice_file": str(voice_file), "pace": pace,
                                  "created": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=1) + "\n", encoding="utf-8")
    chars = sum(len(sc["line"]["text"]) for sc in pj["scenes"])
    return {"ok": True, "action": "narrate", "name": name, "voice": pj["voice"], "chars": chars,
            "approve_url": f"{REVIEW_BASE}/admin/gtm/video-studio/{name}?step=approve",
            "note": "free; a person approves the script in the Studio before the paid narration build"}


def _result(project, rec, action):
    r = fp.Run(project)
    v = rec.get("version") or r.state().get("current")
    out = {"ok": rec.get("status") == "awaiting-approval", "action": action, "project": project, "version": v,
           "status": rec.get("status"), "draft_only": True}
    plan_f = r.fn / f"plan-v{v}.json"
    plan = json.loads(plan_f.read_text(encoding="utf-8")) if plan_f.exists() else {}
    if rec.get("status") == "awaiting-approval":
        out["storyboard"] = storyboard(plan, v, rec.get("duration"))
        out["preview"] = {"path": str(ROOT / rec["preview"]), "seconds": rec.get("duration"), "sound": "silent (dry timings)"}
        out["review"] = deliver(project, v)
    for k in ("changes", "changes_from", "migrated_from", "brief_unchanged", "first_pass_problems", "plan_problems", "scene_problems"):
        if rec.get(k):
            out[k] = rec[k]
    out["questions"] = plan.get("questions") or []
    out["missing_illustrations"] = plan.get("missing_primitives") or []
    calls = rec.get("model_calls") or []
    out["model_usage"] = {"calls": len(calls), "api_equivalent_usd": round(sum(c.get("equivalent_api_cost_usd") or 0 for c in calls), 3),
                          "billing": "Claude Code login (subscription), not billed per call"} if calls else {"calls": 0}
    out["next"] = ("Watch the preview; reply approve, or describe a change in plain words." if out["ok"] else
                   "Answer the questions in plain words (they become a revision)." if out["questions"] else
                   "Report the problems to the person; nothing was rendered.")
    return out


def status(project):
    r = fp.Run(project); st = r.state()
    c = fp.check(project)
    vs = []
    for e in st["versions"]:
        cv = c["versions"][str(e["version"])]
        rn = REVIEW_ROOT / "projects" / review_name(project, e["version"]) / "fieldnotes" / MARKER
        vs.append({"version": e["version"], "status": e["status"], "revision": e.get("revision"), "compat": cv["status"],
                   "problems": cv["problems"], "review_copy": rn.exists()})
    return {"ok": True, "action": "status", "project": project, "current": st.get("current"), "versions_now": c["current"], "versions": vs}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="fieldnotes_agent")
    ap.add_argument("action", choices=["quote", "new", "revise", "replan", "migrate", "rebuild", "deliver", "status", "narrate"])
    ap.add_argument("project", nargs="?")
    ap.add_argument("extra", nargs="?", help="quote: the project")
    ap.add_argument("--quote", default=None)
    ap.add_argument("--change", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--version", type=int, default=None)
    ap.add_argument("--voice-file", default=None, help="narrate: voice contract JSON (voice_id, model_id, settings)")
    ap.add_argument("--pace", default="natural", choices=list(PACES))
    ap.add_argument("--name", default=None)
    a = ap.parse_args(argv)
    if a.action == "quote":
        print(json.dumps(quote(a.project, a.extra), indent=1)); return
    if not a.project or not NAME_OK.match(a.project):
        raise SystemExit(json.dumps({"ok": False, "error": "a project name: 2 to 40 lower-case letters, digits or dashes"}))
    _need_quote(a.action, a.project, a.quote)
    r = fp.Run(a.project)
    stdout = sys.stdout
    sys.stdout = sys.stderr   # the planner's progress lines go to stderr; stdout carries one JSON object
    try:
        if a.action == "new":
            if r.fn.exists() and r.state()["versions"]:
                raise SystemExit(json.dumps({"ok": False, "error": f"{a.project} already exists; use revise"}))
            if (r.dir / "project.json").exists() and not r.fn.exists():
                raise SystemExit(json.dumps({"ok": False, "error": f"projects/{a.project} is not a field-notes project"}))
            brief = sys.stdin.read()
            if len(brief.split()) < 12:
                raise SystemExit(json.dumps({"ok": False, "error": "the brief (stdin) is empty or too short"}))
            res = _result(a.project, fp.run_version(a.project, brief, title=a.title), "new")
        elif a.action == "revise":
            st = r.state()
            if not st["versions"] or not (a.change or "").strip():
                raise SystemExit(json.dumps({"ok": False, "error": "revise needs an existing project and --change in plain words"}))
            brief = (r.fn / f"brief-v{st['current']}.txt").read_text(encoding="utf-8")
            res = _result(a.project, fp.run_version(a.project, brief, revision=a.change.strip()), "revise")
        elif a.action == "replan":
            st = r.state()
            if not st["versions"]:
                raise SystemExit(json.dumps({"ok": False, "error": "nothing to plan again; use new"}))
            brief = (r.fn / f"brief-v{st['current']}.txt").read_text(encoding="utf-8")
            res = _result(a.project, fp.run_version(a.project, brief), "replan")
        elif a.action == "migrate":
            res = _result(a.project, fp.migrate(a.project, version=a.version), "migrate")
        elif a.action == "rebuild":
            out = fp.rebuild(a.project, version=a.version)
            ok = out.get("status") == "awaiting-approval"
            res = {"ok": ok, "action": "rebuild", "project": a.project, "version": out.get("version"), "status": out.get("status"),
                   "renderer": out["versions"]["renderer"], "model_usage": {"calls": 0},
                   "preview": {"path": str(ROOT / out["preview"]), "seconds": out.get("duration"), "sound": "silent (dry timings)"} if ok else None,
                   "review": deliver(a.project, out.get("version"), rebuild=True) if ok else None,
                   "note": "the saved plan re-rendered with the current renderer and compiler; same story, no model call"}
        elif a.action == "narrate":
            if not a.version or not a.voice_file:
                raise SystemExit(json.dumps({"ok": False, "error": "narrate needs --version and --voice-file"}))
            res = narrated_copy(a.project, a.version, a.voice_file, a.pace, a.name)
        elif a.action == "deliver":
            res = {"ok": True, "action": "deliver", "project": a.project, "review": deliver(a.project, a.version)}
        else:
            res = status(a.project)
    finally:
        sys.stdout = stdout
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
