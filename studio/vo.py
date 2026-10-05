"""Voiceover: one ElevenLabs request per scene line (with neighbouring text for natural flow), then two cuts
assembled on their own clocks. Lines are cached in generated/vo/ by a hash of their text + voice settings,
so editing one line only re-buys that line."""
import hashlib, json
from .common import ffmpeg, SR
from .elevenlabs import ElevenLabs


def line_key(p, text):
    v = p.data["voice"]
    return hashlib.sha1(json.dumps([text, v["voice_id"], v["model"], v.get("settings")], sort_keys=True).encode()).hexdigest()[:10]


def generate(p, env, force=False):
    el = ElevenLabs(env["ELEVENLABS_API_KEY"])
    v = p.data["voice"]; d = p.gen / "vo"; d.mkdir(exist_ok=True)
    scenes = p.scenes()
    texts = [s["line"]["text"] for s in scenes]
    for i, s in enumerate(scenes):
        key = line_key(p, s["line"]["text"])
        mp3, js = d / f"{s['id']}-{key}.mp3", d / f"{s['id']}-{key}.json"
        if mp3.exists() and js.exists() and not force:
            continue
        audio, words = el.tts(v["voice_id"], v["model"], s["line"]["text"], v.get("settings", {}),
                              " ".join(texts[max(0, i - 2):i]), texts[i + 1] if i + 1 < len(texts) else "")
        mp3.write_bytes(audio)
        js.write_text(json.dumps({"text": s["line"]["text"], "words": words}, indent=1), encoding="utf-8")
        print(f"  vo {s['id']}: {len(words)} words, {words[-1]['e']:.2f} s")


DRY_WPS = 2.6   # synthetic speaking rate for --dry-timings (words per second)


def dry_words(text):
    """Fake word timings for a layout preview: evenly spaced at DRY_WPS, no voice involved."""
    return [{"w": w, "s": round(0.04 + i / DRY_WPS, 3), "e": round(0.04 + i / DRY_WPS + 0.85 / DRY_WPS, 3)}
            for i, w in enumerate(text.split())]


def assemble(p, cut, dry=False):
    """Join the cached line recordings onto this cut's clock. dry=True fakes the word timings and writes silence
    instead (layout preview only: no generated voice is read and no API is called)."""
    v = p.data["voice"]; d = p.gen / "vo"; out = p.build; out.mkdir(exist_ok=True)
    t = v.get("lead_in", 0.5); parts, words, lines = [], [], []
    pause_i = 0 if cut == "landscape" else 1
    for s in p.scenes(cut):
        key = line_key(p, s["line"]["text"])
        if dry:
            w = dry_words(s["line"]["text"])
        else:
            js = d / f"{s['id']}-{key}.json"
            if not js.exists():
                raise SystemExit(f"No voiceover for {s['id']} yet ({js.name}). Build without --offline to buy it, "
                                 "or use --dry-timings for a silent layout preview.")
            w = json.loads(js.read_text(encoding="utf-8"))["words"]
        a, b = max(0.0, w[0]["s"] - 0.04), w[-1]["e"] + 0.12
        lines.append({"scene": s["id"], "start": round(t, 3), "end": round(t + b - a, 3), "text": s["line"]["text"]})
        words += [{"scene": s["id"], "w": x["w"], "s": round(t + x["s"] - a, 3), "e": round(t + x["e"] - a, 3)} for x in w]
        parts.append((d / f"{s['id']}-{key}.mp3", a, b, t))
        t += (b - a) + s["line"].get("pause", [0.45, 0.35])[pause_i]
    total = round(t, 3)
    if dry:
        ffmpeg("-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo", "-t", f"{total:.3f}", "-ar", SR, out / f"vo-{cut}.wav")
        (out / f"words-{cut}.json").write_text(json.dumps({"duration": total, "dry": True, "lines": lines, "words": words}, indent=1), encoding="utf-8")
        print(f"  vo {cut}: DRY {total:.2f} s, {len(words)} synthetic words at {DRY_WPS} words/s, silent")
        return
    ins, flt, labels = [], [], []
    for k, (f, a, b, at) in enumerate(parts):
        ins += ["-i", str(f)]; ms = int(round(at * 1000))
        flt.append(f"[{k}:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS,aresample={SR},aformat=channel_layouts=stereo,"
                   f"afade=t=out:st={max(0, b - a - 0.06):.3f}:d=0.06,adelay={ms}|{ms}[v{k}]")
        labels.append(f"[v{k}]")
    flt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,apad=whole_dur={total},atrim=0:{total}[out]")
    ffmpeg(*ins, "-filter_complex", ";".join(flt), "-map", "[out]", "-ar", SR, out / f"vo-{cut}.wav")
    (out / f"words-{cut}.json").write_text(json.dumps({"duration": total, "lines": lines, "words": words}, indent=1), encoding="utf-8")
    print(f"  vo {cut}: {total:.2f} s, {len(words)} words")
