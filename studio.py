#!/usr/bin/env python3
"""Video Studio: mascot explainer videos from a project.json, a mascot image and an ElevenLabs key.

  python studio.py setup                      keys, media provider, tool checks (run once)
  python studio.py check                      test the saved keys / sign-in
  python studio.py new <name> --mascot m.png --logo logo.png [--mark mark.png] [--describe "..."]
  python studio.py voices                     list ElevenLabs voices (to pick voice.voice_id)
  python studio.py poses <name>               make the mascot poses listed in project.json
  python studio.py transitions <name>         make the transition clips listed in project.json (optional)
  python studio.py build <name>               voiceover, sound, music, beats, mix, pages (both cuts)
  python studio.py render <name>              render MP4s (after build)
  python studio.py all <name>                 build + checks + render + checks
Common flags: --cut landscape|vertical|both, --force (rebuy generated media), --only a,b,
  --offline (no API calls), --dry-timings (silent layout preview with synthetic timings, no API calls)
"""
import argparse, getpass, json, os, shutil, subprocess, sys
from pathlib import Path

if sys.version_info < (3, 9):
    sys.exit("Python 3.9 or newer is needed.")
from studio.common import ROOT, Project, load_env, write_env, require  # noqa: E402


def cuts(a, p=None):
    want = ["landscape", "vertical"] if a.cut == "both" else [a.cut]
    if p is not None and p.vertical_only and "landscape" in want:
        print(f"  landscape: skipped ({p.name} is entertainment style, which has the vertical cut only)")
        want = [c for c in want if c != "landscape"]
    return want


def dry(a):
    """--dry-timings (or STUDIO_DRY_TIMINGS=1): synthetic word times and silent audio, for layout previews only."""
    return bool(getattr(a, "dry_timings", False) or os.environ.get("STUDIO_DRY_TIMINGS", "") not in ("", "0"))


def cmd_setup(a):
    print("Video Studio setup. Keys are saved to .env in this folder (git-ignored), never to project files.\n")
    env = load_env(); new = {}
    problems = [t for t in ("node", "npm", "ffmpeg", "ffprobe") if not shutil.which(t)]
    if problems:
        print("Missing tools on PATH: " + ", ".join(problems) + " (install them, then re-run setup)\n")
    if not (ROOT / "node_modules" / "hyperframes").exists() and shutil.which("npm"):
        print("Installing the pinned renderer (npm install)...")
        subprocess.run(["npm", "install", "--no-fund", "--no-audit"], cwd=ROOT, check=True, shell=(sys.platform == "win32"))
    k = getpass.getpass(f"ElevenLabs API key{' [keep current]' if env.get('ELEVENLABS_API_KEY') else ''}: ").strip()
    if k: new["ELEVENLABS_API_KEY"] = k
    cur = env.get("MEDIA_PROVIDER", "")
    choice = input(f"Image/video provider for poses and transitions: google (Gemini + Veo, API key) or higgsfield (CLI sign-in) [{cur or 'google'}]: ").strip().lower() or cur or "google"
    if choice not in ("google", "higgsfield"):
        sys.exit("Please answer google or higgsfield.")
    new["MEDIA_PROVIDER"] = choice
    if choice == "google":
        g = getpass.getpass(f"Gemini API key (Google AI Studio){' [keep current]' if env.get('GEMINI_API_KEY') else ''}: ").strip()
        if g: new["GEMINI_API_KEY"] = g
    write_env(new)
    if choice == "higgsfield":
        from studio import providers
        exe = providers.hf_bin() or providers.install_hf()
        print(f"Higgsfield CLI: {exe}\nSigning in opens your browser (Higgsfield's API keys can't upload a local mascot image, so the CLI is used).")
        subprocess.run([exe, "auth", "login"])
        print("If you have more than one workspace, pick one with:  " + exe + " workspace set <workspace_id>")
    print("\nSaved. Checking...")
    cmd_check(a)
    print("\nPlaywright (page checks) needs a browser once:  python -m playwright install chromium" +
          ("  (on Windows also: chromium-headless-shell)" if sys.platform == "win32" else ""))


def cmd_check(a):
    env = load_env(); ok = True
    from studio.elevenlabs import ElevenLabs
    from studio import providers
    for label, fn in [("ElevenLabs", lambda: ElevenLabs(require(env, "ELEVENLABS_API_KEY", "voice, sound and music")).check()),
                      ("Media provider", lambda: providers.get(env).check())]:
        try:
            print("  " + fn())
        except SystemExit as e:
            ok = False; print(f"  {label}: {e}")
        except Exception as e:  # noqa: BLE001
            ok = False; print(f"  {label}: FAILED {e}")
    for t in ("node", "ffmpeg", "ffprobe"):
        print(f"  {t}: {'found' if shutil.which(t) else 'MISSING'}")
    print(f"  renderer: {'installed' if (ROOT / 'node_modules' / 'hyperframes').exists() else 'MISSING (npm install)'}")
    if not ok: sys.exit(1)


