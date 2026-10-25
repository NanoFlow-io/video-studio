"""Owner Featured business profiles: find a business by name, say what its profile still needs, start a new one.

    python -m studio.owner_profile find  "<business name or slug>"
    python -m studio.owner_profile check <tenant>
    python -m studio.owner_profile init  <tenant> --name "Business Name" [--website URL] [--number "949 669 7337"]

A profile (templates-experimental/owner-featured-field-notes-v1/tenants/<tenant>.json) holds only the business's own
details: presenter (Argil look), voice, logo, number, brand colours, the saved close and an optional music override.
`init` fills what can be found automatically (logo via the socials logo finder, brand colours from the logo, the phone
number from the website) and leaves the presenter, voice and close for a person to choose. Free: no paid calls except
the logo finder's own check (a fraction of a cent of Gemini), which only runs when no logo is given."""
import argparse, json, re, subprocess, sys, urllib.request
from collections import Counter
from pathlib import Path

from .owner_featured import FORMAT_DIR, sha256

TENANTS = FORMAT_DIR / "tenants"
ASSETS = Path("/home/adam/video-studio/owner-featured/businesses")
LOGO_FINDER = Path("/home/adam/techbots-data/nano-3d/reels/socials/logo_find.py")
LOGO_FINDER_PY = Path("/home/adam/techbots-data/nano-3d/reels/.venv-face/bin/python")
DIGITS = "zero one two three four five six seven eight nine".split()
REQUIRED = {   # what a reel needs, in the order a person sets it up
    "business_name": "business name",
    "logo.file": "logo",
    "contact_number.display": "phone number",
    "voice.voice_id": "owner voice (ElevenLabs voice)",
    "argil.avatar_id": "presenter (Argil look)",
    "argil.runner": "where the Argil call runs (server with the business's Argil key)",
    "close.clip": "saved close (made once by close-setup, then approved)",
}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower().replace("&", "and"))


def profiles():
    for p in sorted(TENANTS.glob("*.json")):
        yield json.loads(p.read_text(encoding="utf-8"))


def find(name):
    """The profile whose slug, business name or alias matches `name` (ignoring case, spaces, punctuation, '&'/'and').
    Falls back to a unique partial match. Returns (profile or None, candidates)."""
    n = norm(name)
    all_ = list(profiles())
    keys = lambda p: {norm(p["tenant"]), norm(p.get("business_name")), *map(norm, p.get("aliases", []))}
    exact = [p for p in all_ if n in keys(p)]
    if len(exact) == 1:
        return exact[0], []
    part = [p for p in all_ if any(n and (n in k or k in n) for k in keys(p) if k)]
    if len(part) == 1:
        return part[0], []
    return None, [p["tenant"] for p in (exact or part)]


def get(d, dotted):
    for k in dotted.split("."):
        d = (d or {}).get(k) if isinstance(d, dict) else None
    return d


def check(tenant):
    """Which required details are missing or unapproved, and which files fail their checksum."""
    p = json.loads((TENANTS / f"{tenant}.json").read_text(encoding="utf-8"))
    missing = [label for k, label in REQUIRED.items() if not get(p, k)]
    problems = []
    logo = get(p, "logo.file")
    if logo and not Path(logo).exists():
        problems.append(f"logo file not found: {logo}")
    clip = get(p, "close.clip")
    if clip:
        f = Path(p["close"]["dir"]) / clip
        if not f.exists() or (p["close"].get("sha256") and sha256(f) != p["close"]["sha256"]):
            problems.append(f"saved close missing or changed: {f}")
        if not p["close"].get("approved"):
            missing.append("approval of the saved close")
    for k in ("voice", "argil"):
        if get(p, f"{k}.voice_id" if k == "voice" else f"{k}.avatar_id") and not get(p, f"{k}.approved"):
            missing.append(f"approval of the {'owner voice' if k == 'voice' else 'presenter look'}")
    music = p.get("music") or json.loads((FORMAT_DIR / "format.json").read_text(encoding="utf-8"))["music"].get("default_bed")
    if music and Path(music["file"]).exists() and sha256(music["file"]) != music["sha256"]:
        problems.append(f"music bed changed: {music['file']}")
    return {"tenant": tenant, "ready": not missing and not problems, "missing": missing, "problems": problems,
            "music": "business override" if p.get("music") else "template default"}


def spoken(display):
    groups = re.findall(r"\d+", display)
    return ", ".join(" ".join(DIGITS[int(c)] for c in g) for g in groups)


