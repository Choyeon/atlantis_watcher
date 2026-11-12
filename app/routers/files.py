# -*- coding: utf-8 -*-
"""
文件系统相关API路由
"""
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from app.logging_utils import get_logger
from app.decorators import async_log_exceptions
from app.models import (
    BaseResponse, FileOperationRequest, FileContentRequest, 
    DriveInfo, FileInfo
)
from app.services.file_service import FileService
from app.exceptions import (
    FileOperationError, ValidationError, AtlantisWatcherException
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/drives")
@async_log_exceptions()
async def get_drives() -> Dict[str, Any]:
    """
    获取系统驱动器列表
    
    Returns:
        Dict[str, Any]: 驱动器列表响应
    """
    logger.info("API请求 - 获取驱动器列表")
    
    try:
        drives = FileService.get_drives()
        return {
            "success": True,
            "drives": [drive.dict() for drive in drives],
            "count": len(drives)
        }
    except (FileOperationError, AtlantisWatcherException) as e:
        logger.error(f"获取驱动器列表失败: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "message": e.message,
                "error_code": e.error_code
            }
        )


@router.get("/list")
@async_log_exceptions()
async def list_files(path: str = "/") -> Dict[str, Any]:
    """
    获取指定目录下的文件和文件夹列表
    
    Args:
        path: 目录路径
        
    Returns:
        Dict[str, Any]: 文件列表响应
    """
    logger.info(f"API请求 - 列出目录文件: {path}")
    
    try:
        return FileService.list_files(path)
    except (FileOperationError, AtlantisWatcherException) as e:
        logger.error(f"列出目录文件失败: {e.message}")
        
        # 根据错误类型返回不同的HTTP状态码
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if e.error_code == "PATH_NOT_EXISTS":
            status_code = status.HTTP_404_NOT_FOUND
        elif e.error_code == "PERMISSION_DENIED":
            status_code = status.HTTP_403_FORBIDDEN
        elif e.error_code == "NOT_DIRECTORY":
            status_code = status.HTTP_400_BAD_REQUEST
            
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "message": e.message,
                "error_code": e.error_code
            }
        )


@router.get("/content")
@async_log_exceptions()
async def get_file_content(path: str) -> Dict[str, Any]:
    """
    获取文件内容
    
    Args:
        path: 文件路径
        
    Returns:
        Dict[str, Any]: 文件内容响应
    """
    logger.info(f"API请求 - 获取文件内容: {path}")
    
    try:
        return FileService.get_file_content(path)
    except (FileOperationError, ValidationError, AtlantisWatcherException) as e:
        logger.error(f"获取文件内容失败: {e.message}")
        
        # 根据错误类型返回不同的HTTP状态码
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if e.error_code == "FILE_NOT_EXISTS":
            status_code = status.HTTP_404_NOT_FOUND
        elif e.error_code == "IS_DIRECTORY":
            status_code = status.HTTP_400_BAD_REQUEST
        elif e.error_code == "FILE_TOO_LARGE":
            status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        elif e.error_code == "NOT_TEXT_FILE":
            status_code = status.HTTP_400_BAD_REQUEST
            
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "message": e.message,
                "error_code": e.error_code
            }
        )


@router.post("/content")
@async_log_exceptions()
async def save_file_content(request: FileContentRequest) -> BaseResponse:
    """
    保存文件内容
    
    Args:
        request: 文件内容请求
        
    Returns:
        BaseResponse: 保存结果
    """
    logger.info(f"API请求 - 保存文件内容: {request.path}")
    
    try:
        result = FileService.save_file_content(request)
        return BaseResponse(
            success=result["success"],
            message=result["message"],
            data=result
        )
    except (FileOperationError, ValidationError, AtlantisWatcherException) as e:
        logger.error(f"保存文件内容失败: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "message": e.message,
                "error_code": e.error_code
            }
        )


@router.post("/mkdir", response_model=BaseResponse)
@async_log_exceptions()
async def create_directory(request: Dict[str, str]) -> BaseResponse:
    """
    创建目录

    Args:
        request: 包含 path 的请求体

    Returns:
        BaseResponse: 操作结果
    """
    path = request.get("path")
    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "路径不能为空"}
        )

    logger.info(f"API请求 - 创建目录: {path}")

    try:
        result = FileService.create_directory(path)
        return BaseResponse(
            success=result["success"],
            message=result["message"],
            data=result
        )
    except (FileOperationError, ValidationError, AtlantisWatcherException) as e:
        logger.error(f"创建目录失败: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": e.message, "error_code": e.error_code}
        )


@router.post("/create", response_model=BaseResponse)
@async_log_exceptions()
async def create_file(request: Dict[str, str]) -> BaseResponse:
    """
    创建新文件

    Args:
        request: 包含 path 的请求体，可选 content

    Returns:
        BaseResponse: 操作结果
    """
    path = request.get("path")
    if not path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "路径不能为空"}
        )

    content = request.get("content", "")
    logger.info(f"API请求 - 创建文件: {path}")

    try:
        result = FileService.create_file(path, content)
        return BaseResponse(
            success=result["success"],
            message=result["message"],
            data=result
        )
    except (FileOperationError, ValidationError, AtlantisWatcherException) as e:
        logger.error(f"创建文件失败: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": e.message, "error_code": e.error_code}
        )


