# NanoFlow.io Video Studio

Video Studio turns a written script and a mascot image into finished explainer videos. You describe the video in one JSON file: the lines the narrator says, the words that appear on screen, the colours, and the moments where things should happen. The studio then produces two videos from it:

- a **landscape cut** (16:9, 1920x1080) for websites, YouTube and LinkedIn
- a **vertical cut** (9:16, 1080x1920) for Reels, TikTok and Shorts, with large two-word captions for people watching on mute

Both cuts share the same voice recording, sound design and timing. Every animation and every sound effect is pinned to a specific spoken word, so when the narrator says "missed", the call card flips to "Missed call" on that word, with a sound on the same frame.

The repo includes the NanoFlow explainer as a complete worked example in `projects/nanoflow`: 15 scenes, about 80 seconds in landscape and 49 seconds in vertical, starring the NanoFlow robot.

## Contents

1. [What you need](#what-you-need)
2. [Installation](#installation)
3. [Setup: keys and provider](#setup-keys-and-provider)
4. [Rendering the example](#rendering-the-example)
5. [Making your own video](#making-your-own-video)
6. [How the pipeline works](#how-the-pipeline-works)
7. [project.json reference](#projectjson-reference)
8. [Scenes, lines and cues](#scenes-lines-and-cues)
9. [Scene type reference](#scene-type-reference)
10. [Mascot poses](#mascot-poses)
11. [Transition clips](#transition-clips)
12. [Sound and music](#sound-and-music)
13. [Costs and caching](#costs-and-caching)
14. [Checks](#checks)
15. [Command reference](#command-reference)
16. [Troubleshooting](#troubleshooting)
17. [Swapping providers](#swapping-providers)
18. [Repo layout](#repo-layout)
19. [Licences](#licences)

## What you need

**Software**

| Tool | Version | Used for |
|---|---|---|
| Python | 3.9 or newer | The pipeline itself |
| Node.js | 22 or newer | HyperFrames, the renderer |
| ffmpeg and ffprobe | Any recent build, on your PATH | Audio editing, mixing, checks |
| Chromium | Installed through Playwright | Rendering pages and checking them |

**Accounts**

| Service | Needed for | Notes |
|---|---|---|
| ElevenLabs | Voiceover, sound effects, music | Required. Music generation needs a paid plan. |
| Google AI Studio (Gemini API) | Mascot poses and transition clips | One of Google or Higgsfield. A single Gemini API key covers both images (Nano Banana) and video (Veo). |
| Higgsfield | Mascot poses and transition clips | One of Google or Higgsfield. Uses Higgsfield's official CLI, which signs in through your browser. |

You only need a media provider if you want the studio to generate poses or transition clips. If you already have transparent images of your mascot, you can drop them into the project and skip generation altogether.

## Installation

```bash
git clone https://github.com/NanoFlow-io/video-studio.git
cd video-studio

pip install -r requirements.txt          # numpy, pillow, playwright
npm install                              # the pinned renderer (HyperFrames) and GSAP
python -m playwright install chromium    # a browser for rendering and page checks
```

Extra steps for some setups:

- **Windows:** also run `python -m playwright install chromium-headless-shell`. HyperFrames checks the browser by running it with `--version`, and the desktop build of Chrome on Windows opens a window instead of answering. The studio finds the headless shell automatically.
- **Google as your provider:** also run `pip install "rembg[cpu]"`. Gemini returns images without transparency, so the studio cuts the mascot out locally. The first run downloads a model of about 170 MB.

ffmpeg is not installed by any of the commands above. Get it from [ffmpeg.org](https://ffmpeg.org/download.html), your package manager (`brew install ffmpeg`, `apt install ffmpeg`, `winget install ffmpeg`), or any other source, and make sure `ffmpeg` and `ffprobe` both run from a terminal.

## Setup: keys and provider

```bash
python studio.py setup
```

Setup walks you through four things:

1. It checks that node, npm, ffmpeg and ffprobe are available, and runs `npm install` if the renderer is missing.
2. It asks for your **ElevenLabs API key**.
3. It asks you to choose a **media provider**: `google` or `higgsfield`.
4. For Google it asks for your **Gemini API key**. For Higgsfield it downloads the official CLI into `tools/higgsfield/` and opens your browser to sign in.

Keys are typed into a hidden prompt and saved to a file called `.env` in the repo folder. That file is listed in `.gitignore`, so it is never committed. You can also write it by hand using `.env.example` as a template, or provide the same values as environment variables, which take priority over the file.

Afterwards, and any time you want to confirm everything still works:

```bash
python studio.py check
```

This makes a free test call to each service and reports the result, for example your ElevenLabs plan and usage, or whether the Gemini image and video models are available to your key.

### Why Higgsfield uses a sign-in instead of a key

Higgsfield offers API keys, but its key-based API only accepts images as public web addresses and has no way to upload a file. Your mascot is a file on your computer, so it cannot be passed in that way. Higgsfield's official CLI uploads local files for you, so the studio uses the CLI instead. You sign in once in the browser. Sign-ins expire after a while, and `python studio.py check` will tell you when to sign in again with `tools/higgsfield/hf auth login` (or `hf.exe` on Windows).

If your Higgsfield account has more than one workspace, choose one with `hf workspace set <workspace_id>`.

## Rendering the example

```bash
python studio.py all nanoflow
```

This builds and renders both cuts of the NanoFlow explainer. The finished files are:

```
projects/nanoflow/build/out/nanoflow-16x9/renders/nanoflow-16x9.mp4
projects/nanoflow/build/out/nanoflow-9x16/renders/nanoflow-9x16.mp4
```

The example's mascot poses are already in the repo, so this step does not use your media provider. It does buy the voiceover, sound effects and music from ElevenLabs on the first run, because generated audio is not committed. See [Costs and caching](#costs-and-caching).

Rendering speed depends on your machine. On a server with no graphics card the 49 second vertical cut takes about two minutes. A machine with a GPU is several times faster.

## Making your own video

### 1. Create a project

```bash
python studio.py new acme --mascot path/to/mascot.png --logo path/to/logo.png --mark path/to/icon.png \
  --describe "a friendly blue fox wearing a yellow hard hat and a tool belt"
```

This creates `projects/acme/` with your images copied in and a `project.json` that starts as a copy of the NanoFlow example. The options:

- `--mascot` is your character. A clean image on a plain background works best.
- `--logo` is your full logo, used on the reveal and the end card.
- `--mark` is a square icon, used in the centre of the integrations scene. If you leave it out, the logo is used.
- `--describe` is one line describing what the mascot looks like. It is added to every pose request and helps keep the character consistent.

### 2. Write the video

Open `projects/acme/project.json` and work through it:

- Rewrite each scene's `line.text`: the narration.
- Rewrite each scene's `data`: the words on screen. The [Scene type reference](#scene-type-reference) lists the fields for every type.
- Check that each cue's `at` word still appears in the new line. The build tells you if one does not.
- Remove scenes you do not need and reorder the rest. Scene `id`s just need to be unique.
- Set your colours under `palette`, `backgrounds` and `solids`.
- Choose a voice. Run `python studio.py voices` to list the voices on your ElevenLabs account, then put the id you want in `voice.voice_id`.
- Rewrite the `poses` list to describe the poses your scenes need.

Delete the `_todo` note at the top of the file when you are done.

### 3. Generate the poses

```bash
python studio.py poses acme
```

Each pose is generated from your mascot image, made transparent if needed, and saved as `projects/acme/poses/<name>.webp`. Open them and check them. To redo one: `python studio.py poses acme --only wave --force`.

### 4. Build and render

```bash
python studio.py all acme
```

You can also run the stages separately:

```bash
python studio.py build acme       # voice, sound, music, timing, mix, pages
python studio.py render acme      # page check, render, video checks
```

When you change the script, run `all` again. Only lines whose text changed are sent to ElevenLabs again. When you only change on-screen words, colours or cue timing, use `--offline` to rebuild without any API calls:

```bash
python studio.py all acme --offline
```

## How the pipeline works

```
project.json + mascot image
   |
   |-- poses .............. provider image model -> transparent WebP stills (once per pose)
   |-- transitions ........ provider video model -> short silent clips (optional)
   |
   |-- voiceover .......... ElevenLabs, one request per line, returns audio plus the time of every character
   |-- assemble ........... lines joined with set pauses, separately for each cut (the vertical cut skips some lines)
   |-- beats .............. every cue resolved to a time: "the word 'missed' in scene S02" becomes 3.27 s
   |-- sound and music .... ElevenLabs sound effects and two music beds, generated once and cached
   |-- mix ................ voice + music (ducked under the voice) + every sound effect at its cue
   |-- pages .............. one self-contained HTML page per cut, animated with GSAP on a paused timeline
   |-- render ............. HyperFrames seeks the page frame by frame and encodes MP4 with the mix
   '-- checks ............. page errors, blank frames, decode test, audibility, optional sync measurements
```

A few design decisions make the results reliable:

- **One clock.** The picture and the sound both read the same timing file (`build/beats-<cut>.json`), so they cannot drift apart. Moving a cue moves its animation and its sound together.
- **Word timing from the voice itself.** ElevenLabs returns the start and end time of every character it speaks, so there is no separate transcription step and no guessing.
- **Deterministic frames.** Every frame is a pure function of time. Random elements use fixed seeds, and nothing depends on the real clock. Rendering the same project twice produces the same video.
- **Line-by-line voice.** Each line is recorded on its own, with the neighbouring lines passed along so the delivery still flows. This lets the two cuts use different pauses and different subsets of lines from one recording, and it means editing one line only re-records that line.
- **Pinned renderer.** HyperFrames and GSAP are pinned to exact versions in `package.json`, so a new release cannot change your output without you choosing to upgrade.

## project.json reference

Every project lives in `projects/<name>/` and is described by `project.json`. Paths inside it are relative to the project folder.

| Field | Type | Description |
|---|---|---|
| `name` | text | Shown in page titles. |
| `brand.logo` | path | Full logo, used on the reveal scene and the end card. |
| `brand.mark` | path | Square icon, used in the centre of the integrations hub. |
| `mascot.reference` | path | The mascot image every pose is generated from. |
| `mascot.description` | text | One line describing the mascot's look, added to every pose request. |
| `poses` | object | Pose name mapped to a description of what the mascot is doing. See [Mascot poses](#mascot-poses). |
| `pose_aspect` | number | Width divided by height of the pose images. Default 0.7466 (a 3:4 canvas). |
| `palette` | object | Brand colours, described below. |
| `fonts` | object | Font families for `title`, `body` and `note` (handwritten notes). |
| `backgrounds` | object | Named scene backgrounds. Values are any CSS background: a colour, a gradient or several layered gradients. |
| `solids` | object | One flat colour for each background name, used for the colour wipe into that scene. |
| `voice` | object | ElevenLabs voice settings, described below. |
| `music` | object | The two music beds, described in [Sound and music](#sound-and-music). |
| `sfx` | object | Prompts for every generated sound effect. |
| `audio` | object | Mix levels, described in [Sound and music](#sound-and-music). |
| `transitions` | list | Optional generated clips. See [Transition clips](#transition-clips). |
| `scenes` | list | The video itself, in order. See [Scenes, lines and cues](#scenes-lines-and-cues). |

**palette**

| Key | Used for |
|---|---|
| `primary` | Main brand colour: buttons, chips, the clock face, chat headers |
| `primary2` | A lighter companion to the primary colour: icons, connector lines |
| `secondary` | Handwritten notes, the unhappy review path, clock hands |
| `accent` | Highlight colour: the number one rank, call rings, the lock icon |
| `ink`, `ink2` | Main text colour and secondary text colour |
| `paper` | Default page background |
| `good`, `bad` | Success green and warning red |
| `grad` | The gradient used on accent words in titles, as a CSS gradient |

**fonts**

The studio ships with DM Sans (titles), Nunito (body) and Caveat (handwritten notes). To use other fonts, create `projects/<name>/fonts/` containing your font files and a `fonts.css` with the `@font-face` rules, then set the family names in `fonts`. Fonts are loaded from local files only, so renders work without an internet connection.

**voice**

| Key | Description |
|---|---|
| `voice_id` | The ElevenLabs voice. List yours with `python studio.py voices`. |
| `model` | The ElevenLabs model, for example `eleven_multilingual_v2`. |
| `settings` | Passed straight to ElevenLabs: `stability`, `similarity_boost`, `style`, `use_speaker_boost`, `speed`. |
| `lead_in` | Seconds of silence before the first word. Default 0.5. |
| `tail` | Seconds the video holds after the last word, for the end card. Default 2.6. |

Changing the voice or its settings re-records every line on the next build.

## Scenes, lines and cues

A scene is one spoken line plus what happens on screen while it is spoken. Here is a complete scene from the example:

```json
{
  "id": "S02",
  "type": "missed_to_competitor",
  "pose": "ladder",
  "bg": "peach",
  "line": {
    "text": "You can't pick up, so the job goes to the next name on Google.",
    "vertical": true,
    "pause": [0.45, 0.35]
  },
  "wipe": false,
  "data": {
    "incoming": "Incoming call",
    "missed": "Missed call",
    "search": "plumber near me",
    "results": [["Your business", "Missed call"], ["Next business", "Answers every call"], ["Another business", "4.6 stars"]],
    "winner": 1,
    "stamp": "Booked",
    "note": "the job went elsewhere"
  },
  "cues": [
    {"name": "wipe",   "at": "start",  "sfx": "el:whoosh_a",  "gain": -12},
    {"name": "missed", "at": "pick",   "sfx": "el:missed_tone", "gain": -8},
    {"name": "list",   "at": "job",    "sfx": "el:slide_up",  "gain": -9},
    {"name": "next",   "at": "next",   "sfx": "el:whoosh_b",  "gain": -12},
    {"name": "booked", "at": "Google", "sfx": "kit:drop_001", "gain": -8}
  ]
}
```

**Scene fields**

| Field | Description |
|---|---|
| `id` | Any unique name. Cue ids in the timing files are written as `<id>.<cue name>`, for example `S02.missed`. |
| `type` | Which scene layout to use. See the [Scene type reference](#scene-type-reference). |
| `pose` | Which mascot pose appears in the scene. Must exist in `projects/<name>/poses/`. |
| `bg` | A name from `backgrounds`. |
| `line.text` | What the narrator says during this scene. |
| `line.vertical` | `false` leaves this scene out of the vertical cut. Default `true`. |
| `line.pause` | Seconds of silence after the line, as `[landscape, vertical]`. Shorter pauses in the vertical cut keep it punchy. |
| `wipe` | `false` cuts straight into the scene instead of using a colour wipe. Useful when a scene continues the previous one. |
| `turn` | `true` marks the reveal moment. The music switches from the first bed to the second here, and the previous scene's cue named `off` becomes the silent held beat before it. Use it on one scene at most. |
| `captions` | `false` hides vertical captions for this scene. Useful when large text already shows the words. |
| `data` | The on-screen words and settings for this scene type. |
| `cues` | The timed moments in the scene. |

**Cue fields**

| Field | Description |
|---|---|
| `name` | The moment this cue drives. Each scene type reads specific cue names (listed in the reference). You can also add extra cues purely for sound. |
| `at` | When it happens. Either a word from the line, matched from its start and ignoring case and punctuation (`"pick"` matches "pick" and "picking"), or `start` (the scene start), `start+0.3`, or `end+0.45` (seconds after the last word of the line). |
| `occ` | Which match to use when the word appears more than once. 0 is the first. Default 0. |
| `delta` | Shift in seconds, positive or negative. For example `-0.05` lands just before the word. |
| `sfx` | The sound for this moment: `el:<name>` for a sound generated from your `sfx` prompts, `kit:<name>` for a bundled interface sound, or `null` for silence. |
| `gain` | Volume of the sound in dB. 0 is full volume; -12 is quiet. |
| `rate` | Playback speed and pitch of the sound. 1.1 is slightly higher and shorter. Handy for giving repeated sounds some variety. |
| `note` | A description for your own reference. It appears in the sound sheet. |

Every build writes a readable sound sheet to `projects/<name>/build/sound-sheet-<cut>.md`, listing every cue in time order with its word, sound and gain.

## Scene type reference

All feature types accept `title` and `title_accent` (the second part of the title, drawn in the brand gradient), plus `title_color` and `floats` (a list of colours for the small drifting background shapes). Where a type lists a cue, project.json must provide a cue with that name, and the build stops with a clear message if one is missing.

Icons available for `icon` fields: `phone`, `mail`, `msg`, `star`, `check`, `x`, `search`, `lock`, `play`, `cal`, `person`.

### incoming_call

An isometric floor builds itself tile by tile, the mascot pops up, and a call card rings and shakes.

| Data | Description |
|---|---|
| `label` | Small caps label, for example "INCOMING CALL" |
| `name` | Caller name in large type |
| `sub` | Line under the name |
| `floor_a`, `floor_b` | Optional tile colours (hex) |

Cues: `tiles` (floor starts building), `ring` (ring waves and shake).

### missed_to_competitor

The call card flips to a missed call, a search results list slides in, and the call flies to another business, which gets stamped.

| Data | Description |
|---|---|
| `incoming`, `missed` | Text on the call card before and after |
| `search` | The search box text |
| `results` | Three rows of `[name, sub line]`. The first row is shown greyed out as "you". |
| `winner` | Index of the row that gets the call. Default 1. |
| `stamp` | Text of the chip stamped on the winning row |
| `note` | Optional handwritten note under the panel |

Cues: `missed`, `list`, `next` (the call flies), `booked` (the stamp lands).

### problem_stack

Three problems pile up: an inbox counter races up with envelopes raining in, a review waits for a reply, and a social account goes grey with a cobweb.

| Data | Description |
|---|---|
| `title`, `title_color` | Scene title and its colour (white suits dark backgrounds) |
| `inbox`, `inbox_sub`, `inbox_count` | Inbox card label, sub line, and the number the counter reaches |
| `full` | Chip that pops onto the inbox card |
| `review_title`, `review_sub` | Review card text |
| `social_label`, `social_title`, `social_value` | Social card text |

Cues: `inbox`, `full`, `review`, `social`, `stale` (card greys out, cobweb draws).

### night_admin

Night scene with a moon, a lamp glow behind the mascot and a clock running on into the night. A big word slams in. The lamp then clicks off and the scene goes dark: the held beat before the reveal.

| Data | Description |
|---|---|
| `chip` | Chip under the clock |
| `word` | The big word |

Cues: `tick` (clock starts running), `word`, `off` (lamp off, screen dims).

### reveal

The turn. A white flash, rotating sunburst rays, the logo pops in with confetti, a tagline slides up, and the mascot jumps on an isometric floor.

| Data | Description |
|---|---|
| `tagline`, `tagline_accent` | Tagline and its gradient part |
| `ray_a`, `ray_b` | Optional ray colours (any CSS colour, use some transparency) |
| `floor_a`, `floor_b` | Optional tile colours |

Cues: `logo`, `tag`, `jump`.

### call_answered

An incoming call with "on a job" and "closed" chips flips to "answered". A details card ticks off each field, a transcript types itself out, and a next step chip appears.

| Data | Description |
|---|---|
| `incoming`, `caller` | Call card text |
| `busy`, `closed` | The two status chips |
| `answered`, `answered_sub` | Text on the answered card |
| `details_title`, `details` | Card title and up to four `[label, value]` rows |
| `transcript_title`, `transcript` | Card title and the text that types out. Use `\n` for line breaks. |
| `type_seconds` | How long the typing takes. Default 1.25. |
| `next` | The next step chip |

Cues: `busy`, `closed`, `answer`, `qual` (details tick one after another), `transcript`, `next`.

### inbox_sort

An inbox of five emails shuffles into priority order, priority tags pop, and "draft ready" chips appear on chosen rows.

| Data | Description |
|---|---|
| `card_title` | Title inside the inbox card |
| `items` | Five rows of `[from, subject, tag text, tag background, tag text colour]` in their starting order |
| `order` | The final position of each item. `[1, 3, 4, 0, 2]` moves item 0 to position 1, item 1 to the top, and so on. |
| `drafts` | Item indexes that get a draft chip |
| `draft_label` | Text on the draft chips |

Cues: `sort`, `priority`, `drafts`.

### rank_list

Three cards arrive in the order they came in, then re-rank so the best one rises to the top with a highlight and a chip.

| Data | Description |
|---|---|
| `cards` | Up to three `{cue, icon, color, title, sub}`. List them best first: the first card ends at the top, and the cards arrive in reverse order. |
| `take` | Chip on the top card |

Cues: one per card, named by its `cue` value, plus `rank` (the re-order) and `first` (the chip).

### review_split

A "job complete" chip, a text message asking for a rating, stars lighting up, then two paths: a happy customer to a public review and an unhappy customer to a private note.

| Data | Description |
|---|---|
| `done` | The opening chip |
| `sms_label`, `sms` | Message card label and text |
| `good_title`, `good_sub` | Happy path card |
| `bad_title`, `bad_sub` | Unhappy path card |

Cues: `done`, `sms`, `stars`, `happy` (arrow draws), `good` (card arrives), `unhappy`, `bad`.

### chat_booking

A website in a browser window, with a chat widget: the visitor asks, the assistant replies, and a booking confirmation appears, followed by a day and night chip.

| Data | Description |
|---|---|
| `site` | Address shown in the browser bar |
| `header` | Chat widget header |
| `question`, `answer` | The two chat bubbles |
| `booked`, `booked_sub` | Booking card text |
| `clock` | Text of the day and night chip |

Cues: `site`, `chat`, `reply`, `book`, `clock`.

### content_reels

Three phone-shaped reels fan in, a carousel slides through its pages, and two chips appear.

| Data | Description |
|---|---|
| `images` | Three image paths shown in the reels, relative to the project folder |
| `reel_label` | Label in the corner of each reel |
| `slides` | Carousel page titles |
| `chip_a`, `chip_b` | The two chips |

Cues: `reels`, `carousel`, `a`, `b`.

### integrations_hub

Your mark sits in a hub. Four tiles slide in and plug into it, each connection turning green, then the hub glows.

| Data | Description |
|---|---|
| `tiles` | Up to four `{cue, label}` |
| `ok` | Chip under the hub when everything is connected |

Cues: `hub`, one per tile named by its `cue` value, and `ok`.

### phone_approve

A phone shows a list of things waiting for approval. A finger taps, every item turns approved, and a lock chip appears.

| Data | Description |
|---|---|
| `screen_title`, `screen_sub` | Phone screen heading |
| `items` | Three `[title, sub line]` rows |
| `approve`, `approved` | Button text before and after |
| `lock` | Lock chip text |

Cues: `phone`, `tap`, `approve`, `lock`.

### recap

Up to three big lines slam in one after another on a dark background. The last one uses a warm gradient.

| Data | Description |
|---|---|
| `lines` | Up to three lines |
| `last_gradient` | Optional CSS gradient for the last line |

Cues: `l1`, `l2`, `l3`, one per line.

### end_card

The logo pops in with confetti, the tagline appears, a large button bounces in, the web address types out, and a handwritten note settles at the bottom.

| Data | Description |
|---|---|
| `tagline` | Tagline. Put ` \| ` (space, bar, space) where the vertical cut should break the line. |
| `button` | Button text |
| `url` | Web address that types out |
| `note` | Optional handwritten note |

Cues: `logo`, `button`, `url`, `chord` (the final flourish).

### Layout

Every type lays itself out for both cuts. In landscape, the mascot stands on the left, the title sits top left, and the scene's panel fills the right. In vertical, the title is at the top, the panel in the middle, the caption below it and the mascot at the bottom. Long text can overflow its card: keep on-screen copy close in length to the example, and check the snapshots described in [Checks](#checks).

## Mascot poses

Each entry in `poses` describes one pose:

```json
"poses": {
  "wave": "waving hello with one hand raised, mid-step, cheerful",
  "headset": "wearing a slim call-centre headset, one hand touching the earpiece, the other giving a thumbs up"
}
```

The studio builds the full request for you, along these lines: "Exactly the same character as the reference image: [your description]. Keep proportions, colours, materials and face identical. Pose: [the pose]. Full body, centred, transparent or pure white background, no shadow, no text, no logos."

What happens with each provider:

- **Google** sends your mascot image and the request to the Gemini image model (`gemini-3.1-flash-image` by default; change it with `GOOGLE_IMAGE_MODEL` in `.env`). The result has no transparency, so the studio removes the background locally with rembg.
- **Higgsfield** sends them to GPT Image 2.5 through the CLI, asking for a transparent background directly. If an image still comes back without transparency, the studio removes the background locally.

Either way the pose is resized to 1400 pixels tall, placed on a consistent transparent canvas, and saved as WebP. Every pose shares the same canvas shape, so the mascot stands at a steady size from scene to scene.

Tips:

- Describe props and actions, not style. The style comes from your reference image.
- Say what should not appear, for example "no writing on the clipboard". Image models like to add text.
- If a cut-out shows a pale halo on dark backgrounds, regenerate that pose with `--cutout`, which always runs the local background removal.
- You can skip generation entirely by saving your own transparent WebP files as `projects/<name>/poses/<pose>.webp`.

## Transition clips

Transition clips are optional short pieces of generated video laid over a scene change, for example the mascot leaping and spinning just before the logo reveal.

```json
"transitions": [
  {
    "id": "reveal",
    "enabled": true,
    "scene": "S05",
    "align": "before",
    "seconds": 1.2,
    "from": 0.3,
    "pose": "jump",
    "bg": "paper",
    "prompt": "The mascot leaps up joyfully and spins once in place, static camera, no text"
  }
]
```

| Field | Description |
|---|---|
| `id` | Name of the clip |
| `enabled` | `false` keeps the entry but skips it |
| `scene` | The scene boundary the clip covers |
| `align` | `before` ends the clip as the scene starts, `center` straddles the cut, `after` starts with the scene |
| `seconds` | How much of the generated clip to use |
| `from` | Where in the generated clip to start, in seconds. Default 0.3, which skips the still opening frames. |
| `pose`, `bg` | The starting frame: this pose on this background's solid colour |
| `prompt` | What should happen in the clip |

Generate the clips, then rebuild:

```bash
python studio.py transitions acme
python studio.py all acme --offline
```

The studio composes a starting frame at each cut's aspect ratio and animates it: with Veo (`veo-3.1-fast-generate-preview` by default; change it with `GOOGLE_VIDEO_MODEL`) or with Kling 3.0 through the Higgsfield CLI. It then trims the result to `seconds`, fits it to the frame and removes its audio, because the mix owns the soundtrack. A clip that has not been generated is simply skipped and the normal colour wipe plays instead.

## Sound and music

### Sound effects

Sounds come from two places:

- `kit:` sounds are bundled in `assets/sfx-kit/`: short interface clicks, pops and chimes from Kenney's Interface Sounds (CC0). They are: back_001, click_001, click_003, close_001, confirmation_001, drop_001, glass_001, maximize_001, minimize_001, open_001, pluck_001, scratch_001, scroll_001, switch_001.
- `el:` sounds are generated by ElevenLabs from the prompts in `sfx`:

```json
"sfx": {
  "phone_ring": {"prompt": "modern smartphone ringtone, two short bright rings, clean, no music", "seconds": 1.6},
  "whoosh_a": {"prompt": "fast clean air whoosh transition, short", "seconds": 0.5}
}
```

Only sounds actually used by a cue are generated. A result that comes back silent is retried automatically, up to three times. Prompts, levels and attempts are recorded in `generated/sfx/provenance.json`.

### Music

```json
"music": {
  "bed_a": {"prompt": "Instrumental only, no vocals. Light underscore, 108 bpm, ...", "ms": 20000},
  "bed_b": {"prompt": "Instrumental only, no vocals. Bright upbeat launch music, 112 bpm, ...", "ms": 66000}
}
```

With a scene marked `turn`, the first bed plays from the start until the held beat, there is a moment of silence, and the second bed starts with the reveal and plays to the end, fading out over the last two seconds. Without a turn, a single bed plays under the whole video. Make the second bed at least as long as the part of the video after the turn. A bed that is too short is looped.

### The mix

The mix places every sound at its exact sample position and treats each layer separately:

- **Voice** is normalised so its peaks sit just under full scale.
- **Music** is set to a constant loudness (`audio.music_db`, default -26 dB) and ducks under the voice by `audio.duck_db` (default -9 dB) whenever the narrator speaks. The duck has a fast attack and a gentle release.
- **Sound effects** play at their cue's `gain`, plus a bus level for all effects (`audio.sfx_bus_db`, default +4 dB, which lifts them clear of the voice). Sounds listed in `audio.peak_align` are positioned by their loudest moment rather than their start, so the hit of a whoosh or a slam lands exactly on the cut. Leave longer, rolling sounds out of that list, or they will start noticeably early.
- **Limiter.** A soft limiter catches peaks above -3 dB, and the result is normalised to -1 dB.

After mixing, the build lists any cue whose sound is more than 14 dB below the voice and music around it, since such sounds may be hard to hear. Very short clicks often appear on that list even when they are audible, because the check measures average level over a quarter of a second. Listen before you change gains.

## Costs and caching

Paid media is stored in `projects/<name>/generated/` and reused on every build:

| Folder | Contains | Regenerated when |
|---|---|---|
| `generated/vo/` | One file per scene line | That line's text or the voice settings change, or you pass `--force` |
| `generated/sfx/` | One file per generated sound | You pass `--force --only <name>` |
| `generated/music/` | The two beds | You pass `--force --only bed_a` (or `bed_b`) |
| `generated/transitions/` | One clip per transition and cut | You pass `--force` to the transitions command |
| `poses/` | Mascot poses (committed to the repo) | You pass `--force` to the poses command |

`generated/` and `build/` are listed in `.gitignore`. Commit `generated/` only if you deliberately want to share the purchased media with your team.

For scale, the NanoFlow example uses about 3,000 characters of ElevenLabs voiceover, 32 generated sound effects and about 86 seconds of generated music. Pose and clip costs depend on your provider's pricing. Use `--offline` while you adjust copy, colours and timing, so builds make no API calls at all.

## Checks

`python studio.py all` and `python studio.py render` check each cut at two points:

**Before rendering**
- The page is opened in a headless browser. It must register its animation timeline and raise no JavaScript errors. This catches things like a cue name missing from project.json or a scene type with a typo.

**After rendering**
- The MP4 must decode from start to finish without errors, and must contain video and audio.
- A frame is taken every five seconds and tested for being blank. The frames are saved with a contact sheet at `build/frames-<cut>/sheet.png` for a quick visual review.

`python studio.py verify <name> --cues S02.missed,S14.l1` also measures how far apart the picture change and the sound onset are at those cues. The measurement looks for the biggest visual change and the sharpest sound in a short window, so it can occasionally latch onto a nearby spoken word or a wipe instead. Read it as a pointer, not a verdict.

To look at exact moments without rendering, use HyperFrames snapshots from a cut folder:

```bash
cd projects/acme/build/out/acme-16x9
node ../../../../../node_modules/hyperframes/bin/hyperframes.mjs snapshot . --at 2.5,10,30 --no-end
```

## Command reference

| Command | What it does |
|---|---|
| `python studio.py setup` | Saves keys and the provider choice to `.env`, installs the renderer and the Higgsfield CLI if needed, and tests everything |
| `python studio.py check` | Tests the saved keys or sign-in and the installed tools |
| `python studio.py new <name> --mascot <file> --logo <file> [--mark <file>] [--describe "<text>"]` | Creates a project from the NanoFlow template |
| `python studio.py voices` | Lists the voices on your ElevenLabs account |
| `python studio.py poses <name>` | Generates missing poses |
| `python studio.py transitions <name>` | Generates missing transition clips |
| `python studio.py build <name>` | Voice, sound, music, timing, mix and pages |
| `python studio.py render <name>` | Page check, render and video checks (run build first) |
| `python studio.py verify <name> [--cues a,b]` | Re-runs the checks on existing output |
| `python studio.py all <name>` | Build and render in one go |

Options:

| Option | Applies to | Description |
|---|---|---|
| `--cut landscape`, `--cut vertical`, `--cut both` | build, render, verify, all | Which cut to work on. Default both. |
| `--force` | poses, transitions, build, all | Regenerate paid media instead of reusing it |
| `--only a,b` | poses, transitions, build, all | Limit generation to these pose, clip or sound names |
| `--cutout` | poses | Always run local background removal |
| `--offline` | build, all | Use cached media only and make no API calls |
| `--quality draft`, `--quality looks`, `--quality delivery` | render, all | Encoding quality. Default looks. |

## Troubleshooting

**"Chrome cannot start" or the renderer hangs on Windows.** Install the headless shell: `python -m playwright install chromium-headless-shell`. You can also point HyperFrames at a specific browser with the `HYPERFRAMES_BROWSER_PATH` environment variable.

**"No browser for page checks".** Run `python -m playwright install chromium`. The check also falls back to an installed Chrome or Edge.

**"project.json cue problems".** The build lists each problem: a scene missing a cue its type needs, or a cue whose `at` word is not in the line. Words are matched from their start, ignoring case and punctuation, so `"answer"` matches "answers". Use `occ` when the word appears more than once.

**"Missing poses".** A scene uses a pose that has no file in `poses/`. Add it to `poses` in project.json and run the poses command, or rename the scene's `pose`.

**Text overflows a card.** On-screen copy has room for roughly what the example uses. Shorten the text, or adjust sizes in `engine/scenes.js`.

**A sound plays early.** If it is listed in `audio.peak_align`, it is positioned by its loudest moment. Remove it from that list for sounds that build slowly.

**Music cuts off or repeats.** Generate a longer bed: raise its `ms` and run `python studio.py build <name> --force --only bed_b`.

**Higgsfield says "Not authenticated" or "Session expired".** Sign in again with `tools/higgsfield/hf auth login`.

**Gemini models "NOT listed" in the check.** Model names change over time. Set `GOOGLE_IMAGE_MODEL` or `GOOGLE_VIDEO_MODEL` in `.env` to a model your key has access to.

**The render is slow.** Rendering uses your graphics card when one is available. Without one, expect a few minutes per minute of video. Use `--cut vertical` while iterating, since the vertical cut is shorter.

## Swapping providers

Every provider sits behind a small interface, so you can replace one without touching the rest of the pipeline.

**Voice, sound effects and music** live in `studio/elevenlabs.py`. A replacement needs four methods:

- `tts(...)`: returns the audio as MP3 bytes, plus word timings as a list of `{"w": word, "s": start seconds, "e": end seconds}`. Any text to speech service with word timestamps works. So does a local voice model followed by a word-level transcription tool such as faster-whisper.
- `sfx(...)` and `music(...)`: write MP3 files.
- `check()`: returns a status line.

**Poses and clips** live in `studio/providers.py`. Add a class with three methods and return it from `get()` for a new `MEDIA_PROVIDER` value:

- `check()`: returns a status line.
- `image(ref_png, prompt, dst, aspect)`: writes an image to `dst`.
- `video(start_png, prompt, dst, aspect, seconds)`: writes an MP4 to `dst`.

**The renderer** is HyperFrames, called from `studio/render.py`. The pages it renders are ordinary HTML with a paused GSAP timeline registered as `window.__timelines.main`, so any tool that can seek a page frame by frame can render them.

## Repo layout

```
studio.py                  command line entry point
studio/
  common.py                paths, .env handling, project loading, HTTP helpers
  elevenlabs.py            ElevenLabs client: voice with word timings, sound effects, music
  providers.py             Google (Gemini, Veo) and Higgsfield (CLI) providers
  media.py                 mascot poses and transition clips
  vo.py                    voiceover per line, assembled per cut
  beats.py                 cue resolution and validation, sound sheets
  audio.py                 sound effect and music generation
  mix.py                   the mix
  cuts.py                  builds the HTML page for each cut
  render.py                runs the pinned renderer
  verify.py                page, frame and sync checks
engine/
  template.html            page template
  scenes.js                the scene library: layouts, motion, captions
assets/
  fonts/                   DM Sans, Nunito, Caveat, with licences
  sfx-kit/                 Kenney interface sounds, with licence
projects/
  nanoflow/
    project.json           the example video
    mascot/ poses/ brand/ images/
    generated/             purchased media cache (git-ignored)
    build/                 build output and renders (git-ignored)
package.json               pinned HyperFrames and GSAP
requirements.txt           Python packages
.env.example               template for your keys
```

## Licences

- **Code** in this repository is released under the MIT licence. See `LICENSE`.
- **Fonts** in `assets/fonts/` are under the SIL Open Font License 1.1. The licence files are included alongside them.
- **Interface sounds** in `assets/sfx-kit/` are CC0 (public domain), from [Kenney](https://kenney.nl/assets/interface-sounds).
- **HyperFrames** (Apache 2.0) and **GSAP** (GreenSock Standard "no charge" licence) are installed by `npm install` under their own licences and are not part of this repository.
- **Generated media**, meaning the voice, sound effects, music, poses and clips you create, is governed by the terms of the provider that generated it.
- **NanoFlow example assets.** The NanoFlow name, logo, mascot artwork and photographs in `projects/nanoflow/` belong to NanoFlow. They are included as an example only and are not covered by the MIT licence. Please do not use them in your own videos.
