"""Separate device evidence from model claims; ambiguous UI requires review."""
import json
from pathlib import Path

ACTION_TOOLS = {"tap", "swipe", "type_text", "launch_app", "press_key", "click_control"}


def action_evidence(logs, pin=""):
    """Keep function names and result status only, never PIN entry arguments."""
    calls, errors = [], []
    pin_entry_observed = False
    records = 0
    for path in sorted(Path(logs).glob("galaxy_mobile-arena-*/response.log")):
        digits = ""
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                records += 1
                for action in record.get("action", []):
                    function = action.get("function", "").split("/")[-1]
                    payload = action.get("result", {}).get("result", {})
                    if function in ACTION_TOOLS:
                        success = payload.get("success") is True
                        calls.append({"trace": path.parent.name, "line": number,
                                      "function": function, "success": success})
                        if pin and success:
                            args = action.get("arguments", {})
                            if function == "type_text":
                                pin_entry_observed |= args.get("text") == pin
                                digits = ""
                            elif function in {"click_control", "press_key"}:
                                label = str(args.get("control_name", "")) if function == "click_control" else str(args.get("key_code", ""))
                                if function == "press_key":
                                    if label.startswith("KEYCODE_"):
                                        label = label.removeprefix("KEYCODE_")
                                    elif label.isdecimal():
                                        code = int(label)
                                        label = str(code - 7) if 7 <= code <= 16 else ""
                                if len(label) == 1 and label in "0123456789":
                                    digits = (digits + label)[-len(pin):]
                                    pin_entry_observed |= digits == pin
                                else:
                                    digits = ""
                            else:
                                digits = ""
            except (ValueError, TypeError, AttributeError) as exc:
                errors.append(f"Malformed action record at {path.name}:{number}: {type(exc).__name__}")
    return {"calls": calls, "errors": errors, "records": records, "pin_entry_observed": pin_entry_observed,
            "passed": any(c["success"] for c in calls) and not errors}


def final_answer(execution, device):
    """Keep actual responses unchanged, including prose and multiple terminal tasks.

    Only read result fields, never task descriptions, requests or thoughts.
    The surrounding structure is evaluator metadata, not an agent output schema.
    """
    tasks = execution.get("tasks", {})
    if not tasks or any(t.get("target_device_id") != device for t in tasks.values()):
        raise ValueError("Missing tasks or unexpected device")
    sinks = [(task_id, t) for task_id, t in tasks.items() if not t.get("dependents")]
    if not sinks:
        raise ValueError("No terminal device tasks")
    responses = []
    for task_id, task in sinks:
        result = task.get("result") or {}
        if task.get("status") != "completed" or result.get("status") != "completed":
            raise ValueError("Terminal device task did not complete")
        rounds = result.get("result")
        raw = rounds[-1].get("result") if isinstance(rounds, list) and rounds and isinstance(rounds[-1], dict) else None
        responses.append({"task_id": task_id, "result": raw})
    rounds = (execution.get("galaxy", {}).get("session_results") or {}).get("final_results")
    galaxy_result = rounds[-1].get("result") if isinstance(rounds, list) and rounds and isinstance(rounds[-1], dict) else None
    return {"device_results": responses, "galaxy_result": galaxy_result}


def has_content(value):
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(has_content(v) for v in value.values())
    if isinstance(value, list):
        return any(has_content(v) for v in value)
    return value is not None and type(value) in (int, float)


def evaluate(case, context, answer, before, after, actions, evidence_dir):
    trace_present = (actions.get("records", 0) > 0 or actions.get("passed") is True) and not actions.get("errors")
    checks = {"device_trace_available": trace_present}
    if case == "unlock":
        checks.update(initially_locked=before.get("locked") is True,
                      finally_unlocked=after.get("locked") is False,
                      awake=after.get("awake") is True,
                      pin_entry_observed=actions.get("pin_entry_observed") is True)
        return {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
                "method": "independent ADB keyguard state transition + PIN input evidence"}
    checks["independent_evidence"] = any((evidence_dir / name).is_file() for name in ("screen.png", "ui.xml"))
    if case == "weather":
        checks["feedback_present"] = (has_content(answer.get("galaxy_result")) or
                                      any(has_content(item.get("result")) for item in answer.get("device_results", [])))
        location = context["weather_location"]
        checklist = [f"截图、UI 树与本轮轨迹确认通过手机天气应用查询了{location}，不是其他地区或浏览器搜索",
                     f"确认所查为上海时区 {context['date']} 当天的天气，区分当前实况和今天预报",
                     "核对实际自然语言反馈是否回答了天气问题，内容与界面证据一致；不要求包名、固定措辞或温度字段齐全"]
    else:
        checklist = [f"前后证据和本轮轨迹确认向 {context['contact']} 一对一聊天新发了周五下午喝咖啡的邀约，措辞可以不同",
                     f"周五按本轮日期理解为 {context['friday']}；不要求消息写出具体日期",
                     "确认是新发出的消息而非草稿、旧消息或群聊，检查发送中/失败标记及是否重复发送；不要求对方回复或已读"]
    # Foreground package, exact fields and the last screen are observations,
    # not outcome requirements. An agent may legitimately navigate away after
    # reading/sending; review the entire trace before deciding success/failure.
    return {"status": "review_required" if all(checks.values()) else "failed",
            "checks": checks,
            "observations": {"foreground_package": after.get("foreground_package"),
                             "foreground_source": after.get("foreground_source"),
                             "visible_ui_packages": after.get("visible_ui_packages", []),
                             "locked": after.get("locked"),
                             "evidence_errors": after.get("evidence_errors", [])},
            "method": "execution evidence + human review of task outcome and natural response",
            "review_checklist": checklist,
            "reason": "Judge task meaning against independent evidence; no agent JSON schema or exact-string grading"}
