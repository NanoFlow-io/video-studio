# Field-notes scene renderer (experimental, 2026-10-11)

`owner-explainer-field-notes-v1`, section 3 of the owner-explainer reel. The renderer is `engine/fieldnotes.js`; a
scene opts in with `"type": "fieldnotes"`. `studio/cuts.py` splices the file into a page only when a project has such a
scene, so every other project's page is byte-identical (checked against all 16 live and template projects). Vertical
1080x1920 only. Worked example: `projects/fieldnotes-tn-cool-before-peak/project.json`.

## What is automatic and what is not

| Step | Status |
|---|---|
| Scene data -> animated page -> MP4 (`studio.py build`, `render`) | **working** |
| Timings from narration words (cues), so real audio re-times everything | **working** (`build` with real voice) |
| Silent provisional timings | **working** (`build --dry-timings`, 2.6 words/s) |
| Validation of scene data before anything is built | **working** (`beats.validate`) |
| Natural-language prompt -> scene data | **manual for now** (a person or Nano writes the JSON below) |

It is a working renderer, not a prompt-to-animation workflow: nothing turns a brief into objects, positions and
actions yet. The planning step below is how that JSON is written today.

## From a prompt to scene data (manual planning step)

1. **Facts first.** Fill the template inputs (business, customer, problem, verified cause, solution, realistic outcome).
   Nothing in a scene may go beyond them: no invented rates, times, statistics or guarantees.
2. **Narration split.** One chapter per beat; each scene's `line.text` is its part of the owner's script. `line.pause`
   `[0, s]` holds a beat after its words (vertical cut uses the second number).
3. **Cue words.** For each moment the picture must hit a word, add a cue: `{ "name": "peak", "at": "peak", "sfx": null }`
   (`at` is a word of the line, matched from its start, or `start` / `end` / `cut` with +/- seconds).
4. **Cast.** Pick objects (kinds below) once; give each an `id` and a position. Reuse the same ids in later chapters:
   they carry over in their final state.
5. **Actions.** One action per visible change: what (`do`), on what (`target`), when (`at`: seconds after the scene
   starts, or a cue name with an optional offset such as `"before+0.3"`). Build up, act, annotate, then resolve.
6. **Check** with `python studio.py build <project> --dry-timings`, look at frames, then render.

## Scene data

```jsonc
{ "id": "F02", "type": "fieldnotes",
  "line": { "text": "Cool your home before peak rates,", "pause": [0, 0.6] },
  "cues": [ { "name": "before", "at": "before", "sfx": null } ],
  "data": {
    "header": { "brand": "TRUE NORTH", "label": "FIELD NOTES", "chapter": "THE SHIFT", "index": 2, "total": 3 },
    "kicker": "BEFORE THE PEAK",
    "headline": { "lines": [ { "text": "Cool the house" }, { "text": "earlier", "em": "blue", "at": "before" } ],
                  "at": 0.15, "size": 112, "max": 900 },
    "transition": "bands",            // optional broad sage / ink / ochre wipe into this chapter
    "continue": true,                 // default: objects from the previous fieldnotes scene carry over
    "objects": [ ... ], "actions": [ ... ] } }
```

Headline: up to 3 lines, rising line by line; `em` = `ochre` (white on ochre box), `blue` (underline), `sage` (underlay)
or `italic` (serif accent), wiped in at the line's `at`. Long lines shrink together to fit `max` (down to 70%). The
headline and kicker leave just before the next fieldnotes chapter.

## Objects (kinds) and their actions

Every object takes `draw` (outlines draw on, fills tint in), `show` (fade in) and `hide`. Callouts, notes and cards
stay in their own scene unless `"carry": true`; everything else carries on.

| Kind | Fields | Extra actions |
|---|---|---|
| `house` | x, y (ground line), scale | `fill` { level 0..1, dur }: blue cooling fills the house from the floor |
| `ac_unit` | x, y (ground), scale | `run` { speed rev/s, 0 = off }: fan spins, air lines fade with speed |
| `timeline` | x, y (axis), w, left, right, `bands` [{id, from, to, label}], `segs` [{id, from, to, level}], `playhead` {pos} | parts `timeline.<id>`: `show` / `hide`; `seg` { from?, to?, level?, dur } moves or resizes a segment; `timeline.playhead`: `playhead` { from?, to, dur } |
| `gauge` | x, y, w, label, level, low, high, color | `set` { level, dur } |
| `thermostat` | x, y, r, angle | `turn` { by degrees, dur }: needle turns, up chevron appears |
| `arrow` | points [[x,y], ...] (2 = straight, 3 = curve), color, width, dash, head | `flow` { dur }: dashes travel along a dashed arrow |
| `callout` | x, y (anchor), lx?, ly, text, style `tag` / `label` / `note` | (leader draws, then the label) |
| `note` | x, y, text, align, size, color | |
| `card` | x, y, w, text, check | (slides up; the check-list card with the ochre offset) |

Positions and fractions are plain numbers in the 1080x1920 frame; timeline `from` / `to` / `pos` are fractions of its
width. Colours are palette names from `project.json` `palette` (ochre, sage, blue, blueStroke, ink...) or hex.

## Inputs for a new video

Copy `projects/fieldnotes-tn-cool-before-peak/`, then edit `project.json`: `voice` (the owner's narrator), each
scene's `line.text` and `cues`, and the `data` blocks. Keep `fonts/` (Inter Tight, Inter, Instrument Serif, OFL).
Preview free with `--dry-timings`; once the script is approved, `build` (paid narration) re-times the same actions to
the real words, then `render` (local) or `render-remote`.

## Remaining gaps

- Prompt to scene data is manual (above). An agent step could draft the JSON from the template inputs; not built.
- Seven drawable kinds today (house, AC unit, timeline, gauge, thermostat, arrow, callout/note/card). Other stories need
  new kinds (map, network, cutaway, bar list), each a small function in `engine/fieldnotes.js`.
- No dark or olive full-screen chapter card yet (only the bands wipe).
- Not wired into the platform (agent API, wizard, Studio UI); local projects and the CLI only.
- No owner footage, avatar or CTA sections; this renders section 3 only.
