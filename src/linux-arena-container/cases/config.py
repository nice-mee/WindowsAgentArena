"""Compare explicit before/after values in a structured or natural answer."""
import re
from .common import setup_inputs, verify_readonly, judge_structured, structured, checked

ID = "config"
DIFFICULTY = 'easy'
MODE = "cli"
VERSION = "3"
REQUEST_VERSION = "2"
EXPECTED = {"changes": {"timeout": {"before": "30", "after": "60"},
                        "debug": {"before": "false", "after": "true"}}}


def setup(work):
    return setup_inputs(ID, work)


def make_request(work):
    return (f"帮我比较 {work / 'before.conf'} 和 {work / 'after.conf'}，"
            "告诉我哪些配置值变了，以及修改前后的值。")


def judge_answer(raw, expected):
    if isinstance(structured(raw), dict):
        return judge_structured(raw, expected)
    text = re.sub(r"[*`]", "", raw) if isinstance(raw, str) else ""
    pattern = (r"^\s*(?:[-•]|\d+[.)])?\s*([A-Za-z_]\w*)\s*[:：]\s*"
               r"(?:修改前\s*[=:：]\s*|从\s*)?['\"]?([\w.-]+)['\"]?\s*"
               r"(?:->|→|改为|变为|到)\s*(?:修改后\s*[=:：]\s*)?['\"]?([\w.-]+)")
    matches = re.findall(pattern, text, re.M)
    changes = {key: {"before": before, "after": after} for key, before, after in matches}
    consistent = all(changes[key] == {"before": before, "after": after}
                     for key, before, after in matches)
    return checked({"configuration_changes": bool(matches) and consistent and changes == expected["changes"]},
                   actual=changes, expected=expected["changes"],
                   reason="Compare explicit key: before -> after statements")


def verify(work, state, answers, traces):
    return verify_readonly(work, state, answers, traces, lambda raw: judge_answer(raw, EXPECTED))
