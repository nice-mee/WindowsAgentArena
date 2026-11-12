"""Archive old files as ZIP and move recent files into a separate directory."""
import hashlib
import os
from pathlib import PurePosixPath
import time
from zipfile import ZipFile, BadZipFile
from .common import setup_inputs, file_hashes, checked

ID, MODE, VERSION = "archive_by_age", "cli", "1"
DIFFICULTY = 'medium'
ARTIFACT = True


def setup(work):
    state = setup_inputs(ID, work)
    state["reference_time"] = time.time()
    state["mtimes"], state["old"], state["new"] = {}, {}, {}
    for name, value in state["sha256"].items():
        path = work / name
        old = path.name.startswith("old_")
        modified = state["reference_time"] - (45 if old else 2) * 86400
        os.utime(path, (modified, modified))
        state["mtimes"][name] = modified
        state["old" if old else "new"][path.name] = value
    (work / "old_files").mkdir()
    (work / "new_files").mkdir()
    return state


def make_request(work):
    return (f"把 {work / 'test_files'} 里超过 30 天没改过的文件打成 ZIP 放到 {work / 'old_files'}，"
            f"其余文件移到 {work / 'new_files'}。")


def verify(work, state, answers, traces):
    archived = {}
    archives = list((work / "old_files").rglob("*"))
    archives = [p for p in archives if p.is_file() or p.is_symlink()]
    try:
        for path in archives:
            if path.suffix.lower() != ".zip" or path.is_symlink():
                return checked({"valid_zip_outputs": False})
            with ZipFile(path) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    name = PurePosixPath(member.filename).name
                    if name in archived:
                        return checked({"archive_members_unique": False})
                    archived[name] = hashlib.sha256(archive.read(member)).hexdigest()
    except (BadZipFile, OSError, RuntimeError, NotImplementedError) as exc:
        return checked({"valid_zip_outputs": False}, reason=str(exc))
    return checked({"old_files_archived": archived == state["old"],
                    "new_files_moved": file_hashes(work / "new_files") == state["new"]
                    and all(not (work / "test_files" / name).exists() for name in state["new"])},
                   archived_files=sorted(archived))
