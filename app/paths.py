# -*- coding: utf-8 -*-
"""统一路径解析。

两类目录严格分离：
  - 资源目录（只读）：源码态为项目根，PyInstaller 态为 sys._MEIPASS
  - 数据目录（可写）：%LOCALAPPDATA%/AtlantisWatcher，日志/设置都落在这里

过去 main.py 靠 os.chdir() 隐式决定日志位置，tray_icon.py 另写一套图标探测；
本模块把两者收敛成唯一入口，任何模块都不应再自行拼资源路径。
"""
import os
import sys
from pathlib import Path

APP_DIR_NAME = "AtlantisWatcher"


def is_frozen() -> bool:
    """是否运行在 PyInstaller 冻结态"""
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    """资源根目录（源码态=项目根，冻结态=_MEIPASS）"""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parent.parent


def resolve_resource(*parts: str) -> Path:
    """解析只读资源的绝对路径"""
    return project_root().joinpath(*parts)


def executable_dir() -> Path:
    """可执行文件所在目录"""
    return Path(sys.executable).resolve().parent


def user_data_dir() -> Path:
    """可写的用户数据目录，不存在时自动创建"""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return user_data_dir() / "settings.json"


def log_path() -> Path:
    return user_data_dir() / "log.txt"


def dist_dir() -> Path:
    return resolve_resource("static", "dist")


def assets_dir() -> Path:
    return dist_dir() / "assets"


def static_dir() -> Path:
    return resolve_resource("static")


def icon_candidates() -> list[Path]:
    """按优先级返回图标候选路径"""
    candidates = []
    if is_frozen():
        candidates.append(executable_dir() / "icon.ico")
        candidates.append(resolve_resource("icon.ico"))
    candidates.append(resolve_resource("icon.ico"))
    candidates.append(Path("icon.ico"))
    # 去重且保持顺序
    seen, result = set(), []
    for item in candidates:
        key = str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
