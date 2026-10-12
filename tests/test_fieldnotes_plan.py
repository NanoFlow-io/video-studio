"""Field-notes composition planner: validation (facts, primitives, layout, events, claims, fit, cue words) and the
deterministic compiler. Fixture plans here are hand-written test inputs (no model call); they do not prove the prompt
workflow (that is `studio.py fieldnotes`)."""
import copy, json, shutil, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from studio import beats, fieldnotes_compose as fc, fieldnotes_plan as fp  # noqa: E402

BRIEF_DENTAL = ("FICTIONAL TEST: Harbor Lane Dental, a family dental practice. Audience: parents. Problem: missed check-ups leave "
                "an empty chair. Cause: the only reminder is an evening email that is easy to miss. Solution: a text two days ahead "
                "they can reply to. Outcome: the slot can be offered to another patient.")
DENTAL = {
    "facts": {"business": "Harbor Lane Dental (fictional)", "business_type": "dental", "audience": "parents", "problem": "empty chair",
              "cause": "evening email missed", "solution": "text two days ahead", "outcome": "slot offered to another patient"},
    "questions": [], "missing_primitives": [{"name": "tooth", "why": "decoration only", "essential": False}],
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
         "narration": "Now a text comes two days ahead, they reply to reschedule, and the slot goes to another patient.",
         "events": [{"on": "text", "do": "message", "obj": "phone", "type": "text", "text": "Can you make it?"},
                    {"on": "text", "do": "remind", "obj": "cal", "days_before": 2, "medium": "text"},
                    {"on": "reply", "do": "draw", "obj": "parent"},
                    {"on": "reply", "do": "message", "obj": "phone", "type": "reply", "text": "Please reschedule"},
                    {"on": "slot", "do": "state", "obj": "cal", "state": "rebooked"},
                    {"on": "patient", "do": "state", "obj": "chair", "state": "occupied"},
                    {"on": "patient", "do": "checklist", "text": "Reply to reschedule"}]}],
}
BRIEF_HOME = ("True North, an HVAC company. Audience: homeowners on time-of-use plans. Problem: AC runs at peak price. Cause: the peak "
              "window costs more. Solution: cool before peak, raise the thermostat a little. Outcome: shift some cooling.")
HOME = {
    "facts": {"business": "True North", "business_type": "HVAC", "audience": "homeowners", "problem": "AC at peak", "cause": "peak costs more",
              "solution": "pre-cool", "outcome": "shift cooling"},
    "questions": [], "missing_primitives": [],
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


if __name__ == "__main__":
    unittest.main()
