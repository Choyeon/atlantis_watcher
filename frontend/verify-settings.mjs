/**
 * 设置页可视化回归：桌面 + 移动视口。
 * 需后端已运行： python main.py --no-elevation
 * 用法： node verify-settings.mjs
 *       AW_BASE_URL=http://127.0.0.1:26542 node verify-settings.mjs
 */
import { chromium } from 'playwright'

const BASE = process.env.AW_BASE_URL || 'http://127.0.0.1:26541'
const errors = []
const browser = await chromium.launch()

for (const vp of [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 }
]) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } })
  const page = await ctx.newPage()
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[${vp.name}:console] ${msg.text()}`)
  })
  page.on('pageerror', err => errors.push(`[${vp.name}:pageerror] ${err.message}`))

  try {
    // 服务端存在长连接/轮询，networkidle 可能永不触发；改为等待关键内容渲染。
    await page.goto(`${BASE}/#/settings`, { waitUntil: 'domcontentloaded', timeout: 20000 })
    await page.locator('.ios-switch').first().waitFor({ state: 'attached', timeout: 15000 })
    await page.waitForTimeout(1200)

    const body = await page.locator('body').innerText()
    for (const needle of ['访问地址', '开机自动启动', '服务端口', '保存设置', '日志级别']) {
      if (!body.includes(needle)) errors.push(`[${vp.name}] 缺少文本: ${needle}`)
    }
    const switches = await page.locator('.ios-switch').count()
    if (switches < 5) errors.push(`[${vp.name}] 开关数量异常: ${switches}`)

    console.log(`${vp.name}: switches=${switches} bodyChars=${body.length}`)
  } catch (err) {
    errors.push(`[${vp.name}] 页面加载失败: ${err.message}`)
    console.log(`${vp.name}: FAILED ${err.message}`)
  } finally {
    await ctx.close()
  }
}

await browser.close()
if (errors.length) {
  console.error('SETTINGS_UI_FAILED', errors)
  process.exit(1)
}
console.log('SETTINGS_UI_OK')
