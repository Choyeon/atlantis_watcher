/**
 * 局域网主机嗅探
 *
 * 场景：APK 安装后，前端资源打包在应用内，需要找到运行 Atlantis Watcher 的主机。
 * 浏览器/WebView 无法直接探测 TCP 端口，但可以用 HTTP 请求反推端口是否开放：
 * 向候选主机的 /health 发起请求，能拿到 Atlantis Watcher 的健康响应即命中。
 *
 * 策略：
 *   1. 优先读取浏览器/WebView 已知的自身 IP（部分环境可从 RTCPeerConnection 取到）
 *   2. 由自身 IP 推导网段，扫描同 /24 网段的全部主机
 *   3. 高并发 + 短超时，尽快收敛
 *   4. 命中后立即返回首个可用地址
 */

/** 单个探测请求的超时（毫秒）——局域网响应通常 <100ms，600ms 足够容忍丢包 */
const PROBE_TIMEOUT = 600

/** 整轮扫描的总超时（毫秒）——超时即放弃，进入手动配置 */
const SCAN_TIMEOUT = 8000

/** 并发数——过高会触发移动端 WebView 的连接数限制 */
const CONCURRENCY = 24

/** 目标端口 */
const PORT = 26541

/** 扫描路径——后端健康检查端点，返回 JSON 且带 CORS 头 */
const HEALTH_PATH = '/health'

/**
 * 获取本机在局域网中的 IP 候选。
 * RTCPeerConnection 的 ICE 候选里包含本机候选地址，是浏览器里
 * 拿到自身局域网 IP 最可靠的方式（无需 STUN 服务器也能拿到 host candidate）。
 */
export async function getLocalIPs() {
  const ips = new Set()

  // 1. WebRTC ICE 候选
  try {
    if (typeof RTCPeerConnection !== 'undefined') {
      const pc = new RTCPeerConnection({ iceServers: [] })
      const gathered = new Promise(resolve => {
        const timer = setTimeout(resolve, 1200)
        pc.onicecandidate = e => {
          if (!e.candidate) {
            clearTimeout(timer)
            resolve()
            return
          }
          const parts = e.candidate.candidate.split(' ')
          const addr = parts[4]
          if (addr && /^\d+\.\d+\.\d+\.\d+$/.test(addr)) ips.add(addr)
        }
      })
      pc.createDataChannel('probe')
      await pc.createOffer()
      await pc.setLocalDescription(await pc.createOffer())
      await gathered
      pc.close()
    }
  } catch {
    /* WebRTC 不可用时忽略 */
  }

  // 2. 部分 Android WebView 暴露的接口
  try {
    if (typeof window !== 'undefined') {
      const conn = window.navigator && window.navigator.connection
      const addr = conn && (conn.localIp || conn.ip)
      if (addr && /^\d+\.\d+\.\d+\.\d+$/.test(addr)) ips.add(addr)
    }
  } catch {
    /* 忽略 */
  }

  return [...ips]
}

/**
 * 由本机 IP 推导候选网段。
 * 例如 192.168.2.110 → 扫描 192.168.2.1 ~ 192.168.2.254
 */
export function expandSubnet(ip) {
  const parts = ip.split('.').map(Number)
  if (parts.length !== 4 || parts.some(n => !Number.isInteger(n) || n < 0 || n > 255)) {
    return []
  }
  const hosts = []
  for (let h = 1; h <= 254; h++) {
    hosts.push(`${parts[0]}.${parts[1]}.${parts[2]}.${h}`)
  }
  return hosts
}

/**
 * 无法取得本机 IP 时的兜底网段。
 *
 * 移动端 WebView 常拿不到自身的局域网地址（WebRTC 候选被裁剪、
 * 或未授予相应权限），此时按常见家用/办公网段轮询。
 * 覆盖范围有限，但配合并发探测仍能命中大多数场景。
 */
const FALLBACK_SUBNETS = [
  '192.168.1.1',
  '192.168.0.1',
  '192.168.2.1',
  '10.0.0.1',
  '10.0.1.1',
  '172.16.0.1'
]

/**
 * 探测单个主机是否运行 Atlantis Watcher。
 * @returns {Promise<string|null>} 命中返回主机地址，否则 null
 */
async function probeHost(ip) {
  const url = `http://${ip}:${PORT}${HEALTH_PATH}`
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), PROBE_TIMEOUT)
  try {
    const res = await fetch(url, {
      method: 'GET',
      signal: ctrl.signal,
      cache: 'no-store'
    })
    if (!res.ok) return null
    const data = await res.json()
    // 校验响应体，避免误判成其他占用同端口的服务
    if (data && (data.service === 'Atlantis Watcher' || data.status === 'healthy')) {
      return `http://${ip}:${PORT}`
    }
    return null
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

/**
 * 扫描局域网，返回首个可用主机地址。
 *
 * @param {object} options
 * @param {(found: string, total: number) => void} [options.onProgress] 进度回调
 * @param {string[]} [options.extraCandidates] 额外候选（如用户手动输入过的地址）
 * @returns {Promise<{host: string|null, scanned: number, timedOut: boolean}>}
 */
export async function scanLanHosts(options = {}) {
  const { onProgress, extraCandidates = [] } = options

  const localIPs = await getLocalIPs()
  const candidates = new Set(extraCandidates.filter(Boolean))

  // 由本机 IP 展开网段
  for (const ip of localIPs) {
    for (const host of expandSubnet(ip)) candidates.add(host)
  }

  // 兜底网段：即使拿不到本机 IP 也有一组候选可探
  // （本机网段已知时，把兜底网段排到后面，避免拖慢）
  for (const seed of FALLBACK_SUBNETS) {
    for (const host of expandSubnet(seed)) candidates.add(host)
  }

  const list = [...candidates]
  const total = list.length
  let scanned = 0

  // 整轮超时控制
  const deadline = Date.now() + SCAN_TIMEOUT

  // 优先探测已知/手动地址（命中最快）
  const priority = list.filter(h => extraCandidates.includes(h))
  const rest = list.filter(h => !extraCandidates.includes(h))
  const ordered = [...priority, ...rest]

  let hit = null

  const worker = async () => {
    while (ordered.length && !hit) {
      if (Date.now() > deadline) return
      const ip = ordered.shift()
      const result = await probeHost(ip)
      scanned++
      if (result) {
        hit = result
        if (onProgress) onProgress(result, scanned, total)
        return
      }
      if (scanned % 16 === 0 && onProgress) {
        onProgress(null, scanned, total)
      }
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, ordered.length) }, () => worker())
  )

  return {
    host: hit,
    scanned,
    timedOut: !hit && Date.now() > deadline
  }
}
