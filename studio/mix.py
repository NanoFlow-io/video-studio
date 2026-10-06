"""Mix voice + music + every SFX cue at its exact sample position, per cut -> build/mix-<cut>.wav.
Music: bed_a until the held beat before the "turn" scene, silence, bed_b from the turn (one bed if there is
no turn). Music sits at a fixed loudness and ducks under the voice. Fast transients (whooshes, slams) are
placed by their loudest moment so the hit lands on the cut. A cue with a stop time (`until`/`dur`) holds its
sound for that span, looped, faded at the stop and optionally ducked under the voice. Ends with a soft limiter.
Held sounds are then measured against the voice (build/sound-report-<cut>.json): a measurement, not a listen."""
import json, subprocess
import numpy as np
from .common import ROOT, SR

KIT = ROOT / "assets" / "sfx-kit"
MASKING_MARGIN_DB = 12   # held sound report: voice under this many dB above the sound on a word = masking risk
FELT_PAUSE_DBFS = -42    # held sound report: quieter than this in the pauses = may not be felt


def _load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def _db(x):
    return 10 ** (x / 20)


def _place(bus, clip, t):
    i = int(round(t * SR))
    if i >= len(bus): return
    n = min(len(clip), len(bus) - i); bus[i:i + n] += clip[:n]


def _rate(clip, r):
    if r == 1.0: return clip
    idx = np.arange(0, len(clip) - 1, r)
    return np.stack([np.interp(idx, np.arange(len(clip)), clip[:, c]) for c in range(2)], axis=1).astype(np.float32)


def _rms(x):
    return float(np.sqrt(np.mean(x ** 2)) + 1e-9)


def _write(path, x):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "-", str(path)],
                   input=(np.clip(x, -1, 1) * 32767).astype("<i2").tobytes(), check=True)


def _gate(vo):
    """(speaking, gate): speaking = 20 ms voice RMS above -38 dB; gate = its 0..1 envelope (40 ms attack, 350 ms release)."""
    win = int(0.02 * SR)
    e = np.sqrt(np.convolve((vo ** 2).mean(axis=1), np.ones(win) / win, mode="same"))
    speaking = (e > _db(-38)).astype(np.float32)
    gate = np.empty_like(speaking); cur = 0.0
    att, rel = 1 - np.exp(-1 / (0.04 * SR)), 1 - np.exp(-1 / (0.35 * SR))
    for i in range(len(speaking)):
        cur += (speaking[i] - cur) * (att if speaking[i] > cur else rel); gate[i] = cur
    return speaking, gate


