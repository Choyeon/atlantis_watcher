# -*- coding: utf-8 -*-
"""命令执行与电源控制路由。

架构优化：
  - 异常映射统一交给 app.factory 的全局 handler（旧版每个端点复制一段 try/except）
  - 所有 subprocess / Win32 同步调用走线程池，不再阻塞 asyncio event loop
  - 去掉未使用的 ShutdownRequest 死导入
"""
import asyncio

from fastapi import APIRouter, HTTPException, status

from app.logging_utils import get_logger
from app.models import BaseResponse, CommandRequest
from app.services.command_service import CommandService

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["commands"])


def _pack(result, message: str) -> BaseResponse:
    """CommandResponse / dict 统一包装成 BaseResponse（输出保持在 data 里）"""
    data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    return BaseResponse(
        success=bool(data.get("success", True)),
        message=message,
        data=data,
    )


@router.post("/cmd")
async def execute_command(request: CommandRequest) -> BaseResponse:
    logger.info(f"收到命令执行请求: {request.command}, PowerShell: {request.is_powershell}")
    result = await asyncio.to_thread(CommandService.execute_command, request)
    return _pack(result, "命令执行完成")


@router.post("/shutdown")
async def shutdown() -> BaseResponse:
    result = await asyncio.to_thread(CommandService.shutdown_system)
    return _pack(result, "关机命令已执行")


@router.post("/shutdown/{seconds}")
async def shutdown_with_delay(seconds: int) -> BaseResponse:
    if seconds < 0 or seconds > 86400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "延迟时间必须在 0-86400 秒之间"},
        )
    result = await asyncio.to_thread(CommandService.shutdown_system, seconds)
    return _pack(result, f"延迟 {seconds} 秒关机命令已执行")


@router.post("/cancel")
async def cancel_shutdown() -> BaseResponse:
    result = await asyncio.to_thread(CommandService.cancel_shutdown)
    return _pack(result, "取消关机命令已执行")


@router.post("/reboot")
async def reboot() -> BaseResponse:
    result = await asyncio.to_thread(CommandService.restart_system)
    return _pack(result, "重启命令已执行")


@router.post("/lock")
async def lock_screen() -> BaseResponse:
    result = await asyncio.to_thread(CommandService.lock_screen)
    return _pack(result, result.get("message", "屏幕已锁定"))


@router.post("/logout")
async def logout() -> BaseResponse:
    result = await asyncio.to_thread(CommandService.logout_system)
    return _pack(result, "注销命令已执行")


@router.post("/monitor/off")
async def turn_off_monitor() -> BaseResponse:
    """关闭显示器：仅熄屏，系统与后台服务继续运行"""
    result = await asyncio.to_thread(CommandService.turn_off_monitor)
    return _pack(result, result.get("message", "已关闭显示器"))


@router.post("/monitor/on")
async def turn_on_monitor() -> BaseResponse:
    """点亮显示器：供手机端远程恢复熄屏后的画面"""
    result = await asyncio.to_thread(CommandService.turn_on_monitor)
    return _pack(result, result.get("message", "已点亮显示器"))
