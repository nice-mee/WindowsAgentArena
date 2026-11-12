"""Owned host processes and isolated UFO runtime logs."""
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time


def group_running(pgid):
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = path.read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == pgid and fields[0] != "Z":
                return True
        except (OSError, IndexError, ValueError):
            continue
    return False


def stop_group(process):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            process.poll()
            if not group_running(process.pid):
                process.wait(timeout=3)
                return True
            time.sleep(0.1)
    return not group_running(process.pid)


def runtime_directory(ufo_root, run_dir, sensitive):
    # UFO uses relative paths for logs/assets. Give this run its own working
    # directory, so no source/config edits or raw logs go into the UFO checkout.
    if sensitive:
        if not Path("/dev/shm").is_dir():
            raise RuntimeError("Unlock requires /dev/shm for temporary sensitive runtime logs")
        directory = Path(tempfile.mkdtemp(prefix="mobile-arena-", dir="/dev/shm"))
    else:
        directory = run_dir / "runtime"
        directory.mkdir(mode=0o700)
    for source in ufo_root.iterdir():
        if source.name not in {"logs", ".git", "__pycache__"}:
            (directory / source.name).symlink_to(source, target_is_directory=source.is_dir())
    (directory / "logs").mkdir(mode=0o700)
    return directory


def redact_logs(directory):
    for path in directory.rglob("*.log"):
        # pathlib rglob does not descend into symlinked repository directories.
        if path.is_symlink():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"(UFO Server API key:\s*)\S+", r"\1<redacted>", text)
        text = re.sub(r"([?&]token=)[^\s&\"'<>]+", r"\1<redacted>", text)
        path.write_text(text, encoding="utf-8")


