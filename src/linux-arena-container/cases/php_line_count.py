"""OSWorld-derived recursive PHP line count; no shell setup script is run."""
import re

from .common import setup_inputs, verify_readonly, structured

ID = "php_line_count"
DIFFICULTY = 'easy'
MODE = "cli"
VERSION = "2"
REQUEST_VERSION = "1"


def setup(work):
    state = setup_inputs(ID, work)
    state["line_counts"] = {name: (work / name).read_bytes().count(b"\n")
                            for name in state["sha256"] if name.endswith(".php")}
    if not state["line_counts"]:
        raise ValueError("No PHP files in fixture")
    state["expected_total"] = sum(state["line_counts"].values())
    return state


def make_request(work):
    return f"{work / 'project'} 这个项目的 PHP 文件一共多少行？"


def judge_answer(raw, expected):
    if raw is None or raw == "" or (isinstance(raw, str) and not raw.strip()):
        return {"status": "failed", "reason": "Missing answer"}
    value = structured(raw)
    if type(value) is int:
        total = value
    elif isinstance(value, dict) and set(value) == {"total_lines"} and type(value["total_lines"]) is int:
        total = value["total_lines"]
    elif isinstance(raw, str):
        # Extract labelled totals, never search for the expected number. Several
        # consistent total statements are fine; conflict, uncertainty or negation
        # needs review. Per-file subtotals are not mistaken for the final answer.
        text = re.sub(r"[*`]", "", raw.strip())
        patterns = [r"(?:一共|总共|共|合计|总计)?\s*(\d+)\s*行[。.!！]?",
                    r"(?:这个项目的?\s*)?PHP\s*文件(?:一共|总共|共|合计|总计)(?:有)?\s*(\d+)\s*行[。.!！]?",
                    r"(?:There are\s+)?(\d+)\s+lines(?:\s+(?:in total|total))?[.!]?"]
        matches = [m for p in patterns if (m := re.fullmatch(p, text, re.IGNORECASE))]
        if matches:
            total = int(matches[0].group(1))
        else:
            uncertain = re.search(r"不是|并非|不确定|可能|预计|假设|如果|例如|示例|无法|失败|\b(?:not|uncertain|maybe|example|if|failed)\b", text, re.I)
            labels = [r"总行数\s*(?:为|是|[:：=])?\s*(\d+)\s*行?",
                      r"(?:总计|合计|一共|总共)\s*[:：=]?\s*(\d+)\s*行",
                      r"(?:total\s+(?:number\s+of\s+)?lines|line\s+count)\s*(?:is|[:=])?\s*(\d+)\b",
                      r"\b(\d+)\s+total\b"]
            totals = {int(value) for pattern in labels for value in re.findall(pattern, text, re.I)}
            if uncertain or len(totals) != 1:
                return {"status": "review_required", "expected": expected,
                        "reason": "No consistent explicit total, or qualified/conflicting answer"}
            total = totals.pop()
    else:
        return {"status": "review_required", "expected": expected, "reason": "Unrecognized answer"}
    return {"status": "passed" if total == expected else "failed", "actual": total, "expected": expected}


def verify(work, state, answers, traces):
    result = verify_readonly(work, state, answers, traces,
                             lambda raw: judge_answer(raw, state["expected_total"]))
    result["review_checklist"] = ["确认最终答案明确给出整个项目的 PHP 总行数", "按换行字节计数，不能漏掉子目录或混入其他文件类型", "对照本轮各文件读取/统计轨迹与 materials.json 中独立计算的总数"]
    return result
