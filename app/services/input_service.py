# -*- coding: utf-8 -*-
"""远程输入注入服务 —— 屏幕共享的「操控」半边。

设计要点：

1. **坐标归一化**：前端一律发送 0..1 的归一化坐标，后端乘以真实屏幕尺寸。
   网页窗口、APK 横屏全屏、object-fit:contain 产生的黑边、不同 DPI
   都由此统一，避免出现「看到的画面位置」与「实际点击位置」错位。
2. **不阻塞事件循环**：本模块全部是同步 Win32 / GDI 调用，由路由层用
   asyncio.to_thread 执行（与 /ws/screen 的截屏编码同一套路）。
3. **延迟导入**：pyautogui 是重量级原生依赖，只在首次真正注入输入时加载。
4. **能力收敛**：按键名走白名单、文本限长、坐标限幅、滚轮限幅；
   总开关由 settings.remote_control_enabled 控制（路由层每次事件都检查，
   因此设置页关闭后无需重连即刻生效）。
"""
import logging
from typing import Any, Dict, List, Tuple

from app.models import ControlEvent
from app.platform import windows as platform

logger = logging.getLogger(__name__)

# pyautogui 认识的命名键（前端只发送这些名字）
NAMED_KEYS = frozenset({
    "enter", "esc", "escape", "tab", "space", "backspace", "delete", "insert",
    "up", "down", "left", "right", "home", "end", "pageup", "pagedown",
    "ctrl", "alt", "shift", "win", "capslock", "numlock", "printscreen", "pause",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
})

# 允许的单字符标点（pyautogui 可按键名直接输入）
PUNCT_KEYS = frozenset(set("`-=[]\\;',./"))

_COORD_EVENTS = frozenset({"move", "down", "up", "click", "dblclick", "wheel"})
_MAX_WHEEL = 12


def _screen_size() -> Tuple[int, int]:
    import pyautogui
    size = pyautogui.size()
    return int(size.width), int(size.height)


def _pixel(event: ControlEvent, width: int, height: int) -> Tuple[int, int]:
    """归一化坐标 → 真实屏幕像素（最后一像素也要能点到）"""
    if event.x is None or event.y is None:
        raise ValueError("该输入事件缺少归一化坐标 x / y")
    px = int(round(min(max(event.x, 0.0), 1.0) * (width - 1)))
    py = int(round(min(max(event.y, 0.0), 1.0) * (height - 1)))
    return px, py


def _validate_keys(raw: str) -> List[str]:
    """把 'ctrl+c' 这类组合键拆开并逐个白名单校验"""
    parts = [part.strip().lower() for part in raw.split("+") if part.strip()]
    if not parts or len(parts) > 4:
        raise ValueError("组合键格式不合法")
    for part in parts:
        if part not in NAMED_KEYS and part not in PUNCT_KEYS and not (len(part) == 1 and part.isalnum()):
            raise ValueError(f"不支持的按键: {part}")
    return parts


def _key_action(action: str, parts: List[str]) -> None:
    import pyautogui
    if action == "key":
        if len(parts) == 1:
            pyautogui.press(parts[0])
        else:
            pyautogui.hotkey(*parts)
    elif action == "keydown":
        pyautogui.keyDown(parts[0])
    else:
        pyautogui.keyUp(parts[0])


def _paste_text(text: str) -> None:
    """中文等非 ASCII 文本走剪贴板粘贴（pyautogui.write 只能打 ASCII）。"""
    import pyautogui
    if not platform.copy_to_clipboard(text):
        raise RuntimeError("写入系统剪贴板失败，无法粘贴文本")
    pyautogui.hotkey("ctrl", "v")


class InputService:
    """把一条 ControlEvent 翻译成真实输入。"""

    @staticmethod
    def apply(event: ControlEvent) -> Dict[str, Any]:
        import pyautogui

        # 关闭保险丝（鼠标甩到屏幕角落时抛异常）与每次调用后的默认 0.1s 停顿，
        # 否则连续拖动会被拖成幻灯片。
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0

        width, height = _screen_size()
        kind = event.type

        if kind in _COORD_EVENTS:
            px, py = _pixel(event, width, height)
            pyautogui.moveTo(px, py, duration=0)

            if kind == "down":
                pyautogui.mouseDown(button=event.button)
            elif kind == "up":
                pyautogui.mouseUp(button=event.button)
            elif kind in ("click", "dblclick"):
                clicks = 2 if kind == "dblclick" else event.clicks
                pyautogui.click(px, py, clicks=clicks, interval=0, button=event.button)
            elif kind == "wheel":
                steps = int(max(-_MAX_WHEEL, min(_MAX_WHEEL, event.delta)))
                if steps:
                    # 前端 deltaY 向下为正；pyautogui.scroll 正数向上，故取反由前端完成
                    pyautogui.scroll(steps)

        elif kind in ("key", "keydown", "keyup"):
            if not event.key:
                raise ValueError("按键事件缺少 key")
            _key_action(kind, _validate_keys(event.key))

        elif kind in ("text", "paste"):
            text = event.text or ""
            if not text:
                raise ValueError("文本事件缺少 text")
            if kind == "paste" or any(ord(ch) > 127 for ch in text):
                _paste_text(text)
            else:
                pyautogui.write(text, interval=0)
        else:  # pragma: no cover - Pydantic Literal 已挡住
            raise ValueError(f"不支持的事件类型: {kind}")

        return {
            "ok": True,
            "type": kind,
            "screen": {"width": width, "height": height},
        }
