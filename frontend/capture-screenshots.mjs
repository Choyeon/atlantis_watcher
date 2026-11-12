/**
 * README 代表性页面截图生成器
 *
 * 用法（需后端已运行）：
 *   AW_BASE_URL=http://127.0.0.1:26542 node capture-screenshots.mjs
 *
 * 设计约束：
 *  1. 屏幕共享通道 /ws/screen 用 Playwright 拦截并注入「示例桌面」JPEG 帧，
 *     绝不把真实桌面截进公开文档；示例帧由 Canvas 现场绘制，无需额外素材文件。
 *  2. 页面里的内网 IP、临时端口、主机名、用户名、本机路径统一示例化，
 *     避免公开仓库泄露环境信息。
 *  3. 输出 assets/screenshots/*.png，README 用相对路径引用。
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const BASE = process.env.AW_BASE_URL || 'http://127.0.0.1:26541'
const BASE_PORT = new URL(BASE).port || '26541'
const HERE = path.dirname(fileURLToPath(import.meta.url))
const OUT = path.resolve(HERE, '../assets/screenshots')
mkdirSync(OUT, { recursive: true })

// needle 必须是「页面主体独有」的文本：用侧栏里也出现的词（如「进程管理」）
// 会在懒加载 chunk 挂载前就判定完成，截出一张只有框架的白板。
const SHOTS = [
  { file: '01-overview.png', hash: '#/overview', needle: '磁盘分区', width: 1440, height: 900 },
  { file: '02-screen-control.png', hash: '#/screen', needle: '开始共享', width: 1440, height: 900, screen: true },
  { file: '03-processes.png', hash: '#/processes', needle: '自动刷新', width: 1440, height: 900, extraWait: 1400 },
  { file: '04-settings.png', hash: '#/settings', needle: '访问地址', width: 1440, height: 900 },
  { file: '05-mobile-overview.png', hash: '#/overview', needle: '磁盘分区', width: 390, height: 844 },
  { file: '06-mobile-screen.png', hash: '#/screen', needle: '开始共享', width: 390, height: 844, screen: true }
]

function escapeRe(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/* --------------------------------------------------------------------------
   示例桌面：纯 Canvas 绘制的深海仪表盘，作为屏幕共享画面的替身
   -------------------------------------------------------------------------- */
