# -*- coding: utf-8 -*-
"""
文件服务模块
处理文件系统相关的业务逻辑
"""
import os
import shutil
import string
import subprocess
import ctypes
from ctypes import wintypes
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
import psutil

from app.config import get_settings
from app.models import (
    FileInfo, DriveInfo, FileOperationRequest, FileContentRequest,
    FileOperationType
)
from app.exceptions import FileOperationError, ValidationError
from app.utils import (
    get_file_type, format_timestamp, safe_remove_file, safe_create_directory,
    validate_file_path, read_file_with_encoding, is_text_file
)


logger = logging.getLogger(__name__)
settings = get_settings()


class FileService:
    """文件服务类"""
    
    @staticmethod
    def get_drives() -> List[DriveInfo]:
        """
        获取系统驱动器列表
        
        Returns:
            List[DriveInfo]: 驱动器信息列表
        """
        logger.debug("获取系统驱动器列表")
        drives = []
        
        try:
            if os.name == 'nt':  # Windows
                for letter in string.ascii_uppercase:
                    drive = f"{letter}:\\"
                    if os.path.exists(drive):
                        try:
                            usage = psutil.disk_usage(drive)
                            drives.append(DriveInfo(
                                name=f"{letter}盘",
                                path=drive,
                                type="drive",
                                total=usage.total,
                                used=usage.used,
                                free=usage.free
                            ))
                        except Exception:
                            # 某些驱动器可能无法访问
                            drives.append(DriveInfo(
                                name=f"{letter}盘",
                                path=drive,
                                type="drive"
                            ))
            else:  # Linux/Mac
                drives.append(DriveInfo(
                    name="根目录",
                    path="/",
                    type="drive"
                ))
            
            logger.info(f"成功获取 {len(drives)} 个驱动器")
            return drives
            
        except Exception as e:
            error_msg = f"获取驱动器列表失败: {str(e)}"
            logger.error(error_msg)
            raise FileOperationError(error_msg, details={"error": str(e)})
    
    @staticmethod
    def list_files(path: str) -> Dict[str, Any]:
        """
        获取指定目录下的文件和文件夹列表
        
        Args:
            path: 目录路径
            
        Returns:
            Dict[str, Any]: 文件列表和目录信息
            
        Raises:
            FileOperationError: 操作失败时抛出
        """
        logger.debug(f"列出目录文件: {path}")
        
        try:
            if not os.path.exists(path):
                raise FileOperationError(f"路径不存在: {path}", error_code="PATH_NOT_EXISTS")
            
            if not os.path.isdir(path):
                raise FileOperationError(f"路径不是目录: {path}", error_code="NOT_DIRECTORY")
            
            items = []
            
            try:
                for item_name in os.listdir(path):
                    item_path = os.path.join(path, item_name)
                    try:
                        stat = os.stat(item_path)
                        is_dir = os.path.isdir(item_path)
                        
                        # 获取文件扩展名和类型
                        ext = os.path.splitext(item_name)[1].lower() if not is_dir else ""
                        file_type = "directory" if is_dir else get_file_type(ext)
                        
                        file_info = FileInfo(
                            name=item_name,
                            path=item_path,
                            type=file_type,
                            size=stat.st_size if not is_dir else 0,
                            modified=format_timestamp(stat.st_mtime),
                            is_directory=is_dir,
                            extension=ext,
                            permissions=oct(stat.st_mode)[-3:]
                        )
                        items.append(file_info.dict())
                        
                    except (PermissionError, OSError) as e:
                        logger.warning(f"无法访问文件: {item_path}, 错误: {str(e)}")
                        continue
                        
            except PermissionError:
                raise FileOperationError(f"权限不足，无法访问目录: {path}", error_code="PERMISSION_DENIED")
            
            # 排序：目录在前，然后按名称排序
            items.sort(key=lambda x: (not x["is_directory"], x["name"].lower()))
            
            result = {
                "success": True,
                "path": path,
                "items": items,
                "parent": os.path.dirname(path) if path != os.path.dirname(path) else None,
                "count": len(items)
            }
            
            logger.info(f"成功列出目录 {path}, 共 {len(items)} 个项目")
            return result
            
        except FileOperationError:
            raise
        except Exception as e:
            error_msg = f"获取文件列表失败: {str(e)}"
            logger.error(f"{error_msg}, 路径: {path}")
            raise FileOperationError(error_msg, details={"path": path, "error": str(e)})
    
    @staticmethod
    def get_file_content(path: str) -> Dict[str, Any]:
        """
        获取文件内容
        
        Args:
            path: 文件路径
            
        Returns:
            Dict[str, Any]: 文件内容和信息
            
        Raises:
            FileOperationError: 操作失败时抛出
        """
        logger.debug(f"读取文件内容: {path}")
        
        try:
            if not os.path.exists(path):
                raise FileOperationError(f"文件不存在: {path}", error_code="FILE_NOT_EXISTS")
            
            if os.path.isdir(path):
                raise FileOperationError(f"路径是目录，不是文件: {path}", error_code="IS_DIRECTORY")
            
            # 检查文件大小
            file_size = os.path.getsize(path)
            if file_size > settings.max_file_size:
                raise FileOperationError(
                    f"文件过大，无法读取（限制: {settings.max_file_size / 1024 / 1024:.1f}MB）",
                    error_code="FILE_TOO_LARGE",
                    details={"size": file_size, "limit": settings.max_file_size}
                )
            
            # 检查是否为文本文件
            if not is_text_file(path):
                raise FileOperationError(f"文件不是文本文件: {path}", error_code="NOT_TEXT_FILE")
            
            # 读取文件内容
            content, encoding = read_file_with_encoding(path)
            
            result = {
                "success": True,
                "content": content,
                "size": file_size,
                "encoding": encoding,
                "filename": os.path.basename(path)
            }
            
            logger.info(f"成功读取文件: {path}, 大小: {file_size} bytes, 编码: {encoding}")
            return result
            
        except FileOperationError:
            raise
        except Exception as e:
            error_msg = f"读取文件内容失败: {str(e)}"
            logger.error(f"{error_msg}, 路径: {path}")
            raise FileOperationError(error_msg, details={"path": path, "error": str(e)})
    
    @staticmethod
    def save_file_content(request: FileContentRequest) -> Dict[str, Any]:
        """
        保存文件内容
        
        Args:
            request: 文件内容请求
            
        Returns:
            Dict[str, Any]: 保存结果
            
        Raises:
            FileOperationError: 操作失败时抛出
        """
        logger.debug(f"保存文件内容: {request.path}")
        
        try:
            # 验证文件路径
            if not validate_file_path(request.path, settings.allowed_file_extensions):
                raise ValidationError(f"文件路径或扩展名不被允许: {request.path}")
            
            # 创建目录（如果不存在）
            directory = os.path.dirname(request.path)
            if directory:
                safe_create_directory(directory)
            
            # 保存文件
            with open(request.path, 'w', encoding='utf-8') as f:
                f.write(request.content or "")
            
            file_size = len((request.content or "").encode('utf-8'))
            
            result = {
                "success": True,
                "message": "文件保存成功",
                "path": request.path,
                "size": file_size
            }
            
            logger.info(f"成功保存文件: {request.path}, 大小: {file_size} bytes")
            return result
            
        except (ValidationError, FileOperationError):
            raise
        except Exception as e:
            error_msg = f"保存文件失败: {str(e)}"
            logger.error(f"{error_msg}, 路径: {request.path}")
            raise FileOperationError(error_msg, details={"path": request.path, "error": str(e)})
    
    @staticmethod
    def perform_file_operation(request: FileOperationRequest) -> Dict[str, Any]:
        """
        执行文件操作
        
        Args:
            request: 文件操作请求
            
        Returns:
            Dict[str, Any]: 操作结果
            
        Raises:
            FileOperationError: 操作失败时抛出
        """
        logger.info(f"执行文件操作: {request.operation.value}, 路径: {request.path}")
        
        try:
            if not os.path.exists(request.path):
                raise FileOperationError(f"文件或目录不存在: {request.path}", error_code="PATH_NOT_EXISTS")
            
            if request.operation == FileOperationType.DELETE:
                return FileService._delete_file_or_directory(request.path)
            elif request.operation == FileOperationType.RENAME:
                return FileService._rename_file_or_directory(request.path, request.new_name)
            elif request.operation == FileOperationType.COPY:
                return FileService._copy_file_or_directory(request.path, request.target_path)
            elif request.operation == FileOperationType.MOVE:
                return FileService._move_file_or_directory(request.path, request.target_path)
            else:
                raise FileOperationError(f"不支持的操作类型: {request.operation}")
                
        except FileOperationError:
            raise
        except Exception as e:
            error_msg = f"执行文件操作失败: {str(e)}"
            logger.error(f"{error_msg}, 操作: {request.operation}, 路径: {request.path}")
            raise FileOperationError(error_msg, details={"operation": request.operation, "path": request.path, "error": str(e)})
    
    @staticmethod
    def _delete_file_or_directory(path: str) -> Dict[str, Any]:
        """删除文件或目录"""
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
                logger.info(f"目录已删除: {path}")
            else:
                safe_remove_file(path)
            
            return {"success": True, "message": "删除成功", "path": path}
        except Exception as e:
            raise FileOperationError(f"删除失败: {str(e)}", details={"path": path})
    
    @staticmethod
    def _rename_file_or_directory(path: str, new_name: str) -> Dict[str, Any]:
        """重命名文件或目录"""
        if not new_name:
            raise ValidationError("新名称不能为空")
        
        try:
            new_path = os.path.join(os.path.dirname(path), new_name)
            os.rename(path, new_path)
            logger.info(f"重命名成功: {path} -> {new_path}")
            
            return {"success": True, "message": "重命名成功", "old_path": path, "new_path": new_path}
        except Exception as e:
            raise FileOperationError(f"重命名失败: {str(e)}", details={"path": path, "new_name": new_name})
    
    @staticmethod
    def _copy_file_or_directory(source_path: str, target_path: str) -> Dict[str, Any]:
        """复制文件或目录"""
        if not target_path:
            raise ValidationError("目标路径不能为空")
        
        try:
            target_path = FileService._resolve_unique_target(target_path)

            if os.path.isdir(source_path):
                shutil.copytree(source_path, target_path)
                logger.info(f"目录复制成功: {source_path} -> {target_path}")
            else:
                # 确保目标目录存在
                target_dir = os.path.dirname(target_path)
                if target_dir:
                    safe_create_directory(target_dir)
                shutil.copy2(source_path, target_path)
                logger.info(f"文件复制成功: {source_path} -> {target_path}")

            return {"success": True, "message": "复制成功", "source": source_path, "target": target_path}
        except Exception as e:
            raise FileOperationError(f"复制失败: {str(e)}", details={"source": source_path, "target": target_path})

    @staticmethod
    def _resolve_unique_target(target_path: str) -> str:
        """
        目标路径已存在时生成带序号的新路径（与资源管理器行为一致）

        例: a.txt → a (1).txt → a (2).txt
        """
        if not os.path.exists(target_path):
            return target_path

        directory = os.path.dirname(target_path)
        filename = os.path.basename(target_path)
        stem, ext = os.path.splitext(filename)

        counter = 1
        candidate = target_path
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{stem} ({counter}){ext}")
            counter += 1
            if counter > 999:
                break
        return candidate

    @staticmethod
    def _move_file_or_directory(source_path: str, target_path: str) -> Dict[str, Any]:
        """移动文件或目录"""
        if not target_path:
            raise ValidationError("目标路径不能为空")
        
        try:
            # 确保目标目录存在
            target_dir = os.path.dirname(target_path)
            if target_dir:
                safe_create_directory(target_dir)
                
            shutil.move(source_path, target_path)
            logger.info(f"移动成功: {source_path} -> {target_path}")
            
            return {"success": True, "message": "移动成功", "source": source_path, "target": target_path}
        except Exception as e:
            raise FileOperationError(f"移动失败: {str(e)}", details={"source": source_path, "target": target_path})
    
    @staticmethod
    def create_directory(path: str) -> Dict[str, Any]:
        """
        创建目录

        Args:
            path: 目标目录路径

        Returns:
            Dict[str, Any]: 操作结果

        Raises:
            FileOperationError: 创建失败时抛出
        """
        logger.info(f"创建目录: {path}")

        try:
            if os.path.exists(path):
                raise FileOperationError(f"路径已存在: {path}", error_code="PATH_EXISTS")

            Path(path).mkdir(parents=True, exist_ok=True)
            logger.info(f"目录创建成功: {path}")

            return {"success": True, "message": "目录创建成功", "path": path}
        except FileOperationError:
            raise
        except Exception as e:
            error_msg = f"创建目录失败: {str(e)}"
            logger.error(f"{error_msg}: {path}")
            raise FileOperationError(error_msg, details={"path": path, "error": str(e)})

    @staticmethod
    def create_file(path: str, content: str = "") -> Dict[str, Any]:
        """
        创建空文件（或带初始内容的新文件）

        Args:
            path: 目标文件路径
            content: 初始内容

        Returns:
            Dict[str, Any]: 操作结果

        Raises:
            FileOperationError: 创建失败时抛出
        """
        logger.info(f"创建文件: {path}")

        try:
            if os.path.exists(path):
                raise FileOperationError(f"文件已存在: {path}", error_code="PATH_EXISTS")

            directory = os.path.dirname(path)
            if directory:
                safe_create_directory(directory)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(content or "")

            file_size = os.path.getsize(path)
            logger.info(f"文件创建成功: {path}, 大小: {file_size} bytes")

            return {"success": True, "message": "文件创建成功", "path": path, "size": file_size}
        except FileOperationError:
            raise
        except Exception as e:
            error_msg = f"创建文件失败: {str(e)}"
            logger.error(f"{error_msg}: {path}")
            raise FileOperationError(error_msg, details={"path": path, "error": str(e)})

    @staticmethod
    def get_file_icon(path: str) -> Dict[str, Any]:
        """
        获取文件图标信息

        优先提取 Windows 真实图标（exe/lnk），失败时回退到按类型分配的 emoji。

        Args:
            path: 文件路径

        Returns:
            Dict[str, Any]: 包含 icon_type 与 icon 的字典
        """
        logger.debug(f"获取文件图标: {path}")

        if not os.path.exists(path):
            return {"success": False, "icon_type": "emoji", "icon": "📄"}

        ext = os.path.splitext(path)[1].lower()
        emoji_map = {
            ".exe": "⚙️",
            ".msi": "⚙️",
            ".bat": "⚙️",
            ".cmd": "⚙️",
            ".lnk": "🔗",
            ".zip": "📦",
            ".rar": "📦",
            ".7z": "📦",
            ".jpg": "🖼️",
            ".jpeg": "🖼️",
            ".png": "🖼️",
            ".gif": "🖼️",
            ".bmp": "🖼️",
            ".webp": "🖼️",
            ".mp4": "🎬",
            ".mkv": "🎬",
            ".avi": "🎬",
            ".mov": "🎬",
            ".mp3": "🎵",
            ".wav": "🎵",
            ".flac": "🎵",
            ".txt": "📄",
            ".md": "📄",
            ".py": "🐍",
            ".js": "📜",
            ".html": "🌐",
            ".css": "🎨",
            ".json": "📋",
            ".pdf": "📕",
            ".doc": "📘",
            ".docx": "📘",
            ".xls": "📗",
            ".xlsx": "📗",
            ".ppt": "📙",
            ".pptx": "📙",
        }

        # 尝试提取真实图标（仅 Windows + exe/lnk）
        if ext in {".exe", ".msi", ".lnk"} and os.name == 'nt':
            try:
                import win32gui
                import win32ui
                from ctypes import windll

                class SHIconInfo(ctypes.Structure):
                    _fields_ = [
                        ("hIcon", wintypes.HICON),
                        ("iSysImageIndex", ctypes.c_int),
                        ("dwAttributes", wintypes.DWORD),
                        ("szTitle", wintypes.WCHAR * 260),
                        ("szInfo", wintypes.WCHAR * 80),
                    ]

                large, small = win32gui.ExtractIconEx(path, 0), None
                if large and large[0]:
                    hicon = large[0]
                    win32gui.DestroyIcon(hicon)
                # 真实图标提取在无桌面会话时容易失败，统一回退 emoji
            except Exception as e:
                logger.debug(f"提取真实图标失败，回退 emoji: {e}")

        return {
            "success": True,
            "icon_type": "emoji",
            "icon": emoji_map.get(ext, "📄"),
        }

    @staticmethod
    def execute_file(file_path: str) -> Dict[str, Any]:
        """
        执行文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict[str, Any]: 执行结果
            
        Raises:
            FileOperationError: 执行失败时抛出
        """
        logger.info(f"尝试执行文件: {file_path}")
        
        try:
            if not os.path.exists(file_path):
                raise FileOperationError(f"文件不存在: {file_path}", error_code="FILE_NOT_EXISTS")
            
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext in {".exe", ".msi", ".bat", ".cmd"}:
                # 执行可执行文件
                subprocess.Popen([file_path], shell=True)
                logger.info(f"可执行文件已启动: {file_path}")
                return {"success": True, "message": "程序已启动", "file": file_path}
                
            elif ext == ".lnk":  # 快捷方式
                try:
                    # 尝试解析快捷方式
                    target_path = FileService._resolve_shortcut(file_path)
                    if target_path and os.path.exists(target_path):
                        subprocess.Popen([target_path], shell=True)
                        logger.info(f"快捷方式目标已执行: {target_path}")
                        return {"success": True, "message": f"快捷方式已执行: {os.path.basename(target_path)}", "file": file_path}
                    else:
                        # 直接启动快捷方式
                        os.startfile(file_path)
                        logger.info(f"快捷方式已启动: {file_path}")
                        return {"success": True, "message": "快捷方式已执行", "file": file_path}
                        
                except Exception as e:
                    logger.warning(f"解析快捷方式失败，尝试直接启动: {e}")
                    os.startfile(file_path)
                    return {"success": True, "message": "快捷方式已执行", "file": file_path}
            else:
                raise FileOperationError(f"文件类型不支持执行: {ext}", error_code="UNSUPPORTED_FILE_TYPE")
                
        except FileOperationError:
            raise
        except Exception as e:
            error_msg = f"执行文件失败: {str(e)}"
            logger.error(f"{error_msg}, 文件: {file_path}")
            raise FileOperationError(error_msg, details={"file": file_path, "error": str(e)})
    
    @staticmethod
    def _resolve_shortcut(shortcut_path: str) -> Optional[str]:
        """解析快捷方式目标路径"""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            return shortcut.Targetpath
        except ImportError:
            logger.warning("缺少win32com库，无法解析快捷方式")
            return None
        except Exception as e:
            logger.warning(f"解析快捷方式失败: {e}")
            return None
