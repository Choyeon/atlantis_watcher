import { chromium } from 'playwright';
import fs from 'fs';

const OUT = process.cwd() + '/shots';
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const errors = [];

const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
  deviceScaleFactor: 2
});
const page = await ctx.newPage();
page.on('console', m => { if (m.type() === 'error') errors.push('[console] ' + m.text()); });
page.on('pageerror', e => errors.push('[pageerror] ' + e.message));

await page.goto('http://127.0.0.1:26541/', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);

// 切到终端页（背景有丰富内容，最能体现折射）
await page.evaluate(() => { window.location.hash = '#/terminal'; });
await page.waitForTimeout(2200);

const probe = await page.evaluate(() => {
  const pill = document.querySelector('.tabbar__pill');
  const out = { pillFound: !!pill };
  if (!pill) return out;

  // glassy-liquid 注入的图层
  const fx = pill.querySelector('gl-fx');
  out.fxInjected = !!fx;
  if (fx) {
    out.layers = [...fx.children].map(c => c.tagName.toLowerCase());
    const b = fx.querySelector('gl-l.b');
    if (b) {
      const cs = getComputedStyle(b);
      out.backdropLayer = {
        backdropFilter: cs.backdropFilter || cs.webkitBackdropFilter,
        hasSvgFilter: /url\(/.test(cs.backdropFilter || cs.webkitBackdropFilter || '')
      };
    }
    const svg = fx.querySelector('svg');
    if (svg) {
      const filters = [...svg.querySelectorAll('filter')].map(f => ({
        id: f.id,
        hasDisplacement: !!f.querySelector('feDisplacementMap')
      }));
      out.filters = filters;
    }
  }

  // 宿主自身不应有 background（否则成为 backdrop root 阻断折射）
  const host = getComputedStyle(pill);
  out.hostBackground = host.backgroundColor;
  out.hostBackdrop = host.backdropFilter;

  out.items = document.querySelectorAll('.tabbar__item').length;
  out.orb = document.querySelectorAll('.tabbar__orb').length;
  out.sheen = document.querySelectorAll('.lg-sheen').length;
  out.specular = document.querySelectorAll('.lg-specular').length;

  const ind = document.querySelector('.lg-liquid-indicator');
  if (ind) {
    const cs = getComputedStyle(ind);
    out.indicator = { transform: cs.transform, width: cs.width };
  }
  return out;
});

console.log(JSON.stringify(probe, null, 2));
await page.screenshot({ path: OUT + '/gl-01-terminal.png' });

// 概览页截图
await page.evaluate(() => { window.location.hash = '#/overview'; });
await page.waitForTimeout(1800);
await page.screenshot({ path: OUT + '/gl-02-overview.png' });

// 浅色主题
await page.evaluate(() => {
  document.documentElement.setAttribute('data-theme', 'light');
  window.location.hash = '#/files';
});
await page.waitForTimeout(1800);
await page.screenshot({ path: OUT + '/gl-03-light.png' });

console.log('\n=== 控制台错误 ===');
console.log(errors.length ? errors.join('\n') : '(无)');

await browser.close();
