# -*- coding: utf-8 -*-
"""用户偏好持久化。

设置写入 %LOCALAPPDATA%/AtlantisWatcher/settings.json，原子替换避免写一半损坏。
带校验（Pydantic）、线程锁、变更订阅，供设置 API 与托盘共用。
"""
import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Tuple

from pydantic import BaseModel, Field, ValidationError

from app.logging_utils import get_logger
from app.paths import settings_path

logger = get_logger(__name__)

# 修改后必须重启 HTTP 服务才能生效的字段
RESTART_REQUIRED_FIELDS = frozenset({"host", "port"})


class UserSettings(BaseModel):
    """可由用户在设置页修改的偏好。默认值即出厂设置。"""
    auto_start: bool = Field(default=False, description="开机自动启动")
    show_tray: bool = Field(default=True, description="显示系统托盘图标")
    start_minimized: bool = Field(default=True, description="启动后不自动打开管理页面")
    notify_on_start: bool = Field(default=False, description="启动完成时显示托盘通知")
    port: int = Field(default=26541, ge=1024, le=65535, description="服务端口")
    host: str = Field(default="0.0.0.0", description="监听地址")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO", description="日志级别")
    screen_share_fps: int = Field(default=15, ge=1, le=60, description="屏幕共享帧率")
    screen_share_quality: int = Field(default=70, ge=10, le=100, description="屏幕共享 JPEG 质量")
    remote_control_enabled: bool = Field(default=True, description="允许通过屏幕共享页面注入鼠标/键盘，关闭后仅可观看")
    require_admin: bool = Field(default=True, description="启动时检查管理员权限")

    model_config = {"validate_assignment": True, "extra": "ignore"}


class SettingsStore:
    """线程安全的偏好存储 + 变更通知"""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else settings_path()
        self._lock = threading.RLock()
        self._listeners: List[Callable[[UserSettings, set], None]] = []
        self.is_first_run = not self.path.exists()
        self._data = self._load()

    def _load(self) -> UserSettings:
        if not self.path.exists():
            logger.info("设置文件不存在，使用默认设置")
            return UserSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return UserSettings.model_validate(raw)
        except (json.JSONDecodeError, ValidationError, OSError) as exc:
            logger.warning(f"设置文件损坏({exc})，回退到默认设置")
            return UserSettings()

    @property
    def data(self) -> UserSettings:
        """返回当前偏好快照（调用方只读）"""
        with self._lock:
            return self._data.model_copy(deep=True)

    def save(self) -> None:
        """原子写盘（临时文件 + os.replace）"""
        with self._lock:
            payload = self._data.model_dump()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            logger.error(f"写入设置失败: {exc}")
            raise

    def subscribe(self, listener: Callable[[UserSettings, set], None]) -> None:
        """订阅变更；回调参数为 (新设置, 变更字段名集合)"""
        with self._lock:
            self._listeners.append(listener)

    def update(self, patch: Dict[str, Any]) -> Tuple[UserSettings, set]:
        """局部更新并持久化。

        Raises:
            ValueError: 含未知字段或值校验失败

        Returns:
            (最新设置, 变更字段名集合)
        """
        unknown = set(patch) - set(UserSettings.model_fields)
        if unknown:
            raise ValueError(f"未知设置项: {', '.join(sorted(unknown))}")

        with self._lock:
            current = self._data.model_dump()
            try:
                updated = UserSettings.model_validate({**current, **patch})
            except ValidationError as exc:
                raise ValueError(str(exc)) from exc
            changed = {key for key in patch if getattr(updated, key) != getattr(self._data, key)}
            self._data = updated
            listeners = list(self._listeners)

        if not changed:
            return updated.model_copy(deep=True), changed

        try:
            self.save()
        except OSError:
            # 落盘失败时回滚内存值，避免内存与磁盘不一致
            with self._lock:
                self._data = UserSettings.model_validate(current)
            raise

        for listener in listeners:
            try:
                listener(updated, changed)
            except Exception as exc:  # 订阅者异常不能阻断设置更新
                logger.error(f"设置变更订阅者异常: {exc}")

        logger.info(f"设置已更新: {', '.join(sorted(changed))}")
        return updated.model_copy(deep=True), changed
