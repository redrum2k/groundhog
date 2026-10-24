const { chromium, expect } = require('@playwright/test');
const fs=require('node:fs'),path=require('node:path');
const origin='http://127.0.0.1:3107';
const retained=JSON.parse(fs.readFileSync('artifacts/v6-reviewer-browser/failure.json','utf8'));
const prior=JSON.parse(fs.readFileSync('artifacts/v6-model-browser-c/report.json','utf8'));
const output=path.resolve('artifacts/v6-reviewer-resume');fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});let latest;const posts=[],errors=[],failures=[];
 try{
  await expect.poll(async()=>{try{return(await fetch(`${origin}/api/catalog/corpora`)).status;}catch{return 0;}},{timeout:30000}).toBe(200);
  const page=await browser.newPage({viewport:{width:1600,height:1100}});page.setDefaultTimeout(20000);
  await page.addInitScript(id=>localStorage.setItem('objection.catalog.run',id),retained.latest.run_id);
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts.push({url:r.url(),body:r.postDataJSON()});});
  page.on('response',async r=>{if(r.status()>=400)failures.push({url:r.url(),status:r.status()});if(r.url().includes('/events?')){const b=await r.json().catch(()=>null);if(b?.events?.length)latest=b.events.at(-1);}});
  const oldBefore=await(await page.request.get(`${origin}/api/catalog/runs/${prior.new_order}/events?after=0`)).json();
  await page.goto(origin,{waitUntil:'networkidle'});await page.getByRole('button',{name:'Catalog live',exact:true}).click();
  await expect.poll(()=>latest?.order.order_state).toBe('human_review');
  if(latest.run_id!==retained.latest.run_id||latest.order.ledger.length)throw new Error('Not the retained held order');
  const held=latest;await page.getByRole('button',{name:/Owned human review/}).click();
  await page.getByLabel('Reviewer action').selectOption('release_authorization');
  await page.getByLabel('Reviewer reason').fill('Two readable uploads remain unregistered. Release uncaptured mock authorization; preserve UNKNOWN and original accepted terms.');
  await expect(page.getByRole('button',{name:'Record bound reviewer decision',exact:true})).toBeEnabled();
  await page.screenshot({path:path.join(output,'01-cited-owned-hold.png'),fullPage:true});
  await page.getByRole('button',{name:'Record bound reviewer decision',exact:true}).click();
  await expect.poll(()=>latest?.payment?.payment.state).toBe('voided');
  if(latest.order.ledger.length!==1||latest.order.ledger[0].kind!=='release'||latest.accepted_snapshot_sha256!==held.accepted_snapshot_sha256)throw new Error('Wrong release or snapshot rewrite');
  if(latest.order.decisions.at(-1).actor!=='reviewer:local-trusted')throw new Error('Wrong reviewer authority');
  const oldAfter=await(await page.request.get(`${origin}/api/catalog/runs/${prior.new_order}/events?after=0`)).json();
  if(JSON.stringify(oldBefore.events)!==JSON.stringify(oldAfter.events))throw new Error('Prior accepted/captured order changed');
  const count=posts.length;await page.getByRole('button',{name:'Read-only replay',exact:true}).click();await page.getByRole('button',{name:'Overview',exact:true}).click();await page.reload({waitUntil:'networkidle'});
  if(posts.length!==count||posts.length!==1)throw new Error('Resume/replay created extra commands');
  await page.screenshot({path:path.join(output,'02-voided-not-refunded.png'),fullPage:true});
  if(errors.length||failures.length)throw new Error('Browser error');
  const report={mode:'live_backend / retained actual order / synthetic trusted reviewer / mock release',retained_failure:'v6-reviewer-browser/failure.json',held,final:latest,old_accepted_order_unchanged:true,new_draft_used_base:held.procedure_version==='catalog-static-v1',posts,errors,failures,replay_mutations:0};
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({order:latest.run_id,state:latest.order.order_state,payment:latest.payment.payment.state,release_count:latest.order.ledger.length,old_accepted_order_unchanged:true,posts:posts.length,errors,failures}));
 }catch(error){fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:String(error),latest,posts,errors,failures},null,2));throw error;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
