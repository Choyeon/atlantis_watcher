/**
 * 交互回归：验证写操作与危险操作确认流程
 */
import { chromium } from 'playwright'

const BASE = process.env.AW_BASE_URL || 'http://127.0.0.1:26541'
const errors = []

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await ctx.newPage()
page.on('pageerror', e => errors.push(`[pageerror] ${e.message}`))
page.on('console', m => {
  if (m.type() === 'error') errors.push(`[console] ${m.text()}`)
})

await page.goto(`${BASE}/#/files`, { waitUntil: 'networkidle' })
await page.waitForTimeout(2500)

// 1) 新建文件夹
const testName = 'ui_test_folder'
await page.getByRole('button', { name: /新建文件夹/ }).click()
await page.waitForTimeout(500)
await page.locator('#create-name').fill(testName)
await page.getByRole('button', { name: '创建' }).click()
await page.waitForTimeout(1800)

const created = await page.locator('.file-row__name', { hasText: testName }).count()
console.log(`[新建文件夹] 出现在列表中 = ${created > 0} (count=${created})`)

const toastText = await page.locator('.toast__desc').first().textContent().catch(() => '-')
console.log(`[新建文件夹] 提示 = ${toastText}`)

// 2) 右键菜单 → 重命名
const row = page.locator('.file-row', { hasText: testName }).first()
await row.click({ button: 'right' })
await page.waitForTimeout(500)
const menuItems = await page.locator('.ctx-menu__item').allTextContents()
console.log(`[右键菜单] 项 = ${menuItems.map(s => s.trim()).join(' | ')}`)

await page.getByRole('button', { name: '重命名', exact: true }).click()
await page.waitForTimeout(500)
await page.locator('#rename-input').fill(testName + '_renamed')
await page.getByRole('button', { name: '保存' }).click()
await page.waitForTimeout(1800)

const renamed = await page.locator('.file-row__name', { hasText: testName + '_renamed' }).count()
console.log(`[重命名] 生效 = ${renamed > 0}`)

// 3) 复制 → 粘贴
await page.locator('.file-row', { hasText: testName + '_renamed' }).first().click({ button: 'right' })
await page.waitForTimeout(400)
await page.getByRole('button', { name: '复制', exact: true }).click()
await page.waitForTimeout(600)
const pasteBtn = page.getByRole('button', { name: /粘贴/ })
const pasteDisabled = await pasteBtn.isDisabled()
console.log(`[粘贴按钮] 复制后可点击 = ${!pasteDisabled}`)
await pasteBtn.click()
await page.waitForTimeout(1800)
const copies = await page.locator('.file-row__name', { hasText: testName + '_renamed' }).count()
console.log(`[粘贴] 副本数量 = ${copies} (应为 2)`)

// 4) 搜索过滤（监控页）
await page.evaluate(() => {
  window.location.hash = '#/monitor'
})
await page.waitForTimeout(2200)
const before = await page.locator('table tbody tr').count()
await page.locator('input[type="search"]').fill('System')
await page.waitForTimeout(700)
const after = await page.locator('table tbody tr').count()
console.log(`[进程搜索] 过滤前 ${before} 行 → 过滤后 ${after} 行`)

// 5) 危险操作确认弹窗（快捷操作页）
await page.evaluate(() => {
  window.location.hash = '#/power'
})
await page.waitForTimeout(1200)
await page.getByRole('button', { name: /立即关机/ }).click()
await page.waitForTimeout(600)
const modalTitle = await page.locator('.modal__title').textContent().catch(() => '-')
const hasCancel = await page.getByRole('button', { name: '取消', exact: true }).count()
console.log(`[危险操作] 弹窗标题 = "${modalTitle?.trim()}" | 有取消按钮 = ${hasCancel > 0}`)
await page.getByRole('button', { name: '取消', exact: true }).click()
await page.waitForTimeout(500)

// 6) 主题切换持久化
await page.evaluate(() => {
  document.querySelector('.rail__theme')?.click()
})
await page.waitForTimeout(600)
const theme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
const stored = await page.evaluate(() => localStorage.getItem('atlantis-theme'))
console.log(`[主题切换] 当前 = ${theme} | localStorage = ${stored}`)

// 7) 清理测试目录
await page.evaluate(() => {
  window.location.hash = '#/files'
})
await page.waitForTimeout(1800)
for (const suffix of ['', '_renamed']) {
  const name = testName + suffix
  const r = page.locator('.file-row', { hasText: name }).first()
  if (await r.count()) {
    await r.click({ button: 'right' })
    await page.waitForTimeout(400)
    await page.getByRole('button', { name: '删除', exact: true }).click()
    await page.waitForTimeout(1600)
  }
}
const remaining = await page.locator('.file-row__name', { hasText: testName }).count()
console.log(`[清理] 残留测试目录 = ${remaining} (应为 0)`)

await browser.close()

console.log('\n===== 错误 =====')
console.log(errors.length ? errors.join('\n') : '无错误 ✓')
process.exit(errors.length ? 1 : 0)
