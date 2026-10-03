"""Checks: the page loads without errors and registers its timeline (before rendering), and on the finished
MP4 a frame every 5 s (blank test + contact sheet) and A/V sync at chosen cues."""
import asyncio, json, subprocess
import numpy as np


def page(p, cut):
    from playwright.async_api import async_playwright
    d = p.out_dir(cut)

    async def run():
        async with async_playwright() as pw:
            b = None
            for opts in ({}, {"channel": "chrome"}, {"channel": "msedge"}):   # Playwright's browser, else an installed one
                try:
                    b = await pw.chromium.launch(**opts); break
                except Exception:  # noqa: BLE001
                    continue
            if b is None:
                raise SystemExit("No browser for page checks. Run `python -m playwright install chromium`.")
            pg = await b.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto((d / "index.html").resolve().as_uri())
            await asyncio.sleep(2)
            ok = await pg.evaluate("!!(window.__timelines && window.__timelines.main)")
            await b.close()
            return ok, errs
    ok, errs = asyncio.run(run())
    print(f"  page {cut}: timeline {'registered' if ok else 'MISSING'}; {('errors: ' + '; '.join(errs)) if errs else 'no errors'}")
    if not ok or errs:
        raise SystemExit(1)


def video(p, cut, cue_ids=()):
    from PIL import Image
    mp4 = p.render_path(cut)
    B = json.loads((p.build / f"beats-{cut}.json").read_text(encoding="utf-8"))
    C = {c["id"]: c["t"] for c in B["cues"]}
    w, h = (192, 108) if cut == "landscape" else (108, 192)
    out = p.build / f"frames-{cut}"; out.mkdir(exist_ok=True)
    thumbs, blank = [], []
    for t in np.arange(0, B["duration"], 5.0):
        f = out / f"f{int(t):03d}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t + 0.01:.2f}", "-i", str(mp4), "-frames:v", "1", str(f)], check=True)
        im = np.asarray(Image.open(f).convert("L"), np.float32)
        if im.std() < 4: blank.append(int(t))
        thumbs.append(Image.open(f).convert("RGB").resize((384, 216) if cut == "landscape" else (216, 384)))
    tw, th = thumbs[0].size; cols = 6 if cut == "landscape" else 9
    sheet = Image.new("RGB", (tw * cols, th * ((len(thumbs) + cols - 1) // cols)), "white")
    for i, t in enumerate(thumbs): sheet.paste(t, ((i % cols) * tw, (i // cols) * th))
    sheet.save(out / "sheet.png")
    print(f"  frames {cut}: {len(thumbs)} checked, blank at {blank or 'none'} -> {out / 'sheet.png'}")
    if not cue_ids: return
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-vn", "-f", "f32le", "-ac", "1", "-ar", "48000", "-"], capture_output=True, check=True).stdout
    aud = np.frombuffer(raw, np.float32)
    for cid in cue_ids:
        t = C[cid]; t0 = t - 0.35
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-i", str(mp4), "-frames:v", "22", "-vf", f"fps=30,scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
        dd = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2)); vt = t0 + (int(np.argmax(dd)) + 1) / 30
        seg = aud[int((t - .35) * 48000):int((t + .35) * 48000)]; hop = 240
        e = np.array([np.sqrt(np.mean(seg[i:i + hop] ** 2)) + 1e-6 for i in range(0, len(seg) - hop, hop)])
        at = t - .35 + (int(np.argmax(20 * np.log10(e[1:] / e[:-1]))) + 1) * hop / 48000
        print(f"  sync {cid}: cue {t:.3f} | picture {vt:.3f} | audio {at:.3f} | audio-video {1000 * (at - vt):+.0f} ms (the metric can latch onto a nearby word or wipe)")
