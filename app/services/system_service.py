# -*- coding: utf-8 -*-
"""
系统服务模块
处理系统相关的业务逻辑
"""
import psutil
import socket
from typing import List, Dict, Any
from datetime import datetime
import logging

from app.config import get_settings
from app.models import SystemInfo, ProcessInfo, MonitorData, NetworkInterface, DiskPartition
from app.exceptions import SystemOperationError
from app.utils import format_timestamp


logger = logging.getLogger(__name__)
settings = get_settings()


class SystemService:
    """系统服务类"""
    
    @staticmethod
    def get_system_info() -> SystemInfo:
        """
        获取系统基本信息
        
        Returns:
            SystemInfo: 系统信息对象
            
        Raises:
            SystemOperationError: 获取系统信息失败时抛出
        """
        try:
            logger.debug("开始获取系统信息")
            
            # CPU信息
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # 内存信息
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # 磁盘信息
            disk_partitions = []
            for partition in psutil.disk_partitions():
                try:
                    partition_usage = psutil.disk_usage(partition.mountpoint)
                    disk_partitions.append(DiskPartition(
                        device=partition.device,
                        mountpoint=partition.mountpoint,
                        fstype=partition.fstype,
                        total=partition_usage.total,
                        used=partition_usage.used,
                        free=partition_usage.free,
                        percent=round((partition_usage.used / partition_usage.total) * 100, 2)
                    ).dict())
                except (PermissionError, FileNotFoundError) as e:
                    logger.warning(f"无权限访问磁盘分区 {partition.device}: {str(e)}")
                    continue
            
            # 系统启动时间和运行时间
            import time
            boot_time = psutil.boot_time()
            current_time = time.time()
            uptime_seconds = current_time - boot_time
            uptime_days = int(uptime_seconds // 86400)
            uptime_hours = int((uptime_seconds % 86400) // 3600)
            uptime_minutes = int((uptime_seconds % 3600) // 60)
            
            # 进程数统计
            process_count = len(list(psutil.process_iter()))
            
            # 网络信息
            network_io = psutil.net_io_counters()
            network_interfaces = []
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        network_interfaces.append(NetworkInterface(
                            interface=interface,
                            ip=addr.address,
                            netmask=addr.netmask
                        ).dict())
            
            system_info = SystemInfo(
                timestamp=datetime.now().isoformat(),
                system={
                    "boot_time": datetime.fromtimestamp(boot_time).isoformat(),
                    "uptime": {
                        "total_seconds": int(uptime_seconds),
                        "days": uptime_days,
                        "hours": uptime_hours,
                        "minutes": uptime_minutes,
                        "formatted": f"{uptime_days}天 {uptime_hours}小时 {uptime_minutes}分钟"
                    },
                    "process_count": process_count
                },
                cpu={
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "frequency": {
                        "current": cpu_freq.current if cpu_freq else None,
                        "min": cpu_freq.min if cpu_freq else None,
                        "max": cpu_freq.max if cpu_freq else None
                    }
                },
                memory={
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent,
                    "swap_total": swap.total,
                    "swap_used": swap.used,
                    "swap_percent": swap.percent
                },
                disk=disk_partitions,
                network={
                    "io": {
                        "bytes_sent": network_io.bytes_sent,
                        "bytes_recv": network_io.bytes_recv,
                        "packets_sent": network_io.packets_sent,
                        "packets_recv": network_io.packets_recv
                    },
                    "interfaces": network_interfaces
                }
            )
            
            logger.info("系统信息获取成功")
            return system_info
            
        except Exception as e:
            error_msg = f"获取系统信息失败: {str(e)}"
            logger.error(error_msg)
            raise SystemOperationError(error_msg, details={"error": str(e)})
    
    @staticmethod
    def get_processes() -> List[ProcessInfo]:
        """
        获取系统进程列表
        
        Returns:
            List[ProcessInfo]: 进程信息列表
            
        Raises:
            SystemOperationError: 获取进程信息失败时抛出
        """
        try:
            logger.debug("开始获取进程列表")
            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
                try:
                    proc_info = proc.info
                    # 限制CPU百分比在合理范围内
                    cpu_percent = max(0, min(proc_info['cpu_percent'] or 0, 100))
                    
                    process_info = ProcessInfo(
                        pid=proc_info['pid'],
                        name=proc_info['name'],
                        cpu_percent=round(cpu_percent, 2),
                        memory_percent=round(proc_info['memory_percent'] or 0, 2),
                        status=proc_info['status'],
                        create_time=format_timestamp(proc_info['create_time'])
                    )
                    processes.append(process_info)
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # 按CPU使用率排序，返回前N个进程
            processes.sort(key=lambda x: x.cpu_percent, reverse=True)
            result = processes[:settings.max_processes_display]
            
            logger.info(f"成功获取 {len(result)} 个进程信息")
            return result
            
        except Exception as e:
            error_msg = f"获取进程列表失败: {str(e)}"
            logger.error(error_msg)
            raise SystemOperationError(error_msg, details={"error": str(e)})
    
    @staticmethod
    def kill_process(pid: int, force: bool = False) -> Dict[str, Any]:
        """
        终止指定进程
        
        Args:
            pid: 进程ID
            force: 是否强制终止
            
        Returns:
            Dict[str, Any]: 操作结果
            
        Raises:
            SystemOperationError: 终止进程失败时抛出
        """
        try:
            logger.info(f"尝试终止进程 PID: {pid}, 强制模式: {force}")
            
            proc = psutil.Process(pid)
            proc_name = proc.name()
            
            if force:
                proc.kill()  # 强制结束
                logger.info(f"强制终止进程: {proc_name} (PID: {pid})")
            else:
                proc.terminate()  # 正常结束
                logger.info(f"正常终止进程: {proc_name} (PID: {pid})")
            
            # 等待进程结束
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                if not force:
                    proc.kill()  # 如果正常结束失败，强制结束
                    proc.wait(timeout=3)
                    logger.warning(f"正常终止超时，已强制终止进程: {proc_name} (PID: {pid})")
            
            return {
                "success": True,
                "message": f"进程 {proc_name} (PID: {pid}) 已终止",
                "process_name": proc_name,
                "pid": pid,
                "force": force
            }
            
        except psutil.NoSuchProcess:
            raise SystemOperationError("进程不存在", error_code="PROCESS_NOT_FOUND", details={"pid": pid})
        except psutil.AccessDenied:
            raise SystemOperationError("权限不足，无法终止该进程", error_code="ACCESS_DENIED", details={"pid": pid})
        except Exception as e:
            error_msg = f"终止进程失败: {str(e)}"
            logger.error(f"{error_msg}, PID: {pid}")
            raise SystemOperationError(error_msg, details={"pid": pid, "error": str(e)})
    
    @staticmethod
    def get_monitor_data(last_network_io: Dict[str, int], last_time: float) -> tuple[MonitorData, Dict[str, int], float]:
        """
        获取系统监控数据
        
        Args:
            last_network_io: 上次网络IO数据
            last_time: 上次获取时间
            
        Returns:
            tuple: (监控数据, 当前网络IO数据, 当前时间)
        """
        import time
        
        try:
            current_time = time.time()
            current_network_io = psutil.net_io_counters()._asdict()
            time_diff = current_time - last_time
            
            # 计算网络速度
            upload_speed = 0
            download_speed = 0
            if time_diff > 0 and last_network_io:
                upload_speed = (current_network_io['bytes_sent'] - last_network_io.get('bytes_sent', 0)) / time_diff
                download_speed = (current_network_io['bytes_recv'] - last_network_io.get('bytes_recv', 0)) / time_diff
            
            memory = psutil.virtual_memory()
            
            monitor_data = MonitorData(
                timestamp=datetime.now().isoformat(),
                cpu_percent=psutil.cpu_percent(),
                memory={
                    "percent": memory.percent,
                    "used": memory.used,
                    "total": memory.total
                },
                network={
                    "upload_speed": max(0, upload_speed),  # 确保不为负数
                    "download_speed": max(0, download_speed),
                    "total_sent": current_network_io['bytes_sent'],
                    "total_recv": current_network_io['bytes_recv']
                }
            )
            
            return monitor_data, current_network_io, current_time
            
        except Exception as e:
            logger.error(f"获取监控数据失败: {str(e)}")
            # 返回默认数据
            empty_io = {"bytes_sent": 0, "bytes_recv": 0}
            default_data = MonitorData(
                timestamp=datetime.now().isoformat(),
                cpu_percent=0.0,
                memory={"percent": 0.0, "used": 0, "total": 0},
                network={"upload_speed": 0.0, "download_speed": 0.0, "total_sent": 0, "total_recv": 0}
            )
            return default_data, empty_io, time.time()
