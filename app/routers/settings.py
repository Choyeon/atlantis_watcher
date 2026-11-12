# -*- coding: utf-8 -*-
"""用户设置 API。

GET  /api/settings          读取设置 + 字段元信息 + 自启真实状态 + 运行时信息
PUT  /api/settings          局部更新（持久化、校验、联动平台能力）
POST /api/settings/restart  重启 HTTP 服务（改端口/监听地址后使用）
"""
import asyncio

from fastapi import APIRouter, Body, HTTPException, status

from app.logging_utils import get_logger
from app.models import BaseResponse
from app.runtime import get_context

logger = get_logger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", summary="读取设置")
async def read_settings() -> BaseResponse:
    return BaseResponse(success=True, message="设置读取成功", data=get_context().settings_snapshot())


@router.put("", summary="更新设置")
async def update_settings(payload: dict = Body(default_factory=dict)) -> BaseResponse:
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "请求体必须是非空的设置对象"},
        )
    try:
        result = await asyncio.to_thread(get_context().apply_settings, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": str(exc)},
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "message": f"设置写入失败: {exc}"},
        ) from exc

    message = "设置已保存"
    if result["requires_restart"]:
        message += "；端口/监听地址需重启服务后生效"
    if result["warning"]:
        message += f"；{result['warning']}"
    return BaseResponse(success=True, message=message, data=result)


@router.post("/restart", summary="重启 HTTP 服务")
async def restart_service() -> BaseResponse:
    ok = await asyncio.to_thread(get_context().restart_server)
    return BaseResponse(
        success=ok,
        message="服务已重启" if ok else "服务重启失败，请查看日志",
        data={"runtime": get_context().runtime_info()},
    )
