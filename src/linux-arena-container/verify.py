"""Extract device results and inspect actual MCP evidence."""
import json
from pathlib import Path
import shlex


def check_reads(traces, materials, filenames):
    """Require content-bearing MCP results for this run's material paths."""
    read_files, calls, errors, terminal_statuses = set(), [], [], []
    for trace in traces:
        if not trace["device"]:
            continue
        path = Path(trace["copy"])
        last_status = None
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                last_status = record.get("status")
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
                    valid |= (tool == "wc" and any(t == "--lines" or (t.startswith("-") and "l" in t[1:] and not t.startswith("--")) for t in tokens[1:])
                              and payload.get("success") is True and payload.get("exit_code") == 0)
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
        terminal_statuses.append({"log": str(path), "status": last_status})
        if last_status != "FINISH":
            errors.append(f"Device trace did not finish successfully: {path} ({last_status})")
    return {"passed": set(filenames) <= read_files and not errors,
            "files_read": sorted(read_files), "missing": sorted(set(filenames) - read_files),
            "calls": calls, "errors": errors, "terminal_statuses": terminal_statuses}


def final_answer(execution, device):
    tasks = execution.get("tasks", {})
    if not tasks or any(t.get("target_device_id") != device for t in tasks.values()):
        raise ValueError("Missing tasks or unexpected target device")
    sinks = [(key, t) for key, t in tasks.items() if not t.get("dependents")]
    if not sinks:
        raise ValueError("No terminal device task")
    answers = []
    for key, task in sinks:
        result = task.get("result") or {}
        if task.get("status") != "completed" or result.get("status") != "completed":
            raise ValueError("Final device task did not complete")
        rounds = result.get("result")
        if not isinstance(rounds, list) or not rounds or not isinstance(rounds[-1], dict) or "result" not in rounds[-1]:
            raise ValueError("Final device task has no round result")
        answers.append({"task_id": key, "result": rounds[-1]["result"]})
    galaxy_rounds = (execution.get("galaxy", {}).get("session_results") or {}).get("final_results")
    galaxy_result = galaxy_rounds[-1].get("result") if isinstance(galaxy_rounds, list) and galaxy_rounds and isinstance(galaxy_rounds[-1], dict) else None
    return {"device_results": answers, "galaxy_result": galaxy_result}

