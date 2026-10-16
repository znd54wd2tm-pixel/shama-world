/* Server results always precede animation. Fast mode changes presentation only. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g,(s)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  const money = (n) => '$' + Number(n || 0).toLocaleString('ru-RU',{maximumFractionDigits:2}).replace(/\u00a0/g,' ');
  const rarities = {COMMON:'Обычный',UNCOMMON:'Необычный',RARE:'Редкий',EPIC:'Эпический',LEGENDARY:'Легендарный',MYTHIC:'Мифический'};
  const uuid = () => window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const read = (key) => { try { return JSON.parse(localStorage.getItem(key)); } catch (_) { return null; } };
  const write = (key,value) => { try { value == null ? localStorage.removeItem(key) : localStorage.setItem(key,JSON.stringify(value)); } catch (_) {} };
  window.shamaMoney = money;
  window.shamaRarity = (r) => rarities[r] || r;

  window.createCaseUI = function (ctx) {
    let selected = null, fast = false, busy = false, saving = false, userId = 0, results = [], focus = 0, selectedIds = new Set();
    let scene = null, sceneGeneration = 0, skip = false, animationCancel = null, animationLabel = '', actionKey = null, activeAction = false;
    const supported = new Map();
    const pendingKey = () => `shama:pending-opening:${userId}`;
    const resultKey = () => `shama:last-opening:${userId}`;
    const toast = (s) => ctx.toast(s);
    const request = (path, method='GET', body, key) => window.api.request(path,{method,headers:{...(body?{'Content-Type':'application/json'}:{}),...(key?{'X-Game-Request-Id':key}:{})},...(body?{body:JSON.stringify(body)}:{})});
    function stopScene() { sceneGeneration++; scene?.dispose(); scene=null; }
    async function mountScene(host, data, preview) {
      stopScene(); const generation = sceneGeneration;
      try {
        const module = await import('./case-scene.js');
        if (generation !== sceneGeneration || (fast && preview)) return null;
        scene = module.createCaseScene(host,data,{preview}); return scene;
      } catch (_) { host.dataset.renderer='fallback'; return null; }
    }
    function setBusy(value) { busy=value; ctx.busy(value); $('open-case-button').disabled=value; $('open-ten-cases-button').disabled=value; $('fast-open-toggle').disabled=value || saving; }
    function syncFast() {
      const button=$('fast-open-toggle'); button.setAttribute('aria-pressed',String(fast)); button.classList.toggle('is-active',fast);
      $('fast-open-label').textContent=fast?'Быстрый прокрут':'Обычное открытие';
      $('case-scene').classList.toggle('fast-preview',fast);
    }
    async function toggleFast() {
      if (saving || busy) return;
      saving=true; $('fast-open-toggle').disabled=true;
      try { const value=await request('/api/settings','PATCH',{fast_open:!fast}); fast=value.fast_open; syncFast();
        toast(fast?'⚡ Быстрый прокрут включён':'Быстрый прокрут выключен');
        if (fast) stopScene(); else if(selected) mountScene($('case-scene'),selected,true);
      } catch(error) { toast(error.message); }
      finally { saving=false; $('fast-open-toggle').disabled=false; }
    }
    async function showCase(id) {
      if(busy || activeAction) return;
      try {
        selected=await window.api.getCase(id); ctx.selected(selected);
        $('case-detail-image').src=selected.image; $('case-detail-image').alt=selected.name;
        $('case-detail-name').textContent=selected.name; $('case-detail-description').textContent=selected.description;
        $('case-detail-price').textContent=money(selected.price); $('case-player-balance').textContent=money(ctx.user()?.balance);
        $('case-kind-label').textContent=selected.kind==='BUSINESS'?'ПРЕДПРИЯТИЯ':'КОЛЛЕКЦИЯ';
        $('open-case-button').textContent=`Открыть 1 за ${money(selected.price)}`;
        $('open-ten-cases-button').textContent=`Открыть 10 за ${money(selected.price*10)}`;
        $('case-drop-preview').innerHTML=selected.drops.map((r)=>`<article class="drop-preview rarity-${r.rarity.toLowerCase()}"><img src="${esc(r.image)}" alt="" loading="lazy"/><strong>${esc(r.name)}</strong><small>${rarities[r.rarity]} · ${Number((r.chance*100).toFixed(3))}%</small></article>`).join('');
        syncFast(); setBusy(false); ctx.openModal('case-modal');
        $('case-scene').dataset.renderer='fallback';
        if(!fast) mountScene($('case-scene'),selected,true);
      } catch(error) { toast(error.message); }
    }
    function showChances() {
      if (!selected) return;
      $('chances-list').innerHTML=selected.drops.map((r)=>`<div class="chance-row"><img src="${esc(r.image)}" alt=""/><div class="chance-info"><strong>${esc(r.name)}</strong><span class="rarity-${r.rarity.toLowerCase()}">${rarities[r.rarity]}</span></div><div class="chance-value"><strong>${Number((r.chance*100).toFixed(3))}%</strong><small>${money(r.value)}</small></div></div>`).join(''); ctx.openModal('chances-modal');
    }
    function wait(ms) { return new Promise((resolve)=>{ const timer=setTimeout(()=>{animationCancel=null;resolve();},ms); animationCancel=()=>{clearTimeout(timer);animationCancel=null;resolve();}; }); }
    async function animate(item,index,total) {
      $('opening-stage').classList.remove('is-hidden'); $('opening-result').classList.add('is-hidden');
      $('opening-sequence').textContent=`${index+1} / ${total}`;
      $('opening-status').textContent='Кейс открывается';
      $('opening-3d').classList.remove('is-hidden'); $('opening-reel-wrap').classList.add('is-hidden');
      $('opening-case-image').src=selected.image;
      const model=await mountScene($('opening-3d'),selected,false);
      if(skip) {stopScene();return;}
      if(model) { const animation=model.play(); animationCancel=()=>stopScene(); await animation; animationCancel=null; }
      else await wait(250);
      if(skip) {stopScene();return;}
      stopScene(); $('opening-3d').classList.add('is-hidden'); $('opening-reel-wrap').classList.remove('is-hidden');
      $('opening-status').textContent='Результат определён сервером';
      const reel=$('opening-reel'),pool=selected.drops.length?selected.drops:[item],winnerIndex=24;
      const cards=Array.from({length:30},(_,i)=>i===winnerIndex?item:pool[(i*7+index)%pool.length]);
      reel.innerHTML=cards.map((r)=>`<div class="opening-reel-card rarity-${r.rarity.toLowerCase()}"><img src="${esc(r.image)}" alt=""/><strong>${esc(r.name)}</strong><small>${rarities[r.rarity]}</small></div>`).join('');
      reel.style.transition='none'; reel.style.transform='translate3d(0,0,0)';
      await new Promise(requestAnimationFrame);
      if(skip) return;
      const winner=reel.children[winnerIndex],wrap=$('opening-reel-wrap');
      const target=wrap.clientWidth/2-winner.offsetLeft-winner.offsetWidth/2;
      reel.style.transition='transform 3000ms cubic-bezier(.08,.73,.12,1)';
      reel.style.transform=`translate3d(${target}px,0,0)`;
      await wait(3000); winner.classList.add('is-landed');
    }
    function activeItems() { return results.filter((r)=>r.kind==='ITEM' && ['AVAILABLE','KEPT'].includes(r.status)); }
    function renderResults() {
      const item=results[focus]; if(!item) return;
      $('opening-stage').classList.add('is-hidden'); $('opening-result').classList.remove('is-hidden'); $('opening-close').classList.remove('is-hidden'); $('opening-skip').classList.add('is-hidden');
      $('result-image').src=item.image; $('result-image').alt=item.name;
      $('result-name').textContent=item.name; $('result-rarity').textContent=rarities[item.rarity]; $('result-rarity').className=`rarity-label rarity-${item.rarity.toLowerCase()}`;
      $('result-value').textContent=money(item.compensation || item.value);
      $('result-value-label').textContent=item.compensation?'Компенсация за повтор':'Стоимость';
      $('opening-result-kicker').textContent=results.length>1?`${results.length} результатов сохранено`:(item.kind==='BUSINESS'?'Предприятие получено':'Предмет получен');
      $('result-description').textContent=item.compensation?`Повторное предприятие. Начислено ${money(item.compensation)} — 50% исходной стоимости.`:item.kind==='BUSINESS'?'Предприятие доступно в разделе «Заработок».':(['AVAILABLE','KEPT'].includes(item.status)?'Предмет уже защищённо сохранён на сервере.':({SOLD:'Предмет продан',UPGRADED:'Предмет использован в апгрейде',MARKET:'Предмет выставлен на SH MARKET',TRANSFERRED:'Предмет передан покупателю'}[item.status]||item.status));
      const usable=activeItems(),chosen=usable.filter((r)=>selectedIds.has(r.result_id));
      $('result-batch').classList.toggle('is-hidden',results.length<2);
      $('result-batch').innerHTML=results.map((r,i)=>`<article class="result-mini rarity-${r.rarity.toLowerCase()} ${i===focus?'is-focused':''}"><button type="button" data-result-focus="${i}" aria-label="Посмотреть ${esc(r.name)}"><img src="${esc(r.image)}" alt=""/><strong>${esc(r.name)}</strong><small>${r.compensation?`+${money(r.compensation)}`:rarities[r.rarity]}</small></button>${r.kind==='ITEM'&&['AVAILABLE','KEPT'].includes(r.status)?`<label><input type="checkbox" data-result-select="${esc(r.result_id)}" ${selectedIds.has(r.result_id)?'checked':''}/>Выбрать</label>`:`<small>${r.kind==='BUSINESS'?'Предприятие':esc(r.status)}</small>`}</article>`).join('');
      const sell=$('opening-sell-button'); sell.classList.toggle('is-hidden',usable.length===0); sell.disabled=activeAction||chosen.length===0; sell.textContent=results.length===1?`Продать сразу за ${money(item.value)}`:`Продать выбранные (${chosen.length}) · ${money(chosen.reduce((sum,r)=>sum+r.value,0))}`;
      $('saved-button').textContent=results.length===1?'Сохранить в инвентарь':'Сохранить всё в инвентарь'; $('saved-button').disabled=activeAction;
      $('saved-button').classList.toggle('is-hidden',item.kind==='BUSINESS');
      $('result-business-button').classList.toggle('is-hidden',item.kind!=='BUSINESS');
      $('result-upgrade-button').classList.toggle('is-hidden',!supported.get(item.id)||item.kind!=='ITEM'||!['AVAILABLE','KEPT'].includes(item.status));
      $('result-upgrade-selected').classList.toggle('is-hidden',results.length<2||!chosen.some((r)=>supported.get(r.id)));
      $('result-sell-one').classList.toggle('is-hidden',results.length<2||item.kind!=='ITEM'||!['AVAILABLE','KEPT'].includes(item.status));
      $('result-keep-one').classList.toggle('is-hidden',results.length<2||item.kind!=='ITEM'||!['AVAILABLE','KEPT'].includes(item.status));
    }
    async function resolveSupport() {
      const items=[...new Map(activeItems().map((r)=>[r.id,r])).values()];
      await Promise.allSettled(items.map(async(r)=>{try{supported.set(r.id,(await window.api.getUpgradeTargets(r.id)).items.length>0);}catch(_){supported.set(r.id,false);}}));
      renderResults();
    }
    function showResults(items) {
      results=items; focus=0; selectedIds=new Set(activeItems().map((r)=>r.result_id)); supported.clear();
      ctx.openModal('opening-modal'); renderResults(); resolveSupport();
    }
    async function open(quantity=1,recover=false) {
      if(!selected || busy || activeAction || saving) return;
      const old=read(pendingKey());
      if(old && (old.caseId!==selected.id || old.quantity!==quantity)) { toast('Сначала восстановите предыдущее открытие'); await recoverPending(); return; }
      const pending=old || {caseId:selected.id,quantity,requestId:uuid()};
      write(pendingKey(),pending); setBusy(true); ctx.lastCase(selected.id); skip=false;
      const single=$('open-case-button'),ten=$('open-ten-cases-button');
      const button=quantity===1?single:ten,label=button.textContent; button.textContent='Сервер сохраняет результат…';
      let response=null;
      try {
        stopScene();
        if(recover) {try{response=await request(`/api/openings/by-request/${encodeURIComponent(pending.requestId)}`);}catch(error){if(error.status!==404)throw error;}}
        if(!response) response=await (quantity===1?window.api.openCase(selected.id,pending.requestId):window.api.openTenCases(selected.id,pending.requestId));
        write(pendingKey(),null); write(resultKey(),pending.requestId); $('opening-recovery').classList.add('is-hidden');
        ctx.update({balance:response.balance,xp:response.xp,level:response.level}); ctx.closeModal('case-modal',true);
        $('opening-close').classList.add('is-hidden'); $('opening-result').classList.add('is-hidden'); $('opening-skip').classList.toggle('is-hidden',fast); ctx.openModal('opening-modal');
        results=response.items || [response.item];
        if(!fast && !recover) for(let i=0;i<results.length&&!skip;i++) await animate(results[i],i,results.length);
        showResults(results);
        window.api.getMe().then(ctx.update).catch(()=>{});
      } catch(error) {
        if(response) { showResults(response.items||[response.item]); toast('Результат сохранён. Анимация недоступна.'); }
        else { if(error.status && error.status<500) write(pendingKey(),null); toast(error.message); updateRecovery(); }
      } finally { stopScene(); setBusy(false); button.textContent=label; }
    }
    async function action(kind,one=false) {
      if(activeAction) return;
      const chosen=(one?[results[focus]]:results.filter((r)=>kind==='keep'||selectedIds.has(r.result_id))).filter((r)=>r.kind==='ITEM'&&['AVAILABLE','KEPT'].includes(r.status));
      if(!chosen.length) {if(kind==='keep') ctx.closeModal('opening-modal');return;}
      activeAction=true; const payload={result_ids:chosen.map((r)=>r.result_id)}; const signature=JSON.stringify({kind,payload});
      if(!actionKey || actionKey.signature!==signature) actionKey={signature,id:uuid()};
      renderResults();
      try { const response=await request(`/api/openings/results/${kind}`,'POST',payload,actionKey.id); ctx.update({balance:response.balance}); chosen.forEach((r)=>{r.status=kind==='sell'?'SOLD':'KEPT';}); actionKey=null; toast(kind==='sell'?`Продано за ${money(response.amount)}`:'Сохранено в инвентарь');
        if(kind==='keep'&&!one) ctx.closeModal('opening-modal',true);
      } catch(error) {toast(error.message);} finally {activeAction=false;renderResults();ctx.reloadInventory();}
    }
    async function upgrade(many=false) {
      const items=(many?results.filter((r)=>selectedIds.has(r.result_id)):[results[focus]]).filter((r)=>r.kind==='ITEM'&&supported.get(r.id)&&['AVAILABLE','KEPT'].includes(r.status));
      if(!items.length||activeAction) return;
      ctx.closeModal('opening-modal'); ctx.upgrade(items);
    }
    function updateRecovery() { $('opening-recovery').classList.toggle('is-hidden',!read(pendingKey())); }
    async function recoverPending() { const pending=read(pendingKey());if(!pending)return;await showCase(pending.caseId);await open(pending.quantity,true); }
    async function history() {
      try {const data=await request('/api/openings');$('opening-history-list').innerHTML=data.operations.length?data.operations.map((o)=>`<button class="history-opening" data-restore-opening="${esc(o.request_id)}"><strong>${o.quantity} × ${esc(o.items[0]?.kind==='BUSINESS'?'Бизнес-кейс':'Кейс')}</strong><span>${money(o.total_price)} · ${esc(o.created_at)}</span><small>${o.items.map((i)=>esc(i.name)).join(' · ')}</small></button>`).join(''):'<p class="muted">Открытий пока нет.</p>';ctx.openModal('opening-history-modal');}catch(error){toast(error.message);}
    }
    async function restore(key) {try{const operation=await request(`/api/openings/by-request/${encodeURIComponent(key)}`);ctx.closeModal('opening-history-modal');write(resultKey(),key);showResults(operation.items);ctx.update(await window.api.getMe());}catch(error){toast(error.message);}}
    $('fast-open-toggle').addEventListener('click',toggleFast);
    $('opening-skip').addEventListener('click',()=>{skip=true;animationCancel?.();stopScene();});
    $('restore-opening-button').addEventListener('click',recoverPending);
    $('opening-history-button').addEventListener('click',history);
    $('result-upgrade-button').addEventListener('click',()=>upgrade());
    $('result-upgrade-selected').addEventListener('click',()=>upgrade(true));
    $('result-sell-one').addEventListener('click',()=>action('sell',true));
    $('result-keep-one').addEventListener('click',()=>action('keep',true));
    $('result-business-button').addEventListener('click',()=>{ctx.closeModal('opening-modal');ctx.navigate('earn');});
    document.addEventListener('click',(event)=>{const button=event.target.closest('[data-result-focus]');if(button){focus=Number(button.dataset.resultFocus);renderResults();}const restoreButton=event.target.closest('[data-restore-opening]');if(restoreButton)restore(restoreButton.dataset.restoreOpening);});
    $('result-batch').addEventListener('change',(event)=>{const input=event.target.closest('[data-result-select]');if(input){input.checked?selectedIds.add(input.dataset.resultSelect):selectedIds.delete(input.dataset.resultSelect);renderResults();}});
    return {showCase,showChances,open,action,
      async init(id) {userId=id; const value=await request('/api/settings');fast=value.fast_open;syncFast();updateRecovery();const key=read(resultKey());if(key)await restore(key);},
      close(id) {if(id==='case-modal')stopScene();if(id==='opening-modal'){skip=true;animationCancel?.();stopScene();write(resultKey(),null);} },
      get busy() {return busy||activeAction;}
    };
  };
})();
