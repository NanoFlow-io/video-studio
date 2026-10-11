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

It is NOT a functioning animation template: there is no motion, narration sync or video output yet.

Re-render the stills after editing the JSON (free, local Chromium):

    /home/adam/video-studio/.venv/bin/python templates-experimental/owner-explainer-field-notes-v1/preview/render.py

## Gap for the animation test

The Studio engine (`engine/scenes.js`) has no scene type for this look (its types are the Nano reel and footage
layouts). Proposed, pending approval: an opt-in engine module `engine/fieldnotes.js`, spliced in by `studio/cuts.py`
only for projects whose scenes use `type: "fieldnotes"` (the same gating as `engine/humour.js`, so every other project's
page stays byte-identical). It would port this preview's SVG parts and drive the motion rules with GSAP from the
project's word cues, so the owner's narration, the cue timings, the mix, the remote render and provenance all stay the
existing Studio pipeline. Rendering is free (plex-server). The only possible paid item is the narration if it is
synthesised rather than the owner's recording: about 1 ElevenLabs credit per character (about 200 credits for a 13.5 s
test), quoted before any run.
