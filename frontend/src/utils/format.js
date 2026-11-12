/** 格式化工具函数 */

/** 字节数 → 可读字符串 */
export function formatBytes(bytes, decimals = 1) {
  const num = Number(bytes)
  if (!Number.isFinite(num) || num <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const i = Math.min(Math.floor(Math.log(num) / Math.log(1024)), units.length - 1)
  const value = num / Math.pow(1024, i)
  return `${value.toFixed(i === 0 ? 0 : decimals)} ${units[i]}`
}

/** 字节速率 → 可读字符串 */
export function formatSpeed(bytesPerSecond) {
  const num = Number(bytesPerSecond)
  if (!Number.isFinite(num) || num <= 0) return '0 B/s'
  return `${formatBytes(num)}/s`
}

/** 时间戳 → 本地时间字符串 */
export function formatDateTime(value) {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleString('zh-CN', { hour12: false })
}

/** 时间戳 → 相对时间 */
export function formatRelative(value) {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '-'
  const diff = Date.now() - d.getTime()
  const abs = Math.abs(diff)
  const min = 60_000
  const hour = 60 * min
  const day = 24 * hour
  if (abs < min) return '刚刚'
  if (abs < hour) return `${Math.floor(abs / min)} 分钟前`
  if (abs < day) return `${Math.floor(abs / hour)} 小时前`
  return `${Math.floor(abs / day)} 天前`
}

/** 秒 → 运行时长 */
export function formatUptime(seconds) {
  const s = Math.max(0, Math.floor(Number(seconds) || 0))
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d} 天 ${h} 小时`
  if (h > 0) return `${h} 小时 ${m} 分`
  return `${m} 分钟`
}

/** 百分比 → 保留一位小数 */
export function formatPercent(value, decimals = 1) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '0.0'
  return num.toFixed(decimals)
}

/** 数值安全转换 */
export function toNumber(value, fallback = 0) {
  const num = Number(value)
  return Number.isFinite(num) ? num : fallback
}

/** HTML 转义（渲染 innerHTML 时兜底） */
export function escapeHtml(text) {
  if (text === null || text === undefined) return ''
  return String(text).replace(/[&<>"']/g, m => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  })[m])
}

/** 路径分隔符归一化为 Windows 反斜杠 */
export function normalizePath(path) {
  if (!path) return ''
  let p = String(path).replace(/\//g, '\\')
  // 保留盘符根目录的单反斜杠
  if (/^[A-Za-z]:\\$/.test(p)) return p
  p = p.replace(/\\+$/, '')
  return p || '\\'
}

/** 拼接目录与文件名 */
export function joinPath(dir, name) {
  const base = normalizePath(dir)
  if (!base) return name
  return base.endsWith('\\') ? `${base}${name}` : `${base}\\${name}`
}

/** 取父目录 */
export function parentPath(path) {
  const p = normalizePath(path)
  if (!p) return ''
  const idx = p.lastIndexOf('\\')
  if (idx <= 1) return p.slice(0, 2) || '\\'
  return p.slice(0, idx)
}

/** 取路径最后一段 */
export function baseName(path) {
  const p = normalizePath(path)
  const idx = p.lastIndexOf('\\')
  return idx >= 0 ? p.slice(idx + 1) : p
}

/** 按占用率判断颜色语义 */
export function usageLevel(percent) {
  const p = Number(percent) || 0
  if (p >= 90) return 'danger'
  if (p >= 75) return 'warn'
  return 'ok'
}

/** 进程状态 → 语义色 */
export function processStatusLevel(status) {
  const map = {
    running: 'ok',
    sleeping: 'info',
    stopped: 'warn',
    zombie: 'danger'
  }
  return map[status] || 'info'
}
