/* Integration test for the explicit localhost dev fixture; never production. */
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.SHAMA_TEST_URL||'http://127.0.0.1:8766';
if(!/^http:\/\/(localhost|127\.0\.0\.1):/.test(base))throw Error('Local fixture required');
let browser;
(async()=>{
 browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--use-angle=swiftshader','--disable-gpu-sandbox']});
 const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:1});
 const page=await context.newPage(),errors=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.url().startsWith(base)&&r.status()>=500)errors.push(`${r.status()} ${r.url()}`);});
 await page.route('https://telegram.org/**',r=>r.fulfill({body:'',contentType:'application/javascript'}));
 await page.route('https://fonts.googleapis.com/**',r=>r.fulfill({body:'',contentType:'text/css'}));
 const check=(name,value)=>{assert.ok(value,name);checks.push(name);console.log('PASS',name);};
 await page.goto(base,{waitUntil:'networkidle'});await page.waitForSelector('#app:not(.is-hidden)');
 await page.waitForSelector('.world-wallet');
 check('World displays actual balance and XP',await page.locator('.world-wallet progress').count()===1);
 for(const viewport of [{width:375,height:812},{width:390,height:844},{width:430,height:932}]){
   await page.setViewportSize(viewport);
   for(const tab of ['world','cases','earn','inventory','upgrade','market','profile']){
     await page.locator(`.nav-item[data-nav="${tab}"]`).click();
     await page.waitForTimeout(180);
     check(`${viewport.width}: ${tab} tab and no overflow`,await page.locator(`#page-${tab}`).evaluate(el=>el.classList.contains('is-active'))&&await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   }
   await page.locator('.nav-item[data-nav="cases"]').click();
   await page.screenshot({path:path.join(__dirname,`../.test-data/cases-${viewport.width}.png`)});
 }
 check('Five approved covers',await page.locator('.case-card img').evaluateAll(imgs=>imgs.length===5&&imgs.every(i=>i.src.includes('user-')&&i.complete&&i.naturalWidth===1280)));
 await page.locator('[data-case-id]').first().click();await page.waitForSelector('#case-modal:not(.is-hidden)');
 await page.waitForFunction(()=>document.querySelector('#case-scene canvas'));
 check('Original cover is visible alongside the 3D preview',await page.locator('#case-cover-thumbnail').isVisible());
 const original=(await (await context.request.get(base+'/api/inventory')).json()).items.find(i=>i.asset_key==='football');
 check('Case preview uses the canonical item image',await page.locator('#case-drop-preview img').evaluateAll((imgs,expected)=>imgs.some(i=>new URL(i.src).pathname===expected),original.image));
 if(await page.locator('#fast-open-toggle').getAttribute('aria-pressed')==='true')await page.locator('#fast-open-toggle').click();
 await page.locator('#open-ten-cases-button').click();await page.waitForSelector('.independent-reel-wrap');
 check('Ten independent reels are mounted together',await page.locator('.independent-reel-wrap').count()===10);
 check('Ten distinct server result IDs',new Set(await page.locator('.independent-reel-wrap').evaluateAll(els=>els.map(n=>n.dataset.resultId))).size===10);
 await page.screenshot({path:path.join(__dirname,'../.test-data/ten-reels.png')});
 await page.waitForSelector('#opening-result:not(.is-hidden)');check('Ten results match tracks',await page.locator('.result-mini').count()===10);
 await page.locator('#saved-button').click();await page.locator('#opening-modal').waitFor({state:'hidden'});
 await page.locator('[data-case-id]').first().click();await page.locator('#fast-open-toggle').click();
 await page.waitForFunction(()=>document.querySelector('#fast-open-toggle').getAttribute('aria-pressed')==='true');
 check('Fast mode retains WebGL preview',await page.locator('#case-scene canvas').count()===1);
 await page.locator('#open-case-button').click();await page.waitForSelector('#opening-3d canvas');
 check('Fast opening retains actual 3D scene',await page.locator('#opening-3d canvas').count()===1);
 await page.waitForSelector('#opening-result:not(.is-hidden)');
 const before=await (await context.request.get(base+'/api/me')).json();
 await page.reload({waitUntil:'networkidle'});await page.waitForSelector('#opening-result:not(.is-hidden)');
 const after=await (await context.request.get(base+'/api/me')).json();check('Restart restores reward without second charge',before.cases_opened===after.cases_opened&&before.balance===after.balance);
 await page.locator('#saved-button').click();await page.locator('#opening-modal').waitFor({state:'hidden'});
 await page.locator('.nav-item[data-nav="inventory"]').click();
 const inventoryCard=page.locator(`#inventory-grid [data-item-id="${original.id}"]`);await inventoryCard.waitFor();
 check('Inventory uses the same item image',await inventoryCard.locator('img').evaluate((i,expected)=>new URL(i.src).pathname===expected,original.image));
 await inventoryCard.click();await page.waitForSelector('#item-modal:not(.is-hidden)');
 check('Item details use the same image',await page.locator('#item-detail-image').evaluate((i,expected)=>new URL(i.src).pathname===expected,original.image));
 await page.locator('[data-close-modal="item-modal"]').click();
 await page.locator('.nav-item[data-nav="upgrade"]').click();
 await page.locator(`[data-upgrade-item-id="${original.id}"]`).click();
 check('Upgrade source uses the same item image',await page.locator('#upgrade-source-card img').evaluate((i,expected)=>new URL(i.src).pathname===expected,original.image));
 await page.locator('.nav-item[data-nav="market"]').click();await page.locator('#list-inventory-form').waitFor({state:'attached'});
 await page.locator('.market-sell-form summary').click();
 await page.locator('#list-inventory-form [name="item"]').selectOption(String(original.id));
 await page.locator('#list-inventory-form [name="price"]').fill('100');await page.locator('#list-inventory-form button').click();
 const listed=page.locator('.player-listing').filter({hasText:original.name});await listed.waitFor();
 check('Player market uses the same item image',await listed.locator('img').evaluate((i,expected)=>new URL(i.src).pathname===expected,original.image));
 await listed.locator('[data-listing-action="cancel"]').click();await listed.waitFor({state:'detached'});
 check('Item listing can be cancelled and returned',true);
 await page.locator('.nav-item[data-nav="earn"]').click();
 const businesses=await (await context.request.get(base+'/api/businesses')).json();
 let coffee=businesses.enterprises.find(e=>e.code==='coffee');
 if(!coffee){const type=businesses.catalog.find(c=>c.code==='coffee');const r=await context.request.post(`${base}/api/businesses/${type.id}/buy`,{data:{},headers:{'X-Game-Request-Id':'browser-coffee'}});assert.equal(r.status(),200);coffee=(await r.json()).enterprise;await page.locator('.nav-item[data-nav="world"]').click();await page.locator('.nav-item[data-nav="earn"]').click();}
 const card=page.locator(`[data-enterprise-card="${coffee.id}"]`);await card.waitFor();
 await card.locator(`details[data-menu-key="${coffee.id}:management"]>summary`).click();
 for(const direction of ['equipment','premises','marketing','automation']){
   const menu=card.locator(`details[data-menu-key="${coffee.id}:${direction}"]`);await menu.locator('summary').click();
   const purchase=menu.locator('[data-business-action="upgrade"]').first();
   if(!await purchase.isDisabled()){
     await purchase.scrollIntoViewIfNeeded();const y=await page.evaluate(()=>scrollY);await purchase.click();
     await page.waitForFunction(({id,key})=>document.querySelector(`[data-enterprise-card="${id}"] [data-menu-key="${id}:${key}"] strong`)===null&&document.querySelector(`[data-menu-key="${id}:${key}"] summary`).textContent.includes('1/3'),{id:coffee.id,key:direction});
     check(`${direction} keeps section, menu and scroll`,await menu.getAttribute('open')!==null&&await page.locator('#page-earn').evaluate(n=>n.classList.contains('is-active'))&&Math.abs(await page.evaluate(()=>scrollY)-y)<70);
   }
 }
 await card.locator(`details[data-menu-key="${coffee.id}:staff"]>summary`).click();await card.locator('[data-business-action="hire"]').first().click();
 await page.waitForFunction(id=>document.querySelector(`[data-enterprise-card="${id}"] .employee-list`).textContent.includes('Сотрудник'),coffee.id);
 check('Hiring keeps management expanded',await card.locator(`details[data-menu-key="${coffee.id}:management"]`).getAttribute('open')!==null);
 await page.screenshot({path:path.join(__dirname,'../.test-data/business-management.png')});
 await page.locator('#page-earn [data-open-finance]').first().click();await page.waitForSelector('.finance-capital');
 check('Bank dialog is above navigation',await page.locator('#finance-close').evaluate(el=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}));
 for(const sub of ['deposits','market','loans','more','home']){await page.locator(`#finance-nav [data-finance-page="${sub}"]`).click();check(`Bank ${sub} tab`,await page.locator('#finance-content').textContent()!=='');}
 await page.locator('#finance-nav [data-finance-page="deposits"]').click();await page.locator('[data-finance-form="deposit"] button').click();await page.waitForSelector('[data-finance-action="close-deposit"]');
 check('Deposit creates real server record',(await (await context.request.get(base+'/api/finance')).json()).deposits.length>0);
 await page.screenshot({path:path.join(__dirname,'../.test-data/bank-deposits.png')});
 await page.locator('#finance-nav [data-finance-page="market"]').click();
 const stock=page.locator('[data-finance-form="stock"]').first();
 const company=await stock.locator('[name="company"]').inputValue();
 const stockBefore=(await (await context.request.get(base+'/api/finance')).json()).companies.find(c=>c.code===company).holding;
 await stock.locator('button').click();
 await page.waitForFunction(async ({base,company,expected})=>{const s=await (await fetch(base+'/api/finance')).json();return s.companies.find(c=>c.code===company).holding===expected;},{base,company,expected:stockBefore+1});
 check('Stock purchase changes actual server ownership',true);
 await page.waitForTimeout(250);
 await page.locator('[data-finance-form="stock"]').first().locator('[name="side"]').selectOption('sell');
 await page.locator('[data-finance-form="stock"]').first().locator('button').click();
 await page.waitForFunction(async ({base,company,expected})=>{const s=await (await fetch(base+'/api/finance')).json();return s.companies.find(c=>c.code===company).holding===expected;},{base,company,expected:stockBefore});
 check('Stock sale changes actual server ownership',true);
 await page.locator('#finance-close').click();
 check('Modal releases page scrolling',!await page.locator('body').evaluate(n=>n.classList.contains('finance-open')));
 await page.locator('#page-earn [data-open-finance]').first().click();await page.waitForSelector('.finance-panel');await page.keyboard.press('Escape');
 check('Escape closes bank and releases scroll',await page.locator('#finance-modal').evaluate(n=>n.classList.contains('is-hidden'))&&!await page.locator('body').evaluate(n=>n.classList.contains('finance-open')));
 check('No JavaScript or server failures',errors.length===0);
 fs.writeFileSync(path.join(__dirname,'../.test-data/browser-v16.json'),JSON.stringify({checks,errors},null,2));
 await browser.close();console.log(`TOTAL ${checks.length} checks passed`);
})().catch(async e=>{console.error(e);if(browser)await browser.close();process.exitCode=1;});
