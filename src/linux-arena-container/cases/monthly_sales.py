"""Grade six monthly totals in the workbook saved by Calc."""
from .common import setup_inputs, checked
from .workbooks import read_workbook

ID, MODE, VERSION = "monthly_sales", "gui", "1"
DIFFICULTY = 'medium'
APPLICATION = "calc"
FILENAME = "SalesRep.xlsx"
ARTIFACT = True


def setup(work):
    state = setup_inputs(ID, work)
    sheets = read_workbook(work / FILENAME)
    if not sheets or "Sheet1" not in sheets:
        raise ValueError("Cannot read sales input")
    rows = sheets["Sheet1"]["rows"]
    state["source_rows"] = rows
    state["expected_totals"] = {month: sum(row[column] for row in rows[1:])
                                for column, month in enumerate(rows[0]) if column > 0}
    return state


def make_request(work):
    return (f"在 Calc 中，把 {work / FILENAME} 每个月的销售总额汇总到 Sheet2，"
            "列名用 Month 和 Total，并保存。")


def verify(work, state, answers, traces):
    sheets = read_workbook(work / FILENAME)
    if not sheets or "Sheet1" not in sheets or "Sheet2" not in sheets:
        return checked({"saved_summary_sheet_present": False})
    rows = [row for row in sheets["Sheet2"]["rows"] if row]
    totals = {}
    valid = bool(rows) and "Month" in rows[0] and "Total" in rows[0]
    if valid:
        month_col, total_col = rows[0].index("Month"), rows[0].index("Total")
        for row in rows[1:]:
            if len(row) <= max(month_col, total_col):
                valid = False
                break
            month, total = row[month_col], row[total_col]
            if not isinstance(month, str) or month in totals or type(total) not in (int, float):
                valid = False
                break
            totals[month] = total
    return checked({"monthly_totals": valid and totals == state["expected_totals"],
                    "source_data_preserved": sheets["Sheet1"]["rows"] == state["source_rows"]},
                   actual_totals=totals, expected_totals=state["expected_totals"])
