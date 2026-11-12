"""OSWorld names deduplication, preserving first occurrence and source cells."""
from .common import setup_inputs, checked

ID, MODE, VERSION, DIFFICULTY = "unique_names", "gui", "1", "medium"
APPLICATION, FILENAME, ARTIFACT = "calc", "Names_Duplicate_Unique.xlsx", True


def setup(work):
    return setup_inputs(ID, work)


def make_request(work):
    return (f"在 Calc 中打开 {work / FILENAME}，将 Names with Duplicates 列中的姓名去重后填入 "
            "Unique Names 列，保留首次出现的顺序，不改动其他区域，并保存。")


def verify(work, state, answers, traces):
    from prepare_assets import HERE
    from .workbooks import read_workbook
    source = read_workbook(HERE / "fixtures" / ID / FILENAME)
    actual = read_workbook(work / FILENAME)
    if not actual or set(actual) != set(source):
        return checked({"saved_workbook": False})
    expected = [row[:] for row in source["Sheet1"]["rows"]]
    names = list(dict.fromkeys(row[1] for row in expected[1:] if len(row) > 1 and row[1] is not None))
    for i, row in enumerate(expected[1:]):
        row += [None] * (4 - len(row))
        row[3] = names[i] if i < len(names) else None
        while row and row[-1] is None:
            row.pop()
    return checked({"ordered_unique_names_and_preserved_cells": actual["Sheet1"]["rows"] == expected})
