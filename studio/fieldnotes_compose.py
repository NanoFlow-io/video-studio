"""Field-notes composition planner (experimental, 2026-10-12): the catalogue of illustration primitives, plan validation
and the deterministic compiler from a composition plan to fieldnotes scene data.

A plan names a CAST of concrete illustrated objects (people, devices, places, documents, diagrams) placed on a fixed
3x3 layout grid, and per chapter the EVENTS that change them (draw, state, message, connect, break, fix, pulse...).
The Field Notes layout and look are fixed (header, headline, paper, palette, fonts, motion); only the illustrations and
the explanatory composition come from the brief. Everything here is data checking and arithmetic: nothing in a plan is
executed. Add a primitive by drawing it in engine/fieldnotes.js and describing it in PRIMS below; the planner prompt,
the validator and the compiler all read PRIMS."""
import copy, json, re
from pathlib import Path

from .common import ROOT

STYLE_DIR = ROOT / "templates-experimental" / "owner-explainer-field-notes-v1"
DRY_WPS = 2.6
FACTS = ("business", "audience", "problem", "cause", "solution", "outcome")
LIMITS = {"chapter": 14, "kicker": 28, "headline": 20, "callout": 22, "note": 30, "checklist": 34, "label": 22,
          "message": 34, "sign": 12, "step": 40, "window_label": 14, "left": 22, "right": 22, "gauge_label": 30}
BANNED = ("guarantee", "guaranteed", "always", "never", "best", "lowest", "cheapest", "save", "saves", "savings", "promise")
LEVEL = {"high": 0.85, "medium": 0.55, "low": 0.3}
WORD_RE = re.compile(r"[A-Za-z0-9'’-]+")

# Layout grid: the illustration band (y 600 to 1530) as 3 columns x 3 rows; below it the lower band holds an optional
# gauge, a note and the closing checklist card.
GRID = {"x0": 72, "y0": 600, "cw": 312, "rh": 310, "cols": 3, "rows": 3}

# ---- the primitive catalogue: what can be drawn, where it fits, its states and verbs (param specs) ----
E = lambda *vals: {"enum": list(vals)}
PRIMS = {
    "person": {"desc": "a person (customer, patient, parent, staff or owner); present, away (a dashed outline: missing), happy",
               "spans": ["1x1", "1x2"], "states": ["present", "away", "happy"], "verbs": {"state": {"state": E("present", "away", "happy")}}},
    "chair": {"desc": "an appointment chair (dentist, salon, clinic, barber): empty (dashed outline where the person should be) or occupied",
              "spans": ["1x1", "2x1", "2x2"], "states": ["empty", "occupied"], "verbs": {"state": {"state": E("empty", "occupied")}}},
    "calendar": {"desc": "a calendar with one appointment day: booked, empty (missed, an X) or rebooked (a check); 'remind' marks a reminder sent N days before with an arrow to the appointment",
                 "spans": ["1x1", "2x1", "2x2"], "states": ["booked", "empty", "rebooked"],
                 "verbs": {"state": {"state": E("booked", "empty", "rebooked")}, "remind": {"days_before": {"int": [1, 3]}, "medium": E("email", "text")}}},
    "phone": {"desc": "a phone screen showing up to 3 messages in order: an email notification, a text from the business, or the customer's reply; 'bury' stacks other notifications above the messages so they sink out of sight",
              "spans": ["1x2"], "verbs": {"message": {"type": E("email", "text", "reply"), "text": {"str": "message"}}, "bury": {}}},
    "envelope": {"desc": "an email or letter: sent, unread (a dot), missed (faded) or opened",
                 "spans": ["1x1", "2x1"], "states": ["sent", "unread", "missed", "opened"], "verbs": {"state": {"state": E("sent", "unread", "missed", "opened")}}},
    "building": {"desc": "the business's premises (shop, clinic, office) with a short sign", "spans": ["1x1", "2x1", "2x2"], "params": {"sign": {"str": "sign"}}},
    "house": {"desc": "a home with blue cooling that can fill it", "spans": ["2x1"], "verbs": {"cool": {"level": E("full", "partial")}}},
    "ac_unit": {"desc": "an outdoor air-conditioning unit whose fan runs high, low or off", "spans": ["1x1"], "verbs": {"speed": {"speed": E("high", "low", "off")}}},
    "thermostat": {"desc": "a wall thermostat dial that can be turned up or down", "spans": ["1x1"], "verbs": {"turn": {"direction": E("up", "down")}}},
    "timeline": {"desc": "a day from earlier to later with a price or time window, activity bars that can shift earlier or shrink, and a moving marker",
                 "spans": ["3x1"], "params": {"window_label": {"str": "window_label"}, "left": {"str": "left"}, "right": {"str": "right"}},
                 "verbs": {"window": {}, "activity": {}, "shift_earlier": {}, "reduce": {"level": E("low", "medium")}, "playhead": {"through": E("window", "before")}}},
    "steps": {"desc": "an abstract chain of 3 to 5 numbered steps (break and fix mark the link after a step); use ONLY when no concrete objects can show the mechanism",
              "spans": ["2x3", "3x3"], "params": {"steps": {"steps": True}},
              "verbs": {"highlight": {"step": {"step": True}, "tone": E("problem", "fix", "neutral")}, "break": {"step": {"step": True}, "label": {"str": "label"}},
                        "fix": {"step": {"step": True}, "label": {"str": "label"}}, "pulse": {}}},
}
GENERIC_VERBS = {"draw": {}, "hide": {}, "callout": {"text": {"str": "callout"}}}
SCENE_EVENTS = {"connect": {"id": {"id": True}, "from": {"obj": True}, "to": {"obj": True}, "style": E("solid", "dashed"), "label": {"str": "label"}},
                "break": {"link": {"link": True}, "label": {"str": "label"}}, "fix": {"link": {"link": True}, "label": {"str": "label"}},
                "pulse": {"link": {"link": True}}, "gauge": {"label": {"str": "gauge_label"}, "level": E("high", "medium", "low")},
                "note": {"text": {"str": "note"}}, "checklist": {"text": {"str": "checklist"}}}


