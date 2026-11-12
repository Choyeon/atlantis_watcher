# -*- coding: utf-8 -*-
"""
系统相关API路由
"""
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status
from app.logging_utils import get_logger
from app.decorators import async_log_exceptions
from app.models import BaseResponse, ProcessKillRequest, ProcessInfo, SystemInfo
from app.services.system_service import SystemService
from app.exceptions import SystemOperationError, AtlantisWatcherException

logger = get_logger(__name__)
router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info", response_model=SystemInfo)
@async_log_exceptions()
async def get_system_info() -> SystemInfo:
    """
    获取系统基本信息
    
    Returns:
        SystemInfo: 系统信息
    """
    logger.info("API请求 - 获取系统信息")
    
    try:
        return SystemService.get_system_info()
    except (SystemOperationError, AtlantisWatcherException) as e:
        logger.error(f"获取系统信息失败: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "message": e.message,
                "error_code": e.error_code
            }
        )


@router.get("/processes")
@async_log_exceptions()
async def get_processes() -> Dict[str, Any]:
    """
    获取系统进程列表
    
    Returns:
        Dict[str, Any]: 进程列表响应
    """
    logger.info("API请求 - 获取进程列表")
    
    try:
        processes = SystemService.get_processes()
        return {
            "success": True,
            "processes": [process.dict() for process in processes],
            "count": len(processes)
        }
    except (SystemOperationError, AtlantisWatcherException) as e:
        logger.error(f"获取进程列表失败: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "message": e.message,
                "error_code": e.error_code
            }
        )


@router.post("/kill-process")
@async_log_exceptions()
async def kill_process(request: ProcessKillRequest) -> BaseResponse:
    """
    终止指定进程
    
    Args:
        request: 进程终止请求
        
    Returns:
        BaseResponse: 操作结果
    """
    logger.info(f"API请求 - 终止进程: PID={request.pid}, force={request.force}")
    
    try:
        result = SystemService.kill_process(request.pid, request.force)
        return BaseResponse(
            success=result["success"],
            message=result["message"],
            data=result
        )
    except (SystemOperationError, AtlantisWatcherException) as e:
        logger.error(f"终止进程失败: {e.message}")
        
        # 根据错误类型返回不同的HTTP状态码
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if e.error_code == "PROCESS_NOT_FOUND":
            status_code = status.HTTP_404_NOT_FOUND
        elif e.error_code == "ACCESS_DENIED":
            status_code = status.HTTP_403_FORBIDDEN
            
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "message": e.message,
                "error_code": e.error_code
            }
        )
