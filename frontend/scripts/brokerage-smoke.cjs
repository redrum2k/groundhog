// Real production frontend -> same-origin Next bridge -> local backend. Mock only.
const {chromium,expect}=require('@playwright/test');
const fs=require('node:fs'); const path=require('node:path');
const origin=process.env.BROKER_SMOKE_ORIGIN || 'http://127.0.0.1:3016';
if (!['127.0.0.1','localhost'].includes(new URL(origin).hostname)) throw new Error('Trusted local demo only');
const output=path.resolve(process.env.BROKER_SMOKE_OUTPUT || 'artifacts/broker-browser');
const ending=process.env.BROKER_SMOKE_ENDING || 'captured';
if(!['captured','held'].includes(ending))throw new Error('Unsupported smoke ending');
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL});
 const context=await browser.newContext({viewport:{width:1440,height:900}});
 // The isolated mock journey connects a synthetic buyer; it cannot sign or send transactions.
 const buyer='0x'+'4'.repeat(40);
 await context.addInitScript(address=>{
  window.ethereum={request:async({method})=>{
   if(method==='eth_requestAccounts' || method==='eth_accounts') return [address];
   if(method==='eth_chainId') return '0x14a34';
   throw new Error('Mock smoke refuses wallet signing and transactions');
  }};
 },buyer);
 await context.tracing.start({screenshots:true,snapshots:true});
 const page=await context.newPage(); const errors=[]; let latest;
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',async response=>{if(response.ok() && /\/runs\/[^/]+\/events/.test(response.url())) latest=await response.json();});
 try {
  await page.goto(new URL('/', origin).href);
  await page.getByRole('button',{name:/^Summit Fitness/}).click();
  await page.getByRole('button',{name:'Connect MetaMask',exact:true}).click();
  await expect(page.getByText(buyer,{exact:true})).toBeVisible();
  await page.screenshot({path:path.join(output,'wallet-settings.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(output,'wallet-settings-mobile.png'),fullPage:true});
  await page.getByRole('button',{name:'Close wallet settings',exact:true}).click();
  await expect(page.getByRole('button',{name:/^Summit Fitness/})).toBeVisible();
  await page.setViewportSize({width:1440,height:900});
  await page.getByLabel('Dataset request').fill('SF adults 25–34, gym members or fitness-app users, grouped by ZIP.');
  await page.getByRole('button',{name:'Create request',exact:true}).click();
  await expect(page.getByRole('button',{name:'Prepare quote',exact:true})).toBeVisible({timeout:20000});
  await page.getByRole('button',{name:'Prepare quote',exact:true}).click();
  await expect(page.getByRole('button',{name:'Accept & simulate $1.00',exact:true})).toBeVisible();
  if(latest.quote.payment_terms.mode !== 'mock') throw new Error('Smoke refuses live payment mode');
  if(latest.quote.payment_terms.payment_info.payer !== buyer) throw new Error('Saved buyer missing from quote');
  if(latest.quote.payment_terms.amount_atomic !== '1000000') throw new Error('Quote is not exactly 1 test USDC');
  await expect(page.getByLabel('Buyer wallet address (optional in mock mode)')).toHaveCount(0);
  await page.screenshot({path:path.join(output,'quote.png'),fullPage:true});
  await page.getByRole('button',{name:'Accept & simulate $1.00',exact:true}).click();
  await expect(page.getByRole('main',{name:'Run view'})).toBeVisible();
  await page.screenshot({path:path.join(output,'agent-working.png'),fullPage:true});
  await page.getByRole('button',{name:'Customer view',exact:true}).click();
  await expect(page.getByRole('link',{name:'Download CSV',exact:true})).toBeVisible({timeout:20000});
  await expect(page.getByRole('cell',{name:'94110',exact:true})).toBeVisible();
  await expect(page.locator('tr').filter({hasText:'94129'})).toContainText('suppressed');
  await page.screenshot({path:path.join(output,'delivery.png'),fullPage:true});
  const run=latest.request.request_id;
  await expect(page.getByRole('button',{name:'Admin review',exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'Run',exact:true}).click();
  await expect(page.getByRole('button',{name:'Admin review',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'approve',exact:true})).toHaveCount(0);
  await page.screenshot({path:path.join(output,'run.png'),fullPage:true});
  if(latest.request.request_id!==run) throw new Error('Run view changed the run');
  await page.getByRole('button',{name:'Customer view',exact:true}).click();
  await expect(page.getByRole('link',{name:'Download CSV',exact:true})).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button',{name:/^Summit Fitness/})).toContainText('0x4444');
  await expect(page.getByRole('link',{name:'Download CSV',exact:true})).toBeVisible();
  if(latest.request.request_id!==run) throw new Error('Reload created another run');
  const csv=await (await context.request.get(new URL(await page.getByRole('link',{name:'Download CSV',exact:true}).getAttribute('href'),origin).href)).body();
  fs.writeFileSync(path.join(output,'delivery.csv'),csv);
  if(ending==='held') {
   await page.getByRole('button',{name:'Object',exact:true}).click();
   await page.getByLabel('Your complaint',{exact:true}).fill('Do these aggregates prove each membership is still paid today?');
   await page.getByRole('button',{name:'Send complaint',exact:true}).click();
   await expect.poll(()=>latest?.evidence_request ?? null,{timeout:20000}).not.toBeNull();
   await page.getByRole('button',{name:'Customer view',exact:true}).click();
   await expect(page.getByRole('button',{name:'Accept verified delivery',exact:true})).toHaveCount(0);
   if(latest.payment.payment.state!=='funded')throw new Error('Unresolved complaint did not retain held funding');
   const proof=await (await context.request.get(`${origin}/api/live/orders/${latest.binding.orderId}/payment-justification`)).json();
   if(proof.capture_eligible_now || proof.bookings.length || !proof.blockers.some(b=>b.includes('unresolved dispute')))throw new Error('No inspectable unresolved-payment hold');
   fs.writeFileSync(path.join(output,'held-payment-justification.json'),JSON.stringify(proof,null,2));
  } else {
   await page.getByRole('button',{name:'Accept verified delivery',exact:true}).click();
   await expect(page.getByRole('main',{name:'Run view'})).toBeVisible();
   await expect.poll(()=>latest?.payment?.payment.state,{timeout:20000}).toBe('captured');
  }
  if(errors.length)throw new Error(errors.join('\n'));
  if(latest.payment.explorer_links.length) throw new Error('Mock explorer link');
  const events=await (await context.request.get(`${origin}/api/live/runs/${run}/events`)).json();
  fs.writeFileSync(path.join(output,'events-payment.json'),JSON.stringify(events,null,2));
  await page.screenshot({path:path.join(output,ending+'.png'),fullPage:true});
  if(process.env.BROKER_SMOKE_EXTRA==='oakland' && ending==='captured') {
   await page.getByRole('button',{name:'Customer view',exact:true}).click();
   await page.getByText('Request additional work',{exact:true}).click();
   await page.getByRole('button',{name:'Request provider oakland offer',exact:true}).click();
   await expect(page.getByText('Separate offer: $0.50.',{exact:true})).toBeVisible();
   await page.getByRole('button',{name:'Review separate offer',exact:true}).click();
   await expect(page.getByRole('button',{name:'Accept & simulate $0.50',exact:true})).toBeVisible();
   if(latest.quote.amount.amount_minor!==50 || latest.quote.payment_terms.amount_atomic!=='500000')throw new Error('Fractional quote changed authorization amount');
   await page.screenshot({path:path.join(output,'fractional-quote.png'),fullPage:true});
   await page.getByRole('button',{name:'Accept & simulate $0.50',exact:true}).click();
   await expect(page.getByRole('main',{name:'Run view'})).toBeVisible();
   await page.getByRole('button',{name:'Customer view',exact:true}).click();
   await expect(page.getByRole('button',{name:'Accept verified delivery',exact:true})).toBeVisible({timeout:20000});
   await page.getByRole('button',{name:'Accept verified delivery',exact:true}).click();
   await expect.poll(()=>latest?.payment?.payment.state,{timeout:20000}).toBe('captured');
   const proof=await (await context.request.get(`${origin}/api/live/orders/${latest.binding.orderId}/payment-justification`)).json();
   if(proof.exact_price!=='0.50' || proof.amount_atomic!=='500000' || proof.bookings.length!==1 || proof.bookings[0].amount.amount_minor!==50)throw new Error('Fractional booking differs');
   fs.writeFileSync(path.join(output,'fractional-payment-justification.json'),JSON.stringify(proof,null,2));
   await page.screenshot({path:path.join(output,'fractional-captured.png'),fullPage:true});
  }
  console.log(JSON.stringify({run,output,browser:await browser.version(),mock:true,ending,extra:process.env.BROKER_SMOKE_EXTRA || null,errors}));
 } catch(error) {
  fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:String(error),latest,errors},null,2));
  await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});
  throw error;
 } finally {await context.tracing.stop({path:path.join(output,'trace.zip')});await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
