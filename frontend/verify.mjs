/**
 * 可视化验证脚本
 * 用无头 Chromium 打开每个路由，捕获控制台错误 + 页面异常，并截图。
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const BASE = process.env.AW_BASE_URL || 'http://127.0.0.1:26541'
const OUT = 'shots'
mkdirSync(OUT, { recursive: true })

const ROUTES = [
  { hash: '#/overview', name: '01-overview' },
  { hash: '#/power', name: '02-power' },
  { hash: '#/monitor', name: '03-monitor' },
  { hash: '#/files', name: '04-files' },
  { hash: '#/terminal', name: '05-terminal' },
  { hash: '#/screen', name: '06-screen' }
]

const errors = []

const browser = await chromium.launch()

// 桌面视口
const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
const page = await desktop.newPage()

page.on('console', msg => {
  if (msg.type() === 'error') errors.push(`[console:${msg.location().url.split('/').pop()}] ${msg.text()}`)
})
page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`))
page.on('requestfailed', req => {
  const url = req.url()
  if (url.includes('/static/')) errors.push(`[404-asset] ${url} :: ${req.failure()?.errorText}`)
})

await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
await page.waitForTimeout(2500)

for (const route of ROUTES) {
  await page.evaluate(h => {
    window.location.hash = h
  }, route.hash)
  // 等待该视图的数据加载完成（进程表/文件列表渲染出条目）
  await page
    .waitForFunction(
      () => {
        const rows = document.querySelectorAll('.file-row, table tbody tr')
        return rows.length > 0 || document.querySelector('.gauge__num')
      },
      { timeout: 8000 }
    )
    .catch(() => {})
  await page.waitForTimeout(900)
  await page.screenshot({ path: `${OUT}/${route.name}.png` })
  console.log(`✓ 截图 ${route.name}`)
}

// 浅色主题验证
await page.evaluate(() => {
  document.documentElement.setAttribute('data-theme', 'light')
})
await page.waitForTimeout(600)
await page.screenshot({ path: `${OUT}/07-light-theme.png` })
console.log('✓ 截图 07-light-theme')

// 交互验证：文件列表是否渲染出真实条目
await page.evaluate(() => {
  window.location.hash = '#/files'
})
await page.waitForTimeout(2000)
// 等待文件列表真正渲染出条目（后端异步加载）
await page
  .waitForFunction(() => document.querySelectorAll('.file-row').length > 0, { timeout: 10000 })
  .catch(() => {})
await page.waitForTimeout(500)
const fileRows = await page.locator('.file-row').count()
const firstFiles = await page.locator('.file-row__name').allTextContents()
console.log(`\n[文件列表] 渲染行数 = ${fileRows}`)
console.log(`[文件列表] 前 5 项 = ${firstFiles.slice(0, 5).join(', ')}`)

// 交互验证：监控页进程表
await page.evaluate(() => {
  window.location.hash = '#/monitor'
})
await page.waitForTimeout(2200)
const procRows = await page.locator('table tbody tr').count()
const firstProc = await page.locator('.proc-name').first().textContent().catch(() => '-')
console.log(`[进程表] 行数 = ${procRows} | 首行 = ${firstProc}`)

// 交互验证：概览页读数
await page.evaluate(() => {
  window.location.hash = '#/overview'
})
await page.waitForTimeout(2000)
const gauges = await page.locator('.gauge__num').allTextContents()
const labels = await page.locator('.gauge .aw-label').allTextContents()
console.log(`[概览读数] ${labels.map((l, i) => `${l}=${gauges[i]}`).join(' | ')}`)

// 交互验证：终端执行命令
await page.evaluate(() => {
  window.location.hash = '#/terminal'
})
await page.waitForTimeout(1200)
await page.locator('.terminal__input').fill('echo playwright-terminal-ok')
await page.locator('.terminal__input').press('Enter')
await page.waitForTimeout(3000)
const termText = await page.locator('.terminal__out').textContent()
console.log(`[终端] 包含回显 = ${termText.includes('playwright-terminal-ok')}`)

// 移动端视口
const mobile = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 2,
  isMobile: true,
  hasTouch: true
})
const mpage = await mobile.newPage()
mpage.on('pageerror', err => errors.push(`[mobile-pageerror] ${err.message}`))
await mpage.goto(`${BASE}/#/overview`, { waitUntil: 'networkidle' })
await mpage.waitForTimeout(2200)
await mpage.screenshot({ path: `${OUT}/08-mobile-overview.png` })
console.log('✓ 截图 08-mobile-overview')
const tabbarVisible = await mpage.locator('.tabbar').isVisible()
console.log(`[移动端] 底部标签栏可见 = ${tabbarVisible}`)

await mpage.evaluate(() => {
  window.location.hash = '#/files'
})
await mpage.waitForTimeout(1800)
await mpage.screenshot({ path: `${OUT}/09-mobile-files.png` })
console.log('✓ 截图 09-mobile-files')

await browser.close()

console.log('\n===== 控制台/网络错误 =====')
if (errors.length === 0) {
  console.log('无错误 ✓')
} else {
  errors.forEach(e => console.log('  ' + e))
}
process.exit(errors.length ? 1 : 0)
