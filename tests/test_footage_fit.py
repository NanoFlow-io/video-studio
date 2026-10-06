"""Footage fit, continuity, data-media-start and the held-sound report. Run from the repo root:
  .venv/bin/python -m unittest discover -s tests -v"""
import shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np  # noqa: E402
from studio import beats, cuts, mediafit, mix  # noqa: E402
from studio.common import SR  # noqa: E402

FF = shutil.which("ffmpeg") or str(Path.home() / ".local" / "bin" / "ffmpeg")


def clip(path, seconds, color="red"):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s=64x114:d={seconds}", "-r", "30",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


def sc(sid, start, end, t="broll"):
    return {"id": sid, "type": t, "start": start, "end": end}


class MediaFit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.base = Path(cls.tmp.name)
        clip(cls.base / "media/a.mp4", 3); clip(cls.base / "media/b.mp4", 3, "blue"); clip(cls.base / "media/long.mp4", 8, "green")
        shutil.copy(cls.base / "media/a.mp4", cls.base / "media/a-copy.mp4")   # same bytes, other name

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_fit(self, scenes, data, dry=False):
        return mediafit.check("vertical", scenes, {k: {"data": v} for k, v in data.items()}, self.base, dry=dry)

    def test_exact_and_longer_pass(self):
        r = self.run_fit([sc("R01", 0, 3.0, "hook"), sc("R02", 3.0, 5.0)], {"R01": {"media": "media/a.mp4"}, "R02": {"media": "media/long.mp4"}})
        self.assertEqual(r["problems"], []); self.assertTrue(all(x["ok"] for x in r["scenes"]))
        self.assertAlmostEqual(r["scenes"][0]["duration"], 3.0, places=2)

    def test_short_fails_with_numbers(self):
        r = self.run_fit([sc("R02", 1.0, 4.2)], {"R02": {"media": "media/a.mp4"}})
        self.assertEqual(len(r["problems"]), 1); row = r["scenes"][0]
        self.assertFalse(row["ok"]); self.assertEqual(row["needed"], 3.2); self.assertAlmostEqual(row["usable"], 3.0, places=2)
        self.assertIn("short", r["problems"][0])
        self.assertEqual(self.run_fit([sc("R02", 1.0, 4.02)], {"R02": {"media": "media/a.mp4"}})["problems"], [])   # within a frame

    def test_media_in_reduces_usable(self):
        r = self.run_fit([sc("R02", 0, 2.5)], {"R02": {"media": "media/a.mp4", "media_in": 1.0}})
        self.assertAlmostEqual(r["scenes"][0]["usable"], 2.0, places=2); self.assertEqual(len(r["problems"]), 1)
        self.assertEqual(self.run_fit([sc("R02", 0, 2.0)], {"R02": {"media": "media/a.mp4", "media_in": 1.0}})["problems"], [])

    def test_media_in_past_end_fails(self):
        r = self.run_fit([sc("R02", 0, 0.5)], {"R02": {"media": "media/a.mp4", "media_in": 3.0}})
        self.assertEqual(len(r["problems"]), 1); self.assertIn("at or past the end", r["problems"][0])

    def test_restart_fails_then_suggestion_passes(self):
        scenes = [sc("R02", 2.0, 3.0), sc("R03", 3.0, 4.5)]
        r = self.run_fit(scenes, {"R02": {"media": "media/long.mp4", "media_in": 0.5}, "R03": {"media": "media/long.mp4"}})
        self.assertEqual(r["restarts"], ["R03"]); self.assertEqual(len(r["problems"]), 1)
        self.assertIn("R03 restarts media/long.mp4 at 0s; to continue from R02 set data.media_in to 1.500", r["problems"][0])
        ok = self.run_fit(scenes, {"R02": {"media": "media/long.mp4", "media_in": 0.5}, "R03": {"media": "media/long.mp4", "media_in": 1.5}})
        self.assertEqual((ok["problems"], ok["warnings"], ok["restarts"]), ([], [], []))
        self.assertEqual(ok["scenes"][1]["same_source_as"], "R02")
        near = self.run_fit(scenes, {"R02": {"media": "media/long.mp4", "media_in": 0.5}, "R03": {"media": "media/long.mp4", "media_in": 1.58}})
        self.assertEqual(near["problems"], [])   # within 0.1 s

    def test_identical_bytes_are_one_source(self):
        r = self.run_fit([sc("R02", 0, 1.0), sc("R03", 1.0, 2.0)], {"R02": {"media": "media/a.mp4"}, "R03": {"media": "media/a-copy.mp4"}})
        self.assertEqual(r["scenes"][0]["sha256"], r["scenes"][1]["sha256"]); self.assertEqual(r["restarts"], ["R03"])
        diff = self.run_fit([sc("R02", 0, 1.0), sc("R03", 1.0, 2.0)], {"R02": {"media": "media/a.mp4"}, "R03": {"media": "media/b.mp4"}})
        self.assertEqual(diff["problems"], [])

    def test_replay_passes(self):
        r = self.run_fit([sc("R02", 0, 1.0), sc("R03", 1.0, 2.0)], {"R02": {"media": "media/a.mp4"}, "R03": {"media": "media/a.mp4", "replay": True}})
        self.assertEqual((r["problems"], r["warnings"]), ([], [])); self.assertTrue(r["scenes"][1]["replay"])
        self.assertIn("replays: R03", mediafit.summary(r))

    def test_non_adjacent_reuse_warns(self):
        r = self.run_fit([sc("R02", 0, 1.0), sc("R03", 1.0, 2.0), sc("R04", 2.0, 3.0)],
                         {"R02": {"media": "media/a.mp4"}, "R03": {"media": "media/b.mp4"}, "R04": {"media": "media/a.mp4"}})
        self.assertEqual(r["problems"], []); self.assertEqual(r["warnings"], ["possible repeated payoff: R04 reuses the source of R02 (media/a.mp4)"])
        rp = self.run_fit([sc("R02", 0, 1.0), sc("R03", 1.0, 2.0), sc("R04", 2.0, 3.0)],
                          {"R02": {"media": "media/a.mp4"}, "R03": {"media": "media/b.mp4"}, "R04": {"media": "media/a.mp4", "replay": True}})
        self.assertEqual(rp["warnings"], [])

    def test_images_and_other_types_ignored(self):
        r = self.run_fit([sc("R01", 0, 9.0, "hook"), sc("R02", 9.0, 20.0), sc("R03", 20.0, 30.0, "end_card")],
                         {"R01": {"media": "media/x.png"}, "R02": {"media": "media/x.png"}, "R03": {}})
        self.assertEqual(r["scenes"], []); self.assertEqual(mediafit.summary(r), "  media vertical: no .mp4 clips")

    def test_run_writes_report_and_stops(self):
        with tempfile.TemporaryDirectory() as b:
            p = SimpleNamespace(dir=self.base, build=Path(b), data={"scenes": [{"id": "R02", "type": "broll", "data": {"media": "media/a.mp4"}}]})
            with self.assertRaises(SystemExit) as e:
                mediafit.run(p, "vertical", {"dry": False, "scenes": [sc("R02", 0, 5.0)]})
            self.assertIn("media fit problems:", str(e.exception))
            rep = __import__("json").loads((Path(b) / "media-fit-vertical.json").read_text())
            self.assertEqual(sorted(rep), ["cut", "dry", "problems", "scenes", "warnings"]); self.assertEqual(len(rep["problems"]), 1)
            mediafit.run(p, "vertical", {"dry": True, "scenes": [sc("R02", 0, 5.0)]})   # dry: warns, no stop

    def test_dry_warns_instead(self):
        r = self.run_fit([sc("R02", 0, 5.0)], {"R02": {"media": "media/a.mp4"}}, dry=True)
        self.assertEqual(r["problems"], []); self.assertEqual(len(r["warnings"]), 1); self.assertTrue(r["warnings"][0].startswith("DRY"))


