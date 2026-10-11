# Owner Explainer — Field Notes v1: style sheet

Reference ID `owner-explainer-field-notes-v1`. Experimental. Section 3 of the owner-explainer reel only (the animated
cause-and-solution explanation). Derived from the reference video's explainer section (about 22.4 s to 62 s of 72.7 s,
720x1280, 30 fps), inspected as 2 s contact sheets, full-size settled frames and 3 fps motion strips. Machine-readable
values live in `template.json`; this file explains them. Never reuse the reference's watermark, script, place names,
map, ant or house artwork; only its visual language.

## Palette (sampled)

Median of quantised pixel clusters from settled frames; within about 3 RGB steps.

| Token | Hex | Where it appears in the reference |
|---|---|---|
| paper | `#E7E0D4` | page background (light `#EDE7DB`, shaded `#DCD4C8`) |
| grid | `#D6CEC0` | faint 54 px grid and survey rings, about 30% opacity |
| ink | `#1B1B15` | headlines, outlines, roofs, the dark chapter card and wipe band |
| ochre | `#D58745` | highlight box behind a headline word, tags, network nodes, doors, the wipe band |
| ochreRule | `#C3996F` | thin header progress rule (anti-aliased ochre) |
| sage | `#698157` | shield outline, check badge, timeline nodes, doors |
| sageWipe | `#6C8454` | diagonal wipe band |
| olivecard | `#4C5C3C` | full-screen chapter card ("So what's the solution?") |
| sageTint | `#B1B799` | under-highlight behind a headline word, shield fill |
| dustyBlue | `#A5BDD5` | windows, perimeter ring fill, underline emphasis |
| blueStroke | `#7E9CC0` | ring and indicator strokes (estimated: confirm at review) |
| tan / brown / brownDeep / brownDark | `#BC9C7C` `#A47C5C` `#84644C` `#7C5C44` | soil layers of cutaways |
| groundTint | `#E1D5C3` | ground discs and map land fill |

Use ochre for the one thing the narration names, sage for the fix, blue for water, air or protection perimeters,
browns only inside cutaways. Never more than three accent colours in one composition.

## Typography

| Role | Reference look | Template face | Status |
|---|---|---|---|
| Headline | heavy neo-grotesque, very tight tracking, left aligned, 2 to 3 lines | Inter Tight 800, -0.035em, line-height 1.0, 112 px at 1080 wide (auto-fits down to 70%) | **substitute**: the original face is not identifiable with certainty (Inter Display or a Neue Haas style grotesk) |
| Header and kicker | small uppercase, wide tracking, the place name bold and FIELD NOTES light | Inter 600/700, 0.18 to 0.2em | **substitute** |
| Emphasis word / annotation / quote | condensed elegant italic serif ("ants", "...and it's real.", "It's been a lifesaver.") | Instrument Serif Italic | **substitute** (closest free match) |

No confirmed matches: the reference ships no font metadata and the shapes are close to several grotesques. All three
substitutes are SIL Open Font License, stored in `fonts/`.

## Layout (1080 x 1920)

- Margins 72 px. Header at y 150: `[BUSINESS] FIELD NOTES` left, `CHAPTER NN/TT` right; a 2 px rule at y 188 with an
  ochre progress segment = chapter / total.
- Kicker at y 246: 40 px ochre dash, uppercase label. Headline from y 290, left aligned, max 3 lines, width 900.
- Emphasis on one headline word or line only: white text on an ochre box (problem words), a sage underlay (fix words), or
  a blue underline (cause words). Italic serif may replace one word of the headline.
- One illustration per chapter in the band y 620 to 1520, fixed camera, generous paper around it. Lower band
  y 1540 to 1760 for a small indicator: timeline, bar list, checklist card or measurement note. Nothing below 1760
  (platform UI).

## Illustration treatment

- Flat, vector-like, 4 px dark outlines with round joins, muted flat fills, no gradients, no shadows except the hard
  ochre offset behind a checklist card.
- Explanatory, not decorative: cutaways (soil layers), annotated objects with leader lines, networks of nodes, maps with
  roads, measurement brackets, indicator cards with a bar, timelines with checked nodes, bar lists.
- Consistent objects within a chapter (the same building returns), distinct compositions between chapters (elevation,
  cutaway, protected elevation).
- Paper: faint grid, soft uneven radial shading, fine grain. All generated (no image files).

## Motion language (observed over time, not only stills)

1. **Headline reveal**: line by line, rising about 20 px, hard ease-out. The emphasis box wipes in behind the line on the
   spoken word, then the text turns white. The previous headline leaves by sliding up and fading.
2. **Diagram assembly**: outlines draw on first, fills tint in after, parts arrive in story order (map land, then roads,
   then lots, then labels; ant outline, then fill, then labels).
3. **Causal action**: the cause visibly travels (ants marching along roads, a dashed path drawing with a travelling marker,
   a network growing outward from one seed node).
4. **Annotation**: leader line first, then the label, tag or italic note. Measurement brackets draw end to end.
5. **Resolution**: the fix wraps the subject (perimeter ring draws, shield outline draws and fills, check badge pops); the
   problem retreats (ants pushed out); a timeline ticks through the cadence.
6. **Transitions**: sparing. Broad diagonal geometric wipes (sage, near-black, ochre bands) or a full-screen olive or
   dark card with a huge faint italic glyph and a two-line question whose underline draws in ochre.
7. **Pacing**: completed diagrams hold at least 1 s; the camera never moves. Forbidden: glossy 3D, neon, bouncy easing
   (the check badge pop is the only overshoot), random zooms, particles, stock-icon slideshows.

## Not part of this template

Opening problem footage, the owner avatar, the closing "Contact [BUSINESS NAME]" CTA, captions over footage and any
reference watermark.
