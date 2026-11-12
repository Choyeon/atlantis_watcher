import { http } from './client'

/**
 * 设置与运行时 API
 * 后端端点位于 app/routers/settings.py、app/routers/meta.py
 * 返回 BaseResponse { success, message, data }，真正的负载在 data 内
 */

/** 读取设置 + 字段元信息 + 自启真实状态 + 运行时信息 */
export function fetchSettings() {
  return http.get('/api/settings')
}

/** 局部更新设置（只传改动的字段） */
export function saveSettings(patch) {
  return http.put('/api/settings', patch)
}

/** 重启 HTTP 服务（修改端口 / 监听地址后调用） */
export function restartService() {
  return http.post('/api/settings/restart', {})
}

/** 运行时信息（地址列表、运行时长、日志与设置文件路径） */
export function fetchRuntime() {
  return http.get('/api/runtime')
}
