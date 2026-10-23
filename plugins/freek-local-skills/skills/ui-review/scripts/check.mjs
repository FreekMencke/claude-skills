// Measures what a script can check on a running UI and prints one JSON report: axe (WCAG 2.2 AA tags), horizontal
// overflow, `transition: all`, images without dimensions, console errors and failed requests per page and width; motion
// left running under reduced motion; a keyboard walk from the top and one that starts scrolled (focus under a sticky
// header shows only then); the states of each data view forced with page.route; and form checks. It never fails a run:
// it reports, and the ui-review skill judges.
//   node check.mjs <plan.json> --out <dir> [--modules <dir>]
// The plan's shape is in ../references/plan.md. Viewport screenshots go to --out. Playwright and @axe-core/playwright
// load from --modules (default: the current folder, so run it from the app's repo when it has them).
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { parseArgs } from 'node:util';

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']; // without wcag22aa, target-size never runs
const HEIGHTS = { 1440: 900, 768: 1024, 375: 812, 320: 640 };
const MAX_STOPS = 40;
const MAX_LIST = 8;
const USAGE = 'Usage: node check.mjs <plan.json> --out <dir> [--modules <dir>]';

let plan, out, modules;
try {
  const { values, positionals } = parseArgs({
    options: { out: { type: 'string' }, modules: { type: 'string', default: process.cwd() } },
    allowPositionals: true,
    strict: true,
  });
  if (positionals.length !== 1 || !values.out) throw new Error('A plan and --out are required.');
  plan = JSON.parse(readFileSync(positionals[0], 'utf8'));
  ({ out, modules } = values);
} catch (error) {
  console.error(`${error.message}\n${USAGE}`);
  process.exit(2);
}

let chromium, AxeBuilder;
try {
  const require = createRequire(join(resolve(modules), 'noop.js'));
  ({ chromium } = require('playwright'));
  AxeBuilder = require('@axe-core/playwright').default;
} catch {
  console.error(
    `playwright and @axe-core/playwright aren't installed under ${modules}. In a scratch folder:\n` +
      '  npm install --ignore-scripts playwright@1.64.1 @axe-core/playwright@4.14.0\n' +
      '  npx playwright install --only-shell chromium\nthen pass --modules <that folder>.',
  );
  process.exit(2);
}

mkdirSync(out, { recursive: true });
const widths = plan.widths ?? [1440, 768, 375, 320];
const colorScheme = plan.colorScheme ?? 'light';
const url = (path) => new URL(path, plan.base).href;
const slug = (path) => path.replace(/^\/|\/$/g, '').replace(/[^\w-]+/g, '-') || 'home';
const report = { base: plan.base, colorScheme, widths, pages: [], motion: [], keyboard: [], states: [], forms: [], notRun: [] };

// In-page helpers, installed in every page before its scripts run
const helpers = () => {
  const describe = (el) => {
    if (!el || el === document.body || el === document.documentElement) return 'body';
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    else if (el.classList.length) s += '.' + [...el.classList].slice(0, 2).join('.');
    const text = (el.getAttribute('aria-label') ?? el.textContent ?? '').trim().replace(/\s+/g, ' ').slice(0, 30);
    return text ? `${s} "${text}"` : s;
  };
  // What a focus indicator can change; compared between focused and at rest, so a resting box-shadow isn't a ring
  const look = (el) => {
    const s = getComputedStyle(el);
    return {
      outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) ? `outline ${s.outlineStyle} ${s.outlineWidth} ${s.outlineColor}` : '',
      shadow: s.boxShadow !== 'none' ? `shadow ${s.boxShadow}` : '',
      background: `background ${s.backgroundColor}`,
      border: `border ${s.borderColor} ${s.borderWidth}`,
      text: `text ${s.color} ${s.textDecorationLine}`,
    };
  };
  // How many of the corners and the centre show the element on top: 0/5 is fully covered (WCAG 2.4.11)
  const uncovered = (el) => {
    const r = el.getBoundingClientRect();
    const points = [[r.left + 1, r.top + 1], [r.right - 1, r.top + 1], [r.left + 1, r.bottom - 1], [r.right - 1, r.bottom - 1], [r.left + r.width / 2, r.top + r.height / 2]];
    return points.filter(([x, y]) => { const hit = document.elementFromPoint(x, y); return hit && (el.contains(hit) || hit.contains(el)); }).length;
  };
  // Elements sticking out past the viewport's right edge, outermost only
  const overflow = (root = document.body) => {
    const offenders = [...root.querySelectorAll('*')].filter((el) => el.checkVisibility() && el.getBoundingClientRect().right > innerWidth + 1);
    const outermost = offenders.filter((el) => !offenders.includes(el.parentElement));
    return { page: document.documentElement.scrollWidth - document.documentElement.clientWidth, count: outermost.length, elements: outermost.slice(0, 8).map(describe) };
  };
  const statusText = () => [...document.querySelectorAll('[role=status], [role=alert], [aria-live]')].map((el) => `${describe(el).split(' ')[0]}: ${el.textContent.trim().slice(0, 80)}`);
  window.__ui = { describe, look, uncovered, overflow, statusText, stops: [] };
};

