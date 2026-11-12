#!/usr/bin/env python3
"""Explicit, hash-pinned asset preparation; never execute upstream scripts."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
LOCK = HERE / "provenance/assets.lock.json"
OSWORLD_COMMIT = "8903ebeb0efdf74331bd7dc37ed91ccbbff22317"
MAX_BYTES = 32 * 1024 * 1024


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(root=HERE):
    value = json.loads((root / "provenance/assets.lock.json").read_text())
    if value["osworld_commit"] != OSWORLD_COMMIT:
        raise ValueError("Unexpected OSWorld source version")
    return value


def asset_path(root, name):
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Invalid asset path: {name}")
    path = root / relative
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError(f"Symlink in asset path: {name}")
    return path


def check_entry(root, entry):
    path = asset_path(root, entry["path"])
    if not path.is_file():
        raise ValueError(f"Missing local asset: {entry['path']}; run prepare_assets.py explicitly")
    if path.stat().st_size != entry["size"] or digest(path) != entry["sha256"]:
        raise ValueError(f"Asset hash mismatch: {entry['path']}")


def check_case(case_id, root=HERE):
    entries = [e for e in manifest(root)["files"] if e["case_id"] == case_id]
    if not entries:
        raise ValueError(f"No asset manifest for {case_id}")
    for entry in entries:
        check_entry(root, entry)
    expected = {e["path"] for e in entries if e["role"] == "fixture"}
    directory = root / "fixtures" / case_id
    actual = {str(p.relative_to(root)) for p in directory.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != expected:
        raise ValueError(f"Unexpected fixture file set for {case_id}")
    return entries


def prepare(entries, root=HERE, check_only=False):
    """One attempt per file. Existing mismatches are errors, never overwritten."""
    errors = []
    for entry in entries:
        try:
            path = asset_path(root, entry["path"])
            if not path.exists() and not check_only:
                url = entry.get("url")
                if not url:
                    raise ValueError(f"Missing repository fixture: {entry['path']}; restore it from version control")
                with urlopen(url, timeout=45) as response:
                    content = response.read(MAX_BYTES + 1)
                if len(content) != entry["size"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
                    raise ValueError(f"Downloaded bytes do not match lock: {entry['path']}")
                path.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation also prevents concurrent preparation overwrites.
                with path.open("xb") as stream:
                    stream.write(content)
            check_entry(root, entry)
            print(f"OK {entry['path']}", flush=True)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            print(f"ERROR {exc}", flush=True)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Offline verification only")
    parser.add_argument("--case", action="append", help="Limit to a case (repeatable); default all")
    args = parser.parse_args()
    lock = manifest()
    known = {e["case_id"] for e in lock["files"]}
    if args.case and set(args.case) - known:
        parser.error("Unknown case in asset manifest")
    entries = [e for e in lock["files"] if not args.case or e["case_id"] in args.case]
    errors = prepare(entries, check_only=args.check)
    print(f"Assets: {len(entries) - len(errors)}/{len(entries)} verified")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
