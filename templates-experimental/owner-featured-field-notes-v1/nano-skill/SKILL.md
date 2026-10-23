---
name: owner-featured-reel
description: Make an "Owner Featured" reel for any business with a profile (customer reaction hook, the owner's talking-head intro, a NEW topic-specific Field Notes animated explainer, the business's saved branded close, shared music) from a one-line topic, e.g. "use the Owner Featured template for XYZ Heating and make it about turning ceiling fans off". Also sets up a new business (profile, presenter, voice, saved close) and restyles a close's phone-number card. Quotes first, stops at every approval gate, never publishes. Use when an admin asks Nano for an Owner Featured / owner-featured / "animated template" reel, or "a reel like Summer Bill Shock".
---

# Owner Featured reel (draft and review only)

Format: `templates-experimental/owner-featured-field-notes-v1/format.json` (locked; reference build: True North Summer
Bill Shock v4, approved by Bob 2026-10-12). The format is generic. Each business's details live only in
`tenants/<slug>.json`: presenter (Argil look), voice, logo, number, brand colours, saved close, optional music (the
shared NanoFlow bed is the default). Run everything from `/home/adam/video-studio` with `.venv/bin/python`.

## What the person says

One line is enough: **"Use the Owner Featured template for <business> and make it about <topic>."**
They may add their own lines; use them as given.

## 1. Find the business (free)

`.venv/bin/python -m studio.owner_profile find "<business as they said it>"`
- One match and `ready: true`: carry on.
- One match, not ready: say exactly what is missing (the `missing` list, in plain words) and offer the setup below. Stop.
- No match: ask which business, or offer to set it up. Never borrow another business's presenter, voice, logo or number.

## 2. Write the lines and quote (free) - Gate 1: quote

Write the filled prompt yourself from the topic, as the owner talking to a customer: natural, direct, useful, never
brochure copy. Facts only from the person or the business's own material; nothing invented (no prices, savings
figures, rebates or customer details).

```
Make an Owner Featured reel for <slug>: <short title>.
1. Customer reaction: <who, where, the visible reaction; nothing printed legible>. Owner voiceover: "<one short line>"
2. Owner intro: "<one or two short lines, the owner introducing himself or herself and the point>"
3. Explainer: <Field Notes brief: problem, cause, fix, realistic outcome>
```

Run `.venv/bin/python -m studio.owner_featured draft <slug> <project> <<'EOF' ... EOF`, then
`.venv/bin/python -m studio.fieldnotes_agent quote new <project>-fn`. Show the person: the three lines, the brief, and
the quote by funding type (provider charges, prepaid credits, subscription-funded work, local work). Default is a NEW
middle; reuse an earlier one only if they say "reuse project <name>". When they approve:
`.venv/bin/python -m studio.owner_steps gate <project> quote --words "<their words>"`.

## 3. The new Field Notes middle - Gates 2 and 3 (in the Studio)

Follow the fieldnotes-explainer skill: `new <project>-fn --quote <id>` with the item 3 brief; show the storyboard and
silent preview; revisions only via `revise` with their words. On approval: `gate <project> storyboard --words ...`.
Then `fieldnotes_agent narrate <project>-fn --version <N> --voice-file <voice.contract_file> --pace brisk`, quote the
characters (0.5 ElevenLabs credit each), and the person presses Approve Script in the Studio. After they have listened:
`gate <project> narration --words ...`.

## 4. Customer reaction - Gate 4: keyframe

Write the keyframe prompt (photoreal 9:16, natural candid moment, nothing printed legible, no text or brands) to a file;
`owner_steps keyframe <project> --prompt-file F` (2 Higgsfield credits). Show the still. On approval:
`gate <project> keyframe --words ... --file <keyframe>`. Then write the motion prompt (one continuous 5 s shot, static
camera, reaction early and readable, no speech or lip movement); `owner_steps animate <project> --prompt-file F`
(8.75 credits).

## 5. Owner voice - Gate 5: voice

`owner_steps voice <project>` (one take each for the hook line and intro, pace from the profile's speed setting). Send
both files. On approval: `gate <project> voice --words ...`. Then `owner_steps argil <project>` (one Argil clip, run
on the business's server).

## 6. Assemble and review - Gate 6: final

`owner_steps assemble <project> --middle <the narrated Studio project>`, then `owner_steps review <project>`.
Report `checks` (duration, peak per channel, any retiming) and give the review link only if `link_check.verified`.
On approval: `gate <project> final --words ...`. That is the end: publishing and scheduling are the person's own steps.

## New business setup (once)

1. `owner_profile init <slug> --name "<Business>" [--website URL] [--number "714 555 0100"] [--logo file]`. It
   finds the logo, brand colours and phone number where it can. Show what it found and ask the person to confirm.
2. The person chooses the presenter (Argil avatar) and ElevenLabs voice; record their ids, the runner (server with the
   business's Argil key) and the approvals in the profile.
3. Saved close: `owner_steps close-draft <slug> <project> --line "<close line with the number spoken digit by digit>"`,
   quote, `gate quote`, `voice`, `gate voice`, `argil`, `close-compose <project> --style bar|italic|split`, `review`,
   and after the person approves, `gate close` then `close-save`.

## Restyle a close's number card (free)

`owner_steps close-restyle <slug> <project> --style bar|italic|split` uses the approved talking head, only the card
changes. `review`, then `gate close` and `close-save` after approval. The old close is kept and listed in the profile.

## Never

- Publish, schedule, upload, merge, deploy, restart, or approve on the person's behalf. Record a gate only with their words.
- Spend beyond the approved quote, retake automatically (`--retake` needs the person's request and a new quote).
- Time-stretch narration. Hand-edit Field Notes scene data. Change a saved close, the music or `format.json`.
- Put business details in `format.json` or use one business's details for another.
- Delete or overwrite earlier review copies or closes.
