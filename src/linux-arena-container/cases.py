"""Two fixed, read-only cases. References stay outside the task materials."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = {
    "logs": {
        "files": ["app.log"],
        "instruction": (
            "读取 app.log。每行第二列是日志级别，只统计该列严格等于 ERROR 的行，"
            "不要把消息正文中的 ERROR 算进去。返回 error_count（整数）、"
            "error_request_ids（按日志顺序排列的 request_id 字符串数组）、"
            "error_codes（按日志顺序排列的 code 字符串数组，保留重复值）。"
        ),
        "expected": {
            "error_count": 3,
            "error_request_ids": ["r02", "r04", "r07"],
            "error_codes": ["E_DB", "E_UPSTREAM", "E_DB"],
        },
    },
    "config": {
        "files": ["before.conf", "after.conf"],
        "instruction": (
            "比较 before.conf 与 after.conf 的 key=value 配置。返回 changes 对象，"
            "仅包含值发生变化的配置项，每项的值为 {\"before\": 原字符串值, "
            "\"after\": 新字符串值}。所有配置值都使用字符串，不包含未变化项。"
        ),
        "expected": {
            "changes": {
                "timeout": {"before": "30", "after": "60"},
                "debug": {"before": "false", "after": "true"},
            }
        },
    },
}


def make_request(case_id, run_id, materials, device):
    return (
        f"请由 Galaxy 自行规划并交给 LinuxAgent 完成以下只读任务。"
        f"唯一目标设备是 {device}（Linux）。本轮标识为 {run_id}。\n"
        f"素材目录：{materials}\n{CASES[case_id]['instruction']}\n"
        "必须通过 Linux MCP 实际读取本轮素材，不修改文件。仅访问上述素材目录，"
        "不要读取评测程序、标准答案或其他运行日志。当前工具支持读取、搜索、比较，"
        "不支持 shell 管道、重定向或任意脚本。diff 退出码 1 表示发现差异。\n"
        "最终设备子任务的 result 必须是包含上述字段和 run_id 的一个纯 JSON 对象，"
        f"其中 run_id 为 \"{run_id}\"；不要 Markdown 或额外说明。"
        "Galaxy 应保留设备实际返回的完整 JSON，不要仅返回完成声明。"
    )


def check_answer(case_id, run_id, raw):
    """Parse only the actual final device result; never search prompts for answers."""
    try:
        answer = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError) as exc:
        return {"passed": False, "error": f"Invalid JSON answer: {exc}"}
    expected = {"run_id": run_id, **CASES[case_id]["expected"]}
    # JSON serialization preserves distinctions such as true vs 1 and 3.0 vs 3.
    passed = json.dumps(answer, sort_keys=True) == json.dumps(expected, sort_keys=True)
    return {"passed": passed, "actual": answer, "expected": expected}
