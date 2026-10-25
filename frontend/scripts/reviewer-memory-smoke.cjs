// Actual browser -> Next bridge -> isolated backend with injected assessor transport.
// Never run against an existing demo, paid model or live-payment backend.
const {chromium,expect}=require('@playwright/test');
const fs=require('node:fs');
const path=require('node:path');
const origin=process.env.BROKER_SMOKE_ORIGIN || 'http://127.0.0.1:3057';
if(!['127.0.0.1','localhost'].includes(new URL(origin).hostname))throw new Error('Local test only');
const output=path.resolve(process.env.BROKER_SMOKE_OUTPUT || '/private/tmp/groundhog-memory-browser-results');
fs.mkdirSync(output,{recursive:true});
const prompt='SF adults 25-34, gym membership or fitness app users, by ZIP. Exclude yoga.';
const easy='Regenerate the delivery because ZIP 94110 is missing.';
const ambiguous='The Wellness label looks like a gym category; is standalone yoga omitted from what I bought?';
const followup='Under our accepted scope, standalone yoga counts as gym membership.';
const guidance="For a yoga-as-gym interpretation, inspect the frozen authority's yoga_is_gym cell. The Wellness label alone is not membership evidence. Compare the current accepted category and definition; do not infer inclusion or a delivery defect from a label. If taxonomy is null or conflicts with scope, retain UNKNOWN or CONFLICT.";
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.tracing.start({screenshots:true,snapshots:true});
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function runId(){return JSON.parse(await page.evaluate(()=>localStorage.getItem('datumco.live-run.v1'))).id;}
 async function read(run){
  let after=0,current;const events=[];
  do{const response=await context.request.get(`${origin}/api/live/runs/${run}/events?after=${after}`);expect(response.ok()).toBe(true);current=await response.json();events.push(...current.events);after=current.next_after;}while(!current.caught_up);
  return {...current,events};
 }
 async function deliver(){
  await page.getByLabel('Dataset request').fill(prompt);
  await page.getByRole('button',{name:'Create request',exact:true}).click();
  await page.getByRole('button',{name:'Prepare quote',exact:true}).click({timeout:20000});
  const run=await runId();
  expect((await read(run)).quote.payment_terms.mode).toBe('mock');
  await page.getByRole('button',{name:'Accept & simulate $1.00',exact:true}).click();
  await page.getByRole('button',{name:'Customer view',exact:true}).click();
  await expect(page.getByRole('link',{name:'Download CSV'})).toBeVisible({timeout:20000});
  return run;
 }
 async function complain(text,repeat=false){
  await page.getByRole('button',{name:'Customer view',exact:true}).click();
  await page.getByRole('button',{name:repeat?'Object again':'Object',exact:true}).click();
  await page.getByLabel('Your complaint',{exact:true}).fill(text);
  await page.getByRole('button',{name:'Send complaint',exact:true}).click();
 }
 try{
  await page.goto(`${origin}/live`);
  const first=await deliver();
  await complain(easy);
  await expect(page.getByText('Objection not upheld',{exact:true}).first()).toBeVisible({timeout:20000});
  let state=await read(first);
  const firstFinding=state.events.findLast(e=>e.type==='verdict').verdict.finding;
  expect(firstFinding.effective.reason_code).toBe('INJECTED_OFFLINE_TEST');
  expect(firstFinding.reviewer_guidance).toEqual([]);
  const reviewDeadline=state.reviewClosesAt;
  await complain(ambiguous,true);
  await page.getByRole('button',{name:'Customer view',exact:true}).click();
  await page.getByRole('button',{name:/don.t have this evidence/}).click({timeout:20000});
  await page.getByRole('button',{name:'Open human review',exact:true}).click({timeout:20000});
  await page.getByLabel('Reason or evidence answer').fill('Inspect the exact taxonomy cell, not only its label.');
  await page.getByLabel('Guidance for similar cases (optional)').fill(guidance);
  await page.getByText('Supporting evidence',{exact:true}).click();
  await page.getByRole('checkbox',{name:/yoga_is_gym/}).first().check();
  const ackPromise=page.waitForResponse(r=>r.url().endsWith('/decisions') && r.request().method()==='POST');
  await page.getByRole('button',{name:'Escalate',exact:true}).click();
  const ackResponse=await ackPromise;expect(ackResponse.ok()).toBe(true);
  const ack=await ackResponse.json();expect(ack.guidance_memory_id).toBeTruthy();
  await expect(page.getByText('Guidance saved for similar cases')).toBeVisible();
  state=await read(first);expect(state.reviewClosesAt).toBe(reviewDeadline);
  expect(state.payment.payment.state).toBe('funded');
  await page.screenshot({path:path.join(output,'saved.png'),fullPage:true});
  await page.reload();
  await page.getByRole('button',{name:'Escalated to a person: settle the dispute'}).click({timeout:20000});
  await expect(page.getByText('Guidance saved for similar cases')).toBeVisible();
  await page.getByRole('button',{name:'New request',exact:true}).click();
  const second=await deliver();
  await complain(followup);
  await expect(page.getByText('Prior reviewer guidance consulted',{exact:true})).toBeVisible({timeout:20000});
  await page.getByText('Prior reviewer guidance consulted',{exact:true}).click();
  await page.getByText('Current supporting citations',{exact:true}).click();
  const later=await read(second);
  const finding=later.events.findLast(e=>e.type==='verdict').verdict.finding;
  expect(finding.reviewer_guidance[0].memory_id).toBe(ack.guidance_memory_id);
  expect(finding.effective.result).toBe('FAIL');
  expect(later.payment.payment.state).toBe('funded');
  expect(errors).toEqual([]);
  await page.screenshot({path:path.join(output,'consulted.png'),fullPage:true});
  fs.writeFileSync(path.join(output,'evidence.json'),JSON.stringify({injected:true,realModelImprovementVerified:false,first:state,second:later,errors},null,2));
  console.log(JSON.stringify({first,second,output,injected:true,realModelImprovementVerified:false}));
 }finally{await context.tracing.stop({path:path.join(output,'trace.zip')});await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
