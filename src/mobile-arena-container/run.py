#!/usr/bin/env python3
"""Run one Galaxy -> MobileAgent -> Mobile MCP case on a physical Android phone."""
import argparse
from datetime import datetime, timezone
import fcntl
import getpass
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

from cases import CASES, make_request, task_context
from runtime import group_running, stop_group, runtime_directory, redact_logs
from phone import preflight, save, snapshot
from verify import action_evidence, evaluate, final_answer

HERE = Path(__file__).resolve().parent


class RunFinished(Exception):
    """Leave the execution phase while still finalizing the recorded result."""


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def run(args):
    started = time.monotonic()
    case = CASES.get(args.case)
    run_id = "mobile-arena-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    run_dir = args.output / run_id
    run_dir.mkdir(parents=True, mode=0o700)
    context = task_context()
    result = {"case_id": args.case, "case_version": case.VERSION if case else None,
              "run_id": run_id, "status": "running", "mode": "mobile_gui",
              "started_at": datetime.now(timezone.utc).isoformat(), "context": context,
              "initialization": {"status": "not_started"}, "execution": {"status": "not_started"},
              "verification": {"status": "not_run"}, "cleanup": {"status": "pending"}, "errors": []}
    save(run_dir / "result.json", result)
    print(f"运行目录：{run_dir}", flush=True)
    process, runtime, pin = None, None, ""
    serial, setup_started, case_state = None, False, {}
    group_stopped = True
    previous_handlers = {}

    def interrupted(signum, frame):
        # Once interrupted, allow the bounded cleanup to finish even if another
        # SIGTERM/Ctrl+C arrives. SIGKILL remains outside application control.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        raise KeyboardInterrupt(f"Received signal {signum}")

    for sig in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[sig] = signal.signal(sig, interrupted)
    try:
        info = preflight(args.serial)
        serial = info["serial"]
        result["serial"] = serial
        save(run_dir / "preflight.json", info)
        if args.probe:
            result["status"] = "preflight_passed"
            result["initialization"] = {"status": "passed"}
            raise RunFinished
        if info["serial"].startswith("emulator-"):
            raise RuntimeError("These cases target the user's physical phone")
        locked = info["state"]["locked"]
        if locked is None:
            raise RuntimeError("Cannot determine keyguard state on this phone; adapt parser before evaluation")
        if args.case == "unlock":
            if not locked:
                raise RuntimeError("Unlock requires a locked phone before startup; arena will not change lock settings")
            if not sys.stdin.isatty():
                raise RuntimeError("Unlock requires an interactive terminal for hidden PIN input")
            pin = getpass.getpass("请输入本轮解锁密码（不回显、不保存）：")
            if not re.fullmatch(r"[0-9]{4,16}", pin):
                raise RuntimeError("This unlock case supports a 4–16 digit PIN")
        elif locked:
            raise RuntimeError("This case requires an unlocked phone at startup")
        if args.case == "wechat" and "com.tencent.mm" not in info["packages"]:
            raise RuntimeError("WeChat is not installed")
        if args.case == "weather" and info["device_date"] != context["date"]:
            raise RuntimeError("Phone date differs from today's Asia/Shanghai date")
        if hasattr(case, "setup"):
            setup_started = True
            case.setup(serial, case_state)
            save(run_dir / "initial_state.json", case_state)
        before = snapshot(info["serial"], run_dir / "before")
        if before["locked"] != locked:
            raise RuntimeError("Lock state changed during initialization")
        if case_state.get("expected_package") == before.get("foreground_package") and "expected_package" in case_state:
            raise RuntimeError("Initial screen already matches the task target")
        settings = {"run_id": run_id, "case": args.case, "serial": info["serial"],
                    "device": args.device, "ufo_root": str(args.ufo_root), "context": context,
                    "request": make_request(args.case)}
        save(run_dir / "request.json", settings)
        runtime = runtime_directory(args.ufo_root, run_dir, args.case == "unlock")
        # Parent's env credentials are not persisted; worker creates fresh service keys.
        env = dict(os.environ, ANDROID_SERIAL=info["serial"], PYTHONDONTWRITEBYTECODE="1")
        env.pop("MOBILE_ARENA_PIN", None)
        stream_path = os.devnull if args.case == "unlock" else str(run_dir / "galaxy.log")
        with open(stream_path, "w") as stream:
            process = subprocess.Popen([sys.executable, "-u", str(HERE / "galaxy_worker.py"), str(run_dir)],
                                       cwd=runtime, env=env, stdin=subprocess.PIPE,
                                       stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            group_stopped = False
            try:
                process.communicate(input=(pin + "\n").encode() if pin else b"", timeout=args.timeout)
            except subprocess.TimeoutExpired:
                result["status"] = "timeout"
                result["errors"].append(f"Service startup/Galaxy exceeded {args.timeout}s; no automatic retry")
        group_stopped = stop_group(process)
        initialization = read_json(run_dir / "initialization.json", {"status": "failed"})
        execution = read_json(run_dir / "execution.json", {"status": "not_started"})
        result["initialization"] = initialization
        result["execution"] = {k: v for k, v in execution.items() if k not in {"tasks", "galaxy"}}
        result["execution"]["worker_exit_code"] = process.returncode
        if result["status"] == "timeout":
            raise RunFinished
        if initialization.get("status") != "passed":
            result["status"] = "initialization_failed"
            raise RunFinished
        if (process.returncode != 0 or execution.get("status") != "completed"
                or execution.get("device_stopped_confirmed") is not True or not group_stopped):
            result["status"] = "execution_failed"
            raise RunFinished
        # A stopped host group alone never proves remote Android actions ended.
        # Only successful task-end acknowledgments allow post-run verification.
        result["device_operations_stopped"] = True
        result["status"] = "verification_error"
        after = snapshot(info["serial"], run_dir / "after")
        actions = action_evidence(runtime / "logs", pin)
        save(run_dir / "actions.json", actions)
        try:
            answer = final_answer(execution, args.device)
        except (ValueError, TypeError, KeyError) as exc:
            result["status"] = "verification_failed"
            result["verification"] = {"status": "failed", "error": str(exc)}
            raise RunFinished
        save(run_dir / "answer.json", answer)
        if hasattr(case, "verify"):
            result["verification"] = case.verify(serial, case_state, after)
        else:
            result["verification"] = evaluate(args.case, context, answer, before, after,
                                              actions, run_dir / "after")
        status = result["verification"]["status"]
        result["status"] = "verification_failed" if status == "failed" else status
    except RunFinished:
        pass
    except KeyboardInterrupt as exc:
        result["status"] = "interrupted"
        result["errors"].append(str(exc) or "Interrupted")
    except Exception as exc:
        if result["status"] == "running":
            result["status"] = "initialization_failed" if process is None else "execution_failed"
        error = str(exc).replace(pin, "<redacted>") if pin else str(exc)
        result["errors"].append(error)
        if process is None:
            result["initialization"] = {"status": "failed", "error": error}
    finally:
        try:
            if process is not None and not group_stopped:
                group_stopped = stop_group(process)
            result["owned_process_group_stopped"] = group_stopped
            execution = {}
            if process is not None:
                result["initialization"] = read_json(run_dir / "initialization.json", result["initialization"])
                execution = read_json(run_dir / "execution.json", result["execution"])
                result["execution"] = {k: v for k, v in execution.items() if k not in {"tasks", "galaxy"}}
                result["execution"]["worker_exit_code"] = process.returncode
                if result["status"] == "timeout":
                    result["execution"]["status"] = "timeout" if (run_dir / "submission.json").exists() else "not_started"
            submitted = (run_dir / "submission.json").exists()
            result["device_operations_stopped"] = group_stopped and (
                not submitted or execution.get("device_stopped_confirmed") is True)
            phone_cleanup = "Existing case: business state retained"
            if setup_started:
                save(run_dir / "initial_state.json", case_state)
                if result["device_operations_stopped"]:
                    case.cleanup(serial, case_state)
                    phone_cleanup = "Original test settings restored; returned to home screen"
                else:
                    phone_cleanup = "Stop unconfirmed; phone state retained; original values in initial_state.json"
            if runtime is not None and group_stopped:
                if args.case != "unlock" and (runtime / "logs").exists():
                    shutil.copytree(runtime / "logs", run_dir / "traces", dirs_exist_ok=True)
                shutil.rmtree(runtime)
            result["cleanup"] = {
                "status": "completed" if group_stopped else "stop_unconfirmed",
                "phone_data": phone_cleanup,
                "runtime": "removed" if runtime and group_stopped else str(runtime) if runtime else None}
            if args.case == "unlock":
                result["sensitive_logs"] = "Raw stdout disabled; raw UFO logs only in temporary /dev/shm runtime, not archived"
            redact_logs(run_dir)
        except Exception as exc:
            result["cleanup"] = {"status": "failed", "error": str(exc)}
            result["status"] = "cleanup_failed"
        finally:
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            save(run_dir / "result.json", result)
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
            print(f"结果：{result['status']}\n{run_dir / 'result.json'}", flush=True)
    return 0 if result["status"] in {"passed", "preflight_passed"} else 3 if result["status"] == "review_required" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--probe", action="store_true", help="Read-only phone inventory; no Galaxy request")
    parser.add_argument("--serial", help="ADB serial; required if multiple devices are connected")
    parser.add_argument("--device", default="mobile_device_1")
    parser.add_argument("--local-services", action="store_true", help="Explicit alias for the default owned-service mode")
    parser.add_argument("--timeout", type=float, default=900, help="Service startup + Galaxy wall-clock seconds")
    parser.add_argument("--ufo-root", type=Path, default=HERE.parents[2] / "UFO3")
    parser.add_argument("--output", type=Path, default=HERE / "runs")
    args = parser.parse_args()
    if not args.probe and not args.case:
        parser.error("--case is required unless --probe is used")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    args.output, args.ufo_root = args.output.resolve(), args.ufo_root.resolve()
    if not args.probe and not (args.ufo_root / "galaxy/galaxy_client.py").is_file():
        parser.error("--ufo-root must point to the existing UFO3 repository")
    os.umask(0o077)
    (HERE / "runs").mkdir(exist_ok=True)
    with (HERE / "runs/.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another Mobile arena run is active")
        return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
