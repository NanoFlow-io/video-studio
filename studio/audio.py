"""Sound effects and music beds from ElevenLabs, cached in generated/. Only missing files are bought."""
import json
from .elevenlabs import ElevenLabs
from .common import mean_db


def generate(p, env, force=()):
    el = ElevenLabs(env["ELEVENLABS_API_KEY"])
    sd = p.gen / "sfx"; sd.mkdir(exist_ok=True)
    used = {c["sfx"].split(":", 1)[1] for s in p.scenes() for c in s.get("cues", []) if c.get("sfx", "") and c["sfx"].startswith("el:")}
    lib = p.data.get("sfx", {})
    missing = sorted(used - set(lib))
    if missing:
        raise SystemExit("These el: sounds are used by cues but have no prompt in project.json \"sfx\": " + ", ".join(missing))
    prov_p = sd / "provenance.json"
    prov = json.loads(prov_p.read_text(encoding="utf-8")) if prov_p.exists() else {}
    for name in sorted(used):
        dst = sd / f"{name}.mp3"
        if dst.exists() and name not in force:
            continue
        db, tries = el.sfx(lib[name]["prompt"], lib[name]["seconds"], dst)
        prov[name] = {"provider": "ElevenLabs sound-generation", **lib[name], "mean_db": db, "attempts": tries}
        print(f"  sfx {name}: mean {db} dB ({tries} attempt{'s' if tries > 1 else ''})")
        prov_p.write_text(json.dumps(prov, indent=1), encoding="utf-8")
    md = p.gen / "music"; md.mkdir(exist_ok=True)
    for name, m in p.data.get("music", {}).items():
        dst = md / f"{name}.mp3"
        if dst.exists() and name not in force:
            continue
        db = el.music(m["prompt"], m["ms"], dst)
        (md / f"{name}.json").write_text(json.dumps({"provider": "ElevenLabs Music (music_v1)", **m}, indent=1), encoding="utf-8")
        print(f"  music {name}: mean {db} dB")
