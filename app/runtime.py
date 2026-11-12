# -*- coding: utf-8 -*-
"""运行期上下文：进程内唯一的状态与生命周期持有者。

过去 server / tray / 回调散落在 main() 的局部闭包里，托盘「重启服务」是空壳、
退出用 os._exit(0) 硬杀。这里把服务、托盘、设置、地址、优雅停机收敛到一个对象，
所有入口（HTTP API、托盘菜单、信号）都通过它操作进程。
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from app import __version__ as APP_VERSION
from app.config import Settings, apply_user_settings, get_settings
from app.logging_utils import get_logger, set_log_level
from app.paths import is_frozen, log_path, settings_path
from app.platform import windows as platform
from app.server import create_uvicorn_server, run_server
from app.settings_store import RESTART_REQUIRED_FIELDS, SettingsStore, UserSettings

logger = get_logger(__name__)


@dataclass
class AppContext:
    """进程级依赖容器（由 bootstrap 组装，注入 FastAPI 与托盘）"""

    store: SettingsStore
    settings: Settings = field(default_factory=get_settings)
    fastapi_app: Any = None
    server: Any = None
    server_thread: Optional[threading.Thread] = None
    tray: Any = None
    started_at: float = field(default_factory=time.time)
    shutdown_event: threading.Event = field(default_factory=threading.Event)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _ip: str = field(default="", repr=False)
    _ip_cached_at: float = field(default=0.0, repr=False)

    # ---------- 网络地址 ----------
    def primary_ip(self) -> str:
        """带 5 秒缓存的主 IP，避免 /health 被高频调用时反复探测"""
        with self._lock:
            if self._ip and time.monotonic() - self._ip_cached_at < 5:
                return self._ip
        ip = platform.primary_address() or "127.0.0.1"
        with self._lock:
            self._ip, self._ip_cached_at = ip, time.monotonic()
        return ip

    def endpoint(self) -> Tuple[str, int]:
        """返回 (IP, 端口)"""
        return self.primary_ip(), self.settings.port

    def url(self) -> str:
        ip, port = self.endpoint()
        return f"http://{ip}:{port}"

    def invalidate_address_cache(self) -> None:
        with self._lock:
            self._ip_cached_at = 0.0

    # ---------- 运行信息 ----------
    def runtime_info(self) -> Dict[str, Any]:
        ip, port = self.endpoint()
        return {
            "service": "Atlantis Watcher",
            "version": APP_VERSION,
            "status": "running",
            "host": self.settings.host,
            "port": port,
            "ip": ip,
            "url": f"http://{ip}:{port}",
            "addresses": platform.network_addresses(),
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "mode": "frozen" if is_frozen() else "source",
            "tray_visible": bool(self.tray and self.tray.visible),
            "auto_start": platform.autostart_status().get("enabled", False),
            "log_file": str(log_path()),
            "settings_file": str(settings_path()),
        }

    # ---------- 服务生命周期 ----------
    def start_server(self) -> bool:
        """在守护线程启动 Uvicorn；始终传入 app 实例，杜绝字符串导入重复建实例"""
        with self._lock:
            if self.fastapi_app is None:
                raise RuntimeError("FastAPI 应用尚未注入 AppContext")
            server = create_uvicorn_server(app=self.fastapi_app)
            thread = threading.Thread(
                target=run_server, args=(server,), name="aw-uvicorn", daemon=True
            )
            self.server, self.server_thread = server, thread
            thread.start()
        logger.info(f"服务线程已启动: {self.url()}")
        return True

    def restart_server(self, timeout: float = 10.0) -> bool:
        """真正重启 HTTP 服务：停旧实例 → 等端口释放 → 起新实例"""
        with self._lock:
            old_server, old_thread = self.server, self.server_thread
        if old_server is not None:
            old_server.should_exit = True
        if old_thread and old_thread.is_alive():
            old_thread.join(timeout=timeout)
            if old_thread.is_alive():
                logger.error("旧服务线程未能在超时内退出，重启中止")
                return False
        try:
            self.start_server()
            logger.info("HTTP 服务已重启")
            return True
        except Exception as exc:
            logger.exception(f"重启 HTTP 服务失败: {exc}")
            return False

    # ---------- 设置 ----------
    def apply_settings(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        """更新偏好、同步运行期配置、联动平台能力，返回最新快照"""
        user, changed = self.store.update(patch)
        apply_user_settings(user)

        warning = ""
        if "auto_start" in changed:
            try:
                platform.set_autostart(user.auto_start)
            except Exception as exc:
                warning = f"开机自启动设置失败: {exc}"
                logger.error(warning)
        if "log_level" in changed:
            set_log_level(user.log_level)
        if "show_tray" in changed and self.tray is not None:
            self.tray.set_visible(user.show_tray)
        if self.tray is not None:
            self.tray.refresh()

        return {
            "settings": user.model_dump(),
            "changed": sorted(changed),
            "requires_restart": bool(changed & RESTART_REQUIRED_FIELDS),
            "auto_start": platform.autostart_status(),
            "runtime": self.runtime_info(),
            "warning": warning,
        }

    def settings_snapshot(self) -> Dict[str, Any]:
        return {
            "settings": self.store.data.model_dump(),
            "fields": {
                name: {
                    "type": field.annotation.__name__ if hasattr(field.annotation, "__name__") else str(field.annotation),
                    "description": field.description or "",
                    "restart_required": name in RESTART_REQUIRED_FIELDS,
                }
                for name, field in UserSettings.model_fields.items()
            },
            "auto_start": platform.autostart_status(),
            "runtime": self.runtime_info(),
        }

    # ---------- 停机 ----------
    def request_shutdown(self) -> None:
        """请求退出：只置事件 + 停托盘，真正清理交给 shutdown()"""
        self.shutdown_event.set()
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception as exc:
                logger.debug(f"停止托盘时异常: {exc}")

    def shutdown(self) -> None:
        """优雅停机：should_exit → join → 停托盘 → flush 日志"""
        self.shutdown_event.set()
        with self._lock:
            server, thread, tray = self.server, self.server_thread, self.tray
        if server is not None:
            server.should_exit = True
        if thread and thread.is_alive():
            thread.join(timeout=8)
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass
        logger.info("=== Atlantis Watcher 已优雅停止 ===")
        logging.shutdown()


_context: Optional[AppContext] = None
_context_lock = threading.Lock()


def init_context(store: SettingsStore) -> AppContext:
    global _context
    with _context_lock:
        _context = AppContext(store=store)
        return _context


def get_context() -> AppContext:
    if _context is None:
        raise RuntimeError("AppContext 尚未初始化，请先调用 init_context()")
    return _context
