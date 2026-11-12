import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchSystemInfo, fetchProcesses } from '@/api/system'
import { toNumber } from '@/utils/format'

/**
 * 系统状态 Store
 * 汇总 REST 快照 + WebSocket 实时流。
 *
 * 数据流设计：
 *   /api/system/info      → 一次性快照（磁盘、网络接口、启动时间等）
 *   /ws/monitor           → 每 2 秒推送 cpu_percent / memory / network
 */
export const useSystemStore = defineStore('system', () => {
  const info = ref(null)
  const processes = ref([])
  const loading = ref(false)
  const error = ref('')
  const connected = ref(false)
  const lastUpdate = ref(null)

  // 实时流中的最新值（覆盖快照）
  const live = ref({
    cpuPercent: 0,
    memoryPercent: 0,
    memoryUsed: 0,
    memoryTotal: 0,
    uploadSpeed: 0,
    downloadSpeed: 0
  })

  const cpuPercent = computed(() => live.value.cpuPercent)
  const memoryPercent = computed(() => live.value.memoryPercent)

  const cpu = computed(() => {
    const base = info.value?.cpu
    return {
      percent: live.value.cpuPercent || toNumber(base?.percent),
      count: toNumber(base?.count),
      frequency: base?.frequency || null
    }
  })

  const memory = computed(() => {
    const base = info.value?.memory || {}
    return {
      percent: live.value.memoryPercent || toNumber(base.percent),
      used: live.value.memoryUsed || toNumber(base.used),
      total: live.value.memoryTotal || toNumber(base.total),
      available: toNumber(base.available),
      swapTotal: toNumber(base.swap_total),
      swapPercent: toNumber(base.swap_percent)
    }
  })

  const network = computed(() => {
    const base = info.value?.network || {}
    return {
      uploadSpeed: live.value.uploadSpeed,
      downloadSpeed: live.value.downloadSpeed,
      totalSent: toNumber(base.io?.bytes_sent),
      totalRecv: toNumber(base.io?.bytes_recv),
      interfaces: base.interfaces || []
    }
  })

  const disk = computed(() => info.value?.disk || [])

  const system = computed(() => {
    const s = info.value?.system || {}
    return {
      uptime: s.uptime?.total_seconds ?? 0,
      uptimeFormatted: s.uptime?.formatted || '-',
      processCount: toNumber(s.process_count),
      bootTime: s.boot_time || null
    }
  })

  /** 拉取系统快照 */
  async function loadInfo() {
    loading.value = true
    error.value = ''
    try {
      info.value = await fetchSystemInfo()
      lastUpdate.value = new Date()
      return true
    } catch (err) {
      error.value = err.message || '无法加载系统信息'
      return false
    } finally {
      loading.value = false
    }
  }

  /** 拉取进程列表 */
  async function loadProcesses() {
    try {
      const data = await fetchProcesses()
      processes.value = data?.processes || []
      return true
    } catch (err) {
      error.value = err.message || '无法加载进程列表'
      return false
    }
  }

  /** 接收 WebSocket 实时数据 */
  function applyLive(data) {
    if (!data) return
    if (data.cpu_percent !== undefined) {
      live.value.cpuPercent = toNumber(data.cpu_percent)
    }
    if (data.memory) {
      live.value.memoryPercent = toNumber(data.memory.percent)
      live.value.memoryUsed = toNumber(data.memory.used)
      live.value.memoryTotal = toNumber(data.memory.total)
    }
    if (data.network) {
      live.value.uploadSpeed = toNumber(data.network.upload_speed)
      live.value.downloadSpeed = toNumber(data.network.download_speed)
    }
    lastUpdate.value = new Date()
  }

  function setConnected(value) {
    connected.value = value
  }

  return {
    info,
    processes,
    loading,
    error,
    connected,
    lastUpdate,
    live,
    cpu,
    memory,
    network,
    disk,
    system,
    cpuPercent,
    memoryPercent,
    loadInfo,
    loadProcesses,
    applyLive,
    setConnected
  }
})
