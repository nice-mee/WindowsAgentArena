"""Offline batch checks; no phone or model calls."""
import argparse
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import batch
from cases import CASES


class MobileBatchTests(unittest.TestCase):
    def test_runs_in_explicit_order_preserves_review_and_unselected_cases(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            args = argparse.Namespace(case=["unlock", "weather"], output=directory)
            def fake_runner(args):
                path = args.output / "run1"
                path.mkdir(parents=True)
                (path / "result.json").write_text(json.dumps({"status": "review_required", "run_id": "run1", "device_operations_stopped": True}))
            runner = Mock(side_effect=fake_runner)
            result = batch.execute_batch(args, directory, runner)
            self.assertEqual([call.args[0].case for call in runner.call_args_list], ["unlock", "weather"])
            self.assertEqual(result["counts"], {"not_executed": len(CASES) - 2, "review_required": 2})
            self.assertIsNone(result["stop_reason"])

    def test_does_not_advance_after_unconfirmed_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            args = argparse.Namespace(case=["weather", "wechat"], output=directory)
            def fake_runner(args):
                path = args.output / "run1"
                path.mkdir(parents=True)
                (path / "result.json").write_text(json.dumps({"status": "timeout", "run_id": "run1", "device_operations_stopped": False}))
            runner = Mock(side_effect=fake_runner)
            result = batch.execute_batch(args, directory, runner)
            self.assertEqual(runner.call_count, 1)
            self.assertEqual(result["counts"], {"not_executed": len(CASES) - 1, "timeout": 1})


if __name__ == "__main__":
    unittest.main()
