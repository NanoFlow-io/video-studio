"""Field-notes planner: plan validation (facts, claims, text fit, cue words, event order) and the deterministic compiler.
Fixture plans here are hand-written test inputs (no model call); they do not prove the prompt workflow."""
import copy, json, shutil, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from studio import beats, fieldnotes_plan as fp  # noqa: E402

BRIEF_HOME = "True North, an HVAC company. Audience: homeowners on time-of-use plans. Problem: AC runs at peak price. " \
             "Cause: peak window costs more. Solution: cool before peak, raise the thermostat a little. Outcome: shift some cooling."
HOME = {
    "facts": {"business": "True North", "business_type": "HVAC", "audience": "homeowners", "problem": "AC at peak",
              "cause": "peak costs more", "solution": "pre-cool", "outcome": "shift cooling"},
    "questions": [], "gap": None, "stage": "home_energy",
    "stage_params": {"window_label": "PEAK PRICE", "left": "EARLIER IN THE DAY", "right": "LATER", "gauge_label": "COOLING DURING PEAK HOURS", "thermostat": True},
    "chapters": [
        {"chapter": "THE PROBLEM", "kicker": "ON A TIME-OF-USE PLAN", "headline": ["When the AC runs", "at peak price"], "emphasis": "ochre",
         "emphasis_on": "peak", "narration": "On a time-of-use plan, your AC often runs at peak price.",
         "events": [{"on": "start", "do": "establish"}, {"on": "plan", "do": "window"}, {"on": "runs", "do": "activity", "in": "window"},
                    {"on": "runs", "do": "ac", "speed": "high"}, {"on": "peak", "do": "gauge", "level": "high"}]},
        {"chapter": "THE SHIFT", "kicker": "BEFORE THE PEAK", "headline": ["Cool the house", "earlier"], "emphasis": "blue",
         "narration": "Cool your home before peak rates.", "events": [{"on": "Cool", "do": "cool", "level": "full"}, {"on": "before", "do": "shift_earlier"},
                                                                      {"on": "rates", "do": "callout", "target": "before", "text": "Pre-cool here"}]},
        {"chapter": "THE FIX", "kicker": "DURING THE PEAK", "headline": ["Raise it", "a little"], "emphasis": "sage",
         "narration": "Then raise the thermostat a little and check your plan.",
         "events": [{"on": "raise", "do": "raise_setting", "label": "A LITTLE HIGHER"}, {"on": "little", "do": "reduce_in_window", "level": "low"},
                    {"on": "little", "do": "gauge", "level": "low"}, {"on": "check", "do": "checklist", "text": "Check your rate plan."}]}],
}
BRIEF_FLOW = "FICTIONAL TEST: Harbor Lane Dental. Audience: patients. Problem: missed appointments. Cause: the reminder email " \
             "arrives the day before. Solution: a text reminder with a reply to reschedule. Outcome: open slots get rebooked."
FLOW = {
    "facts": {"business": "Harbor Lane Dental (fictional)", "business_type": "dental", "audience": "patients", "problem": "missed",
              "cause": "late email", "solution": "text reminder", "outcome": "rebooked"},
    "questions": [], "gap": None, "stage": "process_flow",
    "stage_params": {"steps": [{"id": "s1", "label": "Appointment booked"}, {"id": "s2", "label": "Reminder sent"},
                               {"id": "s3", "label": "Patient sees it"}, {"id": "s4", "label": "Chair filled"}]},
    "chapters": [
        {"chapter": "THE PROBLEM", "kicker": "MISSED APPOINTMENTS", "headline": ["Empty chairs", "on the day"], "emphasis": "ochre",
         "narration": "Patients miss visits when the reminder comes too late.",
         "events": [{"on": "start", "do": "establish"}, {"on": "reminder", "do": "break", "link": ["s2", "s3"], "label": "Email, day before"},
                    {"on": "late", "do": "highlight", "step": "s4", "tone": "problem"}]},
        {"chapter": "THE FIX", "kicker": "A TEXT THEY CAN ANSWER", "headline": ["Text, and let", "them reply"], "emphasis": "sage",
         "narration": "A text reminder lets them reply to reschedule, so the slot gets rebooked.",
         "events": [{"on": "text", "do": "fix", "link": ["s2", "s3"], "label": "Text with reply"}, {"on": "reply", "do": "pulse", "from": "s1", "to": "s4"},
                    {"on": "rebooked", "do": "highlight", "step": "s4", "tone": "fix"}, {"on": "rebooked", "do": "checklist", "text": "Reply to reschedule."}]}],
}


