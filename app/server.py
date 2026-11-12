# -*- coding: utf-8 -*-
"""Uvicorn 服务器封装（只负责建实例与跑线程，生命周期归 AppContext）。"""
import threading
from typing import Any

import uvicorn
from uvicorn.config import Config

from app.config import get_settings
from app.logging_utils import get_logger

logger = get_logger(__name__)


def create_uvicorn_server(app: Any, host: str | None = None, port: int | None = None) -> uvicorn.Server:
    """创建 Uvicorn 实例。

    必须传入 app 对象：字符串导入路径会在打包态重新 import 入口模块，
    导致 FastAPI 实例被重复创建、路由重复注册。
    """
    settings = get_settings()
    actual_host = host or settings.host
    actual_port = port or settings.port
    logger.info(f"创建 Uvicorn 服务器: {actual_host}:{actual_port}")

    config = Config(
        app=app,
        host=actual_host,
        port=actual_port,
        log_config=None,          # 日志由 app.logging_utils 统一接管
        access_log=not settings.debug,
        timeout_keep_alive=30,
        limit_concurrency=200,
        ws_max_size=8 * 1024 * 1024,
        ws_ping_interval=20,
        ws_ping_timeout=20,
    )
    return uvicorn.Server(config)


def run_server(server: uvicorn.Server) -> None:
    """在线程内运行服务器（由 AppContext.start_server 调用）"""
    logger.info(f"启动 FastAPI 服务: {server.config.host}:{server.config.port} "
                f"(thread={threading.current_thread().name})")
    try:
        server.run()
        logger.info("FastAPI 服务已停止")
    except Exception as exc:
        logger.exception(f"运行 FastAPI 服务时发生错误: {exc}")
        raise