@router.get("/icon")
@async_log_exceptions()
async def get_file_icon(path: str) -> Dict[str, Any]:
    """
    获取文件图标

    Args:
        path: 文件路径

    Returns:
        Dict[str, Any]: 图标信息
    """
    logger.info(f"API请求 - 获取文件图标: {path}")

    try:
        return FileService.get_file_icon(path)
    except Exception as e:
        logger.error(f"获取文件图标失败: {str(e)}")
        return {"success": False, "icon_type": "emoji", "icon": "📄"}


@router.post("/operation")
@async_log_exceptions()
async def file_operation(request: FileOperationRequest) -> BaseResponse:
    """
    执行文件操作（重命名、删除、复制、移动）
    
    Args:
        request: 文件操作请求
        
    Returns:
        BaseResponse: 操作结果
    """
    logger.info(f"API请求 - 文件操作: {request.operation.value}, 路径: {request.path}")
    
    try:
        result = FileService.perform_file_operation(request)
        return BaseResponse(
            success=result["success"],
            message=result["message"],
            data=result
        )
    except (FileOperationError, ValidationError, AtlantisWatcherException) as e:
        logger.error(f"文件操作失败: {e.message}")
        
        # 根据错误类型返回不同的HTTP状态码
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if e.error_code == "PATH_NOT_EXISTS":
            status_code = status.HTTP_404_NOT_FOUND
        elif "validation" in e.error_code.lower() if e.error_code else False:
            status_code = status.HTTP_400_BAD_REQUEST
            
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "message": e.message,
                "error_code": e.error_code
            }
        )


@router.post("/execute")
@async_log_exceptions()
async def execute_file(request: Dict[str, str]) -> BaseResponse:
    """
    执行文件
    
    Args:
        request: 包含文件路径的请求
        
    Returns:
        BaseResponse: 执行结果
    """
    file_path = request.get("path")
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "文件路径不能为空"
            }
        )
    
    logger.info(f"API请求 - 执行文件: {file_path}")
    
    try:
        result = FileService.execute_file(file_path)
        return BaseResponse(
            success=result["success"],
            message=result["message"],
            data=result
        )
    except (FileOperationError, AtlantisWatcherException) as e:
        logger.error(f"执行文件失败: {e.message}")
        
        # 根据错误类型返回不同的HTTP状态码
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if e.error_code == "FILE_NOT_EXISTS":
            status_code = status.HTTP_404_NOT_FOUND
        elif e.error_code == "UNSUPPORTED_FILE_TYPE":
            status_code = status.HTTP_400_BAD_REQUEST
            
        raise HTTPException(
            status_code=status_code,
            detail={
                "success": False,
                "message": e.message,
                "error_code": e.error_code
            }
        )


@router.get("/download")
@async_log_exceptions()
async def download_file(path: str):
    """
    下载文件
    
    Args:
        path: 文件路径
        
    Returns:
        FileResponse: 文件响应
    """
    import os
    
    logger.info(f"API请求 - 下载文件: {path}")
    
    try:
        if not os.path.exists(path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "message": "文件不存在"
                }
            )
        
        if os.path.isdir(path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "message": "不能下载目录"
                }
            )
        
        return FileResponse(
            path=path,
            filename=os.path.basename(path),
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "message": f"下载文件失败: {str(e)}"
            }
        )


@router.post("/upload")
@async_log_exceptions()
async def upload_file(file: UploadFile = File(...), path: str = Form(...)) -> BaseResponse:
    """
    上传文件到指定路径
    
    Args:
        file: 上传的文件
        path: 目标路径
        
    Returns:
        BaseResponse: 上传结果
    """
    import os
    from app.utils import safe_create_directory
    
    logger.info(f"API请求 - 上传文件: {file.filename} 到 {path}")
    
    try:
        # 确保目标路径存在
        if not os.path.exists(path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "message": "目标路径不存在"
                }
            )
        
        if not os.path.isdir(path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "success": False,
                    "message": "目标路径不是目录"
                }
            )
        
        # 构建完整的文件路径
        file_path = os.path.join(path, file.filename)
        
        # 检查文件是否已存在，生成新名称
        if os.path.exists(file_path):
            base_name, ext = os.path.splitext(file.filename)
            counter = 1
            while os.path.exists(file_path):
                new_filename = f"{base_name}({counter}){ext}"
                file_path = os.path.join(path, new_filename)
                counter += 1
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # 获取文件信息
        file_size = os.path.getsize(file_path)
        
        logger.info(f"文件上传成功: {file_path}, 大小: {file_size} bytes")
        
        return BaseResponse(
            success=True,
            message="文件上传成功",
            data={
                "filename": os.path.basename(file_path),
                "path": file_path,
                "size": file_size
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "message": f"文件上传失败: {str(e)}"
            }
        )
