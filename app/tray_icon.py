# -*- coding: utf-8 -*-
"""系统托盘（重构版）。

改进点：
  1. 标题与菜单直接显示「IP:端口」完整访问地址，不再只显示裸 IP 或中文错误串
  2. 菜单只有一处构建逻辑（旧版在 refresh_ip / setup_tray_icon 各写一份）
  3. 持有 AppContext：重启服务 / 退出 / 自启开关都是真实动作，不再是空壳回调
  4. 后台轮询网络变化自动刷新，无需手动点「刷新」
  5. 支持显示/隐藏切换与优雅停止，配合 bootstrap 走 should_exit 而非 os._exit(0)
"""
import os
import threading
import webbrowser

import pystray
from PIL import Image, ImageDraw

from app import paths
from app.logging_utils import get_logger
from app.platform import windows as platform
from app.runtime import AppContext

logger = get_logger(__name__)


def create_default_icon() -> Image.Image:
    """无图标文件时的兜底：与品牌真源一致的极简「声呐眼」。

    几何按 tools/brand_assets.py 的 0-100 归一化坐标乘 0.64（64px 画布）。
    """
    u = 0.64
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def p(v: float) -> int:
        return int(round(v * u))

    draw.rounded_rectangle([0, 0, 63, 63], radius=p(22), fill=(11, 18, 32, 255))
    draw.arc([p(22), p(24), p(76), p(78)], start=20, end=300,
             fill=(53, 214, 189, 255), width=p(9))
    draw.ellipse([p(40.5), p(42.5), p(57.5), p(59.5)], fill=(53, 214, 189, 255))
    draw.ellipse([p(73.4), p(25.4), p(82.6), p(34.6)], fill=(245, 182, 66, 255))
    return img


def load_icon() -> Image.Image:
    """按 app.paths 提供的候选顺序加载图标，并从 ICO 中选托盘最佳尺寸帧。

    ICO 含 16..256 共 7 帧，各帧按尺寸做了 LOD 简化；pystray 直接拿
    PIL 默认帧（通常是最大帧）再缩小会丢掉小尺寸的优化，因此显式挑
    <=48px 的最大帧。
    """
    for candidate in paths.icon_candidates():
        try:
            if not candidate.is_file():
                continue
            img = Image.open(candidate)
            try:
                sizes = sorted(img.ico.sizes())
                preferred = max((s for s in sizes if s[0] <= 48), default=None)
                if preferred is not None:
                    img = img.ico.getimage(preferred)
            except (AttributeError, KeyError, OSError):
                pass  # 非 ICO（如 PNG）时直接用原图
            return img.convert("RGBA") if img.mode != "RGBA" else img.copy()
        except Exception as exc:
            logger.debug(f"图标读取失败 {candidate}: {exc}")
    logger.warning("未找到图标文件，使用内置图标")
    return create_default_icon()