const settle = (page) => page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
const open = async (context, path, { wait = true } = {}) => {
  const page = await context.newPage();
  const console_ = [], failed = [];
  page.on('console', (msg) => msg.type() === 'error' && console_.push(msg.text().split('\n')[0].slice(0, 200)));
  page.on('requestfailed', (req) => failed.push(`${req.method()} ${req.url()} ${req.failure()?.errorText}`));
  page.on('response', (res) => res.status() >= 400 && failed.push(`${res.request().method()} ${res.url()} ${res.status()}`));
  await page.goto(url(path), { waitUntil: wait ? 'load' : 'commit' });
  if (wait) await settle(page);
  return { page, console: console_, failed };
};
const newContext = (browser, width, options = {}) =>
  browser.newContext({ viewport: { width, height: HEIGHTS[width] ?? 900 }, colorScheme, ...options });
const axe = async (page, root) => {
  const builder = new AxeBuilder({ page }).withTags(TAGS);
  if (root) builder.include(root);
  const { violations, incomplete } = await builder.analyze();
  return {
    violations: violations.map(({ id, impact, nodes }) => ({ id, impact, count: nodes.length, targets: nodes.slice(0, 5).map((n) => n.target.join(' >> ')) })),
    incomplete: incomplete.map(({ id, nodes }) => `${id} ${nodes.length}`),
  };
};
const text = (page, root) => page.evaluate((root) => (document.querySelector(root) ?? document.body).innerText.trim().replace(/\n{2,}/g, '\n').slice(0, 600), root);
const lines = (s) => new Set(s.split('\n').map((l) => l.trim()).filter(Boolean));

// Tab from the top, then again with each target first scrolled to the top of the viewport (under any sticky header)
const walk = async (page) => {
  await page.evaluate(() => { document.activeElement?.blur(); scrollTo(0, 0); });
  for (let i = 0; i < MAX_STOPS; i++) {
    await page.keyboard.press('Tab');
    const done = await page.evaluate(() => {
      const el = document.activeElement, { stops } = window.__ui;
      if (el === document.body || stops.some((s) => s.el === el)) return true;
      stops.push({ el, focused: window.__ui.look(el), visible: el.matches(':focus-visible'), uncovered: window.__ui.uncovered(el) });
      return false;
    });
    if (done) break;
  }
  const stops = await page.evaluate(() => {
    document.activeElement?.blur();
    return window.__ui.stops.map(({ el, focused, visible, uncovered }) => {
      const rest = window.__ui.look(el);
      const changed = Object.keys(focused).filter((k) => focused[k] && focused[k] !== rest[k]).map((k) => focused[k]);
      return `${window.__ui.describe(el)} | ${changed.join('; ') || 'NO INDICATOR'}${visible ? '' : ' (not :focus-visible)'} | ${uncovered}/5`;
    });
  });
  const scrolled = [];
  for (let i = 1; i < stops.length; i++) {
    await page.evaluate((i) => {
      const { stops } = window.__ui;
      stops[i - 1].el.focus({ preventScroll: true });
      scrollBy(0, stops[i].el.getBoundingClientRect().top);
    }, i);
    await page.keyboard.press('Tab');
    const row = await page.evaluate((i) => {
      const el = document.activeElement;
      if (el !== window.__ui.stops[i].el) return null;
      const n = window.__ui.uncovered(el);
      return n < 5 ? `${window.__ui.describe(el)} | ${n}/5` : null;
    }, i);
    if (row) scrolled.push(row);
  }
  return { stops, partlyOrFullyCoveredWhenScrolled: scrolled };
};

const pageChecks = (page) =>
  page.evaluate(() => {
    const all = [...document.querySelectorAll('*')];
    const transitionAll = all.filter((el) => {
      const s = getComputedStyle(el);
      return s.transitionProperty.split(',').some((p) => p.trim() === 'all') && s.transitionDuration.split(',').some((d) => parseFloat(d) > 0);
    });
    const images = [...document.images].filter((img) => !(img.getAttribute('width') && img.getAttribute('height')) && getComputedStyle(img).aspectRatio === 'auto');
    return {
      overflow: window.__ui.overflow(),
      transitionAll: { count: transitionAll.length, elements: transitionAll.slice(0, 8).map(window.__ui.describe) },
      imagesWithoutSize: { count: images.length, elements: images.slice(0, 8).map((img) => `${window.__ui.describe(img)} ${img.currentSrc.slice(-60)}`) },
    };
  });

