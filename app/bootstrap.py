# -*- coding: utf-8 -*-
"""进程启动 / 停机编排。

把原先散在 main.py 的日志初始化、UAC、自启动、服务线程、托盘、退出
收敛成一条明确的生命周期链：

    setup_logging → 载入设置 → 权限 → 自启对齐 → 建应用 → 起服务 → 托盘阻塞
                                            ↓ 退出请求
                                    context.shutdown()（should_exit + join + flush）

不再有模块级 FastAPI 实例，不再用 os._exit(0) 硬杀进程。
"""
import sys
import webbrowser

from app import paths
from app.config import apply_user_settings, get_settings
from app.factory import create_app
from app.logging_utils import get_logger, set_log_level, setup_logging
from app.platform import windows as platform
from app.runtime import init_context
from app.settings_store import SettingsStore
from app.tray_icon import TrayManager

logger = get_logger(__name__)


def _reconcile_autostart(context) -> None:
    """让注册表状态与用户设置一致，并清理旧版启动文件夹快捷方式。

    首次运行且系统里已存在旧版自启时，继承「开启」，避免升级后行为突变。
    """
    store = context.store
    status = platform.autostart_status()

    if store.is_first_run and (status["enabled"] or status["legacy_shortcut"]):
        logger.info("检测到旧版自启动配置，继承为开启")
        store.update({"auto_start": True})
        apply_user_settings(store.data)

    target = store.data.auto_start
    if status["enabled"] != target:
        try:
            platform.set_autostart(target)
        except Exception as exc:
            logger.error(f"同步开机自启动失败: {exc}")
    platform.remove_legacy_shortcut()


def bootstrap() -> int:
    """启动整个进程，返回退出码"""
    # 日志必须最先初始化；路径由 app.paths 显式给出，不再依赖 os.chdir()
    setup_logging()
    logger.info("=== Atlantis Watcher 进程启动 ===")

    store = SettingsStore()
    apply_user_settings(store.data)
    set_log_level(store.data.log_level)
    logger.info(
        f"模式={'打包版' if paths.is_frozen() else '源码版'} | "
        f"设置={store.path} | 日志={paths.log_path()}"
    )

    settings = get_settings()
    skip_elevation = "--no-elevation" in sys.argv  # 仅用于本地调试/自动化
    if not skip_elevation and settings.require_admin and not platform.is_admin():
        logger.warning("未获得管理员权限，尝试 UAC 提权")
        if platform.request_elevation():
            return 0  # 提权进程已启动，当前进程退出
        logger.warning("提权未生效，继续以当前权限运行")

    context = init_context(store)
    _reconcile_autostart(context)

    app = create_app(context)
    context.fastapi_app = app
    try:
        context.start_server()
    except Exception as exc:
        logger.exception(f"启动 HTTP 服务失败: {exc}")
        return 1

    if not store.data.start_minimized:
        try:
            webbrowser.open(context.url())
        except Exception as exc:
            logger.debug(f"启动后打开管理页面失败: {exc}")

    tray = TrayManager(context)
    context.tray = tray
    try:
        tray.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    except Exception as exc:
        logger.exception(f"托盘运行异常，服务继续保活: {exc}")
        context.shutdown_event.wait()
    finally:
        context.shutdown()
    return 0
