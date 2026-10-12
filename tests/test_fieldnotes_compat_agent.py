"""Field-notes saved-plan compatibility, migration and Nano's draft-only entry point. The model is stubbed (no calls);
the saved-plan tests read the real projects in this repository and must leave them untouched."""
import copy, hashlib, io, json, shutil, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from studio import common, fieldnotes_agent as ag, fieldnotes_compose as fc, fieldnotes_plan as fp  # noqa: E402
from test_fieldnotes_plan import BRIEF_DENTAL, DENTAL  # noqa: E402

REPO = HERE.parent
USAGE = {"model": "stub", "equivalent_api_cost_usd": 0.0}


def overstated(plan):
    """DENTAL with the hedged outcome shown as done (the shape of the saved dental v1 to v3 endings)."""
    bad = copy.deepcopy(plan)
    bad["chapters"][2]["events"] = [x for x in bad["chapters"][2]["events"] if not (x.get("obj") == "cal" and x.get("do") == "state")]
    bad["chapters"][2]["events"].append({"on": "slot", "do": "state", "obj": "cal", "state": "rebooked"})
    return bad


def digest(d):
    return {p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob("*")) if p.is_file()}


class Versions(unittest.TestCase):
    def test_versions_are_recorded_numbers_and_the_renderer_declares_its_own(self):
        v = fc.versions()
        self.assertEqual(set(v), {"schema", "planner", "validator", "renderer"})
        self.assertTrue(all(isinstance(x, int) and x > 0 for x in v.values()))
        self.assertIn(f"Renderer version: {v['renderer']}", (REPO / "engine" / "fieldnotes.js").read_text(encoding="utf-8")[:2000])

    def test_schema_is_recognised(self):
        self.assertEqual(fc.plan_schema(DENTAL), 2)
        self.assertEqual(fc.plan_schema({"stage": "flow", "chapters": []}), 1)
        self.assertEqual(fc.plan_schema({}), 0)


class Compatibility(unittest.TestCase):
    def test_current_plan_is_compatible(self):
        self.assertEqual(fc.compatibility(DENTAL, BRIEF_DENTAL, {"status": "awaiting-approval"})["status"], "compatible")

    def test_overstated_outcome_needs_migration_and_is_not_waved_through(self):
        c = fc.compatibility(overstated(DENTAL), BRIEF_DENTAL, {"status": "awaiting-approval"})
        self.assertEqual(c["status"], "needs-migration")
        self.assertTrue(any("shows cal as 'rebooked'" in p for p in c["problems"]))

    def test_old_schema_needs_migration_and_legacy_versions_are_marked_unrecorded(self):
        c = fc.compatibility({"stage": "flow", "chapters": []}, BRIEF_DENTAL, {"status": "awaiting-approval", "style": {"renderer_sha": "x"}})
        self.assertEqual(c["status"], "needs-migration")
        self.assertIs(c["recorded"]["recorded"], False)
        self.assertEqual(c["recorded"]["schema"], 1)

    def test_a_run_that_stopped_has_nothing_to_migrate(self):
        self.assertEqual(fc.compatibility(DENTAL, BRIEF_DENTAL, {"status": "needs-answers"})["status"], "not-previewed")


class LengthWithOtherProblems(unittest.TestCase):
    def test_the_length_is_reported_together_with_other_problems(self):
        """2026-10-12: a repair fixed a cramped label but ran 22 s for a 15 s brief, because the length was only
        checked once everything else passed; one repair call now sees both."""
        bad = copy.deepcopy(DENTAL); bad["chapters"][0]["emphasis"] = "neon"
        p = "\n".join(fc.validate_plan(bad, BRIEF_DENTAL + " About 6 seconds."))
        self.assertIn("emphasis must be", p)
        self.assertIn("the brief asks for about 6 s", p)


class SavedPlans(unittest.TestCase):
    """The real True North and dental plans in this repository, checked without writing anything."""
    def check(self, name):
        if not (REPO / "projects" / name / "fieldnotes" / "run.json").exists():
            self.skipTest(f"{name} not in this checkout")
        return {int(k): v for k, v in fp.check(name, write=False)["versions"].items()}

    def test_dental_v1_to_v3_need_migration_for_the_overstated_outcome_and_v4_is_compatible(self):
        c = self.check("fn-dental-illustrated")
        for v in (1, 2, 3):
            self.assertEqual(c[v]["status"], "needs-migration", v)
            self.assertTrue(any(p.startswith("outcome check") for p in c[v]["problems"]), v)
        self.assertEqual(c[4]["status"], "compatible")

    def test_true_north_plans_need_migration(self):
        self.assertEqual(self.check("fn-tn-illustrated")[1]["status"], "needs-migration")
        self.assertIn("schema 1", self.check("fn-tn-cool-before-peak")[1]["problems"][0])

    def test_checking_touches_no_plan_brief_report_or_preview(self):
        d = REPO / "projects" / "fn-dental-illustrated" / "fieldnotes"
        keep = {k: v for k, v in digest(d).items() if not k.startswith("compat")}
        self.check("fn-dental-illustrated")
        self.assertEqual({k: v for k, v in digest(d).items() if not k.startswith("compat")}, keep)


