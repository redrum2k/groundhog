// Actual saved proposal -> isolated probe -> separate approval -> activation ->
// genuine Claude clarification -> new accepted order. No desired-verdict inputs.
const { chromium, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const origin = process.env.ACCEPTANCE_ORIGIN || 'http://127.0.0.1:3107';
const output = path.resolve(process.env.ACCEPTANCE_ARTIFACT_DIR || 'artifacts/v6-model-browser');
if (!['127.0.0.1', 'localhost'].includes(new URL(origin).hostname)) throw new Error('Local only');
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const errors = [], failures = [], posts = [], responses = [];
  let latest, draft, activation, before;
  try {
    await expect.poll(async () => {
      try { return (await fetch(`${origin}/api/catalog/corpora`)).status; } catch { return 0; }
    }, { timeout: 30000, intervals: [250, 500, 1000] }).toBe(200);
    const page = await browser.newPage({ viewport: { width: 1600, height: 1100 } });
    page.setDefaultTimeout(30000);
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (r.method() === 'POST') posts.push({ url: r.url(), body: r.postDataJSON() }); });
    page.on('response', async r => {
      if (r.status() >= 400) failures.push({ url: r.url(), status: r.status() });
      const body = await r.json().catch(() => null);
      if (r.url().includes('/events?') && body?.events?.length) latest = body.events.at(-1);
      if (body?.request_id && body?.status) draft = body;
      if (body?.status === 'ACTIVE') activation = body;
      if (r.request().method() === 'POST') responses.push({ url: r.url(), status: r.status(), body });
    });
    await page.goto(origin, { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'Catalog live', exact: true }).click();
    await expect(page.getByLabel('Provider corpus')).toHaveValue('storage-2026');
    const scope = await page.request.get(`${origin}/api/catalog/improvements/scopes/storage-2026`);
    before = await scope.json();
    if (before.active_version !== 'catalog-static-v1') {
      if (process.env.REVALIDATE_VERSION !== before.active_version) throw new Error('Requires original inactive candidate; do not replay lifecycle');
      await page.getByRole('button', { name: 'Improve future work', exact: true }).click();
      await page.getByLabel('Improvement reason').fill('Shared timeout and source-change enforcement changed after retained first browser failure. Revoke the exact old version, re-probe unchanged candidate, approve exact new source. No accepted order or outcome is rewritten.');
      await page.getByRole('button', { name: 'Revoke active procedure for future drafts · reviewer', exact: true }).click();
      await expect(page.getByRole('status')).toContainText('REVOKED');
      before = await (await page.request.get(`${origin}/api/catalog/improvements/scopes/storage-2026`)).json();
    }
    const candidate = before.records.find(r => r.kind === 'catalog_patch' && r.data.mode === 'ANTHROPIC');
    if (!candidate) throw new Error('Genuine saved candidate missing');
    const navigationPosts = posts.length;
    await page.getByRole('button', { name: 'Improve future work', exact: true }).click();
    await expect(page.getByText(candidate.id, { exact: true })).toBeVisible();
    if (posts.length !== navigationPosts) throw new Error('Opening improvement panel mutated');
    await page.screenshot({ path: path.join(output, '01-genuine-proposal.png'), fullPage: true });
    await page.getByRole('button', { name: 'Validate candidate in isolated workflows', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('COMPLETE', { timeout: 60000 });
    await expect(page.getByRole('button', { name: 'Approve exact tested candidate · reviewer', exact: true })).toBeEnabled();
    await page.screenshot({ path: path.join(output, '02-isolated-probe.png'), fullPage: true });
    await page.getByRole('button', { name: 'Approve exact tested candidate · reviewer', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('APPROVED');
    await page.getByRole('button', { name: 'Activate for future drafts · reviewer', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('ACTIVE');
    await expect.poll(() => activation?.version_id).toBeTruthy();
    await page.screenshot({ path: path.join(output, '03-prospective-activation.png'), fullPage: true });
    await page.getByRole('button', { name: 'New order', exact: true }).click();
    await page.getByLabel('Requested work').fill('Select storage products under 1.25 kg and unit price at most USD 35.');
    await page.getByRole('button', { name: 'Create new draft', exact: true }).click();
    await page.getByRole('button', { name: 'Compile draft · synthetic staff', exact: true }).click();
    await expect(page.getByLabel('Clarification answer')).toBeVisible({ timeout: 75000 });
    if (!draft?.question || !['weight_concept', 'weight'].includes(draft.question.field)) throw new Error(`Inspect actual model clarification before responding: ${JSON.stringify(draft?.question)}`);
    const modelQuestion = draft.question;
    await page.screenshot({ path: path.join(output, '04-real-model-question.png'), fullPage: true });
    await page.getByLabel('Clarification answer').fill('Use the weight of one item, excluding its outer shipping packaging.');
    await page.getByRole('button', { name: 'Send answer', exact: true }).click();
    await page.getByRole('button', { name: 'Compile draft · synthetic staff', exact: true }).click();
    await page.getByRole('button', { name: 'Request server quote', exact: true }).click();
    await page.getByRole('button', { name: 'Accept this quote · customer', exact: true }).click();
    await page.getByRole('button', { name: 'Prepare funding', exact: true }).click();
    await page.getByRole('button', { name: 'Authorize mock funding · customer', exact: true }).click();
    await expect.poll(() => latest?.payment?.payment.state).toBe('funded');
    const acceptedHash = latest.accepted_snapshot_sha256;
    if (latest.procedure_version !== activation.version_id) throw new Error('Fresh order did not pin active procedure');
    await page.getByRole('button', { name: /Produce & verify/ }).click();
    await page.getByRole('button', { name: 'Execute queued work · synthetic staff', exact: true }).click();
    await expect.poll(() => latest?.order.amendments?.[0]?.actor).toBe('system:registered-evidence-acquisition');
    await page.getByRole('button', { name: 'Execute queued work · synthetic staff', exact: true }).click();
    await expect.poll(() => latest?.order.amendments?.[0]?.classification).toBe('evidence_only');
    await page.getByRole('button', { name: 'Execute queued work · synthetic staff', exact: true }).click();
    await expect.poll(() => latest?.order.order_state).toBe('delivered');
    if (latest.order.ledger.length || latest.accepted_snapshot_sha256 !== acceptedHash) throw new Error('Early capture or accepted-snapshot mutation');
    await page.screenshot({ path: path.join(output, '05-auto-acquired-verified-new-order.png'), fullPage: true });
    const pdf = latest.order.deliveries.at(-1).pdf;
    const downloaded = await page.request.get(`${origin}/api/catalog/orders/${latest.run_id}/artifacts/${pdf.artifact_id}`);
    if (!downloaded.ok()) throw new Error('Real delivery PDF unavailable');
    fs.writeFileSync(path.join(output, 'delivered.pdf'), await downloaded.body());
    await page.getByRole('button', { name: /Review delivery/ }).click();
    await page.getByRole('button', { name: 'Accept current delivery · customer', exact: true }).click();
    await expect.poll(() => latest?.payment?.payment.state).toBe('captured');
    const count = posts.length;
    await page.getByRole('button', { name: 'Read-only replay', exact: true }).click();
    await page.getByRole('button', { name: 'Overview', exact: true }).click();
    await page.reload({ waitUntil: 'networkidle' });
    await expect.poll(() => latest?.order.order_state).toBe('closed');
    if (posts.length !== count) throw new Error('Replay/refresh issued mutation');
    await page.screenshot({ path: path.join(output, '06-closed-resumed.png'), fullPage: true });
    if (errors.length || failures.length) throw new Error('Browser errors or failed requests');
    const report = { browser: await browser.version(), mode: 'live_backend / genuine_Claude_proposal_and_clarification / synthetic_reviewer / mock_finance',
      candidate_id: candidate.id, active_version: activation.version_id, question: modelQuestion, new_order: latest.run_id,
      state: latest.order.order_state, payment: latest.payment.payment.state, capture_count: latest.order.ledger.length,
      replay_mutations: 0, posts, responses, errors, failures, latest };
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ new_order: latest.run_id, version: activation.version_id, question: modelQuestion, state: report.state, payment: report.payment, posts: posts.length, errors, failures }));
  } catch (error) {
    fs.writeFileSync(path.join(output, 'failure.json'), JSON.stringify({ error: String(error), latest, draft, activation, posts, responses, errors, failures }, null, 2));
    throw error;
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
