"""Owner Featured reel steps after the draft: one command per step, each refusing to run before its approval gate.

    python -m studio.owner_steps gate     <project> <gate> --words "<the person's own words>" [--file F]
    python -m studio.owner_steps keyframe <project> --prompt-file F            (paid: Higgsfield 2 credits)
    python -m studio.owner_steps animate  <project> --prompt-file F            (paid: Higgsfield 8.75 credits)
    python -m studio.owner_steps voice    <project>                            (paid: ElevenLabs, 0.5 credit/character)
    python -m studio.owner_steps argil    <project>                            (paid: one Argil clip)
    python -m studio.owner_steps assemble <project> --middle <studio project>  (local)
    python -m studio.owner_steps review   <project>                            (local: Studio review copy + link check)
    python -m studio.owner_steps status   <project>

    python -m studio.owner_steps close-draft   <tenant> <project> --line "<close line>"   (new business: saved close)
    python -m studio.owner_steps close-compose <project> [--style bar|italic|split]       (local, after voice + argil)
    python -m studio.owner_steps close-restyle <tenant> <project> --style S               (local: new card, same talking head)
    python -m studio.owner_steps close-save    <project>                                  (after gate close)

Gates, in order: quote -> (storyboard, narration: Field Notes middle, in the Studio) -> keyframe -> voice -> final.
A gate is recorded only with the person's own approving words. No step repeats a paid call: a retake needs
--retake --words "<the person asking for it>" and is a new quote. Narration is never time-stretched; if the talking
head and its audio differ in length, the video is retimed to the audio."""
import argparse, json, re, secrets, shlex, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

from .owner_featured import FORMAT_DIR, WORK, sha256

GATES = ("quote", "storyboard", "narration", "keyframe", "voice", "final", "close")
STUDIO = Path("/home/adam/video-studio")
NEEDS = {"keyframe": ["quote"], "animate": ["quote", "keyframe"], "voice": ["quote"], "argil": ["quote", "voice"],
         "assemble": ["quote", "keyframe", "voice"], "close-compose": ["quote", "voice"], "close-save": ["close"]}
COST = {"keyframe": {"higgsfield_credits": 2}, "animate": {"higgsfield_credits": 8.75}, "argil": {"argil_clips": 1}}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fail(msg, **kw):
    raise SystemExit(json.dumps({"ok": False, "error": msg, **kw}, ensure_ascii=False))


