"""Reduce the first worksheet's zoom through Calc and preserve its data."""
from .common import setup_inputs, checked
from .workbooks import read_workbook

ID, MODE, VERSION = "zoom_out", "gui", "1"
DIFFICULTY = 'easy'
APPLICATION = "calc"
FILENAME = "Zoom_Out_Oversized_Cells.xlsx"
ARTIFACT = True


def setup(work):
    state = setup_inputs(ID, work)
    state["sheets"] = read_workbook(work / FILENAME)
    if not state["sheets"]:
        raise ValueError("Cannot read initial workbook")
    return state


def make_request(work):
    return f"在 Calc 中，{work / FILENAME} 这张表显示得太大了，帮我缩小一点并保存。"


def verify(work, state, answers, traces):
    actual = read_workbook(work / FILENAME)
    if not actual:
        return checked({"saved_workbook_readable": False})
    first = next(iter(state["sheets"]))
    zoom = actual.get(first, {}).get("zoom")
    return checked({"zoom_reduced": zoom is not None and 0 < zoom < min(260, state["sheets"][first]["zoom"]),
                    "cell_data_preserved": {name: sheet["rows"] for name, sheet in actual.items()}
                    == {name: sheet["rows"] for name, sheet in state["sheets"].items()}}, actual_zoom=zoom)
