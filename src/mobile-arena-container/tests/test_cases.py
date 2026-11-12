"""MVP case and runner checks using fake phone state, never a connected device."""
import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import batch
from cases import CASES
import galaxy_worker
import phone
import run


class CaseTests(unittest.TestCase):
    def test_nine_default_cases_exclude_opt_in_tasks(self):
        suite = batch.load_suite(run.HERE / "suites/mobile_mvp.json")
        self.assertEqual(len(suite["cases"]), 9)
        self.assertEqual(len(CASES), 12)
        self.assertFalse(set(suite["cases"]) & {"wechat", "weather", "unlock"})
        for name in suite["cases"]:
            self.assertTrue(all(callable(getattr(CASES[name], method)) for method in ("setup", "make_request", "verify", "cleanup")))

    def test_navigation_requires_actual_target_app(self):
        for name in ("home", "open_settings", "open_camera", "open_clock", "open_calculator"):
            with self.subTest(case=name):
                case, state = CASES[name], {}
                with patch.object(phone, "resolve_activity", return_value="target.app/.Main"), \
                        patch.object(phone, "go_home"), patch.object(phone, "start_activity"):
                    case.setup("phone", state)
                self.assertEqual(case.verify("phone", state, {"locked": False, "foreground_package": "target.app"})["status"], "passed")
                self.assertEqual(case.verify("phone", state, {"locked": False, "foreground_package": "wrong.app"})["status"], "failed")

    def test_settings_initialize_compare_and_restore(self):
        for name, original, target in (("auto_rotate", "1", "1"), ("auto_brightness", "0", "0"),
                                       ("screen_timeout", "30000", "120000"), ("font_size", "1.2", "1.3")):
            with self.subTest(case=name):
                case, state = CASES[name], {}
                values = {"current": original}
                def write(serial, key, value):
                    values["current"] = value
                with patch.object(phone, "read_setting", side_effect=lambda *args: values["current"]), \
                        patch.object(phone, "write_setting", side_effect=write), patch.object(phone, "go_home"):
                    case.setup("phone", state)
                    self.assertEqual(state["original"], original)
                    self.assertEqual(case.verify("phone", state, {})["status"], "failed")
                    values["current"] = target  # Simulated agent result, not a real task execution.
                    self.assertEqual(case.verify("phone", state, {})["status"], "passed")
                    case.cleanup("phone", state)
                    self.assertEqual(values["current"], original)

    def test_app_resolution_reports_missing_default(self):
        with patch.object(phone, "adb", return_value="No activity found"):
            with self.assertRaisesRegex(RuntimeError, "No default app"):
                phone.resolve_activity("phone", "action")
        with patch.object(phone, "adb", return_value="target.app/.Main"):
            self.assertEqual(phone.resolve_activity("phone", "action"), "target.app/.Main")

    def test_brightness_restores_mode_and_manual_level(self):
        values = {"screen_brightness_mode": "0", "screen_brightness": "120"}
        state = {}
        with patch.object(phone, "read_setting", side_effect=lambda serial, key: values[key]), \
                patch.object(phone, "write_setting", side_effect=lambda serial, key, value: values.update({key: value})), \
                patch.object(phone, "go_home"):
            CASES["auto_brightness"].setup("phone", state)
            values.update(screen_brightness_mode="0", screen_brightness="200")
            CASES["auto_brightness"].cleanup("phone", state)
        self.assertEqual(values, {"screen_brightness_mode": "0", "screen_brightness": "120"})


