"""Field-notes composition planner: validation (facts, primitives, layout, events, claims, fit, cue words) and the
deterministic compiler. Fixture plans here are hand-written test inputs (no model call); they do not prove the prompt
workflow (that is `studio.py fieldnotes`)."""
import copy, json, shutil, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from studio import beats, fieldnotes_compose as fc, fieldnotes_plan as fp  # noqa: E402

BRIEF_DENTAL = ("FICTIONAL TEST: Harbor Lane Dental, a family dental practice. Audience: parents. Problem: a check-up visit is "
                "booked, then missed, and the chair sits empty. Cause: the only reminder is one evening email that is easy to miss. "
                "Solution: a text comes two days ahead that they can answer, so they reply to reschedule or move it. "
                "Outcome: the slot can be offered to another patient.")
DENTAL = {
    "facts": {"business": "Harbor Lane Dental (fictional)", "business_type": "dental", "audience": "parents", "problem": "empty chair",
              "cause": "evening email missed", "solution": "text two days ahead", "outcome": "slot offered to another patient"},
    "questions": [], "missing_primitives": [{"name": "tooth", "why": "decoration only", "essential": False}],
    "claims": [{"text": "A booked visit an empty chair", "support": "a check-up visit is booked, then missed, and the chair sits empty"},
               {"text": "A check-up is booked, then missed, and the chair sits empty.", "support": "a check-up visit is booked, then missed, and the chair sits empty"},
               {"text": "Missed visit", "support": "a check-up visit is booked, then missed"},
               {"text": "An evening email easy to miss", "support": "one evening email that is easy to miss"},
               {"text": "Our only reminder was an evening email, easy to miss.", "support": "the only reminder is one evening email that is easy to miss"},
               {"text": "Text ahead, reply to move it", "support": "a text comes two days ahead that they can answer, so they reply to reschedule or move it"},
               {"text": "Now a text comes two days ahead, they reply to reschedule, and we can offer the slot.", "support": "a text comes two days ahead that they can answer, so they reply to reschedule or move it"},
               {"text": "Reply to reschedule", "support": "they reply to reschedule"}],
    "cast": [{"id": "cal", "kind": "calendar", "slot": "r1c1", "span": "1x1", "state": "booked"},
             {"id": "chair", "kind": "chair", "slot": "r2c1", "span": "2x1", "state": "occupied"},
             {"id": "phone", "kind": "phone", "slot": "r1c3", "span": "1x2"},
             {"id": "parent", "kind": "person", "slot": "r3c3", "span": "1x1"},
             {"id": "patient", "kind": "person", "slot": "r3c1", "span": "1x1", "state": "away"}],
    "chapters": [
        {"chapter": "THE PROBLEM", "kicker": "MISSED CHECK-UPS", "headline": ["A booked visit", "an empty chair"], "emphasis": "ochre",
         "narration": "A check-up is booked, then missed, and the chair sits empty.",
         "events": [{"on": "start", "do": "draw", "obj": "cal"}, {"on": "booked", "do": "draw", "obj": "chair"},
                    {"on": "missed", "do": "state", "obj": "chair", "state": "empty"}, {"on": "missed", "do": "state", "obj": "cal", "state": "empty"},
                    {"on": "empty", "do": "callout", "obj": "cal", "text": "Missed visit"}]},
        {"chapter": "THE CAUSE", "kicker": "ONE EVENING EMAIL", "headline": ["An evening email", "easy to miss"], "emphasis": "blue",
         "narration": "Our only reminder was an evening email, easy to miss.",
         "events": [{"on": "start", "do": "draw", "obj": "phone"}, {"on": "reminder", "do": "message", "obj": "phone", "type": "email", "text": "Reminder: check-up"},
                    {"on": "easy", "do": "bury", "obj": "phone"}, {"on": "miss", "do": "remind", "obj": "cal", "days_before": 1, "medium": "email"}]},
        {"chapter": "THE FIX", "kicker": "A TEXT THEY CAN ANSWER", "headline": ["Text ahead,", "reply to move it"], "emphasis": "sage",
         "narration": "Now a text comes two days ahead, they reply to reschedule, and we can offer the slot.",
         "events": [{"on": "text", "do": "message", "obj": "phone", "type": "text", "text": "Can you make it?"},
                    {"on": "text", "do": "remind", "obj": "cal", "days_before": 2, "medium": "text"},
                    {"on": "reply", "do": "draw", "obj": "parent"},
                    {"on": "reply", "do": "message", "obj": "phone", "type": "reply", "text": "Please reschedule"},
                    {"on": "offer", "do": "state", "obj": "cal", "state": "available"},
                    {"on": "slot", "do": "checklist", "text": "Reply to reschedule"}]}],
}
BRIEF_HOME = ("True North, an HVAC company. Audience: homeowners on time-of-use plans. Problem: on a time-of-use plan, your AC often "
              "runs at peak price. Cause: the peak window costs more. Solution: cool your home before peak rates, then raise the "
              "thermostat a little higher. Outcome: shift some cooling during peak.")
