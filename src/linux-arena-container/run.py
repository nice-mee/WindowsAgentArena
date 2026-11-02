#!/usr/bin/env python3
"""Initialize one local case, run Galaxy, check actual output, and clean materials."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid

from cases import CASES, HERE, check_answer, make_request


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def group_running(group):
    # Exclude zombies: they cannot execute tools and may await reaping by PID 1.
    for entry in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = entry.read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == group and fields[0] != "Z":
                return True
        except (FileNotFoundError, ProcessLookupError):
            continue
    return False


def stop_group(process):
    """Stop this run's worker/services/tools, never a pre-existing service."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            process.poll()
            if not group_running(process.pid):
                return True
            time.sleep(0.1)
    process.wait(timeout=3)
    return not group_running(process.pid)


def collect_traces(ufo_root, run_id, run_dir):
    sources = sorted((ufo_root / "logs").glob(f"galaxy_{run_id}_*/response.log"))
    galaxy_log = ufo_root / "logs" / "galaxy" / run_id / "response.log"
    if galaxy_log.exists():
        sources.append(galaxy_log)
    copies = []
    for source in sources:
        target = run_dir / "traces" / source.parent.name / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copies.append({"source": str(source), "copy": str(target), "device": source != galaxy_log})
    return copies


def check_reads(traces, materials, filenames):
    """Require content-bearing MCP results for this run's material paths."""
    read_files, calls, errors = set(), [], []
    for trace in traces:
        if not trace["device"]:
            continue
        path = Path(trace["copy"])
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                for action in record.get("action", []):
                    if action.get("function", "").split("/")[-1] != "execute_command":
                        continue
                    arguments = action["arguments"]
                    tokens = shlex.split(arguments.get("command", ""))
                    payload = action.get("result", {}).get("result", {})
                    call = {"log": str(path), "line": line_number,
                            "command": arguments.get("command"), "cwd": arguments.get("cwd"),
                            "exit_code": payload.get("exit_code"), "files": []}
                    calls.append(call)
                    if not tokens or not payload.get("stdout"):
                        continue
                    tool = Path(tokens[0]).name
                    valid = (tool in {"cat", "head", "tail", "grep", "cut", "more", "less"}
                             and payload.get("success") is True and payload.get("exit_code") == 0)
                    valid |= tool == "diff" and payload.get("exit_code") in {0, 1}
                    if not valid:
                        continue
                    for token in tokens[1:]:
                        candidate = Path(token)
                        if not candidate.is_absolute():
                            # No guessed cwd: absent cwd requires an absolute operand.
                            if not arguments.get("cwd"):
                                continue
                            candidate = Path(arguments["cwd"]) / candidate
                        for filename in filenames:
                            if candidate.resolve() == materials / filename:
                                read_files.add(filename)
                                call["files"].append(filename)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                errors.append(f"{path}:{line_number}: {exc}")
    return {"passed": set(filenames) <= read_files and not errors,
            "files_read": sorted(read_files), "missing": sorted(set(filenames) - read_files),
            "calls": calls, "errors": errors}


def final_answer(execution, device):
    tasks = execution.get("tasks", {})
    if not tasks or any(t.get("target_device_id") != device for t in tasks.values()):
        raise ValueError("Missing tasks or unexpected target device")
    sinks = [t for t in tasks.values() if not t.get("dependents")]
    if len(sinks) != 1:
        raise ValueError("Expected one final device result; ambiguous or missing terminal task")
    task = sinks[0]
    result = task.get("result") or {}
    if task.get("status") != "completed" or result.get("status") != "completed":
        raise ValueError("Final device task did not complete")
    rounds = result.get("result")
    if not isinstance(rounds, list) or not rounds or "result" not in rounds[-1]:
        raise ValueError("Final device task has no round result")
    return rounds[-1]["result"]


def redact_logs(run_dir):
    # UFO's server prints its local auth token at startup. Do not retain it.
    for path in run_dir.rglob("*.log"):
        text = path.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"(UFO Server API key:\s*)\S+", r"\1<redacted>", text)
        text = re.sub(r"([?&]token=)[^\s&\"'<>]+", r"\1<redacted>", text)
        path.write_text(text, encoding="utf-8")


