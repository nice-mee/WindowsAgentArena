"""Log statistics. Version 2 removes evaluator-specific answer instructions."""
import re
from .common import setup_inputs, verify_readonly, judge_structured, structured, checked

ID = "logs"
DIFFICULTY = 'easy'
MODE = "cli"
VERSION = "3"
REQUEST_VERSION = "2"
EXPECTED = {"error_count": 3, "error_request_ids": ["r02", "r04", "r07"],
            "error_codes": ["E_DB", "E_UPSTREAM", "E_DB"]}


def setup(work):
    return setup_inputs(ID, work)


def make_request(work):
    return (f"帮我看看 {work / 'app.log'} 里有多少条 ERROR 日志，"
            "把这些日志的 request_id 和 code 按出现顺序列出来，重复值也保留。")


def judge_answer(raw, expected):
    if isinstance(structured(raw), dict):
        return judge_structured(raw, expected)
    text = re.sub(r"[*`]", "", raw) if isinstance(raw, str) else ""
    counts = {int(n) for pattern in (
        r"ERROR\s*(?:级别)?\s*(?:日志)?\s*(?:总条数|数量|条数|共有|共|有)\s*[:：]?\s*(\d+)",
        r"(\d+)\s*条\s*ERROR",
    ) for n in re.findall(pattern, text, re.I)}
    pair_pattern = r"request_id\s*[=:：]\s*['\"]?([\w-]+)['\"]?[,，;；\s]+code\s*[=:：]\s*['\"]?([\w-]+)"
    blocks, current = [], []
    for line in text.splitlines() + [""]:
        pair = re.search(pair_pattern, line, re.ASCII)
        if pair:
            current.append(pair.groups())
        elif current:
            blocks.append(current)
            current = []
    expected_pairs = list(zip(expected["error_request_ids"], expected["error_codes"]))
    return checked({"error_count": counts == {expected["error_count"]},
                    "ordered_fields": bool(blocks) and all(block == expected_pairs for block in blocks)},
                   actual_counts=sorted(counts), actual_pairs=blocks,
                   reason="Compare explicit ERROR count and ordered request_id/code lines")


def verify(work, state, answers, traces):
    return verify_readonly(work, state, answers, traces, lambda raw: judge_answer(raw, EXPECTED))
