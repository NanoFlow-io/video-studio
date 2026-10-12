# Field-notes scene renderer (experimental, 2026-10-11)

`owner-explainer-field-notes-v1`, section 3 of the owner-explainer reel. The renderer is `engine/fieldnotes.js`; a
scene opts in with `"type": "fieldnotes"`. `studio/cuts.py` splices the file into a page only when a project has such a
scene, so every other project's page is byte-identical (checked against all 16 live and template projects). Vertical
1080x1920 only. Worked example: `projects/fieldnotes-tn-cool-before-peak/project.json`.

## What is automatic and what is not

| Step | Status |
|---|---|
| Ordinary-language brief -> plan -> validated scene data (`studio.py fieldnotes`) | **working (experimental, local command)** |
| Missing narration drafted from the brief's facts only; essential missing facts asked as questions | **working** |
| Plan validation: facts, claims (numbers and absolute words only from the brief), text fit, cue words, event order, duration | **working** |
| Scene data -> animated page -> silent MP4 | **working** |
| Revision in plain words (`fieldnotes revise`), re-render from a saved plan (`fieldnotes rebuild`) | **working** |
| Human approval of the preview | **manual by design** (a person watches it; then the normal Studio script approval gates paid narration) |
| Studio UI or agent API for the workflow | **not built**: local command only (Nano or Ender can run it for Bob) |

## The prompt workflow (`python studio.py fieldnotes ...`)

1. Write the brief in plain words (business, audience, problem, verified cause, solution, realistic outcome; optional
   narration and length) in a text file. Examples: `briefs/true-north-cool-before-peak.txt`,
   `briefs/fictional-harbor-lane-dental.txt`.
2. `python studio.py fieldnotes new <project> <brief.txt>` plans, validates, compiles, builds with silent dry timings
   and renders the preview. If an essential fact is missing it stops and lists the questions; if the story needs a diagram
   the renderer does not have, it stops and names the gap. Nothing is invented to fill either.
3. Watch `projects/<project>/fieldnotes/preview-v<N>.mp4`; a person approves it or asks for changes.
4. Changes: `python studio.py fieldnotes revise <project> "keep it to 15 seconds and end on Reply to reschedule"`
   (the change is applied to the brief, saved as `brief-v<N+1>.txt`, then planned again), or edit the brief text and run
   `fieldnotes replan <project> <brief.txt>`. `fieldnotes rebuild <project>` re-renders the saved plan with no model call
   (the same plan gives byte-identical scene data). `fieldnotes status <project>` lists the versions.

How it works: one headless model call (studio/fieldnotes_prompt.md, Claude Code on this server's login, no tools,
throwaway directory) returns a small plan: facts, chapters, narration, and a diagram stage with events from a fixed
vocabulary. `studio/fieldnotes_plan.py` validates it (one repair call with the problems if needed), then compiles it into
this page's scene data, choosing every position, cue word and timing itself. The model never writes scene data or code,
and nothing in a brief is executed. Each version keeps `brief-v<N>.txt`, `plan-v<N>.json`, `report-v<N>.json` (style,
renderer and planner hashes, Studio commit, model usage, validation results, render settings) and `preview-v<N>.mp4`.

Diagram stages today: `home_energy` (house, outdoor AC, day timeline with a price window, thermostat, gauge) and
`process_flow` (3 to 5 numbered steps with links that break and get fixed, a pulse, highlights). A story that needs
anything else (maps, networks, cutaways, bar comparisons) is reported as a gap until that stage exists.

## Manual planning (when writing scene data by hand)

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
| `flow` | x, y, w, boxH, gap, nodes [{id, label}] | parts: a step id or a link `l1`..: `show` / `hide`, `highlight` { tone ochre/sage/blue/none } on a step, `mark` { state broken/ok, label } on a link; `pulse` { from, to } on the flow |

Positions and fractions are plain numbers in the 1080x1920 frame; timeline `from` / `to` / `pos` are fractions of its
width. Colours are palette names from `project.json` `palette` (ochre, sage, blue, blueStroke, ink...) or hex.

## Inputs for a new video

Copy `projects/fieldnotes-tn-cool-before-peak/`, then edit `project.json`: `voice` (the owner's narrator), each
scene's `line.text` and `cues`, and the `data` blocks. Keep `fonts/` (Inter Tight, Inter, Instrument Serif, OFL).
Preview free with `--dry-timings`; once the script is approved, `build` (paid narration) re-times the same actions to
the real words, then `render` (local) or `render-remote`.

## Remaining gaps

- The prompt workflow is a local command; no Studio UI or agent API route yet.
- Two planner stages (home energy, process flow). Other stories need new kinds and stages (map, network, cutaway, bar
  comparison); the planner reports them as gaps rather than substituting a picture.
- No dark or olive full-screen chapter card yet (only the bands wipe).
- Not wired into the platform (agent API, wizard, Studio UI); local projects and the CLI only.
- No owner footage, avatar or CTA sections; this renders section 3 only.