async function buildDemoFrame(browser) {
  const page = await browser.newPage()
  const base64 = await page.evaluate(() => {
    const c = document.createElement('canvas')
    c.width = 1280
    c.height = 720
    const x = c.getContext('2d')
    const DEEP = '#0b1220'
    const HULL = '#101d31'
    const PANEL = '#14243b'
    const EDGE = '#22364f'
    const ACCENT = '#35d6bd'
    const AMBER = '#f5b642'
    const TEXT = '#e8eef7'
    const DIM = '#8194ad'
    const font = (size, weight = '400') =>
      `${weight} ${size}px "Segoe UI", "Microsoft YaHei", Arial, sans-serif`

    function round(px, py, w, h, r, fill, stroke) {
      x.beginPath()
      x.moveTo(px + r, py)
      x.lineTo(px + w - r, py)
      x.quadraticCurveTo(px + w, py, px + w, py + r)
      x.lineTo(px + w, py + h - r)
      x.quadraticCurveTo(px + w, py + h, px + w - r, py + h)
      x.lineTo(px + r, py + h)
      x.quadraticCurveTo(px, py + h, px, py + h - r)
      x.lineTo(px, py + r)
      x.quadraticCurveTo(px, py, px + r, py)
      x.closePath()
      if (fill) { x.fillStyle = fill; x.fill() }
      if (stroke) { x.strokeStyle = stroke; x.lineWidth = 1; x.stroke() }
    }

    function line(points, color, width = 2) {
      x.beginPath()
      points.forEach(([px, py], i) => (i ? x.lineTo(px, py) : x.moveTo(px, py)))
      x.strokeStyle = color
      x.lineWidth = width
      x.lineJoin = 'round'
      x.stroke()
    }

    // 桌面背景 + 细网格
    x.fillStyle = DEEP
    x.fillRect(0, 0, 1280, 720)
    x.strokeStyle = 'rgba(53,214,189,0.045)'
    x.lineWidth = 1
    for (let i = 0; i <= 1280; i += 40) { x.beginPath(); x.moveTo(i, 0); x.lineTo(i, 720); x.stroke() }
    for (let i = 0; i <= 720; i += 40) { x.beginPath(); x.moveTo(0, i); x.lineTo(1280, i); x.stroke() }

    // 顶部窗口栏
    x.fillStyle = HULL
    x.fillRect(0, 0, 1280, 46)
    x.fillStyle = ACCENT
    x.fillRect(24, 17, 12, 12)
    x.font = font(15, '600')
    x.fillStyle = TEXT
    x.fillText('ATLANTIS  /  SYSTEM MONITOR', 48, 30)
    x.font = font(12)
    x.fillStyle = DIM
    x.fillText('LIVE SESSION   ·   192.168.1.24:26541', 940, 30)
    x.fillStyle = AMBER
    x.beginPath(); x.arc(1220, 23, 5, 0, Math.PI * 2); x.fill()
    x.fillStyle = ACCENT
    x.beginPath(); x.arc(1240, 23, 5, 0, Math.PI * 2); x.fill()

    // 三个指标卡
    const metrics = [
      { label: 'CPU', value: '42%', color: ACCENT, seed: 0.7 },
      { label: 'MEMORY', value: '68%', color: '#6ee7d7', seed: 1.3 },
      { label: 'NETWORK', value: '2.4 MB/s', color: AMBER, seed: 2.1 }
    ]
    metrics.forEach((m, i) => {
      const px = 30 + i * 268
      round(px, 72, 248, 128, 8, PANEL, EDGE)
      x.font = font(12, '600')
      x.fillStyle = DIM
      x.fillText(m.label, px + 18, 96)
      x.font = font(30, '600')
      x.fillStyle = TEXT
      x.fillText(m.value, px + 18, 136)
      const pts = []
      for (let k = 0; k < 30; k++) {
        const v = Math.sin(k * 0.55 + m.seed) * 9 + Math.sin(k * 0.19 + m.seed * 2) * 5
        pts.push([px + 18 + k * 7.2, 170 + v])
      }
      line(pts, m.color, 1.8)
    })

    // 主图表窗口
    round(30, 220, 900, 400, 8, PANEL, EDGE)
    x.font = font(13, '600')
    x.fillStyle = TEXT
    x.fillText('PERFORMANCE  /  LAST 60 SECONDS', 52, 248)
    x.font = font(11)
    x.fillStyle = DIM
    x.fillText('SAMPLED EVERY 2s', 52, 266)
    // 图表区网格
    const gx = 52, gy = 286, gw = 856, gh = 310
    x.strokeStyle = 'rgba(129,148,173,0.16)'
    for (let k = 0; k <= 4; k++) {
      const yy = gy + (gh / 4) * k
      x.beginPath(); x.moveTo(gx, yy); x.lineTo(gx + gw, yy); x.stroke()
    }
    for (let k = 0; k <= 10; k++) {
      const xx = gx + (gw / 10) * k
      x.beginPath(); x.moveTo(xx, gy); x.lineTo(xx, gy + gh); x.stroke()
    }
    // 两条曲线
    const cpu = [], mem = []
    for (let k = 0; k <= 60; k++) {
      const xx = gx + (gw / 60) * k
      cpu.push([xx, gy + 150 - Math.sin(k * 0.22) * 62 - Math.sin(k * 0.07) * 28])
      mem.push([xx, gy + 205 - Math.sin(k * 0.16 + 1.2) * 34 - Math.sin(k * 0.05) * 16])
    }
    // CPU 面积
    x.beginPath()
    x.moveTo(cpu[0][0], gy + gh)
    cpu.forEach(([px, py]) => x.lineTo(px, py))
    x.lineTo(cpu[cpu.length - 1][0], gy + gh)
    x.closePath()
    x.fillStyle = 'rgba(53,214,189,0.10)'
    x.fill()
    line(cpu, ACCENT, 2.4)
    line(mem, AMBER, 2)
    // 图例放在标题行右端，避免与副标题叠字
    const lx = gx + gw - 160
    x.font = font(11)
    x.fillStyle = ACCENT; x.fillRect(lx, 244, 12, 3)
    x.fillStyle = DIM; x.fillText('CPU', lx + 18, 248)
    x.fillStyle = AMBER; x.fillRect(lx + 66, 244, 12, 3)
    x.fillStyle = DIM; x.fillText('MEM', lx + 84, 248)

    // 右侧状态列
    round(950, 220, 300, 400, 8, PANEL, EDGE)
    x.font = font(13, '600')
    x.fillStyle = TEXT
    x.fillText('SERVICE STATUS', 972, 248)
    const rows = [
      ['HTTP SERVICE', 'ONLINE', ACCENT],
      ['SCREEN STREAM', 'LIVE', ACCENT],
      ['REMOTE CONTROL', 'ENABLED', ACCENT],
      ['AUTO START', 'OFF', DIM],
      ['UPTIME', '04:12:38', TEXT],
      ['LOG LEVEL', 'INFO', TEXT]
    ]
    rows.forEach((r, i) => {
      const yy = 290 + i * 52
      x.font = font(12)
      x.fillStyle = DIM
      x.fillText(r[0], 972, yy)
      x.font = font(12, '600')
      x.fillStyle = r[2]
      x.fillText(r[1], 1195 - x.measureText(r[1]).width, yy)
      x.strokeStyle = 'rgba(129,148,173,0.14)'
      x.beginPath(); x.moveTo(972, yy + 18); x.lineTo(1228, yy + 18); x.stroke()
    })

    // 底部任务栏
    x.fillStyle = HULL
    x.fillRect(0, 676, 1280, 44)
    x.fillStyle = ACCENT
    x.beginPath(); x.arc(28, 698, 7, 0, Math.PI * 2); x.fill()
    x.font = font(12, '600')
    x.fillStyle = TEXT
    x.fillText('Atlantis Watcher', 46, 703)
    x.font = font(11)
    x.fillStyle = DIM
    x.fillText('DEEP SEA CONSOLE  ·  v1.1.0', 210, 703)
    x.fillText('21:48', 1190, 703)

    return c.toDataURL('image/jpeg', 0.9).split(',')[1]
  })
  await page.close()
  return Buffer.from(base64, 'base64')
}

