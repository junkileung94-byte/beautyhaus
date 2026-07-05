// Full page-to-page Playwright audit crawl of violahairextensions.co.uk
// (+ a few pages of the current Canadian site violahairextensions.co for gap analysis).
//
// Usage:  node audit/crawl.mjs
// Needs:  playwright installed in NODE_PATH or a sibling node_modules (see NODE_PATH env)
//
// Resume-safe: URLs whose desktop+mobile screenshots already exist are skipped.
// Output: audit/screenshots/{desktop,mobile}/<group>/<handle>.png
//         audit/data/pages/<handle>.md      (extracted copy for static pages)
//         audit/data/page-meta.json         (title/h1/meta/anatomy per URL)
//         audit/data/design-tokens.json     (computed styles from representative pages)
//         audit/data/crawl-log.json         (status per URL)

import { createRequire } from 'node:module';
import { existsSync, writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const BASE = 'https://www.violahairextensions.co.uk';
const CA = 'https://violahairextensions.co';
const ROOT = path.dirname(new URL(import.meta.url).pathname);
const SHOTS = path.join(ROOT, 'screenshots');
const DATA = path.join(ROOT, 'data');
mkdirSync(path.join(DATA, 'pages'), { recursive: true });

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};
const CONCURRENCY = 4;
const NAV_TIMEOUT = 45000;

// ---------- build URL list from sitemaps ----------
async function fetchText(url) {
  const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 (audit crawl)' } });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.text();
}

function extractLocs(xml) {
  return [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1].trim());
}

async function buildUrlList() {
  const idx = await fetchText(`${BASE}/sitemap.xml`);
  const children = extractLocs(idx).filter((u) => !u.includes('agentic'));
  const urls = [];
  for (const child of children) {
    const xml = await fetchText(child);
    for (const loc of extractLocs(xml)) {
      if (loc.includes('/products/')) urls.push({ url: loc, group: 'products' });
      else if (loc.includes('/collections/')) urls.push({ url: loc, group: 'collections' });
      else if (loc.includes('/pages/')) urls.push({ url: loc, group: 'pages' });
      else if (loc.includes('/blogs/')) urls.push({ url: loc, group: 'blogs' });
      else if (new URL(loc).pathname === '/') urls.push({ url: loc, group: 'home' });
    }
  }
  // blogs: keep the listing(s) + first 3 posts only
  const blogPosts = urls.filter((u) => u.group === 'blogs' && /\/blogs\/[^/]+\/./.test(new URL(u.url).pathname));
  const blogListings = urls.filter((u) => u.group === 'blogs' && !/\/blogs\/[^/]+\/./.test(new URL(u.url).pathname));
  const keptBlogs = [...blogListings, ...blogPosts.slice(0, 3)];
  const rest = urls.filter((u) => u.group !== 'blogs');
  if (!rest.some((u) => u.group === 'home')) rest.unshift({ url: `${BASE}/`, group: 'home' });

  // current Canadian site for gap analysis
  const ca = [
    { url: `${CA}/`, group: 'ca' },
    { url: `${CA}/collections/all`, group: 'ca' },
    { url: `${CA}/pages/contact-us`, group: 'ca' },
  ];
  return [...rest, ...keptBlogs, ...ca];
}

function slugFor(u) {
  const p = new URL(u.url).pathname.replace(/\/$/, '');
  if (p === '' || p === '/') return u.group === 'ca' ? 'ca-home' : 'home';
  return p.split('/').filter(Boolean).join('__').replace(/[^a-z0-9_-]/gi, '-').slice(0, 120);
}

// ---------- per-page behavior ----------
async function dismissPopups(page) {
  const selectors = [
    '#shopify-pc__banner__btn-accept', // cookie banner accept
    'button:has-text("Accept")',
    'button[aria-label="Close dialog"]',
    'button[aria-label="Close"]',
    '.klaviyo-close-form',
    '[data-testid="POPUP"] button[aria-label*="lose"]',
    '.needsclick[aria-label="Close dialog"]',
  ];
  for (const sel of selectors) {
    try {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 400 })) await el.click({ timeout: 1500 });
    } catch { /* not present */ }
  }
  await page.keyboard.press('Escape').catch(() => {});
}

