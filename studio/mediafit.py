"""Footage fit and continuity for hook/broll .mp4 media, checked after the beats and before the mix and the page.
Each clip must cover its scene window from data.media_in; a clip whose source (sha256 of the bytes, so a renamed
copy is the same source) also played in the scene before must continue where that scene stopped, unless
data.replay is true. Writes build/media-fit-<cut>.json; problems stop the build (warnings in a dry build)."""
import hashlib, json, os, shutil, subprocess
from pathlib import Path

FRAME = 1 / 30        # a shortfall above one frame is a problem
CONTINUE_TOL = 0.1    # seconds a continuation may miss prev.media_in + prev window by
TYPES = ("hook", "broll")
_SHA = {}             # (path, size, mtime_ns) -> sha256; a speed cache only, identity is the sha


def ffprobe_bin():
    local = Path.home() / ".local" / "bin" / "ffprobe"
    return shutil.which("ffprobe") or (str(local) if local.is_file() else None)


def sha256(path):
    st = os.stat(path); key = (str(Path(path).resolve()), st.st_size, st.st_mtime_ns)
    if key not in _SHA:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        _SHA[key] = h.hexdigest()
    return _SHA[key]


def duration(path):
    """Seconds of the first video stream (the container's duration when the stream has none)."""
    exe = ffprobe_bin()
    if not exe:
        raise SystemExit("ffprobe is not on PATH. Install ffmpeg (https://ffmpeg.org) and try again.")
    r = subprocess.run([exe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    for v in [s.get("duration") for s in j.get("streams", [])] + [j.get("format", {}).get("duration")]:
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    raise ValueError(f"ffprobe found no duration ({r.stderr.strip()[:200] or 'no video stream'})")


def check(cut, scenes, defs, base, dry=False):
    """Core check on plain data: scenes = beats scenes (id, type, start, end) in cut order, defs = {id: project
    scene}, base = the project dir media paths are relative to. Returns the report (no files written)."""
    r3 = lambda x: None if x is None else round(x, 3)
    rows, problems, warnings, restarts, prev = [], [], [], [], None
    for s in scenes:
        d = (defs.get(s["id"]) or {}).get("data") or {}
        media = str(d.get("media") or "")
        if s["type"] not in TYPES or not media.lower().endswith(".mp4"):
            prev = None; continue
        sid, mi, replay = s["id"], float(d.get("media_in") or 0), d.get("replay") is True
        needed = s["end"] - s["start"]
        row = {"id": sid, "media": media, "sha256": None, "duration": None, "media_in": r3(mi), "usable": None,
               "needed": r3(needed), "ok": False, "replay": replay, "same_source_as": None}
        rows.append(row)
        try:
            sha, dur = sha256(base / media), duration(base / media)
        except (OSError, ValueError) as e:
            problems.append(f"{sid} ({s['type']}): cannot read {media}: {e}"); prev = None; continue
        usable = dur - mi
        row.update(sha256=sha, duration=r3(dur), usable=r3(usable))
        ok = True
        if mi >= dur:
            ok = False; problems.append(f"{sid} ({s['type']}): data.media_in {mi:g} s is at or past the end of {media} ({dur:.3f} s)")
        elif needed - usable > FRAME:
            ok = False; problems.append(f"{sid} ({s['type']}): {media} has {usable:.3f} s from {mi:g} s but the scene runs {needed:.3f} s "
                                        f"({needed - usable:.3f} s short); use a longer clip, an earlier data.media_in or a shorter line")
        earlier = [x for x in rows[:-1] if x["sha256"] == sha]
        if prev and prev["sha256"] == sha:
            row["same_source_as"] = prev["id"]
            want = prev["media_in"] + prev["needed"]
            if not replay and abs(mi - want) > CONTINUE_TOL:
                ok = False; restarts.append(sid)
                problems.append(f"{sid} {'restarts' if mi < want else 'jumps in'} {media} at {mi:g}s; to continue from {prev['id']} "
                                f"set data.media_in to {want:.3f} (or data.replay: true for an intentional replay)")
        elif earlier:
            row["same_source_as"] = earlier[-1]["id"]
            if not replay:
                warnings.append(f"possible repeated payoff: {sid} reuses the source of {earlier[-1]['id']} ({media})")
        row["ok"] = ok
        prev = row
    if dry:
        warnings, problems = [f"DRY (would stop a real build): {x}" for x in problems] + warnings, []
    return {"cut": cut, "dry": bool(dry), "scenes": rows, "problems": problems, "warnings": warnings, "restarts": restarts}


def summary(rep):
    rows = rep["scenes"]
    if not rows:
        return f"  media {rep['cut']}: no .mp4 clips"
    fit = sum(1 for x in rows if x["ok"])
    replays = [x["id"] for x in rows if x["replay"] and x["same_source_as"]]
    n = f"{len(rows)} clip{'s' if len(rows) > 1 else ''}" if fit == len(rows) else f"{fit} of {len(rows)} clips"
    return (f"  media {rep['cut']}: {n} fit; restarts: {', '.join(rep['restarts']) or 'none'}; "
            f"{'replays: ' + ', '.join(replays) + '; ' if replays else ''}warnings: {len(rep['warnings']) or 'none'}{' (DRY)' if rep['dry'] else ''}")


def run(p, cut, beats):
    """Check one cut, write build/media-fit-<cut>.json, print the summary; SystemExit on problems (not in a dry build)."""
    rep = check(cut, beats["scenes"], {s["id"]: s for s in p.data["scenes"]}, p.dir, dry=bool(beats.get("dry")))
    out = {k: rep[k] for k in ("cut", "dry", "scenes", "problems", "warnings")}
    (p.build / f"media-fit-{cut}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(summary(rep))
    for w in rep["warnings"]:
        print(f"    warning: {w}")
    if rep["problems"]:
        raise SystemExit("media fit problems:\n  " + "\n  ".join(rep["problems"]))
    return rep