HOME = {
    "facts": {"business": "True North", "business_type": "HVAC", "audience": "homeowners", "problem": "AC at peak", "cause": "peak costs more",
              "solution": "pre-cool", "outcome": "shift cooling"},
    "questions": [], "missing_primitives": [],
    "claims": [{"text": "When the AC runs at peak price", "support": "your AC often runs at peak price"},
               {"text": "On a time-of-use plan, your AC often runs at peak price.", "support": "on a time-of-use plan, your AC often runs at peak price"},
               {"text": "COOLING DURING PEAK", "support": "shift some cooling during peak"},
               {"text": "Cool early, raise it a little", "support": "cool your home before peak rates, then raise the thermostat a little higher"},
               {"text": "Cool your home before peak rates, then raise the thermostat a little.", "support": "cool your home before peak rates, then raise the thermostat a little higher"},
               {"text": "A little higher", "support": "raise the thermostat a little higher"}],
    "cast": [{"id": "thermo", "kind": "thermostat", "slot": "r1c1", "span": "1x1"},
             {"id": "home", "kind": "house", "slot": "r2c1", "span": "2x1"}, {"id": "ac", "kind": "ac_unit", "slot": "r2c3", "span": "1x1"},
             {"id": "day", "kind": "timeline", "slot": "r3c1", "span": "3x1", "params": {"window_label": "PEAK PRICE", "left": "EARLIER IN THE DAY", "right": "LATER"}}],
    "chapters": [
        {"chapter": "THE PROBLEM", "kicker": "ON A TIME-OF-USE PLAN", "headline": ["When the AC runs", "at peak price"], "emphasis": "ochre",
         "narration": "On a time-of-use plan, your AC often runs at peak price.",
         "events": [{"on": "start", "do": "draw", "obj": "home"}, {"on": "start", "do": "draw", "obj": "ac"}, {"on": "start", "do": "draw", "obj": "day"},
                    {"on": "plan", "do": "window", "obj": "day"}, {"on": "runs", "do": "activity", "obj": "day"},
                    {"on": "runs", "do": "speed", "obj": "ac", "speed": "high"}, {"on": "peak", "do": "gauge", "label": "COOLING DURING PEAK", "level": "high"}]},
        {"chapter": "THE FIX", "kicker": "BEFORE AND DURING PEAK", "headline": ["Cool early,", "raise it a little"], "emphasis": "sage",
         "narration": "Cool your home before peak rates, then raise the thermostat a little.",
         "events": [{"on": "Cool", "do": "cool", "obj": "home", "level": "full"}, {"on": "before", "do": "shift_earlier", "obj": "day"},
                    {"on": "raise", "do": "draw", "obj": "thermo"}, {"on": "raise", "do": "turn", "obj": "thermo", "direction": "up"},
                    {"on": "thermostat", "do": "callout", "obj": "thermo", "text": "A little higher"},
                    {"on": "little", "do": "reduce", "obj": "day", "level": "low"}, {"on": "little", "do": "gauge", "label": "COOLING DURING PEAK", "level": "low"}]}],
}


