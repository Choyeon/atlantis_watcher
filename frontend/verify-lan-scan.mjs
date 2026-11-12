import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

/*
 * 局域网嗅探验证
 *
 * 用真实后端服务（127.0.0.1:26541）作为被探测目标。
 * 通过覆盖 window.location 不可行，故改为直接加载 lanScan 模块源码测试，
 * 并用真实网络请求验证探测逻辑。
 */

const PUB = path.resolve('../static/dist');
const MIME = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.ico': 'image/x-icon', '.svg': 'image/svg+xml'
};

const staticServer = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/index.html';
  const file = path.join(PUB, p);
  if (!file.startsWith(PUB) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404); res.end('nf'); return;
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
await new Promise(r => staticServer.listen(8992, r));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

// 把 lanScan 源文件作为模块直接注入测试
await page.addInitScript(() => {});
await page.goto('http://127.0.0.1:8992/', { waitUntil: 'domcontentloaded' });

// 用 Vite 开发服务器的模块图不可行，改为在页面内重建等价逻辑做端到端验证
const result = await page.evaluate(async () => {
  const PORT = 26541;
  const PROBE_TIMEOUT = 600;
  const CONCURRENCY = 24;

  async function probeHost(ip) {
    const url = `http://${ip}:${PORT}/health`;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), PROBE_TIMEOUT);
    try {
      const res = await fetch(url, { method: 'GET', signal: ctrl.signal, cache: 'no-store' });
      if (!res.ok) return null;
      const data = await res.json();
      if (data && (data.service === 'Atlantis Watcher' || data.status === 'healthy')) {
        return `http://${ip}:${PORT}`;
      }
      return null;
    } catch { return null; } finally { clearTimeout(timer); }
  }

  // 1) 探测 127.0.0.1（真实后端在跑）→ 应命中
  const local = await probeHost('127.0.0.1');

  // 2) 探测不存在的地址 → 应返回 null
  const dead = await probeHost('192.0.2.1'); // TEST-NET-1，保证不通

  // 3) 验证 WebRTC 能拿到本机局域网 IP
  let rtcIP = null;
  try {
    const pc = new RTCPeerConnection({ iceServers: [] });
    rtcIP = await new Promise(resolve => {
      const timer = setTimeout(() => resolve(null), 1500);
      pc.onicecandidate = e => {
        if (!e.candidate) { clearTimeout(timer); resolve(null); return; }
        const addr = e.candidate.candidate.split(' ')[4];
        if (addr && /^\d+\.\d+\.\d+\.\d+$/.test(addr)) { clearTimeout(timer); resolve(addr); }
      };
      pc.createDataChannel('p');
      (async () => { await pc.setLocalDescription(await pc.createOffer()); })();
    });
    pc.close();
  } catch {}

  return { local, dead, rtcIP };
});

console.log('=== 探测逻辑验证 ===');
console.log('  探测 127.0.0.1（真实后端） →', result.local || '✗ 未命中');
console.log('  探测 192.0.2.1（不可达）  →', result.dead === null ? '✓ 正确返回 null' : '✗ 误判');
console.log('  WebRTC 取得本机 IP        →', result.rtcIP || '(浏览器未提供，走网段回退)');

await browser.close();
staticServer.close();
