"""Image (mascot poses) and video (transition clips) providers.

google      GEMINI_API_KEY. Poses: Gemini image model ("Nano Banana", reference image + prompt; no alpha, so the
            background is removed locally with rembg). Transitions: Veo (image-to-video, polled, downloaded).
higgsfield  Official Higgsfield CLI (`hf`), signed in once with `hf auth login` (browser). Higgsfield's
            key-based REST API only takes images by public URL and has no upload endpoint, so a local mascot
            file has to go through the CLI, which uploads it. Poses: gpt_image_2_5 with a transparent
            background. Transitions: Kling via the CLI.
"""
import base64, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
from .common import ROOT, http, download

G_API = "https://generativelanguage.googleapis.com/v1beta"


class Google:
    def __init__(self, env):
        self.key = env.get("GEMINI_API_KEY") or sys.exit("GEMINI_API_KEY is missing (python studio.py setup)")
        self.h = {"x-goog-api-key": self.key}
        self.image_model = env.get("GOOGLE_IMAGE_MODEL", "gemini-3.1-flash-image")
        self.video_model = env.get("GOOGLE_VIDEO_MODEL", "veo-3.1-fast-generate-preview")

    def check(self):
        d = http("GET", f"{G_API}/models?pageSize=200", self.h)
        names = [m["name"].split("/")[-1] for m in d.get("models", [])]
        return f"Gemini OK: image model {self.image_model} {'available' if self.image_model in names else 'NOT listed'}, video model {self.video_model} {'available' if self.video_model in names else 'NOT listed'}"

    def image(self, ref_png, prompt, dst, aspect="3:4"):
        body = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(Path(ref_png).read_bytes()).decode()}}]}],
                "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect, "imageSize": "2K"}}}
        d = http("POST", f"{G_API}/models/{self.image_model}:generateContent", self.h, body, timeout=300)
        for part in d.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            inl = part.get("inlineData") or part.get("inline_data")
            if inl and inl.get("data"):
                Path(dst).write_bytes(base64.b64decode(inl["data"])); return dst
        raise RuntimeError("Gemini returned no image: " + json.dumps(d)[:400])

    def video(self, start_png, prompt, dst, aspect="16:9", seconds=4):
        body = {"instances": [{"prompt": prompt, "image": {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(Path(start_png).read_bytes()).decode()}}}],
                "parameters": {"aspectRatio": aspect, "durationSeconds": str(seconds), "resolution": "1080p" if aspect == "16:9" else "720p"}}
        op = http("POST", f"{G_API}/models/{self.video_model}:predictLongRunning", self.h, body)
        name = op["name"]
        for _ in range(120):
            time.sleep(10)
            op = http("GET", f"{G_API}/{name}", self.h)
            if op.get("done"): break
        if not op.get("done"): raise RuntimeError("Veo timed out: " + name)
        if op.get("error"): raise RuntimeError("Veo error: " + json.dumps(op["error"]))
        uri = op["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
        return download(uri, dst, self.h)


HF_VERSION = "1.1.26"


def hf_bin():
    for name in ("hf", "higgsfield"):
        p = shutil.which(name)
        if p: return p
    local = ROOT / "tools" / "higgsfield" / ("hf.exe" if os.name == "nt" else "hf")
    return str(local) if local.exists() else None


def install_hf():
    """Download the pinned Higgsfield CLI release into tools/higgsfield/ (no admin rights needed)."""
    import platform, tarfile, io
    osn = {"Windows": "windows", "Darwin": "darwin", "Linux": "linux"}[platform.system()]
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "amd64"
    url = f"https://github.com/higgsfield-ai/cli/releases/download/v{HF_VERSION}/hf_{HF_VERSION}_{osn}_{arch}.tar.gz"
    d = ROOT / "tools" / "higgsfield"; d.mkdir(parents=True, exist_ok=True)
    tmp = d / "hf.tar.gz"; download(url, tmp)
    with tarfile.open(tmp) as t:
        t.extractall(d)
    tmp.unlink()
    exe = d / ("hf.exe" if osn == "windows" else "hf")
    if osn != "windows": exe.chmod(0o755)
    return str(exe)


class Higgsfield:
    def __init__(self, env):
        self.bin = hf_bin() or sys.exit("Higgsfield CLI not found. Run `python studio.py setup` (it installs it into tools/higgsfield).")
        self.env = {**os.environ, "HIGGSFIELD_DISABLE_TELEMETRY": "1"}

    def run(self, *args, timeout=1800):
        r = subprocess.run([self.bin, *args, "--json"], capture_output=True, text=True, timeout=timeout, env=self.env)
        if r.returncode:
            raise RuntimeError(f"hf {' '.join(args[:3])} failed: {(r.stderr or r.stdout)[-600:]}")
        return r.stdout

    def check(self):
        self.run("workspace", "list", timeout=60)   # fails with "Not authenticated" if the login has expired
        return "Higgsfield OK: CLI signed in (" + self.bin + ")"

    def _result_url(self, out, exts):
        urls = re.findall(r"https://[^\s\"']+", out)
        for u in urls:
            if any(u.split("?")[0].lower().endswith(e) for e in exts): return u
        if urls: return urls[-1]
        raise RuntimeError("no result URL in Higgsfield output: " + out[-400:])

    def image(self, ref_png, prompt, dst, aspect="3:4"):
        out = self.run("generate", "create", "gpt_image_2_5", "--prompt", prompt, "--image-references", str(ref_png),
                       "--aspect_ratio", aspect, "--quality", "high", "--resolution", "2k", "--background", "transparent", "--wait", "--wait-timeout", "15m")
        return download(self._result_url(out, (".png", ".webp", ".jpg", ".jpeg")), dst)

    def video(self, start_png, prompt, dst, aspect="16:9", seconds=5):
        out = self.run("generate", "create", "kling3_0", "--prompt", prompt, "--start-image", str(start_png),
                       "--duration", str(max(5, int(seconds))), "--mode", "pro", "--sound", "off", "--wait", "--wait-timeout", "30m")
        return download(self._result_url(out, (".mp4", ".mov", ".webm")), dst)


def get(env):
    name = (env.get("MEDIA_PROVIDER") or "").lower()
    if name == "google": return Google(env)
    if name == "higgsfield": return Higgsfield(env)
    sys.exit("MEDIA_PROVIDER is not set to google or higgsfield. Run `python studio.py setup`.")