class ValidatePlan(unittest.TestCase):
    def test_fixtures_are_valid(self):
        self.assertEqual(fc.validate_plan(DENTAL, BRIEF_DENTAL), [])
        self.assertEqual(fc.validate_plan(HOME, BRIEF_HOME), [])

    def test_layout_and_primitives(self):
        bad = copy.deepcopy(DENTAL)
        bad["cast"].append({"id": "tooth", "kind": "tooth", "slot": "r2c3", "span": "1x1"})
        bad["cast"].append({"id": "extra", "kind": "person", "slot": "r1c1", "span": "1x1"})
        bad["cast"].append({"id": "wide", "kind": "phone", "slot": "r3c2", "span": "1x2"})
        p = "\n".join(fc.validate_plan(bad, BRIEF_DENTAL))
        for want in ("not a supported primitive", "missing_primitives", "overlaps cal", "runs off the grid"):
            self.assertIn(want, p)

    def test_events_claims_fit_cues(self):
        bad = copy.deepcopy(DENTAL)
        ch = bad["chapters"]
        ch[0]["headline"][0] = "A headline that is far too long"
        ch[0]["narration"] = "We guarantee 40% fewer missed visits, booked then missed, and the chair sits empty."
        ch[1]["events"].insert(0, {"on": "start", "do": "message", "obj": "parent", "type": "text", "text": "hi"})
        ch[2]["events"].append({"on": "telegram", "do": "state", "obj": "cal", "state": "rebooked"})
        ch[2]["events"].append({"on": "start", "do": "state", "obj": "cal", "state": "sparkly"})
        ch[2]["events"].append({"on": "start", "do": "break", "link": "nope"})
        p = "\n".join(fc.validate_plan(bad, BRIEF_DENTAL))
        for want in ("limit is 20", "'40%'", "'guarantee'", "a person takes", "'telegram' is not a word", "state must be one of",
                     "must be a connection made earlier"):
            self.assertIn(want, p)

    def test_draw_before_change_and_connect(self):
        bad = copy.deepcopy(DENTAL)
        bad["chapters"][0]["events"].insert(0, {"on": "start", "do": "connect", "id": "c1", "from": "cal", "to": "phone"})
        p = "\n".join(fc.validate_plan(bad, BRIEF_DENTAL))
        self.assertIn("draw phone before connecting it", p)

    def test_questions_and_essential_missing_primitives_stop(self):
        self.assertEqual(fc.validate_plan({**DENTAL, "questions": ["What is the cause?"]}, BRIEF_DENTAL), ["missing fact: What is the cause?"])
        r = fc.validate_plan({**DENTAL, "missing_primitives": [{"name": "map", "why": "delivery zones", "essential": True}]}, BRIEF_DENTAL)
        self.assertEqual(r, ["missing illustration: map: delivery zones"])

    def test_callout_needs_room(self):
        bad = copy.deepcopy(DENTAL)   # chair r2c1-2: above is cal r1c1 and free r1c2 -> blocked above; right r2c3 is phone -> no room
        bad["cast"].append({"id": "x", "kind": "envelope", "slot": "r1c2", "span": "1x1"})
        bad["chapters"][0]["events"].append({"on": "empty", "do": "callout", "obj": "chair", "text": "Empty chair"})
        self.assertIn("no free room next to chair", "\n".join(fc.validate_plan(bad, BRIEF_DENTAL)))

    def test_catalogue_text_lists_every_primitive(self):
        t = fc.catalog_text()
        for k in fc.PRIMS:
            self.assertIn(f"`{k}`", t)