def phone_from_site(url):
    """The first tel: link (or a US-style number) on the business's own homepage. Free; None when unsure."""
    try:
        html = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r'href="tel:([+\d\-(). ]{7,20})"', html) or re.search(r"\(?\b(\d{3})\)?[ .\-](\d{3})[ .\-](\d{4})\b", html)
    if not m:
        return None
    d = re.sub(r"\D", "", m.group(0) if m.re.groups == 3 else m.group(1))
    d = d[1:] if len(d) == 11 and d[0] == "1" else d
    return f"{d[:3]} {d[3:6]} {d[6:]}" if len(d) == 10 else None


def colors_from_logo(png):
    """Primary = the most common dark saturated colour, accent = the next distinct one; None if the logo is mono."""
    from PIL import Image
    im = Image.open(png).convert("RGBA")
    im.thumbnail((400, 400))
    px = [p[:3] for p in im.get_flattened_data() if p[3] > 240]
    sat = lambda c: max(c) - min(c)
    cnt = Counter(tuple(v // 16 * 16 + 8 for v in c) for c in px if sat(c) > 40 and max(c) > 40)
    picks = []
    for c, _ in cnt.most_common(40):
        if all(sum(abs(a - b) for a, b in zip(c, q)) > 120 for q in picks):
            picks.append(c)
        if len(picks) == 2:
            break
    if not picks:
        return None
    picks.sort(key=sum)                    # darker first: the primary carries white text
    hexc = lambda c: "#%02X%02X%02X" % c
    return {"primary": hexc(picks[0]), "accent": hexc(picks[-1]) if len(picks) > 1 else hexc(picks[0]), "card": "#FFFFFF"}


def find_logo(name, website, dst):
    if not LOGO_FINDER.exists():
        return None
    args = [str(LOGO_FINDER_PY), str(LOGO_FINDER), "--company", name] + (["--website", website] if website else [])
    r = subprocess.run(args, capture_output=True, text=True, cwd=LOGO_FINDER.parent, timeout=600)
    m = re.findall(r"(/[^\s\"']+\.png)", r.stdout)
    if not m or not Path(m[-1]).exists():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(Path(m[-1]).read_bytes())
    return dst


def init(tenant, name, website=None, number=None, logo=None):
    if not re.match(r"^[a-z0-9][a-z0-9-]{1,39}$", tenant):
        raise SystemExit("tenant: 2 to 40 lower-case letters, digits or dashes")
    path = TENANTS / f"{tenant}.json"
    if path.exists():
        raise SystemExit(f"{path.name} already exists; edit it instead")
    folder = ASSETS / tenant
    found = {}
    if logo:
        dst = folder / "logo.png"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(Path(logo).read_bytes())
        found["logo"] = "given"
    else:
        dst = find_logo(name, website, folder / "logo.png")
        found["logo"] = "logo finder" if dst else "not found"
    found["number"] = "given" if number else None
    number = number or (phone_from_site(website) if website else None)
    found["number"] = found["number"] or ("website" if number else "not found")
    p = {"tenant": tenant, "business_name": name, "aliases": [], "website": website,
         "voice": {"provider": "elevenlabs", "voice_id": None, "name": None, "model": "eleven_turbo_v2_5",
                   "settings": {"stability": 0.4, "similarity_boost": 0.85, "style": 0.35, "speed": 1.12}, "contract_file": None, "approved": None},
         "argil": {"actor": None, "look": None, "avatar_id": None, "approved": None, "runner": None},
         "logo": {"file": str(dst) if dst else None, "sha256_prefix": sha256(dst)[:12] if dst else None},
         "contact_number": {"display": number, "spoken": spoken(number) if number else None, "source": found["number"]},
         "close": {"id": None, "dir": str(folder / f"{tenant}-close-v0"), "clip": None, "sha256": None, "approved": None,
                   "line": f"For help with <service>, call {name} on <spoken number>."},
         "brand": {"colors": colors_from_logo(dst) if dst else None, "colors_source": "sampled from the logo" if dst else None, "card_style": "split"},
         "music": None}
    path.write_text(json.dumps(p, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"profile": str(path), "found": found, **check(tenant)}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="owner_profile")
    ap.add_argument("action", choices=["find", "check", "init"])
    ap.add_argument("name")
    ap.add_argument("--name", dest="business")
    ap.add_argument("--website")
    ap.add_argument("--number")
    ap.add_argument("--logo")
    a = ap.parse_args(argv)
    if a.action == "find":
        p, cands = find(a.name)
        out = {"tenant": p["tenant"], "business_name": p["business_name"], **check(p["tenant"])} if p else \
              {"tenant": None, "candidates": cands, "note": "no single match; ask which business, or set one up with init"}
    elif a.action == "check":
        out = check(a.name)
    else:
        if not a.business:
            raise SystemExit("init needs --name")
        out = init(a.name, a.business, a.website, a.number, a.logo)
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