async function lazyScroll(page) {
  await page.evaluate(async () => {
    const step = window.innerHeight;
    const max = Math.min(document.body.scrollHeight, 30000);
    for (let y = 0; y < max; y += step) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 120));
    }
    window.scrollTo(0, 0);
    await new Promise((r) => setTimeout(r, 400));
  });
}

async function extractMeta(page, group) {
  return page.evaluate((group) => {
    const txt = (sel) => document.querySelector(sel)?.textContent?.trim() || null;
    const meta = {
      title: document.title,
      h1: txt('h1'),
      metaDescription: document.querySelector('meta[name="description"]')?.content || null,
      breadcrumbs: [...document.querySelectorAll('nav[aria-label*="readcrumb" i] a, .breadcrumb a, .breadcrumbs a')].map((a) => a.textContent.trim()),
    };
    if (group === 'products') {
      meta.product = {
        price: txt('.price, [class*="price"]'),
        optionNames: [...document.querySelectorAll('form[action*="/cart/add"] label, variant-selects legend, .product-form__input label, .product-form__input legend')]
          .map((l) => l.textContent.trim()).filter((v, i, a) => v && a.indexOf(v) === i).slice(0, 12),
        hasReviews: !!document.querySelector('[class*="review" i], #judgeme_product_reviews, .jdgm-widget'),
        descriptionLength: (txt('.product__description, [class*="product-description"], .product-single__description') || '').length,
        tabHeadings: [...document.querySelectorAll('.accordion summary, [class*="tab"][role="tab"], details summary')].map((e) => e.textContent.trim()).slice(0, 10),
      };
    }
    if (group === 'pages' || group === 'blogs' || group === 'home') {
      const main = document.querySelector('main') || document.body;
      meta.copy = main.innerText.replace(/\n{3,}/g, '\n\n').slice(0, 20000);
    }
    if (group === 'collections') {
      meta.collection = {
        description: txt('.collection__description, .collection-description, .rte'),
        productCardCount: document.querySelectorAll('.grid__item .card, .product-card, [class*="product-item"], li.grid__item').length,
      };
    }
    return meta;
  }, group);
}

async function extractDesignTokens(page) {
  return page.evaluate(() => {
    const pick = (el, props) => {
      if (!el) return null;
      const cs = getComputedStyle(el);
      return Object.fromEntries(props.map((p) => [p, cs.getPropertyValue(p)]));
    };
    const q = (sel) => document.querySelector(sel);
    const btn = q('button[type="submit"], .button, .btn, a.button') || q('form[action*="cart"] button');
    return {
      url: location.href,
      body: pick(document.body, ['font-family', 'font-size', 'line-height', 'color', 'background-color']),
      h1: pick(q('h1'), ['font-family', 'font-size', 'font-weight', 'letter-spacing', 'color', 'text-transform']),
      h2: pick(q('h2'), ['font-family', 'font-size', 'font-weight', 'color', 'text-transform']),
      h3: pick(q('h3'), ['font-family', 'font-size', 'font-weight', 'color']),
      link: pick(q('main a, a'), ['color', 'text-decoration-line']),
      button: pick(btn, ['font-family', 'font-size', 'font-weight', 'color', 'background-color', 'border-radius', 'padding', 'border', 'text-transform', 'letter-spacing']),
      header: pick(q('header, .header'), ['background-color', 'color', 'position']),
      announcement: pick(q('.announcement-bar, [class*="announcement"]'), ['background-color', 'color', 'font-size']),
      footer: pick(q('footer, .footer'), ['background-color', 'color']),
      badge: pick(q('.badge, [class*="badge"]'), ['background-color', 'color', 'border-radius', 'font-size']),
      card: pick(q('.card, .product-card, [class*="card"]'), ['background-color', 'border-radius', 'box-shadow', 'border']),
      cssVars: (() => {
        const out = {};
        const cs = getComputedStyle(document.documentElement);
        for (const sheet of document.styleSheets) {
          let rules; try { rules = sheet.cssRules; } catch { continue; }
          for (const rule of rules) {
            if (rule.selectorText === ':root' && rule.style) {
              for (const name of rule.style) if (name.startsWith('--')) out[name] = cs.getPropertyValue(name).trim();
            }
          }
        }
        return out;
      })(),
      fontsLoaded: [...document.fonts].map((f) => `${f.family} ${f.weight} ${f.style}`).filter((v, i, a) => a.indexOf(v) === i),
    };
  });
}

