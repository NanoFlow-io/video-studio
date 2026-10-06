"""AI provenance: carry the source clips' AIGC labels (the GB 45438 implicit label Kling writes into the MP4) into
the final export unchanged. Labels are copied verbatim, never written or edited here: `AIGC` holds the first labelled
source's label exactly as it was, `aigc_sources` a JSON list of every distinct source label string in scene order.
A metadata-only remux (no re-encode); the streams are checked packet-identical before the file is replaced. No
labelled source, no change. Writes build/provenance-<cut>.json."""
import hashlib, json, os, subprocess
from pathlib import Path

TAGS = ("-map_metadata", "0", "-movflags", "+use_metadata_tags")   # keep custom MP4 tags through ffmpeg


def label_of(path):
    """The file's AIGC tag (verbatim string), or None."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json", str(path)], capture_output=True, text=True)
    tags = (json.loads(r.stdout or "{}").get("format") or {}).get("tags") or {}
    return next((v for k, v in tags.items() if k.lower() == "aigc" and v), None)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _streams_md5(path):
    out = {}
    for kind in ("v", "a"):
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", f"0:{kind}?", "-c", "copy", "-f", "md5", "-"], capture_output=True, text=True)
        out[kind] = r.stdout.strip()
    return out


def sources(p, cut, beats):
    """Labelled media used by the cut, in scene order: [{scene, file, sha256, label}]."""
    defs = {s["id"]: s for s in p.data["scenes"]}; tag = {"landscape": "16x9", "vertical": "9x16"}[cut]
    files = []
    for s in beats["scenes"]:
        d = (defs.get(s["id"]) or {}).get("data") or {}
        files += [(s["id"], p.dir / d[k]) for k in ("media", "proof") if d.get(k)]
    files += [(t["id"], p.gen / "transitions" / f"{t['id']}-{tag}.mp4") for t in p.data.get("transitions", [])]
    out = []
    for scene, f in files:
        if f.is_file() and (lab := label_of(f)):
            out.append({"scene": scene, "file": str(f.relative_to(p.dir)), "sha256": _sha(f), "label": lab})
    return out


def apply(render_path, labels):
    """Write AIGC/aigc_sources into the render (verbatim labels). Returns True when the file changed."""
    want = {"AIGC": labels[0], "aigc_sources": json.dumps(labels, ensure_ascii=False)}
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json", str(render_path)], capture_output=True, text=True)
    have = (json.loads(r.stdout or "{}").get("format") or {}).get("tags") or {}
    if all(have.get(k) == v for k, v in want.items()):
        return False
    tmp = Path(render_path).with_suffix(".provenance.tmp.mp4")
    meta = [x for k, v in want.items() for x in ("-metadata", f"{k}={v}")]
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(render_path), "-map", "0", "-c", "copy", *TAGS, *meta, str(tmp)], check=True)
    try:
        if _streams_md5(tmp) != _streams_md5(render_path):
            raise SystemExit(f"provenance: remux changed the streams of {render_path}; render left as it was")
        if label_of(tmp) != labels[0]:
            raise SystemExit(f"provenance: the AIGC label did not survive the remux of {render_path}; render left as it was")
        os.replace(tmp, render_path)
    finally:
        if tmp.exists(): tmp.unlink()
    return True


def run(p, cut):
    """Label one cut's render from its sources; writes build/provenance-<cut>.json and prints one line."""
    render_path = p.render_path(cut)
    if not render_path.exists():
        raise SystemExit(f"provenance: no render for the {cut} cut yet")
    beats = json.loads((p.build / f"beats-{cut}.json").read_text(encoding="utf-8"))
    src = sources(p, cut, beats)
    labels = list(dict.fromkeys(s["label"] for s in src))
    before = _sha(render_path)
    changed = apply(render_path, labels) if labels else False
    rep = {"cut": cut, "render": str(render_path.relative_to(p.dir)), "sha256_before": before, "sha256_after": _sha(render_path),
           "written": changed, "labels": labels, "sources": src}
    (p.build / f"provenance-{cut}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  provenance {cut}: " + (f"{len(labels)} source label(s) from {len(src)} clip(s), {'written' if changed else 'already present'}"
                                      if labels else "no labelled AI source; render unchanged"))
    return rep