class OutcomeStrength(unittest.TestCase):
    """The illustrated outcome must not overstate the brief (2026-10-12 review: 'can offer the slot')."""
    def test_hedged_brief_refuses_done_states_and_certain_narration(self):
        bad = copy.deepcopy(DENTAL)
        fix = bad["chapters"][2]
        fix["events"] = [x for x in fix["events"] if x.get("obj") != "cal" or x.get("do") != "state"]
        fix["events"] += [{"on": "slot", "do": "state", "obj": "cal", "state": "rebooked"}, {"on": "slot", "do": "state", "obj": "chair", "state": "occupied"}]
        fix["narration"] = "Now a text comes two days ahead, they reply to reschedule, and we fill the slot."
        p = "\n".join(fc.validate_plan(bad, BRIEF_DENTAL))
        self.assertIn("shows cal as 'rebooked'", p)
        self.assertIn("shows chair as 'occupied'", p)
        self.assertIn("must keep that (can, could or may)", p)

    def test_available_and_hedged_narration_pass(self):
        self.assertEqual([x for x in fc.validate_plan(DENTAL, BRIEF_DENTAL) if x.startswith("outcome")], [])

    def test_unhedged_brief_may_show_the_result(self):
        brief = BRIEF_DENTAL.replace("the slot can be offered to another patient", "the slot goes to another patient")
        plan = copy.deepcopy(DENTAL); plan["facts"]["outcome"] = "slot goes to another patient"
        plan["chapters"][2]["events"].append({"on": "slot", "do": "state", "obj": "cal", "state": "rebooked"})
        self.assertEqual([x for x in fc.validate_plan(plan, brief) if x.startswith("outcome")], [])

    def test_owner_supplied_narration_needs_no_hedge_but_pictures_still_do(self):
        plan = copy.deepcopy(DENTAL)
        plan["chapters"][2]["narration"] = "Now a text comes two days ahead, they reply to reschedule, and we offer the slot."
        plan["supplied_narration"] = " ".join(c["narration"] for c in plan["chapters"])
        p = "\n".join(fc.validate_plan(plan, BRIEF_DENTAL))
        self.assertNotIn("must keep that (can, could or may)", p)
        plan["chapters"][2]["events"].append({"on": "slot", "do": "state", "obj": "cal", "state": "rebooked"})
        self.assertIn("shows cal as 'rebooked'", "\n".join(fc.validate_plan(plan, BRIEF_DENTAL)))

    def test_a_booked_start_is_not_an_outcome(self):   # the starting state in chapter 1 is the situation, not a claim
        self.assertEqual(fc.outcome_problems({"facts": {"outcome": "can be offered"}, "chapters": [
            {"narration": "It can be offered.", "events": [{"do": "state", "obj": "cal", "state": "rebooked"}]}]}, "Outcome: can", {"cal": "calendar"}), [])


class SameWordOrdering(unittest.TestCase):
    """Events that share a spoken word unfold briefly but never pass the next cue (2026-10-12: a link was drawn after
    it broke, which reset its label)."""
    def plan(self):
        p = copy.deepcopy(DENTAL)
        p["chapters"][1]["narration"] = "Our only reminder: an evening email, seen late."
        p["chapters"][1]["events"] = [{"on": "start", "do": "draw", "obj": "phone"}, {"on": "start", "do": "draw", "obj": "chair"},
            {"on": "email", "do": "message", "obj": "phone", "type": "email", "text": "Reminder: check-up"},
            {"on": "email", "do": "state", "obj": "patient", "state": "away"},
            {"on": "email", "do": "remind", "obj": "cal", "days_before": 1, "medium": "email"},
            {"on": "email", "do": "connect", "id": "c1", "from": "phone", "to": "chair", "style": "dashed", "label": "Evening email"},
            {"on": "late", "do": "break", "link": "c1", "label": "Seen too late"}]
        p["chapters"][0]["events"].insert(0, {"on": "start", "do": "draw", "obj": "patient"})
        return p

    def times(self, scene):
        nar, cues = scene["line"]["text"], {c["name"]: c["at"] for c in scene["cues"]}
        out = []
        for a in scene["data"]["actions"]:
            at = a["at"]
            if isinstance(at, (int, float)): out.append((at, a)); continue
            name, off = (at.split("+") + ["0"])[:2] if "+" in at else (at, "0")
            out.append((fc._est_word_time(nar, cues[name]) + float(off), a))
        return out

    def test_draw_comes_before_break_and_order_is_kept(self):
        pj = fc.compile_plan(self.plan(), "x", "x")
        ts = self.times(pj["scenes"][1])
        draw = next(t for t, a in ts if a["do"] == "draw" and a["target"] == "c1")
        brk = next(t for t, a in ts if a["do"] == "mark" and a["target"] == "c1")
        late = fc._est_word_time(pj["scenes"][1]["line"]["text"], "late")
        self.assertLess(draw, brk)
        self.assertLess(draw, late)

    def test_stagger_is_capped_below_the_next_word(self):
        pj = fc.compile_plan(self.plan(), "x", "x")
        late = fc._est_word_time(pj["scenes"][1]["line"]["text"], "late")
        on_email = [t for t, a in self.times(pj["scenes"][1]) if a["do"] in ("message", "state", "remind") or (a["do"] == "draw" and a["target"] == "c1")]
        self.assertTrue(all(t < late for t in on_email), on_email)


