#!/usr/bin/env python3
"""Record a human decision for a natural answer while retaining automatic checks."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path

from run import save


def record_review(directory, decision, note):
    if decision not in {"pass", "fail"} or not note.strip():
        raise ValueError("Use pass/fail and a concrete evidence-based note")
    with (directory / ".review.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = json.loads((directory / "result.json").read_text())
        verification = result["verification"]
        if result["status"] != "review_required" or verification["status"] != "review_required":
            raise ValueError("Only review_required runs can be adjudicated")
        if (not result.get("device_operations_stopped") or not verification["trace"]["passed"]
                or not verification["materials_unchanged"] or not (directory / "answer.json").is_file()
                or not (directory / "evidence/materials").is_dir()):
            raise ValueError("Missing independent evidence or confirmed stop")
        review = {"decision": decision, "note": note, "reviewed_at": datetime.now(timezone.utc).isoformat(),
                  "method": "human review of actual response, independent reference and device trace"}
        if (directory / "review.json").exists():
            raise ValueError("Existing review cannot be overwritten")
        save(directory / "review.json", review)
        result["human_review"] = review
        result["status"] = "passed" if decision == "pass" else "verification_failed"
        save(directory / "result.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--decision", choices=("pass", "fail"), required=True)
    parser.add_argument("--note", required=True)
    args = parser.parse_args()
    try:
        result = record_review(args.run_dir.resolve(), args.decision, args.note)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(result["status"])


if __name__ == "__main__":
    main()
