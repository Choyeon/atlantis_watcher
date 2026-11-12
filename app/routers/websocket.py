# -*- coding: utf-8 -*-
"""
WebSocket相关路由
"""
import asyncio
import time
import json
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.logging_utils import get_logger
from app.decorators import async_log_exceptions
from app.services.system_service import SystemService
from app.config import get_settings

logger = get_logger(__name__)
router = APIRouter(tags=["websocket"])
settings = get_settings()


def _encode_screen_frame(quality: int) -> bytes:
    """截屏并编码为 JPEG。

    cv2 / numpy / pyautogui 是重量级原生依赖：改为首次用到屏幕共享时才加载，
    避免 import main 就把它们常驻内存、拖慢冷启动。
    本函数为同步阻塞调用，端点里通过 asyncio.to_thread 执行。
    """
    import cv2
    import numpy as np
    import pyautogui

    img = pyautogui.screenshot()
    frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, int(quality)])
    if not ok:
        raise RuntimeError("屏幕帧 JPEG 编码失败")
    return buffer.tobytes()


@router.websocket("/ws/monitor")
@async_log_exceptions()
async def monitor_websocket(websocket: WebSocket):
    """
    系统监控WebSocket端点
    
    Args:
        websocket: WebSocket连接
    """
    await websocket.accept()
    logger.info("系统监控WebSocket连接已建立")
    
    # 存储上一次的网络IO数据用于计算速度
    last_network_io: Dict[str, int] = {}
    last_time = time.time()
    
    try:
        while True:
            try:
                # 检查是否有来自客户端的心跳消息
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                    if data == "ping":
                        await websocket.send_text("pong")
                        continue
                except asyncio.TimeoutError:
                    pass
                
                # 获取系统监控数据
                monitor_data, current_network_io, current_time = SystemService.get_monitor_data(
                    last_network_io, last_time
                )
                
                # 发送监控数据
                await websocket.send_text(monitor_data.json())
                
                # 更新上一次的数据
                last_network_io = current_network_io
                last_time = current_time
                
                # 等待2秒后发送下一次数据
                await asyncio.sleep(2)
                
            except WebSocketDisconnect:
                logger.info("客户端主动断开监控WebSocket连接")
                break
            except asyncio.CancelledError:
                logger.info("监控WebSocket任务被取消")
                break
            except Exception as e:
                logger.error(f"发送监控数据错误: {str(e)}")
                # 尝试发送错误信息给客户端
                try:
                    error_data = {
                        "error": True,
                        "message": f"数据获取失败: {str(e)}",
                        "timestamp": time.time()
                    }
                    await websocket.send_text(json.dumps(error_data))
                except Exception:
                    # 如果发送失败，说明连接已断开
                    break
                
                await asyncio.sleep(2)
                
    except Exception as e:
        logger.error(f"监控WebSocket连接错误: {str(e)}")
    finally:
        logger.info("系统监控WebSocket连接已关闭")
        try:
            await websocket.close()
        except Exception as e:
            logger.warning(f"关闭WebSocket连接时出错: {str(e)}")


@router.websocket("/ws/screen")
@async_log_exceptions()
async def screen_share_websocket(websocket: WebSocket):
    """
    屏幕共享WebSocket端点
    
    Args:
        websocket: WebSocket连接
    """
    await websocket.accept()
    
    # 帧率 / 质量每帧从运行期配置读取：设置页改动即时生效，无需重连。
    # settings 是单例且采用原地更新，因此这里读到的始终是最新值。
    last_activity = time.time()
    client_alive = True
    last_screenshot_time = 0.0

    logger.info("屏幕共享 WebSocket 连接已建立（帧率与质量取自运行期设置）")
    
    # 创建心跳检测任务
    async def heartbeat():
        nonlocal client_alive, last_activity
        try:
            while client_alive:
                # 检查客户端是否超时
                if time.time() - last_activity > settings.websocket_timeout:
                    logger.info(f"客户端超过{settings.websocket_timeout}秒没有活动，关闭连接")
                    client_alive = False
                    break
                await asyncio.sleep(30)  # 每30秒检查一次
        except asyncio.CancelledError:
            logger.info("心跳检测任务被取消")
        except Exception as e:
            logger.error(f"心跳检测任务异常: {str(e)}")
            client_alive = False
    
    # 启动心跳检测任务
    heartbeat_task = asyncio.create_task(heartbeat())
    
    try:
        # 主循环发送屏幕截图
        while client_alive:
            try:
                # 检查是否有来自客户端的消息（非阻塞）
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                    if data == "ping":
                        # 收到心跳包，更新最后活动时间
                        last_activity = time.time()
                        await websocket.send_text("pong")
                        continue
                except asyncio.TimeoutError:
                    # 没有收到消息，继续发送屏幕截图
                    pass
                except WebSocketDisconnect:
                    logger.info("客户端主动断开屏幕共享连接")
                    break
                
                # 控制帧率：以当前配置为准（旧版把用户设置的 FPS 强制压回 5–20）
                target_fps = max(1, settings.screen_share_fps)
                frame_interval = 1.0 / target_fps
                elapsed = time.time() - last_screenshot_time
                if elapsed < frame_interval:
                    await asyncio.sleep(frame_interval - elapsed)
                    continue

                # 截屏 + 编码放到线程池，避免同步 GDI 调用阻塞 event loop
                try:
                    started = time.time()
                    last_screenshot_time = started
                    frame_bytes = await asyncio.to_thread(
                        _encode_screen_frame, settings.screen_share_quality
                    )
                    await websocket.send_bytes(frame_bytes)
                    last_activity = time.time()

                    # 单帧耗时超预算时轻微退避，下一帧仍以配置帧率为基准
                    processing_time = time.time() - started
                    if processing_time > frame_interval * 1.2:
                        await asyncio.sleep(min(processing_time - frame_interval, 0.5))
                except Exception as e:
                    logger.error(f"发送屏幕截图错误: {str(e)}")
                    break
                    
            except asyncio.CancelledError:
                logger.info("屏幕共享任务被取消")
                break
            except Exception as e:
                logger.error(f"屏幕共享主循环错误: {str(e)}")
                break
                
    except Exception as e:
        logger.error(f"屏幕共享WebSocket连接错误: {str(e)}")
    finally:
        # 停止心跳检测任务
        client_alive = False
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            logger.debug("心跳检测任务已取消")
        except Exception as e:
            logger.warning(f"取消心跳检测任务时出错: {str(e)}")
        
        logger.info("屏幕共享WebSocket连接已关闭")
        
        # 确保连接已关闭
        try:
            await websocket.close()
        except Exception as e:
            logger.warning(f"关闭屏幕共享WebSocket连接时出错: {str(e)}")
