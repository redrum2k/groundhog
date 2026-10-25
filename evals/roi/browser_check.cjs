// Local report QA only. Never connects to an application backend or alters order data.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {pathToFileURL}=require('node:url');
const {chromium,expect}=require(path.resolve(__dirname,'../../frontend/node_modules/@playwright/test'));
const directory=path.resolve(process.argv[2]||'');
const reportName=process.argv[3]||'report.html',stem=path.parse(reportName).name;
if(path.basename(reportName)!==reportName)throw Error('Report must be a local filename');
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
(async()=>{
 const files=['results.json','work-ledger.json','inputs.json','capsule.json','quality.json'];
 const before=Object.fromEntries(files.map(f=>[f,sha(path.join(directory,f))]));
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'msedge'});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],network=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(/^https?:/.test(r.url())||r.method()!=='GET')network.push({method:r.method(),url:r.url()});});
 try{
  await page.goto(pathToFileURL(path.join(directory,reportName)).href);
  await expect(page.getByRole('heading',{name:/What does knowledge/})).toBeVisible();
  await expect(page.locator('#quality-score')).toHaveText('60 / 60');
  await expect(page.locator('#seal-value')).toHaveText('39s');
  await expect(page.getByText('Unavailable',{exact:true})).toBeVisible();
  await page.screenshot({path:path.join(directory,stem+'-desktop.png'),fullPage:true});
  await page.screenshot({path:path.join(directory,stem+'-desktop-top.png')});
  const parity=JSON.parse(fs.readFileSync(path.join(directory,'calculator-parity.json'),'utf8'));
  for(const test of parity){
   await page.locator('#baseline').selectOption(test.baseline);
   await page.locator(`[data-profile="${test.profile}"]`).click();
   await page.locator('#realization').fill(String(test.realization*100));
   const state=await page.evaluate(()=>window.roiView);
   for(const [js,py] of [['capacity','capacity_hours'],['cost','incremental_cost'],['net','net_capacity_value'],['cash','conditional_cash_impact'],['breakEven','break_even_seconds']]){
    if(Math.abs(state.economics[js]-test.expected[py])>1e-7)throw Error(`Calculator parity mismatch ${js}: ${JSON.stringify(test)}`);
   }
  }
  await page.locator('#realization').fill('0');
  await expect(page.locator('#cash-break-even')).toContainText('No cash break-even');
  await page.locator('#time-scale').fill('0');
  await expect(page.locator('#unit-economics')).toContainText('No volume break-even');
  await page.locator('#time-scale').fill('100');
  await page.locator('#governance').fill('300');
  const negative=await page.evaluate(()=>window.roiView.economics);
  if(negative.cash!==negative.negative-negative.cost)throw Error('Negative labor was discounted at zero realization');
  await page.locator('#setup').fill('0');
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.locator('#annual-value')).toHaveText('Check inputs');
  await page.locator('#reset').click();
  await expect(page.locator('#seal-value')).toHaveText('39s');
  await page.locator('#trace-filter').selectOption('exception');
  if(await page.locator('#trace-table tbody tr').count()!==8)throw Error('Held cases disappeared');
  await page.locator('#trace-filter').selectOption('all');
  if(await page.locator('#trace-table tbody tr').count()!==60)throw Error('Wrong scheduled denominator');
  const traceLinks=await page.locator('#trace-table tbody a').evaluateAll(els=>els.map(e=>e.getAttribute('href')));
  if(!traceLinks.every(link=>fs.existsSync(path.join(directory,link))))throw Error('Trace link has no original record');
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:path.join(directory,stem+'-mobile.png'),fullPage:true});
  await page.screenshot({path:path.join(directory,stem+'-mobile-top.png')});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth))throw Error('Mobile horizontal page overflow');
  for(const file of files)if(before[file]!==sha(path.join(directory,file)))throw Error('Dashboard changed observed evidence');
  if(errors.length||network.length)throw Error(JSON.stringify({errors,network}));
  const result={status:'PASS',calculator_comparisons:parity.length,observed_data_unchanged:true,network_requests:network,errors,viewports:['1440x1000','390x844'],held_cases_visible:8,total_cases_visible:60};
  fs.writeFileSync(path.join(directory,stem+'-browser-check.json'),JSON.stringify(result,null,2),{flag:'wx'});
  console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
