import json, tempfile, unittest
from pathlib import Path
from unittest import mock

from studio import owner_card as oc, owner_featured as of, owner_profile as op, owner_steps as os_

TOPIC = '''Make an Owner Featured reel for True North Heating and Air: Fan Off.
1. Customer reaction: a homeowner comes home to an empty living room with the ceiling fan still spinning and sighs. Owner voiceover: "Nobody's home, but the fan's still running."
2. Owner intro: "Hi, I'm Dim from True North. Here's a quick one."
3. Explainer: problem, ceiling fans left on in empty rooms; cause, a fan cools people, not rooms; fix, switch it off when you leave; outcome, a little less electricity used.
'''


def fake_hf(*args, **kw):
    return '{"result": "https://example.invalid/out.png"} https://example.invalid/out.mp4'


def fake_download(url, dst):
    Path(dst).write_bytes(b"x")
    return Path(dst)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        of.draft("truenorth", "fan-off", TOPIC, work=self.tmp.name)
        self.p = os_.Project("fan-off", self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_business_found_by_name_and_shared_music(self):
        d = json.loads((Path(self.tmp.name) / "fan-off" / "draft.json").read_text())
        self.assertEqual(d["tenant"], "truenorth")
        self.assertEqual(d["music"]["source"], "template default")
        self.assertTrue(d["music"]["sha256_ok"])
        self.assertEqual(d["problems"], [])

    def test_paid_steps_wait_for_their_gates(self):
        for step in (lambda: os_.keyframe(self.p, "x"), lambda: os_.voice(self.p), lambda: os_.argil(self.p),
                     lambda: os_.assemble(self.p, "m")):
            with self.assertRaises(SystemExit) as e:
                step()
            self.assertIn("waits for the person's approval", str(e.exception))

    def test_gate_needs_words_and_something_to_approve(self):
        with self.assertRaises(SystemExit):
            os_.gate(self.p, "quote", "")
        with self.assertRaises(SystemExit):
            os_.gate(self.p, "keyframe", "looks good")       # no keyframe made yet
        self.assertTrue(os_.gate(self.p, "quote", "Approved, go ahead")["ok"])

    @mock.patch.object(os_, "download", side_effect=fake_download)
    @mock.patch.object(os_, "hf_run", side_effect=fake_hf)
    def test_no_automatic_retakes(self, hf, dl):
        os_.gate(self.p, "quote", "approved")
        r = os_.keyframe(self.p, "a homeowner, ceiling fan")
        self.assertTrue(r["ok"])
        self.assertEqual(self.p.state["spend"][-1]["higgsfield_credits"], 2)
        with self.assertRaises(SystemExit) as e:
            os_.keyframe(self.p, "again")
        self.assertIn("no automatic retakes", str(e.exception))
        with self.assertRaises(SystemExit):
            os_.keyframe(self.p, "again", retake=True)       # a retake needs the person's request
        os_.keyframe(self.p, "again", retake=True, words="Bob: try her looking up at the fan")
        self.assertEqual(self.p.state["spend"][-1]["retake_request"], "Bob: try her looking up at the fan")
        self.assertEqual(hf.call_count, 2)
        with self.assertRaises(SystemExit):
            os_.animate(self.p, "move")                      # the new still is not approved yet

    def test_new_middle_needs_studio_approvals_before_assembly(self):
        for g in ("quote", "keyframe", "voice"):
            self.p.state["gates"][g] = {"words": "ok"}
        with self.assertRaises(SystemExit) as e:
            os_.assemble(self.p, "m")
        self.assertIn("storyboard", str(e.exception))


class ProfileTests(unittest.TestCase):
    def test_find_by_alias_and_check(self):
        p, _ = op.find("true north heating & air")
        self.assertEqual(p["tenant"], "truenorth")
        self.assertEqual(op.find("TN")[0]["tenant"], "truenorth")
        self.assertIsNone(op.find("XYZ Plumbing")[0])
        self.assertTrue(op.check("truenorth")["ready"])

    def test_spoken_number(self):
        self.assertEqual(op.spoken("949 669 7337"), "nine four nine, six six nine, seven three three seven")

    def test_init_fills_what_it_can_and_lists_the_rest(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(op, "TENANTS", Path(d) / "t"), \
                mock.patch.object(op, "ASSETS", Path(d) / "a"):
            (Path(d) / "t").mkdir()
            logo = Path(oc.load_profile("truenorth")["logo"]["file"])
            r = op.init("xyz-air", "XYZ Air", number="714 555 0100", logo=str(logo))
            self.assertFalse(r["ready"])
            for need in ("owner voice (ElevenLabs voice)", "presenter (Argil look)"):
                self.assertIn(need, r["missing"])
            prof = json.loads((Path(d) / "t" / "xyz-air.json").read_text())
            self.assertEqual(prof["contact_number"]["spoken"], "seven one four, five five five, zero one zero zero")
            self.assertTrue(prof["brand"]["colors"]["primary"].startswith("#"))
            with self.assertRaises(SystemExit):
                op.init("xyz-air", "XYZ Air")


class CardTests(unittest.TestCase):
    def test_every_style_stays_in_the_top_band(self):
        prof = oc.load_profile("truenorth")
        for s in oc.STYLES:
            card, num = oc.layers(prof, s)
            for layer in (card, num):
                box = layer.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
                self.assertLessEqual(box[3], 344, f"{s} reaches the presenter's face")


if __name__ == "__main__":
    unittest.main()


class CloseSaveTests(unittest.TestCase):
    def test_restyle_needs_approval_and_keeps_the_old_close(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "fmt" / "tenants").mkdir(parents=True)
            shutil.copy(of.FORMAT_DIR / "format.json", d / "fmt" / "format.json")
            prof = oc.load_profile("truenorth")
            old = d / "closes" / "truenorth-close-v1"
            old.mkdir(parents=True)
            src = Path(prof["close"]["dir"])
            for f in ("close-v1.mp4", "dim-truck1-close-raw.mp4", "speech.json"):
                shutil.copy(src / f, old / f)
            prof["close"]["dir"] = str(old)
            (d / "fmt" / "tenants" / "truenorth.json").write_text(json.dumps(prof))
            with mock.patch.object(os_, "FORMAT_DIR", d / "fmt"):
                os_.close_restyle("truenorth", "restyle", "split", work=d / "work")
                p = os_.Project("restyle", d / "work")
                with self.assertRaises(SystemExit):
                    os_.close_save(p)
                os_.gate(p, "close", "Bob: yes, use the split card")
                r = os_.close_save(p)
            new = json.loads((d / "fmt" / "tenants" / "truenorth.json").read_text())
            self.assertEqual(new["close"]["id"], "truenorth-close-v2")
            self.assertEqual(new["brand"]["card_style"], "split")
            self.assertEqual(new["close_history"][-1]["id"], "truenorth-close-v1")
            self.assertTrue((old / "close-v1.mp4").exists())
            self.assertTrue(Path(r["saved_close"], "close-v2.mp4").exists())
