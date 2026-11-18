/**
 * 玻璃材质探针
 * 检查 GlassTabBar 的折射层、拖动放大镜与主题表现
 *
 * 用法：
 *   node verify-glass.mjs
 *   AW_BASE=http://127.0.0.1:5173 node verify-glass.mjs
 */
import { chromium } from 'playwright'
import fs from 'node:fs'

const BASE = process.env.AW_BASE || 'http://127.0.0.1:26541'
const OUT = process.cwd() + '/shots'
fs.mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const errors = []
const envWarnings = []

/** 后端未启动时 /api 与 /ws 的连通性报错属于环境噪声 */
function onConsole(m) {
  if (m.type() !== 'error') return
  const text = m.text()
  const url = m.location()?.url || ''
  if ((/Failed to load resource/.test(text) && url.includes('/api/')) || text.includes('/ws/monitor')) {
    envWarnings.push(`[环境] ${text} @ ${url}`)
    return
  }
  errors.push(`[console] ${text}`)
}

const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
  deviceScaleFactor: 2
})
const page = await ctx.newPage()
page.on('console', onConsole)
page.on('pageerror', e => errors.push('[pageerror] ' + e.message))

await page.goto(BASE + '/', { waitUntil: 'networkidle' })
await page.waitForTimeout(1500)

// 切到终端页（背景有丰富内容，最能体现折射）
await page.evaluate(() => { window.location.hash = '#/terminal'; })
await page.waitForTimeout(2200)

const probe = await page.evaluate(() => {
  const bar = document.querySelector('.tabbar__pill')
  const out = { barFound: !!bar }
  if (!bar) return out

  // 材质层在 GlassTabBar 的 Shadow DOM 内
  const sr = bar.shadowRoot
  out.shadow = !!sr
  if (!sr) return out

  const fx = sr.querySelector('gl-fx')
  out.fxInjected = !!fx
  if (fx) {
    out.layers = [...fx.children].map(c => c.tagName.toLowerCase() + (c.className ? '.' + c.className : ''))
    const b = fx.querySelector('gl-l.b')
    if (b) {
      const cs = getComputedStyle(b)
      out.backdropLayer = {
        backdropFilter: cs.backdropFilter || cs.webkitBackdropFilter,
        hasSvgFilter: /url\(/.test(cs.backdropFilter || cs.webkitBackdropFilter || '')
      }
    }
    const svg = fx.querySelector('svg')
    if (svg) {
      out.filters = [...svg.querySelectorAll('filter')].map(f => ({
        id: f.id,
        hasDisplacement: !!f.querySelector('feDisplacementMap')
      }))
    }
  }

  // 放大镜是独立的玻璃表面，拖动时透明度上升
  const lens = sr.querySelector('.lens')
  out.lens = !!lens
  if (lens) {
    out.lensFx = !!lens.querySelector('gl-fx')
    out.lensTransform = lens.style.transform || ''
    out.lensVisibility = getComputedStyle(lens).visibility
  }

  // glass-tab 是 light DOM 的子元素（slot 进入 Shadow DOM）
  out.tabs = bar.querySelectorAll('glass-tab').length
  out.pillPart = !!sr.querySelector('[part="indicator"]')
  out.lensPart = !!sr.querySelector('[part="lens"]')

  // 宿主不应自带 background（会成为 backdrop root 阻断折射）
  const host = getComputedStyle(bar)
  out.hostBackground = host.backgroundColor
  out.hostBackdrop = host.backdropFilter

  return out
})

console.log(JSON.stringify(probe, null, 2))
await page.screenshot({ path: OUT + '/gl-01-terminal.png' })

// 概览页截图
await page.evaluate(() => { window.location.hash = '#/overview'; })
await page.waitForTimeout(1800)
await page.screenshot({ path: OUT + '/gl-02-overview.png' })

// 浅色主题
await page.evaluate(() => {
  document.documentElement.setAttribute('data-theme', 'light')
  window.location.hash = '#/files'
})
await page.waitForTimeout(1800)
await page.screenshot({ path: OUT + '/gl-03-light.png' })

console.log('\n=== 环境告警（后端未启动） ===')
console.log(envWarnings.length ? `${envWarnings[0]}\n… 共 ${envWarnings.length} 条` : '(无)')
console.log('\n=== 控制台错误 ===')
console.log(errors.length ? errors.join('\n') : '(无)')

await browser.close()