class ValidatePlan(unittest.TestCase):
    def test_fixtures_are_valid(self):
        self.assertEqual(fp.validate_plan(HOME, BRIEF_HOME), [])
        self.assertEqual(fp.validate_plan(FLOW, BRIEF_FLOW), [])

    def test_problems_are_named(self):
        bad = copy.deepcopy(FLOW)
        bad["chapters"][0]["headline"][0] = "A headline that is far too long"
        bad["chapters"][0]["narration"] = "We guarantee 40% fewer missed visits when the reminder comes too late."
        bad["chapters"][0]["events"][1]["link"] = ["s1", "s3"]
        bad["chapters"][1]["events"][0]["on"] = "telegram"
        bad["chapters"][1]["events"].append({"on": "start", "do": "explode"})
        p = "\n".join(fp.validate_plan(bad, BRIEF_FLOW))
        for want in ("limit is 20", "'40%'", "'guarantee'", "two adjacent steps", "'telegram' is not a word", "not an event of the process_flow stage"):
            self.assertIn(want, p)

    def test_questions_and_gaps_stop_the_run(self):
        self.assertEqual(fp.validate_plan({**FLOW, "questions": ["What is the verified cause?"]}, BRIEF_FLOW), ["missing fact: What is the verified cause?"])
        self.assertTrue(fp.validate_plan({**FLOW, "gap": "a map of delivery zones"}, BRIEF_FLOW)[0].startswith("unsupported diagram"))

    def test_supplied_narration_must_be_word_for_word(self):
        p = {**copy.deepcopy(FLOW), "supplied_narration": "Something else entirely."}
        p["facts"]["narration_supplied"] = True
        self.assertIn("word for word", "\n".join(fp.validate_plan(p, BRIEF_FLOW)))

    def test_order_rules(self):
        bad = copy.deepcopy(HOME); bad["chapters"][0]["events"] = [{"on": "start", "do": "window"}] + bad["chapters"][0]["events"]
        self.assertIn("established first", "\n".join(fp.validate_plan(bad, BRIEF_HOME)))


class Compile(unittest.TestCase):
    def setUp(self):
        self.names = []

    def tearDown(self):
        for n in self.names:
            shutil.rmtree(fp.ROOT / "projects" / n, ignore_errors=True)

    def compiled(self, plan, name):
        pj = fp.compile_plan(plan, name, name)
        d = fp.ROOT / "projects" / name; d.mkdir(parents=True, exist_ok=True); self.names.append(name)
        (d / "project.json").write_text(json.dumps(pj))
        return pj, beats.validate(SimpleNamespace(dir=d, data=pj))

    def test_both_stages_compile_to_valid_scenes(self):
        for plan, name in ((HOME, "zz-test-fn-home"), (FLOW, "zz-test-fn-flow")):
            pj, probs = self.compiled(plan, name)
            self.assertEqual(probs, [], name)
            self.assertEqual(len(pj["scenes"]), len(plan["chapters"]))
            self.assertTrue(all(s["type"] == "fieldnotes" for s in pj["scenes"]))
        pj, _ = self.compiled(FLOW, "zz-test-fn-flow2")
        kinds = {o.get("kind") for s in pj["scenes"] for o in s["data"]["objects"]}
        self.assertIn("flow", kinds); self.assertNotIn("house", kinds)   # a different diagram, not the house

    def test_deterministic_and_cues_from_words(self):
        a, b = fp.compile_plan(HOME, "x", "x"), fp.compile_plan(copy.deepcopy(HOME), "x", "x")
        self.assertEqual(a, b)
        f1 = a["scenes"][0]
        self.assertEqual({c["at"] for c in f1["cues"]}, {"plan", "runs", "peak"})
        self.assertNotIn("_note_", json.dumps(a))

    def test_no_model_call_without_a_run(self):
        with mock.patch.object(fp, "ask_model", side_effect=AssertionError("model called")):
            fp.compile_plan(FLOW, "y", "y"); fp.validate_plan(FLOW, BRIEF_FLOW)


if __name__ == "__main__":
    unittest.main()
