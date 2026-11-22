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

    const railImage = page.locator('.rail__mark .brand-mark')
    if (await railImage.count() < 1) errors.push(`[${vp.name}] 侧栏品牌图标未渲染`)
    await railImage.first().evaluate((node) => {
      if (node.complete && node.naturalWidth > 0) return
      return new Promise((resolve) => node.addEventListener('load', resolve, { once: true }))
    })
    const naturalWidth = await railImage.first().evaluate((node) => node.naturalWidth || 0)
    if (naturalWidth < 1) errors.push(`[${vp.name}] 侧栏品牌图标资源未加载`)

    console.log(`${vp.name}: marks=${marks} imageWidth=${naturalWidth}`)
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
