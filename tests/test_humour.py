"""Humour treatment: the clean end card's cue requirement, headline validation and the engine splice. Run from the
repo root:  .venv/bin/python -m unittest discover -s tests -v"""
import json, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from studio import beats, cuts  # noqa: E402

LINE = "Running a business is no joke. NanoFlow gets you."


def end_card(data, cues):
    return {"id": "R04", "type": "end_card", "pose": "wave", "bg": "end", "line": {"text": LINE}, "data": data, "cues": cues}


def hook(**data):
    return {"id": "R01", "type": "hook", "pose": "tired", "line": {"text": "Be your own boss, they said."}, "cues": [], "data": {"words": [], **data}}


class CleanEndCard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.build = Path(self.tmp.name)
        words = [{"scene": "R04", "w": w, "s": round(0.5 + i * 0.3, 3), "e": round(0.7 + i * 0.3, 3)} for i, w in enumerate(LINE.split())]
        (self.build / "words-vertical.json").write_text(json.dumps({"duration": 4.0, "lines": [{"scene": "R04", "start": 0.5, "end": 3.4, "text": LINE}], "words": words}))

    def tearDown(self):
        self.tmp.cleanup()

    def run_build(self, scene):
        data = {"name": "t", "voice": {"tail": 1.0}, "scenes": [scene]}
        p = SimpleNamespace(dir=self.build, build=self.build, data=data, scenes=lambda cut=None: data["scenes"])
        return beats.build(p, "vertical")

    def test_required(self):
        self.assertEqual(beats.required(end_card({"clean": True}, [])), ["logo"])
        self.assertEqual(beats.required(end_card({"clean": False}, [])), ["logo", "button", "url", "chord"])
        self.assertEqual(beats.required(end_card({}, [])), ["logo", "button", "url", "chord"])

    def test_clean_needs_only_logo(self):
        out = self.run_build(end_card({"clean": True, "tagline": "a | b"}, [{"name": "logo", "at": "NanoFlow", "sfx": None}]))
        self.assertEqual([c["id"] for c in out["cues"]], ["R04.logo"])
        extra = self.run_build(end_card({"clean": True, "tagline": "a | b"}, [{"name": "logo", "at": "NanoFlow", "sfx": None},
                                                                             {"name": "button", "at": "end", "sfx": None}]))
        self.assertEqual(len(extra["cues"]), 2)   # unused cues are fine

    def test_clean_without_logo_stops(self):
        with self.assertRaises(SystemExit) as e:
            self.run_build(end_card({"clean": True, "tagline": "a | b"}, []))
        self.assertIn("needs a cue named 'logo'", str(e.exception)); self.assertNotIn("'button'", str(e.exception))

    def test_normal_end_card_still_needs_all(self):
        with self.assertRaises(SystemExit) as e:
            self.run_build(end_card({"tagline": "a | b"}, [{"name": "logo", "at": "NanoFlow", "sfx": None}]))
        for n in ("button", "url", "chord"):
            self.assertIn(f"needs a cue named '{n}'", str(e.exception))

    def test_clean_must_be_bool_on_end_card(self):
        p = SimpleNamespace(dir=self.build, data={"scenes": [end_card({"clean": "yes"}, [])]})
        self.assertEqual(len([x for x in beats.validate(p) if "data.clean" in x]), 1)
        p = SimpleNamespace(dir=self.build, data={"layout": "footage", "scenes": [hook(pill="Hi", clean=True)]})
        self.assertEqual(len([x for x in beats.validate(p) if "data.clean" in x]), 1)