/* --------------------------------------------------------------------------
   环境信息脱敏：把真实 IP / 端口 / 主机名 / 用户名 / 路径换成示例值
   -------------------------------------------------------------------------- */
function buildRules(hostname, username) {
  const rules = [
    // 先保护监听地址 0.0.0.0，避免被下面的 IP 规则吃掉
    ['0\\.0\\.0\\.0', 'g', '__AW_ZERO__'],
    // 临时端口统一显示为默认端口
    [':' + escapeRe(BASE_PORT), 'g', ':26541'],
    ['(?:\\d{1,3}\\.){3}\\d{1,3}:\\d{2,5}', 'g', '192.168.1.24:26541'],
    ['(?:\\d{1,3}\\.){3}\\d{1,3}', 'g', '192.168.1.24'],
    ['__AW_ZERO__', 'g', '0.0.0.0']
  ]
  if (username) {
    rules.push([
      'C:\\\\Users\\\\' + escapeRe(username) + '\\\\AppData\\\\Local\\\\AtlantisWatcher',
      'g',
      '%LOCALAPPDATA%\\AtlantisWatcher'
    ])
  }
  if (hostname && hostname.length > 2) {
    rules.push([escapeRe(hostname), 'g', 'DESKTOP-ATLANTIS'])
  }
  return rules
}

async function sanitize(page, rules) {
  // 连接成功提示会常驻到手动关闭，产品截图里不需要
  await page.addStyleTag({ content: '.toasts { display: none !important; }' })
  await page.evaluate(entries => {
    const compiled = entries.map(([p, f, r]) => [new RegExp(p, f), r])
    // 设置/日志绝对路径来自运行时（隔离环境是 Temp\aw_ui_xxx\...），
    // 统一收敛成 %LOCALAPPDATA%\AtlantisWatcher\<文件名>，不暴露真实用户名与临时目录。
    const cleanLocalPath = value => value
      .replace(
        /C:\\Users\\[^\\\s]+\\AppData\\Local\\[^\s]*?AtlantisWatcher\\[^\s\\]+/g,
        full => '%LOCALAPPDATA%\\AtlantisWatcher\\' + full.split('\\').pop()
      )
      .replace(/D:\\PythonProjects\\[^\s\\]+/g, 'D:\\Projects\\AtlantisWatcher')
    const apply = value => {
      let s = cleanLocalPath(value)
      for (const [re, rep] of compiled) s = s.replace(re, rep)
      // 规则可能把路径中间层替换成示例主机名，统一收敛成标准形式
      return s.replace(
        /%LOCALAPPDATA%\\(?:[^\\\s]+\\)*AtlantisWatcher\\/g,
        '%LOCALAPPDATA%\\AtlantisWatcher\\'
      )
    }
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null)
    const nodes = []
    while (walker.nextNode()) nodes.push(walker.currentNode)
    for (const node of nodes) {
      const value = node.nodeValue
      if (!value || !value.trim()) continue
      const next = apply(value)
      if (next !== value) node.nodeValue = next
    }
    // 最终扫描：无论前面哪条规则生成了中间层目录，都把本地数据路径收敛成标准形式
    const normalizeLocalDataPath = text => text.replace(
      /(?:[A-Za-z]:\\Users\\[^\s]*?|%LOCALAPPDATA%\\[^\s]*?)AtlantisWatcher\\[^\s\\]+/g,
      full => '%LOCALAPPDATA%\\AtlantisWatcher\\' + full.split('\\').pop()
    )
    for (const node of nodes) {
      if (node.nodeValue) node.nodeValue = normalizeLocalDataPath(node.nodeValue)
    }
    for (const input of document.querySelectorAll('input')) {
      if (input.value) input.value = apply(input.value)
    }
    // 进程名换成通用示例名：保留真实数值/状态/操作列，但不公开本机装了什么
    const demoNames = [
      'explorer.exe', 'svchost.exe', 'chrome.exe', 'msedge.exe', 'code.exe',
      'python.exe', 'dwm.exe', 'services.exe', 'conhost.exe', 'powershell.exe',
      'RuntimeBroker.exe', 'SearchIndexer.exe', 'audiodg.exe', 'fontdrvhost.exe'
    ]
    document.querySelectorAll('td.proc-name').forEach((cell, i) => {
      const name = demoNames[i % demoNames.length]
      if (cell.firstChild && cell.firstChild.nodeType === 3) cell.firstChild.nodeValue = name
      else cell.textContent = name
      cell.setAttribute('title', name)
    })
  }, rules)
}

