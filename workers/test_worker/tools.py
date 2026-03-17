"""
计算工具集 - LangChain 工具定义
为计算智能体提供各种数学计算能力
"""

from langchain_core.tools import tool


@tool
def add(a: float, b: float) -> str:
    """执行加法运算。需要传入两个数字。"""
    return f"{a} + {b} = {a + b}"


@tool
def subtract(a: float, b: float) -> str:
    """执行减法运算。需要传入两个数字（第一个减去第二个）。"""
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
def calculate_power(base: float, exponent: float) -> str:
    """计算幂运算（base 的 exponent 次方）。需要传入底数和指数。"""
    result = base ** exponent
    return f"{base}^{exponent} = {result}"


@tool
def calculate_sqrt(n: float) -> str:
    """计算平方根。需要传入一个非负数。"""
    if n < 0:
        return "错误：不能计算负数的平方根"
    import math
    result = math.sqrt(n)
    return f"√{n} = {result}"


@tool
def calculate_absolute(n: float) -> str:
    """计算绝对值。需要传入一个数字。"""
    result = abs(n)
    return f"|{n}| = {result}"


@tool
def calculate_modulus(a: float, b: float) -> str:
    """计算取模运算（a 除以 b 的余数）。需要传入两个数字。"""
    if b == 0:
        return "错误：除数不能为 0"
    result = a % b
    return f"{a} mod {b} = {result}"


@tool
def calculate_expression(expression: str) -> str:
    """
    安全计算数学表达式。支持加减乘除、括号等运算。
    需要传入数学表达式字符串，例如 "12 * 3 + 5" 或 "(15 + 25) / 4"。
    """
    try:
        # 使用受限环境进行 eval，仅允许数学运算
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