class LinkLabels(unittest.TestCase):
    """Link labels stay on the frame, off other links' markers and labels, and off the drawings (2026-10-12: a label
    covered another link, then sat on the phone's edge)."""
    def rects(self, pj):
        out = []
        for s in pj["scenes"]:
            for o in s["data"]["objects"]:
                if o.get("kind") == "link":
                    mx, my = (o["from"][0] + o["to"][0]) / 2, (o["from"][1] + o["to"][1]) / 2
                    out.append((o["id"], (mx, my), fc._label_rect(mx, my, o["labelSide"], len(o["label"] or "x"))))
        return out

    def layout(self, cast):
        p = copy.deepcopy(DENTAL)
        p["cast"] = cast
        ev = p["chapters"][0]["events"] = [{"on": "start", "do": "draw", "obj": o["id"]} for o in cast]
        ev += [{"on": "start", "do": "connect", "id": "c1", "from": "mail", "to": "parent", "style": "dashed", "label": "Seen too late"},
               {"on": "start", "do": "connect", "id": "c2", "from": "phone", "to": "parent", "style": "solid", "label": "Text two days ahead"}]
        for c in p["chapters"][1:]:
            c["events"] = [{"on": "start", "do": "note", "text": "x"}]
        return p

    def test_cramped_layout_is_refused_for_a_repair(self):
        # the v3 layout: phone directly above the parent, a 90 px gap, no clean spot for the text link's label
        p = self.layout([{"id": "chair", "kind": "chair", "slot": "r1c1", "span": "2x1"}, {"id": "phone", "kind": "phone", "slot": "r1c3", "span": "1x2"},
                         {"id": "mail", "kind": "envelope", "slot": "r2c1", "span": "2x1"}, {"id": "cal", "kind": "calendar", "slot": "r3c1", "span": "2x1"},
                         {"id": "parent", "kind": "person", "slot": "r3c3", "span": "1x1"}])
        self.assertIn("connection c2 (phone to parent): no clear room", "\n".join(fc.link_label_problems(p)))

    def test_roomy_layout_places_both_labels_cleanly(self):
        p = self.layout([{"id": "phone", "kind": "phone", "slot": "r1c3", "span": "1x2"}, {"id": "mail", "kind": "envelope", "slot": "r1c1", "span": "1x1"},
                         {"id": "parent", "kind": "person", "slot": "r3c1", "span": "1x1"}])
        self.assertEqual(fc.link_label_problems(p), [])
        r = self.rects(fc.compile_plan(p, "x", "x"))
        (_, m1, a), (_, m2, b) = r
        self.assertEqual(fc._overlap(a, b), 0)
        for rect, other in ((a, m2), (b, m1)):
            self.assertEqual(fc._overlap(rect, (other[0] - 24, other[1] - 24, other[0] + 24, other[1] + 24)), 0)
            self.assertTrue(rect[0] >= 40 and rect[2] <= 1040)
        for oid in ("phone", "mail", "parent"):
            o = next(x for x in p["cast"] if x["id"] == oid); bx = fc.box(o["slot"], o["span"])
            for rect in (a, b):
                self.assertEqual(fc._overlap(rect, (bx["x0"], bx["y0"], bx["x0"] + bx["w"], bx["y0"] + bx["h"])), 0, oid)

class Zoom(unittest.TestCase):
    def plan(self, **kw):
        p = copy.deepcopy(DENTAL)
        p["cast"].append({"id": "mail", "kind": "envelope", "slot": "r3c3", "span": "1x1"})
        p["cast"] = [o for o in p["cast"] if o["id"] != "parent"]
        p["chapters"][2]["events"] = [x for x in p["chapters"][2]["events"] if x.get("obj") != "parent"]
        p["chapters"][1]["events"] += [{"on": "miss", "do": "draw", "obj": "mail"}, {"on": "miss", "do": "zoom", "obj": "phone", "msg": "email", "to": "mail", **kw}]
        return p

    def test_zoom_compiles_with_the_target_rect(self):
        self.assertEqual(fc.validate_plan(self.plan(), BRIEF_DENTAL), [])
        pj = fc.compile_plan(self.plan(), "x", "x")
        z = next(a for s in pj["scenes"] for a in s["data"]["actions"] if a["do"] == "zoom")
        b = fc.box("r2c3", "1x1")
        self.assertTrue(b["x0"] <= z["rect"]["x0"] < z["rect"]["x1"] <= b["x0"] + b["w"])

    def test_zoom_needs_the_message_and_another_object(self):
        p = "\n".join(fc.validate_plan(self.plan(msg="reply"), BRIEF_DENTAL))
        self.assertIn("no reply message on phone yet", p)
        p = "\n".join(fc.validate_plan(self.plan(to="phone"), BRIEF_DENTAL))
        self.assertIn("zoom needs another cast object", p)


