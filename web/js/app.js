(function () {
  "use strict";

  const state = {
    currentUser: null,
    currentPage: "world",
    cases: [],
    selectedCase: null,
    inventory: [],
    opening: false,
    upgrade: { source: null, target: null, preview: null, targets: [], filter: "ALL", sort: "asc", running: false },
    sell: { item: null, quantity: 1, running: false },
    earnings: null,
    market: null,
    activeJob: null,
    mission: { kind: null, step: 0, total: 0, timer: null, deadline: 0, courier: 0, factory: 0, huntFound: false },
    inventoryFilter: "ALL",
    marketTimer: null,
  };
  const pageNames = {
    earn: ["ЗАРАБОТОК", "Раздел в разработке", "Новые способы заработка уже в пути."],
    profile: ["ПРОФИЛЬ", "PLAYER STATS", ""],
    market: ["SH MARKET", "MAC MARKET", ""],
  };
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[char]));
  const rarityClass = (rarity) => `rarity-${String(rarity || "common").toLowerCase()}`;

  function setTelegramReady() {
    if (!window.Telegram || !window.Telegram.WebApp) return;
    window.Telegram.WebApp.ready(); window.Telegram.WebApp.expand();
    if (window.Telegram.WebApp.setHeaderColor) window.Telegram.WebApp.setHeaderColor("#0a0713");
  }
  function initials(user) { return `${(user.first_name || "S")[0]}${(user.last_name || "W")[0]}`.toUpperCase(); }
  function openModal(id) { document.getElementById(id).classList.remove("is-hidden"); }
  function closeModal(id) { document.getElementById(id).classList.add("is-hidden"); }
  function toast(message) { const element = $("#toast"); element.textContent = message; element.classList.remove("is-hidden"); window.clearTimeout(toast.timer); toast.timer = window.setTimeout(() => element.classList.add("is-hidden"), 2800); }
  function showError(message) { $("#loading-screen").classList.add("is-hidden"); $("#app").classList.add("is-hidden"); $("#error-screen").classList.remove("is-hidden"); $("#error-message").textContent = message; }
  function showApp() { $("#loading-screen").classList.add("is-hidden"); $("#error-screen").classList.add("is-hidden"); $("#app").classList.remove("is-hidden"); }

  function renderUser(user) {
    state.currentUser = user;
    const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ") || "Игрок SHAMA";
    $("#welcome-name").textContent = user.first_name || "игрок";
    $("#profile-username").textContent = user.username ? `@${user.username}` : "Игрок SHAMA";
    $("#profile-full-name").textContent = fullName;
    $("#profile-level").textContent = user.level; $("#profile-balance").textContent = user.balance; $("#profile-xp").textContent = user.xp;
    $("#xp-progress").style.width = `${Math.min(100, user.xp % 100)}%`; $("#profile-xp-label").textContent = Math.min(100, user.xp % 100);
    $("#profile-avatar").textContent = initials(user); $("#profile-avatar-large").textContent = initials(user); $("#cases-balance").textContent = `${user.balance} SH`;
    const pageAvatar = $("#profile-page-avatar"); if (pageAvatar) pageAvatar.textContent = initials(user);
    const pageUsername = $("#profile-page-username"); if (pageUsername) pageUsername.textContent = user.username ? `@${user.username}` : "Игрок SHAMA";
    const pageFullName = $("#profile-page-full-name"); if (pageFullName) pageFullName.textContent = fullName;
    const pageLevel = $("#profile-page-level"); if (pageLevel) pageLevel.textContent = user.level;
    const pageBalance = $("#profile-page-balance"); if (pageBalance) pageBalance.textContent = `${user.balance} SH`;
    const pageXp = $("#profile-page-xp"); if (pageXp) pageXp.textContent = `${Math.min(100, user.xp % 100)} / 100`;
    const pageProgress = $("#profile-page-progress"); if (pageProgress) pageProgress.style.width = `${Math.min(100, user.xp % 100)}%`;
    const activityBalance = $("#activity-balance"); if (activityBalance) activityBalance.textContent = `${user.balance} SH`;
    const activityLevel = $("#activity-level"); if (activityLevel) activityLevel.textContent = `LVL ${user.level}`;
    ["#global-balance", "#inventory-balance", "#upgrade-balance", "#profile-stat-balance"].forEach((selector) => { const element = $(selector); if (element) element.textContent = `◈ ${user.balance} SH`; });
    const statLevel = $("#profile-stat-level"); if (statLevel) statLevel.textContent = `${user.level} / ${user.xp} XP`;
    const statCases = $("#profile-stat-cases"); if (statCases) statCases.textContent = user.cases_opened;
    const statCollected = $("#profile-stat-collected"); if (statCollected) statCollected.textContent = user.items_collected;
    const statUpgrades = $("#profile-stat-upgrades"); if (statUpgrades) statUpgrades.textContent = user.upgrades_total;
    const statSold = $("#profile-stat-sold"); if (statSold) statSold.textContent = user.total_items_sold;
    const statEarned = $("#profile-stat-earned"); if (statEarned) statEarned.textContent = `${user.total_sh_earned_from_sales} SH`;
    ["#global-balance", "#inventory-balance", "#upgrade-balance"].forEach((selector) => { const element = $(selector); if (element) { element.classList.remove("balance-pulse"); void element.offsetWidth; element.classList.add("balance-pulse"); } });
  }
  function renderPage(page) {
    const pages = ["world", "cases", "earn", "inventory", "upgrade", "market", "profile"];
    pages.forEach((name) => { const element = document.getElementById(`page-${name}`); if (element) element.classList.toggle("is-active", name === page); });
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("is-active", item.dataset.nav === page));
    if (page === "cases") loadCases();
    if (page === "inventory") loadInventory();
    if (page === "upgrade") loadUpgrade();
    if (page === "earn") loadEarnings();
    if (page === "market") loadMarket();
    if (page === "profile") { loadTransactions(); loadProfileExtras(); }
    state.currentPage = page;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function renderCases() {
    $("#cases-grid").innerHTML = state.cases.map((item) => { const price = Number(item.price) || 0; const tier = price >= 5000 ? "mythic" : price >= 2500 ? "legendary" : price >= 1000 ? "epic" : price >= 500 ? "rare" : price >= 250 ? "uncommon" : "common"; return `<button type="button" class="case-card card case-tier-${tier}" data-case-id="${item.id}"><div class="case-art"><img src="${item.image}" alt="${escapeHtml(item.name)}" /><span class="case-shine"></span><span class="case-tier-badge">${tier.toUpperCase()}</span></div><div class="case-card-overlay"><span class="eyebrow">CASE DROP</span><strong>${escapeHtml(item.name)}</strong><div class="case-card-bottom"><span class="case-card-price">${item.price} SH</span><span class="case-open-hint">OPEN&nbsp;→</span></div></div></button>`; }).join("");
    $("#cases-balance").textContent = `${state.currentUser ? state.currentUser.balance : "—"} SH`;
    const count = $("#cases-count"); if (count) count.textContent = state.cases.length;
  }
  async function loadCases() { if (state.cases.length) return renderCases(); try { state.cases = (await window.api.getCases()).cases || []; renderCases(); } catch (error) { toast(error.message || "Не удалось загрузить кейсы."); } }
  function chancePercent(chance) { return `${(Number(chance) * 100).toFixed(Number(chance) < 0.1 ? 1 : 0)}%`; }
  async function showCase(caseId) {
    try { state.selectedCase = await window.api.getCase(caseId); const item = state.selectedCase; $("#case-detail-image").src = item.image; $("#case-detail-image").alt = item.name; $("#case-detail-name").textContent = item.name; $("#case-detail-description").textContent = item.description; $("#case-detail-price").textContent = `${item.price} SH`; $("#open-case-button").textContent = `ОТКРЫТЬ ЗА ${item.price} SH`; $("#open-case-button").disabled = false; openModal("case-modal"); } catch (error) { toast(error.message || "Не удалось загрузить кейс."); }
  }
  function showChances() {
    if (!state.selectedCase) return; $("#chances-list").innerHTML = state.selectedCase.drops.map((item) => `<div class="chance-row"><img src="${item.image}" alt="" /><div class="chance-info"><strong>${escapeHtml(item.name)}</strong><span class="${rarityClass(item.rarity)}">${item.rarity}</span></div><div class="chance-value"><strong>${chancePercent(item.chance)}</strong><small>${item.value} SH</small></div></div>`).join(""); openModal("chances-modal");
  }
  async function openSelectedCase() {
    if (!state.selectedCase || state.opening) return; const button = $("#open-case-button"); button.disabled = true; state.opening = true; button.classList.add("is-loading"); button.dataset.originalText = button.textContent; button.textContent = "ОТКРЫВАЕМ...";
    try { const requestId = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now().toString(36)}-${performance.now().toString(36)}`; const result = await window.api.openCase(state.selectedCase.id, requestId); state.currentUser.balance = result.balance; state.currentUser.xp = result.xp; state.currentUser.level = result.level; renderUser(state.currentUser); closeModal("case-modal"); $("#opening-stage").classList.remove("is-hidden"); $("#opening-result").classList.add("is-hidden"); $("#opening-case-image").src = state.selectedCase.image; openModal("opening-modal"); window.setTimeout(() => revealCaseItem(result.item), 1500); } catch (error) { button.disabled = false; button.classList.remove("is-loading"); button.textContent = button.dataset.originalText || "ОТКРЫТЬ"; toast(error.status === 400 && /Недостаточно/.test(error.message) ? "НЕДОСТАТОЧНО SH" : (error.message || "Не удалось открыть кейс.")); } finally { state.opening = false; }
  }
  function revealCaseItem(item) { $("#opening-stage").classList.add("is-revealed"); window.setTimeout(() => { $("#opening-stage").classList.add("is-hidden"); $("#result-image").src = item.image; $("#result-image").alt = item.name; $("#result-name").textContent = item.name; $("#result-rarity").textContent = item.rarity; $("#result-rarity").className = `rarity-label ${rarityClass(item.rarity)}`; $("#result-value").textContent = item.value; $("#opening-result").classList.remove("is-hidden"); }, 380); }

  async function loadInventory() { try { const result = await window.api.getInventory(); state.inventory = result.items || []; renderInventory(); renderUpgradeInventory(); } catch (error) { toast(error.message || "Не удалось загрузить инвентарь."); } }
  function renderInventory() {
    const visible = state.inventory.filter((item) => state.inventoryFilter === "ALL" || String(item.rarity).toUpperCase() === state.inventoryFilter);
    $("#inventory-count").textContent = `${state.inventory.reduce((sum, item) => sum + item.quantity, 0)} предметов`;
    $("#inventory-empty").classList.toggle("is-hidden", state.inventory.length > 0);
    $("#inventory-grid").innerHTML = visible.map((item) => `<button type="button" class="inventory-card card ${rarityClass(item.rarity)}" data-item-id="${item.id}"><div class="item-image-wrap"><img src="${item.image}" alt="${escapeHtml(item.name)}" /></div><div class="item-card-copy"><strong>${escapeHtml(item.name)}</strong><span class="rarity-label">${item.rarity}</span><small>${item.value} SH · ×${item.quantity}</small></div></button>`).join("");
  }
  async function showItem(itemId) { try { const item = await window.api.getInventoryItem(itemId); $("#item-modal").dataset.itemId = item.id; $("#item-detail-image").src = item.image; $("#item-detail-image").alt = item.name; $("#item-detail-name").textContent = item.name; $("#item-detail-rarity").textContent = item.rarity; $("#item-detail-rarity").className = `rarity-label ${rarityClass(item.rarity)}`; $("#item-detail-value").textContent = item.value; $("#item-detail-quantity").textContent = item.quantity; $("#item-detail-description").textContent = item.description; openModal("item-modal"); } catch (error) { toast(error.message || "Не удалось загрузить предмет."); } }
  function clampSellQuantity(value) { const max = state.sell.item ? state.sell.item.quantity : 1; const parsed = Number(value); if (!Number.isFinite(parsed)) return 1; return Math.min(max, Math.max(1, Math.trunc(parsed))); }
  function renderSellModal() { const item = state.sell.item; if (!item) return; const quantity = clampSellQuantity(state.sell.quantity); state.sell.quantity = quantity; $("#sell-image").src = item.image; $("#sell-image").alt = item.name; $("#sell-name").textContent = item.name; $("#sell-price").textContent = `${item.value} SH / EACH`; $("#sell-quantity").value = quantity; $("#sell-quantity").max = item.quantity; $("#sell-total-value").textContent = `${item.value * quantity} SH`; $("#confirm-sell-button").disabled = state.sell.running; $("#confirm-sell-button").textContent = state.sell.running ? "SELLING..." : "SELL"; }
  async function openSellModal(itemId) { try { const item = await window.api.getInventoryItem(itemId); state.sell.item = item; state.sell.quantity = 1; renderSellModal(); closeModal("item-modal"); openModal("sell-modal"); } catch (error) { toast(error.status === 409 ? "ITEM NO LONGER AVAILABLE" : (error.message || "SALE FAILED")); } }
  function updateSellQuantity(value) { state.sell.quantity = clampSellQuantity(value); renderSellModal(); }
  async function confirmSell() { const item = state.sell.item; if (!item || state.sell.running) return; state.sell.quantity = clampSellQuantity(state.sell.quantity); state.sell.running = true; renderSellModal(); try { const requestId = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now().toString(36)}-${performance.now().toString(36)}`; const result = await window.api.sellItem(item.id, state.sell.quantity, requestId); state.currentUser.balance = result.balance; if (result.total_items_sold !== undefined) state.currentUser.total_items_sold = result.total_items_sold; if (result.total_sh_earned_from_sales !== undefined) state.currentUser.total_sh_earned_from_sales = result.total_sh_earned_from_sales; renderUser(state.currentUser); closeModal("sell-modal"); toast(`ITEM SOLD · +${result.amount} SH`); await loadInventory(); state.sell.item = null; } catch (error) { const message = error.status >= 500 ? "SALE FAILED · TRY AGAIN" : (error.message === "NOT ENOUGH ITEMS" ? "NOT ENOUGH ITEMS" : (error.status === 409 && /ITEM|недоступен/.test(error.message || "") ? "ITEM NO LONGER AVAILABLE" : (error.message || "SALE FAILED"))); toast(message); } finally { state.sell.running = false; renderSellModal(); } }
  async function loadTransactions() { try { const result = await window.api.getTransactions(); $("#transactions-list").innerHTML = result.transactions && result.transactions.length ? result.transactions.map((item) => `<div class="transaction-row"><img src="${item.item_image || "/assets/items/neon-token.svg"}" alt="" /><span><strong>${escapeHtml(item.type)} · ${escapeHtml(item.item_name || "SH") } ×${item.quantity}</strong><small>${item.balance_before} SH → ${item.balance_after} SH</small></span><b>+${item.amount} SH</b></div>`).join("") : `<p class="muted">История транзакций пока пуста.</p>`; } catch (_) { $("#transactions-list").innerHTML = `<p class="muted">История транзакций недоступна.</p>`; } }

  function renderWorldLocations(items) { const target = $("#world-locations"); if (!target) return; target.innerHTML = items.map((item) => `<button type="button" class="world-location card ${item.unlocked ? "" : "is-locked"}" data-world-type="${escapeHtml(item.type)}" ${item.unlocked ? "" : "disabled"}><img src="${item.image}" alt="${escapeHtml(item.name)}" /><span class="badge">${item.unlocked ? "OPEN" : `LVL ${item.unlock_level}`}</span><div class="world-location-copy"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.description)}</small></div></button>`).join(""); }
  async function loadWorld() { try { const result = await window.api.getWorld(); renderWorldLocations(result.locations || []); } catch (_) {} }
  function passiveLabel(system) { return ({ farm: "ФЕРМА", business: "БИЗНЕС", bank: "БАНК" })[system] || system; }
  function renderEarnings() { const data = state.earnings; if (!data) return; $("#earnings-balance").textContent = `◈ ${data.balance} SH`; $("#passive-grid").innerHTML = Object.entries(data.systems || {}).map(([system, item]) => `<article class="passive-card card"><span class="eyebrow">${passiveLabel(system)}</span><h3>LEVEL ${item.level}</h3><div class="passive-meta"><span>${item.income_per_minute} SH / MIN</span><span>${item.unlocked ? "UNLOCKED" : "LOCKED"}</span></div><div class="passive-available">+${item.available} SH</div><div class="passive-actions"><button class="button button-secondary" data-claim-system="${system}" ${item.unlocked ? "" : "disabled"}>CLAIM</button><button class="button button-primary" data-upgrade-system="${system}" ${item.next && item.unlocked ? "" : "disabled"}>${item.next ? `LVL ${item.next.level}` : "MAX"}</button></div>${item.next ? `<small class="muted">UPGRADE ${item.next.upgrade_cost} SH · NEXT ${item.next.income_per_minute}/MIN</small>` : ""}</article>`).join(""); const jobs = [{ kind: "courier", title: "COURIER", description: "Доставь заказ через городскую сцену.", reward: "до 120 SH", cooldown: "60 SEC" }, { kind: "factory", title: "CASE FACTORY", description: "Собери кейс на конвейере.", reward: "до 90 SH", cooldown: "30 SEC" }, { kind: "hunt", title: "ОХОТА ЗА ПЕЧАТЬЮ", description: "Найди печать среди объектов.", reward: "до 75 SH", cooldown: "45 SEC" }]; $("#jobs-grid").innerHTML = jobs.map((job) => `<article class="job-card card"><span class="eyebrow">${job.cooldown}</span><h3>${job.title}</h3><p>${job.description}</p><small class="accent">${job.reward}</small><button class="button button-primary" data-start-job="${job.kind}">START</button></article>`).join(""); }
  async function loadEarnings() { try { state.earnings = await window.api.getEarnings(); renderEarnings(); } catch (error) { toast(error.message || "Не удалось загрузить заработок."); } }
  async function claimSystem(system) { try { const result = await window.api.claimEarnings(system); state.currentUser.balance = result.balance; renderUser(state.currentUser); await loadEarnings(); toast(`+${result.amount} SH`); } catch (error) { toast(error.message || "Не удалось получить доход."); } }
  async function upgradeSystem(system) { try { const result = await window.api.upgradeEarnings(system); state.currentUser.balance = result.balance; renderUser(state.currentUser); await loadEarnings(); toast(`${passiveLabel(system)} LEVEL ${result.level}`); } catch (error) { toast(error.message || "Улучшение недоступно."); } }
  function missionMeta(kind) {
    const key = String(kind || "").toUpperCase();
    return key === "COURIER" ? { title: "COURIER DELIVERY", eyebrow: "COURIER HUB", total: 3, reward: "до 120 SH" } : key === "FACTORY" ? { title: "CASE ASSEMBLY", eyebrow: "CASE FACTORY", total: 4, reward: "до 90 SH" } : { title: "HUNT FOR THE SEAL", eyebrow: "CITY HUNT", total: 1, reward: "до 75 SH" };
  }
  function setMissionProgress(step, total, status) {
    state.mission.step = step;
    state.mission.total = total;
    const bar = $("#mission-progress-bar"); if (bar) bar.style.width = `${Math.min(100, Math.max(0, step / Math.max(1, total) * 100))}%`;
    const count = $("#mission-step-count"); if (count) count.textContent = `${step} / ${total}`;
    const label = $("#mission-status"); if (label) label.textContent = status;
    const complete = $("#mission-complete"); if (complete) complete.disabled = step < total;
  }
  function missionTick() {
    if (!state.activeJob || !state.mission.deadline) return;
    const left = Math.max(0, state.mission.deadline - Date.now());
    const seconds = Math.ceil(left / 1000);
    const time = $("#mission-time"); if (time) time.textContent = seconds;
    if (left <= 0) { state.mission.deadline = 0; toast("ВРЕМЯ ВЫШЛО"); closeModal("mission-modal"); state.activeJob = null; $("#active-job").classList.add("is-hidden"); return; }
    state.mission.timer = window.setTimeout(missionTick, 250);
  }
  function renderCourierMission() {
    const scene = $("#mission-scene");
    scene.className = "mission-scene courier";
    scene.innerHTML = `<div class="courier-sky"></div><div class="courier-cityline"></div><div class="courier-road"></div><div class="courier-lane"></div><div class="mission-hud">COURIER HUB · ORDER #${String(state.activeJob.session_id || "").slice(-4)}</div><div class="courier-car" id="courier-car"></div><div class="courier-point" id="courier-point">◆</div><div class="courier-controls"><button class="button button-secondary" data-mission-action="pickup">ЗАБРАТЬ ЗАКАЗ</button><button class="button button-primary" data-mission-action="drive" disabled>ЕДЕМ</button><button class="button button-primary" data-mission-action="deliver" disabled>ДОСТАВИТЬ</button></div>`;
    setMissionProgress(0, 3, "Забери заказ на складе");
  }
  function renderFactoryMission() {
    const scene = $("#mission-scene"); scene.className = "mission-scene factory-scene";
    scene.innerHTML = `<div class="factory-label">CASE FACTORY · ASSEMBLY LINE</div><div class="factory-arm"></div><div class="factory-belt"></div><button class="factory-part p1" data-factory-step="0">◈</button><button class="factory-part p2" data-factory-step="1">◇</button><button class="factory-part p3" data-factory-step="2">▣</button><button class="factory-part p4" data-factory-step="3">✦</button>`;
    setMissionProgress(0, 4, "Собери детали в правильном порядке");
  }
  function renderHuntMission() {
    const symbols = ["◇","◈","✦","⬡","△","○","▣","⌁","✧"].sort(() => Math.random() - .5);
    const target = Math.floor(Math.random() * symbols.length); state.mission.huntTarget = target;
    const scene = $("#mission-scene"); scene.className = "mission-scene hunt-scene";
    scene.innerHTML = `<div class="hunt-label">HUNT FOR THE SEAL</div><div class="hunt-clue">Найди скрытую печать</div><div class="hunt-grid">${symbols.map((symbol, i) => `<button class="hunt-target" data-hunt-index="${i}">${symbol}</button>`).join("")}</div>`;
    setMissionProgress(0, 1, "Найди печать среди 9 объектов");
  }
  function showActiveJob(session) {
    state.activeJob = { ...session, progress: 0 };
    const meta = missionMeta(session.kind);
    $("#mission-eyebrow").textContent = meta.eyebrow; $("#mission-title").textContent = meta.title;
    state.mission = { kind: String(session.kind || "").toUpperCase(), step: 0, total: meta.total, timer: null, deadline: Date.parse(session.expires_at) || (Date.now() + 60000), courier: 0, factory: 0, huntFound: false, huntTarget: -1 };
    if (state.mission.timer) window.clearTimeout(state.mission.timer);
    if (state.mission.kind === "COURIER") renderCourierMission(); else if (state.mission.kind === "FACTORY") renderFactoryMission(); else renderHuntMission();
    openModal("mission-modal"); missionTick();
    const old = $("#active-job"); if (old) old.classList.add("is-hidden");
  }
  function missionCourier(action) {
    if (!state.activeJob) return;
    if (action === "pickup" && state.mission.step === 0) { state.mission.step = 1; setMissionProgress(1,3,"Заказ получен. Доедь до точки доставки"); $("[data-mission-action='pickup']").disabled=true; $("[data-mission-action='drive']").disabled=false; }
    else if (action === "drive" && state.mission.step === 1) { state.mission.step = 2; const car=$("#courier-car"); if(car) car.style.transform="translateX(165px)"; const point=$("#courier-point"); if(point) point.classList.add("is-done"); setMissionProgress(2,3,"Ты на месте. Передай заказ"); $("[data-mission-action='drive']").disabled=true; $("[data-mission-action='deliver']").disabled=false; }
    else if (action === "deliver" && state.mission.step === 2) { setMissionProgress(3,3,"Заказ доставлен. Можно завершить миссию"); $("[data-mission-action='deliver']").disabled=true; }
  }
  function missionFactory(step) {
    if (Number(step) !== state.mission.step) return;
    const button = document.querySelector(`[data-factory-step="${step}"]`); if (!button) return;
    button.classList.add("is-done"); button.disabled = true; state.mission.step += 1;
    setMissionProgress(state.mission.step,4,state.mission.step >= 4 ? "Кейс собран. Заверши миссию" : `Установи деталь ${state.mission.step + 1} из 4`);
  }
  function missionHunt(index) {
    if (state.mission.huntFound) return;
    const button = document.querySelector(`[data-hunt-index="${index}"]`); if (!button) return;
    if (Number(index) === state.mission.huntTarget) { button.classList.add("is-found"); state.mission.huntFound = true; setMissionProgress(1,1,"Печать найдена. Заверши миссию"); }
    else { button.classList.add("is-wrong"); window.setTimeout(() => button.classList.remove("is-wrong"), 450); toast("Не та печать"); }
  }
  async function completeActiveJob() { if (!state.activeJob) return; const button = $("#complete-job-button"); if (button) button.disabled = true; try { const result = await window.api.completeJob(state.activeJob.session_id); if (result.balance !== undefined) { state.currentUser.balance = result.balance; state.currentUser.xp = result.xp ?? state.currentUser.xp; state.currentUser.level = result.level ?? state.currentUser.level; renderUser(state.currentUser); } toast(result.success ? `+${result.reward} SH` : "MISSION FAILED"); state.activeJob = null; if (state.mission.timer) window.clearTimeout(state.mission.timer); closeModal("mission-modal"); $("#active-job").classList.add("is-hidden"); await loadEarnings(); } catch (error) { if (button) button.disabled = false; toast(error.message || "Задание не завершено."); } }
  function renderMarket(data) {
    state.market = data;
    $("#market-balance").textContent = `◈ ${state.currentUser.balance} SH`;
    const end = Date.parse(data.rotation.ends_at); const timer = $("#market-timer");
    if (state.marketTimer) window.clearTimeout(state.marketTimer);
    const tick = () => { const left = Math.max(0, end - Date.now()); const s = Math.floor(left / 1000); timer.textContent = `NEXT REFRESH · ${String(Math.floor(s / 3600)).padStart(2, "0")}:${String(Math.floor(s / 60) % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`; if (left > 0 && state.currentPage === "market") state.marketTimer = window.setTimeout(tick, 1000); }; tick();
    const query = ($( "#market-search" )?.value || "").trim().toLowerCase(); const sort = $("#market-sort")?.value || "default";
    let offers = [...(data.offers || [])].filter((offer) => !query || String(offer.name).toLowerCase().includes(query) || String(offer.rarity).toLowerCase().includes(query));
    if (sort === "price-asc") offers.sort((a,b) => a.price - b.price); if (sort === "price-desc") offers.sort((a,b) => b.price - a.price);
    $("#market-offers").innerHTML = offers.length ? offers.map((offer) => `<article class="market-offer card"><img src="${offer.image}" alt="${escapeHtml(offer.name)}" /><strong>${escapeHtml(offer.name)}</strong><small>${offer.rarity} · STOCK ${offer.stock}</small><b>${offer.price} SH</b><button class="button button-primary market-buy" data-market-offer="${offer.offer_id}" ${offer.stock < 1 ? "disabled" : ""}>BUY</button></article>`).join("") : `<div class="empty-state"><div class="empty-icon">⌕</div><h2>Ничего не найдено</h2><p class="muted">Попробуй изменить запрос.</p></div>`;
  }
  async function loadMarket() { try { renderMarket(await window.api.getMarket()); } catch (error) { toast(error.message || "Рынок недоступен."); } }
  async function buyMarketOffer(offerId) { try { const requestId = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${performance.now()}`; const result = await window.api.buyMarketOffer(offerId, requestId); state.currentUser.balance = result.balance; state.currentUser.xp = result.xp ?? state.currentUser.xp; state.currentUser.level = result.level ?? state.currentUser.level; renderUser(state.currentUser); toast(`${result.item.name} PURCHASED`); await loadMarket(); await loadInventory(); } catch (error) { toast(error.message || "Покупка не выполнена."); } }
  async function loadProfileExtras() { try { const result = await window.api.getProfile(); const list = $("#profile-achievements-list"); if (list) list.innerHTML = `<div class="profile-stat-row"><span>ACHIEVEMENTS</span><strong>${(result.achievements || []).filter((item) => item.unlocked).length} / ${(result.achievements || []).length}</strong></div>` + (result.achievements || []).map((item) => `<div class="profile-achievement ${item.unlocked ? "is-unlocked" : ""}"><span>${item.unlocked ? "✓" : "○"}</span><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.description)} · ${item.progress}/${item.requirement}</small></div></div>`).join(""); const daily = await window.api.getDaily(); const button = $("#daily-claim-button"); if (button) { button.disabled = daily.claimed; button.textContent = daily.claimed ? "CLAIMED TODAY" : `CLAIM ${daily.reward} SH`; } } catch (_) {} }
  async function loadProfileExtras() { try { const result = await window.api.getProfile(); const profileUser = result.user || {}; const rate = $("#profile-stat-success-rate"); if (rate) rate.textContent = `${profileUser.upgrade_success_rate || 0}%`; const spent = $("#profile-stat-spent"); if (spent) spent.textContent = `${profileUser.total_sh_spent || 0} SH`; const passive = $("#profile-stat-passive"); if (passive) passive.textContent = `${profileUser.farm_level || 1} / ${profileUser.business_level || 0} / ${profileUser.bank_level || 0}`; const list = $("#profile-achievements-list"); if (list) list.innerHTML = `<div class="profile-stat-row"><span>ACHIEVEMENTS</span><strong>${(result.achievements || []).filter((item) => item.unlocked).length} / ${(result.achievements || []).length}</strong></div>` + (result.achievements || []).map((item) => `<div class="profile-achievement ${item.unlocked ? "is-unlocked" : ""}"><span>${item.unlocked ? "✓" : "○"}</span><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.description)} · ${item.progress}/${item.requirement}</small></div></div>`).join(""); const daily = await window.api.getDaily(); const button = $("#daily-claim-button"); if (button) { button.disabled = daily.claimed; button.textContent = daily.claimed ? "CLAIMED TODAY" : `CLAIM ${daily.reward} SH`; } } catch (_) {} }
  async function claimDaily() { const button = $("#daily-claim-button"); if (button) button.disabled = true; try { const result = await window.api.claimDaily(); state.currentUser.balance = result.balance; state.currentUser.xp = result.xp; state.currentUser.level = result.level; renderUser(state.currentUser); toast(`DAILY BONUS · +${result.reward} SH`); await loadProfileExtras(); } catch (error) { toast(error.message || "Ежедневный бонус недоступен."); if (button) button.disabled = false; } }
  function renderUpgradeItem(item, label) { if (!item) return `<span class="slot-label">${label}</span><span class="slot-empty">Выбери предмет</span>`; return `<span class="slot-label">${label}</span><img class="upgrade-item-image" src="${item.image}" alt="${escapeHtml(item.name)}" /><strong>${escapeHtml(item.name)}</strong><span class="${rarityClass(item.rarity)} rarity-label">${item.rarity}</span><b>${item.value} SH</b>`; }
  function renderUpgradeSlots() { $("#upgrade-source-card").innerHTML = renderUpgradeItem(state.upgrade.source, "MY ITEM"); $("#upgrade-target-card").innerHTML = renderUpgradeItem(state.upgrade.target, "TARGET"); const chance = state.upgrade.preview ? Number(state.upgrade.preview.chance) : 0; $("#upgrade-chance").textContent = state.upgrade.preview ? `${chance.toFixed(1)}%` : "—"; const wheelChance=$("#upgrade-wheel-chance"); if(wheelChance) wheelChance.textContent=state.upgrade.preview?`${chance.toFixed(1)}%`:"—"; const wheelStatus=$("#upgrade-wheel-status"); if(wheelStatus) wheelStatus.textContent=state.upgrade.preview?`Зона успеха · ${chance.toFixed(1)}% · риск без комиссии`:"Выбери предмет и цель"; $("#upgrade-chance-bar").style.width = `${chance}%`; $("#upgrade-wheel").style.setProperty("--success-size", `${chance}%`); $("#upgrade-button").disabled = !state.upgrade.preview || state.upgrade.running; $("#upgrade-button").textContent = state.upgrade.preview ? `UPGRADE ${chance.toFixed(1)}%` : "UPGRADE"; }
  function renderUpgradeInventory() { $("#upgrade-inventory-empty").classList.toggle("is-hidden", state.inventory.length > 0); $("#upgrade-inventory-grid").innerHTML = state.inventory.map((item) => `<button type="button" class="inventory-card card premium-item ${rarityClass(item.rarity)} ${state.upgrade.source && state.upgrade.source.id === item.id ? "is-selected" : ""}" data-upgrade-item-id="${item.id}"><div class="item-image-wrap"><img src="${item.image}" alt="${escapeHtml(item.name)}" /></div><div class="item-card-copy"><strong>${escapeHtml(item.name)}</strong><span class="rarity-label">${item.rarity}</span><small>${item.value} SH · ×${item.quantity}</small></div></button>`).join(""); }
  async function selectUpgradeSource(itemId) { const item = state.inventory.find((candidate) => candidate.id === itemId); if (!item) return toast("ITEM NO LONGER AVAILABLE"); state.upgrade.source = item; state.upgrade.target = null; state.upgrade.preview = null; state.upgrade.targets = []; renderUpgradeSlots(); renderUpgradeInventory(); $("#upgrade-recommendations").innerHTML = `<p class="muted">Загружаем цели...</p>`; try { state.upgrade.targets = (await window.api.getUpgradeTargets(item.id)).items || []; renderRecommendations(); } catch (error) { toast(error.message || "Не удалось загрузить цели."); } }
  function renderRecommendations() { const items = state.upgrade.targets.slice(0, 5); $("#upgrade-recommendations").innerHTML = items.length ? items.map((item) => `<button type="button" class="recommendation-card ${rarityClass(item.rarity)}" data-target-id="${item.id}"><span><strong>${escapeHtml(item.name)}</strong><small>${item.value} SH</small></span><b>${Number(item.chance).toFixed(1)}%</b></button>`).join("") : `<p class="muted">Для этого предмета пока нет доступной цели.</p>`; }
  function renderSourcePicker() { $("#upgrade-source-picker").innerHTML = state.inventory.length ? state.inventory.map((item) => `<button type="button" class="picker-item ${rarityClass(item.rarity)}" data-picker-source-id="${item.id}"><img src="${item.image}" alt="" /><span><strong>${escapeHtml(item.name)}</strong><small>${item.rarity} · ${item.value} SH · ×${item.quantity}</small></span></button>`).join("") : `<p class="muted">YOUR INVENTORY IS EMPTY</p>`; openModal("upgrade-source-modal"); }
  function filteredTargets() { const items = state.upgrade.targets.filter((item) => state.upgrade.filter === "ALL" || item.rarity === state.upgrade.filter); return items.sort((a, b) => state.upgrade.sort === "asc" ? a.value - b.value : b.value - a.value); }
  function renderTargetPicker() { const items = filteredTargets(); $("#upgrade-target-picker").innerHTML = items.length ? items.map((item) => `<button type="button" class="picker-item ${rarityClass(item.rarity)}" data-picker-target-id="${item.id}"><img src="${item.image}" alt="" /><span><strong>${escapeHtml(item.name)}</strong><small>${item.rarity} · ${item.value} SH · ${Number(item.chance).toFixed(1)}%</small></span></button>`).join("") : `<p class="muted">Нет предметов дороже исходного.</p>`; }
  async function showTargetPicker() { if (!state.upgrade.source) return toast("Сначала выбери исходный предмет"); if (!state.upgrade.targets.length) { try { state.upgrade.targets = (await window.api.getUpgradeTargets(state.upgrade.source.id)).items || []; } catch (error) { return toast(error.message || "TARGET NO LONGER AVAILABLE"); } } renderTargetPicker(); openModal("upgrade-target-modal"); }
  async function selectUpgradeTarget(itemId) { const target = state.upgrade.targets.find((item) => item.id === itemId); if (!target || !state.upgrade.source) return; state.upgrade.target = target; state.upgrade.preview = null; renderUpgradeSlots(); closeModal("upgrade-target-modal"); try { state.upgrade.preview = await window.api.previewUpgrade(state.upgrade.source.id, target.id); state.upgrade.target = state.upgrade.preview.target; state.upgrade.source = state.upgrade.preview.source; renderUpgradeSlots(); } catch (error) { state.upgrade.target = null; renderUpgradeSlots(); toast(error.message || "TARGET NO LONGER AVAILABLE"); } }
  function showConfirmation() { if (!state.upgrade.preview) return; const { source, target, chance } = state.upgrade.preview; $("#confirm-source").innerHTML = `<img src="${source.image}" alt="" /><span>${escapeHtml(source.name)}<small>${source.value} SH</small></span>`; $("#confirm-target").innerHTML = `<img src="${target.image}" alt="" /><span>${escapeHtml(target.name)}<small>${target.value} SH</small></span>`; $("#confirm-chance").textContent = `${Number(chance).toFixed(1)}%`; openModal("upgrade-confirm-modal"); }
  function setWheelAnimation(result) { const chance = Math.max(1, Math.min(95, Number(result.chance) || 0)); const successDeg = chance * 3.6; const finalSector = result.result === "SUCCESS" ? Math.max(3, successDeg * 0.5) : Math.min(357, successDeg + Math.max(3, (360 - successDeg) * 0.5)); const end = 5 * 360 + finalSector; const wheel = $("#upgrade-wheel"); wheel.style.setProperty("--pointer-end", `${end}deg`); const pointer = $("#upgrade-pointer"); pointer.classList.remove("is-spinning"); pointer.style.transform="translate(-50%,-100%) rotate(0deg)"; void pointer.offsetWidth; pointer.classList.add("is-spinning"); }
  function showUpgradeResult(result) { const success = result.result === "SUCCESS"; $("#upgrade-result-box").classList.toggle("upgrade-failed", !success); $("#upgrade-result-icon").textContent = success ? "✓" : "×"; $("#upgrade-result-title").textContent = success ? "UPGRADE SUCCESS" : "UPGRADE FAILED"; $("#upgrade-result-name").textContent = success ? result.target.name : "SOURCE ITEM LOST"; $("#upgrade-result-route").innerHTML = `<img src="${result.source.image}" alt="" /><span>→</span><img src="${result.target.image}" alt="" />`; $("#upgrade-result-description").textContent = success ? `${result.target.name} добавлен в инвентарь.` : `${result.source.name} больше нет в инвентаре.`; openModal("upgrade-result-modal"); }
  async function executeSelectedUpgrade() { if (!state.upgrade.preview || state.upgrade.running) return; state.upgrade.running = true; $("#confirm-upgrade-button").disabled = true; try { const requestId = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now().toString(36)}-${performance.now().toString(36)}`; const result = await window.api.executeUpgrade(state.upgrade.source.id, state.upgrade.target.id, requestId); closeModal("upgrade-confirm-modal"); setWheelAnimation(result); window.setTimeout(() => showUpgradeResult(result), 2450); state.currentUser.xp = result.xp; state.currentUser.level = result.level; renderUser(state.currentUser); await loadInventory(); await loadUpgradeHistory(); state.upgrade.source = null; state.upgrade.target = null; state.upgrade.preview = null; } catch (error) { const message = error.status >= 500 ? "UPGRADE FAILED TO START" : (error.status === 409 && /недоступен|доступен/.test(error.message) ? "ITEM NO LONGER AVAILABLE" : (error.message || "UPGRADE FAILED TO START")); toast(message); } finally { state.upgrade.running = false; $("#confirm-upgrade-button").disabled = false; renderUpgradeSlots(); } }
  function renderUpgradeHistory(items) { $("#upgrade-history").innerHTML = items.length ? items.map((item) => `<div class="history-row"><div class="history-images"><img src="${item.source_image}" alt="" /><span>→</span><img src="${item.target_image}" alt="" /></div><div class="history-copy"><strong>${escapeHtml(item.source_name)} → ${escapeHtml(item.target_name)}</strong><small>${item.source_value} SH → ${item.target_value} SH · ${Number(item.chance).toFixed(1)}%</small></div><b class="history-result ${item.result === "SUCCESS" ? "success" : "fail"}">${item.result}</b></div>`).join("") : `<p class="muted">История пока пуста.</p>`; }
  async function loadUpgradeHistory() { try { renderUpgradeHistory((await window.api.getUpgradeHistory()).transactions || []); } catch (_) { renderUpgradeHistory([]); } }
  async function loadUpgrade() { await loadInventory(); await loadUpgradeHistory(); renderUpgradeSlots(); }
  async function loadApp() { $("#retry-button").disabled = true; try { await window.api.health(); renderUser(await window.api.getMe()); await loadCases(); await loadWorld(); showApp(); } catch (error) { showError(error.status === 401 ? "Откройте SHAMA WORLD через Telegram, чтобы продолжить." : "Не удалось подключиться к SHAMA WORLD."); } finally { $("#retry-button").disabled = false; } }

  document.addEventListener("DOMContentLoaded", () => {
    setTelegramReady(); $("#retry-button").addEventListener("click", loadApp);
    $("#market-search").addEventListener("input", () => { if (state.market) renderMarket(state.market); });
    $("#market-sort").addEventListener("change", () => { if (state.market) renderMarket(state.market); }); $("#open-case-button").addEventListener("click", openSelectedCase); $("#saved-button").addEventListener("click", () => { closeModal("opening-modal"); loadInventory(); }); $("#upgrade-source-card").addEventListener("click", renderSourcePicker); $("#upgrade-target-card").addEventListener("click", showTargetPicker); $("#upgrade-button").addEventListener("click", showConfirmation); $("#confirm-upgrade-button").addEventListener("click", executeSelectedUpgrade); $("#sell-minus").addEventListener("click", () => updateSellQuantity(state.sell.quantity - 1)); $("#sell-plus").addEventListener("click", () => updateSellQuantity(state.sell.quantity + 1)); $("#sell-max").addEventListener("click", () => updateSellQuantity(state.sell.item ? state.sell.item.quantity : 1)); $("#sell-quantity").addEventListener("input", (event) => updateSellQuantity(event.target.value)); $("#confirm-sell-button").addEventListener("click", confirmSell); $("#target-sort").addEventListener("change", (event) => { state.upgrade.sort = event.target.value; renderTargetPicker(); }); $("#daily-claim-button").addEventListener("click", claimDaily);
    document.addEventListener("click", (event) => { const nav = event.target.closest("[data-nav]"); if (nav) renderPage(nav.dataset.nav); const world = event.target.closest("[data-world-type]"); if (world) { const destination = { market: "market", farm: "earn", business: "earn", bank: "earn", courier: "earn", factory: "earn" }[world.dataset.worldType]; if (destination) renderPage(destination); } const jobStep = event.target.closest("[data-job-step]"); if (jobStep) advanceJobStep(jobStep.dataset.jobStep); const missionAction = event.target.closest("[data-mission-action]"); if (missionAction) missionCourier(missionAction.dataset.missionAction); const factoryPart = event.target.closest("[data-factory-step]"); if (factoryPart) missionFactory(factoryPart.dataset.factoryStep); const huntTarget = event.target.closest("[data-hunt-index]"); if (huntTarget) missionHunt(huntTarget.dataset.huntIndex); const card = event.target.closest("[data-case-id]"); if (card) showCase(Number(card.dataset.caseId)); const item = event.target.closest("[data-item-id]"); if (item) showItem(Number(item.dataset.itemId)); const upgradeItem = event.target.closest("[data-upgrade-item-id]"); if (upgradeItem) selectUpgradeSource(Number(upgradeItem.dataset.upgradeItemId)); const pickerSource = event.target.closest("[data-picker-source-id]"); if (pickerSource) { closeModal("upgrade-source-modal"); selectUpgradeSource(Number(pickerSource.dataset.pickerSourceId)); } const pickerTarget = event.target.closest("[data-picker-target-id]"); if (pickerTarget) selectUpgradeTarget(Number(pickerTarget.dataset.pickerTargetId)); const recommendation = event.target.closest("[data-target-id]"); if (recommendation) selectUpgradeTarget(Number(recommendation.dataset.targetId)); const filter = event.target.closest("[data-rarity-filter]"); if (filter) { state.upgrade.filter = filter.dataset.rarityFilter; document.querySelectorAll("[data-rarity-filter]").forEach((button) => button.classList.toggle("is-active", button === filter)); renderTargetPicker(); }
    const inventoryFilter = event.target.closest("[data-inventory-filter]"); if (inventoryFilter) { state.inventoryFilter = inventoryFilter.dataset.inventoryFilter; document.querySelectorAll("[data-inventory-filter]").forEach((button) => button.classList.toggle("is-active", button === inventoryFilter)); renderInventory(); }
    const close = event.target.closest("[data-close-modal]"); if (close) closeModal(close.dataset.closeModal); if (event.target.closest("[data-action='chances']")) showChances(); const sellAction = event.target.closest("[data-action='sell-item']"); if (sellAction) openSellModal(Number($("#item-modal").dataset.itemId)); const upgradeAction = event.target.closest("[data-action='upgrade-item']"); if (upgradeAction) { const itemId = Number($("#item-modal").dataset.itemId); closeModal("item-modal"); renderPage("upgrade"); selectUpgradeSource(itemId); } const claim = event.target.closest("[data-claim-system]"); if (claim) claimSystem(claim.dataset.claimSystem); const systemUpgrade = event.target.closest("[data-upgrade-system]"); if (systemUpgrade) upgradeSystem(systemUpgrade.dataset.upgradeSystem); const start = event.target.closest("[data-start-job]"); if (start) startJob(start.dataset.startJob); const offer = event.target.closest("[data-market-offer]"); if (offer) buyMarketOffer(Number(offer.dataset.marketOffer)); if (event.target.closest("#complete-job-button")) completeActiveJob(); if (event.target.closest("#mission-complete")) completeActiveJob(); if (event.target.closest("[data-coming-soon]")) toast("Функция будет доступна на следующем этапе."); if (event.target.classList.contains("modal-backdrop")) event.target.classList.add("is-hidden"); });
    loadApp();
  });
}());
