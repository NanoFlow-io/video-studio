"""Field-notes explainer (experimental): engine splice gating and scene-data validation. Run from the repo root:
    .venv/bin/python -m unittest discover -s tests -v"""
import copy, json, sys, unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from studio import beats, cuts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "projects" / "fieldnotes-tn-cool-before-peak" / "project.json"


def example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def problems(data):
    return beats.validate(SimpleNamespace(dir=EXAMPLE.parent, data=data))


class Splice(unittest.TestCase):
    def test_plain_and_humour_pages_unchanged(self):
        js = (ROOT / "engine" / "scenes.js").read_text(encoding="utf-8")
        hj = (ROOT / "engine" / "humour.js").read_text(encoding="utf-8")
        plain = {"scenes": [{"id": "R01", "type": "hook", "data": {"pill": "Hi"}}]}
        self.assertEqual(cuts.engine_js(plain), js)
        humour = {"scenes": [{"id": "R01", "type": "hook", "data": {"headline": {"text": "x"}}}]}
        self.assertEqual(cuts.engine_js(humour), js.replace(cuts.HUMOUR_AT, hj + cuts.HUMOUR_AT))
        self.assertNotIn("FIELD NOTES EXPLAINER", cuts.engine_js(humour))

    def test_fieldnotes_projects_get_fieldnotes_js_before_build(self):
        fj = (ROOT / "engine" / "fieldnotes.js").read_text(encoding="utf-8")
        js = cuts.engine_js(example())
        self.assertEqual(js.count(fj), 1)
        self.assertLess(js.index("TYPES.hook = function"), js.index(fj))
        self.assertLess(js.index(fj), js.index(cuts.HUMOUR_AT))


class Validation(unittest.TestCase):
    def test_example_is_valid(self):
        self.assertEqual(problems(example()), [])
        self.assertIn("fieldnotes", beats.REQUIRED)

    def test_bad_data_is_named(self):
        d = example(); f1, f2 = d["scenes"][0]["data"], d["scenes"][1]["data"]
        f1["headline"]["lines"][1]["em"] = "neon"
        f1["objects"].append({"id": "x", "kind": "blimp"})
        f1["actions"].append({"at": "nope", "do": "draw", "target": "house"})
        f1["actions"].append({"at": 1, "do": "spin", "target": "house"})
        f1["actions"].append({"at": 1, "do": "show", "target": "timeline.ghost"})
        f2["actions"].append({"at": 1, "do": "show", "target": "acpeak"})      # a callout does not carry over
        p = "\n".join(problems(d))
        for want in ("emphasis must be one of", "kind must be one of", "'nope' is not one of this scene's cues",
                     "a house takes", "no band or segment 'ghost'", "no object 'acpeak'"):
            self.assertIn(want, p)

    def test_objects_carry_to_the_next_scene_unless_continue_is_false(self):
        d = example()
        self.assertEqual(problems(d), [])          # F02/F03 act on the house drawn in F01
        d2 = copy.deepcopy(d); d2["scenes"][1]["data"]["continue"] = False
        self.assertTrue(any("no object 'house'" in x for x in problems(d2)))

    def test_scenes_without_a_pose_are_allowed(self):
        self.assertTrue(all("pose" not in s for s in example()["scenes"]))


if __name__ == "__main__":
    unittest.main()
