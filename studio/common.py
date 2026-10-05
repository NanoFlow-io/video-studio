"""Shared paths, .env loading, project loading and small helpers."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
SR = 48000
CUTS = {"landscape": (1920, 1080, "16x9"), "vertical": (1080, 1920, "9x16")}


def load_env():
    """Read KEY=VALUE lines from .env into a dict (process env wins, so CI can inject secrets)."""
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    for k in list(env):
        if os.environ.get(k):
            env[k] = os.environ[k]
    for k in ("ELEVENLABS_API_KEY", "GEMINI_API_KEY", "MEDIA_PROVIDER"):
        if os.environ.get(k) and k not in env:
            env[k] = os.environ[k]
    return env


def require(env, key, why):
    if not env.get(key):
        sys.exit(f"Missing {key} ({why}). Run `python studio.py setup` or add it to .env")
    return env[key]


def write_env(values):
    """Merge values into .env, keeping other lines and comments."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    seen = set()
    for i, line in enumerate(lines):
        m = re.match(r"\s*([A-Z0-9_]+)\s*=", line)
        if m and m.group(1) in values:
            lines[i] = f"{m.group(1)}={values[m.group(1)]}"; seen.add(m.group(1))
    lines += [f"{k}={v}" for k, v in values.items() if k not in seen]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(ENV_FILE, 0o600)
    except OSError:
        pass


class Project:
    def __init__(self, name):
        self.dir = ROOT / "projects" / name
        if not (self.dir / "project.json").exists():
            sys.exit(f"No project at {self.dir}. Create one with `python studio.py new {name}`")
        self.name = name
        self.data = json.loads((self.dir / "project.json").read_text(encoding="utf-8"))
        self.gen = self.dir / "generated"      # paid media (voice, sfx, music, clips); reused unless regenerated
        self.build = self.dir / "build"        # derived files, safe to delete
        for d in (self.gen, self.build):
            d.mkdir(exist_ok=True)

    @property
    def vertical_only(self):
        """Entertainment-style projects (the Brand Kit reel) have only the 9:16 cut."""
        return self.data.get("style") == "entertainment"

    def path(self, rel):
        return self.dir / rel

    def scenes(self, cut=None):
        sc = self.data["scenes"]
        return [s for s in sc if cut != "vertical" or s["line"].get("vertical", True)]

    def out_dir(self, cut):
        return self.build / "out" / f"{self.name}-{CUTS[cut][2]}"

    def render_path(self, cut):
        d = self.out_dir(cut)
        return d / "renders" / f"{d.name}.mp4"


def ffmpeg(*args, capture=False):
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is not on PATH. Install it (https://ffmpeg.org) and try again.")
    return subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True, capture_output=capture)


def mean_db(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else -99.0


def http(method, url, headers=None, body=None, timeout=180, raw=False):
    """Tiny JSON-over-HTTPS helper (stdlib only)."""
    import urllib.request, urllib.error
    data = None
    h = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode(); h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read()
            return b if raw else json.loads(b or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read()[:600].decode("utf-8", "replace")
        raise RuntimeError(f"{method} {url.split('?')[0]} -> HTTP {e.code}: {detail}") from None


def download(url, dst, headers=None):
    import urllib.request
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=600) as r:
        Path(dst).write_bytes(r.read())
    return dst
