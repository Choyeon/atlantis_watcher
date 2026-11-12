import { defineStore } from 'pinia'
import { ref } from 'vue'

let seq = 0

/**
 * 通知 Store
 * 替代旧版直接往 DOM 塞 .notification 节点的写法，
 * 改为集中管理，避免样式与生命周期脱节。
 */
export const useToastStore = defineStore('toast', () => {
  const items = ref([])

  function push(message, type = 'info', options = {}) {
    const id = ++seq
    const item = {
      id,
      type,
      message,
      title: options.title || '',
      duration: options.duration ?? (type === 'error' ? 5200 : 3000)
    }
    items.value.push(item)
    if (item.duration > 0) {
      setTimeout(() => dismiss(id), item.duration)
    }
    return id
  }

  function dismiss(id) {
    const idx = items.value.findIndex(t => t.id === id)
    if (idx !== -1) items.value.splice(idx, 1)
  }

  const success = (msg, opts) => push(msg, 'success', opts)
  const error = (msg, opts) => push(msg, 'error', opts)
  const warning = (msg, opts) => push(msg, 'warning', opts)
  const info = (msg, opts) => push(msg, 'info', opts)

  return { items, push, dismiss, success, error, warning, info }
})