class Compile(unittest.TestCase):
    def setUp(self):
        self.names = []

    def tearDown(self):
        for n in self.names:
            shutil.rmtree(fp.ROOT / "projects" / n, ignore_errors=True)

    def compiled(self, plan, name):
        pj = fc.compile_plan(plan, name, name)
        d = fp.ROOT / "projects" / name; d.mkdir(parents=True, exist_ok=True); self.names.append(name)
        (d / "project.json").write_text(json.dumps(pj))
        return pj, beats.validate(SimpleNamespace(dir=d, data=pj))

    def test_both_compile_to_valid_scenes(self):
        for plan, name in ((DENTAL, "zz-test-fn-dental"), (HOME, "zz-test-fn-home")):
            pj, probs = self.compiled(plan, name)
            self.assertEqual(probs, [], name)
        pj, _ = self.compiled(DENTAL, "zz-test-fn-dental2")
        kinds = {o.get("kind") for s in pj["scenes"] for o in s["data"]["objects"]}
        self.assertTrue({"calendar", "chair", "phone", "person"} <= kinds)
        self.assertNotIn("flow", kinds)

    def test_deterministic_and_inside_the_grid(self):
        a, b = fc.compile_plan(DENTAL, "x", "x"), fc.compile_plan(copy.deepcopy(DENTAL), "x", "x")
        self.assertEqual(a, b)
        for o in a["scenes"][0]["data"]["objects"]:
            if "cx" in o:
                self.assertTrue(72 <= o["cx"] - o["bw"] / 2 and o["cx"] + o["bw"] / 2 <= 1008 and 600 <= o["cy"] - o["bh"] / 2 and o["cy"] + o["bh"] / 2 <= 1530, o["id"])

    def test_no_model_call(self):
        with mock.patch.object(fp, "ask_model", side_effect=AssertionError("model called")):
            fc.compile_plan(DENTAL, "y", "y"); fc.validate_plan(DENTAL, BRIEF_DENTAL)


class ClosingCard(unittest.TestCase):
    """2026-10-12: two checklist events replaced each other on the one closing card, so only the second was readable."""
    def test_one_closing_line_in_the_last_chapter(self):
        bad = copy.deepcopy(HOME)
        bad["chapters"][1]["events"] += [{"on": "raise", "do": "checklist", "text": "Cool your home before peak"},
                                         {"on": "little", "do": "checklist", "text": "Raise the thermostat a little"}]
        p = "\n".join(fc.validate_plan(bad, BRIEF_HOME))
        self.assertIn("the closing card holds one line, but the plan gives 2 checklist events", p)
        early = copy.deepcopy(HOME)
        early["chapters"][0]["events"].append({"on": "plan", "do": "checklist", "text": "Cool your home before peak"})
        self.assertIn("chapter 1: the closing checklist belongs in the last chapter", "\n".join(fc.validate_plan(early, BRIEF_HOME)))

    def test_one_note_per_chapter(self):
        bad = copy.deepcopy(HOME)
        bad["chapters"][0]["events"] += [{"on": "plan", "do": "note", "text": "Peak price"}, {"on": "runs", "do": "note", "text": "AC runs"}]
        self.assertIn("chapter 1: one note per chapter", "\n".join(fc.validate_plan(bad, BRIEF_HOME)))


class SuppliedNarration(unittest.TestCase):
    def test_supplied_narration_is_enforced_even_if_the_model_says_otherwise(self):
        plan = copy.deepcopy(HOME); plan["facts"]["narration_supplied"] = False
        plan["supplied_narration"] = "Different words entirely for this test."
        self.assertIn("must be the supplied narration, word for word", "\n".join(fc.validate_plan(plan, BRIEF_HOME)))

    def test_a_revised_brief_with_narration_is_detected(self):
        b = BRIEF_HOME + '\nNarration: "On a time-of-use plan, cooling can cost more."'
        self.assertEqual(fp.supplied_narration(b), "On a time-of-use plan, cooling can cost more.")


