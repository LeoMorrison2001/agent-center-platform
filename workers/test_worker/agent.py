"""
计算智能体 Worker - 基于 LangChain Agent (简化版)
使用 Sunday SDK 连接到平台，提供数学计算能力
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sdk import LangChainAgent
from langchain_core.tools import tool

# ==========================================
# 定义计算工具（自动收集）
# ==========================================

@tool
def add(a: float, b: float) -> str:
    """执行加法运算。需要传入两个数字。"""
    return f"{a} + {b} = {a + b}"


@tool
def subtract(a: float, b: float) -> str:
    """执行减法运算。需要传入两个数字（第一个减以第二个）。"""
    return f"{a} - {b} = {a - b}"


@tool
def multiply(a: float, b: float) -> str:
    """执行乘法运算。需要传入两个数字。"""
    return f"{a} × {b} = {a * b}"


@tool
def divide(a: float, b: float) -> str:
    """执行除法运算。需要传入两个数字（第一个除以第二个）。"""
    if b == 0:
        return "错误：除数不能为 0"
    return f"{a} ÷ {b} = {a / b}"


@tool
def calculate_expression(expression: str) -> str:
    """
    安全计算数学表达式。支持加减乘除、括号等运算。
    需要传入数学表达式字符串，例如 "12 * 3 + 5" 或 "(15 + 25) / 4"。
    """
    try:
        import math
        allowed_names = {
            **math.__dict__,
            'abs': abs,
            'round': round,
            'min': min,
            'max': max,
        }
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return f"计算结果: {expression} = {result}"
    except Exception as e:
        return f"计算出错: {str(e)}"


# ==========================================
# 创建 LangChain Agent Worker
# ==========================================

worker = LangChainAgent(
    agent_key="calculator"
    # 模型配置由平台统一管理，注册时自动下发
)

# 注册工具（使用 LangChain 的 @tool 装饰器定义的函数）
worker.register_langchain_tool(add)
worker.register_langchain_tool(subtract)
worker.register_langchain_tool(multiply)
worker.register_langchain_tool(divide)
worker.register_langchain_tool(calculate_expression)


# ==========================================
# 启动 Worker
# ==========================================
if __name__ == "__main__":
    worker.run()
