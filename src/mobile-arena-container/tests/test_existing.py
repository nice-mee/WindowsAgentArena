"""Offline checks only: no ADB calls, model requests, or phone interactions."""
import argparse
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
from types import SimpleNamespace
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cases
import galaxy_worker
import phone
import review
import run
import verify


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.context = cases.task_context(datetime(2026, 11, 3, tzinfo=ZoneInfo("Asia/Shanghai")))
        self.actions = {"passed": True, "pin_entry_observed": True}

    def test_friday_and_runtime_pin(self):
        self.assertEqual(self.context["friday"], "2026-11-06")
        self.assertEqual(cases.task_context(datetime(2026, 11, 7, tzinfo=ZoneInfo("Asia/Shanghai")))["friday"], "2026-11-13")
        template = cases.make_request("unlock")
        self.assertIn("<runtime PIN>", template)
        self.assertIn("987654", cases.make_request("unlock", "987654"))

    def test_unknown_or_conflicting_lock_state_is_not_unlocked(self):
        self.assertIsNone(phone.lock_state("No recognized keyguard field"))
        self.assertIsNone(phone.lock_state("mShowingLockscreen=true mKeyguardShowing=false"))
        self.assertTrue(phone.lock_state("KeyguardServiceDelegate\n  showing=true\n  secure=true\n"))
        self.assertFalse(phone.lock_state("mShowingLockscreen=false"))

    def test_unlock_requires_real_transition_not_model_claim(self):
        answer = {"run_id": "r", "unlocked": True}
        for before, after, actions in [({"locked": False}, {"locked": False, "awake": True}, self.actions),
                                       ({"locked": True}, {"locked": None, "awake": True}, self.actions),
                                       ({"locked": True}, {"locked": False, "awake": True}, {"passed": True}),
                                       ({"locked": True}, {"locked": False, "awake": True}, {"passed": False})]:
            result = verify.evaluate("unlock", self.context, answer, before, after, actions, self.directory)
            self.assertEqual(result["status"], "failed")
        result = verify.evaluate("unlock", self.context, answer, {"locked": True},
                                 {"locked": False, "awake": True}, self.actions, self.directory)
        self.assertEqual(result["status"], "passed")

    def test_requests_are_user_language_without_grading_hints(self):
        for case in cases.CASES:
            request = cases.make_request(case)
            self.assertLess(len(request), 80)
            for forbidden in ("Galaxy", "MobileAgent", "MCP", "JSON", "run_id", "字段", "停留", "重试"):
                self.assertNotIn(forbidden, request)
        self.assertIn("北京海淀", cases.make_request("weather"))
        self.assertNotIn("浦东", cases.make_request("weather"))

    def test_wechat_accepts_natural_wording_for_review_not_auto_pass(self):
        (self.directory / "screen.png").write_bytes(b"test evidence")
        answer = {"device_results": [{"result": "已问 Flint 周五下午要不要一起喝咖啡。"}]}
        after = {"locked": False, "foreground_package": None}
        result = verify.evaluate("wechat", self.context, answer, {}, after, self.actions, self.directory)
        self.assertEqual(result["status"], "review_required")
        self.assertTrue(any("旧消息" in item for item in result["review_checklist"]))

    def test_weather_prose_without_package_or_temperature_schema_is_reviewable(self):
        (self.directory / "screen.png").write_bytes(b"test evidence")
        answer = {"device_results": [{"result": "北京海淀今天晴，外出带件外套。"}]}
        result = verify.evaluate("weather", self.context, answer, {}, {"foreground_package": None},
                                 self.actions, self.directory)
        self.assertEqual(result["status"], "review_required")
        self.assertNotIn("foreground", result["checks"])
        self.assertTrue(any("北京市海淀区" in item for item in result["review_checklist"]))
        # Wrong city or stale facts must still be reviewed, never auto-passed.
        answer["device_results"][0]["result"] = "上海浦东昨天晴。"
        result = verify.evaluate("weather", self.context, answer, {}, {}, self.actions, self.directory)
        self.assertEqual(result["status"], "review_required")

    def test_weather_missing_feedback_fails(self):
        (self.directory / "ui.xml").write_text("<hierarchy/>")
        result = verify.evaluate("weather", self.context, {"device_results": [{"result": None}]},
                                 {}, {}, self.actions, self.directory)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["feedback_present"])

    def test_missing_evidence_does_not_auto_pass(self):
        result = verify.evaluate("weather", self.context, {"galaxy_result": "已完成"},
                                 {}, {}, self.actions, self.directory)
        self.assertEqual(result["status"], "failed")

    def test_oem_without_current_focus_uses_single_ui_package(self):
        observed = {"foreground_package": None}
        phone.add_ui_evidence(observed, '<hierarchy><node package="com.coloros.weather2" text="浦东新区"/></hierarchy>')
        self.assertEqual(observed["foreground_package"], "com.coloros.weather2")
        self.assertEqual(observed["foreground_source"], "ui_tree_single_package")
        ambiguous = {"foreground_package": None}
        phone.add_ui_evidence(ambiguous, '<hierarchy><node package="weather"/><node package="keyboard"/></hierarchy>')
        self.assertIsNone(ambiguous["foreground_package"])
        known = {"foreground_package": "existing", "foreground_source": "window_focus"}
        phone.add_ui_evidence(known, '<hierarchy><node package="weather"/></hierarchy>')
        self.assertEqual(known["foreground_package"], "existing")

    def test_secret_redaction_keeps_valid_json(self):
        value = {"request": "PIN 987654", "number": 987654, "elapsed": 1.987654}
        redacted = phone.redact_secret(value, "987654")
        self.assertEqual(redacted["request"], "PIN <redacted>")
        self.assertEqual(redacted["number"], "<redacted>")
        json.loads(json.dumps(redacted))

    def test_final_answer_preserves_prose_and_multiple_terminal_tasks(self):
        with self.assertRaises(ValueError):
            verify.final_answer({"tasks": {}}, "d")
        tasks = {k: {"target_device_id": "d", "dependents": [], "status": "completed",
                     "result": {"status": "completed", "result": [{"result": text}]}}
                 for k, text in (("a", "海淀今天晴。"), ("b", "当前温度适宜。"))}
        execution = {"tasks": tasks, "galaxy": {"session_results": {"final_results": [
            {"request": "must never extract this prompt", "result": "北京海淀今天晴。"}]}}}
        answer = verify.final_answer(execution, "d")
        self.assertEqual(len(answer["device_results"]), 2)
        self.assertEqual(answer["device_results"][0]["result"], "海淀今天晴。")
        self.assertEqual(answer["galaxy_result"], "北京海淀今天晴。")
        self.assertNotIn("must never extract", json.dumps(answer))
        with self.assertRaises(ValueError):
            verify.final_answer(execution, "another-device")

    def test_manual_review_cannot_upgrade_execution_failure(self):
        phone.save(self.directory / "result.json", {"status": "execution_failed"})
        with self.assertRaises(ValueError):
            review.record_review(self.directory, "pass", "checked")

    def test_manual_review_preserves_automatic_verdict(self):
        (self.directory / "after").mkdir()
        (self.directory / "after/screen.png").write_bytes(b"evidence")
        phone.save(self.directory / "answer.json", {})
        phone.save(self.directory / "result.json", {"status": "review_required",
                                                    "verification": {"status": "review_required"}})
        result = review.record_review(self.directory, "pass", "Verified actual evidence")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["verification"]["status"], "review_required")
        with self.assertRaises(ValueError):
            review.record_review(self.directory, "fail", "Cannot overwrite")

    def test_action_summary_omits_password_arguments(self):
        directory = self.directory / "galaxy_mobile-arena-example_task-1"
        directory.mkdir()
        action = {"function": "MobileActionExecutor/type_text", "arguments": {"text": "987654"},
                  "result": {"result": {"success": True}}}
        (directory / "response.log").write_text(json.dumps({"action": [action]}))
        evidence = verify.action_evidence(self.directory, "987654")
        self.assertTrue(evidence["passed"])
        self.assertTrue(evidence["pin_entry_observed"])
        self.assertNotIn("987654", json.dumps(evidence))

    def test_home_key_alone_does_not_prove_pin_unlock(self):
        directory = self.directory / "galaxy_mobile-arena-example_task-1"
        directory.mkdir()
        action = {"function": "MobileActionExecutor/press_key", "arguments": {"key_code": "KEYCODE_HOME"},
                  "result": {"result": {"success": True}}}
        (directory / "response.log").write_text(json.dumps({"action": [action]}))
        evidence = verify.action_evidence(self.directory, "987654")
        self.assertTrue(evidence["passed"])
        self.assertFalse(evidence["pin_entry_observed"])


