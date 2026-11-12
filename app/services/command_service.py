# -*- coding: utf-8 -*-
"""
命令执行服务模块
处理系统命令执行相关的业务逻辑
"""
import subprocess
import time
import os
from typing import Dict, Any
import logging
import ctypes

from app.config import get_settings
from app.models import CommandRequest, CommandResponse
from app.exceptions import CommandExecutionError, SystemOperationError
from app.utils import sanitize_command, calculate_execution_time


logger = logging.getLogger(__name__)
settings = get_settings()


class CommandService:
    """命令执行服务类"""
    
    @staticmethod
    def execute_command(request: CommandRequest) -> CommandResponse:
        """
        执行系统命令
        
        Args:
            request: 命令执行请求
            
        Returns:
            CommandResponse: 命令执行结果
            
        Raises:
            CommandExecutionError: 命令执行失败时抛出
        """
        start_time = time.time()
        timeout = request.timeout or settings.command_timeout
        
        try:
            logger.info(f"执行命令: {request.command}, PowerShell: {request.is_powershell}, 超时: {timeout}秒")
            
            # 安全检查
            if not sanitize_command(request.command, settings.dangerous_commands):
                error_msg = "命令包含危险操作，执行被拒绝"
                logger.warning(f"{error_msg}: {request.command}")
                raise CommandExecutionError(
                    error_msg,
                    error_code="DANGEROUS_COMMAND",
                    details={"command": request.command}
                )
            
            # 执行命令
            if request.is_powershell:
                result = subprocess.run(
                    ["powershell", "-Command", f"chcp 65001; {request.command}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding='utf-8',
                    errors='replace',
                    shell=False,
                    timeout=timeout
                )
            else:
                result = subprocess.run(
                    ["cmd", "/c", f"chcp 65001 & {request.command}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding='utf-8',
                    errors='replace',
                    shell=False,
                    timeout=timeout
                )
            
            # 处理结果
            success = result.returncode == 0
            output = result.stdout.strip() if result.stdout else ""
            error = result.stderr.strip() if result.stderr else ""
            execution_time = calculate_execution_time(start_time)
            
            # 如果成功但没有输出，添加默认消息
            if success and not output:
                output = f"{'PowerShell' if request.is_powershell else 'CMD'}命令执行成功"
            
            response = CommandResponse(
                output=output,
                error=error,
                returncode=result.returncode,
                success=success,
                execution_time=execution_time
            )
            
            log_level = logger.info if success else logger.warning
            log_level(f"命令执行{'成功' if success else '失败'}: {request.command} (耗时: {execution_time}秒)")
            
            return response
            
        except CommandExecutionError:
            # 保留业务异常自带的 error_code（如 DANGEROUS_COMMAND），
            # 不要被下面的通用 except 重新包装成无码异常
            raise
        except subprocess.TimeoutExpired:
            execution_time = calculate_execution_time(start_time)
            error_msg = f"命令执行超时({timeout}秒)"
            logger.error(f"{error_msg}: {request.command}")
            raise CommandExecutionError(
                error_msg,
                error_code="COMMAND_TIMEOUT",
                details={"command": request.command, "timeout": timeout, "execution_time": execution_time}
            )
        except Exception as e:
            execution_time = calculate_execution_time(start_time)
            error_msg = f"命令执行异常: {str(e)}"
            logger.error(f"{error_msg}: {request.command}")
            raise CommandExecutionError(
                error_msg,
                details={"command": request.command, "error": str(e), "execution_time": execution_time}
            )
    
    @staticmethod
    def shutdown_system(delay: int = 0) -> CommandResponse:
        """
        关闭系统
        
        Args:
            delay: 延迟时间(秒)
            
        Returns:
            CommandResponse: 执行结果
        """
        logger.info(f"执行系统关机，延迟: {delay}秒")
        
        command = f"shutdown /s /t {delay}" if delay > 0 else "shutdown /s /t 0"
        request = CommandRequest(command=command)
        
        return CommandService.execute_command(request)
    
    @staticmethod
    def restart_system() -> CommandResponse:
        """
        重启系统
        
        Returns:
            CommandResponse: 执行结果
        """
        logger.info("执行系统重启")
        
        request = CommandRequest(command="shutdown /r /t 0")
        return CommandService.execute_command(request)
    
    @staticmethod
    def cancel_shutdown() -> CommandResponse:
        """
        取消系统关机或重启
        
        Returns:
            CommandResponse: 执行结果
        """
        logger.info("取消系统关机/重启")
        
        request = CommandRequest(command="shutdown /a")
        return CommandService.execute_command(request)
    
    @staticmethod
    def lock_screen() -> Dict[str, Any]:
        """
        锁定屏幕
        
        Returns:
            Dict[str, Any]: 执行结果
            
        Raises:
            SystemOperationError: 锁定失败时抛出
        """
        logger.info("执行屏幕锁定")
        
        try:
            # 使用Windows API锁定屏幕
            result = ctypes.windll.user32.LockWorkStation()
            
            if result:
                logger.info("屏幕锁定成功")
                return {
                    "success": True,
                    "message": "屏幕已锁定",
                    "error": "",
                    "returncode": 0
                }
            else:
                error_msg = "屏幕锁定失败"
                logger.error(error_msg)
                raise SystemOperationError(
                    error_msg,
                    error_code="LOCK_SCREEN_FAILED"
                )
                
        except Exception as e:
            error_msg = f"屏幕锁定异常: {str(e)}"
            logger.error(error_msg)
            raise SystemOperationError(
                error_msg,
                details={"error": str(e)}
            )
    
    @staticmethod
    def set_monitor_power(turn_on: bool) -> Dict[str, Any]:
        """
        控制显示器电源（关闭 / 点亮）

        通过向所有顶层窗口广播 WM_SYSCOMMAND / SC_MONITORPOWER 实现：
            lParam =  2  -> 关闭显示器 (off)
            lParam = -1  -> 点亮显示器 (on)

        注意事项：
        - 只作用于调用进程所在的交互式桌面会话；服务进程 / Session 0 下不生效。
          本项目由桌面用户启动（含托盘图标），处于正确会话，无需管理员权限。
        - 熄屏只切断显示输出，系统不睡眠、进程不中断，HTTP / WebSocket 服务继续运行，
          因此可从手机端再次调用本接口点亮；本机鼠标或键盘输入同样会唤醒。
        - 使用 SendMessageTimeoutW + SMTO_ABORTIFHUNG（2 秒上限），避免某个无响应窗口
          让同步广播把服务卡死；调用方仍应放入线程池执行，不阻塞 asyncio event loop。
        - ctypes 是标准库，PyInstaller 自动收集，无需新增依赖或改 .spec。

        Args:
            turn_on: True 点亮，False 关闭

        Returns:
            Dict[str, Any]: 与 lock_screen() 同风格的结果字典

        Raises:
            SystemOperationError: 非 Windows 平台或 Win32 API 调用异常时抛出
        """
        action = "点亮" if turn_on else "关闭"
        logger.info(f"执行显示器控制: {action}")

        if os.name != 'nt':
            error_msg = "显示器控制仅支持 Windows 平台"
            logger.error(error_msg)
            raise SystemOperationError(error_msg, error_code="UNSUPPORTED_PLATFORM")

        try:
            from ctypes import wintypes

            HWND_BROADCAST = 0xFFFF
            WM_SYSCOMMAND = 0x0112
            SC_MONITORPOWER = 0xF170
            SMTO_ABORTIFHUNG = 0x0002
            MONITOR_OFF = 2
            MONITOR_ON = -1
            TIMEOUT_MS = 2000

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.SendMessageTimeoutW.argtypes = [
                wintypes.HWND,          # hWnd
                wintypes.UINT,          # Msg
                wintypes.WPARAM,        # wParam
                wintypes.LPARAM,        # lParam (有符号，-1 必须正确符号扩展)
                wintypes.UINT,          # fuFlags
                wintypes.UINT,          # uTimeout
                ctypes.POINTER(ctypes.c_size_t)  # lpdwResult (DWORD_PTR, 64 位下 8 字节)
            ]
            user32.SendMessageTimeoutW.restype = wintypes.LPARAM

            # 结果缓冲区必须与 DWORD_PTR 等宽，传 4 字节 DWORD 会被 API 写越界
            result_buf = ctypes.c_size_t(0)
            sent = user32.SendMessageTimeoutW(
                wintypes.HWND(HWND_BROADCAST),
                wintypes.UINT(WM_SYSCOMMAND),
                wintypes.WPARAM(SC_MONITORPOWER),
                wintypes.LPARAM(MONITOR_ON if turn_on else MONITOR_OFF),
                wintypes.UINT(SMTO_ABORTIFHUNG),
                wintypes.UINT(TIMEOUT_MS),
                ctypes.byref(result_buf)
            )

            if not sent:
                # HWND_BROADCAST 下个别窗口超时属正常，指令通常已投递；只记告警不判失败
                logger.warning(
                    f"SendMessageTimeoutW 返回 0 (GetLastError={ctypes.get_last_error()})，"
                    f"显示器{action}指令视为已投递"
                )
            else:
                logger.info(f"显示器控制指令投递成功: {action}")

            return {
                "success": True,
                "message": f"已{action}显示器",
                "error": "",
                "returncode": 0,
                "action": "on" if turn_on else "off"
            }

        except Exception as e:
            error_msg = f"显示器控制异常: {str(e)}"
            logger.error(error_msg)
            raise SystemOperationError(
                error_msg,
                error_code="MONITOR_CONTROL_FAILED",
                details={"error": str(e)}
            )

    @staticmethod
    def turn_off_monitor() -> Dict[str, Any]:
        """关闭显示器（熄屏，系统继续运行）"""
        return CommandService.set_monitor_power(False)

    @staticmethod
    def turn_on_monitor() -> Dict[str, Any]:
        """点亮显示器（远程恢复熄屏后的画面）"""
        return CommandService.set_monitor_power(True)

    @staticmethod
    def logout_system() -> CommandResponse:
        """
        注销系统
        
        Returns:
            CommandResponse: 执行结果
        """
        logger.info("执行系统注销")
        
        request = CommandRequest(command="shutdown /l")
        return CommandService.execute_command(request)
