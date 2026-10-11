# Owner Explainer — Field Notes v1 (`owner-explainer-field-notes-v1`)

EXPERIMENTAL. Kept apart from the weekly reel formats (`projects/nanoflow`, `nanoflow-reel`, `nanoflow-humour`); no
Studio default, template list or platform route points here.

## What is here (2026-10-11)

| File | What it is | Working? |
|---|---|---|
| `template.json` | inputs to fill, sampled palette, fonts (substitutes), layout tokens, motion rules | specification |
| `storyboard.json`, `STORYBOARD.md` | three-beat first test (13.5 s), placeholder slots only | specification |
| `STYLE.md` | reference-grounded style sheet | specification |
| `preview/index.html` + `render.py` | static END-STATE still renderer driven by the JSON files (editable text, palette, layout; SVG diagrams; headline auto-fit) | working, stills only |
| `stills/beat1..3.png` | 1080x1920 keyframes from the preview | produced |
| `fonts/` | Inter Tight, Inter, Instrument Serif (OFL) | used by the preview |

Animation (2026-10-11): `engine/fieldnotes.js` renders scenes of type `fieldnotes` from scene data (objects and timed
actions); see `FIELDNOTES.md` for the data, the object and action types, how to start a new video and what is still
manual. First test: `projects/fieldnotes-tn-cool-before-peak` (silent, provisional timings). The prompt-to-scene-data
step is manual for now, so this is a working renderer, not an automatic prompt-to-animation workflow.

Re-render the stills after editing the JSON (free, local Chromium):

    /home/adam/video-studio/.venv/bin/python templates-experimental/owner-explainer-field-notes-v1/preview/render.py
