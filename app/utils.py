# -*- coding: utf-8 -*-
"""通用工具函数。

已删除死代码：get_lan_ip（只认 192.168 网段，已由 app.platform.windows 取代）、
format_bytes、limit_string_length，以及随之不再使用的 socket / NetworkError 导入。
"""
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.exceptions import FileOperationError

logger = logging.getLogger(__name__)


def format_timestamp(timestamp: float) -> str:
    """格式化时间戳为 ISO 格式字符串"""
    return datetime.fromtimestamp(timestamp).isoformat()


def is_text_file(file_path: str) -> bool:
    """检查文件是否为文本文件（以是否含空字节判断）"""
    try:
        with open(file_path, "rb") as f:
            return b"\0" not in f.read(1024)
    except Exception:
        return False


def get_file_type(extension: str) -> str:
    """根据扩展名判断文件类型"""
    extension = extension.lower()
    type_mapping = {
        "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"},
        "video": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"},
        "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg"},
        "text": {".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml", ".yml", ".yaml"},
        "executable": {".exe", ".msi", ".bat", ".cmd", ".sh"},
        "archive": {".zip", ".rar", ".7z", ".tar", ".gz"},
        "document": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"},
    }
    for file_type, extensions in type_mapping.items():
        if extension in extensions:
            return file_type
    return "file"


def safe_remove_file(file_path: str) -> bool:
    """安全删除文件"""
    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
            logger.info(f"文件已删除: {file_path}")
            return True
        raise FileOperationError(f"文件不存在: {file_path}")
    except PermissionError as e:
        raise FileOperationError(f"权限不足，无法删除文件: {file_path}", details={"error": str(e)})
    except Exception as e:
        raise FileOperationError(f"删除文件失败: {file_path}", details={"error": str(e)})


def safe_create_directory(dir_path: str) -> bool:
    """安全创建目录"""
    try:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.debug(f"目录已创建: {dir_path}")
        return True
    except Exception as e:
        logger.error(f"创建目录失败: {dir_path}, 错误: {str(e)}")
        return False


def validate_file_path(file_path: str, allowed_extensions: Optional[List[str]] = None) -> bool:
    """验证文件路径的安全性（路径遍历 + 扩展名白名单）"""
    normalized_path = os.path.normpath(file_path)
    if ".." in normalized_path or file_path.startswith("/"):
        return False
    if allowed_extensions:
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in allowed_extensions:
            return False
    return True


def calculate_execution_time(start_time: float) -> float:
    """计算执行耗时（秒）"""
    return round(time.time() - start_time, 3)


def sanitize_command(command: str, dangerous_commands: List[str]) -> bool:
    """检查命令是否命中危险操作黑名单"""
    command_lower = command.lower()
    for dangerous_cmd in dangerous_commands:
        if dangerous_cmd.lower() in command_lower:
            return False
    return True


def get_available_encodings() -> List[str]:
    """可用的文件编码列表"""
    return ["utf-8", "gbk", "gb2312", "latin-1", "ascii"]


def read_file_with_encoding(file_path: str,
                            encodings: Optional[List[str]] = None) -> tuple[str, str]:
    """尝试多种编码读取文件，返回 (内容, 命中的编码)"""
    if encodings is None:
        encodings = get_available_encodings()

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read(), encoding
        except UnicodeDecodeError:
            continue
        except Exception as e:
            raise FileOperationError(f"读取文件失败: {file_path}", details={"error": str(e)})

    raise FileOperationError(f"无法解码文件: {file_path}", details={"tried_encodings": encodings})
