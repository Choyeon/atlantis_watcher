# -*- coding: utf-8 -*-
"""业务异常类型。

只保留实际被抛出 / 捕获的类型。已删除从未引用的 ProcessOperationError、
ConfigurationError、NetworkError、WebSocketError，以及与内置异常同名、
从未被 import 的自定义 PermissionError（后者会误导 except 语义）。
"""
from typing import Optional, Dict, Any


class AtlantisWatcherException(Exception):
    """应用基础异常：由 app.factory 的全局 handler 统一映射为 HTTP 响应"""

    def __init__(self, message: str, error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class SystemOperationError(AtlantisWatcherException):
    """系统操作异常"""


class FileOperationError(AtlantisWatcherException):
    """文件操作异常"""


class CommandExecutionError(AtlantisWatcherException):
    """命令执行异常（映射到 HTTP 400）"""


class ValidationError(AtlantisWatcherException):
    """数据验证异常"""