class Project:
    def __init__(self, name, work=WORK):
        self.dir = Path(work) / name
        self.name = name
        if not (self.dir / "draft.json").exists():
            fail(f"no draft for {name}: run studio.owner_featured draft first")
        self.draft = json.loads((self.dir / "draft.json").read_text(encoding="utf-8"))
        sp = self.dir / "state.json"
        self.state = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {"gates": {}, "steps": {}, "spend": []}
        self.tenant = json.loads((FORMAT_DIR / "tenants" / f"{self.draft['tenant']}.json").read_text(encoding="utf-8"))
        self.fmt = json.loads((FORMAT_DIR / "format.json").read_text(encoding="utf-8"))

    def save(self):
        (self.dir / "state.json").write_text(json.dumps(self.state, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    def need(self, step):
        needs = list(NEEDS.get(step, []))
        if step == "assemble" and not (self.draft["parts"][2].get("reuse")):
            needs += ["storyboard", "narration"]          # a new Field Notes middle is approved in the Studio first
        missing = [g for g in needs if g not in self.state["gates"]]
        if missing:
            fail(f"{step} waits for the person's approval at: {', '.join(missing)}", next="show the person what the gate covers; record it with `gate` only after they approve")

    def once(self, step, retake, words):
        if step in self.state["steps"] and not retake:
            fail(f"{step} already ran ({self.state['steps'][step].get('file')}); no automatic retakes",
                 next="only if the person asks for a retake: quote it, then rerun with --retake --words \"<their words>\"")
        if retake and not words:
            fail("--retake needs --words with the person's request")

    def done(self, step, file, cost=None, words=None, **extra):
        self.state["steps"][step] = {"file": str(file), "sha256": sha256(file) if Path(file).is_file() else None, "at": now(), **extra}
        if cost:
            self.state["spend"].append({"step": step, "at": now(), **cost, **({"retake_request": words} if words else {})})
        self.save()

    def file(self, step):
        s = self.state["steps"].get(step)
        return Path(s["file"]) if s else None


def gate(p, name, words, file=None):
    if name not in GATES:
        fail(f"gate must be one of {', '.join(GATES)}")
    if not words or len(words.strip()) < 2:
        fail("a gate needs the person's own approving words")
    if name == "keyframe" and not p.file("keyframe"):
        fail("no keyframe to approve yet")
    if name == "voice" and not p.file("voice"):
        fail("no owner voice to approve yet")
    if name == "close" and not p.file("close-compose"):
        fail("no close to approve yet")
    if name == "final" and not p.file("assemble"):
        fail("no assembled reel to approve yet")
    p.state["gates"][name] = {"words": words.strip(), "at": now(), **({"file": str(file), "sha256": sha256(file)} if file else {})}
    p.save()
    return {"ok": True, "gate": name, "recorded": p.state["gates"][name]}


# ---- paid steps -------------------------------------------------------------------------------------------------

def hf():
    from .providers import hf_bin
    b = hf_bin() or fail("Higgsfield CLI not found")
    return b


def hf_run(*args, timeout=2400):
    import os
    r = subprocess.run([hf(), *args, "--json"], capture_output=True, text=True, timeout=timeout,
                       env={**os.environ, "HIGGSFIELD_DISABLE_TELEMETRY": "1"})
    if r.returncode:
        fail(f"Higgsfield: {(r.stderr or r.stdout)[-500:]}")
    return r.stdout


def result_url(out, exts):
    urls = re.findall(r"https://[^\s\"']+", out)
    for u in urls:
        if any(u.split("?")[0].lower().endswith(e) for e in exts) and "_min." not in u:
            return u
    fail("no result URL in the Higgsfield output")


def download(url, dst):
    from .providers import download as dl
    return dl(url, dst)


def keyframe(p, prompt, retake=False, words=None):
    p.need("keyframe"); p.once("keyframe", retake, words)
    d = p.dir / "keyframe"; d.mkdir(exist_ok=True)
    (d / f"prompt-{int(time.time())}.txt").write_text(prompt, encoding="utf-8")
    out = hf_run("generate", "create", "nano_banana_2", "--prompt", prompt, "--aspect_ratio", "9:16", "--resolution", "2k",
                 "--wait", "--wait-timeout", "15m")
    (d / f"create-{int(time.time())}.json").write_text(out, encoding="utf-8")
    f = download(result_url(out, (".png", ".jpg", ".jpeg", ".webp")), d / f"keyframe-{secrets.token_hex(4)}.png")
    p.done("keyframe", f, COST["keyframe"], words)
    p.state["gates"].pop("keyframe", None); p.save()
    return {"ok": True, "keyframe": str(f), "next": "show the still; record gate keyframe only when the person approves it"}


def animate(p, prompt, retake=False, words=None):
    p.need("animate"); p.once("animate", retake, words)
    kf = Path(p.state["gates"]["keyframe"].get("file") or p.file("keyframe"))
    d = p.dir / "scene1"; d.mkdir(exist_ok=True)
    (d / f"prompt-{int(time.time())}.txt").write_text(prompt, encoding="utf-8")
    out = hf_run("generate", "create", "kling3_0", "--prompt", prompt, "--start-image", str(kf), "--aspect_ratio", "9:16",
                 "--duration", "5", "--mode", "pro", "--sound", "off", "--wait", "--wait-timeout", "30m")
    (d / f"create-{int(time.time())}.json").write_text(out, encoding="utf-8")
    f = download(result_url(out, (".mp4", ".mov", ".webm")), d / f"kling-{secrets.token_hex(4)}.mp4")
    p.done("animate", f, COST["animate"], words)
    return {"ok": True, "animation": str(f)}


def voice_lines(p):
    if p.draft.get("kind") == "close":
        return {"close": p.draft["line"]}
    return {"hook": p.draft["parts"][0]["voiceover"], "intro": p.draft["parts"][1]["line"]}


def voice(p, retake=False, words=None):
    p.need("voice"); p.once("voice", retake, words)
    from .common import load_env
    from .elevenlabs import ElevenLabs
    key = load_env().get("ELEVENLABS_API_KEY") or fail("ELEVENLABS_API_KEY is missing")
    v = p.tenant["voice"]
    d = p.dir / "audio"; d.mkdir(exist_ok=True)
    files, chars = {}, 0
    for name, text in voice_lines(p).items():
        audio, wl = ElevenLabs(key).tts(v["voice_id"], v["model"], text, v["settings"])   # one take; pace = the speed setting
        tag = secrets.token_hex(3)
        (d / f"{name}-{tag}.mp3").write_bytes(audio)
        (d / f"{name}-{tag}.json").write_text(json.dumps({"text": text, "voice_id": v["voice_id"], "model": v["model"],
                                                           "settings": v["settings"], "words": wl}, indent=1) + "\n", encoding="utf-8")
        files[name] = str(d / f"{name}-{tag}.mp3"); chars += len(text)
    p.done("voice", d, {"elevenlabs_credits": chars * 0.5}, words, files=files, characters=chars)
    p.state["gates"].pop("voice", None); p.save()
    return {"ok": True, "files": files, "characters": chars, "next": "send the files; record gate voice only when the person approves"}


def argil(p, retake=False, words=None):
    p.need("argil"); p.once("argil", retake, words)
    a = p.tenant["argil"]; run = a.get("runner") or fail("the business profile has no argil.runner")
    line = "close" if p.draft.get("kind") == "close" else "intro"
    src = Path(p.state["steps"]["voice"]["files"][line])
    folder = f"{p.name}-{secrets.token_hex(3)}"
    ssh = ["ssh", "-i", run["ssh_key"], "-o", "IdentitiesOnly=yes", run["ssh"]]
    subprocess.run(ssh + [f"mkdir -p {shlex.quote(run['media_dir'] + '/' + folder)}"], check=True)
    subprocess.run(["scp", "-q", "-i", run["ssh_key"], "-o", "IdentitiesOnly=yes", str(src),
                    f"{run['ssh']}:{run['media_dir']}/{folder}/{line}.mp3"], check=True)
    url = f"{run['media_url']}/{folder}/{line}.mp3"
    remote_out = f"{run['media_dir']}/{folder}/{line}-argil.mp4"
    script = ARGIL_SCRIPT.format(env=shlex.quote(run["env_file"]), key=run.get("env_key", "ARGIL_API_KEY"), avatar=a["avatar_id"],
                                 audio=url, name=f"{p.tenant['tenant']}-owner-featured-{line}-{int(time.time())}", out=shlex.quote(remote_out))
    r = subprocess.run(ssh + ["bash -s"], input=script, capture_output=True, text=True, timeout=3600)
    if r.returncode:
        fail(f"Argil: {(r.stdout + r.stderr)[-600:]}")
    d = p.dir / "argil"; d.mkdir(exist_ok=True)
    f = d / f"{line}-{folder}.mp4"
    subprocess.run(["scp", "-q", "-i", run["ssh_key"], "-o", "IdentitiesOnly=yes", f"{run['ssh']}:{remote_out}", str(f)], check=True)
    p.done("argil", f, COST["argil"], words, argil=r.stdout.strip()[-300:])
    return {"ok": True, "talking_head": str(f)}


# Runs on the business's server, where its Argil key lives: create, render, poll until DONE, download, delete. No retries.
ARGIL_SCRIPT = r"""set -eu
K=$(grep -h "^{key}=" {env} | head -1 | cut -d= -f2- | tr -d "\"'")
api(){{ curl -sf -X "$1" -H "x-api-key: $K" -H "Content-Type: application/json" "https://api.argil.ai$2" ${{3:+-d "$3"}}; }}
v=$(api POST /v1/videos '{{"name":"{name}","moments":[{{"avatarId":"{avatar}","audioUrl":"{audio}"}}]}}')
id=$(echo "$v" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
api POST /v1/videos/$id/render '{{}}' > /dev/null
for i in $(seq 1 180); do
  s=$(api GET /v1/videos/$id); st=$(echo "$s" | python3 -c 'import json,sys;print(json.load(sys.stdin).get("status",""))')
  [ "$st" = "DONE" ] && break
  case "$st" in FAILED|ERROR|CANCELLED) echo "argil $id $st"; exit 1;; esac
  sleep 10
done
[ "$st" = "DONE" ] || {{ echo "argil $id still $st after 30 min"; exit 1; }}
u=$(echo "$s" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get("videoUrl") or d.get("url") or "")')
curl -sfL -o {out} "$u"
api DELETE /v1/videos/$id > /dev/null || true
echo "argil $id done"
"""


# ---- local steps ------------------------------------------------------------------------------------------------

def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *map(str, args)], check=True)


