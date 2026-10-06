"""Source AI provenance carried into the export: verbatim labels, streams untouched, no invented labels."""
import hashlib, json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from studio import provenance  # noqa: E402

FF = shutil.which("ffmpeg")
A = '{"Label":"1","ContentProducer":"kling","ProduceID":"KLingMuse_aaa","ReservedCode1":null,"ContentPropagator":"kling","PropagateID":"KLingMuse_aaa","ReservedCode2":null}'
B = '{"Label":"1","ContentProducer":"kling","ProduceID":"KLingMuse_bbb","ReservedCode1":null,"ContentPropagator":"kling","PropagateID":"KLingMuse_bbb","ReservedCode2":null}'


def clip(path, label=None, audio=False, color="red"):
    args = [FF, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s=64x114:d=1", "-r", "30"]
    if audio: args += ["-f", "lavfi", "-i", "sine=f=440:d=1", "-shortest"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if label: args += ["-metadata", f"AIGC={label}", "-movflags", "+use_metadata_tags"]
    subprocess.run(args + [str(path)], check=True)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


@unittest.skipUnless(FF and shutil.which("ffprobe"), "ffmpeg/ffprobe needed")
class Provenance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); d = Path(self.tmp.name)
        for sub in ("media", "build/out/x-9x16/renders", "generated/transitions"): (d / sub).mkdir(parents=True)
        clip(d / "media/r01.mp4", A); clip(d / "media/r02.mp4", B, color="blue"); clip(d / "media/r03.mp4", A, color="green")
        clip(d / "media/plain.mp4", color="gray")
        self.render = d / "build/out/x-9x16/renders/x-9x16.mp4"; clip(self.render, audio=True, color="white")
        (d / "build/beats-vertical.json").write_text(json.dumps({"scenes": [{"id": i} for i in ("R01", "R02", "R03", "R04", "R05")]}))
        self.p = SimpleNamespace(dir=d, gen=d / "generated", build=d / "build", render_path=lambda cut: self.render, data={"transitions": [], "scenes": [
            {"id": "R01", "data": {"media": "media/r01.mp4"}}, {"id": "R02", "data": {"media": "media/r02.mp4"}},
            {"id": "R03", "data": {"media": "media/r03.mp4"}}, {"id": "R04", "data": {"media": "media/plain.mp4"}}, {"id": "R05", "data": {}}]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_labels_copied_verbatim_streams_untouched_and_idempotent(self):
        streams = provenance._streams_md5(self.render)
        rep = provenance.run(self.p, "vertical")
        self.assertTrue(rep["written"])
        self.assertEqual(rep["labels"], [A, B])                       # distinct, scene order, verbatim strings
        self.assertEqual(provenance.label_of(self.render), A)          # the first source's label, unchanged
        tags = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json", str(self.render)],
                                         capture_output=True, text=True).stdout)["format"]["tags"]
        self.assertEqual(json.loads(tags["aigc_sources"]), [A, B])
        self.assertEqual(provenance._streams_md5(self.render), streams)   # metadata only
        self.assertEqual([s["scene"] for s in rep["sources"]], ["R01", "R02", "R03"])
        self.assertEqual(rep["sha256_after"], sha(self.render)); self.assertNotEqual(rep["sha256_before"], rep["sha256_after"])
        again = provenance.run(self.p, "vertical")
        self.assertFalse(again["written"]); self.assertEqual(again["sha256_before"], again["sha256_after"])
        self.assertEqual(json.loads((self.p.build / "provenance-vertical.json").read_text())["labels"], [A, B])

    def test_no_labelled_source_leaves_render_unchanged(self):
        for s in self.p.data["scenes"][:3]: s["data"] = {"media": "media/plain.mp4"}
        before = sha(self.render)
        rep = provenance.run(self.p, "vertical")
        self.assertEqual((rep["labels"], rep["written"], sha(self.render)), ([], False, before))
        self.assertIsNone(provenance.label_of(self.render))           # nothing invented

    def test_stream_change_aborts_and_keeps_original(self):
        before = sha(self.render)
        calls = iter([{"v": "x", "a": "y"}, {"v": "z", "a": "y"}])
        with mock.patch.object(provenance, "_streams_md5", side_effect=lambda _p: next(calls)):
            with self.assertRaises(SystemExit):
                provenance.run(self.p, "vertical")
        self.assertEqual(sha(self.render), before)
        self.assertFalse(list(self.render.parent.glob("*.tmp.mp4")))

    def test_transcode_keeps_label_only_with_metadata_flags(self):
        d = self.p.dir
        for name, extra in (("kept.mp4", list(provenance.TAGS)), ("lost.mp4", [])):
            subprocess.run([FF, "-y", "-v", "error", "-i", str(d / "media/r01.mp4"), "-c:v", "libx264", "-an", *extra, str(d / name)], check=True)
        self.assertEqual(provenance.label_of(d / "kept.mp4"), A)
        self.assertIsNone(provenance.label_of(d / "lost.mp4"))         # why plain ffmpeg trims lose the label

    def test_transition_clips_count_as_sources(self):
        clip(self.p.gen / "transitions/T1-9x16.mp4", B, color="yellow")
        for s in self.p.data["scenes"][:3]: s["data"] = {}
        self.p.data["transitions"] = [{"id": "T1"}]
        self.assertEqual(provenance.run(self.p, "vertical")["labels"], [B])


if __name__ == "__main__":
    unittest.main()
