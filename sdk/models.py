"""
SDK 数据模型定义
定义智能体内部使用的数据结构
"""

from typing import Callable, Optional


class TaskHandler:
    """任务处理器包装类"""
    def __init__(self, func: Callable[[str], str], name: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__

    async def handle(self, task: str) -> str:
        """处理任务"""
        # 如果是协程函数，用 await
        if hasattr(self.func, '__code__') and hasattr(self.func.__code__, 'co_flags'):
            import inspect
            if inspect.iscoroutinefunction(self.func):
                return await self.func(task)
        return self.func(task)