class TrayManager:
    """托盘管理器；所有状态来自 AppContext，自身不复制配置"""

    def __init__(self, context: AppContext, poll_interval: int = 30):
        self.context = context
        self.icon: pystray.Icon | None = None
        self.visible = False
        self.poll_interval = poll_interval
        self._monitor_thread: threading.Thread | None = None
        self._last_endpoint: tuple[str, int] | None = None

    # ---------- 展示 ----------
    def title(self) -> str:
        ip, port = self.context.endpoint()
        return f"Atlantis Watcher · {ip}:{port}\n点击打开管理页面"

    def _build_menu(self) -> pystray.Menu:
        ip, port = self.context.endpoint()
        url = f"http://{ip}:{port}"
        auto_status = platform.autostart_status()

        return pystray.Menu(
            pystray.MenuItem(
                f"访问地址  {ip}:{port}",
                lambda icon, item: None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("打开管理页面", self._open_web),
            pystray.MenuItem("打开设置页", self._open_settings),
            pystray.MenuItem("复制访问地址", self._copy_address),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "开机自启动",
                self._toggle_autostart,
                checked=lambda item: platform.autostart_status().get("enabled", False),
                enabled=auto_status["supported"],
            ),
            pystray.MenuItem("查看运行日志", self._open_log),
            pystray.MenuItem("刷新网络地址", self.refresh),
            pystray.MenuItem("重启服务", self._restart_service),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._exit),
        )

    def refresh(self) -> None:
        """重建提示与菜单（地址或状态变化后调用）"""
        self.context.invalidate_address_cache()
        if self.icon is None:
            return
        try:
            self.icon.title = self.title()
            self.icon.menu = self._build_menu()
            self._last_endpoint = self.context.endpoint()
        except Exception as exc:
            logger.error(f"刷新托盘失败: {exc}")

    def set_visible(self, enabled: bool) -> None:
        self.visible = bool(enabled)
        if self.icon is not None:
            try:
                self.icon.visible = bool(enabled)
            except Exception as exc:
                logger.debug(f"切换托盘可见性失败: {exc}")

    # ---------- 菜单动作 ----------
    def _open_web(self, icon=None, item=None) -> None:
        webbrowser.open(self.context.url())

    def _open_settings(self, icon=None, item=None) -> None:
        webbrowser.open(f"{self.context.url()}/#/settings")

    def _open_log(self, icon=None, item=None) -> None:
        log_file = paths.log_path()
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(log_file))
            else:
                webbrowser.open(log_file.as_uri())
        except Exception as exc:
            logger.error(f"打开日志失败: {exc}")

    def _copy_address(self, icon=None, item=None) -> None:
        url = self.context.url()
        ok = platform.copy_to_clipboard(url)
        self._notify(f"已复制 {url}" if ok else f"复制失败，请手动记下：{url}")

    def _toggle_autostart(self, icon=None, item=None) -> None:
        current = platform.autostart_status().get("enabled", False)
        try:
            self.context.apply_settings({"auto_start": not current})
            self.refresh()
            self._notify(f"开机自启动已{'开启' if not current else '关闭'}")
        except Exception as exc:
            logger.error(f"切换开机自启动失败: {exc}")
            self._notify(f"切换失败: {exc}")

    def _restart_service(self, icon=None, item=None) -> None:
        # join 最长 10 秒，放到后台线程避免卡住托盘消息循环
        def worker():
            ok = self.context.restart_server()
            self.refresh()
            self._notify("服务已重启" if ok else "服务重启失败，请查看日志")

        threading.Thread(target=worker, name="aw-tray-restart", daemon=True).start()
        self._notify("正在重启服务…")

    def _exit(self, icon=None, item=None) -> None:
        logger.info("托盘菜单请求退出")
        self.context.request_shutdown()

    def _notify(self, message: str) -> None:
        if self.icon is not None and hasattr(self.icon, "notify"):
            try:
                self.icon.notify(message)
            except Exception:
                pass

    # ---------- 生命周期 ----------
    def run(self) -> None:
        """阻塞运行托盘（Windows 需要主线程消息循环）。

        若设置为隐藏托盘，则主线程改为等待退出事件，服务仍照常运行。
        """
        if not self.context.store.data.show_tray:
            logger.info("托盘已设置为隐藏，主线程转为等待退出事件")
            self.context.shutdown_event.wait()
            return

        self.icon = pystray.Icon("AtlantisWatcher", load_icon(), self.title(), self._build_menu())
        self.visible = True
        self._last_endpoint = self.context.endpoint()
        self._start_monitor()

        if self.context.store.data.notify_on_start:
            self._notify(f"Atlantis Watcher 已启动 · {self.context.url()}")
        try:
            self.icon.run()
        finally:
            self.visible = False
            logger.info("托盘消息循环已结束")

    def _start_monitor(self) -> None:
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, name="aw-tray-monitor", daemon=True
        )
        self._monitor_thread.start()

    def _monitor_loop(self) -> None:
        """网络切换 / 改端口后自动刷新托盘显示"""
        while not self.context.shutdown_event.wait(self.poll_interval):
            try:
                self.context.invalidate_address_cache()
                current = self.context.endpoint()
                if current != self._last_endpoint:
                    logger.info(f"检测到访问地址变化: {self._last_endpoint} → {current}")
                    self.refresh()
            except Exception as exc:
                logger.debug(f"托盘网络轮询异常: {exc}")

    def stop(self) -> None:
        """优雅停止（幂等）"""
        self.visible = False
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception as exc:
                logger.debug(f"停止托盘图标异常: {exc}")
