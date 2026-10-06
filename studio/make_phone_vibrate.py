"""Synthesise assets/sfx-kit/phone_vibrate.wav: a phone buzzing on a hard counter, incoming-call pattern
(buzz 0.45 s, gap 0.2 s, buzz 0.45 s, gap 0.9 s = one 2.0 s cycle). Deterministic and free (no provider),
and it loops seamlessly, so a cue with `until`/`dur` can hold it for any length.

    .venv/bin/python -m studio.make_phone_vibrate
"""
import wave
from pathlib import Path
import numpy as np

SR = 48000
OUT = Path(__file__).resolve().parent.parent / "assets" / "sfx-kit" / "phone_vibrate.wav"
BURSTS = [(0.0, 0.45), (0.65, 0.45)]   # (start, length) seconds inside the cycle
CYCLE = 2.0


def band(x, lo, hi):
    f = np.fft.rfft(x); fr = np.fft.rfftfreq(len(x), 1 / SR)
    f[(fr < lo) | (fr > hi)] = 0
    return np.fft.irfft(f, len(x))


def burst(n, seed):
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    # eccentric-mass motor: spins up over ~40 ms to about 172 Hz, with a slight wobble
    freq = 172 * (1 - 0.3 * np.exp(-t / 0.04)) + 1.8 * np.sin(2 * np.pi * 6.5 * t)
    ph = 2 * np.pi * np.cumsum(freq) / SR
    hum = 0.55 * np.tanh(3.0 * np.sin(ph)) + 0.25 * np.sin(2 * ph + 0.4)
    # the phone body rattling on the counter: a short noise tick once per motor turn
    ticks = band(rng.standard_normal(n), 900, 3200) * (0.5 + 0.5 * np.sin(ph)) ** 10
    x = band(hum + 0.5 * ticks / (np.abs(ticks).max() + 1e-9), 70, 5000)
    a, r = int(0.025 * SR), int(0.06 * SR)
    env = np.ones(n); env[:a] = np.linspace(0, 1, a) ** 2; env[-r:] = np.linspace(1, 0, r) ** 2
    return x * env


def main():
    y = np.zeros(int(CYCLE * SR))
    for k, (s, d) in enumerate(BURSTS):
        i, n = int(s * SR), int(d * SR)
        y[i:i + n] += burst(n, 7 + k)
    y *= 10 ** (-1 / 20) / np.abs(y).max()
    pcm = (np.clip(y, -1, 1) * 32767).astype("<i2")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())
    print(f"wrote {OUT} ({CYCLE:.1f} s loop)")


if __name__ == "__main__":
    main()
