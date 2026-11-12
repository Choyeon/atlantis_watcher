/**
 * 液态玻璃移动端专项验证
 * 验证 iOS 26 风格的导航栏、Sheet 弹窗、安全区适配
 */
import { chromium, devices } from 'playwright'
import { mkdirSync } from 'node:fs'

const BASE = 'http://127.0.0.1:26541'
const OUT = 'shots'
mkdirSync(OUT, { recursive: true })

const errors = []

const browser = await chromium.launch()

// iPhone 15 Pro 模拟
const iphone = devices['iPhone 14 Pro']
const ctx = await browser.newContext({
  ...iphone,
  deviceScaleFactor: 2,
  isMobile: true,
  hasTouch: true
})
const page = await ctx.newPage()

page.on('console', m => {
  if (m.type() === 'error') errors.push(`[console] ${m.text()}`)
})
page.on('pageerror', e => errors.push(`[pageerror] ${e.message}`))

await page.goto(`${BASE}/#/overview`, { waitUntil: 'networkidle' })
await page.waitForTimeout(2500)

// 1. 概览页（液态玻璃导航）
await page.screenshot({ path: `${OUT}/lg-01-overview.png` })
console.log('✓ lg-01-overview')

// 2. 检查玻璃导航关键元素
// 材质由 glassy-liquid 注入（gl-fx 图层 + SVG 位移滤镜）
const glass = await page.locator('.tabbar__pill').count()
const fx = await page.locator('.tabbar__pill gl-fx').count()
const indicator = await page.locator('.lg-liquid-indicator').count()
const backdrop = await page.evaluate(() => {
  const el = document.querySelector('.tabbar__pill gl-l.b')
  if (!el) return 'none'
  const cs = getComputedStyle(el)
  return cs.backdropFilter || cs.webkitBackdropFilter || 'none'
})
console.log(`[液态玻璃] 药丸=${glass} 材质层=${fx} 指示器=${indicator}`)
console.log(`[液态玻璃] 折射滤镜 = ${backdrop}`)

// 3. 检查玻璃是否真的在折射（backdrop-filter: url()）
const refract = await page.evaluate(() => {
  const el = document.querySelector('.tabbar__pill')
  if (!el) return 'none'
  const s = getComputedStyle(el, '::before')
  return s.backdropFilter || 'none'
})
console.log(`[折射层] ::before backdrop-filter = ${refract}`)

// 4. 切换 Tab → 液态指示器应移动
const before = await page.locator('.lg-liquid-indicator').evaluate(el => el.style.transform)
await page.locator('.tabbar__item', { hasText: '终端' }).click()
await page.waitForTimeout(1200)
const after = await page.locator('.lg-liquid-indicator').evaluate(el => el.style.transform)
console.log(`[液态指示器] 切换前 ${before} → 切换后 ${after}  移动=${before !== after}`)
await page.screenshot({ path: `${OUT}/lg-02-terminal.png` })
console.log('✓ lg-02-terminal')

// 5. Sheet 弹窗（iOS 底部抽屉）
await page.evaluate(() => {
  window.location.hash = '#/power'
})
await page.waitForTimeout(1200)
await page.getByRole('button', { name: /立即关机/ }).click()
await page.waitForTimeout(900)
const sheet = await page.locator('.modal').evaluate(el => {
  const s = getComputedStyle(el)
  return { radius: s.borderRadius, animation: s.animationName }
})
console.log(`[Sheet] border-radius=${sheet.radius} animation=${sheet.animation}`)
await page.screenshot({ path: `${OUT}/lg-03-sheet.png` })
console.log('✓ lg-03-sheet')

await page.getByRole('button', { name: '取消', exact: true }).click()
await page.waitForTimeout(500)

// 6. 大标题
const largeTitle = await page.locator('.topbar__title').evaluate(el => ({
  size: getComputedStyle(el).fontSize,
  weight: getComputedStyle(el).fontWeight
}))
console.log(`[iOS 大标题] ${largeTitle.size} / weight ${largeTitle.weight}`)

// 7. 安全区
const padding = await page.locator('.shell__content').evaluate(el => getComputedStyle(el).paddingBottom)
console.log(`[安全区] 内容区底部 padding = ${padding}`)

// 8. 文件页
await page.evaluate(() => {
  window.location.hash = '#/files'
})
await page.waitForTimeout(2000)
await page.screenshot({ path: `${OUT}/lg-04-files.png` })
console.log('✓ lg-04-files')

// 9. 浅色主题下的玻璃
await page.evaluate(() => {
  document.documentElement.setAttribute('data-theme', 'light')
})
await page.waitForTimeout(700)
await page.screenshot({ path: `${OUT}/lg-05-light.png` })
console.log('✓ lg-05-light')

// 10. 桌面端不应受影响
const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const dpage = await desktop.newPage()
dpage.on('pageerror', e => errors.push(`[desktop-pageerror] ${e.message}`))
await dpage.goto(`${BASE}/#/overview`, { waitUntil: 'networkidle' })
await dpage.waitForTimeout(2000)
const tabbarHidden = await dpage.locator('.tabbar').isVisible()
const sidebarVisible = await dpage.locator('.rail').isVisible()
console.log(`[桌面端] 底部栏隐藏=${!tabbarHidden} 侧栏可见=${sidebarVisible}`)
await dpage.screenshot({ path: `${OUT}/lg-06-desktop.png` })
console.log('✓ lg-06-desktop')

await browser.close()

console.log('\n===== 错误 =====')
console.log(errors.length ? errors.join('\n') : '无错误 ✓')
process.exit(errors.length ? 1 : 0)
