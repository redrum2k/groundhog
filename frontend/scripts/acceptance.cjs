const { chromium, expect } = require('@playwright/test');
const path = require('node:path');
const fs = require('node:fs');
const output = path.resolve(process.env.ACCEPTANCE_ARTIFACT_DIR || 'artifacts/browser');
fs.mkdirSync(output, {recursive:true});
const origin = process.env.ACCEPTANCE_ORIGIN || 'http://127.0.0.1:3000';
if (!['127.0.0.1', 'localhost'].includes(new URL(origin).hostname)) throw new Error('Local demo acceptance only');
(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 720}});
    page.setDefaultTimeout(15000);
    const errors = []; const mutations = []; let latest;
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if(message.type() === 'error') errors.push(JSON.stringify({text:message.text(),location:message.location()})); });
    page.on('request', request => { if (request.method() === 'POST') mutations.push(request.url()); });
    page.on('response', async response => {
      if (response.status() === 200 && /\/api\/jobflow\/orders\/[^/]+$/.test(response.url())) {
        const value = await response.json().catch(() => null); if(value?.jobs) latest=value;
      }
    });
    await page.goto(origin, {waitUntil: 'networkidle'});
    const identity = page.getByLabel('Local demo identity');
    await identity.selectOption('customer');
    await page.getByRole('button', {name: /New Northwind case/}).click();
    await expect(page.getByText('Fresh Northwind case recorded. Backend state refreshed.', {exact:true})).toBeVisible({timeout:30000});
    await expect(page.locator('.job-tile')).toHaveCount(100, {timeout: 30000});
    await expect(page.locator('.job-tile.red')).toHaveCount(20);
    await expect(page.locator('.job-tile.orange')).toHaveCount(1);
    await expect(page.locator('.job-tile.green')).toHaveCount(79);
    await page.screenshot({path:path.join(output,'three-colors-1280.png'), fullPage:true});
    const inspectionStart = mutations.length;
    await page.locator('.job-tile').nth(1).click();
    await page.locator('.check-list button').first().click();
    await page.locator('.check-detail .source-card').first().getByRole('button', {name:'Load verified artifact'}).click();
    await expect(page.getByLabel('Cited PDF region')).toBeVisible();
    await page.locator('.pdf-region-view').screenshot({path:path.join(output,'source-highlight.png')});
    await page.getByRole('button', {name:'Overview',exact:true}).click();
    if (mutations.length !== inspectionStart) throw new Error('Source inspection issued a mutation');
    await identity.selectOption('provider');
    await page.getByRole('button', {name:'Correct 20 failed jobs', exact:true}).click();
    await expect(page.locator('.job-tile.red')).toHaveCount(0, {timeout:30000});
    await expect(page.getByLabel('Base order review')).toContainText('held \u00b7 mock', {timeout:30000});
    await page.getByText('Inspect delivered register PDF', {exact:true}).click();
    await page.getByLabel('Base order review').getByRole('button', {name:'Load verified artifact'}).click();
    await expect(page.getByLabel('Base order review').getByRole('link', {name:/Open verified PDF/})).toBeVisible();
    const before = mutations.length;
    await page.getByRole('button', {name:'Replay events',exact:true}).click();
    await page.getByRole('button', {name:'Return to live',exact:true}).click();
    if (mutations.length !== before) throw new Error('Replay issued a mutation');
    await identity.selectOption('controller');
    await page.getByRole('button', {name:'Approve quote',exact:true}).click();
    await identity.selectOption('executor');
    await page.getByRole('button', {name:'Create approved quote',exact:true}).click();
    await identity.selectOption('customer');
    await page.getByRole('button', {name:'Accept quote \u00b7 $8.00',exact:true}).click();
    await page.getByRole('button', {name:'Authorize payment \u00b7 $8.00',exact:true}).click();
    await identity.selectOption('executor');
    await page.getByRole('button', {name:'Record simulated receipt',exact:true}).click();
    await expect.poll(() => latest?.finance?.received_minor, {timeout:20000}).toBe(800);
    if (latest.base_order.order.ledger.length) throw new Error('Added payment captured held base');
    await page.setViewportSize({width:1440,height:900});
    await page.screenshot({path:path.join(output,'held-base-paid-addition-1440.png'),fullPage:true});
    await page.reload({waitUntil:'networkidle'});
    await expect(page.locator('.job-tile')).toHaveCount(100);
    if(errors.length) throw new Error(errors.join('\n'));
    console.log(JSON.stringify({browser:await browser.version(), order_id:latest.id,
      counts:{original:100, validated:latest.jobs.filter(j=>j.kind==='ORIGINAL'&&j.processing==='VALIDATED').length},
      base_phase:latest.base_order.order.payment_phase, received_minor:latest.finance.received_minor,
      correction_cost_minor:latest.finance.correction_cost_minor, replay_mutations:0, js_errors:errors}));
  } finally {await browser.close();}
})().catch(error => {console.error(String(error.message).split('\n').slice(0,12).join('\n')); process.exit(1);});
