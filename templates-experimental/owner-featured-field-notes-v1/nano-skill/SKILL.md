---
name: owner-featured-reel
description: Make an "Owner Featured: Field Notes v1" reel (customer reaction hook, owner intro talking head, a NEW topic-specific Field Notes explainer, the business's saved close, approved music) from a short prompt. Quotes first and stops at every approval gate; never publishes. Use when an admin asks Nano for an Owner Featured reel, an owner-featured Field Notes reel, or "a reel like Summer Bill Shock".
---

# Owner Featured reel (draft and review only)

Format: `templates-experimental/owner-featured-field-notes-v1/format.json` (locked; reference build v4, approved by
Bob 2026-10-12). Business specifics (voice, Argil look, logo, number, close, music) live only in
`tenants/<business>.json`. Run every command from `/home/adam/video-studio` with `.venv/bin/python`.

## Invocation prompt (what the person pastes)

```
Make an Owner Featured reel for <business>: <title>.
1. Customer reaction: <who, where, the visible reaction>. Owner voiceover: "<one line>"
2. Owner intro: "<one or two short lines>"
3. Explainer: <plain-English Field Notes brief: problem, cause, fix, realistic outcome>
Quote first; show me the storyboard, the keyframe and the voice before anything else is made. Draft only.
```

Default: part 3 is a NEW Field Notes story and animation for this topic. Reuse an earlier middle only when item 3
says `reuse project <name>`. Never suggest reuse to save money unless asked.

## Steps and gates (stop at every gate and wait for the person's words)

1. **Draft and quote (free).** `.venv/bin/python -m studio.owner_featured draft <business> <project> < prompt` (quoted
   heredoc). Relay `problems` and stop if any. Otherwise show the quote by funding type: provider charges, prepaid
   usage (Higgsfield credits, ElevenLabs credits, Argil clip), subscription-funded work (planner calls, Nano turns,
   API-equivalent only) and local work (no API charge). Show the Field Notes planner quote too:
   `fieldnotes_agent quote new <project>-fn`. **Gate 1: the person approves the quote.**
2. **New Field Notes middle.** Follow the fieldnotes-explainer skill: `new <project>-fn --quote <id>` with the item 3
   brief. Show the storyboard and the silent preview link. Revisions only through `revise` with the person's words
   (each quoted first). **Gate 2: the person approves the silent preview.**
3. **Middle narration.** `fieldnotes_agent narrate <project>-fn --version <N> --voice-file <voice.contract_file from the business profile>
   --pace brisk`. Quote the characters (0.5 ElevenLabs credit each). **Gate 3: the person presses Approve Script in
   the Studio**; the paid narration build runs there. Listen to the result; never time-stretch it.
4. **Customer keyframe.** Higgsfield nano_banana_2 (2 credits) on the production account, from item 1 and the
   format's hook rules. **Gate 4: the person approves the still before any animation.** Then kling3_0 5 s from the
   approved keyframe (8.75 credits).
5. **Owner voice.** ElevenLabs with the business voice (model, settings, speed from the business profile), one take
   each for the hook line and the intro, pace set at generation. Send both files. **Gate 5: the person listens and
   approves before the Argil render.** No automatic retakes; a retake is a new quote.
6. **Owner intro talking head.** One Argil clip with the business's approved look, run once on the business server
   where its key lives (pattern: `owner-featured/tn-summer-bill-shock/argil/argil-run.sh`; the audio must be at a
   public URL on that server; create, render, poll DONE, download, delete). No retries. If the lips drift from the
   audio, retime the video to the audio, never the audio.
7. **Assembly (local).** Follow `format.json` assembly and music exactly: every part encoded to the middle's stream
   format, Argil crop, fixed gains, concat by stream copy, the saved close unchanged, the music bed at -14 dB with the
   sidechain ducking, fade-in and fade-out rules. Check: duration, lip sync, peak at or below -1 dBFS per channel, the
   spoken number clear over the bed. Make a Studio review copy and check its link with the authenticated probe.
   **Gate 6: the person reviews the final reel.**

## Never

- Publish, schedule, upload to socials, merge, deploy, restart, or approve on the person's behalf.
- Spend beyond the approved quote, retake automatically, or run a paid step before its gate.
- Time-stretch narration. Hand-edit Field Notes scene data. Change the saved close, the music file or the format.
- Put business specifics into `format.json`. Delete or overwrite earlier review copies.
- Write scripts as brochure copy: the owner talks to a customer, natural and direct.
