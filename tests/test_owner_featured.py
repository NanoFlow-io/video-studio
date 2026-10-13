"""Owner Featured drafts: structure and reuse are inherited from the locked format and the business profile; free."""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from studio import owner_featured as of  # noqa: E402

PROMPT = '''Make an Owner Featured: Field Notes v1 reel for truenorth.
Title: Thermostat Wars
1. Customer reaction (about 4 s): a dad turns the thermostat down while his teenager turns it back up. Owner voiceover, exactly: "Fighting over the thermostat again?"
2. Owner intro, exactly: "There's an easier way to keep everyone comfortable."
3. Field Notes explainer: reuse project tn-oc-precool-peak-v4-voiced
4. Close: standard
'''
FRESH = '''Make an Owner Featured reel for truenorth: Filter Day.
1. Customer reaction: a homeowner pulls out a grey, clogged AC filter and winces. Owner voiceover: "When did you last check your filter?"
2. Owner intro: "A clogged filter makes your system work harder."
3. Explainer: problem, a clogged return filter; cause, it restricts airflow; fix, check it monthly in summer and replace it when it looks grey; outcome, the system can run more easily.
'''


class Draft(unittest.TestCase):
    def test_draft_inherits_parts_reuse_and_music(self):
        with tempfile.TemporaryDirectory() as d:
            p = of.draft("truenorth", "tn-thermostat-wars", PROMPT, work=d)
            self.assertEqual([x["role"] for x in p["parts"]], ["customer_reaction_hook", "owner_intro", "field_notes_explanation", "branded_owner_close"])
            self.assertEqual(p["parts"][1]["look"], "Truck 1")
            self.assertEqual(p["parts"][3]["number"], "949 669 7337")
            self.assertEqual(p["music"]["bed_gain_db"], -14)
            self.assertTrue(p["parts"][3]["reuse"]["sha256_ok"] and p["music"]["sha256_ok"])
            self.assertEqual(p["parts"][2]["reuse"]["project"], "tn-oc-precool-peak-v4-voiced")
            self.assertEqual(p["quote"]["prepaid_usage"]["higgsfield_credits"], 10.75)
            self.assertEqual(p["quote"]["variant"], "reused middle (optional variant)")
            self.assertEqual(p["problems"], [])
            self.assertTrue(Path(d, "tn-thermostat-wars", "draft.json").exists())
            self.assertTrue(any("time-stretch" in r for r in p["rules"]))

    def test_a_new_field_notes_middle_is_the_default(self):
        with tempfile.TemporaryDirectory() as d:
            p = of.draft("truenorth", "tn-filter-day", FRESH, work=d)
            self.assertEqual(p["problems"], [])
            self.assertEqual(p["title"], "Filter Day")
            self.assertIsNone(p["parts"][2]["reuse"]); self.assertIn("clogged return filter", p["parts"][2]["brief"])
            steps = [g["step"] for g in p["generate"]]
            self.assertIn("Field Notes story and storyboard (new topic)", steps)
            self.assertIn("Field Notes owner narration", steps)
            q = p["quote"]; self.assertEqual(q["variant"], "new Field Notes middle (default)")
            self.assertEqual(q["provider_charges_usd"], 0.0)
            self.assertGreater(q["prepaid_usage"]["elevenlabs_credits"][0], 100)        # owner lines + middle narration
            self.assertEqual(q["subscription_funded"]["planner_calls"], (1, 2))

    def test_missing_lines_and_unknown_business_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p = of.draft("truenorth", "tn-x", "Title: X\n1. Someone surprised.\n3. Field Notes explainer: reuse project nope-nope\n", work=d)
            self.assertIn("missing hook line", p["problems"]); self.assertIn("missing intro line", p["problems"])
            self.assertTrue(any("has no render" in x for x in p["problems"]))
            with self.assertRaises(SystemExit):
                of.draft("unknown-biz", "tn-x", PROMPT, work=d)

    def test_business_specifics_live_only_in_the_profile(self):
        fmt = (of.FORMAT_DIR / "format.json").read_text()
        for specific in ("949", "BiXJTK87", "7073cbb5", "Dmitriy", "True North Heating"):
            self.assertNotIn(specific, fmt)


if __name__ == "__main__":
    unittest.main()