class SlotHtml(unittest.TestCase):
    def test_media_start_only_when_positive(self):
        s = sc("R02", 1.0, 3.5)
        plain = cuts.slot_html(s, {"media": "media/a.mp4"})
        self.assertEqual(plain, '<div class="mslot" id="slot-R02"><div class="mzoom"><video id="mv-R02" class="clip" data-start="1.000" '
                                'data-duration="2.500" muted playsinline src="assets/project/media/a.mp4"></video></div></div>')
        self.assertEqual(cuts.slot_html(s, {"media": "media/a.mp4", "media_in": 0}), plain)
        self.assertIn('data-duration="2.500" data-media-start="1.250" muted', cuts.slot_html(s, {"media": "media/a.mp4", "media_in": 1.25}))
        self.assertNotIn("<video", cuts.slot_html(s, {"media": "media/a.png"}))
        self.assertEqual(cuts.slot_html(sc("S01", 0, 1, "reveal"), {}), "")


class Validate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)
        for f in ("media/a.mp4", "media/a.png"):
            (self.dir / f).parent.mkdir(exist_ok=True); (self.dir / f).write_bytes(b"x")

    def tearDown(self):
        self.tmp.cleanup()

    def problems(self, **data):
        s = {"id": "R02", "type": "broll", "line": {"text": "hello"}, "cues": [], "data": {"media": "media/a.mp4", "caption": "Hi", **data}}
        return [x for x in beats.validate(SimpleNamespace(dir=self.dir, data={"scenes": [s]})) if "media_in" in x or "replay" in x]

    def test_good(self):
        self.assertEqual(self.problems(media_in=1.5, replay=True), []); self.assertEqual(self.problems(media_in=0), [])

    def test_bad(self):
        for bad in ("1", -0.5, True, [1]):
            self.assertEqual(len(self.problems(media_in=bad)), 1, bad)
        self.assertEqual(len(self.problems(media="media/a.png", media_in=1)), 1)
        for bad in ("yes", 1):
            self.assertEqual(len(self.problems(replay=bad)), 1, bad)


