#!/usr/bin/env python3
"""Initialize one local case, run Galaxy, check actual output, and clean materials."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

from cases import CASES, HERE
from desktop import open_application
from verify import final_answer


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


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
    """Stop owned descendants too: Linux MCP commands create separate sessions."""
    owned = {}

    def descendants():
        table = {}
        for path in Path("/proc").glob("[0-9]*/stat"):
            try:
                fields = path.read_text().rsplit(")", 1)[1].split()
                table[int(path.parent.name)] = (fields[0], int(fields[1]), int(fields[2]), fields[19])
            except (FileNotFoundError, ProcessLookupError):
                continue
        changed = True
        while changed:
            changed = False
            for pid, (state, parent, group, birth) in table.items():
                parent_owned = parent in owned and parent in table and table[parent][3] == owned[parent]
                if pid not in owned and (pid == process.pid or group == process.pid or parent_owned):
                    owned[pid] = birth
                    changed = True
        return {pid for pid, birth in owned.items() if pid in table and table[pid][3] == birth and table[pid][0] != "Z"}

    descendants()
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        for pid in descendants():
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            process.poll()
            if not descendants():
                return True
            time.sleep(0.1)
    process.wait(timeout=3)
    return not descendants()


def collect_traces(ufo_root, run_id, run_dir):
    # Keep the original per-step observations, including a last capture whose
    # model call failed before response.log received a record. Never redraw them.
    for directory in sorted((ufo_root / "logs").glob(f"galaxy_{run_id}_*")):
        if not directory.is_dir():
            continue
        for pattern in ("action_step*.png", "action_step*_ui.json"):
            for source in sorted(directory.glob(pattern)):
                target = run_dir / "traces" / directory.name / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

    # The verifier consumes only response logs; screenshots remain beside them.
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



def redact_logs(run_dir):
    # UFO's server prints its local auth token at startup. Do not retain it.
    for path in run_dir.rglob("*.log"):
        text = path.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"(UFO Server API key:\s*)\S+", r"\1<redacted>", text)
        text = re.sub(r"([?&]token=)[^\s&\"'<>]+", r"\1<redacted>", text)
        path.write_text(text, encoding="utf-8")


def run_case(args):
    started = time.monotonic()
    case = CASES[args.case]
    run_id = "arena-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_dir = args.output / run_id
    materials = run_dir / "materials"
    materials.mkdir(parents=True)
    summary = {"case_id": args.case, "run_id": run_id, "case_version": case.VERSION,
               "difficulty": case.DIFFICULTY,
               "request_version": getattr(case, "REQUEST_VERSION", case.VERSION), "verifier_version": case.VERSION, "mode": case.MODE,
               "started_at": datetime.now(timezone.utc).isoformat(),
               "device": args.device, "local_services": args.local_services,
               "initialization": {"status": "not_started"},
               "execution": {"status": "not_started"},
               "verification": {"status": "not_run"}, "cleanup": {"status": "pending"},
               "status": "running", "errors": [], "run_dir": str(run_dir)}
    save(run_dir / "result.json", summary)
    process, group_stopped, submitted, timed_out = None, True, False, False
    applications = []
    print(f"运行 {args.case}: {run_id}\n结果目录: {run_dir}", flush=True)
    state = {}
    try:
        state = case.setup(materials)
        save(run_dir / "materials.json", state)
        launches = getattr(case, "APPLICATIONS", [])
        if hasattr(case, "APPLICATION"):
            launches = [(case.APPLICATION, case.FILENAME)]
        for app, filename in launches:
            application = open_application(app, materials / filename, run_dir)
            applications.append(application)
            time.sleep(2)
            if application.poll() not in (None, 0):
                raise RuntimeError(f"Application startup failed; see application-{app}.log")
        request = case.make_request(materials)
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
        if not submitted:
            save(run_dir / "initialization.json", {"status": "failed", "error": str(exc)})
    finally:
        if process is not None:
            summary["process_group"] = process.pid
            try:
                group_stopped = stop_group(process)
            except (OSError, subprocess.TimeoutExpired) as exc:
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
        # The worker writes the submission marker before calling Galaxy. Failure
        # to persist a later initialization record cannot prove a remote stop.
        dispatched = (run_dir / "submission.json").exists()
        stopped = group_stopped and (args.local_services or execution.get("device_stopped_confirmed") is True or not dispatched)
        summary["device_operations_stopped"] = bool(stopped)
        if stopped:
            summary["traces"] = collect_traces(args.ufo_root, run_id, run_dir)
            if summary["status"] == "verification_failed":
                try:
                    raw = final_answer(execution, args.device)
                    save(run_dir / "answer.json", {"source": "final device task result", "raw": raw})
                except ValueError as exc:
                    if getattr(case, "ARTIFACT", False):
                        summary["verification"] = case.verify(materials, state, {}, summary["traces"])
                    else:
                        summary["verification"] = {"status": "failed", "error": str(exc)}
                else:
                    summary["verification"] = case.verify(materials, state, raw, summary["traces"])
                status = summary["verification"]["status"]
                summary["status"] = {"passed": "passed", "failed": "verification_failed",
                                     "review_required": "review_required"}[status]
        else:
            if summary["status"] == "verification_failed":
                summary["status"] = "execution_failed"
                summary["execution"]["status"] = "stop_unconfirmed"
            summary["errors"].append("Device stop unconfirmed; verification skipped and materials retained")
    except Exception as exc:
        summary["status"] = "verification_error"
        summary["errors"].append(str(exc))
    finally:
        if summary.get("device_operations_stopped"):
            try:
                stopped_apps = [stop_group(app) for app in reversed(applications)]
                if not all(stopped_apps):
                    raise OSError("Application did not stop; retaining its files")
                if hasattr(case, "cleanup"):
                    case.cleanup(materials, state)
                # Preserve the saved task files before removing this run's scene.
                if state and not any(p.is_symlink() for p in materials.rglob("*")):
                    shutil.copytree(materials, run_dir / "evidence/materials")
                shutil.rmtree(materials)
                profile = run_dir / "application-profile"
                if profile.exists():
                    shutil.rmtree(profile)
                summary["cleanup"] = {"status": "completed", "removed": str(materials)}
            except (OSError, subprocess.TimeoutExpired) as exc:
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
    return summary


def exit_code(summary):
    return 0 if summary["status"] == "passed" else 3 if summary["status"] == "review_required" else 1


def run(args):
    return exit_code(run_case(args))


def interrupt_handler(signum, frame):
    # Permit the bounded cleanup to finish after the first interrupt.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise KeyboardInterrupt(f"Received signal {signum}")


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
        signal.signal(signal.SIGINT, interrupt_handler)
        signal.signal(signal.SIGTERM, interrupt_handler)
        return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