// ---------- main ----------
const urls = await buildUrlList();
const counts = urls.reduce((a, u) => ((a[u.group] = (a[u.group] || 0) + 1), a), {});
console.log(`URL list: ${urls.length} total —`, JSON.stringify(counts));

for (const vp of Object.keys(VIEWPORTS)) for (const g of [...new Set(urls.map((u) => u.group))]) mkdirSync(path.join(SHOTS, vp, g), { recursive: true });

const log = [];
const pageMeta = {};
const designTokens = {};
// representative pages for token extraction (desktop only)
const tokenTargets = new Set([
  `${BASE}/`,
  `${BASE}/collections/nano-tip-hair-extensions`,
  `${BASE}/pages/faqs`,
]);
let tokenProductDone = false;

const browser = await chromium.launch();

async function capture(item, vpName) {
  const slug = slugFor(item);
  const file = path.join(SHOTS, vpName, item.group, `${slug}.png`);
  if (existsSync(file)) return { skipped: true };
  const context = await browser.newContext({
    viewport: { width: VIEWPORTS[vpName].width, height: VIEWPORTS[vpName].height },
    isMobile: !!VIEWPORTS[vpName].isMobile,
    hasTouch: !!VIEWPORTS[vpName].hasTouch,
    deviceScaleFactor: VIEWPORTS[vpName].deviceScaleFactor || 1,
    userAgent: vpName === 'mobile'
      ? 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
      : undefined,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(NAV_TIMEOUT);
  try {
    await page.goto(item.url, { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT });
    await page.waitForLoadState('load', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1200);
    await dismissPopups(page);
    await lazyScroll(page);
    await dismissPopups(page); // some popups fire on scroll
    await page.screenshot({ path: file, fullPage: true, timeout: 30000 });

    if (vpName === 'desktop') {
      const key = `${item.group}/${slug}`;
      pageMeta[key] = { url: item.url, ...(await extractMeta(page, item.group)) };
      if (pageMeta[key].copy && (item.group === 'pages' || item.group === 'blogs')) {
        writeFileSync(path.join(DATA, 'pages', `${slug}.md`), `# ${pageMeta[key].h1 || pageMeta[key].title}\n\nURL: ${item.url}\n\n${pageMeta[key].copy}\n`);
      }
      if (tokenTargets.has(item.url) || (item.group === 'products' && !tokenProductDone)) {
        if (item.group === 'products') tokenProductDone = true;
        designTokens[item.url] = await extractDesignTokens(page);
      }
    }
    return { ok: true };
  } catch (e) {
    return { error: e.message.split('\n')[0] };
  } finally {
    await context.close();
  }
}

const queue = [];
for (const item of urls) for (const vpName of Object.keys(VIEWPORTS)) queue.push({ item, vpName });

let done = 0, errors = 0, skipped = 0;
async function worker() {
  while (queue.length) {
    const job = queue.shift();
    let res = await capture(job.item, job.vpName);
    if (res.error) res = await capture(job.item, job.vpName); // one retry
    done++;
    if (res.error) { errors++; log.push({ url: job.item.url, vp: job.vpName, error: res.error }); }
    else if (res.skipped) skipped++;
    else log.push({ url: job.item.url, vp: job.vpName, ok: true });
    if (done % 25 === 0) {
      console.log(`${done}/${urls.length * 2} done (${errors} errors, ${skipped} skipped)`);
      writeFileSync(path.join(DATA, 'crawl-log.json'), JSON.stringify({ done, total: urls.length * 2, errors, skipped, log }, null, 1));
      writeFileSync(path.join(DATA, 'page-meta.json'), JSON.stringify(pageMeta, null, 1));
    }
  }
}

await Promise.all(Array.from({ length: CONCURRENCY }, worker));
await browser.close();

writeFileSync(path.join(DATA, 'crawl-log.json'), JSON.stringify({ done, total: urls.length * 2, errors, skipped, counts, log }, null, 1));
writeFileSync(path.join(DATA, 'page-meta.json'), JSON.stringify(pageMeta, null, 1));
writeFileSync(path.join(DATA, 'design-tokens.json'), JSON.stringify(designTokens, null, 1));
console.log(`CRAWL COMPLETE: ${done} captures, ${errors} errors, ${skipped} skipped`);
