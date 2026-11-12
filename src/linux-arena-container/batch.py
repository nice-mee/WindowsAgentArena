#!/usr/bin/env python3
"""Run Linux's fifteen-case suite serially; use --suite to select a subset."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
import math
from pathlib import Path
import signal
from types import SimpleNamespace
import uuid

from cases import CASES, HERE
from run import run_case, save, interrupt_handler

STATUSES = ("passed", "initialization_failed", "execution_failed", "verification_failed",
            "timeout", "verification_error", "review_required", "not_executed",
            "interrupted", "cleanup_failed", "running")


def load_suite(path):
    suite = json.loads(path.read_text())
    seen = set()
    for item in suite["cases"]:
        if item["id"] in seen or item["mode"] not in {"cli", "gui"}:
            raise ValueError("Duplicate case or invalid interaction mode in suite")
        seen.add(item["id"])
        if item.get("enabled", True):
            if item["id"] not in CASES or CASES[item["id"]].MODE != item["mode"]:
                raise ValueError(f"Enabled case has no matching implementation: {item['id']}")
        elif not item.get("reason"):
            raise ValueError("A deferred case must explain why it is not executed")
        if item["id"] in CASES:
            # Keep ratings in case modules; expose them in --list and suite.json.
            item["difficulty"] = CASES[item["id"]].DIFFICULTY
    if not seen:
        raise ValueError("Empty suite")
    return suite


def summarize(rows):
    return {mode: {status: sum(row["mode"] == mode and row["status"] == status for row in rows)
                   for status in STATUSES} for mode in ("cli", "gui")}


def execute_suite(suite, args, directory, runner=run_case):
    rows = [{"case_id": item["id"], "mode": item["mode"], "status": "not_executed",
             "difficulty": getattr(CASES.get(item["id"]), "DIFFICULTY", None),
             "reason": item.get("reason", "Not reached yet")} for item in suite["cases"]]
    summary = {"suite": suite["name"], "started_at": datetime.now(timezone.utc).isoformat(),
               "cases": rows, "stop_reason": None}

    def persist():
        summary["counts"] = dict(Counter(row["status"] for row in rows))
        summary["by_mode"] = summarize(rows)
        save(directory / "summary.json", summary)

    persist()
    for item, row in zip(suite["cases"], rows):
        if summary["stop_reason"]:
            row["reason"] = summary["stop_reason"]
            continue
        if not item.get("enabled", True):
            continue
        case_args = SimpleNamespace(**vars(args))
        case_args.case = item["id"]
        case_args.output = directory / "runs"
        row.update(status="running", reason="Running once; no automatic retry")
        persist()
        try:
            result = runner(case_args)
        except (Exception, KeyboardInterrupt) as exc:
            # An unexpected runner crash provides no evidence of device stop.
            row.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "verification_error",
                       reason=f"Runner aborted: {type(exc).__name__}: {exc}")
            summary["stop_reason"] = "Runner aborted; device stop unconfirmed"
            persist()
            continue
        row.update(status=result["status"], run_id=result["run_id"],
                   result=str(Path(result["run_dir"]) / "result.json"))
        row.pop("reason", None)
        if result.get("device_operations_stopped") is not True:
            summary["stop_reason"] = "Device stop unconfirmed; remaining cases not executed"
        elif result["status"] in {"interrupted", "cleanup_failed"}:
            summary["stop_reason"] = "Run interrupted or cleanup failed; remaining cases not executed"
        persist()
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    persist()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=HERE / "suites/linux15.json",
                        help="Suite file (default: suites/linux15.json, all 15 cases)")
    parser.add_argument("--device", default="linux_device_1")
    parser.add_argument("--ufo-root", type=Path, default=HERE.parents[2] / "UFO3")
    parser.add_argument("--output", type=Path, default=HERE / "runs")
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--local-services", action="store_true")
    parser.add_argument("--list", action="store_true", help="List case IDs, modes and difficulties without submitting tasks")
    args = parser.parse_args()
    args.ufo_root, args.output = args.ufo_root.resolve(), args.output.resolve()
    try:
        suite = load_suite(args.suite)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    if args.list:
        print(json.dumps(suite, ensure_ascii=False, indent=2))
        return 0
    if not math.isfinite(args.timeout) or args.timeout <= 0 or not (args.ufo_root / "galaxy/galaxy_client.py").is_file():
        parser.error("Require a positive timeout and a valid UFO3 root")
    (HERE / "runs").mkdir(exist_ok=True)
    with (HERE / "runs/.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another Linux arena case/batch is running")
        directory = args.output / ("batch-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
        directory.mkdir(parents=True)
        save(directory / "suite.json", suite)
        signal.signal(signal.SIGINT, interrupt_handler)
        signal.signal(signal.SIGTERM, interrupt_handler)
        result = execute_suite(suite, args, directory)
    print(f"Batch summary: {directory / 'summary.json'}")
    return 0 if all(row["status"] == "passed" for row in result["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
