const {chromium,expect}=require('@playwright/test');const fs=require('node:fs'),path=require('node:path');
const origin='http://127.0.0.1:3107',output=path.resolve('artifacts/v6-final-readonly-browser');fs.mkdirSync(output,{recursive:true});
const cases=[
 {id:JSON.parse(fs.readFileSync('artifacts/v6-model-browser-c/report.json','utf8')).new_order,payment:'captured',name:'adapted'},
 {id:JSON.parse(fs.readFileSync('artifacts/v6-reviewer-resume/report.json','utf8')).final.run_id,payment:'voided',name:'reviewed'},
 {id:JSON.parse(fs.readFileSync('artifacts/v6-failure-browser/report.json','utf8')).order_id,payment:'captured',name:'corrected'},
];
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true}),posts=[],errors=[],results=[];
try{
 await expect.poll(async()=>{try{return(await fetch(`${origin}/api/catalog/corpora`)).status;}catch{return 0;}},{timeout:30000}).toBe(200);
 for(const item of cases){let latest;const page=await browser.newPage({viewport:{width:1600,height:1100}});
  await page.addInitScript(id=>localStorage.setItem('objection.catalog.run',id),item.id);
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts.push(r.url());});
  page.on('response',async r=>{if(r.status()>=400)errors.push(`${r.status()} ${r.url()}`);if(r.url().includes('/events?')){const b=await r.json().catch(()=>null);if(b?.events?.length)latest=b.events.at(-1);}});
  await page.goto(origin,{waitUntil:'networkidle'});await page.getByRole('button',{name:'Catalog live',exact:true}).click();
  await expect.poll(()=>latest?.payment?.payment.state).toBe(item.payment);
  if(item.payment==='voided')await expect(page.getByRole('button',{name:'Produce & verify, idle',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Overview',exact:true}).click();await page.getByRole('button',{name:'Read-only replay',exact:true}).click();
  await page.screenshot({path:path.join(output,`${item.name}-readonly.png`),fullPage:true});
  results.push({order_id:item.id,payment:latest.payment.payment.state,order_state:latest.order.order_state,accepted_hash:latest.accepted_snapshot_sha256,procedure:latest.procedure_version});await page.close();
 }
 if(posts.length||errors.length)throw new Error('Read-only boundary or browser error');
 fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({results,posts,errors,mutation_requests:0,mode:'live backend / final UI build / read-only existing evidence'},null,2));console.log(JSON.stringify({results,mutation_requests:0,errors}));
}catch(error){fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:String(error),results,posts,errors},null,2));throw error;}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
