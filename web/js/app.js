(function () {
  "use strict";

  const state = {
    currentUser: null,
    currentPage: "world",
    navigationId: 0,
    cases: [],
    selectedCase: null,
    lastOpenedCaseId: null,
    inventory: [],
    opening: false,
    upgrade: { source: null, target: null, preview: null, targets: [], filter: "ALL", sort: "asc", running: false, animationResult: null },
    sell: { item: null, quantity: 1, running: false },
    earnings: null,
    enterprises: null,
    enterpriseView: null,
    earningsFocus: null,
    market: null,
    activeJob: null,
    mission: { kind: null, step: 0, total: 0, timer: null, deadline: 0, courier: 0, factory: 0, huntFound: false },
    inventoryFilter: "ALL",
    marketTimer: null,
    caseScrollTop: 0,
    pendingActions: new Set(),
    operationRequestIds: new Map(),
    dailyClaiming: false,
    jobStarting: false,
    jobCompleting: false,
  };
  const pageNames = {
    profile: ["ПРОФИЛЬ", "PLAYER STATS", ""],
    market: ["SH MARKET", "MAC MARKET", ""],
  };
  const $ = (selector) => document.querySelector(selector);
  const ASSET_VERSION = "2026-09-29-luxury3";
  const THEME_STORAGE_KEY = "shama-world-theme";
  function savedTheme() {
    try { return localStorage.getItem(THEME_STORAGE_KEY) === "white" ? "white" : "dark"; }
    catch (_) { return "dark"; }
  }
  let activeTheme = savedTheme();
  document.documentElement.dataset.theme = activeTheme;

  function applyTheme(theme, persist = true) {
    activeTheme = theme === "white" ? "white" : "dark";
    document.documentElement.dataset.theme = activeTheme;
    document.querySelectorAll("[data-theme-select]").forEach((button) => {
      const selected = button.dataset.themeSelect === activeTheme;
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("is-active", selected);
    });
    const color = activeTheme === "white" ? "#f5f3ed" : "#0b0b0a";
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) metaTheme.content = color;
    if (window.Telegram?.WebApp?.setHeaderColor) window.Telegram.WebApp.setHeaderColor(color);
    if (persist) {
      try { localStorage.setItem(THEME_STORAGE_KEY, activeTheme); } catch (_) { /* Private browsing may disable storage. */ }
    }
  }
  function assetUrl(path) {
    if (!path) return "/assets/items/sh-coins.jpg?v=" + ASSET_VERSION;
    return path.startsWith("/assets/") && !path.includes("?") ? `${path}?v=${ASSET_VERSION}` : path;
  }
  document.addEventListener("error", (event) => {
    const img = event.target;
    if (!(img instanceof HTMLImageElement)) return;
    const src = img.getAttribute("src") || "";
    if (img.dataset.fallbackApplied) return;
    img.dataset.fallbackApplied = "1";
    const fallback = src.startsWith("/assets/cases/")
      ? "/assets/cases/starter.jpg"
      : src.startsWith("/assets/world/")
        ? "/assets/world/shama-world-city.png"
        : "/assets/items/neon-token.svg";
    img.src = `${fallback}?v=${ASSET_VERSION}`;
  }, true);

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[char]));
  const rarityClass = (rarity) => `rarity-${String(rarity || "common").toLowerCase()}`;

  function setTelegramReady() {
    if (!window.Telegram || !window.Telegram.WebApp) return;
    window.Telegram.WebApp.ready(); window.Telegram.WebApp.expand();
    if (window.Telegram.WebApp.setHeaderColor) window.Telegram.WebApp.setHeaderColor(activeTheme === "white" ? "#f5f3ed" : "#0b0b0a");
  }
  function initials(user) { return `${(user.first_name || "S")[0]}${(user.last_name || "W")[0]}`.toUpperCase(); }
  function closeModal(id, force = false) {
    const el = document.getElementById(id);
    if (!el) return;
    if ((id === "opening-modal" || (id === "case-modal" && !force)) && state.opening) return;
    el.classList.add("is-hidden");
    el.setAttribute("aria-hidden", "true");
    if (id === "item-modal") delete el.dataset.itemId;
    if (id === "opening-modal") {
      document.body.classList.remove("case-result-open");
      document.body.style.removeProperty("top");
      window.requestAnimationFrame(() => window.scrollTo(0, state.caseScrollTop));
      state.selectedCase = null;
      const stage = $("#opening-stage");
      const result = $("#opening-result");
      const close = $("#opening-close");
      if (stage) stage.classList.remove("is-hidden", "is-revealed");
      if (result) result.classList.add("is-hidden");
      if (close) close.classList.add("is-hidden");
      const reel = $("#opening-reel");
      if (reel) { reel.style.transition = "none"; reel.style.transform = "translate3d(0,0,0)"; }
    }
    if (id === "case-modal" && !force) state.selectedCase = null;
    if (id === "upgrade-result-modal") resetUpgradeWheel();
  }
  function openModal(id) { const el = document.getElementById(id); if (el) { if (id === "opening-modal") document.body.classList.remove("case-result-open"); el.classList.remove("is-hidden"); el.setAttribute("aria-hidden","false"); } }
  function closeAllModals() {
    document.querySelectorAll(".modal-backdrop").forEach((el) => closeModal(el.id));
  }
  function toast(message, tone) { const element = $("#toast"); element.textContent = message; element.dataset.tone = tone || (/failed|error|недостат|не удалось|недоступ|не выполн|ошиб|no longer/i.test(String(message)) ? "error" : "success"); element.classList.remove("is-hidden"); window.clearTimeout(toast.timer); toast.timer = window.setTimeout(() => element.classList.add("is-hidden"), 2800); }
  function showError(message) { $("#loading-screen").classList.add("is-hidden"); $("#app").classList.add("is-hidden"); $("#error-screen").classList.remove("is-hidden"); $("#error-message").textContent = message; }
  function showApp() { $("#loading-screen").classList.add("is-hidden"); $("#error-screen").classList.add("is-hidden"); $("#app").classList.remove("is-hidden"); }

  function renderUser(user) {
    state.currentUser = user;
    const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ") || "Игрок SHAMA";
    $("#welcome-name").textContent = user.first_name || "игрок";
    $("#profile-username").textContent = user.username ? `@${user.username}` : "Игрок SHAMA";
    $("#profile-full-name").textContent = fullName;
    const legacyLevel = $("#profile-level"); if (legacyLevel) legacyLevel.textContent = user.level;
    const legacyBalance = $("#profile-balance"); if (legacyBalance) legacyBalance.textContent = user.balance;
    $("#profile-xp").textContent = user.xp;
    $("#xp-progress").style.width = `${Math.min(100, user.xp % 100)}%`; $("#profile-xp-label").textContent = Math.min(100, user.xp % 100);
    $("#profile-avatar").textContent = initials(user); $("#profile-avatar-large").textContent = initials(user); $("#cases-balance").textContent = `${user.balance} SH`;
    const pageAvatar = $("#profile-page-avatar"); if (pageAvatar) pageAvatar.textContent = initials(user);
    const pageUsername = $("#profile-page-username"); if (pageUsername) pageUsername.textContent = user.username ? `@${user.username}` : "Игрок SHAMA";
    const pageFullName = $("#profile-page-full-name"); if (pageFullName) pageFullName.textContent = fullName;
    const pageLevel = $("#profile-page-level"); if (pageLevel) pageLevel.textContent = user.level;
    const pageBalance = $("#profile-page-balance"); if (pageBalance) pageBalance.textContent = `${user.balance} SH`;
    const pageXp = $("#profile-page-xp"); if (pageXp) pageXp.textContent = `${Math.min(100, user.xp % 100)} / 100`;
    const pageProgress = $("#profile-page-progress"); if (pageProgress) pageProgress.style.width = `${Math.min(100, user.xp % 100)}%`;
    const nextXp = $("#profile-next-xp"); if (nextXp) nextXp.textContent = `Ещё ${100 - (user.xp % 100)} XP · LVL ${user.level + 1}`;
    const activityBalance = $("#activity-balance"); if (activityBalance) activityBalance.textContent = `${user.balance} SH`;
    const activityLevel = $("#activity-level"); if (activityLevel) activityLevel.textContent = `LVL ${user.level}`;
    ["#global-balance", "#inventory-balance", "#upgrade-balance", "#profile-stat-balance"].forEach((selector) => { const element = $(selector); if (element) element.textContent = `◈ ${user.balance} SH`; });
    const statLevel = $("#profile-stat-level"); if (statLevel) statLevel.textContent = `${user.level} / ${user.xp} XP`;
    const statCases = $("#profile-stat-cases"); if (statCases) statCases.textContent = user.cases_opened;
    const statCollected = $("#profile-stat-collected"); if (statCollected) statCollected.textContent = user.items_collected;
    const statUpgrades = $("#profile-stat-upgrades"); if (statUpgrades) statUpgrades.textContent = user.upgrades_total;
    const statSold = $("#profile-stat-sold"); if (statSold) statSold.textContent = user.total_items_sold;
    const statEarned = $("#profile-stat-earned"); if (statEarned) statEarned.textContent = `${user.total_sh_earned_from_sales} SH`;
    const worldLevel = $("#world-scene-level"); if (worldLevel) worldLevel.textContent = user.level;
    const xpProgress = Math.min(100, user.xp % 100);
    const worldProgress = $("#world-scene-xp-progress"); if (worldProgress) worldProgress.style.width = `${xpProgress}%`;
    const worldXp = $("#world-scene-xp-label"); if (worldXp) worldXp.textContent = `${user.xp % 100} / 100 XP · ${100 - xpProgress} ДО УРОВНЯ ${user.level + 1}`;
    ["#global-balance", "#inventory-balance", "#upgrade-balance"].forEach((selector) => { const element = $(selector); if (element) { element.classList.remove("balance-pulse"); void element.offsetWidth; element.classList.add("balance-pulse"); } });
  }
  function resetUpgradeState() {
    state.upgrade.source = null;
    state.upgrade.target = null;
    state.upgrade.preview = null;
    state.upgrade.targets = [];
    state.upgrade.filter = "ALL";
    state.upgrade.sort = "asc";
    if (!state.upgrade.running) state.upgrade.animationResult = null;
    const rec = $("#upgrade-recommendations");
    if (rec) rec.innerHTML = `<p class="muted">Сначала выбери исходный предмет.</p>`;
    const targetSort = $("#target-sort");
    if (targetSort) targetSort.value = "asc";
    document.querySelectorAll("[data-rarity-filter]").forEach((button) => button.classList.toggle("is-active", button.dataset.rarityFilter === "ALL"));
    renderUpgradeInventory();
    renderUpgradeSlots();
}

  async function renderPage(page) {
    const navigationId = ++state.navigationId;
    closeAllModals();
    if (page !== "upgrade") resetUpgradeState();
    const pages = ["world", "cases", "earn", "inventory", "upgrade", "market", "profile"];
    pages.forEach((name) => { const element = document.getElementById(`page-${name}`); if (element) element.classList.toggle("is-active", name === page); });
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("is-active", item.dataset.nav === page));
    state.currentPage = page;
    if (page === "cases") await loadCases();
    if (page === "inventory") await loadInventory();
    if (page === "upgrade") await loadUpgrade();
    if (page === "earn") await loadEarnings();
    if (page === "market") await loadMarket();
    if (page === "profile") { await loadTransactions(); await loadProfileExtras(); }
    if (navigationId === state.navigationId) window.scrollTo({ top: 0, behavior: "smooth" });
    if (page === "earn" && state.earningsFocus === "factory") {
      state.earningsFocus = null;
      requestAnimationFrame(() => $("#jobs-grid")?.scrollIntoView({ behavior: "smooth", block: "center" }));
    }
  }

  function renderCases() {
    $("#cases-grid").innerHTML = state.cases.map((item) => { const price = Number(item.price) || 0; const tier = price >= 5000 ? "mythic" : price >= 2500 ? "legendary" : price >= 1000 ? "epic" : price >= 500 ? "rare" : price >= 250 ? "uncommon" : "common"; return `<button type="button" class="case-card card case-tier-${tier}" data-case-id="${item.id}" data-tilt-card><div class="case-art"><img src="${assetUrl(item.image)}" alt="${escapeHtml(item.name)}" loading="lazy" decoding="async" /><span class="case-shine"></span><span class="case-tier-badge">${tier.toUpperCase()}</span><span class="case-art-particles" aria-hidden="true"></span></div><div class="case-card-overlay"><span class="eyebrow">CASE DROP</span><strong>${escapeHtml(item.name)}</strong><div class="case-card-bottom"><span class="case-card-price">${fmtMoney(price)} SH</span><span class="case-open-hint">ОТКРЫТЬ&nbsp;→</span></div></div></button>`; }).join("");
    $("#cases-balance").textContent = `${state.currentUser ? state.currentUser.balance : "—"} SH`;
    const count = $("#cases-count"); if (count) count.textContent = state.cases.length;
  }
  async function loadCases() { if (state.cases.length) return renderCases(); try { state.cases = (await window.api.getCases()).cases || []; renderCases(); } catch (error) { toast(error.message || "Не удалось загрузить кейсы."); } }
  function chancePercent(chance) { return `${(Number(chance) * 100).toFixed(Number(chance) < 0.1 ? 1 : 0)}%`; }
  async function showCase(caseId) {
    if (state.opening) return;
    try { state.selectedCase = await window.api.getCase(caseId); const item = state.selectedCase; $("#case-detail-image").src = assetUrl(item.image); $("#case-detail-image").alt = item.name; $("#case-detail-name").textContent = item.name; $("#case-detail-description").textContent = item.description; $("#case-detail-price").textContent = `${item.price} SH`; $("#open-case-button").textContent = `ОТКРЫТЬ ЗА ${item.price} SH`; $("#open-case-button").disabled = false; openModal("case-modal"); } catch (error) { toast(error.message || "Не удалось загрузить кейс."); }
  }
  function showChances() {
    if (!state.selectedCase) return; $("#chances-list").innerHTML = state.selectedCase.drops.map((item) => `<div class="chance-row"><img src="${assetUrl(item.image)}" alt="" /><div class="chance-info"><strong>${escapeHtml(item.name)}</strong><span class="${rarityClass(item.rarity)}">${item.rarity}</span></div><div class="chance-value"><strong>${chancePercent(item.chance)}</strong><small>${item.value} SH</small></div></div>`).join(""); openModal("chances-modal");
  }
  async function openSelectedCase() {
    if (!state.selectedCase || state.opening) return; const button = $("#open-case-button"); button.disabled = true; state.opening = true; state.lastOpenedCaseId = state.selectedCase.id; button.classList.add("is-loading"); button.dataset.originalText = button.textContent; button.textContent = "ОТКРЫВАЕМ...";
    try {
      const requestId = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now().toString(36)}-${performance.now().toString(36)}`;
      const result = await window.api.openCase(state.selectedCase.id, requestId);
      state.currentUser.balance = result.balance; state.currentUser.xp = result.xp; state.currentUser.level = result.level; renderUser(state.currentUser);
      closeModal("case-modal", true);
      $("#opening-stage").classList.remove("is-hidden"); $("#opening-stage").classList.remove("is-revealed");
      $("#opening-result").classList.add("is-hidden"); $("#opening-case-image").src = assetUrl(state.selectedCase.image);
      openModal("opening-modal");
      await startCaseOpeningAnimation(result.item, state.selectedCase.drops || []);
    } catch (error) { button.disabled = false; button.classList.remove("is-loading"); button.textContent = button.dataset.originalText || "ОТКРЫТЬ"; toast(error.status === 400 && /Недостаточно/.test(error.message) ? "НЕДОСТАТОЧНО SH" : (error.message || "Не удалось открыть кейс.")); } finally { state.opening = false; }
  }
  function buildOpeningReel(items, winner) {
    const reel = $("#opening-reel"); if (!reel) return 0;
    const pool = Array.isArray(items) && items.length ? items : [winner];
    const count = 34, winnerIndex = 29;
    const cards = [];
    for (let i = 0; i < count; i++) {
      const item = i === winnerIndex ? winner : pool[Math.floor(Math.random() * pool.length)];
      cards.push(`<div class="opening-reel-card ${rarityClass(item.rarity)} ${i === winnerIndex ? "is-server-winner" : ""}" data-reel-index="${i}"><img src="${assetUrl(item.image)}" alt=""><span>${escapeHtml(item.name)}</span><small>${escapeHtml(item.rarity)}</small></div>`);
    }
    reel.innerHTML = cards.join("");
    return winnerIndex;
  }

  async function startCaseOpeningAnimation(winner, drops) {
    const stage = $("#opening-stage"), reel = $("#opening-reel"), progress = $(".opening-progress span"), status = $("#opening-status"), countdown = $("#opening-countdown");
    if (!stage || !reel) return revealCaseItem(winner);
    const winnerIndex = buildOpeningReel(drops, winner);
    const cards = reel.querySelectorAll(".opening-reel-card");
    const card = cards[winnerIndex];
    const wrap = reel.parentElement;
    const center = wrap.clientWidth / 2;
    const target = card.offsetLeft + card.offsetWidth / 2;
    const finalX = Math.round(center - target);
    reel.style.transition = "none";
    reel.style.transform = "translate3d(0,0,0)";
    reel.classList.remove("is-running");
    void reel.offsetWidth;
    reel.classList.add("is-running");
    reel.style.transition = "transform 3.5s cubic-bezier(.08,.72,.13,1)";
    requestAnimationFrame(() => { reel.style.transform = `translate3d(${finalX}px,0,0)`; });
    if (progress) { progress.style.width = "0%"; requestAnimationFrame(() => { progress.style.width = "100%"; }); }
    const started = performance.now(), duration = 3500;
    status.textContent = "ПРЕДМЕТЫ ВРАЩАЮТСЯ";
    const tick = (now) => {
      const left = Math.max(0, duration - (now - started));
      if (countdown) countdown.textContent = (left / 1000).toFixed(1);
      if (left > 0) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    await new Promise((resolve) => window.setTimeout(resolve, duration));
    reel.classList.remove("is-running");
    card.classList.add("is-landed");
    await revealCaseItem(winner);
  }

  function revealCaseItem(item) {
    const stage = $("#opening-stage");
    const result = $("#opening-result");
    const resultImage = $("#result-image");
    if (!stage || !result || !resultImage) return Promise.resolve();

    stage.classList.add("is-revealed");
    $("#opening-status").textContent = "ДРОП ПОЛУЧЕН";
    return new Promise((resolve) => window.setTimeout(() => {
      stage.classList.add("is-hidden");
      result.classList.remove("is-hidden");
      result.dataset.rarity = String(item.rarity || "common").toLowerCase();
      result.classList.remove("is-celebrating");
      void result.offsetWidth;
      result.classList.add("is-celebrating");
      const close = $("#opening-close");
      if (close) close.classList.remove("is-hidden");
      resultImage.src = assetUrl(item.image);
      resultImage.alt = item.name;
      resultImage.dataset.fallbackApplied = "";
      $("#result-name").textContent = item.name;
      $("#result-rarity").textContent = item.rarity;
      $("#result-rarity").className = `rarity-label ${rarityClass(item.rarity)}`;
      $("#result-value").textContent = item.value;
      state.opening = false;
      // Keep the result inside the modal instead of allowing the page to
      // resize/scroll underneath the Telegram viewport.
      state.caseScrollTop = window.scrollY;
      document.body.style.setProperty("top", `-${state.caseScrollTop}px`, "important");
      document.body.classList.add("case-result-open");
      resolve();
    }, 520));
  }


  async function loadInventory() { try { const result = await window.api.getInventory(); state.inventory = result.items || []; renderInventory(); renderUpgradeInventory(); } catch (error) { toast(error.message || "Не удалось загрузить инвентарь."); } }
  function renderInventory() {
    const visible = state.inventory.filter((item) => state.inventoryFilter === "ALL" || String(item.rarity).toUpperCase() === state.inventoryFilter);
    $("#inventory-count").textContent = `${state.inventory.reduce((sum, item) => sum + item.quantity, 0)} предметов`;
    $("#inventory-empty").classList.toggle("is-hidden", state.inventory.length > 0);
    $("#inventory-grid").innerHTML = visible.map((item) => `<button type="button" class="inventory-card card ${rarityClass(item.rarity)}" data-item-id="${item.id}" data-tilt-card><div class="item-image-wrap"><img src="${assetUrl(item.image)}" alt="${escapeHtml(item.name)}" loading="lazy" decoding="async" /></div><div class="item-card-copy"><strong>${escapeHtml(item.name)}</strong><span class="rarity-label">${item.rarity}</span><small>${fmtMoney(item.value)} SH · ×${item.quantity}</small></div></button>`).join("");
  }
  async function showItem(itemId) { try { closeModal("upgrade-result-modal"); closeModal("upgrade-confirm-modal"); closeModal("upgrade-source-modal"); closeModal("upgrade-target-modal"); const item = await window.api.getInventoryItem(itemId); $("#item-modal").dataset.itemId = item.id; $("#item-detail-image").src = assetUrl(item.image); $("#item-detail-image").alt = item.name; $("#item-detail-name").textContent = item.name; $("#item-detail-rarity").textContent = item.rarity; $("#item-detail-rarity").className = `rarity-label ${rarityClass(item.rarity)}`; $("#item-detail-value").textContent = item.value; $("#item-detail-quantity").textContent = item.quantity; $("#item-detail-description").textContent = item.description; openModal("item-modal"); } catch (error) { toast(error.message || "Не удалось загрузить предмет."); } }
  function clampSellQuantity(value) { const max = state.sell.item ? state.sell.item.quantity : 1; const parsed = Number(value); if (!Number.isFinite(parsed)) return 1; return Math.min(max, Math.max(1, Math.trunc(parsed))); }
  function renderSellModal() { const item = state.sell.item; if (!item) return; const quantity = clampSellQuantity(state.sell.quantity); state.sell.quantity = quantity; $("#sell-image").src = assetUrl(item.image); $("#sell-image").alt = item.name; $("#sell-name").textContent = item.name; $("#sell-price").textContent = `${item.value} SH / EACH`; $("#sell-quantity").value = quantity; $("#sell-quantity").max = item.quantity; $("#sell-total-value").textContent = `${item.value * quantity} SH`; $("#confirm-sell-button").disabled = state.sell.running; $("#confirm-sell-button").textContent = state.sell.running ? "SELLING..." : "SELL"; }
  async function openSellModal(itemId) { try { const item = await window.api.getInventoryItem(itemId); state.sell.item = item; state.sell.quantity = 1; renderSellModal(); closeModal("item-modal"); openModal("sell-modal"); } catch (error) { toast(error.status === 409 ? "ITEM NO LONGER AVAILABLE" : (error.message || "SALE FAILED")); } }
  function updateSellQuantity(value) { state.sell.quantity = clampSellQuantity(value); renderSellModal(); }
  async function confirmSell() { const item = state.sell.item; if (!item || state.sell.running) return; state.sell.quantity = clampSellQuantity(state.sell.quantity); state.sell.running = true; renderSellModal(); try { const requestId = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now().toString(36)}-${performance.now().toString(36)}`; const result = await window.api.sellItem(item.id, state.sell.quantity, requestId); state.currentUser.balance = result.balance; if (result.total_items_sold !== undefined) state.currentUser.total_items_sold = result.total_items_sold; if (result.total_sh_earned_from_sales !== undefined) state.currentUser.total_sh_earned_from_sales = result.total_sh_earned_from_sales; renderUser(state.currentUser); closeModal("sell-modal"); toast(`ITEM SOLD · +${result.amount} SH`); await loadInventory(); state.sell.item = null; } catch (error) { const message = error.status >= 500 ? "SALE FAILED · TRY AGAIN" : (error.message === "NOT ENOUGH ITEMS" ? "NOT ENOUGH ITEMS" : (error.status === 409 && /ITEM|недоступен/.test(error.message || "") ? "ITEM NO LONGER AVAILABLE" : (error.message || "SALE FAILED"))); toast(message); } finally { state.sell.running = false; renderSellModal(); } }
  async function loadTransactions() { try { const result = await window.api.getTransactions(); $("#transactions-list").innerHTML = result.transactions && result.transactions.length ? result.transactions.map((item) => `<div class="transaction-row"><img src="${item.item_image || "/assets/items/neon-token.svg"}" alt="" /><span><strong>${escapeHtml(item.type)} · ${escapeHtml(item.item_name || "SH") } ×${item.quantity}</strong><small>${item.balance_before} SH → ${item.balance_after} SH</small></span><b>+${item.amount} SH</b></div>`).join("") : `<p class="muted">История транзакций пока пуста.</p>`; } catch (_) { $("#transactions-list").innerHTML = `<p class="muted">История транзакций недоступна.</p>`; } }

  function renderWorldLocations(items) { const target = $("#world-locations"); if (!target) return; target.innerHTML = items.map((item) => `<button type="button" class="world-location card ${item.unlocked ? "" : "is-locked"}" data-world-type="${escapeHtml(item.type)}" ${item.unlocked ? "" : "disabled"}><img src="${assetUrl(item.image)}" alt="${escapeHtml(item.name)}" /><span class="badge">${item.unlocked ? "OPEN" : `LVL ${item.unlock_level}`}</span><div class="world-location-copy"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.description)}</small></div></button>`).join(""); }
  function passiveLabel(system) { return ({ farm: "ФЕРМА", business: "БИЗНЕС", bank: "БАНК" })[system] || system; }
  function fmtMoney(value) { return Math.floor(Number(value) || 0).toLocaleString("ru-RU"); }
  function enterpriseScene(code) {
    const scenes = {
      farm: `<span class="scene-hill hill-back"></span><span class="scene-field"></span><span class="scene-barn"><i></i><b></b></span><span class="scene-animal animal-one">♧</span><span class="scene-animal animal-two">♧</span><span class="scene-sun"></span>`,
      business: `<span class="scene-office-floor"></span><span class="scene-desk"><i class="scene-monitor"></i><i class="scene-monitor"></i><b></b></span><span class="scene-worker worker-one"></span><span class="scene-worker worker-two"></span><span class="scene-data-line"></span>`,
      bank: `<span class="scene-bank-building"><i></i><i></i><i></i><b></b></span><span class="scene-vault"></span><span class="scene-coin coin-one">◈</span><span class="scene-coin coin-two">◈</span><span class="scene-chart"><i></i><i></i><i></i><i></i></span>`,
      stadium: `<span class="scene-stadium-ring"></span><span class="scene-stands"></span><span class="scene-pitch"></span><span class="scene-trophy">✦</span>`,
    };
    return `<span class="enterprise-scene enterprise-scene--${code}" aria-hidden="true">${scenes[code] || ""}<span class="scene-scanline"></span></span>`;
  }
  function enterpriseCard(code, title, icon, description, metric, status) { return `<button type="button" class="enterprise-card card enterprise-card--${code}" data-enterprise-open="${code}">${enterpriseScene(code)}<span class="enterprise-card-top"><span><h3>${title}</h3><p>${description}</p></span><b class="enterprise-card-icon">${icon}</b></span><span class="enterprise-card-top"><b class="enterprise-card-value">${metric}</b><small class="enterprise-card-state">${status}</small></span></button>`; }
  function enterprisePanelHead(title, subtitle) { const visual = title === "FARM" ? "farm" : title === "BUSINESS" ? "business" : title === "BANK" ? "bank" : "stadium"; return `<div class="enterprise-panel-head"><div><p class="eyebrow accent">SHAMA WORLD · ECONOMY</p><h2>${title}</h2><p>${subtitle}</p></div><button type="button" class="button button-secondary enterprise-back" data-enterprise-action="back">НАЗАД</button></div>${enterpriseScene(visual)}`; }
  function progressBar(current, total) { const pct = total > 0 ? Math.min(100, current / total * 100) : 0; return `<div class="enterprise-progress"><span style="width:${pct}%"></span></div>`; }
  function farmPanel(farm) {
    const next = farm.next;
    const animalRows = Object.entries(farm.animals).map(([key, animal]) => `<article class="enterprise-row"><div class="enterprise-row-head"><strong>${animal.name}</strong><small>${animal.count}/${animal.capacity} · ${animal.income_per_minute} SH/min за штуку</small></div>${progressBar(animal.count, animal.capacity)}<div class="enterprise-action-row"><input class="enterprise-quantity" type="number" min="1" max="${Math.max(1, animal.capacity - animal.count)}" value="1" aria-label="Количество: ${animal.name}" ${animal.count >= animal.capacity ? "disabled" : ""} /><button type="button" class="button button-primary" data-enterprise-action="animal" data-animal="${key}" ${animal.count >= animal.capacity ? "disabled" : ""}>КУПИТЬ · ${animal.unit_cost} SH / шт.</button></div><small>На максимуме: ${fmtMoney(animal.max_income_per_minute)} SH/min</small></article>`).join("");
    return `<section class="enterprise-panel">${enterprisePanelHead("FARM", "Постройка, животные и доход сохраняются на сервере.")}<div class="enterprise-stats"><div class="enterprise-stat"><span>УРОВЕНЬ АНГАРА</span><b>${escapeHtml(farm.name)}</b></div><div class="enterprise-stat"><span>ТЕКУЩИЙ ДОХОД</span><b>${fmtMoney(farm.income_per_minute)} SH / MIN</b></div><div class="enterprise-stat"><span>ГОТОВО К СБОРУ</span><b>+${fmtMoney(farm.available)} SH</b></div><div class="enterprise-stat"><span>МНОЖИТЕЛЬ</span><b>×${farm.level || 1}</b></div></div>${farm.level ? `<div class="enterprise-list">${animalRows}</div><div class="enterprise-action-row"><button class="button button-secondary" data-enterprise-action="claim" data-system="farm">СОБРАТЬ · ${fmtMoney(farm.available)} SH</button>${next ? `<button class="button button-primary" data-enterprise-action="upgrade" data-system="farm">${escapeHtml(next.name)} · ${fmtMoney(next.cost)} SH</button>` : `<span class="badge">МАКСИМАЛЬНЫЙ УРОВЕНЬ</span>`}</div>` : `<div class="enterprise-note">Начни с «Дешёвого ангара» за 1 500 SH. Животные откроются после покупки постройки.</div><button class="button button-primary" data-enterprise-action="upgrade" data-system="farm">ПОСТРОИТЬ ДЕШЁВЫЙ АНГАР · 1 500 SH</button>`}${next ? `<div class="enterprise-note">Следующий уровень: ${escapeHtml(next.name)} · лимиты ${next.chickens} кур / ${next.pigs} свиней / ${next.cows} коров.</div>` : `<div class="enterprise-note">Ферма полностью улучшена. Ангар и животные доступны между перезапусками.</div>`}</section>`;
  }
  function businessPanel(business) {
    const next = business.next;
    const remaining = Math.max(0, business.ad_remaining_seconds);
    const ads = business.unlocked ? `<div class="enterprise-list">${business.ads.map((ad) => `<article class="enterprise-row"><div class="enterprise-row-head"><strong>РЕКЛАМА · ${ad.name}</strong><small>${ad.minutes} мин · ×2 доход</small></div><div class="enterprise-action-row"><span class="enterprise-note">${remaining ? `Активна ещё ${Math.ceil(remaining / 60)} мин` : `Цена ${fmtMoney(ad.cost)} SH`}</span><button type="button" class="button button-secondary" data-enterprise-action="advertise" data-campaign="${ad.code}" ${remaining ? "disabled" : ""}>${remaining ? "АКТИВНА" : "ЗАПУСТИТЬ"}</button></div></article>`).join("")}</div>` : "";
    return `<section class="enterprise-panel">${enterprisePanelHead("BUSINESS", "Компьютер создаёт доход только при наличии работника.")}<div class="enterprise-stats"><div class="enterprise-stat"><span>ОФИС</span><b>${escapeHtml(business.name)}</b></div><div class="enterprise-stat"><span>ДОХОД</span><b>${fmtMoney(business.income_per_minute)} SH / MIN</b></div><div class="enterprise-stat"><span>КОМПЬЮТЕРЫ</span><b>${business.computers}/${business.computer_capacity} · улучшено ${business.improved_computers}</b></div><div class="enterprise-stat"><span>РАБОЧИЕ</span><b>${business.workers}/${Math.min(business.worker_capacity, business.computers)}</b></div><div class="enterprise-stat"><span>НАКОПЛЕНО</span><b>+${fmtMoney(business.available)} SH</b></div><div class="enterprise-stat"><span>РЕКЛАМА</span><b>${remaining ? `×2 · ${Math.ceil(remaining / 60)} мин` : "Не активна"}</b></div></div>${business.unlocked ? `<article class="enterprise-row"><div class="enterprise-row-head"><strong>КОМПЬЮТЕРЫ</strong><small>Дешёвые ${business.computers - business.improved_computers} · улучшенные ${business.improved_computers}</small></div>${progressBar(business.computers, business.computer_capacity)}<div class="enterprise-action-row"><input class="enterprise-quantity" type="number" min="1" max="30" value="1" aria-label="Количество компьютеров"/><button class="button button-secondary" data-enterprise-action="computer" data-computer-type="cheap">КУПИТЬ · 250 SH</button>${business.level >= 2 ? `<button class="button button-secondary" data-enterprise-action="computer" data-computer-type="improved">НОВЫЙ УЛУЧШЕННЫЙ · 500 SH</button><button class="button button-primary" data-enterprise-action="computer" data-computer-type="upgrade">УЛУЧШИТЬ СТАРЫЙ · 250 SH</button>` : ""}</div><small>Улучшение старого компьютера стоит разницу: 500 − 250 = 250 SH. Доход: 30 SH/min обычный, 90 SH/min улучшенный.</small></article><article class="enterprise-row"><div class="enterprise-row-head"><strong>РАБОЧИЕ</strong><small>${business.workers}/${Math.min(business.worker_capacity, business.computers)}</small></div>${progressBar(business.workers, Math.min(business.worker_capacity, business.computers))}<div class="enterprise-action-row"><input class="enterprise-quantity" type="number" min="1" max="30" value="1" aria-label="Количество работников"/><button class="button button-primary" data-enterprise-action="worker" ${business.workers >= Math.min(business.worker_capacity, business.computers) ? "disabled" : ""}>НАНЯТЬ · 200 SH / чел.</button></div></article><div class="enterprise-action-row"><button class="button button-secondary" data-enterprise-action="claim" data-system="business">СОБРАТЬ · ${fmtMoney(business.available)} SH</button>${next ? `<button class="button button-primary" data-enterprise-action="upgrade" data-system="business">${escapeHtml(next.label)} · ${fmtMoney(next.cost)} SH</button>` : `<span class="badge">МАКСИМУМ</span>`}</div><div class="enterprise-section-title"><span class="eyebrow">AD BOOST · ×2</span></div>${ads}` : `<div class="enterprise-note">Открой направление бизнес с «Арендовать маленький офис» за 3 000 SH.</div><button class="button button-primary" data-enterprise-action="upgrade" data-system="business">АРЕНДОВАТЬ МАЛЕНЬКИЙ ОФИС · 3 000 SH</button>`}</section>`;
  }
  function miniChart(values) {
    const nums = values.map(Number).filter(Number.isFinite); if (nums.length < 2) return `<svg class="investment-chart" viewBox="0 0 100 30" aria-hidden="true"><path d="M1 25 L99 5" fill="none" stroke="#a66bff" stroke-width="2"/></svg>`;
    const min = Math.min(...nums), max = Math.max(...nums), span = max - min || 1;
    const points = nums.map((n, i) => `${(i / (nums.length - 1) * 98 + 1).toFixed(1)},${(27 - (n - min) / span * 23).toFixed(1)}`).join(" ");
    return `<svg class="investment-chart" viewBox="0 0 100 30" aria-hidden="true"><polyline points="${points}" fill="none" stroke="#bd8aff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  }
  function investmentCard(asset, type) {
    const crypto = type === "crypto", quantityStep = crypto ? "0.0001" : "1", owned = crypto ? Number(asset.owned).toFixed(6) : fmtMoney(asset.owned);
    const change = Number(asset.change_percent) || 0; const arrowClass = change < 0 ? "down" : "";
    const changeLabel = crypto ? `${change > 0 ? "+" : ""}${change.toFixed(2)}% · 24 Ч` : `${change > 0 ? "+" : ""}${change.toFixed(2)}% · ЧАС`;
    return `<article class="investment-card"><div class="enterprise-row-head"><h3>${escapeHtml(asset.name)}</h3><small>${crypto ? asset.code : `${fmtMoney(asset.available)} ДОСТУПНО`}</small></div><b class="investment-price">${fmtMoney(asset.price)} SH</b><small class="investment-change ${arrowClass}">${changeLabel}</small>${miniChart(asset.history || [])}<small>У тебя: ${owned} · средняя цена ${fmtMoney(asset.average_cost)} SH</small><div class="investment-form"><input data-trade-quantity type="number" min="${quantityStep}" step="${quantityStep}" value="${quantityStep}" aria-label="Количество ${escapeHtml(asset.name)}"/><input data-trade-price type="number" min="1" step="1" placeholder="Рынок или своя цена" aria-label="Своя цена ${escapeHtml(asset.name)}"/><button class="button button-primary" data-${crypto ? "crypto" : "stock"}-trade="buy" data-code="${asset.code}">BUY</button><button class="button button-secondary" data-${crypto ? "crypto" : "stock"}-trade="sell" data-code="${asset.code}" ${Number(asset.owned) > 0 ? "" : "disabled"}>SELL</button></div>${crypto ? "" : `<small>Дивиденды ${(Number(asset.dividend_rate) * 100).toFixed(0)}% каждые 4 ч</small>`}</article>`;
  }
  function bankPanel(bank) {
    if (!bank.unlocked) return `<section class="enterprise-panel">${enterprisePanelHead("BANK", "Банк откроется после максимального развития фермы и бизнеса.")}<div class="enterprise-note">Нужно: МЕГА-АНГАР, 150 кур, 60 свиней, 50 коров; средний офис, 30 улучшенных компьютеров и 30 работников.</div></section>`;
    const next = bank.next_attraction_cost;
    const events = (bank.events || []).map((item) => `<div class="bank-event ${item.status === "PENALTY" ? "is-penalty" : ""}">${escapeHtml(item.message)} · ${fmtMoney(item.amount)} SH</div>`).join("") || `<small class="muted">Событий пока нет.</small>`;
    return `<section class="enterprise-panel">${enterprisePanelHead("BANK", "Собственный банковский счёт отделён от SH-баланса и депозитов клиентов.")}<div class="enterprise-stats"><div class="enterprise-stat"><span>СРЕДСТВА БАНКА</span><b>${fmtMoney(bank.cash_balance)} SH</b></div><div class="enterprise-stat"><span>ОБЯЗАТЕЛЬСТВА КЛИЕНТАМ</span><b>${fmtMoney(bank.client_liabilities)} SH</b></div><div class="enterprise-stat"><span>КЛИЕНТЫ</span><b>${fmtMoney(bank.clients)}</b></div><div class="enterprise-stat"><span>ЗАРАБОТАННАЯ ПРИБЫЛЬ</span><b>${fmtMoney(bank.profit_balance)} SH</b></div><div class="enterprise-stat"><span>ПРОЦЕНТЫ ПО КРЕДИТАМ</span><b>+${fmtMoney(bank.pending_profit)} SH</b></div><div class="enterprise-stat"><span>ДИВИДЕНДЫ К СБОРУ</span><b>+${fmtMoney(bank.dividend_pending)} SH</b></div></div><div class="enterprise-row"><div class="enterprise-row-head"><strong>ПРИВЛЕЧЕНИЕ КЛИЕНТОВ · ${bank.attraction_level}/5</strong><small>Доход по кредитам 0,01% обязательств в минуту</small></div>${progressBar(bank.attraction_level, 5)}${next ? `<button class="button button-primary" data-enterprise-action="bank-attraction">ЕЩЁ 100 КЛИЕНТОВ · ${fmtMoney(next)} SH</button>` : `<span class="badge">МАКСИМУМ КЛИЕНТОВ</span>`}</div><div class="enterprise-action-row"><button class="button button-secondary" data-enterprise-action="bank-collect">НАЧИСЛИТЬ ПРОЦЕНТЫ</button><button class="button button-secondary" data-enterprise-action="bank-dividends">СОБРАТЬ ДИВИДЕНДЫ</button><button class="button button-secondary" data-enterprise-action="bank-customer">ОБСЛУЖИТЬ КЛИЕНТА</button></div><div class="enterprise-row"><div class="enterprise-row-head"><strong>ВЫВОД ПРИБЫЛИ</strong><small>Депозит клиентов вывести нельзя</small></div><div class="enterprise-action-row"><input id="bank-withdraw-amount" class="enterprise-input" type="number" min="1" max="${bank.profit_balance}" value="${Math.max(1, Math.min(bank.profit_balance, bank.profit_balance || 1))}" aria-label="Сумма вывода прибыли"/><button class="button button-primary" data-enterprise-action="bank-withdraw" ${bank.profit_balance < 1 ? "disabled" : ""}>ВЫВЕСТИ ПРИБЫЛЬ</button></div></div><div class="enterprise-note">Клиентский депозит — обязательство банка. Для выплаты клиентам банк должен сохранять достаточную ликвидность. За нехватку денег при запросе клиента списывается штраф до 500 SH.</div><div class="bank-event-list">${events}</div><div><p class="eyebrow accent">SHARES · GLOBAL SUPPLY · DIVIDENDS EVERY 4H</p><div class="enterprise-grid">${bank.companies.map((item) => investmentCard(item, "stock")).join("")}</div></div><div><p class="eyebrow accent">CRYPTO · PERSISTED MARKET SNAPSHOT</p><div class="enterprise-grid">${bank.crypto.map((item) => investmentCard(item, "crypto")).join("")}</div></div></section>`;
  }
  function renderEnterpriseDetail() {
    const root = $("#enterprise-detail"), data = state.enterprises; if (!root) return;
    if (!state.enterpriseView || !data) { root.classList.add("is-hidden"); root.innerHTML = ""; return; }
    const views = { farm: () => farmPanel(data.farm), business: () => businessPanel(data.business), stadium: () => `<section class="enterprise-panel">${enterprisePanelHead("TORPEDO STADIUM", "Основа для будущей системы развития стадиона.")}<div class="enterprise-note">Архитектура раздела готова. Механика, доходы и вложения появятся в следующем этапе.</div><div class="enterprise-stats"><div class="enterprise-stat"><span>СТАДИОН</span><b>TORPEDO</b></div><div class="enterprise-stat"><span>ЭТАП</span><b>COMING SOON</b></div></div></section>`, bank: () => bankPanel(data.bank) };
    root.innerHTML = (views[state.enterpriseView] || views.farm)(); root.classList.remove("is-hidden");
  }
  function renderEarnings() {
    const data = state.enterprises; if (!data) return;
    $("#earnings-balance").textContent = `◈ ${fmtMoney(data.balance)} SH`;
    const farmState = data.farm.level ? `${data.farm.level}/3 · ${fmtMoney(data.farm.income_per_minute)} SH/MIN` : "ПОСТРОЙ АНГАР";
    const businessState = data.business.level ? `${data.business.level}/2 · ${fmtMoney(data.business.income_per_minute)} SH/MIN` : "АРЕНДУЙ ОФИС";
    const bankState = data.bank.unlocked ? `${fmtMoney(data.bank.cash_balance)} SH НА СЧЁТЕ` : "УСЛОВИЯ РАЗБЛОКИРОВКИ";
    $("#passive-grid").innerHTML = [
      enterpriseCard("farm", "FARM", "♧", "Ангар, животные и производство", farmState, data.farm.is_max ? "MAX" : `+${fmtMoney(data.farm.available)} SH`),
      enterpriseCard("business", "BUSINESS", "▣", "Компьютеры, команда и реклама", businessState, data.business.is_max ? "MAX" : `+${fmtMoney(data.business.available)} SH`),
      enterpriseCard("stadium", "TORPEDO STADIUM", "◉", "Подготовка к будущей системе стадиона", "АРХИТЕКТУРА ГОТОВА", "SOON"),
      enterpriseCard("bank", "BANK", "▤", "Клиенты, акции и криптовалюта", bankState, data.bank.unlocked ? `+${fmtMoney(data.bank.profit_balance)} SH ПРИБЫЛЬ` : "LOCKED"),
    ].join("");
    renderEnterpriseDetail();
    const legacySystems = state.earnings?.systems || {};
    const legacyLabels = { farm: "CITY FARM", business: "CITY BUSINESS", bank: "CITY BANK" };
    const passiveGrid = $("#passive-income-grid");
    if (passiveGrid) passiveGrid.innerHTML = Object.entries(legacySystems).map(([code, system]) => `<article class="passive-income-card card passive-income--${code}"><div class="passive-income-mark">${code === "farm" ? "♧" : code === "business" ? "▣" : "◈"}</div><div class="passive-income-copy"><span class="eyebrow">${legacyLabels[code] || code.toUpperCase()} · LVL ${system.level}</span><strong>${fmtMoney(system.income_per_minute)} SH <small>/ MIN</small></strong><span class="muted">Накоплено · ${fmtMoney(system.available)} SH</span></div><div class="passive-income-actions"><button class="button button-secondary" data-claim-system="${code}" ${!system.unlocked || system.available < 1 ? "disabled" : ""}>СОБРАТЬ</button>${system.next ? `<button class="button button-primary" data-upgrade-system="${code}" ${!system.unlocked ? "disabled" : ""}>LVL ${system.next.level} · ${fmtMoney(system.next.upgrade_cost)} SH</button>` : `<span class="badge badge-muted">MAX</span>`}</div></article>`).join("");
    const jobs = [{ kind: "courier", title: "COURIER", description: "Доставь заказ через городскую сцену.", reward: "до 120 SH", cooldown: "60 SEC" }, { kind: "factory", title: "CASE FACTORY", description: "Собери кейс на конвейере.", reward: "до 90 SH", cooldown: "30 SEC" }, { kind: "hunt", title: "ОХОТА ЗА ПЕЧАТЬЮ", description: "Найди печать среди объектов.", reward: "до 75 SH", cooldown: "45 SEC" }];
    $("#jobs-grid").innerHTML = jobs.map((job) => `<article class="job-card card job-card--${job.kind}"><div class="job-scene" aria-hidden="true"><span class="job-scene-track"></span><span class="job-scene-vehicle">${job.kind === "courier" ? "▰" : job.kind === "factory" ? "▤" : "✦"}</span><span class="job-scene-marker"></span><span class="job-scene-glow"></span></div><div class="job-card-copy"><span class="eyebrow">${job.cooldown}</span><h3>${job.title}</h3><p>${job.description}</p><small class="accent">${job.reward}</small><button class="button button-primary" data-start-job="${job.kind}" ${state.activeJob ? "disabled" : ""}>${state.activeJob ? "IN PROGRESS" : "START"}</button></div></article>`).join(""); updateActiveJobBanner();
  }
  function updateActiveJobBanner() { const banner = $("#active-job"); if (!banner) return; if (!state.activeJob) { banner.classList.add("is-hidden"); banner.innerHTML = ""; return; } banner.innerHTML = `<div><span class="eyebrow accent">ACTIVE JOB</span><strong>${missionMeta(state.activeJob.kind).title}</strong></div><button type="button" class="button button-secondary" data-resume-job="true">CONTINUE</button>`; banner.classList.remove("is-hidden"); }
  async function loadEarnings() { try { const values = await Promise.all([window.api.getEarnings(), window.api.getEnterprise()]); state.earnings = values[0]; state.enterprises = values[1]; renderEarnings(); } catch (error) { toast(error.message || "Не удалось загрузить заработок."); } }
  async function showEnterprise(system) {
    state.enterpriseView = system;
    if (system === "bank" && state.enterprises?.bank?.unlocked) {
      try {
        const market = await window.api.getBankMarket();
        state.enterprises.bank = { ...state.enterprises.bank, ...market.bank, companies: market.companies, crypto: market.crypto };
      } catch (error) { toast(error.message || "Рынок банка временно недоступен.", "error"); }
    }
    renderEarnings();
    requestAnimationFrame(() => $("#enterprise-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }
  async function refreshEnterpriseView() {
    const [me, enterprise] = await Promise.all([window.api.getMe(), window.api.getEnterprise()]);
    state.enterprises = enterprise; renderUser(me);
    if (state.enterpriseView === "bank" && enterprise.bank.unlocked) {
      try { const market = await window.api.getBankMarket(); state.enterprises.bank = { ...enterprise.bank, ...market.bank, companies: market.companies, crypto: market.crypto }; } catch (_) {}
    }
    renderEarnings();
  }
  function operationRequestId(key) {
    const storageKey = `shama-operation:${key}`;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) return saved;
    } catch (_) { /* Keep the retry key in memory when storage is unavailable. */ }
    if (!state.operationRequestIds.has(key)) {
      const id = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now().toString(36)}-${performance.now().toString(36)}`;
      state.operationRequestIds.set(key, id);
      try { localStorage.setItem(storageKey, id); } catch (_) { /* Private browsing may disable storage. */ }
    }
    return state.operationRequestIds.get(key);
  }
  function clearOperationRequestId(key) {
    state.operationRequestIds.delete(key);
    try { localStorage.removeItem(`shama-operation:${key}`); } catch (_) { /* Private browsing may disable storage. */ }
  }
  async function runEnterpriseAction(button, key, action, successMessage) {
    if (state.pendingActions.has(key) || button.disabled) return;
    state.pendingActions.add(key); button.disabled = true; button.dataset.busyLabel = button.textContent; button.textContent = "ЗАГРУЗКА…";
    try { const result = await action(operationRequestId(key)); await refreshEnterpriseView(); clearOperationRequestId(key); toast(typeof successMessage === "function" ? successMessage(result) : successMessage || "ГОТОВО"); }
    catch (error) { toast(error.message || "Операция не выполнена.", "error"); if (button.isConnected) { button.disabled = false; button.textContent = button.dataset.busyLabel || button.textContent; } }
    finally { state.pendingActions.delete(key); }
  }
  function numberIn(button, selector, fallback = 1) { const input = button.closest(".enterprise-row,.investment-card,.enterprise-panel")?.querySelector(selector); const value = Number(input?.value); return Number.isFinite(value) && value > 0 ? value : fallback; }
  function handleEnterpriseClick(event) {
    const card = event.target.closest("[data-enterprise-open]");
    if (card) { showEnterprise(card.dataset.enterpriseOpen); return; }
    const action = event.target.closest("[data-enterprise-action]");
    if (action) {
      const kind = action.dataset.enterpriseAction;
      if (kind === "back") { state.enterpriseView = null; renderEarnings(); return; }
      if (kind === "upgrade") return runEnterpriseAction(action, `enterprise-upgrade:${action.dataset.system}`, (requestId) => window.api.upgradeEnterprise(action.dataset.system, requestId), (result) => `${result.name || result.system.toUpperCase()} · −${fmtMoney(result.cost)} SH`);
      if (kind === "animal") { const quantity = numberIn(action, ".enterprise-quantity"); return runEnterpriseAction(action, `farm-animal:${action.dataset.animal}:${quantity}`, (requestId) => window.api.buyFarmAnimals(action.dataset.animal, quantity, requestId), (result) => `КУПЛЕНО ${result.quantity} · ${result.count}/${result.capacity}`); }
      if (kind === "computer") { const quantity = numberIn(action, ".enterprise-quantity"); const mode = action.dataset.computerType; const options = { improved: mode === "improved", upgrade_existing: mode === "upgrade" }; return runEnterpriseAction(action, `business-computer:${mode}:${quantity}`, (requestId) => window.api.buyBusinessComputers(quantity, options, requestId), (result) => `КОМПЬЮТЕРЫ · ${result.computers} · −${fmtMoney(result.cost)} SH`); }
      if (kind === "worker") { const quantity = numberIn(action, ".enterprise-quantity"); return runEnterpriseAction(action, `business-workers:${quantity}`, (requestId) => window.api.hireBusinessWorkers(quantity, requestId), (result) => `РАБОЧИЕ · ${result.workers}`); }
      if (kind === "advertise") return runEnterpriseAction(action, `business-ad:${action.dataset.campaign}`, (requestId) => window.api.buyBusinessAdvertising(action.dataset.campaign, requestId), "РЕКЛАМА ×2 ЗАПУЩЕНА");
      if (kind === "claim") return runEnterpriseAction(action, `enterprise-claim:${action.dataset.system}`, (requestId) => window.api.claimEnterpriseIncome(action.dataset.system, requestId), (result) => `НАЧИСЛЕНО +${fmtMoney(result.amount)} SH`);
      if (kind === "bank-attraction") return runEnterpriseAction(action, "bank-attraction", (requestId) => window.api.upgradeBankAttraction(requestId), (result) => `БАНК · +${result.clients_added} КЛИЕНТОВ`);
      if (kind === "bank-collect") return runEnterpriseAction(action, "bank-collect", (requestId) => window.api.collectBankProfit(requestId), (result) => `ПРИБЫЛЬ БАНКА · +${fmtMoney(result.amount)} SH`);
      if (kind === "bank-customer") return runEnterpriseAction(action, "bank-customer", (requestId) => window.api.processBankCustomer(requestId), (result) => result.message);
      if (kind === "bank-dividends") return runEnterpriseAction(action, "bank-dividends", (requestId) => window.api.claimBankDividends(requestId), (result) => `ДИВИДЕНДЫ · +${fmtMoney(result.amount)} SH`);
      if (kind === "bank-withdraw") { const amount = numberIn(action, "#bank-withdraw-amount", 0); return runEnterpriseAction(action, `bank-withdraw:${amount}`, (requestId) => window.api.withdrawBankProfit(amount, requestId), (result) => `ВЫВЕДЕНО +${fmtMoney(result.amount)} SH`); }
    }
    const stock = event.target.closest("[data-stock-trade]");
    if (stock) { const wrap = stock.closest(".investment-card"); const quantity = Number(wrap?.querySelector("[data-trade-quantity]")?.value); return runEnterpriseAction(stock, `stock:${stock.dataset.code}:${stock.dataset.stockTrade}:${quantity}`, (requestId) => window.api.tradeBankStock(stock.dataset.code, stock.dataset.stockTrade, quantity, requestId), `${stock.dataset.stockTrade.toUpperCase()} ${stock.dataset.code} · ${quantity} АКЦИЙ`); }
    const crypto = event.target.closest("[data-crypto-trade]");
    if (crypto) { const wrap = crypto.closest(".investment-card"); const quantity = Number(wrap?.querySelector("[data-trade-quantity]")?.value); return runEnterpriseAction(crypto, `crypto:${crypto.dataset.code}:${crypto.dataset.cryptoTrade}:${quantity}`, (requestId) => window.api.tradeBankCrypto(crypto.dataset.code, crypto.dataset.cryptoTrade, quantity, requestId), `${crypto.dataset.cryptoTrade.toUpperCase()} ${crypto.dataset.code} · ${quantity}`); }
  }
  async function claimSystem(system) { const key = `claim:${system}`; const button = document.querySelector(`[data-claim-system="${system}"]`); if (state.pendingActions.has(key)) return; state.pendingActions.add(key); if (button) { button.disabled = true; button.textContent = "CLAIMING..."; } try { const result = await window.api.claimEarnings(system, operationRequestId(key)); state.currentUser.balance = result.balance; renderUser(state.currentUser); await loadEarnings(); clearOperationRequestId(key); toast(`+${result.amount} SH`); } catch (error) { toast(error.message || "Не удалось получить доход."); if (button?.isConnected) button.disabled = false; } finally { state.pendingActions.delete(key); } }
  async function upgradeSystem(system) { const key = `system-upgrade:${system}`; const button = document.querySelector(`[data-upgrade-system="${system}"]`); if (state.pendingActions.has(key)) return; state.pendingActions.add(key); if (button) { button.disabled = true; button.textContent = "UPGRADING..."; } try { const result = await window.api.upgradeEarnings(system, operationRequestId(key)); state.currentUser.balance = result.balance; renderUser(state.currentUser); await loadEarnings(); clearOperationRequestId(key); toast(`${passiveLabel(system)} LEVEL ${result.level}`); } catch (error) { toast(error.message || "Улучшение недоступно."); if (button?.isConnected) button.disabled = false; } finally { state.pendingActions.delete(key); } }
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
    updateActiveJobBanner();
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
  async function completeActiveJob() { if (!state.activeJob || state.jobCompleting) return; state.jobCompleting = true; const button = $("#mission-complete"); if (button) { button.disabled = true; button.textContent = "ЗАВЕРШАЕМ..."; } try { const result = await window.api.completeJob(state.activeJob.session_id); if (result.balance !== undefined) { state.currentUser.balance = result.balance; state.currentUser.xp = result.xp ?? state.currentUser.xp; state.currentUser.level = result.level ?? state.currentUser.level; renderUser(state.currentUser); } toast(result.success ? `+${result.reward} SH` : "MISSION FAILED"); state.activeJob = null; if (state.mission.timer) window.clearTimeout(state.mission.timer); closeModal("mission-modal"); updateActiveJobBanner(); await loadEarnings(); } catch (error) { toast(error.message || "Задание не завершено."); } finally { state.jobCompleting = false; if (button?.isConnected) { button.disabled = false; button.textContent = "ЗАВЕРШИТЬ МИССИЮ"; } } }
  async function startJob(kind) { if (state.jobStarting || state.activeJob) return; const button = document.querySelector(`[data-start-job="${kind}"]`); state.jobStarting = true; if (button) { button.disabled = true; button.textContent = "STARTING..."; } try { const session = await window.api.startJob(kind); showActiveJob(session); toast("ЗАДАНИЕ НАЧАТО"); } catch (error) { toast(error.message || "Не удалось начать задание."); } finally { state.jobStarting = false; if (button?.isConnected) { button.disabled = false; button.textContent = "START"; } } }
  const MARKET_IMAGES = {
    "Shama Tag": "/assets/market/shama-tag.jpg",
    "Solar Core": "/assets/market/solar-core.jpg",
    "Torpedo Cup": "/assets/market/torpedo-cup.jpg",
    "City Villa": "/assets/market/city-villa.jpg",
    "Torpedo Trophy": "/assets/market/torpedo-trophy.jpg",
    "Shadow Mask": "/assets/market/shadow-mask.jpg",
    "Football": "/assets/market/football.jpg",
    "SH Mansion": "/assets/market/sh-mansion.jpg",
  };
  function marketAsset(offer) { return assetUrl(offer.market_image || MARKET_IMAGES[offer.name] || offer.image); }

  function renderMarket(data) {
    state.market = data;
    $("#market-balance").textContent = `◈ ${state.currentUser.balance} SH`;
    const end = Date.parse(data.rotation.ends_at); const timer = $("#market-timer");
    if (state.marketTimer) window.clearTimeout(state.marketTimer);
    const tick = () => { const left = Math.max(0, end - Date.now()); const s = Math.floor(left / 1000); timer.textContent = `NEXT REFRESH · ${String(Math.floor(s / 3600)).padStart(2, "0")}:${String(Math.floor(s / 60) % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`; if (left > 0 && state.currentPage === "market") state.marketTimer = window.setTimeout(tick, 1000); }; tick();
    const query = ($( "#market-search" )?.value || "").trim().toLowerCase(); const sort = $("#market-sort")?.value || "default";
    let offers = [...(data.offers || [])].filter((offer) => !query || String(offer.name).toLowerCase().includes(query) || String(offer.rarity).toLowerCase().includes(query));
    if (sort === "price-asc") offers.sort((a,b) => a.price - b.price); if (sort === "price-desc") offers.sort((a,b) => b.price - a.price);
    $("#market-offers").innerHTML = offers.length ? offers.map((offer) => `<article class="market-offer card"><img src="${marketAsset(offer)}" alt="${escapeHtml(offer.name)}" loading="lazy" decoding="async" /><strong>${escapeHtml(offer.name)}</strong><small>${offer.rarity} · STOCK ${offer.stock}</small><b>${offer.price} SH</b><button class="button button-primary market-buy" data-market-offer="${offer.offer_id}" ${offer.stock < 1 ? "disabled" : ""}>BUY</button></article>`).join("") : `<div class="empty-state"><div class="empty-icon">⌕</div><h2>Ничего не найдено</h2><p class="muted">Попробуй изменить запрос.</p></div>`;
  }
  async function loadMarket() { try { renderMarket(await window.api.getMarket()); } catch (error) { toast(error.message || "Рынок недоступен."); } }
  async function buyMarketOffer(offerId) { const key = `market-buy:${offerId}`; if (state.pendingActions.has(key)) return; const button = document.querySelector(`[data-market-offer="${offerId}"]`); state.pendingActions.add(key); if (button) { button.disabled = true; button.textContent = "BUYING..."; } try { const requestId = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${performance.now()}`; const result = await window.api.buyMarketOffer(offerId, requestId); state.currentUser.balance = result.balance; state.currentUser.xp = result.xp ?? state.currentUser.xp; state.currentUser.level = result.level ?? state.currentUser.level; renderUser(state.currentUser); toast(`${result.item.name} PURCHASED`); await loadMarket(); await loadInventory(); } catch (error) { toast(error.message || "Покупка не выполнена."); if (button?.isConnected) { button.disabled = false; button.textContent = "BUY"; } } finally { state.pendingActions.delete(key); } }
  async function loadProfileExtras() {
    try {
      const result = await window.api.getProfile();
      const profileUser = result.user || {};
      const rate = $("#profile-stat-success-rate");
      if (rate) rate.textContent = `${profileUser.upgrade_success_rate || 0}%`;
      const spent = $("#profile-stat-spent");
      if (spent) spent.textContent = `${fmtMoney(profileUser.total_sh_spent)} SH`;
      const passive = $("#profile-stat-passive");
      if (passive) passive.textContent = `${profileUser.farm_level || 1} / ${profileUser.business_level || 0} / ${profileUser.bank_level || 0}`;
      const economyStats = [
        ["total-earned", "total_sh_earned"], ["invested", "total_invested"], ["total-profit", "total_profit"],
        ["farm-profit", "farm_profit"], ["business-profit", "business_profit"], ["bank-profit", "bank_profit"],
        ["market-pnl", "market_pnl"], ["cases-spent", "cases_spent"],
      ];
      economyStats.forEach(([elementId, dataKey]) => {
        const element = $(`#profile-stat-${elementId}`);
        if (element) element.textContent = `${fmtMoney(profileUser[dataKey])} SH`;
      });
      const list = $("#profile-achievements-list");
      if (list) list.innerHTML = `<div class="profile-stat-row"><span>ACHIEVEMENTS</span><strong>${(result.achievements || []).filter((item) => item.unlocked).length} / ${(result.achievements || []).length}</strong></div>` + (result.achievements || []).map((item) => `<div class="profile-achievement ${item.unlocked ? "is-unlocked" : ""}"><span>${item.unlocked ? "✓" : "○"}</span><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.description)} · ${item.progress}/${item.requirement}</small></div></div>`).join("");
      const daily = await window.api.getDaily();
      const button = $("#daily-claim-button");
      if (button && !state.dailyClaiming) {
        button.disabled = daily.claimed;
        button.textContent = daily.claimed ? "CLAIMED TODAY" : `CLAIM ${daily.reward} SH`;
      }
    } catch (_) {}
  }
  async function claimDaily() { const button = $("#daily-claim-button"); if (state.dailyClaiming || (button && button.disabled)) return; state.dailyClaiming = true; if (button) { button.disabled = true; button.textContent = "CLAIMING..."; } try { const result = await window.api.claimDaily(); state.currentUser.balance = result.balance; state.currentUser.xp = result.xp; state.currentUser.level = result.level; renderUser(state.currentUser); if (button) button.textContent = "CLAIMED TODAY"; toast(`DAILY BONUS · +${result.reward} SH`); await loadProfileExtras(); } catch (error) { toast(error.message || "Ежедневный бонус недоступен."); if (button) { button.disabled = false; button.textContent = "CLAIM 100 SH"; } } finally { state.dailyClaiming = false; } }
  function renderUpgradeItem(item, label) { if (!item) return `<span class="slot-label">${label}</span><span class="slot-empty">Выбери предмет</span>`; return `<span class="slot-label">${label}</span><img class="upgrade-item-image" src="${assetUrl(item.image)}" alt="${escapeHtml(item.name)}" /><strong>${escapeHtml(item.name)}</strong><span class="${rarityClass(item.rarity)} rarity-label">${item.rarity}</span><b>${item.value} SH</b>`; }
  function placeWheelLabels(chance) {
    const successLabel = $("#upgrade-success-label"), riskLabel = $("#upgrade-risk-label");
    if (!successLabel || !riskLabel) return;
    if (chance <= 0) { successLabel.style.display = "none"; riskLabel.style.display = "none"; return; }
    successLabel.style.display = "block"; riskLabel.style.display = "block";
    const successAngle = Number(chance) * 3.6;
    const place = (label, angle) => {
      const radians = (angle - 90) * Math.PI / 180;
      label.style.left = `${50 + Math.cos(radians) * 27}%`;
      label.style.top = `${50 + Math.sin(radians) * 27}%`;
    };
    place(successLabel, successAngle / 2);
    place(riskLabel, successAngle + (360 - successAngle) / 2);
  }
  function renderUpgradeSlots() {
    $("#upgrade-source-card").innerHTML = renderUpgradeItem(state.upgrade.source, "MY ITEM");
    $("#upgrade-target-card").innerHTML = renderUpgradeItem(state.upgrade.target, "TARGET");
    const previewChance = state.upgrade.preview ? Number(state.upgrade.preview.chance) : 0;
    const activeChance = state.upgrade.running && state.upgrade.animationResult ? Number(state.upgrade.animationResult.chance) : previewChance;
    $("#upgrade-chance").textContent = state.upgrade.preview ? `${previewChance.toFixed(1)}%` : "—";
    const wheelChance = $("#upgrade-wheel-chance");
    if (wheelChance) wheelChance.textContent = activeChance ? `${activeChance.toFixed(1)}%` : "—";
    const wheelStatus = $("#upgrade-wheel-status");
    if (wheelStatus && !state.upgrade.running) wheelStatus.textContent = state.upgrade.preview ? `Зона успеха · ${previewChance.toFixed(1)}% · риск без комиссии` : "Выбери предмет и цель";
    $("#upgrade-chance-bar").style.width = `${previewChance}%`;
    $("#upgrade-wheel").style.setProperty("--success-size", `${activeChance}%`);
    placeWheelLabels(activeChance);
    $("#upgrade-source-card").disabled = state.upgrade.running;
    $("#upgrade-target-card").disabled = state.upgrade.running;
    $("#upgrade-button").disabled = !state.upgrade.preview || state.upgrade.running;
    $("#upgrade-button").textContent = state.upgrade.preview ? `UPGRADE ${previewChance.toFixed(1)}%` : "UPGRADE";
  }
  function renderUpgradeInventory() {
    const empty = $("#upgrade-inventory-empty"), grid = $("#upgrade-inventory-grid");
    if (!empty || !grid) return;
    empty.classList.toggle("is-hidden", state.inventory.length > 0);
    grid.innerHTML = state.inventory.map((item) => `<button type="button" class="inventory-card card premium-item ${rarityClass(item.rarity)} ${state.upgrade.source && state.upgrade.source.id === item.id ? "is-selected" : ""}" data-upgrade-item-id="${item.id}" ${state.upgrade.running ? "disabled" : ""}><div class="item-image-wrap"><img src="${assetUrl(item.image)}" alt="${escapeHtml(item.name)}" /></div><div class="item-card-copy"><strong>${escapeHtml(item.name)}</strong><span class="rarity-label">${item.rarity}</span><small>${item.value} SH · ×${item.quantity}</small></div></button>`).join("");
  }
  async function selectUpgradeSource(itemId) {
    if (state.upgrade.running) return;
    const item = state.inventory.find((candidate) => candidate.id === itemId);
    if (!item) return toast("ITEM NO LONGER AVAILABLE");
    state.upgrade.source = item; state.upgrade.target = null; state.upgrade.preview = null; state.upgrade.targets = [];
    renderUpgradeSlots(); renderUpgradeInventory(); $("#upgrade-recommendations").innerHTML = `<p class="muted">Загружаем цели...</p>`;
    try {
      const result = await window.api.getUpgradeTargets(item.id);
      if (state.upgrade.source?.id !== item.id) return;
      state.upgrade.targets = result.items || []; renderRecommendations();
    } catch (error) { if (state.upgrade.source?.id === item.id) toast(error.message || "Не удалось загрузить цели."); }
  }
  function renderRecommendations() { const items = state.upgrade.targets.slice(0, 5); $("#upgrade-recommendations").innerHTML = items.length ? items.map((item) => `<button type="button" class="recommendation-card ${rarityClass(item.rarity)}" data-target-id="${item.id}"><span><strong>${escapeHtml(item.name)}</strong><small>${item.value} SH</small></span><b>${Number(item.chance).toFixed(1)}%</b></button>`).join("") : `<p class="muted">Для этого предмета пока нет доступной цели.</p>`; }
  function renderSourcePicker() { $("#upgrade-source-picker").innerHTML = state.inventory.length ? state.inventory.map((item) => `<button type="button" class="picker-item ${rarityClass(item.rarity)}" data-picker-source-id="${item.id}"><img src="${assetUrl(item.image)}" alt="" /><span><strong>${escapeHtml(item.name)}</strong><small>${item.rarity} · ${item.value} SH · ×${item.quantity}</small></span></button>`).join("") : `<p class="muted">YOUR INVENTORY IS EMPTY</p>`; openModal("upgrade-source-modal"); }
  function filteredTargets() { const items = state.upgrade.targets.filter((item) => state.upgrade.filter === "ALL" || item.rarity === state.upgrade.filter); return items.sort((a, b) => state.upgrade.sort === "asc" ? a.value - b.value : b.value - a.value); }
  function renderTargetPicker() { const items = filteredTargets(); $("#upgrade-target-picker").innerHTML = items.length ? items.map((item) => `<button type="button" class="picker-item ${rarityClass(item.rarity)}" data-picker-target-id="${item.id}"><img src="${assetUrl(item.image)}" alt="" /><span><strong>${escapeHtml(item.name)}</strong><small>${item.rarity} · ${item.value} SH · ${Number(item.chance).toFixed(1)}%</small></span></button>`).join("") : `<p class="muted">Нет предметов дороже исходного.</p>`; }
  async function showTargetPicker() { if (state.upgrade.running) return; if (!state.upgrade.source) return toast("Сначала выбери исходный предмет"); const sourceId = state.upgrade.source.id; if (!state.upgrade.targets.length) { try { const result = await window.api.getUpgradeTargets(sourceId); if (state.upgrade.source?.id !== sourceId || state.currentPage !== "upgrade") return; state.upgrade.targets = result.items || []; } catch (error) { return toast(error.message || "TARGET NO LONGER AVAILABLE"); } } if (state.currentPage !== "upgrade") return; renderTargetPicker(); openModal("upgrade-target-modal"); }
  async function selectUpgradeTarget(itemId) { if (state.upgrade.running) return; const target = state.upgrade.targets.find((item) => item.id === itemId); if (!target || !state.upgrade.source) return; const sourceId = state.upgrade.source.id; state.upgrade.target = target; state.upgrade.preview = null; renderUpgradeSlots(); closeModal("upgrade-target-modal"); try { const preview = await window.api.previewUpgrade(sourceId, target.id); if (state.upgrade.source?.id !== sourceId) return; state.upgrade.preview = preview; state.upgrade.target = preview.target; state.upgrade.source = preview.source; renderUpgradeSlots(); } catch (error) { if (state.upgrade.source?.id === sourceId) { state.upgrade.target = null; renderUpgradeSlots(); toast(error.message || "TARGET NO LONGER AVAILABLE"); } } }
  function showConfirmation() { if (!state.upgrade.preview || state.upgrade.running) return; const { source, target, chance } = state.upgrade.preview; $("#confirm-source").innerHTML = `<img src="${assetUrl(source.image)}" alt="" /><span>${escapeHtml(source.name)}<small>${source.value} SH</small></span>`; $("#confirm-target").innerHTML = `<img src="${assetUrl(target.image)}" alt="" /><span>${escapeHtml(target.name)}<small>${target.value} SH</small></span>`; $("#confirm-chance").textContent = `${Number(chance).toFixed(1)}%`; openModal("upgrade-confirm-modal"); }
  async function setWheelAnimation(result) {
    const chance = Math.max(0.5, Math.min(99.5, Number(result.chance) || 0));
    const successDeg = chance * 3.6;
    const margin = Math.min(7, Math.max(1.5, successDeg * 0.06), Math.max(1.5, (360 - successDeg) * 0.06));
    const randomInRange = (min, max) => min + Math.random() * Math.max(0, max - min);
    let finalSector;
    if (result.result === "SUCCESS") {
      const max = Math.max(margin + 0.2, successDeg - margin);
      finalSector = randomInRange(margin, max);
    } else {
      const min = Math.min(359.8 - margin, successDeg + margin);
      finalSector = randomInRange(min, 359.8 - margin);
    }

    const pointer = $("#upgrade-pointer");
    const wheel = $("#upgrade-wheel");
    const status = $("#upgrade-wheel-status");
    if (!pointer || !wheel) return;

    const spinTransform = (degrees) => `rotate(${degrees}deg) translateY(-88px)`;
    const fastTurns = 5;
    const fastEnd = fastTurns * 360;
    const slowTurns = 2;
    const finalEnd = fastEnd + slowTurns * 360 + finalSector;

    wheel.style.setProperty("--success-size", `${chance}%`);
    pointer.style.transform = spinTransform(0);
    void pointer.offsetWidth;
    const animateRotation = (from, to, duration, ease) => new Promise((resolve) => {
      const started = performance.now();
      const frame = () => {
        const progress = Math.min(1, (performance.now() - started) / duration);
        pointer.style.transform = spinTransform(from + (to - from) * ease(progress));
        if (progress < 1) requestAnimationFrame(frame);
        else resolve();
      };
      requestAnimationFrame(frame);
    });

    // Phase 1: exactly five complete, visibly fast revolutions.
    if (status) status.textContent = "ВРАЩЕНИЕ · 5 ОБОРОТОВ";
    await animateRotation(0, fastEnd, 3000, (progress) => progress);

    // Phase 2: a separate long ease-out. The endpoint is calculated from the
    // server result and lands inside the SUCCESS/RISK sector selected above.
    if (status) status.textContent = result.result === "SUCCESS" ? "ЗАМЕДЛЕНИЕ · SUCCESS" : "ЗАМЕДЛЕНИЕ · RISK";
    await animateRotation(fastEnd, finalEnd, 4700, (progress) => 1 - Math.pow(1 - progress, 3));

    pointer.style.transform = spinTransform(finalEnd);
    if (status) status.textContent = result.result === "SUCCESS" ? `SUCCESS · ${chance.toFixed(1)}%` : `RISK · ${chance.toFixed(1)}%`;
  }

  function resetUpgradeWheel() {
    const pointer = $("#upgrade-pointer"), wheel = $("#upgrade-wheel"), chance = $("#upgrade-wheel-chance"), status = $("#upgrade-wheel-status");
    if (pointer) pointer.style.transform = "rotate(0deg) translateY(-88px)";
    if (wheel) wheel.style.setProperty("--success-size", "0%");
    if (chance) chance.textContent = "—";
    if (status) status.textContent = "Выбери предмет и цель";
    placeWheelLabels(0);
  }

  function showUpgradeResult(result) { const success = result.result === "SUCCESS"; $("#upgrade-result-box").classList.toggle("upgrade-failed", !success); $("#upgrade-result-icon").textContent = success ? "✓" : "×"; $("#upgrade-result-title").textContent = success ? "UPGRADE SUCCESS" : "UPGRADE FAILED"; $("#upgrade-result-name").textContent = success ? result.target.name : "SOURCE ITEM LOST"; $("#upgrade-result-route").innerHTML = `<img src="${assetUrl(result.source.image)}" alt="" /><span>→</span><img src="${assetUrl(result.target.image)}" alt="" />`; $("#upgrade-result-description").textContent = success ? `${result.target.name} добавлен в инвентарь.` : `${result.source.name} больше нет в инвентаре.`; openModal("upgrade-result-modal"); }
  async function executeSelectedUpgrade() {
    if (!state.upgrade.preview || state.upgrade.running) return;
    state.upgrade.running = true;
    $("#confirm-upgrade-button").disabled = true;
    let result = null;
    try {
      const requestId = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now().toString(36)}-${performance.now().toString(36)}`;
      result = await window.api.executeUpgrade(state.upgrade.source.id, state.upgrade.target.id, requestId);
      state.upgrade.animationResult = result;
      renderUpgradeSlots();
      closeModal("upgrade-confirm-modal");
      await setWheelAnimation(result);
      showUpgradeResult(result);
      state.currentUser.xp = result.xp;
      state.currentUser.level = result.level;
      state.currentUser.balance = result.balance;
      renderUser(state.currentUser);
      await loadInventory();
      await loadUpgradeHistory();
      try { renderUser(await window.api.getMe()); } catch (_) {}
    } catch (error) {
      if (result) {
        showUpgradeResult(result);
        toast("Результат сохранён. Обнови инвентарь позже.");
      } else {
        const message = error.status >= 500 ? "UPGRADE FAILED TO START" : (error.status === 409 && /недоступен|доступен/.test(error.message) ? "ITEM NO LONGER AVAILABLE" : (error.message || "UPGRADE FAILED TO START"));
        toast(message);
      }
    } finally {
      state.upgrade.running = false;
      state.upgrade.animationResult = null;
      resetUpgradeState();
      $("#confirm-upgrade-button").disabled = false;
    }
  }

  function renderUpgradeHistory(items) { $("#upgrade-history").innerHTML = items.length ? items.map((item) => `<div class="history-row"><div class="history-images"><img src="${assetUrl(item.source_image)}" alt="" /><span>→</span><img src="${assetUrl(item.target_image)}" alt="" /></div><div class="history-copy"><strong>${escapeHtml(item.source_name)} → ${escapeHtml(item.target_name)}</strong><small>${item.source_value} SH → ${item.target_value} SH · ${Number(item.chance).toFixed(1)}%</small></div><b class="history-result ${item.result === "SUCCESS" ? "success" : "fail"}">${item.result}</b></div>`).join("") : `<p class="muted">История пока пуста.</p>`; }
  async function loadUpgradeHistory() { try { renderUpgradeHistory((await window.api.getUpgradeHistory()).transactions || []); } catch (_) { renderUpgradeHistory([]); } }
  async function loadUpgrade() { await loadInventory(); await loadUpgradeHistory(); renderUpgradeSlots(); }
  async function loadApp() { $("#retry-button").disabled = true; try { await window.api.health(); renderUser(await window.api.getMe()); await loadCases(); showApp(); } catch (error) { showError(error.status === 401 ? "Откройте SHAMA WORLD через Telegram, чтобы продолжить." : "Не удалось подключиться к SHAMA WORLD."); } finally { $("#retry-button").disabled = false; } }

  async function openUpgradeFromItem(itemId) {
    if (state.upgrade.running) return toast("Апгрейд уже выполняется.");
    closeAllModals();
    resetUpgradeState();
    await renderPage("upgrade");
    await selectUpgradeSource(itemId);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function openLastCaseAgain() {
    if (state.opening) return;
    const caseId = state.lastOpenedCaseId;
    closeModal("opening-modal");
    await loadInventory();
    if (!caseId) return;
    await showCase(caseId);
    if (state.selectedCase) await openSelectedCase();
  }

  function bindLightweightParallax() {
    const pointerFine = window.matchMedia?.("(hover: hover) and (pointer: fine)").matches;
    const scene = $("[data-parallax-scene]");
    if (pointerFine && scene) {
      scene.addEventListener("pointermove", (event) => {
        if (event.pointerType === "touch") return;
        const bounds = scene.getBoundingClientRect();
        const x = (event.clientX - bounds.left) / bounds.width - 0.5;
        const y = (event.clientY - bounds.top) / bounds.height - 0.5;
        scene.querySelectorAll("[data-depth]").forEach((layer) => {
          const depth = Number(layer.dataset.depth) || 0;
          layer.style.translate = `${(-x * depth * 34).toFixed(1)}px ${(-y * depth * 22).toFixed(1)}px`;
        });
      });
      scene.addEventListener("pointerleave", () => scene.querySelectorAll("[data-depth]").forEach((layer) => { layer.style.translate = ""; }));
    }
    if (pointerFine) {
      document.addEventListener("pointermove", (event) => {
        const card = event.target.closest("[data-tilt-card]");
        if (!card || event.pointerType === "touch") return;
        const bounds = card.getBoundingClientRect();
        if (!bounds.width || !bounds.height) return;
        const x = (event.clientX - bounds.left) / bounds.width;
        const y = (event.clientY - bounds.top) / bounds.height;
        card.style.setProperty("--tilt-x", `${((0.5 - y) * 7).toFixed(2)}deg`);
        card.style.setProperty("--tilt-y", `${((x - 0.5) * 8).toFixed(2)}deg`);
        card.style.setProperty("--parallax-x", `${((0.5 - x) * 9).toFixed(1)}px`);
        card.style.setProperty("--parallax-y", `${((0.5 - y) * 7).toFixed(1)}px`);
      });
      document.addEventListener("pointerout", (event) => {
        const card = event.target.closest?.("[data-tilt-card]");
        if (!card || (event.relatedTarget instanceof Node && card.contains(event.relatedTarget))) return;
        ["--tilt-x", "--tilt-y", "--parallax-x", "--parallax-y"].forEach((name) => card.style.removeProperty(name));
      });
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyTheme(activeTheme, false); setTelegramReady(); bindLightweightParallax(); $("#retry-button").addEventListener("click", loadApp);
    document.querySelectorAll("[data-theme-select]").forEach((button) => button.addEventListener("click", () => applyTheme(button.dataset.themeSelect)));
    $("#market-search").addEventListener("input", () => { if (state.market) renderMarket(state.market); });
    $("#market-sort").addEventListener("change", () => { if (state.market) renderMarket(state.market); }); $("#open-case-button").addEventListener("click", openSelectedCase); $("#saved-button").addEventListener("click", () => { closeModal("opening-modal"); loadInventory(); }); $("#open-again-button").addEventListener("click", openLastCaseAgain); $("#opening-inventory-button").addEventListener("click", () => { closeModal("opening-modal"); renderPage("inventory").catch((error) => toast(error.message || "Инвентарь временно недоступен.")); }); $("#upgrade-source-card").addEventListener("click", renderSourcePicker); $("#upgrade-target-card").addEventListener("click", showTargetPicker); $("#upgrade-button").addEventListener("click", showConfirmation); $("#confirm-upgrade-button").addEventListener("click", executeSelectedUpgrade); $("#sell-minus").addEventListener("click", () => updateSellQuantity(state.sell.quantity - 1)); $("#sell-plus").addEventListener("click", () => updateSellQuantity(state.sell.quantity + 1)); $("#sell-max").addEventListener("click", () => updateSellQuantity(state.sell.item ? state.sell.item.quantity : 1)); $("#sell-quantity").addEventListener("input", (event) => updateSellQuantity(event.target.value)); $("#confirm-sell-button").addEventListener("click", confirmSell); $("#target-sort").addEventListener("change", (event) => { state.upgrade.sort = event.target.value; renderTargetPicker(); }); $("#daily-claim-button").addEventListener("click", claimDaily);
    document.querySelectorAll("[data-nav]").forEach((nav) => nav.addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); if (state.opening) { toast("Дождись результата открытия кейса."); return; } if (nav.dataset.earnFocus) state.earningsFocus = nav.dataset.earnFocus; else if (nav.dataset.nav !== "earn") state.earningsFocus = null; closeAllModals(); renderPage(nav.dataset.nav).catch((error) => toast(error.message || "Раздел временно недоступен.")); }));
    document.addEventListener("click", (event) => { const nav = event.target.closest("[data-nav]"); if (nav) return; const missionAction = event.target.closest("[data-mission-action]"); if (missionAction) missionCourier(missionAction.dataset.missionAction); const factoryPart = event.target.closest("[data-factory-step]"); if (factoryPart) missionFactory(factoryPart.dataset.factoryStep); const huntTarget = event.target.closest("[data-hunt-index]"); if (huntTarget) missionHunt(huntTarget.dataset.huntIndex); const card = event.target.closest("[data-case-id]"); if (card) showCase(Number(card.dataset.caseId)); const item = event.target.closest("#page-inventory [data-item-id]"); if (item) { event.preventDefault(); event.stopPropagation(); showItem(Number(item.dataset.itemId)); return; } const upgradeItem = event.target.closest("[data-upgrade-item-id]"); if (upgradeItem) selectUpgradeSource(Number(upgradeItem.dataset.upgradeItemId)); const pickerSource = event.target.closest("[data-picker-source-id]"); if (pickerSource) { closeModal("upgrade-source-modal"); selectUpgradeSource(Number(pickerSource.dataset.pickerSourceId)); } const pickerTarget = event.target.closest("[data-picker-target-id]"); if (pickerTarget) selectUpgradeTarget(Number(pickerTarget.dataset.pickerTargetId)); const recommendation = event.target.closest("[data-target-id]"); if (recommendation) selectUpgradeTarget(Number(recommendation.dataset.targetId)); const filter = event.target.closest("[data-rarity-filter]"); if (filter) { state.upgrade.filter = filter.dataset.rarityFilter; document.querySelectorAll("[data-rarity-filter]").forEach((button) => button.classList.toggle("is-active", button === filter)); renderTargetPicker(); }
    const inventoryFilter = event.target.closest("[data-inventory-filter]"); if (inventoryFilter) { state.inventoryFilter = inventoryFilter.dataset.inventoryFilter; document.querySelectorAll("[data-inventory-filter]").forEach((button) => button.classList.toggle("is-active", button === inventoryFilter)); renderInventory(); }
    const close = event.target.closest("[data-close-modal]"); if (close) closeModal(close.dataset.closeModal); if (event.target.closest("[data-action='chances']")) showChances(); const sellAction = event.target.closest("[data-action='sell-item']"); if (sellAction) openSellModal(Number($("#item-modal").dataset.itemId)); const upgradeAction = event.target.closest("[data-action='upgrade-item']"); if (upgradeAction) { const itemId = Number($("#item-modal").dataset.itemId); closeAllModals(); openUpgradeFromItem(itemId); } const claim = event.target.closest("[data-claim-system]"); if (claim) claimSystem(claim.dataset.claimSystem); const systemUpgrade = event.target.closest("[data-upgrade-system]"); if (systemUpgrade) upgradeSystem(systemUpgrade.dataset.upgradeSystem); const start = event.target.closest("[data-start-job]"); if (start) startJob(start.dataset.startJob); if (event.target.closest("[data-resume-job]")) openModal("mission-modal"); const offer = event.target.closest("[data-market-offer]"); if (offer) buyMarketOffer(Number(offer.dataset.marketOffer)); if (event.target.closest("#mission-complete")) completeActiveJob(); if (event.target.closest("[data-coming-soon]")) toast("Функция будет доступна на следующем этапе."); if (event.target.classList.contains("modal-backdrop")) closeModal(event.target.id); });
    document.addEventListener("click", handleEnterpriseClick);
    loadApp();
  });
}());