class SoundReport(unittest.TestCase):
    def setUp(self):
        n = int(4.0 * SR); t = np.arange(n) / SR
        on = ((t % 0.7) < 0.4) & (t > 0.2)   # 0.4 s words, 0.3 s gaps
        self.vo = np.repeat((0.89 * np.sin(2 * np.pi * 220 * t) * on)[:, None], 2, axis=1).astype(np.float32)
        self.words = [{"w": f"w{k}", "s": round(0.7 * k, 3), "e": round(0.7 * k + 0.4, 3)} for k in range(1, 5)]
        self.sg = mix._gate(self.vo); self.buzz = np.repeat(np.sin(2 * np.pi * 150 * t)[:, None], 2, axis=1).astype(np.float32)
        self.cue = {"id": "R01.ring", "sfx": "kit:phone_vibrate", "t": 0.0, "stop": 4.0, "duck_db": 0.0}

    def report(self, level_db):
        return mix.held_report(self.vo, [(self.cue, 0, self.buzz * mix._db(level_db))], *self.sg, self.words)[0]

    def test_low_buzz_may_not_be_felt(self):
        r = self.report(-50)
        self.assertGreater(r["worst_word_margin_db"], 40); self.assertGreater(r["worst_50ms_margin_db"], 40)
        self.assertLess(r["pause_level_dbfs"], -42); self.assertEqual(r["flags"], ["may_not_be_felt"])

    def test_loud_buzz_masking_risk(self):
        r = self.report(-3)
        self.assertLess(r["worst_word_margin_db"], 12); self.assertIn("masking_risk", r["flags"]); self.assertNotIn("may_not_be_felt", r["flags"])
        self.assertAlmostEqual(r["pause_level_dbfs"], -6.0, delta=0.5)   # sine RMS = peak - 3 dB


if __name__ == "__main__":
    unittest.main()
