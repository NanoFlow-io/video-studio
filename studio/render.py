"""Render a cut folder with the pinned HyperFrames (installed by `npm install`), then check it decodes."""
import json, os, platform, subprocess, sys
from pathlib import Path
from .common import ROOT


def _hyperframes_bin():
    pkg = ROOT / "node_modules" / "hyperframes" / "package.json"
    if not pkg.exists():
        sys.exit("HyperFrames is not installed. Run `npm install` in the repo root.")
    b = json.loads(pkg.read_text(encoding="utf-8")).get("bin")
    rel = b if isinstance(b, str) else (b.get("hyperframes") or next(iter(b.values())))
    return str(pkg.parent / rel)


def _env():
    env = {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
    # Windows: desktop chrome.exe opens a window on `--version`, which HyperFrames uses as a health check.
    # Prefer Playwright's headless shell when it is installed (python -m playwright install chromium-headless-shell).
    if platform.system() == "Windows" and not env.get("HYPERFRAMES_BROWSER_PATH"):
        pw = Path(env.get("LOCALAPPDATA", "")) / "ms-playwright"
        for d in sorted(pw.glob("chromium_headless_shell-*"), reverse=True):
            exe = d / "chrome-headless-shell-win64" / "chrome-headless-shell.exe"
            if exe.exists():
                env["HYPERFRAMES_BROWSER_PATH"] = str(exe).replace("\\", "/"); break
    return env


def hyperframes(folder, *args, check=True):
    return subprocess.run(["node", _hyperframes_bin(), *args], cwd=folder, env=_env(), input="\n", text=True, check=check)


def render(p, cut, quality="looks"):
    d = p.out_dir(cut); out = p.render_path(cut); out.parent.mkdir(parents=True, exist_ok=True)
    hyperframes(d, "render", "-o", str(out.relative_to(d)), "--fps", "30", "--quality", quality)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", str(out)], capture_output=True, text=True)
    info = json.loads(probe.stdout or "{}")
    dec = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "null", "-"], capture_output=True, text=True)
    streams = [s["codec_type"] for s in info.get("streams", [])]
    print(f"  render {cut}: {out} | {info.get('format', {}).get('duration', '?')} s | streams {streams} | {'decodes cleanly' if not dec.stderr.strip() else 'DECODE ERRORS'}")
    return out
