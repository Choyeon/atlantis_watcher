# -*- coding: utf-8 -*-
"""远程操控通道。

/ws/control   主通道：低延迟、双向，客户端逐条发 ControlEvent，服务端回 ack/error
/api/control  REST 兜底：WebView 禁用 WebSocket 或做自动化验收时使用
GET /api/control/status  前端据此显示「操控是否可用」

安全说明：输入注入是高危能力，每一条事件都重新读取运行期开关
settings.remote_control_enabled，设置页关闭后无需重连即刻生效。
"""
import asyncio
import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.config import get_settings
from app.logging_utils import get_logger
from app.models import ControlEvent
from app.services.input_service import InputService

logger = get_logger(__name__)
router = APIRouter(tags=["control"])

_DISABLED_MESSAGE = "远程操控已在设置中关闭"


def _enabled() -> bool:
    return bool(get_settings().remote_control_enabled)


def _error(code: str, message: str) -> str:
    return json.dumps({"ok": False, "error": code, "message": message}, ensure_ascii=False)


@router.get("/api/control/status", summary="查询远程操控状态")
async def control_status():
    settings = get_settings()
    result = {
        "enabled": bool(settings.remote_control_enabled),
        "message": "" if settings.remote_control_enabled else _DISABLED_MESSAGE,
    }
    if settings.remote_control_enabled:
        try:
            size = await asyncio.to_thread(_screen_size_safe)
            result["screen"] = {"width": size[0], "height": size[1]}
        except Exception as exc:  # 仅信息展示，取不到尺寸不应让状态接口失败
            logger.debug(f"读取屏幕尺寸失败: {exc}")
            result["screen"] = None
    return result


def _screen_size_safe():
    from app.services.input_service import _screen_size
    return _screen_size()


def _apply(event: ControlEvent):
    """统一的执行 + 异常收敛，供 WS 与 REST 共用。"""
    if not _enabled():
        raise PermissionError(_DISABLED_MESSAGE)
    return InputService.apply(event)


@router.post("/api/control", summary="注入一条远程输入事件")
async def control_rest(event: ControlEvent):
    if not _enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"success": False, "message": _DISABLED_MESSAGE, "error_code": "REMOTE_CONTROL_DISABLED"},
        )
    try:
        return await asyncio.to_thread(_apply, event)
    except Exception as exc:
        logger.warning(f"远程输入执行失败: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": f"远程输入执行失败: {exc}", "error_code": "INPUT_FAILED"},
        ) from exc


@router.websocket("/ws/control")
async def control_websocket(websocket: WebSocket):
    """逐条接收输入事件；事件之间不保留状态，连接断开即视为操控结束。"""
    await websocket.accept()
    logger.info("远程操控通道已建立")
    await websocket.send_text(json.dumps({
        "ok": True, "type": "ready", "enabled": _enabled(),
        "message": "" if _enabled() else _DISABLED_MESSAGE,
    }, ensure_ascii=False))

    try:
        while True:
            raw = await websocket.receive_text()
            if not _enabled():
                await websocket.send_text(_error("REMOTE_CONTROL_DISABLED", _DISABLED_MESSAGE))
                continue
            try:
                event = ControlEvent.model_validate(json.loads(raw))
            except (ValueError, ValidationError) as exc:
                await websocket.send_text(_error("INVALID_EVENT", f"输入事件格式不合法: {exc}"))
                continue

            try:
                result = await asyncio.to_thread(_apply, event)
                await websocket.send_text(json.dumps(result, ensure_ascii=False))
            except Exception as exc:
                logger.warning(f"远程输入执行失败: {exc}")
                await websocket.send_text(_error("INPUT_FAILED", f"远程输入执行失败: {exc}"))
    except WebSocketDisconnect:
        logger.info("远程操控通道已断开")
    except Exception as exc:
        logger.warning(f"远程操控通道异常: {exc}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
