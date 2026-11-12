import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

/*
 * 模拟 Capacitor APK 的 assets/public 目录结构与 https://localhost 协议，
 * 验证前端能否在 APK 环境下正常启动。
 */

const PUB = path.resolve('../static/dist');
const MIME = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.png': 'image/png', '.ico': 'image/x-icon',
  '.svg': 'image/svg+xml', '.woff2': 'font/woff2'
};

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/index.html';
  const file = path.join(PUB, p);
  if (!file.startsWith(PUB) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404); res.end('not found'); return;
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});

await new Promise(r => server.listen(8992, r));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const logs = [];
page.on('console', m => { if (m.type() === 'error') logs.push('[console] ' + m.text()); });
page.on('pageerror', e => logs.push('[pageerror] ' + e.message));
page.on('requestfailed', r => logs.push('[reqfail] ' + r.url().slice(-50) + ' :: ' + r.failure()?.errorText));
page.on('response', r => { if (r.status() >= 400) logs.push(`[http${r.status()}] ` + r.url().slice(-50)); });

await page.goto('http://127.0.0.1:8992/', { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);

const state = await page.evaluate(() => ({
  bootExists: !!document.getElementById('app-boot'),
  appMounted: (document.getElementById('app')?.children.length ?? 0) > 1,
  text: document.body.innerText.slice(0, 80).replace(/\n/g, ' | ')
}));

console.log('=== APK 环境模拟 ===');
console.log(JSON.stringify(state, null, 2));
console.log('\n=== 错误日志 ===');
console.log(logs.length ? logs.join('\n') : '(无)');

await browser.close();
server.close();
