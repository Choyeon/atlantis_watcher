import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { resolveBase } from '@/api/client'

/**
 * WebSocket 组合式函数
 *
 * 修复旧版核心缺陷：
 *   旧 main.js 用统一的 handleWebSocketMessage 把所有消息当 JSON 解析，
 *   但 /ws/screen 推送的是 JPEG 二进制帧（send_bytes），
 *   结果 JSON.parse 抛错 → 屏幕画面永远出不来。
 *
 * 本实现按 endpoint 区分消息类型：
 *   - 文本消息：JSON.parse 后交给 onJson
 *   - 二进制消息：Blob → ArrayBuffer → 交给 onBinary
 */
export function useWebSocket(path, { onJson, onBinary, onOpen, onClose, autoConnect = true } = {}) {
  const ws = shallowRef(null)
  const status = ref('idle') // idle | connecting | open | closed | error
  const lastError = ref('')
  let reconnectTimer = null
  let retryCount = 0
  let manuallyClosed = false

  function buildUrl() {
    // 使用与 HTTP 层一致的主机地址，保证 APK 场景下能连到局域网主机
    const base = resolveBase()
    let origin
    try {
      const u = new URL(base)
      origin = `${u.protocol === 'https:' ? 'wss:' : 'ws:'}//${u.host}`
    } catch {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      origin = `${proto}//${window.location.host}`
    }
    return `${origin}${path}`
  }

  function connect() {
    if (ws.value && (ws.value.readyState === WebSocket.OPEN || ws.value.readyState === WebSocket.CONNECTING)) {
      return
    }
    manuallyClosed = false
    status.value = 'connecting'
    lastError.value = ''

    let socket
    try {
      socket = new WebSocket(buildUrl())
    } catch (err) {
      status.value = 'error'
      lastError.value = err.message
      scheduleReconnect()
      return
    }

    // 二进制帧必须显式指定类型，否则默认 Blob 会浪费一次内存拷贝
    socket.binaryType = 'arraybuffer'
    ws.value = socket

    socket.onopen = () => {
      status.value = 'open'
      retryCount = 0
      onOpen?.()
    }

    socket.onmessage = event => {
      const data = event.data
      if (typeof data === 'string') {
        // 心跳 pong 或 JSON 数据
        if (data === 'pong') return
        try {
          onJson?.(JSON.parse(data))
        } catch {
          onJson?.({ raw: data })
        }
      } else if (data instanceof ArrayBuffer) {
        onBinary?.(data)
      } else if (data instanceof Blob) {
        data.arrayBuffer().then(buf => onBinary?.(buf))
      }
    }

    socket.onerror = () => {
      status.value = 'error'
      lastError.value = 'WebSocket 连接错误'
    }

    socket.onclose = event => {
      status.value = 'closed'
      ws.value = null
      onClose?.(event)
      if (!manuallyClosed) scheduleReconnect()
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    // 指数退避，上限 15s
    const delay = Math.min(1000 * 2 ** retryCount, 15000)
    retryCount += 1
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  function disconnect() {
    manuallyClosed = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws.value) {
      try {
        ws.value.close()
      } catch {
        /* 忽略关闭异常 */
      }
      ws.value = null
    }
    status.value = 'closed'
  }

  function send(data) {
    if (ws.value && ws.value.readyState === WebSocket.OPEN) {
      ws.value.send(data)
      return true
    }
    return false
  }

  onMounted(() => {
    if (autoConnect) connect()
  })

  onBeforeUnmount(() => {
    disconnect()
  })

  return { ws, status, lastError, connect, disconnect, send }
}