// Screenshot one page of a locally served site with Playwright (any OS).
//   node tools/shot.mjs <path e.g. /spectrum/> <out.png> [width=1440] [height=2000] [theme=dark|light]
// Requires a server on SHOT_BASE (default http://127.0.0.1:8743), e.g.
//   python3 -m http.server 8743 --directory site
// and Playwright importable (NODE_PATH pointing at a node_modules with it).
// Narrow widths are true mobile layouts (isMobile + touch); no iframe crop.
import { chromium } from 'playwright';

const [path = '/', out = '/tmp/shot.png', w = '1440', h = '2000', theme = 'dark'] = process.argv.slice(2);
const base = process.env.SHOT_BASE || 'http://127.0.0.1:8743';
const width = +w, height = +h, phone = width < 700;
const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width, height: phone ? 844 : Math.min(height, 1440) },
  deviceScaleFactor: phone ? 2 : 1, isMobile: phone, hasTouch: phone,
  colorScheme: theme === 'light' ? 'light' : 'dark', timezoneId: 'Asia/Taipei', locale: 'zh-TW',
});
const sep = path.includes('?') ? '&' : '?';
await page.goto(`${base}${path}${sep}theme=${theme}`, { waitUntil: 'networkidle', timeout: 45000 }).catch(() => {});
await page.waitForTimeout(400);
const full = await page.evaluate(() => document.documentElement.scrollHeight);
await page.setViewportSize({ width, height: Math.max(phone ? 844 : 600, Math.min(full, height)) });
await page.waitForTimeout(300);
await page.screenshot({ path: out });
await browser.close();
console.log(out);