/* --------------------------------------------------------------------------
   主流程
   -------------------------------------------------------------------------- */
const errors = []
const hostname = os.hostname()
const username = os.userInfo().username
const rules = buildRules(hostname, username)

let sysHostname = ''
try {
  const res = await fetch(`${BASE}/api/system/info`)
  const info = await res.json()
  const data = info?.data ?? info
  sysHostname = data?.hostname || data?.system?.hostname || ''
} catch { /* 取不到就用 os.hostname() */ }
if (sysHostname && sysHostname.length > 2) {
  rules.splice(1, 0, [escapeRe(sysHostname), 'g', 'DESKTOP-ATLANTIS'])
}

const browser = await chromium.launch()
const frame = await buildDemoFrame(browser)
console.log(`DEMO_FRAME_BYTES=${frame.length}`)

for (const shot of SHOTS) {
  const ctx = await browser.newContext({
    viewport: { width: shot.width, height: shot.height },
    deviceScaleFactor: 1,
    reducedMotion: 'reduce'
  })
  const page = await ctx.newPage()
  page.on('pageerror', err => errors.push(`[${shot.file}] pageerror: ${err.message}`))

  try {
    // 屏幕共享通道：只推示例帧，不连真实屏幕流
    await page.routeWebSocket('**/ws/screen', ws => {
      ws.send(frame)
      // 有限帧 + unref：定时器必须自行结束，否则 Node 事件循环无法退出，
      // 表现为截图全部落盘但进程一直挂着直到外层超时。
      let sent = 0
      const timer = setInterval(() => {
        sent += 1
        try { ws.send(frame) } catch { clearInterval(timer) }
        if (sent >= 4) clearInterval(timer)
      }, 700)
      timer.unref?.()
    })
    // 控制通道：静默，避免截图时出现 ACK/toast 干扰
    await page.routeWebSocket('**/ws/control', () => {})

    await page.goto(`${BASE}/${shot.hash}`, { waitUntil: 'domcontentloaded', timeout: 25000 })
    await page.waitForFunction(
      needle => document.body.innerText.includes(needle),
      shot.needle,
      { timeout: 25000 }
    )
    await page.waitForTimeout(1000 + (shot.extraWait || 0))

    if (shot.screen) {
      await page.locator('button:has-text("开始共享")').first().click()
      await page.waitForFunction(() => document.body.innerText.includes('LIVE'), null, { timeout: 12000 })
      await page.waitForTimeout(2800) // 让连接 toast 自然消失
    }

    await sanitize(page, rules)
    await page.screenshot({ path: path.join(OUT, shot.file), animations: 'disabled' })
    console.log(`SAVED ${shot.file}  ${shot.width}x${shot.height}`)
  } catch (err) {
    errors.push(`[${shot.file}] ${err.message}`)
  } finally {
    await ctx.close()
  }
}

await browser.close()
if (errors.length) {
  console.error('CAPTURE_FAILED', errors)
  process.exit(1)
}
console.log('CAPTURE_OK', SHOTS.length, 'screenshots ->', OUT)
