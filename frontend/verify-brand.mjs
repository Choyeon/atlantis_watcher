/**
 * 品牌图标全局适配可视化回归
 *
 * 需后端已运行；端口由 AW_BASE_URL 指定（隔离端口脚本会自动注入）。
 * 用法： node verify-brand.mjs
 */
import { chromium } from 'playwright'

const BASE = process.env.AW_BASE_URL || 'http://127.0.0.1:26541'
const errors = []
const browser = await chromium.launch()

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 }
]

for (const vp of VIEWPORTS) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } })
  const page = await ctx.newPage()
  try {
    await page.goto(`${BASE}/#/settings`, { waitUntil: 'domcontentloaded', timeout: 20000 })
    await page.locator('.brand-mark').first().waitFor({ state: 'attached', timeout: 15000 })

    const marks = await page.locator('.brand-mark').count()
    if (marks < 1) errors.push(`[${vp.name}] 未渲染品牌标记`)

    const railPaths = await page.locator('.rail__mark .brand-mark path').count()
    if (railPaths !== 8) errors.push(`[${vp.name}] 侧栏 mark 路径数异常: ${railPaths} (期望 8)`)

    const hasAccent = await page.locator('.rail__mark .brand-mark path[stroke="#35D6BD"]').count()
    if (hasAccent < 1) errors.push(`[${vp.name}] 声呐环未使用品牌青松石`)

    console.log(`${vp.name}: marks=${marks} railPaths=${railPaths} accentStroke=${hasAccent}`)
  } catch (err) {
    errors.push(`[${vp.name}] ${err.message.split('\n')[0]}`)
  } finally {
    await ctx.close()
  }
}

// 静态品牌资源必须能通过 HTTP 访问（exe / APK 内同样走这条路径）
const ctx = await browser.newContext()
const page = await ctx.newPage()
for (const file of ['favicon.svg', 'favicon.ico', 'favicon-32.png', 'apple-touch-icon.png']) {
  try {
    const resp = await page.request.get(`${BASE}/${file}`, { timeout: 10000 })
    if (resp.status() !== 200) errors.push(`资源 ${file} 返回 ${resp.status()}`)
    else console.log(`asset ${file}: ${resp.status()} ${(await resp.body()).length}B`)
  } catch (err) {
    errors.push(`资源 ${file} 请求失败: ${err.message.split('\n')[0]}`)
  }
}
await ctx.close()
await browser.close()

if (errors.length) {
  console.error(errors.join('\n'))
  console.error('BRAND_UI_FAILED')
  process.exit(1)
}
console.log('BRAND_UI_OK')
