#!/usr/bin/env python3
"""Record evidence-based human adjudication without overwriting automatic checks."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path

from phone import save


def record_review(directory, decision, note):
    if not note.strip():
        raise ValueError("A concrete evidence-based review note is required")
    with (directory / ".review.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / "result.json"
        result = json.loads(path.read_text())
        if result["status"] != "review_required" or result["verification"]["status"] != "review_required":
            raise ValueError("Only review_required runs can be adjudicated; failed execution cannot be upgraded")
        if not any((directory / "after" / name).is_file() for name in ("screen.png", "ui.xml")) or not (directory / "answer.json").is_file():
            raise ValueError("Missing independent screenshot/UI tree or actual response record")
        review = {"decision": decision, "note": note,
                  "reviewed_at": datetime.now(timezone.utc).isoformat(),
                  "method": "human review of independent before/after evidence and execution trace"}
        # Original automatic verification is retained, distinct from human judgment.
        save(directory / "review.json", review)
        result["human_review"] = review
        result["status"] = "passed" if decision == "pass" else "verification_failed"
        save(path, result)
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--decision", choices=("pass", "fail"), required=True)
    parser.add_argument("--note", required=True, help="What evidence was checked and what it established")
    args = parser.parse_args()
    try:
        result = record_review(args.run_dir.resolve(), args.decision, args.note)
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    print(result["status"])