class TempStudio(unittest.TestCase):
    """A throwaway Studio root holding one project with a saved, now-incompatible v1 (overstated outcome)."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fn-compat-"))
        self.name = "fn-test"
        fn = self.tmp / "projects" / self.name / "fieldnotes"
        fn.mkdir(parents=True)
        self.brief = BRIEF_DENTAL + "\n"
        (fn / "brief-v1.txt").write_text(self.brief, encoding="utf-8")
        (fn / "plan-v1.json").write_text(json.dumps(overstated(DENTAL)), encoding="utf-8")
        (fn / "preview-v1.mp4").write_bytes(b"old preview")
        (fn / "report-v1.json").write_text(json.dumps({"version": 1, "status": "awaiting-approval", "duration": 15.0,
                                                       "preview": f"projects/{self.name}/fieldnotes/preview-v1.mp4"}), encoding="utf-8")
        (fn / "run.json").write_text(json.dumps({"name": self.name, "current": 1, "versions": [
            {"version": 1, "status": "awaiting-approval", "preview": f"projects/{self.name}/fieldnotes/preview-v1.mp4"}]}), encoding="utf-8")
        (self.tmp / "projects" / self.name / "project.json").write_text(json.dumps(fc.compile_plan(overstated(DENTAL), self.name, "Test")), encoding="utf-8")
        self.fn = fn
        for target in ((fp, "ROOT"), (common, "ROOT"), (ag, "ROOT")):
            p = mock.patch.object(*target, self.tmp); p.start(); self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def originals(self):
        return {k: v for k, v in digest(self.fn).items() if k.endswith("-v1.txt") or k.endswith("-v1.json") or k.endswith("-v1.mp4")}

    def migrate_with(self, *replies):
        with mock.patch.object(fp, "ask_model", side_effect=[(json.dumps(r), USAGE) for r in replies]) as m, redirect_stdout(io.StringIO()):
            rec = fp.migrate(self.name, version=1, render=False)
        return rec, m


class Migration(TempStudio):
    def test_rebuild_refuses_a_plan_that_needs_migration(self):
        before = (self.tmp / "projects" / self.name / "project.json").read_bytes()
        with self.assertRaises(SystemExit) as e:
            fp.rebuild(self.name, render=False)
        self.assertIn("needs-migration", str(e.exception))
        self.assertEqual((self.tmp / "projects" / self.name / "project.json").read_bytes(), before)

    def test_migration_keeps_the_brief_records_versions_and_reports_changes(self):
        keep = self.originals()
        fixed = copy.deepcopy(DENTAL); fixed["brief"] = "a rewritten brief the model should not be able to change"
        rec, m = self.migrate_with(fixed)
        prompt = m.call_args_list[0].args[0]
        self.assertIn("## Migration", prompt)
        self.assertIn("shows cal as 'rebooked'", prompt)          # the old problems are handed to the planner
        self.assertEqual(rec["status"], "planned")
        self.assertEqual(rec["migrated_from"], 1)
        self.assertTrue(rec["brief_unchanged"])
        self.assertEqual((self.fn / "brief-v2.txt").read_text(encoding="utf-8").strip(), self.brief.strip())
        self.assertEqual(rec["versions"], fc.versions())
        self.assertIn("ending: cal ends available (was rebooked)", rec["changes"])
        self.assertEqual(self.originals(), keep)                   # v1 brief, plan, report and preview untouched
        self.assertTrue((self.fn / "storyboard-v2.md").exists())
        c = fp.check(self.name)["versions"]
        self.assertEqual((c["1"]["status"], c["2"]["status"]), ("needs-migration", "compatible"))

    def test_a_migration_that_still_overstates_is_refused_not_rendered(self):
        keep = self.originals()
        rec, m = self.migrate_with(overstated(DENTAL), overstated(DENTAL))   # first pass and the one repair both overstate
        self.assertEqual(m.call_count, 2)
        self.assertEqual(rec["status"], "invalid-plan")
        self.assertTrue(any("rebooked" in p for p in rec["plan_problems"]))
        self.assertFalse((self.fn / "preview-v2.mp4").exists())
        self.assertEqual(self.originals(), keep)

    def test_a_compatible_version_is_not_migrated(self):
        self.migrate_with(DENTAL)
        with self.assertRaises(SystemExit) as e:
            fp.migrate(self.name, version=2, render=False)
        self.assertIn("compatible", str(e.exception))


class Agent(TempStudio):
    def test_model_actions_need_todays_quote(self):
        q = ag.quote("migrate", self.name)
        self.assertEqual(q["model_calls"], "1 to 2")
        self.assertIn("subscription", q["billing"])
        with self.assertRaises(SystemExit):
            ag.main(["migrate", self.name, "--quote", "nope"])
        self.assertEqual(ag.quote("status", self.name)["model_calls"], "none")
        self.assertNotIn("quote_id", ag.quote("rebuild", self.name))

    def test_review_names_fit_the_studio(self):
        self.assertEqual(ag.review_name("fn-dental", 4), "fn-dental-v4")
        n = ag.review_name("a" * 40, 12)
        self.assertLessEqual(len(n), 40); self.assertTrue(ag.NAME_OK.match(n)); self.assertTrue(n.endswith("-v12"))

    def test_deliver_copies_into_the_studio_once_and_never_touches_foreign_folders(self):
        live = self.tmp / "live"
        with mock.patch.object(ag, "REVIEW_ROOT", live), mock.patch.object(ag, "prove_link", return_value=(True, {"stub": {"ok": True}})):
            out = ag.deliver(self.name, 1)
            self.assertTrue(out["delivered"] and out["verified"])
            mp4 = live / "projects" / "fn-test-v1" / "build" / "out" / "fn-test-v1-9x16" / "renders" / "fn-test-v1-9x16.mp4"
            self.assertEqual(mp4.read_bytes(), b"old preview")
            self.assertTrue(out["url"].endswith("/admin/gtm/video-studio/fn-test-v1?step=publish"))
            pj = json.loads((live / "projects" / "fn-test-v1" / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(pj["name"], "fn-test-v1")
            stamp = (live / "projects" / "fn-test-v1" / "fieldnotes" / ag.MARKER).stat().st_mtime_ns
            ag.deliver(self.name, 1)                                     # same preview: reused, not rewritten
            self.assertEqual((live / "projects" / "fn-test-v1" / "fieldnotes" / ag.MARKER).stat().st_mtime_ns, stamp)
            (live / "projects" / "fn-test-v2").mkdir(parents=True)
            (live / "projects" / "fn-test-v2" / "project.json").write_text("{}", encoding="utf-8")
            self.migrate_with(DENTAL)
            (self.fn / "preview-v2.mp4").write_bytes(b"new"); rep = json.loads((self.fn / "report-v2.json").read_text())
            rep.update(status="awaiting-approval", preview=f"projects/{self.name}/fieldnotes/preview-v2.mp4")
            (self.fn / "report-v2.json").write_text(json.dumps(rep))
            out = ag.deliver(self.name, 2)
            self.assertFalse(out["delivered"]); self.assertIn("not created by this tool", out["why"])
            self.assertEqual((live / "projects" / "fn-test-v2" / "project.json").read_text(), "{}")

    def test_status_marks_versions_needing_migration(self):
        with mock.patch.object(ag, "REVIEW_ROOT", self.tmp / "live"):
            s = ag.status(self.name)
        self.assertEqual(s["versions"][0]["compat"], "needs-migration")
        self.assertEqual(s["versions_now"], fc.versions())


class DraftOnly(unittest.TestCase):
    def test_the_workflow_only_builds_silent_previews_and_renders_locally(self):
        src = (REPO / "studio" / "fieldnotes_plan.py").read_text(encoding="utf-8")
        self.assertIn('"build", r.name, "--dry-timings"', src)
        for word in ("render-remote", "publish", "zernio", "approve("):
            self.assertNotIn(word, src)
        agent = (REPO / "studio" / "fieldnotes_agent.py").read_text(encoding="utf-8")
        self.assertNotIn('"render-remote"', agent); self.assertNotIn("subprocess.run([py", agent)

    def test_storyboard_is_plain_words(self):
        s = fc.storyboard(DENTAL, 3, 15.2)
        self.assertIn("THE PROBLEM", s); self.assertIn("about 15.2 s", s)
        self.assertNotRegex(s, r"[–—{}]")


if __name__ == "__main__":
    unittest.main()
