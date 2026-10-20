/* Enterprise management preserves the focused card, open menus and scroll. */
(function(){
 'use strict';
 const root=document.getElementById('businesses-root'),marketRoot=document.getElementById('player-market-root');
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const money=window.shamaMoney,rarity=window.shamaRarity;
 let businesses=null,market=null,inventory=[],userId=0,businessLoad=null,marketLoad=null;
 const pending=new Set();
 const api=(path,method='GET',data,key)=>window.api.request(path,{method,headers:{...(data?{'Content-Type':'application/json'}:{}),...(key?{'X-Game-Request-Id':key}:{})},...(data?{body:JSON.stringify(data)}:{})});
 const notify=s=>window.shamaToast?.(s);
 const balance=n=>{if(Number.isFinite(n))window.dispatchEvent(new CustomEvent('shama:balance',{detail:n}));};
 function durable(path,data){
   const storage=`shama:action:${userId}:${path}:${JSON.stringify(data)}`;let id;
   try{id=localStorage.getItem(storage);}catch(_){}
   if(!id){id=crypto.randomUUID();try{localStorage.setItem(storage,id);}catch(_){}}
   return {id,clear(){try{localStorage.removeItem(storage);}catch(_){}}};
 }
 const button=(id,action,text,data={},disabled=false)=>`<button type="button" class="button button-secondary" data-business-id="${id}" data-business-action="${action}" data-payload="${esc(JSON.stringify(data))}" ${disabled?'disabled':''}>${esc(text)}</button>`;
 const menu=(id,key,label,html)=>`<details data-menu-key="${id}:${key}" class="business-management"><summary>${label}</summary>${html}</details>`;
 function capture(){
   const open=[...root.querySelectorAll('details[open][data-menu-key]')].map(n=>n.dataset.menuKey);
   const inputs=[...root.querySelectorAll('input[data-input-key]')].map(n=>[n.dataset.inputKey,n.value]);
   const focus=document.activeElement?.dataset.inputKey||null;
   const anchor=[...root.querySelectorAll('[data-enterprise-card]')].find(n=>n.getBoundingClientRect().bottom>100);
   const state={open,inputs,focus,scroll:window.scrollY,anchor:anchor?.dataset.enterpriseCard,anchorTop:anchor?.getBoundingClientRect().top};
   try{sessionStorage.setItem(`shama:business-ui:${userId}`,JSON.stringify(state));}catch(_){}
   return state;
 }
 function restore(saved,scroll=true){
   if(!saved)return;
   root.querySelectorAll('details[data-menu-key]').forEach(n=>n.open=saved.open.includes(n.dataset.menuKey));
   for(const [key,value] of saved.inputs||[])root.querySelectorAll('[data-input-key]').forEach(n=>{if(n.dataset.inputKey===key)n.value=value;});
   if(saved.focus)root.querySelectorAll('[data-input-key]').forEach(n=>{if(n.dataset.inputKey===saved.focus)n.focus({preventScroll:true});});
   if(scroll)requestAnimationFrame(()=>{
     const anchor=root.querySelector(`[data-enterprise-card="${saved.anchor}"]`);
     window.scrollTo({top:anchor?window.scrollY+anchor.getBoundingClientRect().top-saved.anchorTop:saved.scroll,behavior:'instant'});
   });
 }
 function card(r){
   const locked=r.listed,rate=r.hourly;
   const employees=`<div class="employee-list">${r.employees.map(e=>`<div><span>${esc(({worker:'Сотрудник',experienced:'Опытный сотрудник',manager:'Менеджер'})[e.role]||e.role)}<small>${money(e.salary)}/ч</small></span>${button(r.id,'fire','Уволить',{employee_id:e.id},locked)}</div>`).join('')}</div>${r.roles.map(role=>`<div class="employee-hire"><strong>${esc(role.name)}</strong><small>Найм ${money(role.hire_cost)} · зарплата ${money(role.salary)}/ч · +${Math.round(role.bonus*100)}%</small>${button(r.id,'hire','Нанять',{role:role.role},locked||r.employee_count>=r.capacity||r.level<role.level||(role.role==='manager'&&r.employees.some(e=>e.role==='manager')))}</div>`).join('')}`;
   const upgrades=r.upgrades.length?r.upgrades.map(u=>menu(r.id,u.key,`${esc(u.name)} · ${u.level}/3`,`<p>Текущий эффект ${Math.round(u.effect*100)}%${u.next_level?` · следующий ${Math.round(u.next_effect*100)}%`:''}</p>${u.next_level?button(r.id,'upgrade',r.level<u.required_level?`Нужен уровень ${u.required_level}`:`Уровень ${u.next_level} · ${money(u.cost)}`,{direction:u.key,level:u.next_level},locked||r.level<u.required_level):'<p class="muted">Максимальный уровень</p>'}`)).join(''):'<p class="muted">Для киоска улучшений нет.</p>';
   const equipment=r.equipment_options?.length?menu(r.id,'equipment-purchases','Оснащение кофейни',`<p class="muted">Для запуска нужен полный комплект. Общая стоимость ${money(10500)}.</p>${r.equipment_options.map(e=>`<div class="employee-hire"><strong>${esc(e.name)}</strong>${button(r.id,'equipment',e.owned?'Куплено':money(e.price),{key:e.key},locked||e.owned)}</div>`).join('')}`):'';
   return `<article class="business-card" data-enterprise-card="${r.id}"><img class="business-art" src="${esc(r.image)}" alt="${esc(r.name)}" loading="lazy"/><div class="business-card-body"><div class="business-title"><h3>${esc(r.name)}</h3><span>Ур. ${r.level}</span></div><div class="business-status ${r.status==='RUNNING'?'is-running':''}">${locked?'Выставлено на рынке':r.status==='RUNNING'?'Работает':'Приостановлено'}</div>${r.pause_reason?`<p class="business-warning">${esc(r.pause_reason)}</p>`:''}
   <dl class="business-rates"><div><dt>Выручка / ч</dt><dd>${money(rate.revenue)}</dd></div><div><dt>Расходы / ч</dt><dd>−${money(rate.expenses)}</dd></div><div><dt>Зарплата / ч</dt><dd>−${money(rate.wages)}</dd></div><div class="net-profit"><dt>Чистая прибыль / ч</dt><dd>${money(rate.profit)}</dd></div></dl>
   <p class="business-meta">Персонал ${r.employee_count}/${r.capacity} · Бонус +${Math.round(rate.bonus*100)}%<br>Работа ${r.work_hours.toFixed(2)} ч · Опыт ${r.xp_hours.toFixed(2)} ч</p>
   ${button(r.id,'status',r.status==='RUNNING'?'Приостановить':'Возобновить',{status:r.status==='RUNNING'?'PAUSED':'RUNNING'},locked)}
   ${menu(r.id,'management','Сотрудники и улучшения',menu(r.id,'staff','Персонал',employees)+equipment+upgrades)}
   ${menu(r.id,'settings','Название и накопления',`<form data-business-form="rename" data-id="${r.id}"><label>Название<input data-input-key="${r.id}:name" name="name" value="${esc(r.name)}" maxlength="60" required></label><button class="button button-secondary" ${locked?'disabled':''}>Сохранить название</button></form><p class="muted">20% положительной чистой прибыли в накопления при включённой общей настройке банка.</p>${button(r.id,'savings',r.savings_enabled?'Отключить накопления':'Включить накопления',{enabled:!r.savings_enabled},locked)}`)}
   ${menu(r.id,'sale','Продать предприятие',`<form data-list-enterprise="${r.id}"><label>Цена объявления<input data-input-key="${r.id}:price" name="price" type="number" min="1" step="1" value="${r.original_price}" required></label><p class="muted">Комиссия продавца 10%. Сотрудники, оборудование и улучшения переходят покупателю.</p><button class="button button-primary" ${locked?'disabled':''}>Выставить на рынок</button></form><p>Государственный выкуп: <strong>${money(r.state_buyback)}</strong> — 20% расчётной стоимости. Продажа завершает владение этим объектом.</p>${button(r.id,'state-sale',`Подтвердить выкуп за ${money(r.state_buyback)}`,{confirmed:true},locked)}`)}
   </div></article>`;
 }
 function renderBusinesses(saved){
   if(!businesses)return;
   const owned=new Set(businesses.enterprises.map(r=>r.catalog_id));
   root.innerHTML=`<section class="business-section"><div class="business-section-head"><div><span class="eyebrow">ВАШИ АКТИВЫ</span><h2>Мои предприятия</h2></div><span>${businesses.enterprises.length}</span></div><p class="muted">Доход за фактическую работу. Офлайн — до ${businesses.offline_cap_hours} часов.</p><div class="business-grid">${businesses.enterprises.map(card).join('')||'<p class="muted">Выберите первое предприятие в каталоге.</p>'}</div>${menu('catalog','all','Каталог предприятий',`<div class="business-catalog-grid">${businesses.catalog.map(r=>`<article><img src="${esc(r.image)}" alt="" loading="lazy"><strong>${esc(r.name)}</strong><small>${money(r.original_price)}</small>${button(r.id,'buy',owned.has(r.id)?'Уже во владении':'Купить',{},owned.has(r.id))}</article>`).join('')}</div>`)}</section>`;
   restore(saved);
 }
 async function loadBusinesses(){
   if(businessLoad)return businessLoad;
   businessLoad=(async()=>{try{
     businesses=await api('/api/businesses');balance(businesses.balance);
     let saved=root.querySelector('[data-enterprise-card]')?capture():null;
     if(!saved)try{saved=JSON.parse(sessionStorage.getItem(`shama:business-ui:${userId}`));}catch(_){}
     renderBusinesses(saved);
   }catch(e){notify(e.message);}finally{businessLoad=null;}})();return businessLoad;
 }
 async function mutate(path,data,el){
   const owner=el.dataset.businessId||path;if(pending.has(owner))return;
   pending.add(owner);const operation=durable(path,data),label=el.textContent;el.disabled=true;el.textContent='Сохранение…';capture();
   try{
     const result=await api(path,'POST',data,operation.id);operation.clear();balance(result.balance);
     if(result.enterprise){
       const saved=capture(),id=result.enterprise.id,index=businesses.enterprises.findIndex(r=>r.id===id);
       if(index>=0){businesses.enterprises[index]=result.enterprise;const old=root.querySelector(`[data-enterprise-card="${id}"]`);if(old)old.outerHTML=card(result.enterprise);restore(saved);}
       else await loadBusinesses();
     }else if(result.retired_id||path.includes('/businesses/'))await loadBusinesses();
     else{await loadMarket();if(data.enterprise_id)await loadBusinesses();}
     notify('Операция выполнена');
   }catch(e){if(e.status&&e.status<500)operation.clear();notify(e.message);}
   finally{pending.delete(owner);if(el.isConnected){el.disabled=false;el.textContent=label;}}
 }
 async function loadMarket(){
   if(marketLoad)return marketLoad;
   marketLoad=(async()=>{try{const [m,i]=await Promise.all([api('/api/market/listings'),window.api.getInventory()]);market=m;inventory=i.items;userId=m.user_id;renderMarket();}catch(e){notify(e.message);}finally{marketLoad=null;}})();return marketLoad;
 }
 function renderMarket(){
   marketRoot.innerHTML=`<section class="player-market"><h2>Рынок игроков</h2><p class="muted">Предметы: комиссия 5%. Предприятия: комиссия 10%.</p><details class="market-sell-form"><summary>Продать предмет</summary><form id="list-inventory-form"><label>Предмет<select name="item" required><option value="">Выберите предмет</option>${inventory.map(r=>`<option value="${r.id}">${esc(r.name)} · ×${r.quantity}</option>`).join('')}</select></label><label>Цена<input name="price" type="number" min="1" step="1" required></label><button class="button button-primary" ${inventory.length?'':'disabled'}>Выставить на рынок</button></form></details><div class="player-listings">${market.listings.map(r=>`<article class="player-listing"><img src="${esc(r.image)}" alt="${esc(r.name)}" loading="lazy"><div><h3>${esc(r.name)}</h3><small>${rarity(r.rarity)}</small><strong>${money(r.price)}</strong><small>${r.status==='SOLD'?`Продано · комиссия ${money(r.fee)}`:r.seller_id===userId?'Ваше объявление':'Объявление игрока'}</small></div>${r.status==='ACTIVE'?`<button class="button button-secondary" data-listing-action="${r.seller_id===userId?'cancel':'buy'}" data-listing-id="${r.id}">${r.seller_id===userId?'Снять':'Купить'}</button>`:''}</article>`).join('')||'<p class="muted">Объявлений пока нет.</p>'}</div></section>`;
 }
 root.addEventListener('click',e=>{const el=e.target.closest('[data-business-action]');if(el)mutate(`/api/businesses/${el.dataset.businessId}/${el.dataset.businessAction}`,JSON.parse(el.dataset.payload),el);});
 root.addEventListener('toggle',capture,true);
 root.addEventListener('submit',e=>{const form=e.target;e.preventDefault();const data=new FormData(form);if(form.matches('[data-list-enterprise]'))mutate('/api/market/listings/list',{enterprise_id:Number(form.dataset.listEnterprise),price:Number(data.get('price'))},form.querySelector('button'));if(form.dataset.businessForm==='rename')mutate(`/api/businesses/${form.dataset.id}/rename`,{name:data.get('name')},form.querySelector('button'));});
 marketRoot.addEventListener('submit',e=>{e.preventDefault();const data=new FormData(e.target);mutate('/api/market/listings/list',{item_id:Number(data.get('item')),price:Number(data.get('price'))},e.target.querySelector('button'));});
 marketRoot.addEventListener('click',e=>{const el=e.target.closest('[data-listing-action]');if(el)mutate(`/api/market/listings/${el.dataset.listingAction}`,{listing_id:Number(el.dataset.listingId)},el);});
 new MutationObserver(()=>{if(document.getElementById('page-earn').classList.contains('is-active'))loadBusinesses();}).observe(document.getElementById('page-earn'),{attributes:true,attributeFilter:['class']});
 new MutationObserver(()=>{if(document.getElementById('page-market').classList.contains('is-active'))loadMarket();}).observe(document.getElementById('page-market'),{attributes:true,attributeFilter:['class']});
 window.api.getMe().then(u=>{userId=u.id;}).catch(()=>{});
})();
