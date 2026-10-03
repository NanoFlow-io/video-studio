# NanoFlow.io Video Studio

Make mascot-led explainer videos from a JSON script. You supply a mascot image, a logo and the words. The studio then:

- generates the mascot poses and the voiceover, sound effects and music,
- times every animation and sound to the exact spoken word,
- renders a **16:9** and a **9:16** cut (the vertical cut gets two-word captions).

It uses ElevenLabs for voice, sound effects and music. For the mascot poses and the optional transition clips you can use either **Google** (Gemini for images, Veo for video) or **Higgsfield**. If you have none of those, the pipeline is plain Python and HTML, so you can plumb in your own substitutes. See [Swapping providers](#swapping-providers).

The repo ships with the NanoFlow explainer as a worked example: `projects/nanoflow`, 15 scenes, about 80 s landscape and about 49 s vertical.

---

## How it works

```
project.json ──► voiceover (ElevenLabs, one request per line, with word timestamps)
             ──► beats: every cue pinned to a spoken word ("the card flips on 'missed'")
             ──► sound effects + music (ElevenLabs), mixed with the music ducked under the voice
             ──► one HTML page per cut (HyperFrames + GSAP), every frame a pure function of time
             ──► MP4 render (HyperFrames, pinned version) ──► checks (page errors, blank frames, A/V sync)
mascot.png ──► poses (Google Nano Banana or Higgsfield GPT Image) ──► transparent WebP stills
           ──► optional transition clips (Veo or Higgsfield Kling)
```

The picture and the sound read the same timing file, so they cannot drift apart. Edit a line of the script and only that line is re-voiced. Paid media is cached in `projects/<name>/generated/` and reused.

## Requirements

- Python 3.9+
- Node.js 22+ (HyperFrames needs it)
- ffmpeg and ffprobe on your PATH
- Chromium for the renderer and page checks: `python -m playwright install chromium`. On Windows also install `chromium-headless-shell`, because desktop Chrome can't answer HyperFrames' `--version` check there.
- An **ElevenLabs** API key. A paid plan is needed for the Music API.
- One media provider:
  - **Google**: a Gemini API key from [AI Studio](https://aistudio.google.com/apikey). One key covers Nano Banana (poses) and Veo (transitions). The Google route also needs `pip install "rembg[cpu]"` to cut poses out, because Gemini images have no transparency.
  - **Higgsfield**: a Higgsfield account. Setup installs the official [Higgsfield CLI](https://github.com/higgsfield-ai/cli) into `tools/` and signs you in through the browser. Higgsfield's API keys can't be used here: its key-based REST API only accepts images by public URL and has no upload, while the CLI uploads your local mascot file.

## Quick start

```bash
git clone https://github.com/NanoFlow-io/video-studio.git
cd video-studio
pip install -r requirements.txt
npm install                      # pinned HyperFrames + GSAP
python -m playwright install chromium
python studio.py setup           # asks for the keys and your provider, saves them to .env (git-ignored), tests them
python studio.py all nanoflow    # builds and renders the example
```

Your videos land in `projects/nanoflow/build/out/<name>-16x9/renders/` and `-9x16/renders/`.

> **Cost note:** building the example from scratch buys about 3,000 characters of voiceover, 32 sound effects and about 86 s of music on ElevenLabs. Everything is cached, so later builds only pay for what you change. The example's poses are already in the repo, so it needs no image generation.

## Make your own video

```bash
python studio.py new acme --mascot path/to/mascot.png --logo path/to/logo.png --describe "a friendly blue fox in a yellow hard hat"
# edit projects/acme/project.json: script lines, on-screen copy, colours, voice
python studio.py voices          # pick a voice id for project.json "voice.voice_id"
python studio.py poses acme      # generates every pose listed under "poses"
python studio.py all acme        # voice, sound, music, beats, mix, pages, render, checks
```

Useful flags:
- `--cut landscape|vertical|both`
- `--force`: re-buy media.
- `--only name1,name2`: just those poses, sounds or clips.
- `--offline`: rebuild from cached media, with no API calls.
- `--quality draft|looks|delivery`

### project.json

| Field | What it is |
|---|---|
| `name`, `brand.logo`, `brand.mark` | Name, full logo (end card and reveal) and square mark (integrations hub) |
| `mascot.reference`, `mascot.description` | Your mascot image, plus one line describing it, which keeps poses on-model |
| `poses` | Pose name and what the mascot is doing. Each scene picks one with `"pose"`. |
| `palette`, `backgrounds`, `solids`, `fonts` | Colours (CSS values), named scene backgrounds, their flat colour for wipes, and font families. To use your own font files, put `fonts.css` and the font files in `projects/<name>/fonts/`. |
| `voice` | ElevenLabs `voice_id`, `model`, `settings`, plus `lead_in` and `tail` seconds |
| `music` | `bed_a` (before the turn) and `bed_b` (from the turn): prompt and length in ms |
| `sfx` | Name, prompt and seconds for every `el:` sound used by a cue |
| `audio` | `sfx_bus_db`, `music_db`, `duck_db`, and `peak_align` (sounds placed by their loudest moment) |
| `transitions` | Optional generated clips laid over a scene boundary (see below) |
| `scenes` | The video, in order. Each scene is one spoken line. |

A scene:

```json
{
  "id": "S06", "type": "call_answered", "pose": "headset", "bg": "lilac",
  "line": {"text": "When you're busy or closed, it answers the call...", "vertical": true, "pause": [0.45, 0.35]},
  "data": {"title": "Calls", "title_accent": "answered", "answered": "Answered by NanoFlow", "...": "..."},
  "cues": [
    {"name": "answer", "at": "answers", "sfx": "el:pickup", "gain": -6},
    {"name": "wipe", "at": "start", "sfx": "el:whoosh_a", "gain": -12}
  ]
}
```

How the fields work:
- `line.vertical: false` leaves the scene out of the 9:16 cut.
- `pause` is the silence after the line, `[landscape, vertical]`.
- `"turn": true` marks the reveal scene. The music switches there, and the cue named `off` in the scene before it is the held beat.
- `"wipe": false` skips the colour wipe into the scene.
- `"captions": false` hides vertical captions for the scene, which is useful when big text already says it.

Each cue's `at` is a word in the line (first match; use `occ` for a later one), or `start`, `start+0.3` or `end+0.45`. `delta` shifts the cue in seconds. `sfx` is `el:<name>` (generated from your `sfx` prompts), `kit:<name>` (bundled CC0 interface sounds) or `null`. `gain` is in dB and `rate` changes pitch and speed.

### Scene types

Each type reads the `data` fields below and needs the listed cue names. The build tells you if one is missing.

| Type | Shows | Cues |
|---|---|---|
| `incoming_call` | Iso floor, ringing call card | `tiles`, `ring` |
| `missed_to_competitor` | Missed call; the call flies to another business in search results | `missed`, `list`, `next`, `booked` |
| `problem_stack` | Inbox counter fills up, review waiting, stale social account | `inbox`, `full`, `review`, `social`, `stale` |
| `night_admin` | Night, clock running on, big word, lamp off (held beat) | `tick`, `word`, `off` |
| `reveal` | Logo reveal, sunburst, confetti (the turn) | `logo`, `tag`, `jump` |
| `call_answered` | Call answered, details ticked, transcript types out, next-step chip | `busy`, `closed`, `answer`, `qual`, `transcript`, `next` |
| `inbox_sort` | Email rows re-sort by priority, draft chips | `sort`, `priority`, `drafts` |
| `rank_list` | Cards arrive, then re-rank with the best first | one per `cards[].cue`, `rank`, `first` |
| `review_split` | Rating request, then happy path to a public review, unhappy path to you | `done`, `sms`, `stars`, `happy`, `good`, `unhappy`, `bad` |
| `chat_booking` | Website chat books an appointment | `site`, `chat`, `reply`, `book`, `clock` |
| `content_reels` | Reel phones, carousel, two chips | `reels`, `carousel`, `a`, `b` |
| `integrations_hub` | Four tiles plug into your mark | `hub`, one per `tiles[].cue`, `ok` |
| `phone_approve` | Phone list, tap, approve all, lock chip | `phone`, `tap`, `approve`, `lock` |
| `recap` | Up to three slammed lines | `l1`, `l2`, `l3` |
| `end_card` | Logo, button, URL types out, note | `logo`, `button`, `url`, `chord` |

The NanoFlow `project.json` has a complete example of every type. Copy a scene and change its words.

### Transition clips (Veo or Higgsfield)

```json
"transitions": [{"id": "reveal", "enabled": true, "scene": "S05", "align": "before", "seconds": 1.2,
                 "pose": "jump", "bg": "paper", "prompt": "The mascot leaps up and spins once, static camera, no text"}]
```

`python studio.py transitions <name>` builds a start frame for each enabled entry: the pose on the scene background, at each cut's aspect ratio. It animates that frame with Veo (Google) or Kling (Higgsfield) and keeps a silent `seconds`-long slice. The next build lays the clip over the scene boundary: `before`, `center` or `after` the scene start. A clip that hasn't been generated is skipped, and the colour wipe is used instead.

## Swapping providers

- **Voice, sound effects, music:** `studio/elevenlabs.py`. A replacement needs to return MP3 bytes plus word timings (`[{"w", "s", "e"}]`) for the voiceover, and write MP3 files for sound effects and music. Anything with word-level timestamps works, for example a local TTS plus faster-whisper.
- **Poses and clips:** `studio/providers.py`. Add a class with `check()`, `image(ref_png, prompt, dst, aspect)` and `video(start_png, prompt, dst, aspect, seconds)`, and return it from `get()`. You can also skip generation and put your own transparent WebP poses in `projects/<name>/poses/`.

## Checks

`python studio.py all` runs these on each cut:
- **Before rendering:** a headless page check, which needs a registered timeline and no JavaScript errors.
- **After rendering:** a decode check, a frame every 5 s (blank-frame test and a contact sheet in `build/frames-<cut>/`), and an audibility audit of sound cues the voice may cover.

`python studio.py verify <name> --cues S02.missed,S14.l1` adds audio-to-picture sync measurements for specific cues.

## Repo layout

```
studio.py            command line
studio/              pipeline (Python, stdlib + numpy/pillow/playwright)
engine/              page template + scene library (scenes.js)
assets/fonts/        DM Sans, Nunito, Caveat (SIL OFL 1.1, licences included)
assets/sfx-kit/      Kenney Interface Sounds (CC0)
projects/<name>/     project.json, mascot/, poses/, brand/, images/
                     generated/ (paid media cache) and build/ are git-ignored
```

## Licences

- **Code:** MIT (see `LICENSE`).
- **Fonts:** SIL Open Font License 1.1, with licence files in `assets/fonts/`.
- **Interface sounds:** CC0, from [Kenney](https://kenney.nl/assets/interface-sounds).
- **Installed by `npm install`, under their own licences:** HyperFrames (Apache-2.0) and GSAP (GreenSock Standard "no charge" licence).
- **Generated media:** voice, sound, music, poses and clips you generate are governed by your provider's terms.
- **NanoFlow example assets:** the NanoFlow name, logo, mascot artwork and photos in `projects/nanoflow/` belong to NanoFlow. They are included as an example only and are **not** covered by the MIT licence.
