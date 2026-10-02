/* SHAMA WORKS — mobile economy UI. Data and every monetary action stay server-side. */
(function () {
  "use strict";
  const root = document.querySelector("#works-root");
  if (!root || !window.api) return;

  let snapshot = null;
  let view = "city";
  let loading = false;
  const requestIds = new Map();

  const money = (value) => Math.floor(Number(value) || 0).toLocaleString("ru-RU");
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));
  const idFor = (key) => {
    if (requestIds.has(key)) return requestIds.get(key);
    const value = window.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    requestIds.set(key, value);
    return value;
  };
  const clearId = (key) => requestIds.delete(key);

  function updateBalance(balance) {
    if (balance == null) return;
    ["#global-balance", "#earnings-balance", "#cases-balance", "#market-balance"].forEach((selector) => {
      const node = document.querySelector(selector);
      if (node) node.textContent = `◈ ${money(balance)} SH`;
    });
  }

  function questHtml(quest) {
    const progress = Math.min(100, Math.round((Number(quest.current) || 0) / Math.max(1, Number(quest.target) || 1) * 100));
    return `<article class="works-quest ${quest.completed ? "is-complete" : ""} ${quest.locked ? "is-locked" : ""}">
      <span class="works-quest-mark">${quest.completed ? "✓" : quest.locked ? "⌁" : "◈"}</span><div><strong>${escapeHtml(quest.title)}</strong><small>${quest.locked ? `ОТКРЫВАЕТСЯ НА LVL ${quest.unlock_level}` : `${quest.current}/${quest.target} · +${money(quest.reward_sh)} SH · +${quest.reward_xp} XP`}</small><i><b style="width:${progress}%"></b></i></div>
    </article>`;
  }

  function building(code, icon, title, data, unlockLevel) {
    const locked = !data.unlocked;
    const metric = code === "bank" ? `${money(data.cash_balance)} SH` : `+${money(data.income_per_hour)} SH/h`;
    return `<button type="button" class="works-building works-building--${code} ${locked ? "is-locked" : ""}" data-works-view="${code}" ${locked ? "aria-disabled=\"true\"" : ""}>
      <span class="works-building-icon">${icon}</span><span class="works-building-glow"></span><small>${locked ? `LVL ${unlockLevel}` : `LV.${data.level || 1}`}</small><strong>${title}</strong><em>${locked ? "ЗАКРЫТО" : metric}</em>
    </button>`;
  }

  function renderCity() {
    const { farm, business, bank, jobs, quests, passive_per_hour: passive, balance, level } = snapshot;
    root.innerHTML = `<section class="works-hero card"><div><span class="eyebrow">SHAMA WORLD · ECONOMY DISTRICT</span><h2>SHAMA WORKS</h2><p>CAPITAL <b>${money(balance)} SH</b></p></div><div class="works-income"><small>ПАССИВНЫЙ ДОХОД</small><strong>+${money(passive)} <i>SH/h</i></strong><span>LVL ${level}</span></div></section>
      <section class="works-city" aria-label="Мини-город SHAMA WORKS"><div class="works-city-sky"></div><div class="works-city-road"></div>
        ${building("farm", "🌾", "FARM", farm, 3)}${building("business", "🏪", "BUSINESS", business, 5)}${building("bank", "🏦", "BANK", bank, 8)}
        <button type="button" class="works-building works-building--work" data-works-view="work"><span class="works-building-icon">🏭</span><span class="works-building-glow"></span><small>LVL 1</small><strong>WORK</strong><em>${jobs.filter((job) => job.unlocked).length} ПРОФЕССИЙ</em></button>
      </section>
      <section class="works-section"><div class="works-section-head"><div><span class="eyebrow">DAILY BUSINESS</span><h3>Задания дня</h3></div><span>+ SH · XP</span></div><div class="works-quests">${quests.map(questHtml).join("")}</div></section>
      <section class="works-section works-progression"><div class="works-section-head"><div><span class="eyebrow">YOUR ROUTE</span><h3>Прогрессия</h3></div></div><div>${snapshot.progression.map((step) => `<span class="${step.unlocked ? "is-unlocked" : ""}"><b>LVL ${step.level}</b>${escapeHtml(step.name)}</span>`).join("")}</div></section>`;
  }

  function backButton() { return '<button type="button" class="works-back" data-works-view="city">← К ГОРОДУ</button>'; }
  function actionButton(action, text, primary = true, disabled = false) { return `<button type="button" class="button ${primary ? "button-primary" : "button-secondary"}" data-works-action="${action}" ${disabled ? "disabled" : ""}>${text}</button>`; }

  function renderFarm() {
    const farm = snapshot.farm;
    if (!farm.unlocked) return renderLocked("FARM", "🌾", 3);
    const crops = farm.crops.length ? farm.crops.map((crop) => `<span><b>${escapeHtml(crop.name)}</b><i>+${money(crop.income_per_hour)} SH/h</i></span>`).join("") : '<span><b>Построй первую ферму</b><i>Откроет пшеницу</i></span>';
    root.innerHTML = `<section class="works-detail works-detail--farm">${backButton()}<div class="works-detail-title"><span>🌾</span><div><p class="eyebrow">SHAMA WORKS · FARM</p><h2>${escapeHtml(farm.name)}</h2><small>FARM LV.${farm.level} · +${money(farm.income_per_hour)} SH/h</small></div></div><div class="works-meter"><span>СКЛАД <b>${money(farm.storage)} / ${money(farm.storage_capacity)} SH</b></span><i><b style="width:${farm.storage_capacity ? Math.min(100, farm.storage / farm.storage_capacity * 100) : 0}%"></b></i></div><div class="works-crop-list">${crops}</div><div class="works-stats"><span><small>РАБОЧИЕ</small><b>${farm.workers}/${farm.worker_capacity}</b></span><span><small>ПРОИЗВОДСТВО</small><b>+${money(farm.income_per_hour)} SH/h</b></span></div><div class="works-actions">${actionButton("farm-collect", `СОБРАТЬ ${money(farm.storage)} SH`, true, !farm.level || farm.storage < 1)}${actionButton("farm-upgrade", farm.next ? `УЛУЧШИТЬ · ${money(farm.next.cost)} SH` : "МАКСИМАЛЬНЫЙ УРОВЕНЬ", false, !farm.next)}</div><div class="works-hire"><label>НАЙМ РАБОЧИХ <small>${money(farm.worker_cost)} SH / чел.</small></label><div><input id="works-farm-workers" type="number" min="1" max="${Math.max(1, farm.worker_capacity - farm.workers)}" value="1" inputmode="numeric" ${farm.workers >= farm.worker_capacity ? "disabled" : ""}/>${actionButton("farm-workers", "НАНЯТЬ", false, farm.workers >= farm.worker_capacity)}</div></div></section>`;
  }

  function renderBusiness() {
    const business = snapshot.business;
    if (!business.unlocked) return renderLocked("BUSINESS", "🏪", 5);
    root.innerHTML = `<section class="works-detail works-detail--business">${backButton()}<div class="works-detail-title"><span>🏪</span><div><p class="eyebrow">SHAMA WORKS · BUSINESS</p><h2>${escapeHtml(business.name)}</h2><small>BUSINESS LV.${business.level} · +${money(business.income_per_hour)} SH/h</small></div></div><div class="works-meter"><span>НАКОПЛЕНО <b>${money(business.storage)} / ${money(business.storage_capacity)} SH</b></span><i><b style="width:${business.storage_capacity ? Math.min(100, business.storage / business.storage_capacity * 100) : 0}%"></b></i></div><div class="works-stats"><span><small>КОМАНДА</small><b>${business.workers}/${business.worker_capacity}</b></span><span><small>ПРИБЫЛЬ</small><b>+${money(business.income_per_hour)} SH/h</b></span></div><div class="works-actions">${actionButton("business-collect", `СОБРАТЬ ${money(business.storage)} SH`, true, !business.level || business.storage < 1)}${actionButton("business-upgrade", business.next ? `УЛУЧШИТЬ · ${money(business.next.cost)} SH` : "МАКСИМУМ", false, !business.next)}</div><div class="works-hire"><label>НАЙМ СОТРУДНИКОВ <small>${money(business.worker_cost)} SH / чел.</small></label><div><input id="works-business-workers" type="number" min="1" max="${Math.max(1, business.worker_capacity - business.workers)}" value="1" inputmode="numeric" ${business.workers >= business.worker_capacity ? "disabled" : ""}/>${actionButton("business-workers", "НАНЯТЬ", false, business.workers >= business.worker_capacity)}</div></div><p class="works-note">Переходи от ларька к корпорации. Каждый уровень увеличивает доход и вместимость.</p></section>`;
  }

  function renderBank() {
    const bank = snapshot.bank;
    if (!bank.unlocked) return renderLocked("BANK", "🏦", 8);
    const terms = bank.terms.map((term, index) => `<button type="button" class="works-term ${index === 1 ? "is-active" : ""}" data-works-term="${term.days}">${term.days} DAYS <b>${(term.annual_rate * 100).toFixed(1)}%</b></button>`).join("");
    const deposits = bank.deposits.length ? bank.deposits.map((deposit) => `<article class="works-deposit"><div><strong>${money(deposit.principal)} SH</strong><small>${deposit.term_days} дней · +${money(deposit.interest)} SH</small></div><span>${deposit.status === "PAID" ? "ВЫПЛАЧЕН" : deposit.ready ? "ГОТОВ" : new Date(deposit.matures_at).toLocaleDateString("ru-RU")}</span>${deposit.ready ? actionButton(`deposit-collect:${deposit.id}`, `ПОЛУЧИТЬ ${money(deposit.payout)} SH`, true) : ""}</article>`).join("") : '<p class="works-note">Открой первый игровой вклад. Это не реальные финансы.</p>';
    root.innerHTML = `<section class="works-detail works-detail--bank">${backButton()}<div class="works-detail-title"><span>🏦</span><div><p class="eyebrow">SHAMA WORKS · BANK</p><h2>SH BANK</h2><small>Игровой финансовый центр</small></div></div><div class="works-stats"><span><small>СРЕДСТВА БАНКА</small><b>${money(bank.cash_balance)} SH</b></span><span><small>КЛИЕНТСКИЙ КАПИТАЛ</small><b>${money(bank.client_money)} SH</b></span><span><small>ПРИБЫЛЬ</small><b>${money(bank.profit)} SH</b></span></div><section class="works-deposit-create"><span class="eyebrow">TERM DEPOSIT · GAME MECHANIC</span><div class="works-terms">${terms}</div><div><input id="works-deposit-amount" type="number" min="1" value="100" inputmode="numeric" aria-label="Сумма игрового вклада"/>${actionButton("deposit-create", "ОТКРЫТЬ ВКЛАД", true)}</div></section><div class="works-deposits">${deposits}</div></section>`;
  }

  function renderWork() {
    const sessions = (snapshot.active_jobs || []).filter((session) => session.status === "ACTIVE");
    const current = sessions.length ? `<section class="works-active-job"><span class="eyebrow">ACTIVE SHIFT</span>${sessions.map((session) => `<div><strong>${escapeHtml(session.kind)}</strong><small>до ${new Date(session.expires_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</small>${actionButton(`work-complete:${session.id}`, "ЗАВЕРШИТЬ СМЕНУ", true)}</div>`).join("")}</section>` : "";
    root.innerHTML = `<section class="works-detail works-detail--work">${backButton()}<div class="works-detail-title"><span>🏭</span><div><p class="eyebrow">SHAMA WORKS · JOBS</p><h2>WORK</h2><small>Самый быстрый путь развить начальный капитал</small></div></div>${current}<div class="works-job-grid">${snapshot.jobs.map((job) => `<article class="works-job ${job.unlocked ? "" : "is-locked"}"><span>${job.code === "courier" ? "🛵" : job.code === "warehouse" ? "📦" : job.code === "developer" ? "💻" : job.code === "banker" ? "🏦" : job.code === "factory" ? "⚙" : "🔎"}</span><strong>${escapeHtml(job.name)}</strong><p>${escapeHtml(job.description)}</p><small>+${money(job.reward)} SH · +${job.xp} XP · ${job.duration_seconds} sec</small>${job.unlocked ? actionButton(`work-start:${job.code}`, "НАЧАТЬ СМЕНУ", true) : `<em>LVL ${job.unlock_level}</em>`}</article>`).join("")}</div></section>`;
  }

  function renderLocked(title, icon, level) {
    root.innerHTML = `<section class="works-detail works-locked">${backButton()}<span>${icon}</span><p class="eyebrow">SHAMA WORKS</p><h2>${title} ЗАКРЫТ</h2><p>Достигни LVL ${level}, чтобы открыть этот район города.</p></section>`;
  }

  function render() {
    if (!snapshot) return;
    if (view === "farm") return renderFarm();
    if (view === "business") return renderBusiness();
    if (view === "bank") return renderBank();
    if (view === "work") return renderWork();
    renderCity();
  }

  async function load() {
    if (loading) return;
    loading = true;
    try { snapshot = await window.api.getWorks(); updateBalance(snapshot.balance); render(); }
    catch (error) { root.innerHTML = `<div class="works-error">${escapeHtml(error.message || "SHAMA WORKS временно недоступен")}</div>`; }
    finally { loading = false; }
  }

  async function perform(button, request) {
    if (!button || button.disabled) return;
    button.disabled = true; const label = button.textContent; button.textContent = "ОБРАБОТКА…";
    try {
      const result = await request();
      updateBalance(result.balance);
      const reward = (result.quest_completed || []).map((quest) => `+${money(quest.reward_sh)} SH`).join(" · ");
      if (reward && window.shamaToast) window.shamaToast(`DAILY COMPLETE · ${reward}`);
      clearId(button.dataset.worksAction || label); await load();
    } catch (error) {
      button.disabled = false; button.textContent = label;
      if (window.shamaToast) window.shamaToast(error.message || "Операция не выполнена", "error");
    }
  }

  root.addEventListener("click", (event) => {
    const target = event.target.closest("[data-works-view]");
    if (target) { if (target.getAttribute("aria-disabled") === "true") return; view = target.dataset.worksView; render(); return; }
    const button = event.target.closest("[data-works-action]");
    if (!button) return;
    const action = button.dataset.worksAction;
    if (action === "farm-upgrade") return perform(button, () => window.api.upgradeWorksFarm(idFor(action)));
    if (action === "farm-collect") return perform(button, () => window.api.collectWorksFarm(idFor(action)));
    if (action === "farm-workers") { const quantity = Math.max(1, Math.trunc(Number(document.querySelector("#works-farm-workers")?.value) || 1)); return perform(button, () => window.api.hireWorksFarm(quantity, idFor(`${action}:${quantity}`))); }
    if (action === "business-upgrade") return perform(button, () => window.api.upgradeWorksBusiness(idFor(action)));
    if (action === "business-collect") return perform(button, () => window.api.collectWorksBusiness(idFor(action)));
    if (action === "business-workers") { const quantity = Math.max(1, Math.trunc(Number(document.querySelector("#works-business-workers")?.value) || 1)); return perform(button, () => window.api.hireWorksBusiness(quantity, idFor(`${action}:${quantity}`))); }
    if (action === "deposit-create") { const amount = Math.max(1, Math.trunc(Number(document.querySelector("#works-deposit-amount")?.value) || 0)); const term = Number(document.querySelector(".works-term.is-active")?.dataset.worksTerm || 14); return perform(button, () => window.api.createWorksDeposit(amount, term, idFor(`${action}:${amount}:${term}`))); }
    if (action.startsWith("deposit-collect:")) { const depositId = Number(action.split(":")[1]); return perform(button, () => window.api.collectWorksDeposit(depositId, idFor(action))); }
    if (action.startsWith("work-start:")) return perform(button, () => window.api.startJob(action.split(":")[1]));
    if (action.startsWith("work-complete:")) return perform(button, () => window.api.completeJob(Number(action.split(":")[1])));
  });

  root.addEventListener("click", (event) => {
    const term = event.target.closest("[data-works-term]");
    if (!term) return;
    root.querySelectorAll("[data-works-term]").forEach((node) => node.classList.toggle("is-active", node === term));
  });

  const page = document.querySelector("#page-earn");
  new MutationObserver(() => { if (page.classList.contains("is-active")) load(); }).observe(page, { attributes: true, attributeFilter: ["class"] });
  document.addEventListener("DOMContentLoaded", () => { if (page.classList.contains("is-active")) load(); });
})();
