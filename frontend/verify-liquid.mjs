/**
 * 液态玻璃移动端专项验证
 * 验证 iOS 27 风格导航栏、拖动放大镜、Sheet 弹窗、安全区适配
 *
 * 用法：
 *   node verify-liquid.mjs                       # 默认连 FastAPI :26541
 *   AW_BASE=http://127.0.0.1:5173 node verify-liquid.mjs   # 连 Vite dev
 */
import { chromium, devices } from 'playwright'
import { mkdirSync } from 'node:fs'

const BASE = process.env.AW_BASE || 'http://127.0.0.1:26541'
const OUT = 'shots'
mkdirSync(OUT, { recursive: true })

const errors = []
const envWarnings = []

/** 后端未启动时 /api 与 /ws 的连通性报错属于环境噪声，不计入前端错误 */
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

const browser = await chromium.launch()

// iPhone 模拟
const iphone = devices['iPhone 14 Pro']
const ctx = await browser.newContext({
  ...iphone,
  deviceScaleFactor: 2,
  isMobile: true,
  hasTouch: true
})
const page = await ctx.newPage()
page.on('console', onConsole)
page.on('pageerror', e => errors.push(`[pageerror] ${e.message}`))

await page.goto(`${BASE}/#/overview`, { waitUntil: 'networkidle' })
await page.waitForTimeout(2500)

// 1. 概览页（液态玻璃导航）
await page.screenshot({ path: `${OUT}/lg-01-overview.png` })
console.log('✓ lg-01-overview')

// 2. 检查玻璃导航关键元素（材质层在 GlassTabBar 的 Shadow DOM 内）
const glass = await page.locator('.tabbar__pill').count()
const tabs = await page.locator('.tabbar__pill glass-tab').count()
const optics = await page.evaluate(() => {
  const bar = document.querySelector('.tabbar__pill')
  if (!bar) return { bar: false }
  const sr = bar.shadowRoot
  if (!sr) return { bar: true, shadow: false }
  const lens = sr.querySelector('.lens')
  const barFx = sr.querySelector('gl-fx')
  const lensFx = lens?.querySelector('gl-fx')
  const backdrop = sr.querySelector('gl-l.b')
  const cs = backdrop && getComputedStyle(backdrop)
  return {
    bar: true,
    shadow: true,
    lens: !!lens,
    pillPart: !!sr.querySelector('[part="indicator"]'),
    fx: !!barFx,
    lensFx: !!lensFx,
    backdropFilter: cs ? cs.backdropFilter || cs.webkitBackdropFilter || 'none' : 'none',
    refraction: bar.getAttribute('refraction'),
    bezel: bar.getAttribute('bezel')
  }
})
console.log(`[液态玻璃] 药丸=${glass} Tab=${tabs} 放大镜=${optics.lens} 材质层=${optics.fx}`)
console.log(`[液态玻璃] 折射滤镜 = ${optics.backdropFilter}`)
console.log(`[参数] refraction=${optics.refraction} bezel=${optics.bezel}`)
if (tabs !== 4) errors.push(`[导航] 期望 4 个 Tab，实际 ${tabs}`)

// 3. 拖动测试：从「概览」按住拖到「终端」，放大镜应跟随并在松手后切换路由
const first = await page.locator('glass-tab').first().boundingBox()
const last = await page.locator('glass-tab').last().boundingBox()
if (first && last) {
  const y = first.y + first.height / 2
  const fromX = first.x + first.width / 2
  const toX = last.x + last.width / 2

  await page.mouse.move(fromX, y)
  await page.mouse.down()
  await page.mouse.move((fromX + toX) / 2, y, { steps: 8 })
  await page.waitForTimeout(120)

  const midDrag = await page.evaluate(() => {
    const lens = document.querySelector('.tabbar__pill')?.shadowRoot?.querySelector('.lens')
    return {
      transform: lens?.style.transform || '',
      visible: lens ? getComputedStyle(lens).visibility !== 'hidden' : false
    }
  })
  console.log(`[拖动中] 放大镜 transform = ${midDrag.transform || '(空)'}  可见=${midDrag.visible}`)
  await page.screenshot({ path: `${OUT}/lg-02-drag.png` })
  console.log('✓ lg-02-drag')

  await page.mouse.move(toX, y, { steps: 8 })
  // 库内部用弹簧追踪指针，真实手指拖动在松手前也会有短暂停留
  await page.waitForTimeout(180)
  await page.mouse.up()
  await page.waitForTimeout(900)

  const hash = await page.evaluate(() => location.hash)
  console.log(`[拖动切换] 松手后路由 = ${hash}  正确=${hash === '#/terminal'}`)
  if (hash !== '#/terminal') errors.push(`[drag] 松手后路由错误：${hash}`)
  await page.screenshot({ path: `${OUT}/lg-03-terminal.png` })
  console.log('✓ lg-03-terminal')
} else {
  errors.push('[drag] 无法获取 Tab 位置')
}

