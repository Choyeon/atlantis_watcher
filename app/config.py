# -*- coding: utf-8 -*-
"""运行期配置（单一数据源）。

优先级：环境变量 > 用户设置文件 > 默认值。
用户设置由 SettingsStore 加载后经 apply_user_settings() 覆盖。
关键点：get_settings() 始终返回同一个对象，更新时原地写 __dict__，
否则其它模块里 `settings = get_settings()` 的模块级引用会指向过期对象。
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用运行参数（不可变部分由环境变量提供，可变部分来自用户设置）"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ATLANTIS_",
        case_sensitive=False,
        extra="ignore",
    )

    # 服务器
    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=26541, description="监听端口")
    debug: bool = Field(default=False, description="调试模式")

    # 日志
    log_level: str = Field(default="INFO", description="日志级别")
    log_max_size: int = Field(default=10 * 1024 * 1024, description="单份日志上限(字节)")
    log_backup_count: int = Field(default=5, description="日志保留份数")

    # 命令与文件
    command_timeout: int = Field(default=60, description="命令执行超时(秒)")
    dangerous_commands: list[str] = Field(
        default_factory=lambda: ["format", "deltree", "rd /s", "rmdir /s", "del /f", "del /q"],
        description="危险命令黑名单",
    )
    max_file_size: int = Field(default=10 * 1024 * 1024, description="可编辑文件上限(字节)")
    allowed_file_extensions: list[str] = Field(
        default_factory=lambda: [".txt", ".py", ".js", ".html", ".css", ".json", ".xml", ".yml", ".yaml", ".md"],
        description="允许编辑的扩展名",
    )

    # 实时通道
    screen_share_fps: int = Field(default=15, description="屏幕共享帧率")
    screen_share_quality: int = Field(default=70, description="屏幕共享 JPEG 质量")
    remote_control_enabled: bool = Field(default=True, description="允许屏幕共享页注入鼠标/键盘；关闭后只能观看")
    websocket_timeout: int = Field(default=60, description="WebSocket 超时(秒)")

    # 系统
    max_processes_display: int = Field(default=100, description="进程列表上限")
    require_admin: bool = Field(default=True, description="是否校验管理员权限")


settings = Settings()


def get_settings() -> Settings:
    """获取全局配置对象（始终同一实例）"""
    return settings


def update_settings(**kwargs) -> Settings:
    """带校验地原地更新配置，返回同一实例"""
    merged = {**settings.model_dump(), **kwargs}
    validated = Settings.model_validate(merged)
    settings.__dict__.update(validated.__dict__)
    return settings


def apply_user_settings(user) -> None:
    """把用户偏好同步进运行期配置（不落盘，落盘由 SettingsStore 负责）"""
    update_settings(
        host=user.host,
        port=user.port,
        log_level=user.log_level,
        screen_share_fps=user.screen_share_fps,
        screen_share_quality=user.screen_share_quality,
        remote_control_enabled=user.remote_control_enabled,
        require_admin=user.require_admin,
    )
