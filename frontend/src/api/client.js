/**
 * 统一 HTTP 客户端
 * - 统一错误处理：把 FastAPI 的 detail 结构转成可读消息
 * - 统一 baseURL：开发环境走 Vite 代理，生产走同源
 */

const HOST_STORAGE_KEY = 'atlantis-host'

/**
 * 解析 API 基础地址
 *
 * 优先级：
 *   1. localStorage 中的主机设置（APK 场景必填）
 *   2. window.location.origin（浏览器直接访问主机时）
 *   3. 开发环境走 Vite 代理（相对路径）
 */
export function resolveBase() {
  try {
    const saved = localStorage.getItem(HOST_STORAGE_KEY)
    if (saved) return saved.replace(/\/$/, '')
  } catch {
    /* localStorage 不可用时降级 */
  }
  return window.location.origin
}

/** 从后端错误响应中提取可读信息 */
function extractDetail(payload, status) {
  const detail = payload?.detail
  if (!detail) return `请求失败 (HTTP ${status})`
  if (typeof detail === 'string') return detail
  if (typeof detail === 'object') {
    return detail.message || detail.error || detail.error_code || JSON.stringify(detail)
  }
  return String(detail)
}

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

async function request(path, options = {}) {
  const { headers, body, ...rest } = options
  const init = {
    method: options.method || 'GET',
    headers: {
      Accept: 'application/json',
      ...(body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...headers
    },
    ...rest
  }

  if (body !== undefined && body !== null) {
    init.body = body instanceof FormData ? body : JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(`${resolveBase()}${path}`, init)
  } catch (err) {
    throw new ApiError('网络连接失败，请检查服务是否运行', 0, null)
  }

  // 204 / 空响应
  if (response.status === 204) return null

  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!response.ok) {
    throw new ApiError(extractDetail(payload, response.status), response.status, payload)
  }

  return payload
}

export const http = {
  get: (path, options) => request(path, { ...options, method: 'GET' }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  delete: (path, options) => request(path, { ...options, method: 'DELETE' })
}

/** 构造带查询参数的路径 */
export function withQuery(path, params = {}) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (!entries.length) return path
  const qs = entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')
  return `${path}?${qs}`
}
