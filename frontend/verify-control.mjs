/**
 * 远程操控 / 进程管理 / 设置开关 可视化回归（桌面 + 移动视口）。
 * 需后端已运行： python main.py --no-elevation
 * 用法： node verify-control.mjs
 *       AW_BASE_URL=http://127.0.0.1:26542 node verify-control.mjs
 */
import { chromium } from 'playwright'

const BASE = process.env.AW_BASE_URL || 'http://127.0.0.1:26541'
const errors = []
const browser = await chromium.launch()

const CHECKS = [
  { name: 'screen', hash: '#/screen', needles: ['开始共享', '横屏全屏', '操控中', '键盘', '截图'] },
  { name: 'processes', hash: '#/processes', needles: ['进程管理', '自动刷新', '刷新'] },
  { name: 'settings', hash: '#/settings', needles: ['访问地址', '允许远程操控', '保存设置'] }
]

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

  for (const check of CHECKS) {
    try {
      await page.goto(`${BASE}/${check.hash}`, { waitUntil: 'domcontentloaded', timeout: 20000 })
      // 冷加载时 ESM 模块 mount 可能晚于 domcontentloaded 数秒，等特征文本出现再断言
      await page.waitForFunction(
        needle => document.body.innerText.includes(needle),
        check.needles[0],
        { timeout: 20000 }
      )
      await page.waitForTimeout(350)
      const body = await page.locator('body').innerText()
      for (const needle of check.needles) {
        if (!body.includes(needle)) errors.push(`[${vp.name}:${check.name}] 缺少文本: ${needle}`)
      }
      if (check.name === 'settings') {
        const switches = await page.locator('.ios-switch').count()
        if (switches < 6) errors.push(`[${vp.name}:settings] 开关数量异常: ${switches}`)
      }
      console.log(`${vp.name}/${check.name}: bodyChars=${body.length}`)
    } catch (err) {
      errors.push(`[${vp.name}:${check.name}] 页面加载失败: ${err.message}`)
    }
  }

  await ctx.close()
}

await browser.close()
if (errors.length) {
  console.error('CONTROL_UI_FAILED', errors)
  process.exit(1)
}
console.log('CONTROL_UI_OK')
