# Owner Featured: Field Notes v1 (draft, 2026-10-12)

Four parts, vertical 9:16, about 30 to 35 s, brisk owner-to-customer delivery:

1. **Customer problem.** Realistic footage of the customer's moment, owner voiceover. Keyframe first (reviewed), then a
   short Kling animation from the approved keyframe. No readable invented amounts or personal details.
2. **Owner intro.** The owner's Argil talking head (an existing trained look), his ElevenLabs voice, lip-synced.
3. **Explainer.** An accepted narrated Field Notes render, reused unchanged (verified by sha256 before assembly).
4. **Business close.** A saved, versioned close per business: the owner's talking head in the same look as part 2, the
   logo and business name revealed across the top as he names the business, the phone number revealed large beneath as
   he reads it, everything held about 2 s after speech and kept on the final encoded frame.

Per reel, only parts 1 and 2 (and a new explainer when the topic changes) are made. Part 4 is chosen from the saved
closes. Assembly is local (no paid calls): verify each part's checksum, normalise to 1080x1920 30 fps and one audio
format, concatenate, loudness-normalise the joins, render, and check every boundary frame and the last frame.

Ordinary-language use (Nano): "Make an Owner Featured reel for True North about <problem>, using the <explainer>
animation and the standard True North close." Nano quotes the missing parts, gets approval, then builds.
