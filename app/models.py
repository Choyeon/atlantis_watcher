# -*- coding: utf-8 -*-
"""
数据模型定义模块
"""
from typing import Optional, List, Dict, Any, Union, Literal
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = Field(description="操作是否成功")
    message: Optional[str] = Field(None, description="响应消息")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")
    error_code: Optional[str] = Field(None, description="错误代码")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")


class CommandRequest(BaseModel):
    """命令执行请求模型"""
    command: str = Field(..., description="要执行的命令")
    is_powershell: bool = Field(False, description="是否为PowerShell命令")
    timeout: Optional[int] = Field(None, description="超时时间(秒)")


class CommandResponse(BaseModel):
    """命令执行响应模型"""
    output: str = Field(description="命令输出")
    error: str = Field(description="错误信息")
    returncode: int = Field(description="返回码")
    success: bool = Field(description="执行是否成功")
    execution_time: Optional[float] = Field(None, description="执行时间(秒)")


class ProcessKillRequest(BaseModel):
    """进程终止请求模型"""
    pid: int = Field(..., description="进程ID")
    force: bool = Field(False, description="是否强制终止")


class ProcessInfo(BaseModel):
    """进程信息模型"""
    pid: int = Field(description="进程ID")
    name: str = Field(description="进程名称")
    cpu_percent: float = Field(description="CPU使用率百分比")
    memory_percent: float = Field(description="内存使用率百分比")
    status: str = Field(description="进程状态")
    create_time: str = Field(description="创建时间")


class SystemInfo(BaseModel):
    """系统信息模型"""
    timestamp: str = Field(description="时间戳")
    system: Optional[Dict[str, Any]] = Field(None, description="系统运行信息")
    cpu: Dict[str, Any] = Field(description="CPU信息")
    memory: Dict[str, Any] = Field(description="内存信息")
    disk: List[Dict[str, Any]] = Field(description="磁盘信息")
    network: Dict[str, Any] = Field(description="网络信息")


class FileOperationType(str, Enum):
    """文件操作类型枚举"""
    RENAME = "rename"
    DELETE = "delete"
    COPY = "copy"
    MOVE = "move"


class FileOperationRequest(BaseModel):
    """文件操作请求模型"""
    path: str = Field(..., description="文件路径")
    operation: FileOperationType = Field(..., description="操作类型")
    new_name: Optional[str] = Field(None, description="新名称（重命名时使用）")
    target_path: Optional[str] = Field(None, description="目标路径（复制/移动时使用）")


class FileContentRequest(BaseModel):
    """文件内容请求模型"""
    path: str = Field(..., description="文件路径")
    content: Optional[str] = Field(None, description="文件内容")


class FileInfo(BaseModel):
    """文件信息模型"""
    name: str = Field(description="文件名")
    path: str = Field(description="文件路径")
    type: str = Field(description="文件类型")
    size: int = Field(description="文件大小(字节)")
    modified: str = Field(description="修改时间")
    is_directory: bool = Field(description="是否为目录")
    extension: str = Field(description="文件扩展名")
    permissions: str = Field(description="权限")


class DriveInfo(BaseModel):
    """驱动器信息模型"""
    name: str = Field(description="驱动器名称")
    path: str = Field(description="驱动器路径")
    type: str = Field(description="驱动器类型")
    total: Optional[int] = Field(None, description="总空间(字节)")
    used: Optional[int] = Field(None, description="已用空间(字节)")
    free: Optional[int] = Field(None, description="可用空间(字节)")


class MonitorData(BaseModel):
    """监控数据模型"""
    timestamp: str = Field(description="时间戳")
    cpu_percent: float = Field(description="CPU使用率")
    memory: Dict[str, Union[int, float]] = Field(description="内存信息")
    network: Dict[str, Union[int, float]] = Field(description="网络信息")


class NetworkInterface(BaseModel):
    """网络接口信息模型"""
    interface: str = Field(description="接口名称")
    ip: str = Field(description="IP地址")
    netmask: str = Field(description="子网掩码")


class DiskPartition(BaseModel):
    """磁盘分区信息模型"""
    device: str = Field(description="设备名称")
    mountpoint: str = Field(description="挂载点")
    fstype: str = Field(description="文件系统类型")
    total: int = Field(description="总空间(字节)")
    used: int = Field(description="已用空间(字节)")
    free: int = Field(description="可用空间(字节)")
    percent: float = Field(description="使用率百分比")


class ControlEvent(BaseModel):
    """远程输入事件（屏幕共享操控）。

    坐标一律归一化到 0..1，由 app.services.input_service 乘以真实屏幕尺寸换算，
    保证网页 / APK 横屏全屏 / letterbox 黑边下的点击位置与画面一致。
    """
    type: Literal[
        "move", "down", "up", "click", "dblclick", "wheel",
        "key", "keydown", "keyup", "text", "paste",
    ] = Field(..., description="事件类型")
    x: Optional[float] = Field(None, ge=0, le=1, description="归一化横坐标")
    y: Optional[float] = Field(None, ge=0, le=1, description="归一化纵坐标")
    button: Literal["left", "right", "middle"] = Field("left", description="鼠标键")
    clicks: int = Field(1, ge=1, le=3, description="连击次数")
    delta: float = Field(0, ge=-20, le=20, description="滚轮格数（正数向上）")
    key: Optional[str] = Field(None, max_length=48, description="键名或组合键，如 ctrl+c")
    text: Optional[str] = Field(None, max_length=500, description="要输入的文本")

    @model_validator(mode="after")
    def _require_payload(self):
        """把必填校验前移到模型层：非法事件在 422 就被挡住，不进线程池。"""
        if self.type in ("move", "down", "up", "click", "dblclick", "wheel"):
            if self.x is None or self.y is None:
                raise ValueError("坐标类事件必须提供归一化坐标 x / y")
        elif self.type in ("key", "keydown", "keyup"):
            if not self.key:
                raise ValueError("按键事件必须提供 key")
        elif self.type in ("text", "paste"):
            if not self.text:
                raise ValueError("文本事件必须提供 text")
        return self


