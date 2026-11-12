# -*- coding: utf-8 -*-
"""异常处理装饰器。

已删除全库无调用点的 measure_time / async_measure_time 及其 time 依赖。
异常统一 re-raise，由 FastAPI 全局 handler 转成结构化响应。
"""
import functools
import traceback
from typing import Any, Callable, TypeVar

from app.logging_utils import get_logger

logger = get_logger(__name__)
F = TypeVar("F", bound=Callable[..., Any])


def log_exceptions(reraise: bool = True, default_return: Any = None) -> Callable[[F], F]:
    """同步函数异常日志"""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                message = getattr(exc, "message", str(exc))
                logger.error(f"函数 {func.__name__} 异常: {message}")
                logger.error(f"异常堆栈: {traceback.format_exc()}")
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def async_log_exceptions(reraise: bool = True, default_return: Any = None) -> Callable[[F], F]:
    """异步函数异常日志"""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                message = getattr(exc, "message", str(exc))
                logger.error(f"异步函数 {func.__name__} 异常: {message}")
                logger.error(f"异常堆栈: {traceback.format_exc()}")
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator
