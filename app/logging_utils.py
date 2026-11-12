# -*- coding: utf-8 -*-
"""日志配置。

修复旧实现的三个问题：
  1. RotatingFileHandler 是 StreamHandler 子类，旧去重判断导致 console handler 永远挂不上
  2. 直接覆盖 uvicorn/fastapi 的 handlers，重复调用会泄漏文件句柄
  3. 日志路径隐式依赖 cwd，源码态与打包态落盘位置不一致
现在路径由 app.paths 显式给出，配置幂等，子 logger 统一 propagate 到 root。
"""
import logging
import threading
from logging.handlers import RotatingFileHandler

from app import paths

_lock = threading.Lock()
_configured = False
_marker = "_aw_handler"

FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"


def _level(value: str) -> int:
    return getattr(logging, str(value).upper(), logging.INFO)


def setup_logging(level: str | None = None) -> logging.Logger:
    """幂等地初始化日志；重复调用只更新级别，不新建 handler。"""
    global _configured
    from app.config import get_settings

    with _lock:
        settings = get_settings()
        log_level = _level(level or settings.log_level)
        root = logging.getLogger()
        root.setLevel(log_level)

        if not _configured:
            formatter = logging.Formatter(FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
            log_file = paths.log_path()

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=settings.log_max_size,
                backupCount=settings.log_backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            setattr(file_handler, _marker, "file")

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            setattr(console_handler, _marker, "console")

            # 移除本模块此前挂的 handler（幂等保护），保留第三方 handler
            for handler in list(root.handlers):
                if hasattr(handler, _marker):
                    root.removeHandler(handler)
                    handler.close()
            root.addHandler(file_handler)
            root.addHandler(console_handler)

            # uvicorn / fastapi 交给 root 统一输出，不再各自持有文件句柄
            for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
                child = logging.getLogger(name)
                child.handlers.clear()
                child.propagate = True
                child.setLevel(log_level)

            _configured = True
            root.info(f"日志已初始化: {log_file} (level={logging.getLevelName(log_level)})")
        else:
            for handler in root.handlers:
                handler.setLevel(log_level)

    return logging.getLogger(__name__)


def set_log_level(value: str) -> None:
    """设置页改日志级别后即时生效（无需重启）"""
    level = _level(value)
    root = logging.getLogger()
    with _lock:
        root.setLevel(level)
        for handler in root.handlers:
            handler.setLevel(level)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
            logging.getLogger(name).setLevel(level)
    root.info(f"日志级别已切换为 {logging.getLevelName(level)}")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