const animations = (page) =>
  page.evaluate(() => {
    const running = document.getAnimations().filter((a) => a.playState === 'running');
    const name = (a) => `${window.__ui.describe(a.effect?.target)} ${a.animationName ?? a.transitionProperty ?? a.id ?? 'animation'}`;
    return {
      infinite: running.filter((a) => a.effect?.getComputedTiming().iterations === Infinity).map(name).slice(0, 8),
      finite: running.filter((a) => a.effect?.getComputedTiming().iterations !== Infinity).map(name).slice(0, 8),
      smoothScroll: getComputedStyle(document.documentElement).scrollBehavior === 'smooth',
    };
  });

const browser = await chromium.launch().catch((error) => {
  console.error(`Can't start Chromium: ${error.message.split('\n')[0]}`);
  process.exit(2);
});
report.browser = `chromium ${browser.version()}`;
try {
  // Pages at each width: axe, layout checks, a screenshot, the keyboard walks
  for (const width of widths) {
    const context = await newContext(browser, width);
    await context.addInitScript(helpers);
    for (const path of plan.pages ?? []) {
      try {
        const { page, console: errors, failed } = await open(context, path);
        const screenshot = join(out, `${slug(path)}-${width}.png`);
        await page.screenshot({ path: screenshot });
        const result = await axe(page);
        report.pages.push({ path, width, screenshot, ...(await pageChecks(page)), axe: result, consoleErrors: errors.slice(0, MAX_LIST), failedRequests: failed.slice(0, MAX_LIST) });
        report.keyboard.push({ path, width, ...(await walk(page)) });
        await page.close();
      } catch (error) {
        report.notRun.push(`${path} at ${width}: ${error.message.split('\n')[0]}`);
      }
    }
    await context.close();
  }

  // Motion: what still runs at load under reduce, against no-preference
  for (const path of plan.pages ?? []) {
    const row = { path };
    for (const reducedMotion of ['no-preference', 'reduce']) {
      const context = await newContext(browser, widths[0], { reducedMotion });
      await context.addInitScript(helpers);
      try {
        const { page } = await open(context, path);
        row[reducedMotion] = await animations(page);
      } catch (error) {
        report.notRun.push(`motion ${path} (${reducedMotion}): ${error.message.split('\n')[0]}`);
      }
      await context.close();
    }
    report.motion.push(row);
  }

  // Data views: each state forced on the view's API route, axe on the view in each
  for (const view of plan.views ?? []) {
    const root = view.root ?? 'main';
    const bodies = view.bodies ?? {};
    const results = {};
    const states = ['loaded', 'loading', 'empty', 'error', 'network', 'partial', 'long', 'offline'];
    for (const state of states) {
      if (['empty', 'partial', 'long'].includes(state) && !bodies[state]) {
        report.notRun.push(`${view.page} ${state}: no bodies.${state} in the plan`);
        continue;
      }
      if (state === 'offline' && !view.refetch) {
        report.notRun.push(`${view.page} offline: no refetch selector in the plan`);
        continue;
      }
      const width = state === 'long' ? Math.min(...widths) : widths[0];
      const context = await newContext(browser, width);
      await context.addInitScript(helpers);
      let release, failing = true;
      const held = new Promise((r) => (release = r));
      const handlers = {
        loading: async (route) => { await held; await route.fallback(); },
        empty: (route) => route.fulfill({ json: bodies.empty }),
        partial: (route) => route.fulfill({ json: bodies.partial }),
        long: (route) => route.fulfill({ json: bodies.long }),
        error: (route) => (failing ? route.fulfill({ status: 500, body: '' }) : route.fallback()),
        network: (route) => route.abort('connectionrefused'),
      };
      if (handlers[state]) await context.route(view.api, handlers[state]);
      const row = { view: view.page, state, width };
      try {
        // A server-rendered page gets its data on the server, out of page.route's reach: start on `from` and follow
        // `link`, so the view loads its data in the browser
        const { page, console: errors } = await open(context, view.from ?? view.page, { wait: state !== 'loading' || !!view.from });
        if (view.from) {
          await page.locator(view.link).first().click();
          if (state !== 'loading') await settle(page);
        }
        if (state === 'loading') await page.waitForTimeout(1500); // indicators often show after about 1 s
        if (state === 'offline') {
          await context.setOffline(true); // no route is mocked here: a mocked route would still answer offline
          await page.locator(view.refetch).first().click();
          await page.waitForTimeout(1000);
        }
        row.text = await text(page, root);
        row.status = await page.evaluate(() => window.__ui.statusText());
        row.screenshot = join(out, `${slug(view.page)}-${state}-${width}.png`);
        await page.screenshot({ path: row.screenshot });
        if (await page.locator(root).count()) row.axe = await axe(page, root);
        if (state === 'long') row.overflow = await page.evaluate((root) => window.__ui.overflow(document.querySelector(root) ?? document.body), root);
        if (state === 'error' && view.retry) {
          const retry = page.locator(view.retry).first();
          if (await retry.count()) {
            failing = false;
            await retry.focus();
            await page.keyboard.press('Enter');
            await settle(page);
            row.afterRetry = { focus: await page.evaluate(() => window.__ui.describe(document.activeElement)), text: (await text(page, root)).slice(0, 200) };
          } else row.afterRetry = `no element matches ${view.retry}`;
        }
        row.consoleErrors = errors.slice(0, MAX_LIST);
        if (state === 'loading') release();
        results[state] = row;
        report.states.push(row);
      } catch (error) {
        report.notRun.push(`${view.page} ${state}: ${error.message.split('\n')[0]}`);
      }
      release();
      await context.close();
    }
    if (results.empty && results.loaded && results.empty.text === results.loaded.text)
      report.notRun.push(`${view.page}: the empty state shows the same text as the loaded one, so the mock may not reach the view (data loaded during server rendering? set from and link)`);
    // An empty message shown while loading (UIPAT-001): lines only the empty state has, seen in the loading state
    if (results.empty && results.loaded && results.loading) {
      const loaded = lines(results.loaded.text), loading = lines(results.loading.text);
      results.loading.emptyMessageWhileLoading = [...lines(results.empty.text)].filter((l) => !loaded.has(l) && loading.has(l));
    }
  }

  // Forms: no error on passing through an empty field, submit enabled before a submit, focus and errors after submit.
  // Every request but GET is aborted, so a submit never reaches the server.
  for (const form of plan.forms ?? []) {
    const selector = form.form ?? 'form';
    const context = await newContext(browser, widths[0]);
    await context.addInitScript(helpers);
    const blocked = [];
    await context.route('**', (route) => {
      if (route.request().method() === 'GET') return route.fallback();
      blocked.push(`${route.request().method()} ${route.request().url()}`);
      return route.abort();
    });
    const row = { page: form.page, form: selector };
    try {
      const { page } = await open(context, form.page);
      const fields = `${selector} :is([required], [aria-required="true"])`;
      const submit = page.locator(`${selector} :is(button[type=submit], button:not([type]), input[type=submit])`).first();
      row.submitDisabledBeforeSubmit = (await submit.count())
        ? await submit.evaluate((el) => el.disabled || el.getAttribute('aria-disabled') === 'true')
        : 'no submit button found';
      const before = lines(await text(page, selector));
      const first = page.locator(fields).first();
      if (await first.count()) {
        await first.focus();
        await page.keyboard.press('Tab');
        const added = [...lines(await text(page, selector))].filter((l) => !before.has(l));
        row.afterLeavingEmptyField = { field: await first.evaluate((el) => window.__ui.describe(el)), ariaInvalid: await first.getAttribute('aria-invalid'), newText: added.slice(0, 5) };
      } else row.afterLeavingEmptyField = 'no required field found';
      if (row.submitDisabledBeforeSubmit === false) {
        await submit.focus();
        await page.keyboard.press('Enter');
        await page.waitForTimeout(500);
        row.afterSubmit = await page.evaluate((fields) => {
          const label = (el) => el.labels?.[0]?.textContent.trim() ?? el.getAttribute('aria-label') ?? el.name;
          const description = (el) => (el.getAttribute('aria-describedby') ?? '').split(/\s+/).map((id) => document.getElementById(id)?.textContent.trim()).filter(Boolean).join(' | ');
          return {
            focus: window.__ui.describe(document.activeElement),
            fields: [...document.querySelectorAll(fields)].slice(0, 10).map((el) => ({ field: label(el), ariaInvalid: el.getAttribute('aria-invalid'), description: description(el), native: el.validationMessage })),
            status: window.__ui.statusText(),
          };
        }, fields);
        row.screenshot = join(out, `${slug(form.page)}-${slug(selector)}-submitted.png`);
        await page.screenshot({ path: row.screenshot });
      }
      row.blockedRequests = blocked;
    } catch (error) {
      report.notRun.push(`form ${form.page}: ${error.message.split('\n')[0]}`);
    }
    report.forms.push(row);
    await context.close();
  }
} finally {
  await browser.close();
}
console.log(JSON.stringify(report, null, 1));
