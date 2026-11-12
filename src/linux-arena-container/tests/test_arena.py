"""Offline regression and adversarial evidence checks, never model execution."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import batch
from cases import CASES, config, logs, php_line_count
from cases.common import judge_structured
import prepare_assets
import review
import run
from verify import check_reads, final_answer


class ArenaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def trace(self, work, names, command="wc -l", stdout="54 total\n", status="FINISH"):
        path = self.root / "response.log"
        path.write_text(json.dumps({"status": status, "action": [
            {"function": "BashExecutor/execute_command",
             "arguments": {"command": command + " " + " ".join(names), "cwd": str(work)},
             "result": {"result": {"success": True, "exit_code": 0, "stdout": stdout}}}]}))
        return [{"device": True, "copy": str(path)}]

    def args(self, local=False):
        return argparse.Namespace(case="php_line_count", device="linux_device_1", local_services=local,
                                  output=self.root / "runs", ufo_root=self.root / "ufo", timeout=0.01)

    def test_registry_setup_and_natural_requests(self):
        for case in CASES.values():
            work = self.root / case.ID
            work.mkdir()
            state = case.setup(work)
            self.assertTrue(state["sha256"])
            request = case.make_request(work)
            for forbidden in ["run_id", "Galaxy", "LinuxAgent", "MCP", "JSON", "字段", "工具"]:
                self.assertNotIn(forbidden, request)
        state = php_line_count.setup(self.root / "php_second_setup")
        self.assertEqual(state["expected_total"], 54)
        self.assertEqual(len(state["line_counts"]), 4)

    def test_existing_case_correct_and_wrong_structured_answers(self):
        for case in (logs, config):
            self.assertEqual(judge_structured(case.EXPECTED, case.EXPECTED)["status"], "passed")
            wrong = json.loads(json.dumps(case.EXPECTED))
            if case is logs:
                wrong["error_count"] = True
            else:
                wrong["changes"]["timeout"]["after"] = "61"
            self.assertEqual(judge_structured(wrong, case.EXPECTED)["status"], "failed")
            self.assertEqual(judge_structured("完成", case.EXPECTED)["status"], "review_required")
            self.assertEqual(judge_structured(None, case.EXPECTED)["status"], "failed")

    def test_php_count_does_not_search_for_expected_number(self):
        for expected in (54, 127):
            for raw in (str(expected), f"共 {expected} 行。", {"total_lines": expected},
                        f"4 个 PHP 文件，总行数为 {expected} 行。\nindex.php: 8 行\n总计：{expected} 行。"):
                self.assertEqual(php_line_count.judge_answer(raw, expected)["status"], "passed")
            self.assertEqual(php_line_count.judge_answer(f"总行数为 {expected + 1} 行", expected)["status"], "failed")
        for raw in ("完成", "文件 php54.php 有 8 行", "例如，总行数为 54 行。", "总行数为 54 行，但不是最终结果。",
                    "总行数为 54 行。总计 55 行。", "如果总行数为 54 行就完成了", {"total_lines": 54, "note": "not verified"}):
            self.assertEqual(php_line_count.judge_answer(raw, 54)["status"], "review_required")
        self.assertEqual(php_line_count.judge_answer(None, 54)["status"], "failed")

    def test_missing_nested_file_wrong_answer_and_modified_input_fail(self):
        work = self.root / "work"
        work.mkdir()
        state = php_line_count.setup(work)
        answers = {"device_results": [{"result": "54 行"}]}
        names = list(state["sha256"])
        trace = self.trace(work, names)
        self.assertEqual(php_line_count.verify(work, state, answers, trace)["status"], "passed")
        trace = self.trace(work, names[:1])
        self.assertEqual(php_line_count.verify(work, state, answers, trace)["status"], "failed")
        trace = self.trace(work, names)
        answers["device_results"][0]["result"] = "8 行"
        self.assertEqual(php_line_count.verify(work, state, answers, trace)["status"], "failed")
        answers["device_results"][0]["result"] = "54 行"
        (work / names[-1]).write_bytes(b"")
        self.assertEqual(php_line_count.verify(work, state, answers, trace)["status"], "failed")

    def test_trace_rejects_empty_output_wrong_run_byte_counts_and_failed_agent(self):
        work = self.root / "work"
        work.mkdir()
        for command, stdout, status in [("wc -c", "54 total", "FINISH"), ("wc -l", "", "FINISH"), ("wc -l", "54 total", "FAIL")]:
            traces = self.trace(work, ["file.php"], command, stdout, status)
            self.assertFalse(check_reads(traces, work, ["file.php"])["passed"])
        trace = self.trace(work, [str(self.root / "other/file.php")])
        self.assertFalse(check_reads(trace, work, ["file.php"])["passed"])
        self.assertFalse(check_reads([], work, ["file.php"])["passed"])

    def test_final_answer_reads_results_only_and_keeps_multiple_sinks(self):
        task = {"target_device_id": "d", "dependents": [], "status": "completed",
                "result": {"status": "completed", "result": [{"request": "expected=54", "result": "8 行"}]}}
        value = final_answer({"tasks": {"a": task, "b": task}}, "d")
        self.assertEqual(len(value["device_results"]), 2)
        self.assertNotIn("expected", json.dumps(value))
        with self.assertRaises(ValueError):
            final_answer({"tasks": {"a": task}}, "other")

    def test_assets_never_download_during_check_or_repair_bad_files(self):
        entry = {"path": "input", "sha256": "wrong", "size": 1, "url": "https://example.invalid/file"}
        with patch.object(prepare_assets, "urlopen") as network:
            self.assertTrue(prepare_assets.prepare([entry], self.root, check_only=True))
            (self.root / "input").write_bytes(b"x")
            self.assertTrue(prepare_assets.prepare([entry], self.root))
            network.assert_not_called()
        (self.root / "link").symlink_to(self.root / "input")
        with self.assertRaises(ValueError):
            prepare_assets.asset_path(self.root, "link")

    def test_setup_failure_does_not_submit(self):
        with patch.object(php_line_count, "setup", side_effect=ValueError("Missing fixture")), patch.object(run.subprocess, "Popen") as launch:
            result = run.run_case(self.args())
        launch.assert_not_called()
        self.assertEqual(result["status"], "initialization_failed")
        self.assertIn("Missing fixture", result["initialization"]["error"])
        self.assertTrue(result["device_operations_stopped"])

    def test_remote_timeout_retains_scene_and_skips_verification(self):
        def launch(command, **kwargs):
            directory = Path(command[-1])
            run.save(directory / "initialization.json", {"status": "passed"})
            run.save(directory / "submission.json", {"status": "submitting"})
            return Mock(pid=1234, returncode=-15, wait=Mock(side_effect=subprocess.TimeoutExpired(command, 0.01)))
        with patch.object(run.subprocess, "Popen", side_effect=launch), patch.object(run, "stop_group", return_value=True):
            result = run.run_case(self.args(local=False))
        self.assertEqual(result["status"], "timeout")
        self.assertFalse(result["device_operations_stopped"])
        self.assertEqual(result["verification"]["status"], "not_run")
        self.assertTrue((Path(result["run_dir"]) / "materials").is_dir())

    def test_verifier_exception_is_not_an_incorrect_model_answer(self):
        def launch(command, **kwargs):
            directory = Path(command[-1])
            run.save(directory / "initialization.json", {"status": "passed"})
            run.save(directory / "submission.json", {"status": "submitting"})
            task = {"target_device_id": "linux_device_1", "status": "completed", "dependents": [],
                    "result": {"status": "completed", "result": [{"result": "54 行"}]}}
            run.save(directory / "execution.json", {"status": "completed", "device_stopped_confirmed": True, "tasks": {"t": task}})
            return Mock(pid=1234, returncode=0)
        with patch.object(run.subprocess, "Popen", side_effect=launch), patch.object(run, "stop_group", return_value=True), patch.object(php_line_count, "verify", side_effect=ValueError("Broken verifier")):
            result = run.run_case(self.args(local=True))
        self.assertEqual(result["status"], "verification_error")
        self.assertEqual(result["cleanup"]["status"], "completed")
        self.assertIn("Broken verifier", result["errors"])

    def test_stop_also_terminates_command_in_separate_session(self):
        code = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True); print(p.pid,flush=True); time.sleep(60)"
        process = subprocess.Popen([sys.executable, "-u", "-c", code], start_new_session=True, stdout=subprocess.PIPE, text=True)
        self.addCleanup(process.stdout.close)
        try:
            child = int(process.stdout.readline())
            self.assertTrue(run.stop_group(process))
            self.assertFalse(run.group_running(child))
        finally:
            run.stop_group(process)
            process.wait(timeout=3)

    def test_batch_keeps_all_planned_cases_and_stops_on_unconfirmed_device(self):
        suite = {"name": "test", "cases": [{"id": "php_line_count", "mode": "cli"},
                 {"id": "logs", "mode": "cli"}, {"id": "replace_text", "mode": "gui", "enabled": False, "reason": "No GUI tools"}]}
        runner = Mock(return_value={"status": "timeout", "device_operations_stopped": False, "run_id": "r", "run_dir": str(self.root)})
        result = batch.execute_suite(suite, self.args(), self.root, runner)
        self.assertEqual(runner.call_count, 1)
        self.assertEqual([r["status"] for r in result["cases"]], ["timeout", "not_executed", "not_executed"])
        self.assertEqual(result["by_mode"]["gui"]["not_executed"], 1)

    def test_batch_does_not_retry_failure_or_treat_review_as_pass(self):
        suite = {"name": "test", "cases": [{"id": "logs", "mode": "cli"}, {"id": "config", "mode": "cli"}]}
        runner = Mock(side_effect=[{"status": status, "device_operations_stopped": True, "run_id": str(i), "run_dir": str(self.root)}
                                   for i, status in enumerate(["verification_failed", "review_required"])])
        result = batch.execute_suite(suite, self.args(), self.root, runner)
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(result["by_mode"]["cli"]["passed"], 0)
        self.assertIsNone(result["stop_reason"])

    def test_human_review_cannot_upgrade_failed_execution(self):
        run.save(self.root / "result.json", {"status": "execution_failed", "verification": {"status": "not_run"}})
        with self.assertRaises(ValueError):
            review.record_review(self.root, "pass", "Model says completed")
        with self.assertRaises(ValueError):
            review.record_review(self.root, "arbitrary", "note")


if __name__ == "__main__":
    unittest.main()
