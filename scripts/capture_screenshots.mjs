// Captures the README screenshots from the LIVE site, once in the light ("paper")
// theme and once in the dark ("ink") theme, as <name>-light.png and <name>-dark.png.
// The README swaps between them with <picture> and prefers-color-scheme.
//
// How to run (Playwright and Sharp are installed OUTSIDE the repo so that
// package.json and package-lock.json, which the Pages build uses, stay untouched):
//
//   mkdir -p /tmp/daily-tape-shots && cd /tmp/daily-tape-shots
//   npm init -y && npm i playwright sharp && npx playwright install chromium
//   cd /path/to/market-summary
//   NODE_PATH=/tmp/daily-tape-shots/node_modules node scripts/capture_screenshots.mjs
//
// Optional: SITE_URL=https://... to point at another deployment, and
// ONLY=archive,asset-page to capture a subset, and THEMES=light or THEMES=dark to
// capture one theme. Output goes to assets/screenshots/.
// Every image is resized to at most 1800px wide and palette-compressed.

import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");
const sharp = require("sharp");

const SITE = (process.env.SITE_URL ?? "https://coolxng.github.io/market-summary/").replace(/\/?$/, "/");
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "assets", "screenshots");
const ONLY = process.env.ONLY ? new Set(process.env.ONLY.split(",")) : null;
const MAX_WIDTH = 1800;

// README suffix -> site theme name.
const THEMES = { light: "paper", dark: "ink" };
const THEME_FILTER = process.env.THEMES ? new Set(process.env.THEMES.split(",")) : null;

// The site reads localStorage "daily-tape-theme" in an inline head script and
// sets <html data-theme>. Force the theme before any page script runs.
const forceTheme = (theme) => `
  try { localStorage.setItem("daily-tape-theme", "${theme}"); } catch (e) {}
  document.documentElement.dataset.theme = "${theme}";
`;

// Set per theme by the main loop below.
let variant = "light";
const siteTheme = () => THEMES[variant];

// Hide scrollbars, and stop sticky bars from overlapping element screenshots.
const CAPTURE_CSS = `
  ::-webkit-scrollbar { display: none !important; }
  html { scrollbar-width: none !important; }
  .site-header, .report-nav { position: static !important; }
  *, *::before, *::after { caret-color: transparent !important; }
`;

const desktop = { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 };
const mobile = { ...devices["iPhone 14"], viewport: { width: 390, height: 844 }, deviceScaleFactor: 3 };

async function newPage(browser, profile) {
  const colorScheme = variant === "dark" ? "dark" : "light";
  const context = await browser.newContext({ ...profile, colorScheme, reducedMotion: "reduce", serviceWorkers: "block" });
  await context.addInitScript(forceTheme(siteTheme()));
  return { context, page: await context.newPage() };
}

async function open(page, route, readySelector) {
  await page.goto(new URL(route, SITE).href, { waitUntil: "networkidle" });
  await page.addStyleTag({ content: CAPTURE_CSS });
  await page.evaluate(() => document.fonts.ready);
  if (readySelector) await page.waitForSelector(readySelector, { state: "visible", timeout: 30000 });
  const theme = await page.evaluate(() => document.documentElement.dataset.theme);
  if (theme !== siteTheme()) throw new Error(`${route} rendered with theme "${theme}", expected "${siteTheme()}"`);
}

// Scroll through the page so lazy images load, then wait for them.
async function settle(page) {
  await page.evaluate(async () => {
    document.querySelectorAll('img[loading="lazy"]').forEach((img) => { img.loading = "eager"; });
    for (let y = 0; y < document.body.scrollHeight; y += 600) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 60));
    }
    window.scrollTo(0, 0);
    const pending = [...document.images].filter((img) => !img.complete);
    const loaded = Promise.all(pending.map((img) => new Promise((resolve) => { img.onload = img.onerror = resolve; })));
    await Promise.race([loaded, new Promise((resolve) => setTimeout(resolve, 8000))]);
  });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1000);
}

// Page-coordinate box from the top of `from` to the bottom of `to`, full content width.
async function unionBox(page, fromSelector, toSelector, { pad = 32, bottomPad = pad, maxHeight } = {}) {
  return page.evaluate(({ fromSelector, toSelector, pad, bottomPad, maxHeight }) => {
    const a = document.querySelector(fromSelector).getBoundingClientRect();
    const b = document.querySelector(toSelector).getBoundingClientRect();
    const left = Math.max(0, Math.min(a.left, b.left) - pad);
    const right = Math.min(document.documentElement.clientWidth, Math.max(a.right, b.right) + pad);
    const top = Math.max(0, a.top + window.scrollY - pad);
    let height = b.bottom + window.scrollY + bottomPad - top;
    if (maxHeight) height = Math.min(height, maxHeight);
    return { x: left, y: top, width: right - left, height };
  }, { fromSelector, toSelector, pad, bottomPad, maxHeight });
}

