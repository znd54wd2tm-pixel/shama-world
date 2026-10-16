/* Owned enterprises and user offers extend the existing Works and SH MARKET. */
(function () {
  'use strict';
  const root=document.getElementById('businesses-root'),marketRoot=document.getElementById('player-market-root');
  const esc=(s)=>String(s??'').replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=window.shamaMoney,rarity=window.shamaRarity;
  let businesses=null,market=null,inventory=[],loading=false,loadingMarket=false,userId=0;
  const pending=new Set();
  const api=(path,method='GET',data,key)=>window.api.request(path,{method,headers:{...(data?{'Content-Type':'application/json'}:{}),...(key?{'X-Game-Request-Id':key}:{})},...(data?{body:JSON.stringify(data)}:{})});
  const balance=(value)=>window.dispatchEvent(new CustomEvent('shama:balance',{detail:value}));
  const notify=(message)=>window.shamaToast?.(message);
  function durableId(path,data) {
    const key=`shama:action:${userId}:${path}:${JSON.stringify(data)}`;
    let value;try{value=localStorage.getItem(key);}catch(_){}
    if(!value){value=crypto.randomUUID?.()||`${Date.now()}-${Math.random()}`;try{localStorage.setItem(key,value);}catch(_){}}
    return {id:value,clear:()=>{try{localStorage.removeItem(key);}catch(_){}}};
  }
  async function mutate(path,data,button) {
    if(pending.has(path))return;
    pending.add(path);const operation=durableId(path,data);const label=button.textContent;button.disabled=true;button.textContent='Сохранение…';
    try {const result=await api(path,'POST',data,operation.id);operation.clear();balance(result.balance);notify('Операция выполнена');await Promise.all([loadBusinesses(),loadMarket()]);}
    catch(error){if(error.status&&error.status<500)operation.clear();notify(error.message);button.disabled=false;button.textContent=label;}
    finally{pending.delete(path);}
  }
  const action=(id,name,text,data={},disabled=false)=>`<button type="button" class="button button-secondary" data-business-id="${id}" data-business-action="${name}" data-payload="${esc(JSON.stringify(data))}" ${disabled?'disabled':''}>${text}</button>`;
  function renderBusinesses() {
    if(!businesses)return;
    const owned=businesses.enterprises,ownedTypes=new Set(owned.map((r)=>r.catalog_id));
    root.innerHTML=`<section class="business-section"><div class="business-section-head"><div><span class="eyebrow">YOUR CAPITAL</span><h2>Мои предприятия</h2></div><span>${owned.length} / ${businesses.catalog.length}</span></div><p class="muted">Доход за фактическую работу. Офлайн — до 12 часов. Зарплата уже учтена в прибыли.</p>
      <div class="business-grid">${owned.length?owned.map((r)=>{
        const rate=r.hourly,locked=r.listed;
        return `<article class="business-card rarity-${r.rarity.toLowerCase()} ${r.premium?'business-premium':''}"><img class="business-art" src="${esc(r.image)}" alt="${esc(r.name)}" loading="lazy"/><div class="business-card-body"><div class="business-title"><h3>${esc(r.name)}</h3><span>LVL ${r.level}</span></div><div class="business-status ${r.status==='RUNNING'?'is-running':''}">${r.listed?'Выставлено на SH MARKET':r.status==='RUNNING'?'Работает':'Приостановлено'}</div>${r.pause_reason?`<p class="business-warning">${esc(r.pause_reason)}</p>`:''}
        <dl class="business-rates"><div><dt>Выручка / ч</dt><dd>${money(rate.revenue)}</dd></div><div><dt>Базовые расходы / ч</dt><dd>−${money(rate.expenses)}</dd></div><div><dt>Зарплата / ч</dt><dd>−${money(rate.wages)}</dd></div><div class="net-profit"><dt>Чистая прибыль / ч</dt><dd>${money(rate.profit)}</dd></div></dl>
        <p class="business-meta">Персонал ${r.employee_count}/${r.capacity} · Бонус +${Math.round(rate.bonus*100)}%<br/>Работа ${r.work_hours.toFixed(2)} ч · Опыт ${r.xp_hours.toFixed(2)}${r.next_level_hours?' / '+r.next_level_hours:''} ч<br/>Исходная стоимость ${money(r.original_price)}</p>
        ${action(r.id,'status',r.status==='RUNNING'?'Приостановить':'Возобновить',{status:r.status==='RUNNING'?'PAUSED':'RUNNING'},locked)}
        <details class="business-management"><summary>Сотрудники и улучшения</summary><p class="muted">Без персонала: 50% выручки, 70% базовых расходов, опыт ×0,5.</p>
        <div class="employee-list">${r.employees.map((e)=>`<div><span>${e.role==='manager'?'Менеджер':'Специалист'}<small>${money(e.salary)} / ч · +${Math.round(e.bonus*100)}%</small></span>${action(r.id,'fire','Уволить',{employee_id:e.id},locked)}</div>`).join('')}</div>
        ${r.roles.map((role)=>`<div class="employee-hire"><strong>${esc(role.name)}</strong><small>Найм ${money(role.hire_cost)} · зарплата ${money(role.salary)}/ч · +${Math.round(role.bonus*100)}%${r.level<role.level?` · с уровня ${role.level}`:''}</small>${action(r.id,'hire','Нанять',{role:role.role},locked||r.employee_count>=r.capacity||r.level<role.level||(role.role==='manager'&&r.employees.some((e)=>e.role==='manager')))}</div>`).join('')}
        <div class="business-upgrades">${r.upgrades.map((u)=>`<div><strong>${esc(u.name)} ${u.level}/3</strong><small>Текущий эффект: ${u.key==='equipment'||u.key==='marketing'?'+':'−'}${Math.round(u.effect*100)}%${u.next_level?` · следующий ${Math.round(u.next_effect*100)}%`:''}</small>${u.next_level?action(r.id,'upgrade',r.level<u.required_level?`Нужен уровень ${u.required_level}`:`Уровень ${u.next_level} · ${money(u.cost)}`,{direction:u.key,level:u.next_level},locked||r.level<u.required_level):'<span class="muted">Максимум</span>'}</div>`).join('')}</div></details>
        <details class="business-list-form"><summary>Продать на SH MARKET</summary><form data-list-enterprise="${r.id}"><label>Цена продажи<input name="price" type="number" inputmode="numeric" min="1" step="1" value="${r.original_price}" required ${locked?'disabled':''}/></label><p class="muted">Комиссия 5%. Сотрудники и улучшения переходят покупателю.</p><button class="button button-primary" ${locked?'disabled':''}>Выставить на продажу</button></form></details></div></article>`;
      }).join(''):'<div class="business-empty"><strong>Первый актив — начало империи</strong><p>Откройте бизнес-кейс или купите предприятие из каталога.</p></div>'}</div>
      <details class="business-catalog"><summary>Каталог предприятий</summary><div class="business-catalog-grid">${businesses.catalog.map((r)=>`<article><img src="${esc(r.image)}" alt="" loading="lazy"/><strong>${esc(r.name)}</strong><small>${rarity(r.rarity)} · ${money(r.original_price)}</small><small>База: выручка ${money(r.revenue)}/ч · расходы ${money(r.expenses)}/ч</small>${action(r.id,'buy',ownedTypes.has(r.id)?'Уже во владении':`Купить за ${money(r.original_price)}`,{},ownedTypes.has(r.id))}</article>`).join('')}</div></details></section>`;
  }
  async function loadBusinesses() {
    if(loading)return;loading=true;
    try{businesses=await api('/api/businesses');balance(businesses.balance);renderBusinesses();}
    catch(error){root.innerHTML=`<div class="recovery-banner">${esc(error.message)}<button id="reload-businesses" class="button button-secondary">Повторить</button></div>`;}
    finally{loading=false;}
  }
  async function loadMarket() {
    if(loadingMarket)return;loadingMarket=true;
    try{const data=await Promise.all([api('/api/market/listings'),window.api.getInventory()]);market=data[0];userId=market.user_id;inventory=data[1].items;renderMarket();}
    catch(error){marketRoot.innerHTML=`<div class="recovery-banner">${esc(error.message)}<button id="reload-player-market" class="button button-secondary">Повторить</button></div>`;}
    finally{loadingMarket=false;}
  }
  function renderMarket() {
    if(!market)return;
    marketRoot.innerHTML=`<section class="player-market"><div class="business-section-head"><div><span class="eyebrow">SH MARKET · ИГРОКИ</span><h2>Предметы и предприятия</h2></div><span>Комиссия 5%</span></div>
      <details class="market-sell-form"><summary>Выставить предмет из инвентаря</summary><form id="list-inventory-form"><label>Предмет<select name="item" required><option value="">Выберите предмет</option>${inventory.map((r)=>`<option value="${r.id}">${esc(r.name)} · ×${r.quantity}</option>`).join('')}</select></label><label>Цена<input name="price" type="number" min="1" step="1" inputmode="numeric" required/></label><button class="button button-primary" ${inventory.length?'':'disabled'}>Выставить на продажу</button></form></details>
      <div class="player-listings">${market.listings.length?market.listings.map((r)=>`<article class="player-listing rarity-${r.rarity.toLowerCase()}"><img src="${esc(r.image)}" alt="" loading="lazy"/><div><h3>${esc(r.name)}</h3><small>${rarity(r.rarity)}${r.enterprise_id?` · персонал ${r.employees}`:''}</small><strong>${money(r.price)}</strong><small>${r.status==='SOLD'?`Продано · комиссия ${money(r.fee)}`:r.seller_id===market.user_id?'Ваше объявление':'Объявление игрока'}</small>${r.enterprise_id?'<small>Уровень, улучшения и сотрудники сохраняются</small>':''}</div>${r.status==='ACTIVE'?`<button class="button ${r.seller_id===market.user_id?'button-secondary':'button-primary'}" data-listing-action="${r.seller_id===market.user_id?'cancel':'buy'}" data-listing-id="${r.id}">${r.seller_id===market.user_id?'Снять':'Купить'}</button>`:''}</article>`).join(''):'<p class="muted">Пока нет объявлений. Выставьте предмет или предприятие на продажу.</p>'}</div></section>`;
  }
  root.addEventListener('click',(event)=>{if(event.target.closest('#reload-businesses'))return loadBusinesses();const button=event.target.closest('[data-business-action]');if(button)mutate(`/api/businesses/${button.dataset.businessId}/${button.dataset.businessAction}`,JSON.parse(button.dataset.payload),button);});
  root.addEventListener('submit',(event)=>{const form=event.target.closest('[data-list-enterprise]');if(!form)return;event.preventDefault();mutate('/api/market/listings/list',{enterprise_id:Number(form.dataset.listEnterprise),price:Number(new FormData(form).get('price'))},form.querySelector('button'));});
  marketRoot.addEventListener('submit',(event)=>{if(event.target.id!=='list-inventory-form')return;event.preventDefault();const form=event.target,data=new FormData(form);mutate('/api/market/listings/list',{item_id:Number(data.get('item')),price:Number(data.get('price'))},form.querySelector('button'));});
  marketRoot.addEventListener('click',(event)=>{if(event.target.closest('#reload-player-market'))return loadMarket();const button=event.target.closest('[data-listing-action]');if(button)mutate(`/api/market/listings/${button.dataset.listingAction}`,{listing_id:Number(button.dataset.listingId)},button);});
  const earn=document.getElementById('page-earn'),marketPage=document.getElementById('page-market');
  new MutationObserver(()=>{if(earn.classList.contains('is-active'))loadBusinesses();}).observe(earn,{attributes:true,attributeFilter:['class']});
  new MutationObserver(()=>{if(marketPage.classList.contains('is-active'))loadMarket();}).observe(marketPage,{attributes:true,attributeFilter:['class']});
  window.api.getMe().then((user)=>{userId=user.id;}).catch(()=>{});
})();
