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

# Versions recorded with every plan (report-v<N>.json "versions"). Bump the matching number with any change:
#   schema     1 stage diagrams (a280b4f); 2 cast of illustrated objects on a 3x3 grid (c7def36)
#   planner    prompt + compiler. 1 a280b4f; 2 c7def36; 3 same-word stagger, label placement (4889af8); 4 zoom (9baa194);
#              5 claims ledger in the reply, one closing line, timeline drawn as an illustrative example
#   validator  1 stage plans; 2 composition plans (c7def36, 4889af8); 3 outcome strength, label room, zoom rules (9baa194);
#              4 factual grounding (brief words, quantifiers, claims ledger) and closing-card capacity (2026-10-12)
#   renderer   engine/fieldnotes.js "Renderer version: N". 1 f4e3192; 2 c7def36; 3 4889af8; 4 zoom, available (9baa194);
#              5 phone messages always shown whole (smaller type when long; 4 cut them off)
# A saved plan is compatible when its schema is current and it passes the current validator. A renderer or compiler
# change alone never needs a new plan (`fieldnotes rebuild` reuses it); a stricter validator can make an old plan need
# migration, which plans the same approved brief again (`fieldnotes migrate`) and never rewrites the old version.
PLAN_SCHEMA, PLANNER_VERSION, VALIDATOR_VERSION = 2, 5, 4


def renderer_version():
    m = re.search(r"Renderer version: (\d+)", (ROOT / "engine" / "fieldnotes.js").read_text(encoding="utf-8")[:2000])
    return int(m.group(1)) if m else None


def versions():
    return {"schema": PLAN_SCHEMA, "planner": PLANNER_VERSION, "validator": VALIDATOR_VERSION, "renderer": renderer_version()}


