"""Replace text in the editor; grade the file actually saved by the agent."""
from prepare_assets import HERE
from .common import setup_inputs, checked

ID, MODE, VERSION = "replace_text", "gui", "1"
DIFFICULTY = 'easy'
APPLICATION = "code"
FILENAME = "vscode_replace_text.txt"
ARTIFACT = True


def setup(work):
    return setup_inputs(ID, work)


def make_request(work):
    return f"在 VS Code 中，把 {work / FILENAME} 里的 text 全部改成 test 并保存。"


def verify(work, state, answers, traces):
    path = work / FILENAME
    expected = (HERE / "references/replace_text/vscode_replace_text_gold.txt").read_bytes()
    return checked({"saved_text_matches": path.is_file() and not path.is_symlink()
                    and path.read_bytes() == expected})
