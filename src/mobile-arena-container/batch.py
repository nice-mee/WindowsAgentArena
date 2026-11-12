#!/usr/bin/env python3
"""One-command Galaxy evaluation of a fixed Mobile suite, without retries."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

from cases import CASES
from phone import save
from run import HERE, run


def load_suite(path):
    suite = json.loads(path.read_text())
    selected = suite["cases"]
    if not selected or len(set(selected)) != len(selected) or any(case not in CASES for case in selected):
        raise ValueError("Suite must contain unique registered case IDs")
    return suite


def execute_batch(args, directory, runner=run):
    selected = list(args.case)
    serial = getattr(args, "serial", None)
    rows = [{"case_id": case, "mode": "mobile_gui", "status": "not_executed",
             "reason": "Not selected" if case not in selected else "Not reached yet"} for case in CASES]
    result = {"name": getattr(args, "suite_name", "mobile-selected"), "order": selected, "cases": rows, "stop_reason": None,
              "started_at": datetime.now(timezone.utc).isoformat()}

    def persist():
        result["counts"] = dict(Counter(row["status"] for row in rows))
        result["selected_counts"] = dict(Counter(row["status"] for row in rows if row["case_id"] in selected))
        save(directory / "summary.json", result)

    persist()
    for case in selected:
        row = next(r for r in rows if r["case_id"] == case)
        if result["stop_reason"]:
            row["reason"] = result["stop_reason"]
            continue
        case_args = SimpleNamespace(**vars(args))
        case_args.case, case_args.probe = case, False
        case_args.serial = serial
        case_args.output = directory / case
        row.update(status="running", reason="Running once; no automatic retry")
        persist()
        try:
            runner(case_args)
            paths = list(case_args.output.glob("*/result.json"))
            if len(paths) != 1:
                raise ValueError("Expected exactly one result from the selected case")
            record = json.loads(paths[0].read_text())
            serial = serial or record.get("serial")
            row.update(status=record["status"], result=str(paths[0]), run_id=record["run_id"])
            row.pop("reason", None)
            if record.get("device_operations_stopped") is not True:
                result["stop_reason"] = "Device stop unconfirmed; remaining selected cases not executed"
            elif record["status"] in {"interrupted", "cleanup_failed"}:
                result["stop_reason"] = "Interrupted or cleanup failed; remaining selected cases not executed"
            elif record["status"] == "initialization_failed" and not record.get("serial"):
                result["stop_reason"] = "Phone preflight failed; remaining selected cases not executed"
        except (Exception, KeyboardInterrupt) as exc:
            row.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "verification_error",
                       reason=f"Runner aborted: {type(exc).__name__}: {exc}")
            result["stop_reason"] = "Runner aborted; device stop unconfirmed"
        persist()
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    persist()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--case", choices=CASES, action="append",
                           help="Run selected cases in order; wechat sends a real message to Flint")
    selection.add_argument("--suite", type=Path, help="Default: suites/mobile_mvp.json (9 new cases)")
    parser.add_argument("--list", action="store_true", help="Show selected cases and natural requests without ADB or model calls")
    parser.add_argument("--serial")
    parser.add_argument("--device", default="mobile_device_1")
    parser.add_argument("--local-services", action="store_true")
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--ufo-root", type=Path, default=HERE.parents[2] / "UFO3")
    parser.add_argument("--output", type=Path, default=HERE / "runs")
    args = parser.parse_args()
    if args.case:
        suite = {"name": "mobile-selected", "cases": args.case}
    else:
        try:
            suite = load_suite(args.suite or HERE / "suites/mobile_mvp.json")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parser.error(str(exc))
        args.case = suite["cases"]
    args.suite_name = suite["name"]
    args.output, args.ufo_root = args.output.resolve(), args.ufo_root.resolve()
    if len(set(args.case)) != len(args.case):
        parser.error("Duplicate cases are not allowed; each case runs at most once")
    if args.list:
        print(json.dumps({"name": suite["name"], "cases": [
            {"id": name, "request": CASES[name].make_request()} for name in args.case]}, ensure_ascii=False, indent=2))
        return 0
    if not math.isfinite(args.timeout) or args.timeout <= 0 or not (args.ufo_root / "galaxy/galaxy_client.py").is_file():
        parser.error("Require a positive timeout and valid UFO3 root")
    os.umask(0o077)
    (HERE / "runs").mkdir(exist_ok=True)
    with (HERE / "runs/.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another Mobile arena case/batch is active")
        directory = args.output / ("batch-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
        directory.mkdir(parents=True, mode=0o700)
        save(directory / "suite.json", suite)
        result = execute_batch(args, directory)
    print(f"Batch summary: {directory / 'summary.json'}")
    return 0 if all(row["status"] == "passed" for row in result["cases"] if row["case_id"] in args.case) else 1


if __name__ == "__main__":
    raise SystemExit(main())
