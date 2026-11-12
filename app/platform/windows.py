# -*- coding: utf-8 -*-
"""Windows 系统集成：UAC 提权、开机自启动、网络地址、剪贴板。

自启动统一走 HKCU Run 注册表项（标准库 winreg，可开关、可查询、不依赖 COM），
并负责清理旧版遗留在「启动」文件夹的同名快捷方式，避免双重启动。
"""
import os
import socket
import subprocess
import sys
from typing import Any, Dict, List, Optional

from app.logging_utils import get_logger

logger = get_logger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "AtlantisWatcher"
LEGACY_LNK_NAME = "AtlantisWatcher.lnk"


def is_windows() -> bool:
    return os.name == "nt"


def is_admin() -> bool:
    """当前进程是否具备管理员权限"""
    if not is_windows():
        return True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception as exc:
        logger.warning(f"管理员权限检测失败: {exc}")
        return False


def request_elevation() -> bool:
    """请求 UAC 提权并重启自身。返回 True 表示当前进程应退出。"""
    if not is_windows() or getattr(sys, "frozen", False):
        # 打包态由 exe manifest 声明 requireAdministrator，不再二次提权
        return False
    try:
        import ctypes
        params = subprocess.list2cmdline(sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        return True
    except Exception as exc:
        logger.error(f"请求 UAC 提权失败: {exc}")
        return False


def launch_command() -> str:
    """开机自启使用的命令行（冻结态=exe，源码态=python + main.py）"""
    exe = os.path.abspath(sys.executable)
    if getattr(sys, "frozen", False):
        return f'"{exe}"'
    entry = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "main.py")
    return f'"{exe}" "{entry}"'


def _reg_open(access: int):
    import winreg
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)


def autostart_status() -> Dict[str, Any]:
    """查询自启动真实状态（含注册表与目标路径）"""
    result: Dict[str, Any] = {
        "supported": is_windows(),
        "enabled": False,
        "source": "registry",
        "command": None,
        "legacy_shortcut": False,
    }
    if not is_windows():
        return result

    import winreg
    try:
        with _reg_open(winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE)
            result["enabled"] = bool(value)
            result["command"] = value
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning(f"读取自启动注册表失败: {exc}")

    result["legacy_shortcut"] = legacy_shortcut_path().exists()
    return result


def set_autostart(enabled: bool) -> Dict[str, Any]:
    """开启 / 关闭开机自启动，返回最新状态"""
    if not is_windows():
        raise RuntimeError("开机自启动仅支持 Windows")

    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass

    # 无论开关，都清理旧版启动文件夹快捷方式（旧机制会绕过设置造成重复启动）
    remove_legacy_shortcut()
    logger.info(f"开机自启动已{'开启' if enabled else '关闭'}")
    return autostart_status()


def legacy_shortcut_path():
    from pathlib import Path
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / LEGACY_LNK_NAME


def remove_legacy_shortcut() -> bool:
    """删除旧版写入「启动」文件夹的快捷方式"""
    from app.paths import user_data_dir
    path = legacy_shortcut_path()
    if not path.exists():
        return False
    try:
        # 移到数据目录留档，而不是直接抹掉，便于回溯
        archive = user_data_dir() / "legacy-startup-shortcut.lnk.bak"
        archive.write_bytes(path.read_bytes())
        path.unlink()
        logger.info(f"已移除旧版启动文件夹快捷方式，留档于 {archive}")
        return True
    except OSError as exc:
        logger.warning(f"清理旧版快捷方式失败: {exc}")
        return False


def primary_address() -> Optional[str]:
    """取默认路由出口的本机 IPv4；失败返回 None（不再返回中文错误串）"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.4)
            sock.connect(("223.5.5.5", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass
    addresses = network_addresses()
    return addresses[0]["ip"] if addresses else None


def network_addresses() -> List[Dict[str, str]]:
    """列出所有可用 IPv4（排除回环 / 链路本地），私有网段优先"""
    found: List[Dict[str, str]] = []
    try:
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family != socket.AF_INET:
                    continue
                ip = addr.address
                if ip.startswith("127.") or ip.startswith("169.254."):
                    continue
                private = ip.startswith(("192.168.", "10.")) or ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31
                found.append({"interface": iface, "ip": ip, "scope": "private" if private else "public"})
    except Exception as exc:
        logger.debug(f"枚举网卡地址失败: {exc}")

    found.sort(key=lambda item: (item["scope"] != "private", item["ip"]))
    # 按 IP 去重
    seen, unique = set(), []
    for item in found:
        if item["ip"] not in seen:
            seen.add(item["ip"])
            unique.append(item)
    return unique


def copy_to_clipboard(text: str) -> bool:
    """把文本写入 Windows 剪贴板（纯 ctypes，无子进程、无新依赖）"""
    if not is_windows():
        return False
    try:
        import ctypes
        CF_UNICODETEXT, GMEM_MOVEABLE, GMEM_ZEROINIT = 13, 0x0002, 0x0040
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32

        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_int
        user32.EmptyClipboard.restype = ctypes.c_int
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.CloseClipboard.restype = ctypes.c_int

        data = text.encode("utf-16-le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)

        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(handle)
            return False
        user32.EmptyClipboard()
        user32.SetClipboardData(CF_UNICODETEXT, handle)  # 成功后内存归系统所有，不要 GlobalFree
        user32.CloseClipboard()
        return True
    except Exception as exc:
        logger.debug(f"写入剪贴板失败: {exc}")
        return False
