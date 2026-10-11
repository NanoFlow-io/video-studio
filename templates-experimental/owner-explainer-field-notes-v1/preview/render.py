"""Still previews for owner-explainer-field-notes-v1: inlines template.json + storyboard.json into data.js, then
screenshots the END state of each beat at 1080x1920 with local headless Chromium (no network, no cost).
Run:  /home/adam/video-studio/.venv/bin/python preview/render.py   (from the template folder or anywhere)"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "stills"


def main():
    t = json.loads((ROOT / "template.json").read_text(encoding="utf-8"))
    s = json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))
    (HERE / "data.js").write_text(f"window.TEMPLATE={json.dumps(t, ensure_ascii=False)};\nwindow.STORYBOARD={json.dumps(s, ensure_ascii=False)};\n", encoding="utf-8")
    OUT.mkdir(exist_ok=True)
    beats = [int(a) for a in sys.argv[1:]] or [1, 2, 3]
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        for n in beats:
            pg.goto((HERE / "index.html").as_uri() + f"?beat={n}")
            pg.wait_for_selector("body[data-ready='1']", timeout=15000)
            pg.wait_for_timeout(150)
            pg.locator("#frame").screenshot(path=str(OUT / f"beat{n}.png"))
            print(f"stills/beat{n}.png")
        b.close()
    if errors:
        raise SystemExit("page errors: " + "; ".join(errors))


if __name__ == "__main__":
    main()