def held_report(vo, held, speaking, gate, words):
    """Measure each held sound against the voice on the mix's own signals. vo = voice bus after normalisation,
    held = [(cue, i0, placed/ducked clip)], speaking/gate from _gate, words = beats words (s, e on the cut clock).
    Per cue: worst per-word margin (voice minus sound RMS over the word's voiced samples), worst 50 ms voiced
    window margin, and the sound's level in the pauses (gate < 0.05, non-silent sound samples)."""
    db = lambda x: 20 * np.log10(max(1e-9, _rms(x)))
    out = []
    for c, i0, clip in held:
        n = max(0, min(len(clip), len(vo) - i0)); v, s = vo[i0:i0 + n], clip[:n]
        voiced, g = speaking[i0:i0 + n] > 0, gate[i0:i0 + n]
        worst = None
        for w in words:
            a, b = max(0, int(round(w["s"] * SR)) - i0), min(n, int(round(w["e"] * SR)) - i0)
            if b <= a: continue
            m = voiced[a:b]
            if m.sum() < 0.03 * SR: continue
            mg = db(v[a:b][m]) - db(s[a:b][m])
            if worst is None or mg < worst[0]: worst = (mg, w["w"], w["s"])
        W, hop = int(0.05 * SR), int(0.01 * SR)
        cv = np.concatenate([[0], np.cumsum((v ** 2).mean(axis=1) * voiced)]); cs = np.concatenate([[0], np.cumsum((s ** 2).mean(axis=1) * voiced)])
        cn = np.concatenate([[0], np.cumsum(voiced)])
        win = [10 * np.log10(max(1e-18, cv[k + W] - cv[k]) / max(1e-18, cs[k + W] - cs[k]))
               for k in range(0, n - W + 1, hop) if cn[k + W] - cn[k] >= W // 2]
        ps = s[(g < 0.05) & (np.abs(s).max(axis=1) > 1e-4)] if n else s
        pause = db(ps) if len(ps) else None
        r = lambda x: None if x is None else round(float(x), 1)
        flags = (["masking_risk"] if worst is not None and worst[0] < MASKING_MARGIN_DB else []) + \
                (["may_not_be_felt"] if pause is not None and pause < FELT_PAUSE_DBFS else [])
        out.append({"id": c["id"], "sfx": c["sfx"], "start": c["t"], "stop": c["stop"], "duck_db": c.get("duck_db", 0.0),
                    "worst_word_margin_db": r(worst and worst[0]), "worst_word": worst and worst[1], "worst_word_t": worst and worst[2],
                    "worst_50ms_margin_db": r(min(win)) if win else None, "pause_level_dbfs": r(pause), "flags": flags})
    return out


def _sound_report(p, cut, B, vo, held, sg):
    """Write build/sound-report-<cut>.json and one line per held sound. Never fails the build."""
    try:
        cues = held_report(vo, held, *sg, B["words"]) if held else []
        (p.build / f"sound-report-{cut}.json").write_text(json.dumps({"cut": cut, "dry": bool(B.get("dry")), "masking_margin_db": MASKING_MARGIN_DB,
            "felt_pause_dbfs": FELT_PAUSE_DBFS, "note": "measurement only, listen on a phone", "cues": cues}, indent=1), encoding="utf-8")
        f = lambda x: "n/a" if x is None else f"{x:g}"
        for c in cues:
            print(f"  sound {c['id']}: voiced margin >= {f(c['worst_word_margin_db'])} dB (worst 50 ms {f(c['worst_50ms_margin_db'])} dB), "
                  f"pauses {f(c['pause_level_dbfs'])} dBFS{'; ' + ', '.join(c['flags']) if c['flags'] else ''}; measurement only, listen on a phone")
    except Exception as e:  # noqa: BLE001  (a report, never a reason to stop)
        print(f"  sound {cut}: report skipped ({e})")


def mix(p, cut, dry=False):
    A = p.data.get("audio", {})
    B = json.loads((p.build / f"beats-{cut}.json").read_text(encoding="utf-8"))
    N = int(B["duration"] * SR)
    if dry:   # --dry-timings: a silent track of the right length; no generated sound or music is read
        _write(p.build / f"mix-{cut}.wav", np.zeros((N, 2), np.float32))
        print(f"  mix {cut}: DRY {N / SR:.2f} s of silence (layout preview only)")
        _sound_report(p, cut, B, None, [], None)
        return
    vo = np.zeros((N, 2), np.float32); _place(vo, _load(p.build / f"vo-{cut}.wav"), 0.0)

    gate = None   # 0..1 "voice is speaking" envelope, shared by the music and any held sound that ducks
    sg = [None, None]   # (speaking, gate), also read by the held-sound report

    def voice_gate():
        nonlocal gate
        if gate is None:
            sg[:] = _gate(vo); gate = sg[1]
        return gate

    sfx = np.zeros((N, 2), np.float32); cache = {}; peak_names = set(A.get("peak_align", [])); held = []
    for c in B["cues"]:
        if not c["sfx"]: continue
        src, name = c["sfx"].split(":", 1)
        path = KIT / f"{name}.wav" if src == "kit" else p.gen / "sfx" / f"{name}.mp3"
        if path not in cache:
            a = _load(path)
            nz = np.nonzero(np.abs(a).max(axis=1) > _db(-50))[0]
            a = a[nz[0]:] if len(nz) else a
            a = a / max(1e-6, np.abs(a).max()) * _db(-1)
            f = min(len(a), int(0.03 * SR)); a[-f:] *= np.linspace(1, 0, f)[:, None]
            pk = 0.0
            if name in peak_names:
                e = np.convolve(np.abs(a).max(axis=1), np.ones(960) / 960, mode="same"); pk = int(np.argmax(e)) / SR
            cache[path] = (a, pk)
        clip, pk = cache[path]
        clip = _rate(clip, c["rate"]) * _db(c["gain_db"] + A.get("sfx_bus_db", 4.0))
        if c.get("stop") is not None:
            # held sound (cue `until`/`dur`): repeat (loop) or cut to the span, fade out at the stop, duck under the voice
            i0, n = int(round(c["t"] * SR)), int(round((c["stop"] - c["t"]) * SR))
            if c.get("loop", True) and len(clip) < n:
                clip = np.concatenate([clip] * (n // len(clip) + 1))
            clip = clip[:n].copy()
            f = min(len(clip), int(c.get("fade", 0.08) * SR))
            if f: clip[-f:] *= np.linspace(1, 0, f)[:, None]
            if c.get("duck_db"):
                # look ahead 80 ms so the sound is already down when a word starts
                la = int(0.08 * SR); g = voice_gate(); g = np.maximum(g, np.concatenate([g[la:], np.zeros(la, np.float32)]))[i0:i0 + len(clip)]
                clip[:len(g)] *= (_db(c["duck_db"]) ** g)[:, None]
            _place(sfx, clip, c["t"]); held.append((c, i0, clip.copy()))
            continue
        _place(sfx, clip, max(0.0, c["t"] - pk / c["rate"]))

    mus = np.zeros((N, 2), np.float32)
    music = p.data.get("music", {})
    turn = next((s for s in B["scenes"] if any(d["id"] == s["id"] and d.get("turn") for d in p.data["scenes"])), None)
    md = p.gen / "music"
    if turn and "bed_a" in music and "bed_b" in music:
        prev = B["scenes"][B["scenes"].index(turn) - 1]["id"]
        off = next((c["t"] for c in B["cues"] if c["id"] == f"{prev}.off"), turn["start"] - 0.4)
        a = _load(md / "bed_a.mp3")
        while len(a) < int(off * SR): a = np.concatenate([a, a])
        a = a[: int((off + 0.05) * SR)]
        f = int(0.35 * SR); a[-f:] *= np.linspace(1, 0, f)[:, None]
        fi = int(0.3 * SR); a[:fi] *= np.linspace(0, 1, fi)[:, None]
        _place(mus, a, 0.0)
        b = _load(md / "bed_b.mp3")
        while len(b) < N - int(turn["start"] * SR): b = np.concatenate([b, b])
        b = b[: N - int(turn["start"] * SR)]
        fo = min(len(b), int(2.2 * SR)); b[-fo:] *= np.linspace(1, 0, fo)[:, None]
        _place(mus, b, turn["start"])
    elif music:
        b = _load(md / f"{'bed_b' if 'bed_b' in music else next(iter(music))}.mp3")
        while len(b) < N: b = np.concatenate([b, b])
        b = b[:N]; fo = int(2.2 * SR); b[-fo:] *= np.linspace(1, 0, fo)[:, None]
        _place(mus, b, 0.0)
    if np.abs(mus).max() > 0:
        mus *= _db(A.get("music_db", -26)) / _rms(mus[np.abs(mus).max(axis=1) > 1e-4])
        mus *= (_db(A.get("duck_db", -9)) ** voice_gate())[:, None]

    if held: voice_gate()   # the report's speaking flag, from the same (pre-normalisation) voice as the ducks
    vo *= _db(-1) / max(1e-6, np.abs(vo).max())
    m = vo + sfx + mus
    th = _db(-3); over = np.abs(m) > th
    m[over] = np.sign(m[over]) * (th + (1 - th) * np.tanh((np.abs(m[over]) - th) / (1 - th)))
    m *= _db(-1) / np.abs(m).max()
    _write(p.build / f"mix-{cut}.wav", m)
    # audibility audit: SFX vs voice+music in the 0.25 s after each cue
    lvl = lambda x: 20 * np.log10(max(1e-9, _rms(x)))
    low = [c["id"] for c in B["cues"] if c["sfx"] and lvl(sfx[int(c["t"] * SR):int((c["t"] + .25) * SR)]) - lvl((vo + mus)[int(c["t"] * SR):int((c["t"] + .25) * SR)]) < -14]
    print(f"  mix {cut}: {N / SR:.2f} s; cues that may be masked by the voice: {', '.join(low) or 'none'}")
    _sound_report(p, cut, B, vo.copy(), held, sg)
