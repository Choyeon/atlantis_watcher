import { ref } from 'vue'
import { useWebSocket } from './useWebSocket'
import { fetchControlStatus, sendControlEvent } from '@/api/control'

/**
 * 远程操控通道（屏幕共享的操作半边）
 *
 * - 主通道 /ws/control：低延迟、逐事件 ACK
 * - WS 未就绪时自动降级到 POST /api/control，保证 APK WebView 禁用 WS 也能点按
 * - move 按 ~30Hz 节流，pointermove 不会把通道打爆
 * - 后端设置页关闭「允许远程操控」后，ready / error 帧会把 enabled 置 false，
 *   无需重连即刻停止注入
 *
 * 事件坐标一律是归一化 0..1，换算规则见 ScreenView.toNormalized。
 */
export function useRemoteControl({ onError } = {}) {
  const enabled = ref(true)
  const connected = ref(false)
  const screen = ref(null)

  const ws = useWebSocket('/ws/control', {
    autoConnect: false,
    onJson: data => {
      if (data?.type === 'ready') {
        connected.value = true
        enabled.value = !!data.enabled
        return
      }
      if (data?.ok === false) {
        if (data.error === 'REMOTE_CONTROL_DISABLED') enabled.value = false
        onError?.(data.message || data.error || '远程操控失败')
      }
    },
    onClose: () => {
      connected.value = false
    }
  })

  /** 读取后端开关与屏幕尺寸（进入页面时调用一次） */
  async function refreshStatus() {
    try {
      const res = await fetchControlStatus()
      enabled.value = !!res?.enabled
      screen.value = res?.screen || null
      return res
    } catch (err) {
      onError?.(`读取操控状态失败: ${err.message}`)
      return null
    }
  }

  let lastRestMoveAt = 0

  function emit(event) {
    if (!enabled.value) return false

    const payload = JSON.stringify(event)
    if (connected.value && ws.status.value === 'open' && ws.send(payload)) return true

    // REST 兜底：拖动事件降到 ~10Hz，避免退化成 HTTP 洪泛
    if (event.type === 'move') {
      const now = performance.now()
      if (now - lastRestMoveAt < 100) return false
      lastRestMoveAt = now
    }
    sendControlEvent(event).catch(err => onError?.(`远程操控失败: ${err.message}`))
    return true
  }

  let lastMoveAt = 0
  function emitMove(x, y, force = false) {
    const now = performance.now()
    if (!force && now - lastMoveAt < 32) return false
    lastMoveAt = now
    return emit({ type: 'move', x, y })
  }

  function connect() {
    ws.connect()
  }

  function disconnect() {
    ws.disconnect()
    connected.value = false
  }

  return {
    enabled,
    connected,
    screen,
    status: ws.status,
    connect,
    disconnect,
    refreshStatus,
    emit,
    emitMove
  }
}
