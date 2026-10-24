// Production UI -> real local API -> independent coverage check. No scripted verdict.
const {chromium,expect}=require('@playwright/test');
const fs=require('node:fs');
const path=require('node:path');
const origin=process.env.BROKER_SMOKE_ORIGIN || 'http://127.0.0.1:3028';
if(!['127.0.0.1','localhost'].includes(new URL(origin).hostname)) throw new Error('Local demo only');
const output=path.resolve(process.env.BROKER_SMOKE_OUTPUT || 'artifacts/review-browser');
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.tracing.start({screenshots:true,snapshots:true});
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try {
  await page.goto(origin);
  await page.getByLabel('Dataset request').fill('SF adults 25–34, gym members or fitness-app users, grouped by ZIP.');
  await page.getByRole('button',{name:'Create request',exact:true}).click();
  await page.getByRole('button',{name:'Prepare quote',exact:true}).click({timeout:20000});
  const quoteResponse=await context.request.get(`${origin}/api/live/runs/${JSON.parse(await page.evaluate(()=>localStorage.getItem('datumco.live-run.v1'))).id}/events`);
  const quoted=await quoteResponse.json();
  if(quoted.quote?.payment_terms.mode!=='mock') throw new Error('Smoke refuses live payments');
  await page.getByRole('button',{name:'Accept $120.00 quote',exact:true}).click();
  await page.getByRole('button',{name:'Funding',exact:true}).click();
  await page.getByRole('button',{name:'Prepare funding',exact:true}).click();
  await page.getByRole('button',{name:'Simulate mock funding',exact:true}).click();
  await page.getByRole('button',{name:'Delivery & review',exact:true}).click();
  await expect(page.getByRole('link',{name:'Download CSV'})).toBeVisible({timeout:20000});
  await page.getByLabel('Accepted requirement',{exact:true}).selectOption('R-COVERAGE');
  await page.getByLabel('Dataset row',{exact:true}).selectOption('94110');
  await page.getByLabel('Dataset column (optional)',{exact:true}).selectOption('zip');
  await page.getByLabel('Request type',{exact:true}).selectOption('dispute_fact');
  await page.getByLabel('Complaint or scope request',{exact:true}).fill('ZIP 94110 is missing from the delivery');
  const responsePromise=page.waitForResponse(r=>r.url().endsWith('/disputes') && r.request().method()==='POST');
  await page.getByRole('button',{name:'Record complaint',exact:true}).click();
  const response=await responsePromise;
  if(!response.ok()) throw new Error('Complaint rejected: '+await response.text());
  const posted=response.request().postDataJSON();
  if(posted.complaint.field!=='coverage' || posted.complaint.product_id!=='94110' || posted.complaint.column!=='zip') throw new Error('Complaint target was lost');
  let result;
  await expect.poll(async()=>{
    const events=[];let after=0;
    do {
      result=await (await context.request.get(`${origin}/api/live/runs/${quoted.request.request_id}/events?after=${after}`)).json();
      events.push(...result.events);after=result.next_after;
    } while(!result.caught_up);
    result.events=events;
    return events.findLast(e=>e.type==='verdict')?.verdict.kind;
  },{timeout:20000}).toBe('disagree');
  const verdict=result.events.findLast(e=>e.type==='verdict');
  if(!verdict.verdict.reason.includes('exact disputed ZIP is present')) throw new Error('Wrong coverage assessment');
  if(result.evidence_request) throw new Error('Unrelated evidence question consumed budget');
  if(result.payment.explorer_links.length || result.payment.operations.some(o=>o.transaction_hash)) throw new Error('Mock chain claim');
  if(errors.length) throw new Error(errors.join('\n'));
  await page.screenshot({path:path.join(output,'coverage.png'),fullPage:true});
  fs.writeFileSync(path.join(output,'coverage-events.json'),JSON.stringify({posted,result},null,2));
  console.log(JSON.stringify({run:quoted.request.request_id,output,mock:true,verdict:verdict.verdict.kind,errors}));
 } finally {
  await context.tracing.stop({path:path.join(output,'trace.zip')});await browser.close();
 }
})().catch(e=>{console.error(e.message);process.exitCode=1;});
