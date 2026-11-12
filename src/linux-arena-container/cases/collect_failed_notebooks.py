"""Copy matching notebooks while preserving their relative paths."""
from .common import setup_inputs, file_hashes, checked

ID, MODE, VERSION = "collect_failed_notebooks", "cli", "1"
DIFFICULTY = 'easy'
ARTIFACT = True


def setup(work):
    state = setup_inputs(ID, work)
    (work / "fails").mkdir()
    state["expected"] = {name.removeprefix("project/"): value
                         for name, value in state["sha256"].items()
                         if name.endswith("failed.ipynb")}
    return state


def make_request(work):
    return (f"把 {work / 'project'} 里名字以 failed.ipynb 结尾的文件复制到 {work / 'fails'}，"
            "保留它们在项目里的相对目录层级。")


def verify(work, state, answers, traces):
    actual = file_hashes(work / "fails")
    source = {f"project/{name}": value for name, value in file_hashes(work / "project").items()}
    return checked({"collected_paths_and_contents": actual == state["expected"],
                    "source_preserved": source == state["sha256"]},
                   output_files=sorted(actual))
