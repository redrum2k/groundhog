const { chromium, expect } = require('@playwright/test');
const path = require('node:path');
const fs = require('node:fs');
const origin = process.env.ACCEPTANCE_ORIGIN || 'http://127.0.0.1:3106';
const fixtureRoot = path.resolve(process.env.CATALOG_FIXTURE_DIR || '../backend/artifacts/v6-live-b');
const output = path.resolve(process.env.ACCEPTANCE_ARTIFACT_DIR || 'artifacts/v6-browser-b');
fs.mkdirSync(output, {recursive:true});
if (!['127.0.0.1','localhost'].includes(new URL(origin).hostname)) throw new Error('Local acceptance only');

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const results = [], errors = [], failures = [];
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    page.setDefaultTimeout(20000);
    const posts=[]; let latest;
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', r => {if(r.method()==='POST') posts.push({url:r.url(),body:r.postDataJSON()});});
    page.on('response', async r => {
      if(r.status()>=400) failures.push({url:r.url(),status:r.status()});
      if(r.url().includes('/events?') && r.status()===200) {
        const b=await r.json().catch(()=>null); if(b?.events?.length) latest=b.events.at(-1);
      }
    });
    await page.goto(origin,{waitUntil:'networkidle'});
    await page.getByRole('button',{name:'Catalog live',exact:true}).click();
    await expect(page.getByLabel('Provider corpus')).toHaveValue('storage-2026');
    const initialPosts=posts.length;
    await page.getByRole('button',{name:'Overview',exact:true}).click();
    await page.getByRole('button',{name:'New order',exact:true}).click();
    if(posts.length!==initialPosts) throw new Error('Navigation mutated');
    for(const scenario of ['registered','unregistered']) {
      latest=undefined;
      await page.getByRole('button',{name:'New order',exact:true}).click();
      await page.getByRole('button',{name:'Create new draft',exact:true}).click();
      await page.getByRole('button',{name:'Compile draft · synthetic staff',exact:true}).click();
      await page.getByRole('button',{name:'Request server quote',exact:true}).click();
      await page.getByRole('button',{name:'Accept this quote · customer',exact:true}).click();
      await page.getByRole('button',{name:'Prepare funding',exact:true}).click();
      await page.getByRole('button',{name:'Authorize mock funding · customer',exact:true}).click();
      // The backend's durable payment sweeper may confirm before a manual staff
      // button can be observed. Wait for the authoritative committed state.
      await expect.poll(()=>latest?.payment?.payment.state).toBe('funded');
      await page.getByRole('button',{name:/Produce & verify/}).click();
      await page.getByRole('button',{name:'Execute queued work · synthetic staff',exact:true}).click();
      await page.getByLabel('Evidence PDF').setInputFiles(path.join(fixtureRoot,scenario==='registered'?'registered-repair.pdf':'unregistered.pdf'));
      await expect.poll(()=>latest?.order.amendments?.length ?? 0).toBe(1);
      await page.getByRole('button',{name:'Execute queued work · synthetic staff',exact:true}).click();
      if(scenario==='registered') {
        await expect.poll(()=>latest?.order.amendments?.[0]?.classification).toBe('evidence_only');
        await page.getByRole('button',{name:'Execute queued work · synthetic staff',exact:true}).click();
        await expect.poll(()=>latest?.order.order_state).toBe('delivered');
        if(latest.order.ledger.length) throw new Error('PASS captured before review');
        await page.screenshot({path:path.join(output,'verified-before-capture.png'),fullPage:true});
        const pdf=latest.order.deliveries.at(-1).pdf;
        const response=await page.request.get(`${origin}/api/catalog/orders/${latest.run_id}/artifacts/${pdf.artifact_id}`);
        if(!response.ok()) throw new Error('Actual PDF unavailable');
        fs.writeFileSync(path.join(output,'delivered.pdf'),await response.body());
        await page.getByRole('button',{name:/Review delivery/}).click();
        await page.getByRole('button',{name:'Accept current delivery · customer',exact:true}).click();
        await expect.poll(()=>latest?.payment?.payment.state).toBe('captured');
        if(latest.order.ledger.length!==1) throw new Error('Not exactly one capture');
      } else {
        await expect.poll(()=>latest?.order.amendments?.[0]?.classification).toBe('unresolved');
        await page.getByLabel('Evidence PDF').setInputFiles(path.join(fixtureRoot,'unregistered.pdf'));
        await expect.poll(()=>latest?.order.amendments?.length ?? 0).toBe(2);
        await page.getByRole('button',{name:'Execute queued work · synthetic staff',exact:true}).click();
        await expect.poll(()=>latest?.order.order_state).toBe('human_review');
        if(latest.order.ledger.length) throw new Error('Unknown case captured');
      }
      fs.writeFileSync(path.join(output,`${scenario}-event.json`),JSON.stringify(latest,null,2));
      results.push({scenario,run_id:latest.run_id,state:latest.order.order_state,payment:latest.payment.payment.state,revision:latest.aggregate_revision});
      const before=posts.length;
      await page.getByRole('button',{name:'Read-only replay',exact:true}).click();
      await page.getByRole('button',{name:'Overview',exact:true}).click().catch(()=>{});
      await page.screenshot({path:path.join(output,`${scenario}-replay.png`),fullPage:true});
      await page.getByRole('button',{name:'Return to live',exact:true}).click();
      if(posts.length!==before) throw new Error('Replay or navigation issued mutation');
    }
    if(errors.length) throw new Error(errors.join('\n'));
    const report={browser:await browser.version(),results,errors,failures,replay_mutations:0,post_count:posts.length,mode:'live_backend / deterministic compiler / synthetic staff / mock finance'};
    fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  } catch(error) {
    fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:String(error),results,errors,failures},null,2));
    throw error;
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