def probe(f, entries="format=duration"):
    return subprocess.run(["ffprobe", "-v", "error", "-show_entries", entries, "-of", "json", str(f)],
                          capture_output=True, text=True, check=True).stdout


def duration(f):
    return float(json.loads(probe(f))["format"]["duration"])


def loudness(f):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(f), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"^\s+I:\s+(-?[\d.]+) LUFS", r.stderr, re.M)
    return float(m[-1]) if m else None


def peaks(f):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(f), "-af", "astats=measure_overall=none:measure_perchannel=Peak_level",
                        "-f", "null", "-"], capture_output=True, text=True)
    return [float(x) for x in re.findall(r"Peak level dB:\s*(-?[\d.]+|-inf)", r.stderr) if x != "-inf"]


def enc_args(ref):
    s = json.loads(probe(ref, "stream=codec_type,profile,level,time_base,sample_rate,channels"))["streams"]
    v = next(x for x in s if x["codec_type"] == "video")
    ts = v["time_base"].split("/")[1]
    level = {40: "4.0", 41: "4.1", 42: "4.2", 31: "3.1", 32: "3.2", 50: "5.0", 51: "5.1"}.get(v.get("level"), "4.0")
    return ["-c:v", "libx264", "-profile:v", "high", "-level", level, "-pix_fmt", "yuv420p", "-r", "30", "-crf", "16",
            "-preset", "slow", "-video_track_timescale", ts, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


def talking_head_filter(f):
    s = json.loads(probe(f, "stream=width,height"))["streams"]
    w, h = next((x["width"], x["height"]) for x in s if "width" in x)
    if w > h:   # Argil returns portrait looks pillarboxed in 2560x1440
        return "crop=808:1438:876:0,scale=1080:1920:flags=lanczos,setsar=1"
    return "scale=1080:1920:flags=lanczos,setsar=1"


def middle_render(name):
    f = STUDIO / "projects" / name / "build" / "out" / f"{name}-9x16" / "renders" / f"{name}-9x16.mp4"
    return f if f.exists() else None


def assemble(p, middle):
    p.need("assemble")
    mid = middle_render(middle) or fail(f"no render for Studio project {middle}")
    for step in ("animate", "voice", "argil"):
        if not p.file(step):
            fail(f"{step} has not run")
    kf_ok = p.state["gates"]["keyframe"]
    close = Path(p.tenant["close"]["dir"]) / p.tenant["close"]["clip"]
    if sha256(close) != p.tenant["close"]["sha256"]:
        fail("the saved close failed its checksum")
    mus = p.tenant.get("music") or p.fmt["music"]["default_bed"]
    if sha256(mus["file"]) != mus["sha256"]:
        fail("the music bed failed its checksum")
    b = p.dir / "build"; b.mkdir(exist_ok=True)
    enc = enc_args(mid)
    target = loudness(mid)
    files = p.state["steps"]["voice"]["files"]
    # part 1: the reaction with the owner's line over it (0.2 s lead), held at least 4 s
    hook_d = duration(files["hook"])
    l1 = round(min(5.0, max(4.0, 0.2 + hook_d + 1.6)), 2)
    g1 = round(target - loudness(files["hook"]), 2) if target else 0
    ff("-i", p.file("animate"), "-i", files["hook"], "-filter_complex",
       f"[0:v]trim=0:{l1},setpts=PTS-STARTPTS,scale=1080:1920:flags=lanczos,setsar=1,fps=30,format=yuv420p[v];"
       f"[1:a]aresample=48000,adelay=200:all=1,volume={g1}dB,apad=whole_dur={l1},atrim=0:{l1},aformat=channel_layouts=stereo[a]",
       "-map", "[v]", "-map", "[a]", "-t", l1, *enc, b / "part1.mp4")
    # part 2: the talking head with its own audio; video retimed to the audio if Argil's length differs
    th, intro = p.file("argil"), files["intro"]
    ad, vd = duration(intro), duration(th)
    k = ad / vd if abs(ad - vd) > 0.04 else 1.0
    g2 = round(target - loudness(intro), 2) if target else 0
    ff("-i", th, "-i", intro, "-filter_complex",
       f"[0:v]{talking_head_filter(th)},setpts={k:.5f}*PTS,fps=30,format=yuv420p[v];"
       f"[1:a]aresample=48000,volume={g2}dB,apad=whole_dur={ad},aformat=channel_layouts=stereo[a]",
       "-map", "[v]", "-map", "[a]", "-t", round(ad, 3), *enc, b / "part2.mp4")
    # part 3 is stream-copied; part 4 (the saved close) gets a fixed gain to the middle's loudness
    g4 = round(target - loudness(close), 2) if target else 0
    same = lambda f: json.loads(probe(f, "stream=codec_type,time_base,profile,width,height"))["streams"][0]
    vcopy = ["-c:v", "copy"] if same(close) == same(mid) else enc[:enc.index("-c:a")]
    ff("-i", close, *vcopy, "-af", f"volume={g4}dB,aresample=48000", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", b / "part4.mp4")
    lst = b / "concat.txt"
    lst.write_text("".join(f"file '{x}'\n" for x in (b / "part1.mp4", b / "part2.mp4", mid, b / "part4.mp4")), encoding="utf-8")
    dry = b / "reel-no-music.mp4"
    ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", dry)
    # music: one bed under everything, ducked by the reel's own speech, out after the last spoken word
    m = p.fmt["music"]; dk = m["duck"]
    total = duration(dry)
    starts = [0, l1, l1 + ad, l1 + ad + duration(mid)]
    last_word = starts[3] + p.tenant["close"].get("timing", {}).get("speech_end_s", duration(close) - 2.0)
    fo = round(last_word + 0.15, 3)
    final = b / f"{p.name}.mp4"
    ff("-i", dry, "-stream_loop", "-1", "-i", mus["file"], "-filter_complex",
       f"[1:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total},volume={m['bed_gain_db']}dB,"
       f"afade=t=in:d={m['fade_in_s']},afade=t=out:st={fo}:d={round(total - fo, 3)}[bed];"
       f"[0:a]asplit[sp][key];[bed][key]sidechaincompress=threshold={dk['threshold']}:ratio={dk['ratio']}:attack={dk['attack_ms']}:"
       f"release={dk['release_ms']}:knee={dk['knee']}[duck];[sp][duck]amix=inputs=2:normalize=0:duration=first[a]",
       "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", final)
    pk = peaks(final)
    trim = 0.0
    if pk and max(pk) > -1.0:   # one fixed trim of the whole mix (no limiter), so the sample peak lands at -1.05 dBFS
        trim = round(-1.05 - max(pk), 2)
        tmp = b / "trim.mp4"
        ff("-i", final, "-c:v", "copy", "-af", f"volume={trim}dB", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", tmp)
        tmp.replace(final)
        pk = peaks(final)
    checks = {"duration_s": round(duration(final), 3), "peak_dbfs_per_channel": pk, "peak_ok": bool(pk) and max(pk) <= -1.0,
              "talking_head_retimed": round(k, 4), "whole_mix_trim_db": trim, "gains_db": {"hook": g1, "intro": g2, "close": g4}, "middle_lufs": target}
    manifest = {"schema": "owner-featured-build.v2", "project": p.name, "tenant": p.tenant["tenant"], "at": now(),
                "parts": {"1": str(b / "part1.mp4"), "2": str(b / "part2.mp4"), "3": {"file": str(mid), "sha256": sha256(mid)},
                          "4": {"file": str(close), "sha256": p.tenant["close"]["sha256"]}},
                "music": {"file": mus["file"], "sha256": mus["sha256"]}, "final": {"file": str(final), "sha256": sha256(final)},
                "checks": checks, "keyframe_approval": kf_ok}
    (b / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    p.done("assemble", final, None, None, checks=checks)
    return {"ok": True, "final": str(final), "checks": checks,
            "next": "review copy with `review`; if peak_ok is false, tell the person (no limiter is added)"}


def review(p, name=None):
    f = p.file("assemble") or p.file("close-compose") or fail("nothing assembled yet")
    n = name or f"{p.name}-v1"
    while (STUDIO / "projects" / n).exists():
        m = re.match(r"(.*)-v(\d+)$", n)
        n = f"{m.group(1)}-v{int(m.group(2)) + 1}" if m else f"{n}-v2"
    d = STUDIO / "projects" / n
    (d / "build" / "out" / f"{n}-9x16" / "renders").mkdir(parents=True)
    (d / "media").mkdir()
    shutil.copy(f, d / "build" / "out" / f"{n}-9x16" / "renders" / f"{n}-9x16.mp4")
    v = p.tenant["voice"]
    (d / "project.json").write_text(json.dumps({"name": n, "title": f"{p.draft.get('title') or p.name} (Owner Featured review draft)",
        "style": "entertainment", "layout": "footage", "_note": "Assembled review file; not buildable here.",
        "voice": {"voice_id": v["voice_id"], "model": v["model"], "settings": {}}, "scenes": []}, indent=1) + "\n", encoding="utf-8")
    (d / "review-of.json").write_text(json.dumps({"owner_featured": p.name, "file": str(f), "sha256": sha256(f), "at": now()}, indent=1) + "\n")
    p.state.setdefault("reviews", []).append(n); p.save()
    return {"ok": True, "review": n, "url": f"https://techbots.io/admin/gtm/video-studio/{n}", "link_check": link_check(n)}


def link_check(n):
    """The admin media route answers 206 for a signed-in admin and 401 without one. The 5-minute token is never printed."""
    js = r"""const fs=require("fs");const env=Object.fromEntries(fs.readFileSync("/home/adam/techbots-platform/.env","utf8").split("\n")
      .filter(l=>l.includes("=")&&!l.startsWith("#")).map(l=>{const i=l.indexOf("=");return[l.slice(0,i).trim(),l.slice(i+1).trim().replace(/^["']|["']$/g,"")]}));
      const t=require("/home/adam/techbots-platform/node_modules/jsonwebtoken").sign({sub:"nano-check",email:"bobby@nanoflow.io",role:"high_tier"},env.JWT_SECRET,{expiresIn:"5m"});
      const u="http://127.0.0.1:"+(env.PORT||3000)+"/api/admin/gtm/video/projects/"+process.argv[1]+"/media/vertical/video";
      Promise.all([fetch(u,{headers:{Authorization:"Bearer "+t,Range:"bytes=0-99"}}),fetch(u)]).then(([a,b])=>console.log(JSON.stringify({signed_in:a.status,anonymous:b.status})))"""
    r = subprocess.run(["node", "-e", js, n], capture_output=True, text=True, timeout=60)
    try:
        s = json.loads(r.stdout.strip())
        return {**s, "verified": s["signed_in"] == 206 and s["anonymous"] == 401}
    except Exception:
        return {"verified": False, "error": (r.stderr or r.stdout)[-200:]}


# ---- saved close (once per business) -----------------------------------------------------------------------------

def close_draft(tenant, project, line, work=WORK):
    from .owner_profile import check
    d = Path(work) / project
    if d.exists():
        fail(f"{project} exists")
    d.mkdir(parents=True)
    chars = len(line)
    draft = {"schema": "owner-featured-close-draft.v1", "kind": "close", "tenant": tenant, "project": project, "line": line,
             "created": now(), "quote": {"elevenlabs_credits": chars * 0.5, "argil_clips": 1, "provider_charges_usd": 0.0},
             "profile": check(tenant)}
    (d / "draft.json").write_text(json.dumps(draft, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True, **draft}


def close_layers_and_compose(p_or_tenant, raw, out_dir, style, speech_words=None, timing=None):
    from . import owner_card as oc
    prof = p_or_tenant
    card, num = oc.save_layers(prof, out_dir, style)
    if timing is None:
        ws = speech_words
        norm = lambda w: re.sub(r"[^a-z]", "", w.lower())
        name0 = norm(prof["business_name"].split()[0])
        first_digit = norm(prof["contact_number"]["spoken"].split()[0])
        logo_in = next((w["s"] for w in ws if norm(w["w"]) == name0), 1.5)
        number_in = next((w["s"] for w in ws if norm(w["w"]) == first_digit and w["s"] > logo_in), logo_in + 1.5)
        end = ws[-1]["e"]
        timing = {"logo_in_s": round(logo_in, 2), "number_in_s": round(number_in, 2), "speech_end_s": round(end, 2), "duration_s": round(end + 2.0, 2)}
    f = Path(out_dir) / "close.mp4"
    oc.compose_close(raw, card, num, f, timing["logo_in_s"], timing["number_in_s"], timing["duration_s"])
    return f, timing


def close_compose(p, style=None):
    p.need("close-compose")
    raw_src = p.file("argil") or fail("argil has not run")
    style = style or (p.tenant.get("brand") or {}).get("card_style") or "bar"
    out = p.dir / "close"; out.mkdir(exist_ok=True)
    raw = out / "talking-head-raw.mp4"
    ff("-i", raw_src, "-i", p.state["steps"]["voice"]["files"]["close"], "-filter_complex",
       f"[0:v]{talking_head_filter(raw_src)},fps=30,format=yuv420p[v];[1:a]aresample=48000,aformat=channel_layouts=stereo[a]",
       "-map", "[v]", "-map", "[a]", "-shortest", "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-c:a", "aac", "-b:a", "192k", raw)
    vf = Path(p.state["steps"]["voice"]["files"]["close"]).with_suffix(".json")
    words = json.loads(vf.read_text(encoding="utf-8"))["words"]
    f, timing = close_layers_and_compose(p.tenant, raw, out, style, speech_words=words)
    p.done("close-compose", f, None, None, style=style, timing=timing, raw=str(raw))
    return {"ok": True, "close": str(f), "style": style, "timing": timing, "next": "review copy, then gate close when the person approves"}


def close_restyle(tenant, project, style, work=WORK):
    """A new card on the business's existing approved talking head (free). Becomes the saved close only after gate close."""
    prof = json.loads((FORMAT_DIR / "tenants" / f"{tenant}.json").read_text(encoding="utf-8"))
    src = Path(prof["close"]["dir"])
    raw = next(iter(sorted(src.glob("*-raw.mp4"))), None) or fail("no raw talking head saved with the current close")
    d = Path(work) / project
    if d.exists():
        fail(f"{project} exists")
    (d / "close").mkdir(parents=True)
    draft = {"schema": "owner-featured-close-draft.v1", "kind": "close", "tenant": tenant, "project": project, "restyle_of": prof["close"]["id"],
             "line": json.loads((src / "speech.json").read_text())["text"] if (src / "speech.json").exists() else None, "created": now(),
             "quote": {"provider_charges_usd": 0.0, "note": "local render only"}}
    (d / "draft.json").write_text(json.dumps(draft, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    p = Project(project, work)
    f, timing = close_layers_and_compose(prof, raw, d / "close", style, timing=prof["close"].get("timing"))
    p.state["gates"]["quote"] = {"words": "restyle is free (local render)", "at": now()}
    p.done("close-compose", f, None, None, style=style, timing=timing, raw=str(raw))
    return {"ok": True, "close": str(f), "style": style, "next": "review copy, then gate close when the person approves"}


def close_save(p):
    p.need("close-save")
    st = p.state["steps"]["close-compose"]
    prof_path = FORMAT_DIR / "tenants" / f"{p.tenant['tenant']}.json"
    prof = json.loads(prof_path.read_text(encoding="utf-8"))
    base = Path(prof["close"]["dir"]).parent
    n = 1
    while (base / f"{prof['tenant']}-close-v{n}").exists():
        n += 1
    dst = base / f"{prof['tenant']}-close-v{n}"
    dst.mkdir(parents=True)
    shutil.copy(st["file"], dst / f"close-v{n}.mp4")
    shutil.copy(st["raw"], dst / f"{prof['tenant']}-close-raw.mp4")
    for x in ("layer-card-logo.png", "layer-number.png"):
        shutil.copy(Path(st["file"]).parent / x, dst / x)
    if (Path(prof["close"]["dir"]) / "speech.json").exists() and p.draft.get("restyle_of"):
        shutil.copy(Path(prof["close"]["dir"]) / "speech.json", dst / "speech.json")
    man = {"schema": "owner-featured-close.v1", "id": dst.name, "tenant": prof["tenant"], "card_style": st["style"], "timing": st["timing"],
           "status": f"approved for reuse: {p.state['gates']['close']['words']} ({p.state['gates']['close']['at'][:10]})",
           "previous": prof["close"].get("id"), "files": {f.name: {"sha256": sha256(f)} for f in dst.iterdir()}}
    (dst / "manifest.json").write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    prof.setdefault("close_history", []).append({k: prof["close"].get(k) for k in ("id", "dir", "clip", "sha256", "approved")})
    prof["close"].update({"id": dst.name, "dir": str(dst), "clip": f"close-v{n}.mp4", "sha256": sha256(dst / f"close-v{n}.mp4"),
                          "approved": man["status"], "timing": st["timing"]})
    prof.setdefault("brand", {})["card_style"] = st["style"]
    prof_path.write_text(json.dumps(prof, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"ok": True, "saved_close": str(dst), "profile": str(prof_path), "previous_close_kept": prof["close_history"][-1]["dir"]}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="owner_steps")
    ap.add_argument("action", choices=["gate", "keyframe", "animate", "voice", "argil", "assemble", "review", "status",
                                       "close-draft", "close-compose", "close-restyle", "close-save"])
    ap.add_argument("a1"); ap.add_argument("a2", nargs="?")
    ap.add_argument("--words"); ap.add_argument("--file"); ap.add_argument("--prompt-file"); ap.add_argument("--middle")
    ap.add_argument("--retake", action="store_true"); ap.add_argument("--line"); ap.add_argument("--style"); ap.add_argument("--name")
    a = ap.parse_args(argv)
    if a.action == "close-draft":
        out = close_draft(a.a1, a.a2 or fail("close-draft <tenant> <project>"), a.line or fail("--line is required"))
    elif a.action == "close-restyle":
        out = close_restyle(a.a1, a.a2 or fail("close-restyle <tenant> <project>"), a.style or fail("--style is required"))
    else:
        p = Project(a.a1)
        prompt = Path(a.prompt_file).read_text(encoding="utf-8").strip() if a.prompt_file else None
        out = {"gate": lambda: gate(p, a.a2, a.words, a.file),
               "keyframe": lambda: keyframe(p, prompt or fail("--prompt-file is required"), a.retake, a.words),
               "animate": lambda: animate(p, prompt or fail("--prompt-file is required"), a.retake, a.words),
               "voice": lambda: voice(p, a.retake, a.words), "argil": lambda: argil(p, a.retake, a.words),
               "assemble": lambda: assemble(p, a.middle or fail("--middle <studio project> is required")),
               "review": lambda: review(p, a.name), "close-compose": lambda: close_compose(p, a.style),
               "close-save": lambda: close_save(p),
               "status": lambda: {"project": p.name, "gates": list(p.state["gates"]), "steps": list(p.state["steps"]), "spend": p.state["spend"]},
               }[a.action]()
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
