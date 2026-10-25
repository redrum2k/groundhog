// Actual UI + isolated mock backend. No scripted verdict, paid model or chain operation.
const { chromium, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

const origin = process.env.BROKER_SMOKE_ORIGIN || 'http://127.0.0.1:3000';
const backend = process.env.BROKER_SMOKE_BACKEND;
if (!backend) throw new Error('Set BROKER_SMOKE_BACKEND to an isolated mock backend.');
for (const url of [origin, backend]) {
  if (new URL(url).protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(new URL(url).hostname)) {
    throw new Error('Loopback HTTP only');
  }
}
const output = path.resolve(process.env.BROKER_SMOKE_OUTPUT || '../.local/oakland-dispute-check/browser');
fs.mkdirSync(output, { recursive: true });

(async () => {
  const health = await (await fetch(`${backend}/health`)).json();
  if (health.payment_mode !== 'mock' || health.live_settlement_enabled) throw new Error('Mock backend required');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.tracing.start({ screenshots: true, snapshots: true });
  // Redirect this isolated browser only. Never send commands to the user's live backend.
  await context.route('**/api/live/**', async route => {
    const request = route.request();
    const url = new URL(request.url());
    const target = url.pathname.slice('/api/live'.length) + url.search;
    const headers = { 'Content-Type': 'application/json' };
    const key = request.headers()['idempotency-key'];
    if (key) headers['Idempotency-Key'] = key;
    const response = await context.request.fetch(backend + target, {
      method: request.method(), headers, data: request.postData() || undefined,
    });
    await route.fulfill({ response });
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let run;
  async function events() {
    const collected = [];
    let result, after = 0;
    do {
      const response = await context.request.get(`${backend}/runs/${run}/events?after=${after}`);
      if (!response.ok()) throw new Error(await response.text());
      result = await response.json();
      collected.push(...result.events);
      after = result.next_after;
    } while (!result.caught_up);
    return { ...result, events: collected };
  }
  try {
    await page.goto(origin);
    await page.getByLabel('Dataset request').fill('SF adults 25–34 interested in fitness, counts by ZIP.');
    await page.getByRole('button', { name: 'Create request', exact: true }).click();
    await page.getByLabel('Your answer', { exact: true }).fill('Gym membership or fitness-app use');
    await page.getByRole('button', { name: 'Submit answer', exact: true }).click();
    await page.getByRole('button', { name: 'Prepare quote', exact: true }).click();
    run = JSON.parse(await page.evaluate(() => localStorage.getItem('datumco.live-run.v1'))).id;
    const quoted = await events();
    if (quoted.quote.payment_terms.mode !== 'mock') throw new Error('Refusing non-mock checkout');
    await page.getByRole('button', { name: 'Accept & simulate $1.00', exact: true }).click();
    await expect(page.getByRole('main', { name: 'Run view' })).toBeVisible();
    await page.getByRole('button', { name: 'Customer view', exact: true }).click();
    await expect(page.getByRole('link', { name: 'Download CSV' })).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: 'Object', exact: true }).click();
    await page.getByLabel('Your complaint', { exact: true }).fill('Oakland should be there');
    await page.getByRole('button', { name: 'Send complaint', exact: true }).click();
    let result;
    await expect.poll(async () => {
      result = await events();
      return result.events.findLast(event => event.type === 'verdict')?.verdict.kind;
    }, { timeout: 15000 }).toBe('disagree');
    fs.writeFileSync(path.join(output, 'dispute-events.json'), JSON.stringify(result, null, 2));
    const verdict = result.events.findLast(event => event.type === 'verdict').verdict;
    if (!/Oakland/i.test(verdict.reason) || !/San Francisco|\bSF\b/i.test(verdict.reason)) throw new Error('Missing scope explanation');
    if (result.evidence_request) throw new Error('Unsupported complaint asked for evidence');
    if (result.available_actions.some(action => ['approve', 'reject', 'ask', 'escalate'].includes(action.action) && action.enabled)) throw new Error('Unnecessary human decision');
    if (!result.available_actions.some(action => action.action === 'accept' && action.enabled)) throw new Error('Buyer cannot accept delivery');
    for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      await expect(page.getByRole('main', { name: 'Run view' })).toBeVisible();
      const overflow = await page.evaluate(() => [...document.querySelectorAll('.ev-stack')].map(stack => ({
        height: stack.getBoundingClientRect().height,
        client: stack.clientHeight,
        scroll: stack.scrollHeight,
        count: stack.children.length,
      })));
      if (overflow.some(stack => stack.height > 200 || stack.scroll > stack.client + 1 || stack.count > 5)) throw new Error('Unbounded canvas evidence stack: ' + JSON.stringify(overflow));
      await page.screenshot({ path: path.join(output, `canvas-${viewport.width}.png`) });
    }
    for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      await page.getByRole('button', { name: 'Customer view', exact: true }).click();
      await expect(page.getByText(verdict.reason, { exact: true }).first()).toBeInViewport({ ratio: 1 });
      const heading = await page.getByRole('heading', { name: 'Complaint assessment' }).boundingBox();
      const stickyHeader = await page.locator('.cust-h').boundingBox();
      if (heading.y < stickyHeader.y + stickyHeader.height) throw new Error('Assessment hidden behind sticky customer header');
      await expect(page.getByRole('button', { name: /regenerate|approve|Open human review/i })).toHaveCount(0);
      await page.screenshot({ path: path.join(output, `buyer-explanation-${viewport.width}.png`) });
      if (viewport.width === 1440) await page.getByRole('button', { name: 'Run', exact: true }).click();
    }
    await page.getByRole('button', { name: 'Accept verified delivery', exact: true }).click();
    await expect.poll(async () => (await events()).payment.payment.state, { timeout: 15000 }).toBe('captured');
    result = await events();
    if (result.payment.explorer_links.length || result.payment.operations.some(op => op.transaction_hash)) throw new Error('Mock chain claim');
    if (errors.length) throw new Error(errors.join('\n'));
    fs.writeFileSync(path.join(output, 'captured-events.json'), JSON.stringify(result, null, 2));
    await page.screenshot({ path: path.join(output, 'captured.png') });
    console.log(JSON.stringify({ run, output, verdict: verdict.kind, payment: result.payment.payment.state, errors }));
  } catch (error) {
    await page.screenshot({ path: path.join(output, 'failure.png') });
    if (run) fs.writeFileSync(path.join(output, 'failure-events.json'), JSON.stringify(await events(), null, 2));
    throw error;
  } finally {
    await context.tracing.stop({ path: path.join(output, 'trace.zip') });
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