def cmd_new(a):
    dst = ROOT / "projects" / a.name
    if dst.exists(): sys.exit(f"{dst} already exists")
    tpl = json.loads((ROOT / "projects" / "nanoflow" / "project.json").read_text(encoding="utf-8"))
    for sub in ("mascot", "brand", "poses", "images"):
        (dst / sub).mkdir(parents=True, exist_ok=True)
    m = Path(a.mascot); shutil.copy(m, dst / "mascot" / ("reference" + m.suffix.lower()))
    tpl["mascot"] = {"reference": "mascot/reference" + m.suffix.lower(), "description": a.describe or ""}
    lg = Path(a.logo); shutil.copy(lg, dst / "brand" / ("logo" + lg.suffix.lower()))
    mk = Path(a.mark or a.logo); shutil.copy(mk, dst / "brand" / ("mark" + mk.suffix.lower()))
    tpl["brand"] = {"logo": "brand/logo" + lg.suffix.lower(), "mark": "brand/mark" + mk.suffix.lower()}
    tpl["name"] = a.name
    for im in tpl["scenes"]:
        if im["type"] == "content_reels":
            for f in im["data"].get("images", []):
                src = ROOT / "projects" / "nanoflow" / f
                (dst / f).parent.mkdir(parents=True, exist_ok=True); shutil.copy(src, dst / f)
    tpl["_todo"] = ("Copied from the NanoFlow example. Rewrite each scene's line.text and data for your product, "
                    "set palette/backgrounds, pick voice.voice_id (python studio.py voices), then run poses and build.")
    (dst / "project.json").write_text(json.dumps(tpl, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Created {dst}. Next: edit project.json, then `python studio.py poses {a.name}`")


def cmd_voices(a):
    from studio.elevenlabs import ElevenLabs
    for vid, name, cat in ElevenLabs(require(load_env(), "ELEVENLABS_API_KEY", "voices")).voices():
        print(f"  {vid}  {name}  ({cat})")


def cmd_poses(a):
    from studio import media
    media.poses(Project(a.name), load_env(), only=set(filter(None, a.only.split(","))), force=a.force, cutout=a.cutout)


def cmd_transitions(a):
    from studio import media
    media.transitions(Project(a.name), load_env(), only=set(filter(None, a.only.split(","))), force=a.force)


def cmd_build(a):
    from studio import vo, audio, beats, mix, cuts as cutmod
    p, env, dr = Project(a.name), load_env(), dry(a)
    missing = [n for n in {s["pose"] for s in p.data["scenes"]} if not (p.dir / "poses" / f"{n}.webp").exists()]
    if missing: sys.exit(f"Missing poses: {', '.join(sorted(missing))}. Run `python studio.py poses {a.name}` first.")
    problems = beats.validate(p)   # before anything is bought
    if problems: sys.exit("project.json problems:\n  " + "\n  ".join(problems))
    if dr:
        print("DRY TIMINGS: synthetic word times (%.1f words/s) and silent audio, no API calls. Layout preview only." % vo.DRY_WPS)
    elif not a.offline:
        require(env, "ELEVENLABS_API_KEY", "voice, sound and music")
        print("voiceover"); vo.generate(p, env, force=a.force and not a.only)   # --only targets sounds/music, not the voice
        print("sound and music"); audio.generate(p, env, force=set(filter(None, a.only.split(","))) if a.force else ())
    for c in cuts(a, p):
        vo.assemble(p, c, dry=dr); beats.build(p, c); mix.mix(p, c, dry=dr); cutmod.build(p, c)


def cmd_render(a):
    from studio import render, verify
    p = Project(a.name)
    for c in cuts(a, p):
        bj = p.build / f"beats-{c}.json"
        if bj.exists() and json.loads(bj.read_text(encoding="utf-8")).get("dry"):
            print(f"  {c}: built with --dry-timings (synthetic timings, silent). This render is a layout preview, not a deliverable.")
        verify.page(p, c); render.render(p, c, a.quality); verify.video(p, c)


def cmd_verify(a):
    from studio import verify
    p = Project(a.name)
    for c in cuts(a, p):
        verify.page(p, c)
        if p.render_path(c).exists(): verify.video(p, c, [x for x in a.cues.split(",") if x])


def cmd_all(a):
    cmd_build(a); cmd_render(a)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("setup"); sp.add_parser("check"); sp.add_parser("voices")
    n = sp.add_parser("new"); n.add_argument("name"); n.add_argument("--mascot", required=True); n.add_argument("--logo", required=True)
    n.add_argument("--mark"); n.add_argument("--describe", help="one line describing the mascot's look (helps keep poses on-model)")
    for name in ("poses", "transitions", "build", "render", "verify", "all"):
        s = sp.add_parser(name); s.add_argument("name")
        s.add_argument("--cut", default="both", choices=["landscape", "vertical", "both"])
        s.add_argument("--force", action="store_true", help="regenerate paid media instead of reusing it")
        s.add_argument("--only", default="", help="comma list of pose / transition / sound names")
        s.add_argument("--cutout", action="store_true", help="poses: always run local background removal")
        s.add_argument("--offline", action="store_true", help="build: reuse generated media only, no API calls")
        s.add_argument("--dry-timings", action="store_true", help="build: fake word timings (2.6 words/s) and silent audio, "
                       "no API calls; layout preview only (also STUDIO_DRY_TIMINGS=1)")
        s.add_argument("--quality", default="looks", help="render quality: draft, looks, delivery")
        s.add_argument("--cues", default="", help="verify: cue ids to sync-check, e.g. S02.missed,S14.l1")
    a = ap.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