def catalog_text():
    """The primitive catalogue as the planner prompt shows it (generated, so it always matches PRIMS)."""
    def spec(ps):
        out = []
        for k, v in ps.items():
            if "enum" in v: out.append(f'"{k}": {" | ".join(repr(x).replace(chr(39), chr(34)) for x in v["enum"])}')
            elif "int" in v: out.append(f'"{k}": {v["int"][0]} to {v["int"][1]}')
            elif "str" in v: out.append(f'"{k}": "text up to {LIMITS[v["str"]]} characters"')
            elif v.get("steps"): out.append(f'"{k}": [{{"id": "s1", "label": "up to {LIMITS["step"]} characters"}}, ...]')
            elif v.get("step"): out.append(f'"{k}": a step id')
            elif v.get("obj"): out.append(f'"{k}": a cast id')
            elif v.get("link"): out.append(f'"{k}": a connection id')
            elif v.get("id"): out.append(f'"{k}": a new connection id')
        return "{ " + ", ".join(out) + " }" if out else "{}"
    lines = []
    for name, p in PRIMS.items():
        lines.append(f"- `{name}`: {p['desc']}. Span {' or '.join(p['spans'])}."
                     + (f" Params {spec(p['params'])}." if p.get("params") else "")
                     + (f" Starting state one of {', '.join(p['states'])}." if p.get("states") else "")
                     + (" Verbs: " + "; ".join(f"`{v}` {spec(ps)}" for v, ps in p.get("verbs", {}).items()) + "." if p.get("verbs") else ""))
    lines.append("- Any cast object also takes `draw` {}, `hide` {} and `callout` " + spec(GENERIC_VERBS["callout"]) + ".")
    lines.append("- Scene events (no obj): " + "; ".join(f"`{v}` {spec(ps)}" for v, ps in SCENE_EVENTS.items()) + ".")
    return "\n".join(lines)


# ---- small helpers ----
def norm(w):
    return re.sub(r"[^a-z0-9']", "", str(w).lower().replace("’", "'"))


def words(text):
    return WORD_RE.findall(str(text or ""))


def target_seconds(brief):
    m = re.search(r"(?:about|approximately|around|roughly)?\s*(\d{1,3})\s*(?:s\b|sec\b|secs\b|seconds?\b)", brief, re.I)
    return int(m.group(1)) if m and 5 <= int(m.group(1)) <= 120 else None


def _cue_ok(word, narration):
    return word == "start" or any(norm(word) and norm(w).startswith(norm(word)) for w in words(narration))