class RunnerTests(unittest.TestCase):
    def test_wrong_device_profile_stops_before_any_galaxy_request(self):
        with tempfile.TemporaryDirectory() as directory:
            client = Mock(initialize=AsyncMock(), shutdown=AsyncMock(), process_request=AsyncMock())
            client._client.device_manager.device_registry.get_device.return_value = SimpleNamespace(
                os="linux", status=SimpleNamespace(value="idle"),
                capabilities=["cli", "linux_apps"], metadata={"system_info": {"platform": "linux"}})
            settings = {"run_id": "offline-run", "serial": "offline-phone", "device": "mobile_1"}
            module = SimpleNamespace(GalaxyClient=Mock(return_value=client))
            with patch.dict(sys.modules, {"galaxy.galaxy_client": module}), patch.dict(os.environ), \
                    patch.object(galaxy_worker, "start_local", new=AsyncMock(
                        return_value=SimpleNamespace(device_id="mobile_1"))):
                with self.assertRaisesRegex(RuntimeError, "conflicts with host metadata"):
                    asyncio.run(galaxy_worker.execute(settings, Path(directory), ""))
            client.process_request.assert_not_called()
            client.shutdown.assert_awaited_once()
            result = json.loads((Path(directory) / "initialization.json").read_text())
            self.assertEqual(result["status"], "failed")

    def test_mobile_profile_rejects_host_metadata_and_mixed_capabilities(self):
        def profile():
            return SimpleNamespace(os="mobile", status=SimpleNamespace(value="idle"),
                                   capabilities=["mobile_touch", "mobile_apps"],
                                   metadata={"system_info": {"platform": "mobile", "platform_type": "mobile"}})
        galaxy_worker.validate_mobile_profile(profile())
        bad_os = profile()
        bad_os.os = "linux"
        bad_metadata = profile()
        bad_metadata.metadata["system_info"]["platform_type"] = "computer"
        bad_caps = profile()
        bad_caps.capabilities += ["cli", "linux_apps"]
        no_metadata = profile()
        no_metadata.metadata = {}
        for invalid in (None, bad_os, bad_metadata, bad_caps, no_metadata):
            with self.subTest(profile=invalid), self.assertRaises(RuntimeError):
                galaxy_worker.validate_mobile_profile(invalid)

    def exercise(self, mode):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = argparse.Namespace(case="wechat", output=root, probe=False, serial=None,
                                      device="mobile_device_1", ufo_root=root, timeout=0.05)
            before = {"locked": False}
            info = {"serial": "offline-test", "state": before, "packages": ["com.tencent.mm"]}
            runtime = root / "fake-runtime"
            runtime.mkdir()
            (runtime / "logs").mkdir()
            real_popen = subprocess.Popen
            children = []

            def fake_worker(*unused, **kwargs):
                run_dir = Path(unused[0][-1])
                phone.save(run_dir / "submission.json", {"status": "submitting"})
                child = real_popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                   start_new_session=True, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                children.append(child)
                if mode == "sigterm":
                    def communicate(**unused):
                        os.kill(os.getpid(), signal.SIGTERM)
                    child.communicate = communicate
                return child

            old_handler = signal.getsignal(signal.SIGTERM)
            try:
                with patch.object(run, "preflight", return_value=info), \
                        patch.object(run, "snapshot", return_value=before), \
                        patch.object(run, "runtime_directory", return_value=runtime), \
                        patch.object(run.subprocess, "Popen", side_effect=fake_worker):
                    code = run.run(args)
                result = json.loads(next(root.glob("mobile-arena-*/result.json")).read_text())
                self.assertEqual(code, 1)
                self.assertEqual(result["status"], "timeout" if mode == "timeout" else "interrupted")
                self.assertTrue(result["owned_process_group_stopped"])
                self.assertFalse(result["device_operations_stopped"])
                self.assertEqual(result["verification"]["status"], "not_run")
                self.assertEqual(signal.getsignal(signal.SIGTERM), old_handler)
                self.assertFalse(run.group_running(children[0].pid))
            finally:
                for child in children:
                    if child.poll() is None:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
                    if child.stdin:
                        child.stdin.close()

    def test_timeout_stops_owned_dummy_worker_and_retains_failure(self):
        self.exercise("timeout")

    def test_sigterm_persists_result_and_stops_owned_dummy_worker(self):
        self.exercise("sigterm")


if __name__ == "__main__":
    unittest.main()