// 4. 点击切换仍可用
await page.locator('glass-tab', { hasText: '文件' }).click()
await page.waitForTimeout(900)
const afterClick = await page.evaluate(() => location.hash)
console.log(`[点击切换] 路由 = ${afterClick}  正确=${afterClick === '#/files'}`)
if (afterClick !== '#/files') errors.push(`[click] 路由错误：${afterClick}`)
await page.screenshot({ path: `${OUT}/lg-04-files.png` })
console.log('✓ lg-04-files')

// 5. 顶栏「更多」菜单：低频功能仍可达
await page.locator('button[aria-label="更多功能"]').click()
await page.waitForTimeout(300)
const moreItems = await page.locator('.topbar__more-item').count()
const moreVisible = await page.locator('.topbar__more-menu').isVisible()
console.log(`[更多菜单] 可见=${moreVisible} 项目=${moreItems}`)
if (!moreVisible || moreItems !== 3) errors.push('[more] 菜单未正确展开')
await page.screenshot({ path: `${OUT}/lg-05-more.png` })
console.log('✓ lg-05-more')

for (const [label, hash] of [
  ['屏幕共享', '#/screen'],
  ['快捷操作', '#/power'],
  ['设置', '#/settings']
]) {
  if (!(await page.locator('.topbar__more-menu').isVisible())) {
    await page.locator('button[aria-label="更多功能"]').click()
    await page.waitForTimeout(200)
  }
  await page.locator('.topbar__more-item', { hasText: label }).click()
  await page.waitForTimeout(700)
  const h = await page.evaluate(() => location.hash)
  console.log(`[更多→${label}] 路由 = ${h}  正确=${h === hash}`)
  if (h !== hash) errors.push(`[more] ${label} 路由错误：${h}`)
}

// 6. Sheet 弹窗（iOS 底部抽屉）
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
await page.screenshot({ path: `${OUT}/lg-06-sheet.png` })
console.log('✓ lg-06-sheet')

await page.getByRole('button', { name: '取消', exact: true }).click()
await page.waitForTimeout(500)

// 7. 大标题
const largeTitle = await page.locator('.topbar__title').evaluate(el => ({
  size: getComputedStyle(el).fontSize,
  weight: getComputedStyle(el).fontWeight
}))
console.log(`[iOS 大标题] ${largeTitle.size} / weight ${largeTitle.weight}`)

// 8. 安全区
const padding = await page.locator('.shell__content').evaluate(el => getComputedStyle(el).paddingBottom)
console.log(`[安全区] 内容区底部 padding = ${padding}`)

// 9. 文件页
await page.evaluate(() => {
  window.location.hash = '#/files'
})
await page.waitForTimeout(2000)
await page.screenshot({ path: `${OUT}/lg-07-files.png` })
console.log('✓ lg-07-files')

// 10. 浅色主题下的玻璃
await page.evaluate(() => {
  document.documentElement.setAttribute('data-theme', 'light')
})
await page.waitForTimeout(700)
await page.screenshot({ path: `${OUT}/lg-08-light.png` })
console.log('✓ lg-08-light')

// 11. 桌面端不应受影响
const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const dpage = await desktop.newPage()
dpage.on('pageerror', e => errors.push(`[desktop-pageerror] ${e.message}`))
await dpage.goto(`${BASE}/#/overview`, { waitUntil: 'networkidle' })
await dpage.waitForTimeout(2000)
const tabbarHidden = await dpage.locator('.tabbar').isVisible()
const sidebarVisible = await dpage.locator('.rail').isVisible()
const moreHidden = !(await dpage.locator('button[aria-label="更多功能"]').isVisible())
console.log(`[桌面端] 底部栏隐藏=${!tabbarHidden} 侧栏可见=${sidebarVisible} 更多按钮隐藏=${moreHidden}`)
if (!moreHidden) errors.push('[desktop] 更多按钮不应在桌面端显示')
await dpage.screenshot({ path: `${OUT}/lg-09-desktop.png` })
console.log('✓ lg-09-desktop')

await browser.close()

console.log(`\n===== 环境告警（后端未启动） =====\n${envWarnings.length ? envWarnings.slice(0, 2).join('\n') + `\n… 共 ${envWarnings.length} 条` : '无'}`)
console.log('\n===== 错误 =====')
console.log(errors.length ? errors.join('\n') : '无错误 ✓')
process.exit(errors.length ? 1 : 0)
