"""Mix voice + music + every SFX cue at its exact sample position, per cut -> build/mix-<cut>.wav.
Music: bed_a until the held beat before the "turn" scene, silence, bed_b from the turn (one bed if there is
no turn). Music sits at a fixed loudness and ducks under the voice. Fast transients (whooshes, slams) are
placed by their loudest moment so the hit lands on the cut. Ends with a soft limiter."""
import json, subprocess
import numpy as np
from .common import ROOT, SR

KIT = ROOT / "assets" / "sfx-kit"


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


def mix(p, cut):
    A = p.data.get("audio", {})
    B = json.loads((p.build / f"beats-{cut}.json").read_text(encoding="utf-8"))
    N = int(B["duration"] * SR)
    vo = np.zeros((N, 2), np.float32); _place(vo, _load(p.build / f"vo-{cut}.wav"), 0.0)

    sfx = np.zeros((N, 2), np.float32); cache = {}; peak_names = set(A.get("peak_align", []))
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
        _place(sfx, _rate(clip, c["rate"]) * _db(c["gain_db"] + A.get("sfx_bus_db", 4.0)), max(0.0, c["t"] - pk / c["rate"]))

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
        win = int(0.02 * SR)
        e = np.sqrt(np.convolve((vo ** 2).mean(axis=1), np.ones(win) / win, mode="same"))
        speaking = (e > _db(-38)).astype(np.float32)
        g = np.empty_like(speaking); cur = 0.0
        att, rel = 1 - np.exp(-1 / (0.04 * SR)), 1 - np.exp(-1 / (0.35 * SR))
        for i in range(len(speaking)):
            cur += (speaking[i] - cur) * (att if speaking[i] > cur else rel); g[i] = cur
        mus *= (_db(A.get("duck_db", -9)) ** g)[:, None]

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