def plan_schema(plan):
    """1 for the old stage-diagram plans, 2 for cast plans, 0 if unrecognised."""
    if isinstance(plan, dict) and isinstance(plan.get("cast"), list):
        return 2
    if isinstance(plan, dict) and plan.get("stage"):
        return 1
    return 0
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
              "spans": ["1x1", "2x1", "2x2"], "states": ["empty", "occupied"], "verbs": {"state": {"state": E("empty", "occupied")}},
              "outcome_states": ["occupied"]},
    "calendar": {"desc": "a calendar with one appointment day: booked, empty (missed, an X), available (an open slot that can be offered, a plus) or rebooked (a confirmed new booking, a check); 'remind' marks a reminder sent N days before with an arrow to the appointment",
                 "spans": ["1x1", "2x1", "2x2"], "states": ["booked", "empty", "available", "rebooked"],
                 "verbs": {"state": {"state": E("booked", "empty", "available", "rebooked")}, "remind": {"days_before": {"int": [1, 3]}, "medium": E("email", "text")}},
                 "outcome_states": ["rebooked"]},
    "phone": {"desc": "a phone screen showing up to 3 messages in order: an email notification, a text from the business, or the customer's reply; 'bury' stacks other notifications above the messages so they sink out of sight; 'zoom' rings one message and draws zoom lines to another cast object that shows THAT SAME message enlarged (for example an envelope)",
              "spans": ["1x2"], "verbs": {"message": {"type": E("email", "text", "reply"), "text": {"str": "message"}}, "bury": {},
                                          "zoom": {"msg": E("email", "text", "reply"), "to": {"obj": True}}}},
    "envelope": {"desc": "an email or letter: sent, unread (a dot), missed (faded) or opened",
                 "spans": ["1x1", "2x1"], "states": ["sent", "unread", "missed", "opened"], "verbs": {"state": {"state": E("sent", "unread", "missed", "opened")}}},
    "building": {"desc": "the business's premises (shop, clinic, office) with a short sign", "spans": ["1x1", "2x1", "2x2"], "params": {"sign": {"str": "sign"}}},
    "house": {"desc": "a home with blue cooling that can fill it", "spans": ["2x1"], "verbs": {"cool": {"level": E("full", "partial")}}},
    "ac_unit": {"desc": "an outdoor air-conditioning unit whose fan runs high, low or off", "spans": ["1x1"], "verbs": {"speed": {"speed": E("high", "low", "off")}}},
    "thermostat": {"desc": "a wall thermostat dial that can be turned up or down", "spans": ["1x1"], "verbs": {"turn": {"direction": E("up", "down")}}},
    "timeline": {"desc": "an ILLUSTRATIVE example day from earlier to later (not anyone's measured usage) with a price or time window, activity bars, and a moving marker; 'shift_earlier' moves SOME of the activity before the window while part stays in it, 'reduce' shrinks what is in the window (never all of it)",
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
    texts, tagged = [], []   # tagged: (text, kind, where) for the grounding checks

    def fit(text, key, where):
        if text is None: return
        texts.append(str(text)); tagged.append((str(text), key, where))
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
        if isinstance(hl, list) and hl:
            tagged.append((" ".join(str(x) for x in hl), "headline_full", f"{w} headline"))
        if ch.get("emphasis") not in (None, "ochre", "blue", "sage", "italic"):
            out.append(f"{w}: emphasis must be ochre, blue, sage or italic")
        nar = str(ch.get("narration") or "").strip()
        if not nar: out.append(f"{w}: narration is empty")
        spoken.append(nar); texts.append(nar); tagged.append((nar, "narration", f"{w} narration"))
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
                if do == "zoom":
                    if e.get("to") == oid or e.get("to") not in drawn:
                        out.append(f"{we}: zoom needs another cast object, drawn first, to show the enlarged message")
                    if not any(x.get("obj") == oid and x.get("do") == "message" and x.get("type") == e.get("msg")
                               for c2 in chapters[:ci + 1] for x in (c2.get("events") or [])[: (ei if c2 is ch else None)]):
                        out.append(f"{we}: no {e.get('msg')} message on {oid} yet to zoom into")
                    if sum(1 for c2 in chapters for x in (c2.get("events") or []) if x.get("obj") == oid and x.get("do") == "zoom") > 1:
                        out.append(f"{we}: one zoom per phone")
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
    out += outcome_problems(plan, brief, ids)
    out += link_label_problems(plan)
    out += closing_card_problems(plan)
    src = fact_text(brief)   # constraint lines ("no guaranteed outcomes") never count as support
    for t in texts:   # claims: numbers and absolute words only when the brief's facts have them
        for d in re.findall(r"\d[\d,.:%]*", str(t)):
            if d.rstrip(".,") not in src:
                out.append(f"claim check: {d!r} in {t!r} is not in the brief")
        for wd in words(t):
            if norm(wd) in BANNED and norm(wd) not in {norm(x) for x in words(src)}:
                out.append(f"claim check: {wd!r} in {t!r} is not in the brief")
    out += grounding_problems(plan, brief, tagged)
    if facts.get("narration_supplied") and plan.get("supplied_narration"):
        if [norm(x) for x in words(" ".join(spoken))] != [norm(x) for x in words(plan["supplied_narration"])]:
            out.append("the chapters' narration must be the supplied narration, word for word and in order")
    total = len(words(" ".join(spoken)))
    if not 12 <= total <= 90:
        out.append(f"narration is {total} words; keep it between 12 and 90")
    target = target_seconds(brief)
    if target and not facts.get("narration_supplied") and chapters:
        try:   # also with other problems, so one repair call sees the length too (2026-10-12)
            est = estimated_seconds(compile_plan(plan, "check", "check"))
        except Exception:
            est = None   # a plan too broken to compile; its other problems come first
        if est and not 0.8 * target <= est <= 1.2 * target:
            want = max(10, round(total * target / est))
            out.append(f"the brief asks for about {target} s but this plan runs about {est} s; use about {want} words in total"
                       + (" or fewer events after the last word of a chapter" if est > target else ""))
    return out


# ---- factual grounding and closing-card capacity (validator 4, 2026-10-12) ----
# No numbers or guarantee words is not the same as accurate. A plan's statements must be built from the brief's FACT
# lines: every on-screen or drafted word comes from the brief (framing words aside), an amount or comparison (most,
# hardest, all...) appears in the brief sentence quoted for it, and each headline, callout, note, closing line, label,
# gauge label and drafted narration sentence cites the brief sentence that supports it, word for word ("claims").
# These checks stop invented or stretched statements; they cannot prove the brief itself is true (a person confirms it).
NOT_FACTS_RE = re.compile(r"^\s*(constraints?|length|style(\s+notes?)?|notes?\s+for\s+the\s+planner|format)\s*:", re.I)
FRAMING = set("""a an the and or but if so to of in on at for with by from as into onto up down off out over under via per
it its it's this that these those there here then now when while where what why how who which than too also just even
you your you're yours we we're our us they their them he she his her i i'm me my is are was were be been being am
do does did done have has had having get gets got can could may might will would should must shall let lets let's
not no yes before after during earlier later early late first next last soon again still once ago until
step steps way example illustrative eg problem cause fix change shift outcome result why tip tips note
earlier later today day""".split())
QUANT = {"most", "more", "less", "least", "fewer", "fewest", "all", "every", "everyone", "everything", "none", "only",
         "always", "never", "majority", "half", "double", "twice", "triple", "entire", "whole", "max", "maximum",
         "minimum", "much", "many", "lots", "plenty", "nothing", "nobody", "everywhere"}
EST_OK = {"interest", "request", "honest", "modest", "suggest", "rest", "test", "west", "guest", "forest", "harvest",
          "contest", "invest", "protest", "digest", "nest", "chest", "quest", "arrest", "manifest", "pest", "vest"}
LEDGER_KINDS = ("headline_full", "callout", "note", "checklist", "label", "gauge_label", "narration")
LEXICAL_SKIP = ("chapter", "headline_full", "message")   # phone messages are dialogue in the picture; numbers and guarantee words still apply


def fact_text(brief):
    """The brief without its constraint, length and style lines: the only text that can support a statement."""
    return "\n".join(l for l in str(brief).splitlines() if not NOT_FACTS_RE.match(l))


def _stems(text):
    return [w for w in (norm(x).replace("'s", "") for x in words(text)) if w]


def _key(text):
    return " " + " ".join(_stems(text)) + " "


def _quant(w):
    return w in QUANT or (re.fullmatch(r"[a-z]{3,}est", w) is not None and w not in EST_OK)


def _supported(w, pool):
    if w in pool:
        return True
    if len(w) < 4:
        return False
    return any(len(b) >= 4 and w[:min(5, len(w), len(b))] == b[:min(5, len(w), len(b))] for b in pool)


def _sentences(text):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", str(text).strip()) if x.strip()]


def grounding_problems(plan, brief, tagged):
    src = fact_text(brief)
    pool = set(_stems(src))
    out = []
    for text, kind, where in tagged:
        if kind in LEXICAL_SKIP:
            continue
        ws = _stems(text)
        q = sorted({w for w in ws if _quant(w) and w not in pool})
        if q:
            out.append(f"claim check: {where} {text!r} states an amount or comparison ({', '.join(q)}) that the brief does not; say only what the brief says")
        unk = sorted({w for w in ws if w not in FRAMING and not _quant(w) and not w.isdigit() and not _supported(w, pool)})
        if unk:
            out.append(f"claim check: {where} {text!r} uses {', '.join(unk)}, which the brief does not state; use the brief's own facts and words")
    ledger = {}
    for c in plan.get("claims") or []:
        if isinstance(c, dict) and c.get("text"):
            ledger[_key(c["text"])] = c
    supplied = bool((plan.get("facts") or {}).get("narration_supplied") and plan.get("supplied_narration"))
    srck = _key(src)
    for text, kind, where in tagged:
        if kind not in LEDGER_KINDS or (kind == "narration" and supplied) or not str(text).strip():
            continue
        for unit in (_sentences(text) if kind == "narration" else [text]):
            c = ledger.get(_key(unit))
            if not c:
                out.append(f"claim check: {where} {unit!r} needs a \"claims\" entry quoting, word for word, the brief sentence that supports it")
                continue
            sup = str(c.get("support") or "")
            if len(_stems(sup)) < 2 or _key(sup) not in srck:
                out.append(f"claim check: the support for {unit!r} must be copied word for word from the brief's facts (not its constraints)")
                continue
            sp = set(_stems(sup))
            q = sorted({w for w in _stems(unit) if _quant(w) and w not in sp})
            if q:
                out.append(f"claim check: {unit!r} says {', '.join(q)} but its support {sup!r} does not")
    return out


def closing_card_problems(plan):
    """The closing card holds one line, in the last chapter; notes share one spot, so one per chapter."""
    out, chs = [], plan.get("chapters") or []
    lines = [(ci, e) for ci, ch in enumerate(chs) for e in ch.get("events") or [] if e.get("do") == "checklist"]
    if len(lines) > 1:
        out.append(f"the closing card holds one line, but the plan gives {len(lines)} checklist events "
                   f"({'; '.join(repr(e.get('text')) for _, e in lines)}); keep one")
    for ci, e in lines:
        if ci != len(chs) - 1:
            out.append(f"chapter {ci + 1}: the closing checklist belongs in the last chapter")
    for ci, ch in enumerate(chs):
        n = sum(1 for e in ch.get("events") or [] if e.get("do") == "note")
        if n > 1:
            out.append(f"chapter {ci + 1}: one note per chapter (notes share one spot), not {n}")
    return out


HEDGE_RE = re.compile(r"\b(can|could|may|might|able to)\b", re.I)


def outcome_problems(plan, brief, ids):
    """The picture and narration must not state the outcome more strongly than the brief. When the brief's outcome is
    only possible ("the slot can be offered"), states that show it done (a calendar 'rebooked', a chair 'occupied'
    after being empty) are refused, and the last chapter's narration must keep a hedge (can, could, may)."""
    outcome = str((plan.get("facts") or {}).get("outcome") or "")
    m = re.search(r"outcome[^:\n]*:\s*(.+)", brief, re.I)
    source = (m.group(1) if m else "") + " " + outcome
    if not HEDGE_RE.search(source):
        return []
    out, chapters = [], plan.get("chapters") or []
    for ci, ch in enumerate(chapters):
        for e in ch.get("events") or []:
            kind = ids.get(e.get("obj"))
            if e.get("do") == "state" and kind and e.get("state") in PRIMS[kind].get("outcome_states", []) and ci > 0:
                out.append(f"outcome check: chapter {ci + 1} shows {e['obj']} as {e['state']!r}, but the brief only says the outcome is possible "
                           f"({source.strip()[:80]!r}); show it as possible (for a calendar, 'available') rather than done")
    if chapters and not HEDGE_RE.search(str(chapters[-1].get("narration") or "")):
        out.append("outcome check: the brief's outcome is only possible, so the last chapter's narration must keep that (can, could or may)")
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
    if side == "below": return (mx - w / 2, my + 34, mx + w / 2, my + 34 + h)
    if side == "left": return (mx - 30 - w, my - h / 2, mx - 30, my + h / 2)
    return (mx + 30, my - h / 2, mx + 30 + w, my + h / 2)


def _overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def _label_side(p0, p1, n, boxes, mids, horiz, with_score=False):
    """The side for a link's label that keeps it on the frame and off other links' markers and labels and off objects
    (with_score: also the overlap score of that side; 0 means a clean spot)."""
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    best, score_best = None, None
    for side in (["above", "below", "left", "right"] if horiz else ["left", "right", "above", "below"]):
        r = _label_rect(mx, my, side, n)
        s = 0.0
        if r[0] < 40 or r[2] > 1040 or r[1] < 560: s += 1e6
        for (ox, oy, oside, on) in mids:   # other links' markers, and the labels already placed
            s += 50 * _overlap(r, (ox - 24, oy - 24, ox + 24, oy + 24)) + (50 * _overlap(r, _label_rect(ox, oy, oside, on)) if oside else 0)
        for b in boxes.values():   # labels stay off the drawings too (whole boxes: a phone's edge is inside its box)
            s += 3 * _overlap(r, (b["x0"], b["y0"], b["x0"] + b["w"], b["y0"] + b["h"]))
        if score_best is None or s < score_best:
            best, score_best = side, s
    return (best, score_best) if with_score else best


def link_label_problems(plan):
    """Connections whose label has no clean spot (it would cover a drawing, another link or leave the frame)."""
    cast = {o["id"]: o for o in plan.get("cast") or [] if o.get("id") and parse_slot(o.get("slot")) and parse_span(o.get("span"))}
    boxes = {oid: box(o["slot"], o["span"]) for oid, o in cast.items()}
    conns = [x for c in plan.get("chapters") or [] for x in c.get("events") or [] if x.get("do") == "connect" and x.get("from") in boxes and x.get("to") in boxes]
    geo = {x["id"]: (_edge(boxes[x["from"]], (boxes[x["to"]]["cx"], boxes[x["to"]]["cy"])), _edge(boxes[x["to"]], (boxes[x["from"]]["cx"], boxes[x["from"]]["cy"]))) for x in conns}
    out, placed = [], []
    for x in conns:
        labels = [l for l in (x.get("label"), *(y.get("label") for c in plan["chapters"] for y in c.get("events") or [] if y.get("link") == x["id"])) if l]
        if not labels:
            continue
        p0, p1 = geo[x["id"]]
        horiz = abs(p1[0] - p0[0]) > abs(p1[1] - p0[1])
        n = max(len(l) for l in labels)
        others = [((q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2, None, 0) for lid, (q0, q1) in geo.items() if lid != x["id"]]
        side, score = _label_side(p0, p1, n, boxes, placed + others, horiz, with_score=True)
        placed.append(((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, side, n))
        if score > 0:
            out.append(f"connection {x['id']} ({x['from']} to {x['to']}): no clear room for its label {labels[-1]!r}; "
                       "place the two objects further apart (leave a free cell between or beside them) or shorten the label")
    return out


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
    # every link's ends up front, so each label avoids all links' markers, including later ones
    link_geo = {}
    for c2 in chs:
        for x in c2["events"]:
            if x.get("do") == "connect" and x.get("from") in boxes and x.get("to") in boxes:
                a2, b2 = boxes[x["from"]], boxes[x["to"]]
                link_geo[x["id"]] = (_edge(a2, (b2["cx"], b2["cy"])), _edge(b2, (a2["cx"], a2["cy"])))
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
            elif oid and do == "zoom":
                tb = boxes[e["to"]]
                rect = {"x0": round(tb["x0"] + tb["w"] * 0.12), "x1": round(tb["x0"] + tb["w"] * 0.88), "y0": round(tb["y0"] + tb["h"] * 0.18), "y1": round(tb["y0"] + tb["h"] * 0.82)}
                actions.append({"at": when(), "do": "zoom", "target": oid, "msg": e["msg"], "rect": rect})
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
                others = [((q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2, None, 0) for lid, (q0, q1) in link_geo.items() if lid != e["id"]]
                side = _label_side(p0, p1, max((len(x) for x in labels), default=0), boxes, link_mids + others, horiz)
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


# ---- review: a readable storyboard, saved-plan compatibility, and what changed between two plans ----
def _q(s):
    return f'"{s}"'


def event_text(e, kinds):
    """One event as a plain sentence for the storyboard (no dashes)."""
    do, o = e.get("do"), e.get("obj")
    name = f"{o} ({kinds.get(o, '?')})" if o else ""
    lab = f", labelled {_q(e['label'])}" if e.get("label") else ""
    if do == "draw": return f"draw {name}"
    if do == "hide": return f"hide {o}"
    if do == "state": return f"{o} becomes {e.get('state')}"
    if do == "message": return f"{o} shows {'an' if str(e.get('type')).startswith('e') else 'a'} {e.get('type')}: {_q(e.get('text', ''))}"
    if do == "bury": return f"other notifications bury the messages on {o}"
    if do == "zoom": return f"{o} zooms its {e.get('msg')} into {e.get('to')} (the same message, enlarged)"
    if do == "remind": return f"{o} marks a {e.get('medium')} reminder {e.get('days_before')} day{'' if e.get('days_before') == 1 else 's'} before"
    if do == "callout": return f"label on {o}: {_q(e.get('text', ''))}"
    if do == "speed": return f"the {o} fan runs {e.get('speed')}"
    if do == "cool": return f"cool air fills {o} ({e.get('level')})"
    if do == "turn": return f"{o} turns {e.get('direction')}"
    if do == "window": return f"{o} shows its price or time window"
    if do == "activity": return f"activity bars appear on {o}"
    if do == "shift_earlier": return f"the activity on {o} shifts earlier"
    if do == "reduce": return f"the activity on {o} shrinks to {e.get('level')}"
    if do == "playhead": return f"the marker on {o} moves through {'the window' if e.get('through') == 'window' else 'the time before it'}"
    if do == "highlight": return f"step {e.get('step')} on {o} is highlighted ({e.get('tone')})"
    if do in ("break", "fix") and o: return f"the link after step {e.get('step')} on {o} {'breaks' if do == 'break' else 'is fixed'}{lab}"
    if do == "pulse" and o: return f"a pulse runs along {o}"
    if do == "connect": return f"{e.get('style', 'solid')} connection {e.get('id')} from {e.get('from')} to {e.get('to')}{lab}"
    if do in ("break", "fix") and not o: return f"connection {e.get('link')} {'breaks' if do == 'break' else 'is fixed'}{lab}"
    if do == "pulse" and not o: return f"a pulse travels along {e.get('link')}"
    if do == "gauge": return f"gauge {_q(e.get('label', ''))} reads {e.get('level')}"
    if do == "note": return f"note: {_q(e.get('text', ''))}"
    if do == "checklist": return f"closing checklist: {_q(e.get('text', ''))}"
    extra = ", ".join(f"{k} {v}" for k, v in e.items() if k not in ("on", "do", "obj"))
    return f"{o} {do}" + (f" ({extra})" if extra else "")


def storyboard(plan, version=None, duration=None):
    """The plan as a short storyboard a person can read and approve in chat (markdown, no JSON)."""
    if plan_schema(plan) != 2:
        return "(this plan uses an older format; migrate it to get a storyboard)"
    kinds = {o["id"]: o["kind"] for o in plan.get("cast") or [] if o.get("id")}
    head = f"**Storyboard{' v' + str(version) if version else ''}**" + (f" (about {round(float(duration), 1)} s, silent preview)" if duration else "")
    cast = "; ".join(f"{o['id']} = {o['kind']} {o.get('span')} at {o.get('slot')}" + (f", starts {o['state']}" if o.get("state") else "")
                     for o in plan.get("cast") or [])
    lines = [head, "", f"Cast: {cast}", ""]
    for i, ch in enumerate(plan.get("chapters") or []):
        hl = " / ".join(ch.get("headline") or [])
        lines.append(f"{i + 1}. **{ch.get('chapter', '')}**" + (f" · {ch['kicker']}" if ch.get("kicker") else ""))
        lines.append(f"   Headline: {hl}" + (f" ({ch['emphasis']} on line 2)" if ch.get("emphasis") else ""))
        lines.append(f"   Says: {_q(ch.get('narration', '').strip())}")
        evs = [(("at the start" if (e.get("on") in (None, "start")) else f"on {_q(e['on'])}"), event_text(e, kinds)) for e in ch.get("events") or []]
        lines.append("   Shows: " + "; ".join(f"{w}, {t}" for w, t in evs))
    stand = [m for m in plan.get("missing_primitives") or [] if isinstance(m, dict) and not m.get("essential")]
    if stand:
        lines += ["", "Stand-ins: " + "; ".join(f"{m.get('name')}: {m.get('why')}" for m in stand)]
    if plan.get("narration_draft"):
        lines += ["", "Narration was drafted from the brief's facts (not supplied by the owner)."]
    return "\n".join(lines)


def end_states(plan):
    """Each object's state at the end of the video, and whether it is still on screen."""
    st = {o["id"]: o.get("state") or "shown" for o in plan.get("cast") or [] if o.get("id")}
    for ch in plan.get("chapters") or []:
        for e in ch.get("events") or []:
            if e.get("obj") in st:
                if e.get("do") == "state": st[e["obj"]] = e.get("state")
                if e.get("do") == "hide": st[e["obj"]] = "hidden"
    return st


def _texts(plan, do, key):
    return [e.get(key) for ch in plan.get("chapters") or [] for e in ch.get("events") or [] if e.get("do") == do and e.get(key)]


def plan_changes(old, new, old_seconds=None, new_seconds=None):
    """What a migration or revision changed, as plain sentences for a person to review."""
    out = []
    so, sn = plan_schema(old), plan_schema(new)
    if so != sn:
        out.append(f"format: schema {so} ({'stage diagram' if so == 1 else 'unknown'}) replaced by schema {sn} (illustrated cast)"
                   + (f"; the old diagram was {old.get('stage')!r}" if so == 1 else ""))
    oc, nc = old.get("chapters") or [], new.get("chapters") or []
    if len(oc) != len(nc):
        out.append(f"chapters: {len(oc)} became {len(nc)}")
    for i in range(max(len(oc), len(nc))):
        a, b = (oc[i] if i < len(oc) else {}), (nc[i] if i < len(nc) else {})
        for key, label in (("chapter", "label"), ("headline", "headline"), ("narration", "narration")):
            va, vb = a.get(key), b.get(key)
            if key == "headline": va, vb = " / ".join(va or []), " / ".join(vb or [])
            if (va or "").strip() != (vb or "").strip():
                out.append(f"chapter {i + 1} {label}: {_q(va or '')} became {_q(vb or '')}")
    if so == 2 and sn == 2:
        ca = {o["id"]: o for o in old.get("cast") or [] if o.get("id")}
        cb = {o["id"]: o for o in new.get("cast") or [] if o.get("id")}
        for k in ca.keys() - cb.keys(): out.append(f"cast: removed {k} ({ca[k]['kind']})")
        for k in cb.keys() - ca.keys(): out.append(f"cast: added {k} ({cb[k]['kind']} {cb[k].get('span')} at {cb[k].get('slot')})")
        for k in ca.keys() & cb.keys():
            d = [f"{f} {ca[k].get(f)} to {cb[k].get(f)}" for f in ("kind", "slot", "span", "state") if ca[k].get(f) != cb[k].get(f)]
            if d: out.append(f"cast: {k} moved or changed ({', '.join(d)})")
        ea, eb = end_states(old), end_states(new)
        for k in sorted(ea.keys() & eb.keys()):
            if ea[k] != eb[k]: out.append(f"ending: {k} ends {eb[k]} (was {ea[k]})")
    elif sn == 2:
        out.append("cast: " + ", ".join(f"{o['id']} ({o['kind']})" for o in new.get("cast") or []))
    for do, key, what in (("connect", "label", "connection label"), ("break", "label", "break label"), ("fix", "label", "fix label"),
                          ("callout", "text", "callout"), ("checklist", "text", "checklist"), ("message", "text", "phone message")):
        a, b = _texts(old, do, key), _texts(new, do, key)
        for t in [x for x in a if x not in b]: out.append(f"{what} dropped: {_q(t)}")
        for t in [x for x in b if x not in a]: out.append(f"{what} added: {_q(t)}")
    if old_seconds and new_seconds and abs(old_seconds - new_seconds) >= 0.3:
        out.append(f"length: about {round(old_seconds, 1)} s became about {round(new_seconds, 1)} s")
    return out or ["no visible changes"]


def compatibility(plan, brief, report=None):
    """Is a saved plan still usable under the current schema and validator? Never modifies the plan.
    status: compatible (rebuild may reuse it), needs-migration (re-plan the same brief), or not-previewed (the run had
    stopped before a preview: questions, a missing illustration or an invalid plan; nothing to migrate)."""
    report = report or {}
    rec = report.get("versions")
    out = {"current": versions(), "recorded": rec or {"recorded": False, "schema": plan_schema(plan),
           "note": "made before versions were recorded (2026-10-12); hashes: " + json.dumps(report.get("style") or {}, sort_keys=True)}}
    if report.get("status") and report["status"] not in ("awaiting-approval", "approved", "planned"):
        out.update(status="not-previewed", problems=[f"the run stopped: {report['status']}"])
        return out
    sch = plan_schema(plan)
    if sch != PLAN_SCHEMA:
        out.update(status="needs-migration", problems=[f"plan schema {sch} ({'stage diagram' if sch == 1 else 'unrecognised'}) cannot be compiled by "
                                                       f"the current planner (schema {PLAN_SCHEMA})"])
        return out
    probs = validate_plan(plan, brief)
    if probs:
        out.update(status="needs-migration", problems=probs)
        return out
    out.update(status="compatible", problems=[])
    if rec and (rec.get("renderer"), rec.get("planner")) != (out["current"]["renderer"], PLANNER_VERSION):
        out["note"] = "a rebuild will draw this plan with the current renderer and compiler; the saved preview used older ones"
    return out
