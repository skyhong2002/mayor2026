// Photograph every state in states.mjs at both sizes.
//   node capture.mjs site FULL_BASE EMPTY_BASE OUT_DIR [id-filter]
//   node capture.mjs references OUT_DIR [id-filter]
// FULL_BASE / EMPTY_BASE are serve.py servers for the full and empty builds.
// Playwright resolves from ./node_modules (a link to a local install).
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';
import { SIZES, STATES, REFERENCES, NOW } from './states.mjs';

const [mode, ...rest] = process.argv.slice(2);
const browser = await chromium.launch();
const sizes = Object.entries(SIZES).filter(([name]) => !process.env.ONLY_SIZE || name === process.env.ONLY_SIZE);

// Deterministic Math.random so "random neutral" default orderings repeat.
const SEED = `(() => { let s = 20261128; Math.random = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; })();`;

async function settle(page, maxHeight) {
  const height = Math.min(await page.evaluate(() => document.documentElement.scrollHeight), maxHeight * 2);
  for (let y = 0; y < height; y += 600) {
    await page.evaluate((top) => window.scrollTo(0, top), y);
    await page.waitForTimeout(80);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
  await page.evaluate(() => Promise.all([...document.images].filter((img) => !img.complete).map((img) => new Promise((done) => { img.onload = img.onerror = done; setTimeout(done, 4000); }))));
  await page.waitForTimeout(400);
}

async function shoot(page, file, size, { anchor, viewportOnly } = {}) {
  let top = 0;
  if (anchor) {
    top = await page.evaluate((selector) => {
      const node = document.querySelector(selector);
      return node ? Math.round(Math.max(0, node.getBoundingClientRect().top + window.scrollY - 80)) : 0;
    }, anchor);
  }
  if (viewportOnly) {
    await page.evaluate((y) => window.scrollTo(0, y), top);
    await page.waitForTimeout(250);
    return page.screenshot({ path: file });
  }
  const full = await page.evaluate(() => document.documentElement.scrollHeight);
  const height = Math.max(size.height, Math.min(full - top, size.maxHeight));
  // Grow the viewport to the shot height (sticky bars and the deck behave as on a tall screen).
  await page.setViewportSize({ width: size.width, height: Math.round(height) });
  await page.waitForTimeout(500);
  await page.evaluate((y) => window.scrollTo(0, y), top);
  await page.waitForTimeout(300);
  return page.screenshot({ path: file });
}

function context(size, extra = {}) {
  return browser.newContext({
    viewport: { width: size.width, height: size.height }, deviceScaleFactor: size.deviceScaleFactor,
    isMobile: !!size.isMobile, hasTouch: !!size.hasTouch, timezoneId: 'Asia/Taipei', reducedMotion: 'reduce', ...extra,
  });
}

if (mode === 'site') {
  const [full, empty, out, filter] = rest;
  mkdirSync(out, { recursive: true });
  for (const [sizeName, size] of sizes) {
    for (const state of STATES.filter((s) => !filter || s.id.includes(filter))) {
      const ctx = await context(size, { colorScheme: state.theme === 'dark' ? 'dark' : 'light', locale: 'zh-TW' });
      const page = await ctx.newPage();
      await page.addInitScript(SEED);
      await page.clock.setFixedTime(new Date(NOW));
      if (state.route) {
        const [glob, how] = state.route;
        await page.route(glob, (route) => how === 'hang' ? undefined
          : route.fulfill({ status: 500, contentType: 'text/plain', body: 'Server error' }));
      }
      const base = state.site === 'empty' ? empty : full;
      const hang = state.route && state.route[1] === 'hang';
      await page.goto(base + state.path, { waitUntil: hang ? 'domcontentloaded' : 'networkidle', timeout: 45000 }).catch(() => {});
      await page.waitForTimeout(hang ? 1500 : 500);
      for (const selector of state.click || []) {
        await page.locator(selector).first().click({ timeout: 5000 }).catch((e) => console.warn(state.id, 'click failed', selector, e.message.split('\n')[0]));
        await page.waitForTimeout(400);
      }
      if (!hang) await settle(page, size.maxHeight);
      const file = `${out}/${state.id}_${sizeName}.png`;
      await shoot(page, file, size, state);
      console.log(file);
      await ctx.close();
    }
  }
} else if (mode === 'references') {
  const [out, filter] = rest;
  mkdirSync(out, { recursive: true });
  for (const [sizeName, size] of sizes) {
    for (const ref of REFERENCES.filter((r) => !filter || r.id.includes(filter))) {
      const ctx = await context(size, {
        locale: ref.locale || 'en-US',
        userAgent: size.isMobile
          ? 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
          : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
      });
      const page = await ctx.newPage();
      await page.goto(ref.url, { waitUntil: 'domcontentloaded', timeout: 45000 }).catch(() => {});
      await page.waitForTimeout(8000);
      for (const name of ['Reject All', 'Reject all', 'Accept All', 'Accept all', 'Accept', 'Got it', '同意', '我知道了']) {
        const button = page.getByRole('button', { name, exact: true });
        if (await button.count().catch(() => 0)) { await button.first().click({ timeout: 2000 }).catch(() => {}); break; }
      }
      await settle(page, size.maxHeight);
      const file = `${out}/${ref.id}_${sizeName}.png`;
      await shoot(page, file, size, {});
      console.log(file);
      await ctx.close();
    }
  }
}
await browser.close();
