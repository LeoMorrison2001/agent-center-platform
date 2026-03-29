"""
计算智能体 Worker 示例。
使用当前仓库里的 AgentWorker SDK，提供一个最小可运行的计算服务。
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sdk import AgentWorker


worker = AgentWorker(agent_key="calculator")


@worker.on_task
def handle_task(task: str) -> str:
    """仅允许基础算术表达式，避免执行任意代码。"""
    expression = task.strip()
    if not expression:
        return "请输入要计算的表达式，例如: (12 + 3) * 4"

    if not re.fullmatch(r"[0-9+\-*/().\s]+", expression):
        return "仅支持数字、空格和 + - * / ( )"

    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"计算结果: {expression} = {result}"
    except Exception as exc:
        return f"计算失败: {exc}"


if __name__ == "__main__":
    worker.run()
