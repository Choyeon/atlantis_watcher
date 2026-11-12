import { http } from './client'

/**
 * 远程操控 API
 * 主通道是 /ws/control，这里提供状态查询与 REST 兜底。
 * 后端端点位于 app/routers/control.py。
 */

/** 查询操控开关与主机屏幕尺寸 */
export function fetchControlStatus() {
  return http.get('/api/control/status')
}

/** 注入一条输入事件（WS 不可用时的兜底） */
export function sendControlEvent(event) {
  return http.post('/api/control', event)
}
