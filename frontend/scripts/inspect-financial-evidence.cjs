// Read-only primary UI verification against a real persisted order, never playback state.
const {chromium, expect} = require('@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');
async function main() {
  const [run, destination] = process.argv.slice(2);
  const origin = process.env.ACCEPTANCE_ORIGIN || 'http://127.0.0.1:3053';
  if (!run || !destination || !['127.0.0.1','localhost'].includes(new URL(origin).hostname))
    throw new Error('Usage: inspect-financial-evidence.cjs ACTUAL_RUN_ID PROJECT_LOCAL_OUTPUT');
  const output = path.resolve(destination), local = path.resolve(__dirname,'../../.local');
  if (!output.startsWith(local + path.sep)) throw new Error('Evidence must stay in this checkout .local');
  await fs.mkdir(output,{recursive:true});
  const browser = await chromium.launch({headless:true,channel:'msedge'});
  const context = await browser.newContext({viewport:{width:1550,height:1050},reducedMotion:'reduce'});
  await context.tracing.start({screenshots:true,snapshots:true});
  // Select a real saved run using the application's existing reload mechanism.
  // No events, model answers, source procedures or backend state are injected.
  await context.addInitScript(id=>localStorage.setItem('datumco.live-run.v1',JSON.stringify({id})),run);
  const page = await context.newPage(), errors=[], mutations=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST')mutations.push(r.url());});
  const observed={run,origin,errors,mutations};
  try {
    await page.goto(origin+'/live',{waitUntil:'networkidle'});
    await expect(page.getByText('Live backend · mock payments',{exact:true})).toBeVisible();
    observed.customer = await page.locator('body').innerText();
    await page.screenshot({path:path.join(output,'customer.png'),fullPage:true,animations:'disabled'});
    await page.getByRole('button',{name:'Run',exact:true}).click();
    const finding = page.getByRole('button',{name:/^Finding,/});
    if(await finding.count()) await finding.click();
    else await page.getByRole('button',{name:'Funding',exact:true}).click();
    await page.locator('.panel-b').evaluate(el=>{el.scrollTop=0;});
    await page.screenshot({path:path.join(output,'finding.png'),fullPage:true,animations:'disabled'});
    await page.getByText('Why may money move?',{exact:true}).click();
    const result = page.waitForResponse(r=>r.url().endsWith('/payment-justification') && r.status()===200);
    await page.getByRole('button',{name:'Inspect financial evidence',exact:true}).click();
    observed.justification = await (await result).json();
    await expect(page.getByText(/Observed revision/)).toBeVisible();
    const j=observed.justification;
    if(j.agreement.quote.request_id!==run) throw new Error('Customer and operator order differ');
    await expect(page.locator('.panel')).toContainText('$'+j.exact_price);
    for(const c of j.cases) await expect(page.locator('.panel')).toContainText(c.complaint.text);
    for(const b of j.blockers) await expect(page.locator('.panel')).toContainText(b);
    observed.panel=await page.locator('.panel').innerText();
    await page.getByText(/Observed revision/).scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,'financial-evidence.png'),fullPage:true,animations:'disabled'});
    await page.getByRole('button',{name:'Close panel',exact:true}).click();
    await page.getByRole('button',{name:/^(Source learning|Learning active)/}).click();
    const learning=page.getByRole('region',{name:'Persistent source learning'});
    await expect(learning).toBeVisible();
    observed.learning=await learning.innerText();
    await page.screenshot({path:path.join(output,'learning.png'),fullPage:true,animations:'disabled'});
    await page.reload({waitUntil:'networkidle'});
    observed.reloaded=await page.locator('body').innerText();
    if(errors.length || mutations.length)throw new Error(JSON.stringify({errors,mutations}));
    await fs.writeFile(path.join(output,'observed.json'),JSON.stringify(observed,null,2));
    console.log(JSON.stringify({output,run,order:j.order_id,state:j.state,errors,mutations}));
  } catch(e) {
    await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});
    await fs.writeFile(path.join(output,'failure.json'),JSON.stringify({...observed,error:String(e)},null,2));
    throw e;
  } finally {
    await context.tracing.stop({path:path.join(output,'trace.zip')});
    await browser.close();
  }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
