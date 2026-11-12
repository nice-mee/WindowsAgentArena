"""Collect JPG files from a fixed nested photo directory."""
from pathlib import Path
from .common import setup_inputs, file_hashes, checked

ID, MODE, VERSION = "collect_jpg", "cli", "1"
DIFFICULTY = 'easy'
ARTIFACT = True


def setup(work):
    state = setup_inputs(ID, work)
    (work / "cpjpg").mkdir()
    state["expected"] = {Path(name).name: value for name, value in state["sha256"].items()
                         if name.endswith(".jpg")}
    return state


def make_request(work):
    return f"把 {work / 'photos'} 里各个文件夹的 jpg 图片集中复制到 {work / 'cpjpg'}。"


def verify(work, state, answers, traces):
    actual = file_hashes(work / "cpjpg")
    source = {f"photos/{name}": value for name, value in file_hashes(work / "photos").items()}
    return checked({"copied_jpgs": actual == state["expected"],
                    "source_preserved": source == state["sha256"]},
                   output_files=sorted(actual))
