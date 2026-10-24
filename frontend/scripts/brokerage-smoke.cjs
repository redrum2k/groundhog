// Real production frontend -> same-origin Next bridge -> local backend. Mock only.
const {chromium,expect}=require('@playwright/test');
const fs=require('node:fs'); const path=require('node:path');
const origin=process.env.BROKER_SMOKE_ORIGIN || 'http://127.0.0.1:3016';
if (!['127.0.0.1','localhost'].includes(new URL(origin).hostname)) throw new Error('Trusted local demo only');
const output=path.resolve(process.env.BROKER_SMOKE_OUTPUT || 'artifacts/broker-browser');
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:900}});
 await context.tracing.start({screenshots:true,snapshots:true});
 const page=await context.newPage(); const errors=[]; let latest;
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',async response=>{if(response.ok() && /\/runs\/[^/]+\/events/.test(response.url())) latest=await response.json();});
 try {
  await page.goto(origin);
  await page.getByLabel('Dataset request').fill('SF adults 25–34, gym members or fitness-app users, grouped by ZIP.');
  await page.getByRole('button',{name:'Create request',exact:true}).click();
  await expect(page.getByRole('button',{name:'Prepare quote',exact:true})).toBeVisible({timeout:20000});
  await page.getByRole('button',{name:'Prepare quote',exact:true}).click();
  await expect(page.getByRole('button',{name:'Accept $120.00 quote',exact:true})).toBeVisible();
  if(latest.quote.payment_terms.mode !== 'mock') throw new Error('Smoke refuses live payment mode');
  await page.getByRole('button',{name:'Accept $120.00 quote',exact:true}).click();
  await page.getByRole('button',{name:'Funding',exact:true}).click();
  await page.getByRole('button',{name:'Prepare funding',exact:true}).click();
  await page.getByRole('button',{name:'Simulate mock funding',exact:true}).click();
  await page.getByRole('button',{name:'Delivery & review',exact:true}).click();
  await expect(page.getByRole('link',{name:'Download CSV',exact:true})).toBeVisible({timeout:20000});
  await expect(page.getByRole('cell',{name:'94110',exact:true})).toBeVisible();
  await expect(page.locator('tr').filter({hasText:'94129'})).toContainText('suppressed');
  await page.screenshot({path:path.join(output,'delivery.png'),fullPage:true});
  const run=latest.request.request_id;
  await page.reload();
  await page.getByRole('button',{name:'Delivery & review',exact:true}).click();
  await expect(page.getByRole('link',{name:'Download CSV',exact:true})).toBeVisible();
  if(latest.request.request_id!==run) throw new Error('Reload created another run');
  const csv=await (await context.request.get(new URL(await page.getByRole('link',{name:'Download CSV',exact:true}).getAttribute('href'),origin).href)).body();
  fs.writeFileSync(path.join(output,'delivery.csv'),csv);
  await page.getByRole('button',{name:'Accept verified delivery',exact:true}).click();
  await expect.poll(()=>latest?.payment?.payment.state,{timeout:20000}).toBe('captured');
  if(errors.length)throw new Error(errors.join('\n'));
  if(latest.payment.explorer_links.length) throw new Error('Mock explorer link');
  const events=await (await context.request.get(`${origin}/api/live/runs/${run}/events`)).json();
  fs.writeFileSync(path.join(output,'events-payment.json'),JSON.stringify(events,null,2));
  await page.screenshot({path:path.join(output,'captured.png'),fullPage:true});
  console.log(JSON.stringify({run,output,browser:await browser.version(),mock:true,errors}));
 } finally {await context.tracing.stop({path:path.join(output,'trace.zip')});await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