class Headline(unittest.TestCase):
    def problems(self, layout="footage", **data):
        return beats.validate(SimpleNamespace(dir=Path("."), data={"layout": layout, "scenes": [hook(**data)]}))

    def test_good(self):
        self.assertEqual(self.problems(headline={"text": "Know this feeling?"}), [])   # replaces the pill
        self.assertEqual(self.problems(headline={"text": "Know this feeling?", "pos": [0.74, 0.265], "width": 0.4, "size": 120, "accent": "pink"}), [])
        self.assertEqual(self.problems(headline={"text": "x", "pos": [0, 1]}), [])

    def test_bad(self):
        for bad in ({"text": ""}, {"text": "   "}, {}, "Know this", {"text": "one two three four five six seven"},
                    {"text": "x", "pos": [0.5, 1.2]}, {"text": "x", "pos": [-0.1, 0.5]}, {"text": "x", "pos": [0.5]}, {"text": "x", "pos": "top"},
                    {"text": "x", "width": 0}, {"text": "x", "width": 1.5}, {"text": "x", "size": 10}, {"text": "x", "size": True},
                    {"text": "x", "accent": "green"}):
            self.assertEqual(len(self.problems(headline=bad)), 1, bad)

    def test_footage_only_and_hook_only(self):
        self.assertEqual(len(self.problems(layout=None, headline={"text": "x"})), 1)
        p = SimpleNamespace(dir=Path("."), data={"layout": "footage", "scenes": [end_card({"headline": {"text": "x"}, "tagline": "a"}, [])]})
        self.assertEqual(len([x for x in beats.validate(p) if "headline" in x]), 1)

    def test_pill_still_required_without_headline(self):
        self.assertTrue(any("data.pill is required" in x for x in self.problems()))

    def test_hook_caption_alongside_headline(self):
        self.assertEqual(self.problems(headline={"text": "Know this feeling?"}, caption="Be your own boss, they said."), [])
        self.assertEqual(self.problems(pill="Hi", caption=""), [])
        self.assertEqual(len([x for x in self.problems(pill="Hi", caption="Be your own boss.") if "not both" in x]), 1)
        self.assertEqual(len([x for x in self.problems(layout=None, pill="Hi", caption="Be your own boss.") if "footage layout" in x]), 1)
        sc = {**hook(headline={"text": "x"}, caption="Be your own boss."), "captions": True}
        self.assertEqual(len([x for x in beats.validate(SimpleNamespace(dir=Path("."), data={"layout": "footage", "scenes": [sc]})) if "dark chips" in x]), 1)

    def test_engine_draws_the_footage_hook_caption(self):
        js = (cuts.ROOT / "engine" / "scenes.js").read_text(encoding="utf-8")
        hook_js = js[js.index("TYPES.hook = function"):]; footage = hook_js[:hook_js.index("return; }")]
        self.assertIn("if(d.caption) footCaption(sc, s, d.caption);", footage)

    def test_template_hook_has_its_subtitle(self):
        t = json.loads((cuts.ROOT / "projects" / "nanoflow-humour" / "project.json").read_text(encoding="utf-8"))
        r01 = t["scenes"][0]
        self.assertEqual((r01["type"], r01["data"]["caption"]), ("hook", r01["line"]["text"]))


class EngineSplice(unittest.TestCase):
    def test_plain_projects_get_scenes_js_unchanged(self):
        js = (cuts.ROOT / "engine" / "scenes.js").read_text(encoding="utf-8")
        self.assertEqual(cuts.engine_js({"scenes": [hook(pill="Hi"), end_card({"tagline": "a"}, [])]}), js)
        self.assertEqual(cuts.engine_js({"scenes": [end_card({"clean": False}, [])]}), js)

    def test_humour_projects_get_humour_js_before_build(self):
        hj = (cuts.ROOT / "engine" / "humour.js").read_text(encoding="utf-8")
        for data in ({"scenes": [hook(headline={"text": "x"})]}, {"scenes": [end_card({"clean": True}, [])]}):
            js = cuts.engine_js(data)
            self.assertEqual(js.count(hj), 1); self.assertLess(js.index(hj), js.index(cuts.HUMOUR_AT))
            self.assertLess(js.index("TYPES.end_card = function"), js.index(hj))   # wraps the types defined above it


if __name__ == "__main__":
    unittest.main()