def run(args):
    started = time.monotonic()
    run_id = "arena-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_dir = args.output / run_id
    materials = run_dir / "materials"
    materials.mkdir(parents=True)
    summary = {"case_id": args.case, "run_id": run_id,
               "started_at": datetime.now(timezone.utc).isoformat(),
               "device": args.device, "local_services": args.local_services,
               "initialization": {"status": "not_started"},
               "execution": {"status": "not_started"},
               "verification": {"status": "not_run"}, "cleanup": {"status": "pending"},
               "status": "running", "errors": [], "run_dir": str(run_dir)}
    save(run_dir / "result.json", summary)
    process, group_stopped, submitted, timed_out = None, True, False, False
    print(f"运行 {args.case}: {run_id}\n结果目录: {run_dir}", flush=True)
    hashes = {}
    try:
        for name in CASES[args.case]["files"]:
            source = HERE / "fixtures" / args.case / name
            shutil.copyfile(source, materials / name)
            hashes[name] = digest(source)
            if digest(materials / name) != hashes[name]:
                raise RuntimeError(f"Material initialization mismatch: {name}")
        save(run_dir / "materials.json", {"directory": str(materials), "sha256": hashes})
        request = make_request(args.case, run_id, materials, args.device)
        save(run_dir / "request.json", {"run_id": run_id, "request": request,
                                      "ufo_root": str(args.ufo_root), "device": args.device,
                                      "local_services": args.local_services})
        with (run_dir / "galaxy.log").open("w") as log:
            process = subprocess.Popen([sys.executable, "-u", str(HERE / "galaxy_worker.py"), str(run_dir)],
                                       cwd=args.ufo_root, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            submitted, group_stopped = True, False
            try:
                process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                summary["errors"].append(f"Wall-clock deadline exceeded: {args.timeout}s")
    except KeyboardInterrupt:
        summary["status"] = "interrupted"
        summary["errors"].append("Interrupted by user")
    except Exception as exc:
        summary["errors"].append(str(exc))
    finally:
        if process is not None:
            summary["process_group"] = process.pid
            try:
                group_stopped = stop_group(process)
            except OSError as exc:
                summary["errors"].append(f"Failed to stop owned process group: {exc}")

    try:
        initialization = read_json(run_dir / "initialization.json", {"status": "failed", "error": "Worker did not finish initialization"})
        execution = read_json(run_dir / "execution.json", {"status": "not_started"})
        summary["initialization"] = initialization
        summary["execution"] = {k: v for k, v in execution.items() if k not in {"galaxy", "tasks"}}
        summary["execution"]["worker_exit_code"] = process.returncode if process else None
        if summary["status"] != "interrupted":
            if timed_out:
                summary["status"] = "timeout"
                summary["execution"]["status"] = "timeout" if initialization["status"] == "passed" else "not_started"
            elif initialization["status"] != "passed":
                summary["status"] = "initialization_failed"
            elif execution.get("status") != "completed" or process.returncode != 0:
                summary["status"] = "execution_failed"
            else:
                summary["status"] = "verification_failed"
        stopped = group_stopped and (args.local_services or execution.get("device_stopped_confirmed") is True or not submitted or initialization["status"] != "passed")
        summary["device_operations_stopped"] = bool(stopped)
        if stopped:
            summary["traces"] = collect_traces(args.ufo_root, run_id, run_dir)
            if summary["status"] == "verification_failed":
                trace = check_reads(summary["traces"], materials, CASES[args.case]["files"])
                unchanged = all((materials / name).is_file() and digest(materials / name) == value
                                for name, value in hashes.items())
                try:
                    raw = final_answer(execution, args.device)
                    save(run_dir / "answer.json", {"source": "final device task result", "raw": raw})
                    answer = check_answer(args.case, run_id, raw)
                except ValueError as exc:
                    answer = {"passed": False, "error": str(exc)}
                passed = trace["passed"] and answer["passed"] and unchanged
                summary["verification"] = {"status": "passed" if passed else "failed",
                                           "answer": answer, "trace": trace, "materials_unchanged": unchanged}
                summary["status"] = "passed" if passed else "verification_failed"
        else:
            summary["errors"].append("Device stop unconfirmed; verification skipped and materials retained")
    except Exception as exc:
        summary["status"] = "verification_error"
        summary["errors"].append(str(exc))
    finally:
        if summary.get("device_operations_stopped"):
            try:
                shutil.rmtree(materials)
                summary["cleanup"] = {"status": "completed", "removed": str(materials)}
            except OSError as exc:
                summary["cleanup"] = {"status": "failed", "error": str(exc)}
                summary["status"] = "cleanup_failed"
        else:
            summary["cleanup"] = {"status": "retained", "directory": str(materials)}
        summary["elapsed_seconds"] = round(time.monotonic() - started, 3)
        for phase in ("initialization", "execution"):
            if summary[phase].get("error"):
                summary["errors"].append(summary[phase]["error"])
        save(run_dir / "result.json", summary)
        redact_logs(run_dir)
    print(f"结果: {summary['status']}，清理: {summary['cleanup']['status']}\n{run_dir / 'result.json'}", flush=True)
    return 0 if summary["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--device", default="linux_device_1")
    parser.add_argument("--ufo-root", type=Path, default=HERE.parents[2] / "UFO3")
    parser.add_argument("--output", type=Path, default=HERE / "runs")
    parser.add_argument("--timeout", type=float, default=600, help="Total wall-clock seconds including startup")
    parser.add_argument("--local-services", action="store_true", help="Start temporary local MCP/server/client using existing model configuration")
    args = parser.parse_args()
    args.ufo_root, args.output = args.ufo_root.resolve(), args.output.resolve()
    if not math.isfinite(args.timeout) or args.timeout <= 0 or not (args.ufo_root / "galaxy/galaxy_client.py").is_file():
        parser.error("Require a positive timeout and a valid UFO3 root")
    # This is deliberately one serial local arena, not a general device scheduler.
    (HERE / "runs").mkdir(exist_ok=True)
    with (HERE / "runs" / ".lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another Linux arena case is running")
        return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
