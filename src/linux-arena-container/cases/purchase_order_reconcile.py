"""Reconcile fixed local message history with saved purchase order rows."""
import json
from .common import setup_inputs, checked, digest
from .workbooks import read_workbook
from prepare_assets import HERE

ID, MODE, VERSION, DIFFICULTY = "purchase_order_reconcile", "gui", "1", "hard"
FILENAME, ARTIFACT = "Purchase_Order_Form.xlsx", True
APPLICATIONS = [("chrome", "messages/index.html"), ("calc", FILENAME)]


def setup(work):
    return setup_inputs(ID, work)


def make_request(work):
    return (f"请结合浏览器中的本地消息记录 {work / 'messages/index.html'}，"
            f"核对 {work / FILENAME} 中四个团队的八项采购申请。按最新有效规则和单项例外，"
            "在 Review 表填写每项申请的 ID、最终状态和申请总额，状态使用 Approved、Rejected 或 Pending。"
            "在 Purchase Orders 表已有记录之后追加所有获准项目，填写申请 ID、团队、品名、供应商、"
            "数量、单价和总额。保留已有采购记录和申请表，保存工作簿。")


def keyed(rows, width):
    result = {}
    for row in rows:
        if len(row) != width or not row[0] or row[0] in result:
            return None
        result[row[0]] = row[1:]
    return result


def verify(work, state, answers, traces):
    source = read_workbook(HERE / "fixtures" / ID / FILENAME)
    actual = read_workbook(work / FILENAME)
    expected = json.loads((HERE / "references" / ID / "expected.json").read_text())
    if not actual or set(actual) != set(source):
        return checked({"saved_workbook": False})
    review, orders = actual["Review"]["rows"], actual["Purchase Orders"]["rows"]
    old = source["Purchase Orders"]["rows"]
    return checked({
        "all_eight_decisions_and_totals": bool(review) and review[0] == source["Review"]["rows"][0]
            and keyed(review[1:], 3) == expected["review"],
        "approved_orders_only": keyed(orders[len(old):], 7) == expected["orders"],
        "existing_orders_preserved": orders[:len(old)] == old,
        "team_requests_preserved": all(actual[name]["rows"] == source[name]["rows"]
                                       for name in source if name not in {"Review", "Purchase Orders"}),
        "message_history_preserved": all((work / name).is_file() and digest(work / name) == sha
                                         for name, sha in state["sha256"].items() if name != FILENAME),
    })
