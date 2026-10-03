"""Mascot poses (transparent stills) and transition clips, from the configured provider."""
import json, subprocess, tempfile
from pathlib import Path
from PIL import Image
from .common import ffmpeg, CUTS
from . import providers


def _has_alpha(img):
    if img.mode != "RGBA": return False
    a = img.getchannel("A")
    return sum(a.histogram()[:16]) > a.width * a.height * 0.05   # at least 5% of pixels see-through


def _cutout(img):
    try:
        from rembg import remove
    except ImportError:
        raise SystemExit("This pose came back without a transparent background. Install the cut-out tool with "
                         "`pip install \"rembg[cpu]\"` (downloads a ~170 MB model on first use) and run again.")
    return remove(img)


def _prompt(p, pose_text):
    m = p.data["mascot"]
    return (f"Exactly the same character as the reference image: {m.get('description') or 'the character in the reference image'}. "
            "Keep proportions, colours, materials and face identical. "
            f"Pose: {pose_text}. Full body, centred, soft studio lighting, plain transparent or pure white background, "
            "no ground shadow, no text, no logos.")


def poses(p, env, only=(), force=False, cutout=False):
    prov = providers.get(env)
    ref = p.path(p.data["mascot"]["reference"])
    if not ref.exists():
        raise SystemExit(f"Mascot reference image not found: {ref}")
    out = p.dir / "poses"; src = out / "src"; src.mkdir(parents=True, exist_ok=True)
    log_p = src / "provenance.json"
    log = json.loads(log_p.read_text(encoding="utf-8")) if log_p.exists() else {}
    ref_png = src / "_reference.png"
    Image.open(ref).convert("RGBA").save(ref_png)
    for name, text in p.data["poses"].items():
        if only and name not in only: continue
        dst = out / f"{name}.webp"
        if dst.exists() and not force: continue
        raw = src / f"{name}.png"
        prov.image(ref_png, _prompt(p, text), raw)
        img = Image.open(raw).convert("RGBA")
        if cutout or not _has_alpha(img):
            img = _cutout(img)
        w, h = img.size; target_h = 1400
        img = img.resize((round(w * target_h / h), target_h), Image.LANCZOS)
        canvas = Image.new("RGBA", (round(target_h * p.data.get("pose_aspect", 0.7466)), target_h), (0, 0, 0, 0))
        canvas.paste(img, ((canvas.width - img.width) // 2, 0), img)   # keep the pose canvas consistent
        canvas.save(dst, "WEBP", quality=90)
        log[name] = {"provider": env.get("MEDIA_PROVIDER"), "prompt": _prompt(p, text)}
        log_p.write_text(json.dumps(log, indent=1), encoding="utf-8")
        print(f"  pose {name}: {dst}")


def transitions(p, env, only=(), force=False):
    prov = providers.get(env)
    d = p.gen / "transitions"; d.mkdir(exist_ok=True)
    for t in p.data.get("transitions", []):
        if only and t["id"] not in only: continue
        if not t.get("enabled", True) and not only: continue
        for cut, (w, h, tag) in CUTS.items():
            dst = d / f"{t['id']}-{tag}.mp4"
            if dst.exists() and not force: continue
            # start frame: the pose on the scene background colour, at the cut's aspect
            bgc = (p.data.get("solids") or {}).get(t.get("bg", "paper"), p.data["palette"]["paper"])
            frame = Image.new("RGBA", (w, h), bgc)
            pose = Image.open(p.dir / "poses" / f"{t['pose']}.webp").convert("RGBA")
            ph = int(h * 0.7); pose = pose.resize((int(pose.width * ph / pose.height), ph), Image.LANCZOS)
            frame.paste(pose, ((w - pose.width) // 2, h - ph - int(h * 0.08)), pose)
            with tempfile.TemporaryDirectory() as tmp:
                start = Path(tmp) / "start.png"; frame.convert("RGB").save(start)
                raw = Path(tmp) / "raw.mp4"
                prov.video(start, t["prompt"], raw, "16:9" if cut == "landscape" else "9:16")
                # keep the requested slice, fitted to the cut, silent (the mix owns the audio)
                ffmpeg("-ss", t.get("from", 0.3), "-i", raw, "-t", t.get("seconds", 1.2),
                       "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", dst)
            print(f"  transition {t['id']} {cut}: {dst}")
