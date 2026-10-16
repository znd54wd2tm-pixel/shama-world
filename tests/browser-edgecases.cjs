const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.SHAMA_TEST_URL||'http://127.0.0.1:8765';
if(!/^http:\/\/(127\.0\.0\.1|localhost):/.test(base))throw Error('Use a local development server');
let browser;
(async()=>{
  browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--disable-gpu-sandbox','--use-angle=swiftshader']});
  const checks=[],errors=[];
  const check=(name,value)=>{assert.ok(value,name);checks.push(name);console.log('PASS',name);};
  async function openContext(width=390,height=844,fallback=false){
    const context=await browser.newContext({viewport:{width,height},isMobile:true,hasTouch:true});
    const page=await context.newPage();page.on('pageerror',(e)=>errors.push(e.message));
    await page.route('https://telegram.org/**',(r)=>r.fulfill({body:'',contentType:'application/javascript'}));
    await page.route('https://fonts.googleapis.com/**',(r)=>r.fulfill({body:'',contentType:'text/css'}));
    if(fallback)await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return /^webgl/.test(kind)?null:original.call(this,kind,...args);};});
    await page.goto(base,{waitUntil:'networkidle'});await page.waitForSelector('#app:not(.is-hidden)');
    return {context,page};
  }
  async function cases(page){await page.locator('.nav-item[data-nav="cases"]').click();await page.locator('[data-case-id]').first().click();await page.waitForSelector('#case-modal:not(.is-hidden)');}
  async function fast(page,value){if((await page.locator('#fast-open-toggle').getAttribute('aria-pressed'))!==String(value)){await page.locator('#fast-open-toggle').click();await page.waitForFunction((v)=>document.querySelector('#fast-open-toggle').getAttribute('aria-pressed')===String(v),value);}}
  {
    const {context,page}=await openContext(320,568);await cases(page);await fast(page,false);
    const hit=await page.evaluate(()=>['open-case-button','open-ten-cases-button'].every(id=>{const el=document.getElementById(id),r=el.getBoundingClientRect(),at=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return r.height>=44&&r.y>=0&&r.bottom<=innerHeight&&at&&el.contains(at);}));
    check('320 × 568: both opening buttons visible and unobstructed',hit);
    await page.screenshot({path:path.join(__dirname,'../.test-data/iphone-small.png')});
    await page.waitForSelector('#case-scene canvas');
    await page.evaluate(()=>document.querySelector('#case-scene canvas').getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
    await page.waitForFunction(()=>document.getElementById('case-scene').dataset.renderer==='fallback');
    check('WebGL context loss keeps controls and fallback artwork',await page.locator('#case-detail-image').isVisible());
    await context.close();
  }
  {
    const {context,page}=await openContext(412,915,true);await cases(page);await fast(page,false);
    await page.waitForFunction(()=>document.querySelector('#case-scene').dataset.renderer==='fallback');
    check('WebGL unavailable: image fallback is shown',await page.locator('#case-detail-image').isVisible());
    await page.locator('#open-case-button').click();await page.waitForSelector('#opening-result:not(.is-hidden)',{timeout:10000});
    check('WebGL unavailable: server opening still succeeds',await page.locator('#result-name').textContent());
    await context.close();
  }
  {
    const {context,page}=await openContext();await cases(page);await fast(page,true);
    const before=await page.evaluate(async()=> (await(await fetch('/api/me')).json()).cases_opened);
    await page.route('**/api/cases/*/open',async(route)=>{await route.fetch();await route.abort('failed');});
    await page.locator('#open-case-button').click();await page.waitForSelector('#opening-recovery:not(.is-hidden)');
    const stored=await page.evaluate(()=>JSON.parse(localStorage.getItem(Object.keys(localStorage).find(key=>key.startsWith('shama:pending-opening:')))));
    check('Lost response keeps a durable retry key',stored&&stored.requestId);
    await page.unroute('**/api/cases/*/open');await page.reload({waitUntil:'networkidle'});
    await page.locator('.nav-item[data-nav="cases"]').click();await page.locator('#restore-opening-button').click();
    await page.waitForSelector('#opening-result:not(.is-hidden)');
    const after=await page.evaluate(async()=> (await(await fetch('/api/me')).json()).cases_opened);
    check('Lost response recovered without a second opening',after===before+1);
    await context.close();
  }
  {
    const {context,page}=await openContext();await cases(page);await fast(page,false);
    await page.route('**/api/cases/*/open-ten',async(route)=>{const response=await route.fetch();await new Promise(r=>setTimeout(r,800));await route.fulfill({response});});
    await page.locator('#open-ten-cases-button').click();
    check('Slow server: buttons disabled and animation waits',await page.locator('#open-case-button').isDisabled()&&await page.locator('#opening-modal').isHidden());
    await page.waitForFunction(()=>document.getElementById('opening-sequence').textContent==='2 / 10',{timeout:12000});
    check('Ordinary ten: first stop finishes before next 3D opening',await page.locator('#opening-3d canvas').count()===1);
    await page.locator('#opening-skip').click();await page.waitForSelector('#opening-result:not(.is-hidden)');
    check('Skip reveals all ten saved results',await page.locator('.result-mini').count()===10);
    await context.close();
  }
  {
    const {context,page}=await openContext();await page.locator('.nav-item[data-nav="cases"]').click();
    const id=await page.evaluate(async()=> (await(await fetch('/api/cases')).json()).cases.find(c=>c.kind==='BUSINESS'&&c.price===20000).id);
    await page.locator(`[data-case-id="${id}"]`).click();await fast(page,true);
    await page.locator('#open-ten-cases-button').click();await page.waitForSelector('#opening-result:not(.is-hidden)');
    check('Business ten renders ten separate results',await page.locator('.result-mini').count()===10);
    check('Business rewards lead to real enterprises',await page.locator('#result-business-button').isVisible());
    await page.locator('#result-business-button').click();await page.waitForSelector('.business-card');
    check('Awarded enterprises appear in owned section',await page.locator('.business-card').count()>0);
    await context.close();
  }
  check('No unhandled browser errors in edge cases',errors.length===0);
  fs.writeFileSync(path.join(__dirname,'../.test-data/browser-edgechecks.json'),JSON.stringify({checks,errors},null,2));
  await browser.close();
})().catch(async(error)=>{console.error(error);await browser?.close();process.exitCode=1;});
