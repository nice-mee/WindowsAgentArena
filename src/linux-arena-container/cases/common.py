"""Input copying and small result-comparison helpers."""
import json
from pathlib import Path
import shutil

from prepare_assets import HERE, check_case, digest
from verify import check_reads


def file_hashes(directory):
    return {str(p.relative_to(directory)): None if p.is_symlink() else digest(p)
            for p in directory.rglob("*") if p.is_file() or p.is_symlink()}


def checked(checks, **details):
    return {"status": "passed" if all(checks.values()) else "failed",
            "checks": checks, **details}


def setup_inputs(case_id, work):
    entries = check_case(case_id)
    hashes = {}
    prefix = f"fixtures/{case_id}/"
    for entry in entries:
        if entry["role"] != "fixture":
            continue
        name = entry["path"].removeprefix(prefix)
        destination = work / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / entry["path"], destination)
        if digest(destination) != entry["sha256"]:
            raise ValueError(f"Initialization copy mismatch: {name}")
        hashes[name] = entry["sha256"]
    return {"directory": str(work), "sha256": hashes}


def unchanged(work, state):
    actual = {str(p.relative_to(work)) for p in work.rglob("*") if p.is_file() or p.is_symlink()}
    return actual == set(state["sha256"]) and all(
        not (work / name).is_symlink() and digest(work / name) == expected
        for name, expected in state["sha256"].items())


def structured(raw):
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("```json\n") and text.endswith("```"):
            text = text[8:-3].strip()
        elif text.startswith("```\n") and text.endswith("```"):
            text = text[4:-3].strip()
        try:
            return json.loads(text)
        except ValueError:
            pass
    return None


def judge_structured(raw, expected):
    """A voluntarily structured answer can be checked; prose needs review."""
    if raw is None or raw == "" or (isinstance(raw, str) and not raw.strip()):
        return {"status": "failed", "reason": "Missing answer"}
    value = structured(raw)
    if isinstance(value, dict) and set(expected) == value.keys():
        actual = {key: value[key] for key in expected}
        passed = json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)
        return {"status": "passed" if passed else "failed", "actual": actual, "expected": expected}
    return {"status": "review_required", "reason": "Natural answer needs semantic review", "expected": expected}


def verify_readonly(work, state, answers, traces, judge):
    trace = check_reads(traces, work, state["sha256"])
    intact = unchanged(work, state)
    # A single terminal device result is automatic-checkable. Do not search
    # intermediate steps, prompts, or unrelated logs for the desired answer.
    results = answers["device_results"]
    if len(results) == 1:
        answer = judge(results[0]["result"])
    else:
        answer = {"status": "review_required", "reason": "Multiple terminal device results"}
    status = answer["status"] if trace["passed"] and intact else "failed"
    return {"status": status, "answer": answer, "trace": trace, "materials_unchanged": intact}
