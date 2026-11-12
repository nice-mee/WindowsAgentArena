"""Normalize three regular files without changing their contents or directories."""
import stat
from .common import setup_inputs, file_hashes, checked

ID, MODE, VERSION = "normalize_permissions", "cli", "1"
DIFFICULTY = 'easy'
ARTIFACT = True
INITIAL_MODES = {"testDir/file1.txt": 0o755, "testDir/subDir1/file2.txt": 0o644,
                 "testDir/subDir2/file3.txt": 0o777}


def setup(work):
    state = setup_inputs(ID, work)
    for name, mode in INITIAL_MODES.items():
        (work / name).chmod(mode)
    state["directory_modes"] = {str(p.relative_to(work)): stat.S_IMODE(p.stat().st_mode)
                                for p in (work / "testDir").rglob("*") if p.is_dir()}
    state["directory_modes"]["testDir"] = stat.S_IMODE((work / "testDir").stat().st_mode)
    state["initial_modes"] = INITIAL_MODES
    return state


def make_request(work):
    return f"把 {work / 'testDir'} 里所有普通文件的权限统一改成 644。"


def verify(work, state, answers, traces):
    directories = all((work / name).is_dir() and stat.S_IMODE((work / name).stat().st_mode) == mode
                      for name, mode in sorted(state["directory_modes"].items(), key=lambda item: item[0].count("/")))
    # A chmod on directories can prevent even reading their files as a normal user.
    if not directories:
        return checked({"directory_permissions_preserved": False})
    modes = {name: stat.S_IMODE((work / name).stat().st_mode) if (work / name).is_file() else None
             for name in state["sha256"]}
    correct_modes = all(mode == 0o644 for mode in modes.values())
    return checked({"files_and_contents_preserved": correct_modes and file_hashes(work) == state["sha256"],
                    "file_permissions_644": correct_modes,
                    "directory_permissions_preserved": directories}, actual_modes=modes)


def cleanup(work, state):
    # Restore access only to our fixture directories, after grading, so deletion works.
    for name, mode in sorted(state.get("directory_modes", {}).items(), key=lambda item: item[0].count("/")):
        path = work / name
        if path.is_dir() and not path.is_symlink():
            path.chmod(mode)
    for name in state.get("sha256", {}):
        path = work / name
        if path.is_file() and not path.is_symlink():
            path.chmod(0o644)