async function save(buffer, name) {
  name = name.replace(/\.png$/, `-${variant}.png`);
  const file = path.join(OUT, name);
  await sharp(buffer)
    .resize({ width: MAX_WIDTH, withoutEnlargement: true })
    .png({ palette: true, quality: 90, effort: 10, compressionLevel: 9 })
    .toFile(file);
  console.log(`saved ${name}`);
}

const shots = {
  // Desktop hero: the first screen of the latest Close Tape.
  async "close-tape"(browser) {
    const { context, page } = await newPage(browser, desktop);
    await open(page, "", "#regime-monitor");
    await settle(page);
    await save(await page.screenshot({ clip: { x: 0, y: 0, width: 1440, height: 900 } }), "close-tape.png");
    await context.close();
  },

  async "morning-tape"(browser) {
    const { context, page } = await newPage(browser, desktop);
    await open(page, "morning/", "#overnight");
    await settle(page);
    const clip = await unionBox(page, "main [class*=\"issueLine\"]", "#overnight", { pad: 32, bottomPad: 16 });
    await save(await page.screenshot({ fullPage: true, clip }), "morning-tape.png");
    await context.close();
  },

  async "asset-page"(browser) {
    const { context, page } = await newPage(browser, desktop);
    await open(page, "assets/spx/", ".price-chart__canvas svg");
    await settle(page);
    const chart = page.locator(".price-chart__canvas");
    await chart.scrollIntoViewIfNeeded();
    const box = await chart.boundingBox();
    await page.mouse.move(box.x + box.width * 0.52, box.y + box.height * 0.5);
    await page.waitForSelector(".price-chart__tooltip", { state: "visible" });
    await page.waitForTimeout(400);
    const clip = await unionBox(page, 'nav[aria-label="Breadcrumb"]', 'section[aria-label="S&P 500 price chart"]', { pad: 32, bottomPad: 12 });
    await save(await page.screenshot({ fullPage: true, clip }), "asset-page.png");
    await context.close();
  },

  async archive(browser) {
    const { context, page } = await newPage(browser, desktop);
    await open(page, "reports/", 'section[aria-labelledby="sessions-title"] [role="search"]');
    await settle(page);
    const clip = await unionBox(page, 'section[aria-labelledby="sessions-title"] [class*="sectionHeading"]', 'section[aria-labelledby="sessions-title"] [class*="footnote"]', { pad: 40, maxHeight: 1100 });
    await save(await page.screenshot({ fullPage: true, clip }), "archive.png");
    await context.close();
  },

  async "mobile-close-tape"(browser) {
    const { context, page } = await newPage(browser, mobile);
    await open(page, "", "#scorecard");
    await settle(page);
    // Hero through the regime monitor. Extending to the scorecard makes the
    // image several phone screens tall, because the takeaway cards sit between them.
    const bottom = await page.evaluate(() => document.querySelector("#regime-monitor").getBoundingClientRect().bottom + window.scrollY);
    const clip = { x: 0, y: 0, width: 390, height: Math.round(bottom + 32) };
    await save(await page.screenshot({ fullPage: true, clip }), "mobile-close-tape.png");
    await context.close();
  },

  async "leadership-engine"(browser) {
    const { context, page } = await newPage(browser, desktop);
    await open(page, "", "#mega-cap .mega-card svg");
    await settle(page);
    await save(await page.screenshot({ fullPage: true, clip: await unionBox(page, "#mega-cap", "#mega-cap", { pad: 40 }) }), "leadership-engine.png");
    await context.close();
  },

  async "data-health"(browser) {
    const { context, page } = await newPage(browser, desktop);
    await open(page, "", "#data-health");
    await settle(page);
    await save(await page.screenshot({ fullPage: true, clip: await unionBox(page, "#data-health", "#data-health", { pad: 40 }) }), "data-health.png");
    await context.close();
  },
};

const browser = await chromium.launch();
try {
  for (variant of Object.keys(THEMES)) {
    if (THEME_FILTER && !THEME_FILTER.has(variant)) continue;
    for (const [name, capture] of Object.entries(shots)) {
      if (ONLY && !ONLY.has(name)) continue;
      await capture(browser);
    }
  }
} finally {
  await browser.close();
}