class CastParams(unittest.TestCase):
    def test_top_level_timeline_labels_reach_the_page(self):
        plan = copy.deepcopy(HOME)
        day = next(o for o in plan["cast"] if o["id"] == "day"); day.pop("params")
        day.update({"window_label": "PEAK WINDOW", "left": "Earlier (example day)", "right": "Later"})
        self.assertEqual(fc.validate_plan(plan, BRIEF_HOME), [])
        obj = next(o for o in fc.compile_plan(plan, "x", "x")["scenes"][0]["data"]["objects"] if o["id"] == "day")
        self.assertEqual((obj["left"], obj["bands"][0]["label"]), ("Earlier (example day)", "PEAK WINDOW"))


class SomeNotAll(unittest.TestCase):
    def test_shift_earlier_leaves_part_of_the_activity_in_the_window(self):
        pj = fc.compile_plan(HOME, "x", "x")
        acts = [a for sc in pj["scenes"] for a in sc["data"]["actions"] if a.get("target") == "day.atpeak" and a.get("do") == "seg"]
        self.assertTrue(acts and all(a["level"] > 0 for a in acts))   # some cooling stays at peak; never all of it moves


class FactualGrounding(unittest.TestCase):
    """2026-10-12 review: 'AC works hardest when rates peak' and 'Most cooling lands in peak' passed the number and
    guarantee-word checks but were not stated by the owner. Statements must be built from the brief's facts."""
    def plan_with(self, headline, narration, support):
        p = copy.deepcopy(HOME)
        p["chapters"][0]["headline"] = headline
        p["chapters"][0]["narration"] = narration
        p["chapters"][0]["events"] = [e for e in p["chapters"][0]["events"] if e.get("on") in ("start", "plan")]
        p["claims"] = [c for c in p["claims"] if c["text"] not in ("When the AC runs at peak price", "On a time-of-use plan, your AC often runs at peak price.")]
        p["claims"] += [{"text": " ".join(headline), "support": support}, {"text": narration, "support": support}]
        return p

    def test_invented_behaviour_and_comparisons_are_refused(self):
        p = "\n".join(fc.validate_plan(self.plan_with(["AC works hardest", "when rates peak"], "Most cooling lands in peak on a time-of-use plan.",
                                                       "your AC often runs at peak price"), BRIEF_HOME))
        self.assertIn("states an amount or comparison (hardest)", p)
        self.assertIn("states an amount or comparison (most)", p)
        self.assertIn("uses lands", p)
        self.assertIn("works", p)

    def test_a_quantifier_must_be_in_its_own_support(self):
        brief = BRIEF_HOME + " Note: most homes differ."
        plan = self.plan_with(["Most cooling", "at peak price"], "On a time-of-use plan, most cooling runs at peak price.", "your AC often runs at peak price")
        p = "\n".join(fc.validate_plan(plan, brief))
        self.assertIn("says most but its support 'your AC often runs at peak price' does not", p)

    def test_every_statement_needs_a_word_for_word_support(self):
        plan = copy.deepcopy(HOME)
        plan["claims"] = [c for c in plan["claims"] if c["text"] != "A little higher"]
        plan["claims"].append({"text": "A little higher", "support": "raise it slightly higher"})   # not in the brief
        p = "\n".join(fc.validate_plan(plan, BRIEF_HOME))
        self.assertIn("the support for 'A little higher' must be copied word for word", p)
        plan["claims"] = []
        self.assertIn("needs a \"claims\" entry", "\n".join(fc.validate_plan(plan, BRIEF_HOME)))

    def test_constraint_lines_are_not_support(self):
        brief = BRIEF_HOME + "\nConstraints: no guaranteed outcomes, no savings figures."
        plan = copy.deepcopy(HOME)
        plan["chapters"][1]["events"].append({"on": "raise", "do": "note", "text": "Guaranteed savings"})
        plan["claims"].append({"text": "Guaranteed savings", "support": "no guaranteed outcomes, no savings figures"})
        p = "\n".join(fc.validate_plan(plan, brief))
        self.assertIn("'Guaranteed' in 'Guaranteed savings' is not in the brief", p)
        self.assertIn("must be copied word for word from the brief's facts", p)

    def test_supplied_narration_is_its_own_support_and_messages_are_dialogue(self):
        self.assertEqual(fc.validate_plan(HOME, BRIEF_HOME), [])
        self.assertEqual(fc.validate_plan(DENTAL, BRIEF_DENTAL), [])   # 'Can you make it?' on the phone is dialogue


if __name__ == "__main__":
    unittest.main()