class IntegrationTests(unittest.TestCase):
    def run_case_with_fake_worker(self, mode):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = argparse.Namespace(case="auto_rotate", output=root, probe=False, serial=None,
                                      device="mobile_1", ufo_root=root, timeout=1)
            runtime = root / "fake-runtime"
            (runtime / "logs").mkdir(parents=True)
            values = {"current": "0" if mode == "success" else "1"}
            observed = {"locked": False, "awake": True, "foreground_package": "launcher"}
            info = {"serial": "phone", "state": observed, "packages": []}
            def write(serial, key, value):
                values["current"] = value
            def launch(command, **kwargs):
                path = Path(command[-1])
                phone.save(path / "initialization.json", {"status": "passed"})
                phone.save(path / "submission.json", {"status": "submitting"})
                if mode == "success":
                    values["current"] = "1"
                    task = {"target_device_id": "mobile_1", "status": "completed", "dependents": [],
                            "result": {"status": "completed", "result": [{"result": "已开启"}]}}
                    phone.save(path / "execution.json", {"status": "completed", "device_stopped_confirmed": True,
                                                         "tasks": {"task-1": task}})
                    return Mock(returncode=0)
                import subprocess
                return Mock(returncode=-15, communicate=Mock(side_effect=subprocess.TimeoutExpired(command, 1)))
            with patch.object(run, "preflight", return_value=info), patch.object(run, "snapshot", return_value=observed), \
                    patch.object(run, "runtime_directory", return_value=runtime), \
                    patch.object(run.subprocess, "Popen", side_effect=launch), patch.object(run, "stop_group", return_value=True), \
                    patch.object(phone, "read_setting", side_effect=lambda *args: values["current"]), \
                    patch.object(phone, "write_setting", side_effect=write), patch.object(phone, "go_home"):
                run.run(args)
            result = json.loads(next(root.glob("mobile-arena-*/result.json")).read_text())
            if mode == "success":
                self.assertEqual(result["status"], "passed")
                self.assertEqual(values["current"], "0")
                self.assertTrue(result["device_operations_stopped"])
            else:
                self.assertEqual(result["status"], "timeout")
                self.assertEqual(result["execution"]["status"], "timeout")
                self.assertEqual(values["current"], "0")  # Stop unknown: no restoration while the agent might act.
                self.assertFalse(result["device_operations_stopped"])

    def test_runner_grades_before_restoring_settings(self):
        self.run_case_with_fake_worker("success")

    def test_timeout_does_not_restore_while_device_stop_is_unknown(self):
        self.run_case_with_fake_worker("timeout")

    def test_partial_setup_failure_restores_original_value_without_submitting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = argparse.Namespace(case="font_size", output=root, probe=False, serial=None,
                                      device="d", ufo_root=root, timeout=1)
            info = {"serial": "phone", "state": {"locked": False}, "packages": []}
            original, current = "1.2", {"value": "1.2"}
            def write(serial, key, value):
                current["value"] = value
            with patch.object(run, "preflight", return_value=info), \
                    patch.object(phone, "read_setting", side_effect=lambda *args: current["value"]), \
                    patch.object(phone, "write_setting", side_effect=write), \
                    patch.object(phone, "go_home", side_effect=[RuntimeError("home failed"), None]), \
                    patch.object(run.subprocess, "Popen") as launch:
                run.run(args)
            launch.assert_not_called()
            self.assertEqual(current["value"], original)
            result = json.loads(next(root.glob("mobile-arena-*/result.json")).read_text())
            self.assertEqual(result["status"], "initialization_failed")
            self.assertEqual(result["cleanup"]["status"], "completed")

    def test_worker_submits_natural_request_to_galaxy(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = SimpleNamespace(os="mobile", status=SimpleNamespace(value="idle"),
                                      capabilities=["mobile_touch", "mobile_apps"],
                                      metadata={"system_info": {"platform": "mobile", "platform_type": "mobile"}})
            client = Mock(initialize=AsyncMock(), shutdown=AsyncMock(),
                          process_request=AsyncMock(return_value={"session_results": {"status": "FINISH"}}))
            client._client.device_manager.device_registry.get_device.return_value = profile
            client._client.device_manager.get_task_queue_status.return_value = {"is_busy": False, "pending_task_ids": [], "queued_task_ids": []}
            task = {"status": "completed", "result": {"status": "completed"}}
            client._session.current_constellation.to_dict.return_value = {"tasks": {"task-1": task}}
            settings = {"run_id": "offline", "serial": "phone", "device": "mobile_1", "case": "open_camera",
                        "request": CASES["open_camera"].make_request()}
            module = SimpleNamespace(GalaxyClient=Mock(return_value=client))
            with patch.dict(sys.modules, {"galaxy.galaxy_client": module}), patch.dict("os.environ"), \
                    patch.object(galaxy_worker, "start_local", new=AsyncMock(return_value=SimpleNamespace(device_id="mobile_1"))):
                asyncio.run(galaxy_worker.execute(settings, Path(directory), ""))
            client.process_request.assert_awaited_once_with(settings["request"])
            result = json.loads((Path(directory) / "execution.json").read_text())
            self.assertEqual(result["status"], "completed")
            self.assertTrue((Path(directory) / "submission.json").exists())


if __name__ == "__main__":
    unittest.main()