def parse_span(span):
    m = re.fullmatch(r"([1-3])x([1-3])", str(span or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_slot(slot):
    m = re.fullmatch(r"r([1-3])c([1-3])", str(slot or ""))
    return (int(m.group(1)) - 1, int(m.group(2)) - 1) if m else None


def cells(slot, span):
    (r, c), (w, h) = parse_slot(slot), parse_span(span)
    return {(r + i, c + j) for i in range(h) for j in range(w)}


def box(slot, span, pad=10):
    (r, c), (w, h) = parse_slot(slot), parse_span(span)
    g = GRID
    x0, y0 = g["x0"] + c * g["cw"], g["y0"] + r * g["rh"]
    return {"x0": x0 + pad, "y0": y0 + pad, "w": w * g["cw"] - 2 * pad, "h": h * g["rh"] - 2 * pad,
            "cx": x0 + w * g["cw"] / 2, "cy": y0 + h * g["rh"] / 2}


# ---- validation ----
def _check_params(spec, e, where, out, fit, ids=None, links=None, steps=None):
    for k, v in spec.items():
        val = e.get(k)
        if "enum" in v:
            if val not in v["enum"]: out.append(f"{where}: {k} must be one of {', '.join(v['enum'])}, not {val!r}")
        elif "int" in v:
            if not (isinstance(val, int) and v["int"][0] <= val <= v["int"][1]): out.append(f"{where}: {k} must be a whole number {v['int'][0]} to {v['int'][1]}")
        elif "str" in v:
            if val is None or not str(val).strip():
                if k not in ("label", "sign"): out.append(f"{where}: {k} is required")
            else: fit(val, v["str"], where)
        elif v.get("step"):
            if val not in (steps or []): out.append(f"{where}: {k} must be one of the steps {steps}")
        elif v.get("obj"):
            if val not in (ids or {}): out.append(f"{where}: {k} must be a cast id")
        elif v.get("link"):
            if val not in (links or set()): out.append(f"{where}: {k} must be a connection made earlier with connect")


def validate_plan(plan, brief):
    """Problems with a composition plan as plain sentences ([] = fine). Nothing here executes plan content."""
    out, b = [], brief.lower()
    if plan.get("questions"):
        return [f"missing fact: {q}" for q in plan["questions"]]
    essential = [m for m in plan.get("missing_primitives") or [] if isinstance(m, dict) and m.get("essential")]
    if essential:
        return [f"missing illustration: {m.get('name')}: {m.get('why')}" for m in essential]
    facts = plan.get("facts") or {}
    for f in FACTS:
        if not str(facts.get(f) or "").strip():
            out.append(f"facts.{f} is empty: the brief must state it")
    texts = []

    def fit(text, key, where):
        if text is None: return
        texts.append(str(text))
        if len(str(text)) > LIMITS[key]:
            out.append(f"{where}: {text!r} is {len(str(text))} characters; the limit is {LIMITS[key]}")
        if re.search(r"[–—]", str(text)):
            out.append(f"{where}: no em or en dashes")

    # cast and layout
    cast, used, ids = plan.get("cast") or [], {}, {}
    if not 1 <= len(cast) <= 7:
        out.append("the cast needs 1 to 7 objects")
    steps_ids = []
    for i, o in enumerate(cast):
        w = f"cast {o.get('id') or i + 1}"
        kind = o.get("kind")
        if kind not in PRIMS:
            out.append(f"{w}: kind {kind!r} is not a supported primitive ({', '.join(PRIMS)}); name it in missing_primitives instead"); continue
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,15}", str(o.get("id") or "")) or o["id"] in ids or o["id"] in ("gauge", "card"):
            out.append(f"{w}: id must be a short unique lower-case name"); continue
        ids[o["id"]] = kind
        if o.get("span") not in PRIMS[kind]["spans"]:
            out.append(f"{w}: span must be {' or '.join(PRIMS[kind]['spans'])} for a {kind}"); continue
        if not parse_slot(o.get("slot")):
            out.append(f"{w}: slot must be r1c1 to r3c3 (row, column of its top-left cell)"); continue
        cs = cells(o["slot"], o["span"])
        if any(r > 2 or c > 2 for r, c in cs):
            out.append(f"{w}: {o['span']} at {o['slot']} runs off the grid"); continue
        for cell in cs:
            if cell in used: out.append(f"{w}: overlaps {used[cell]} at r{cell[0] + 1}c{cell[1] + 1}")
            used[cell] = o["id"]
        if o.get("state") is not None and o["state"] not in PRIMS[kind].get("states", []):
            out.append(f"{w}: starting state must be one of {PRIMS[kind].get('states', [])}")
        _check_params(PRIMS[kind].get("params", {}), {**{k: o[k] for k in PRIMS[kind].get("params", {}) if k in o}, **(o.get("params") or {})}, w, out, fit)
        if kind == "steps":
            st = (o.get("params") or {}).get("steps") or []
            if not 3 <= len(st) <= 5 or not all(isinstance(s, dict) and s.get("id") and str(s.get("label") or "").strip() for s in st):
                out.append(f"{w}: steps must be 3 to 5 items with id and label")
            for s in st:
                fit(s.get("label"), "step", f"{w} step {s.get('id')}"); steps_ids.append(s.get("id"))
    if sum(1 for o in cast if o.get("kind") == "steps") and len(cast) > 3:
        out.append("an abstract steps diagram leaves room for at most 2 other objects")

    # chapters and events, simulating what is on screen
    chapters = plan.get("chapters") or []
    if not 2 <= len(chapters) <= 4:
        out.append("2 to 4 chapters are needed")
    drawn, links, spoken, gauge = set(), set(), [], False
    for ci, ch in enumerate(chapters):
        w = f"chapter {ci + 1}"
        fit(ch.get("chapter"), "chapter", f"{w} label"); fit(ch.get("kicker"), "kicker", f"{w} kicker")
        hl = ch.get("headline") or []
        if not isinstance(hl, list) or not 1 <= len(hl) <= 2:
            out.append(f"{w}: headline must be 1 or 2 lines")
        for line in hl if isinstance(hl, list) else []:
            fit(line, "headline", f"{w} headline")
        if ch.get("emphasis") not in (None, "ochre", "blue", "sage", "italic"):
            out.append(f"{w}: emphasis must be ochre, blue, sage or italic")
        nar = str(ch.get("narration") or "").strip()
        if not nar: out.append(f"{w}: narration is empty")
        spoken.append(nar); texts.append(nar)
        if ch.get("emphasis_on") and not _cue_ok(ch["emphasis_on"], nar):
            out.append(f"{w}: emphasis_on {ch['emphasis_on']!r} is not a word of its narration")
        evs = ch.get("events") or []
        if not evs: out.append(f"{w}: at least one event is needed")
        for ei, e in enumerate(evs):
            do, oid = e.get("do"), e.get("obj")
            we = f"{w} event {ei + 1} ({do}{' ' + str(oid) if oid else ''})"
            if not _cue_ok(str(e.get("on") or "start"), nar):
                out.append(f"{we}: on {e.get('on')!r} is not a word of this chapter's narration")
            if oid is not None:
                if oid not in ids:
                    out.append(f"{we}: no cast object {oid!r}"); continue
                kind = ids[oid]
                verbs = {**GENERIC_VERBS, **PRIMS[kind].get("verbs", {})}
                if do not in verbs:
                    out.append(f"{we}: a {kind} takes {', '.join(verbs)}"); continue
                if do != "draw" and oid not in drawn:
                    out.append(f"{we}: draw {oid} before changing it")
                if do == "draw": drawn.add(oid)
                if do == "hide": drawn.discard(oid)
                _check_params(verbs[do], e, we, out, fit, ids, links, steps_ids)
                if do == "callout" and not callout_place(plan, oid):
                    out.append(f"{we}: no free room next to {oid} for a callout label; free a neighbouring cell or drop it")
                if do == "message":
                    n = sum(1 for c in chapters[:ci + 1] for x in (c.get("events") or []) if x.get("obj") == oid and x.get("do") == "message")
                    if n > 3: out.append(f"{we}: a phone shows at most 3 messages")
                if kind == "timeline" and do in ("activity",) and not any(x.get("obj") == oid and x.get("do") == "window" for c in chapters[:ci + 1] for x in (c.get("events") or [])):
                    out.append(f"{we}: show the window first")
                if kind == "timeline" and do in ("shift_earlier", "reduce") and not any(x.get("obj") == oid and x.get("do") == "activity" for c in chapters[:ci + 1] for x in (c.get("events") or [])):
                    out.append(f"{we}: needs activity earlier")
            else:
                if do not in SCENE_EVENTS:
                    out.append(f"{we}: {do!r} needs an obj (cast id), or is not an event"); continue
                _check_params(SCENE_EVENTS[do], e, we, out, fit, ids, links, steps_ids)
                if do == "connect":
                    if not re.fullmatch(r"[a-z][a-z0-9_]{0,15}", str(e.get("id") or "")) or e.get("id") in links or e.get("id") in ids:
                        out.append(f"{we}: id must be a new short lower-case name")
                    for end in ("from", "to"):
                        if e.get(end) in ids and e.get(end) not in drawn:
                            out.append(f"{we}: draw {e.get(end)} before connecting it")
                    if e.get("from") == e.get("to"):
                        out.append(f"{we}: from and to must differ")
                    links.add(e.get("id"))
                if do == "gauge": gauge = True
    for t in texts:   # claims: numbers and absolute words only when the brief has them
        for d in re.findall(r"\d[\d,.:%]*", str(t)):
            if d.rstrip(".,") not in brief:
                out.append(f"claim check: {d!r} in {t!r} is not in the brief")
        for wd in words(t):
            if norm(wd) in BANNED and norm(wd) not in {norm(x) for x in words(b)}:
                out.append(f"claim check: {wd!r} in {t!r} is not in the brief")
    if facts.get("narration_supplied") and plan.get("supplied_narration"):
        if [norm(x) for x in words(" ".join(spoken))] != [norm(x) for x in words(plan["supplied_narration"])]:
            out.append("the chapters' narration must be the supplied narration, word for word and in order")
    total = len(words(" ".join(spoken)))
    if not 12 <= total <= 90:
        out.append(f"narration is {total} words; keep it between 12 and 90")
    target = target_seconds(brief)
    if target and not facts.get("narration_supplied") and chapters and not out:
        est = estimated_seconds(compile_plan(plan, "check", "check"))
        if not 0.8 * target <= est <= 1.2 * target:
            want = max(10, round(total * target / est))
            out.append(f"the brief asks for about {target} s but this plan runs about {est} s; use about {want} words in total"
                       + (" or fewer events after the last word of a chapter" if est > target else ""))
    return out


def estimated_seconds(pj):
    """The silent preview's length for a compiled project: the dry-timings maths of studio/vo.py and beats.py."""
    v, t = pj["voice"], pj["voice"].get("lead_in", 0.5)
    for s in pj["scenes"]:
        n = max(1, len(s["line"]["text"].split()))
        t += (n - 1) / DRY_WPS + 0.85 / DRY_WPS + 0.12 + s["line"].get("pause", [0.45, 0.35])[1]
    return round(t + v.get("tail", 2.6), 1)


# ---- layout helpers for callouts and connections ----
def callout_place(plan, oid):
    """Where a callout label for oid can go: above (top row or a free cell above), else beside. None = no room."""
    cast = {o["id"]: o for o in plan.get("cast") or [] if o.get("id")}
    o = cast.get(oid)
    if not o or not parse_slot(o.get("slot")) or not parse_span(o.get("span")):
        return None
    used = set()
    for x in cast.values():
        if x["id"] != oid and parse_slot(x.get("slot")) and parse_span(x.get("span")):
            used |= cells(x["slot"], x["span"])
    (r, c), (w, h) = parse_slot(o["slot"]), parse_span(o["span"])
    bx = box(o["slot"], o["span"])
    if r == 0 or all((r - 1, c + j) not in used for j in range(w)):
        return {"x": bx["cx"], "y": bx["y0"] + 6, "ly": bx["y0"] - 26}
    if c + w <= 2 and all((r + i, c + w) not in used for i in range(h)):
        return {"x": bx["x0"] + bx["w"] - 6, "y": bx["cy"] - 40, "lx": bx["x0"] + bx["w"] + 40, "ly": bx["cy"] - 40}
    if c >= 1 and all((r + i, c - 1) not in used for i in range(h)):
        return {"x": bx["x0"] + 6, "y": bx["cy"] - 40, "lx": bx["x0"] - 40, "ly": bx["cy"] - 40}
    return None


def _edge(bx, toward):
    """The point where the line from the box centre toward `toward` leaves the box (shrunk a little)."""
    cx, cy, hw, hh = bx["cx"], bx["cy"], bx["w"] * 0.42, bx["h"] * 0.42
    dx, dy = toward[0] - cx, toward[1] - cy
    if dx == 0 and dy == 0:
        return [cx, cy]
    k = min(hw / abs(dx) if dx else 1e9, hh / abs(dy) if dy else 1e9)
    return [round(cx + dx * k, 1), round(cy + dy * k, 1)]


def _label_rect(mx, my, side, n):
    """Approximate box of a link label (uppercase tag, about 15 px per character at 20 px) for a side."""
    w, h = 15 * n + 28, 40
    if side == "above": return (mx - w / 2, my - 34 - h, mx + w / 2, my - 34)
    if side == "left": return (mx - 30 - w, my - h / 2, mx - 30, my + h / 2)
    return (mx + 30, my - h / 2, mx + 30 + w, my + h / 2)


def _overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def _label_side(p0, p1, n, boxes, mids, horiz):
    """The side for a link's label that keeps it on the frame and off other links' markers and labels and off objects."""
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    best, score_best = None, None
    for side in (["above", "left", "right"] if horiz else ["left", "right", "above"]):
        r = _label_rect(mx, my, side, n)
        s = 0.0
        if r[0] < 40 or r[2] > 1040 or r[1] < 560: s += 1e6
        for (ox, oy, oside, on) in mids:
            s += 50 * _overlap(r, (ox - 24, oy - 24, ox + 24, oy + 24)) + 50 * _overlap(r, _label_rect(ox, oy, oside, on))
        for b in boxes.values():
            s += _overlap(r, (b["x0"] + b["w"] * 0.08, b["y0"] + b["h"] * 0.08, b["x0"] + b["w"] * 0.92, b["y0"] + b["h"] * 0.92))
        if score_best is None or s < score_best:
            best, score_best = side, s
    return best


# ---- compile ----
def _cue_name(word, used):
    base = re.sub(r"[^a-z0-9]", "", norm(word))[:12] or "w"
    name, k = base, 2
    while name in used:
        name = f"{base}{k}"; k += 1
    used.add(name)
    return name


def _est_word_time(nar, word):
    if word == "start":
        return 0.0
    for i, w in enumerate(words(nar)):
        if norm(w).startswith(norm(word)):
            return 0.2 + i / DRY_WPS
    return 0.0


def _object_def(o):
    """Renderer object data for one cast entry, sized to its grid box."""
    kind, bx, p = o["kind"], box(o["slot"], o["span"]), o.get("params") or {}
    base = {"id": o["id"], "kind": kind}
    if kind in ("person", "chair", "calendar", "phone", "envelope", "building"):
        d = {**base, "cx": bx["cx"], "cy": bx["cy"], "bw": bx["w"], "bh": bx["h"]}
        if o.get("state"): d["state"] = o["state"]
        if kind == "building" and (p.get("sign") or o.get("sign")): d["sign"] = p.get("sign") or o.get("sign")
        return d
    if kind == "house":
        s = round(min(bx["w"] / 360, bx["h"] / 300), 3)
        return {**base, "kind": "house", "x": bx["cx"], "y": bx["y0"] + bx["h"] - 10, "scale": s}
    if kind == "ac_unit":
        s = round(min(bx["w"] / 270, bx["h"] / 235), 3)
        return {**base, "kind": "ac_unit", "x": bx["cx"], "y": bx["y0"] + bx["h"] - 10, "scale": s}
    if kind == "thermostat":
        return {**base, "x": bx["cx"], "y": bx["cy"], "r": round(min(bx["w"], bx["h"]) * 0.36), "angle": -30}
    if kind == "timeline":
        y = bx["y0"] + bx["h"] - 50
        return {**base, "x": bx["x0"], "y": y, "w": bx["w"], "bandH": min(150, bx["h"] - 90),
                "left": p.get("left") or "EARLIER", "right": p.get("right") or "LATER",
                "bands": [{"id": "peak", "from": 0.56, "to": 0.82, "label": p.get("window_label") or "PEAK"}],
                "segs": [{"id": "early", "from": 0.40, "to": 0.56, "level": 0.9}, {"id": "atpeak", "from": 0.56, "to": 0.84, "level": 0.9}],
                "playhead": {"pos": 0.3}}
    if kind == "steps":
        st = p.get("steps") or []
        n = max(1, len(st))
        bh = int(min(150, (bx["h"] - (n - 1) * 46) / n))
        gap = int((bx["h"] - n * bh) / max(1, n - 1))
        return {**base, "kind": "flow", "x": bx["x0"], "y": bx["y0"], "w": int(bx["w"] * 0.72), "boxH": bh, "gap": gap,
                "nodes": [{"id": s["id"], "label": s["label"]} for s in st]}
    raise ValueError(kind)


def compile_plan(plan, name, title):
    """The composition plan -> a project.json dict with fieldnotes scenes. Deterministic: same plan, same project."""
    t = json.loads((STYLE_DIR / "template.json").read_text(encoding="utf-8"))
    pal = t["palette"]
    palette = {"primary": pal["sage"], "accent": pal["ochre"], "ink": pal["ink"], "paper": pal["paper"], "ink2": pal["inkSoft"],
               "grid": pal["grid"], "muted": "#8A8378", "ochre": pal["ochre"], "ochreRule": pal["ochreRule"], "sage": pal["sage"],
               "sageWipe": pal["sageWipe"], "sageTint": pal["sageTint"], "blue": pal["dustyBlue"], "blueStroke": pal["blueStroke"],
               "ground": pal["groundTint"], "card": "#F6F1E8"}
    cast = {o["id"]: o for o in plan["cast"]}
    boxes = {oid: box(o["slot"], o["span"]) for oid, o in cast.items()}
    business = (plan.get("facts") or {}).get("business") or ""
    brand = re.sub(r"[^A-Za-z0-9 &'.]", "", re.sub(r"\(.*?\)", "", business)).strip().upper()[:28]
    chs, n = plan["chapters"], len(plan["chapters"])
    scenes, gauge_drawn, links, link_mids = [], False, {}, []
    for ci, ch in enumerate(chs):
        sid, nar, used = f"F{ci + 1:02d}", ch["narration"].strip(), set()
        cues, actions, objects, cue_of = [], [], [], {}
        if ci == 0:
            objects += [_object_def(o) for o in plan["cast"]]

        def at(word, off=0.0):
            if word in (None, "start"):
                return round(0.35 + off, 2)
            if word not in cue_of:
                cue_of[word] = _cue_name(word, used)
                cues.append({"name": cue_of[word], "at": word, "sfx": None})
            return f"{cue_of[word]}{off:+.2f}" if off else cue_of[word]

        hl = [{"text": x} for x in ch["headline"]]
        if len(hl) == 2 and ch.get("emphasis"):
            hl[1]["em"] = ch["emphasis"]
            if ch.get("emphasis_on"):
                hl[1]["at"] = at(ch["emphasis_on"], 0.15)
        last_est, seq, prev_on = 0.0, 0.0, None
        evs = ch["events"]
        word_t = [_est_word_time(nar, x.get("on") or "start") for x in evs]
        for k, e in enumerate(evs):
            on = e.get("on") or "start"
            # events on the same word unfold 0.2 s apart, but never past the next spoken cue (order stays as planned)
            nxt = next((word_t[j] for j in range(k + 1, len(evs)) if (evs[j].get("on") or "start") != on), None)
            room = max(0.0, (nxt - word_t[k] - 0.15)) if nxt is not None else 1.2
            seq = min(seq + 0.2, room) if on == prev_on else 0.0
            prev_on = on
            when = (lambda off=0.0: at(on, seq + off))
            last_est = max(last_est, _est_word_time(nar, on) + seq + 1.2)
            do, oid = e["do"], e.get("obj")
            kind = cast[oid]["kind"] if oid else None
            if oid and do == "draw":
                actions.append({"at": when(), "do": "draw", "target": oid, "dur": 1.4 if kind == "steps" else 0.7})
            elif oid and do == "hide":
                actions.append({"at": when(), "do": "hide", "target": oid})
            elif oid and do == "callout":
                cid = f"co{ci + 1}{k}"
                objects.append({"id": cid, "kind": "callout", **callout_place(plan, oid), "style": "tag", "text": e["text"]})
                actions.append({"at": when(0.2), "do": "show", "target": cid})
            elif oid and do == "state":
                actions.append({"at": when(), "do": "state", "target": oid, "state": e["state"]})
            elif oid and do == "remind":
                actions.append({"at": when(), "do": "remind", "target": oid, "days_before": e["days_before"], "medium": e["medium"]})
            elif oid and do == "message":
                actions.append({"at": when(), "do": "message", "target": oid, "type": e["type"], "text": e["text"]})
            elif oid and do == "bury":
                actions.append({"at": when(), "do": "bury", "target": oid})
            elif oid and do == "cool":
                arrow_id = f"{oid}_air"
                src = next((x for x in cast.values() if x["kind"] == "ac_unit"), None)
                linked = src and any(x.get("do") == "connect" and {x.get("from"), x.get("to")} == {src["id"], oid}
                                     for c2 in chs for x in c2["events"])
                if src and not linked:   # the plan did not connect them itself: show the airflow
                    a, bxh = boxes[src["id"]], boxes[oid]
                    p0 = [a["cx"] - a["w"] * 0.3, a["cy"] - a["h"] * 0.15]
                    p2 = [bxh["cx"] + bxh["w"] * 0.25, bxh["cy"] - bxh["h"] * 0.05]
                    objects.append({"id": arrow_id, "kind": "arrow", "points": [p0, [(p0[0] + p2[0]) / 2, min(p0[1], p2[1]) - 90], p2], "color": "blueStroke", "dash": True, "width": 6})
                    actions += [{"at": when(), "do": "draw", "target": arrow_id, "dur": 0.6}, {"at": when(0.5), "do": "flow", "target": arrow_id, "dur": 2.4}]
                actions.append({"at": when(0.2), "do": "fill", "target": oid, "level": 1 if e.get("level") != "partial" else 0.6, "dur": 1.4})
            elif oid and do == "speed":
                actions.append({"at": when(), "do": "run", "target": oid, "speed": {"high": 1.6, "low": 0.45, "off": 0}[e["speed"]]})
            elif oid and do == "turn":
                actions.append({"at": when(), "do": "turn", "target": oid, "by": 28 if e["direction"] == "up" else -28, "dur": 0.8})
            elif oid and kind == "timeline":
                if do == "window":
                    actions.append({"at": when(), "do": "show", "target": f"{oid}.peak"})
                elif do == "activity":
                    actions += [{"at": when(), "do": "show", "target": f"{oid}.early", "dur": 0.4}, {"at": when(0.3), "do": "show", "target": f"{oid}.atpeak", "dur": 0.5}]
                elif do == "shift_earlier":
                    objects.append({"id": oid, "segs": [{"id": "moved", "from": 0.62, "to": 0.78, "level": 0.45}]})
                    actions += [{"at": when(), "do": "show", "target": f"{oid}.moved", "dur": 0.3},
                                {"at": when(0.3), "do": "seg", "target": f"{oid}.moved", "from": 0.22, "to": 0.38, "level": 0.9, "dur": 0.9},
                                {"at": when(0.3), "do": "seg", "target": f"{oid}.atpeak", "level": 0.55, "dur": 0.9}]
                elif do == "reduce":
                    actions.append({"at": when(), "do": "seg", "target": f"{oid}.atpeak", "level": 0.2 if e["level"] == "low" else 0.5, "dur": 0.9})
                elif do == "playhead":
                    a0, a1 = (0.56, 0.82) if e["through"] == "window" else (0.2, 0.5)
                    actions += [{"at": when(), "do": "show", "target": f"{oid}.playhead"},
                                {"at": when(0.05), "do": "playhead", "target": f"{oid}.playhead", "from": a0, "to": a1, "dur": 2.0},
                                {"at": "end-0.45", "do": "hide", "target": f"{oid}.playhead"}]
            elif oid and kind == "steps":
                ids = [s["id"] for s in cast[oid]["params"]["steps"]]
                if do == "highlight":
                    actions.append({"at": when(), "do": "highlight", "target": f"{oid}.{e['step']}", "tone": {"problem": "ochre", "fix": "sage", "neutral": "blue"}[e["tone"]]})
                elif do in ("break", "fix"):
                    i = ids.index(e["step"])
                    if i + 1 < len(ids):
                        actions.append({"at": when(), "do": "mark", "target": f"{oid}.l{i + 1}", "state": "broken" if do == "break" else "ok", "label": e.get("label") or ""})
                elif do == "pulse":
                    actions.append({"at": when(), "do": "pulse", "target": oid, "from": ids[0], "to": ids[-1], "dur": 1.6})
            elif do == "connect":
                a, bb = boxes[e["from"]], boxes[e["to"]]
                p0, p1 = _edge(a, (bb["cx"], bb["cy"])), _edge(bb, (a["cx"], a["cy"]))
                links[e["id"]] = True
                horiz = abs(p1[0] - p0[0]) > abs(p1[1] - p0[1])
                labels = [x for x in (e.get("label"), *(y.get("label") for c2 in chs for y in c2["events"] if y.get("link") == e["id"])) if x]
                side = _label_side(p0, p1, max((len(x) for x in labels), default=0), boxes, link_mids, horiz)
                link_mids.append(((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, side, max((len(x) for x in labels), default=0)))
                objects.append({"id": e["id"], "kind": "link", "from": p0, "to": p1, "style": e.get("style") or "solid", "label": e.get("label") or "",
                                "bend": 0.12 if horiz else 0.18, "labelSide": side})
                actions.append({"at": when(), "do": "draw", "target": e["id"], "dur": 0.6})
            elif do in ("break", "fix"):
                actions.append({"at": when(), "do": "mark", "target": e["link"], "state": "broken" if do == "break" else "ok", "label": e.get("label") or ""})
            elif do == "pulse":
                actions.append({"at": when(), "do": "pulse", "target": e["link"], "dur": 1.2})
            elif do == "gauge":
                if not gauge_drawn:
                    objects.append({"id": "gauge", "kind": "gauge", "x": 72, "y": 1566, "w": 520, "label": e["label"], "level": LEVEL[e["level"]], "color": "blueStroke"})
                    actions.append({"at": when(), "do": "draw", "target": "gauge", "dur": 0.6}); gauge_drawn = True
                else:
                    actions.append({"at": when(), "do": "set", "target": "gauge", "level": LEVEL[e["level"]], "dur": 0.9})
            elif do == "note":
                nid = f"no{ci + 1}{k}"
                objects.append({"id": nid, "kind": "note", "x": 1008, "y": 1584, "align": "right", "size": 34, "text": e["text"]})
                actions.append({"at": when(0.2), "do": "show", "target": nid})
            elif do == "checklist":
                objects.append({"id": "card", "kind": "card", "x": 72, "y": 1640, "w": 860, "text": e["text"]})
                actions.append({"at": when(), "do": "show", "target": "card"})
        speech = 0.2 + max(1, len(words(nar))) / DRY_WPS
        hold = round(min(1.6, max(0.4, last_est - speech + 0.5)), 2) if ci < n - 1 else 0
        scenes.append({"id": sid, "type": "fieldnotes", "line": {"text": nar, "pause": [0, hold]}, "cues": cues, "data": {
            **({"transition": "bands"} if ci == n - 1 and n > 2 else {}),
            "header": {"brand": brand, "label": "FIELD NOTES", "chapter": ch["chapter"].upper(), "index": ci + 1, "total": n},
            "kicker": (ch.get("kicker") or "").upper(), "headline": {"lines": hl}, "objects": objects, "actions": actions}})
    from .fieldnotes_plan import DEFAULT_VOICE
    return {"name": name, "title": title, "style": "entertainment",
            "_note": "Generated by `studio.py fieldnotes` from fieldnotes/brief-v*.txt; do not hand-edit (revise the brief instead).",
            "palette": palette, "fonts": {"title": "Inter Tight", "body": "Inter", "note": "Instrument Serif"},
            "voice": copy.deepcopy(DEFAULT_VOICE), "audio": {}, "music": {}, "sfx": {}, "scenes": scenes}
