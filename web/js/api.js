(function () {
  "use strict";
  async function request(path, options) {
    const initData = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp.initData || "" : "";
    const headers = new Headers((options && options.headers) || {});
    if (initData) headers.set("Authorization", `tma ${initData}`);
    const response = await fetch(path, { ...options, headers });
    let payload = null;
    try { payload = await response.json(); } catch (_) { payload = null; }
    if (!response.ok) { const error = new Error(payload && payload.detail ? payload.detail : `Ошибка API (${response.status})`); error.status = response.status; throw error; }
    return payload;
  }
  function operationId(value) {
    if (value) return value;
    return window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  }
  window.api = {
    health: () => request("/api/health"), getMe: () => request("/api/me"), getCases: () => request("/api/cases"),
    getCase: (id) => request(`/api/cases/${id}`), openCase: (id, requestId) => request(`/api/cases/${id}/open`, { method: "POST", headers: { "X-Opening-Request-Id": requestId } }), openFiveCases: (id, requestId) => request(`/api/cases/${id}/open-five`, { method: "POST", headers: { "X-Opening-Request-Id": requestId } }),
    getInventory: () => request("/api/inventory"), getInventoryItem: (id) => request(`/api/inventory/${id}`), getBalance: () => request("/api/balance"),
    sellItem: (itemId, quantity, requestId) => request("/api/inventory/sell", { method: "POST", headers: { "Content-Type": "application/json", "X-Sell-Request-Id": requestId }, body: JSON.stringify({ item_id: itemId, quantity }) }),
    getTransactions: () => request("/api/transactions"),
    getUpgradeTargets: (sourceId) => request(`/api/upgrade/targets?source_item_id=${encodeURIComponent(sourceId)}`),
    previewUpgrade: (sourceId, targetId) => request("/api/upgrade/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_item_id: sourceId, target_item_id: targetId }) }),
    executeUpgrade: (sourceId, targetId, requestId) => request("/api/upgrade/execute", { method: "POST", headers: { "Content-Type": "application/json", "X-Upgrade-Request-Id": requestId }, body: JSON.stringify({ source_item_id: sourceId, target_item_id: targetId }) }),
    getUpgradeHistory: () => request("/api/upgrade/history"),
    getEarnings: () => request("/api/earnings"),
    getWorks: () => request("/api/works"),
    upgradeWorksFarm: (requestId) => request("/api/works/farm/upgrade", { method: "POST", headers: { "X-Works-Request-Id": operationId(requestId) } }),
    collectWorksFarm: (requestId) => request("/api/works/farm/collect", { method: "POST", headers: { "X-Works-Request-Id": operationId(requestId) } }),
    hireWorksFarm: (quantity, requestId) => request("/api/works/farm/workers", { method: "POST", headers: { "Content-Type": "application/json", "X-Works-Request-Id": operationId(requestId) }, body: JSON.stringify({ quantity }) }),
    upgradeWorksBusiness: (requestId) => request("/api/works/business/upgrade", { method: "POST", headers: { "X-Works-Request-Id": operationId(requestId) } }),
    collectWorksBusiness: (requestId) => request("/api/works/business/collect", { method: "POST", headers: { "X-Works-Request-Id": operationId(requestId) } }),
    hireWorksBusiness: (quantity, requestId) => request("/api/works/business/workers", { method: "POST", headers: { "Content-Type": "application/json", "X-Works-Request-Id": operationId(requestId) }, body: JSON.stringify({ quantity }) }),
    createWorksDeposit: (amount, termDays, requestId) => request("/api/works/bank/deposits", { method: "POST", headers: { "Content-Type": "application/json", "X-Works-Request-Id": operationId(requestId) }, body: JSON.stringify({ amount, term_days: termDays }) }),
    collectWorksDeposit: (id, requestId) => request(`/api/works/bank/deposits/${id}/collect`, { method: "POST", headers: { "X-Works-Request-Id": operationId(requestId) } }),
    getEnterprise: () => request("/api/enterprise"),
    upgradeEnterprise: (system, requestId) => request(`/api/enterprise/${encodeURIComponent(system)}/upgrade`, { method: "POST", headers: { "X-Enterprise-Request-Id": operationId(requestId) } }),
    buyFarmAnimals: (animal, quantity, requestId) => request("/api/enterprise/farm/animals", { method: "POST", headers: { "Content-Type": "application/json", "X-Enterprise-Request-Id": operationId(requestId) }, body: JSON.stringify({ animal, quantity }) }),
    buyBusinessComputers: (quantity, options = {}, requestId) => request("/api/enterprise/business/computers", { method: "POST", headers: { "Content-Type": "application/json", "X-Enterprise-Request-Id": operationId(requestId) }, body: JSON.stringify({ quantity, ...options }) }),
    hireBusinessWorkers: (quantity, requestId) => request("/api/enterprise/business/workers", { method: "POST", headers: { "Content-Type": "application/json", "X-Enterprise-Request-Id": operationId(requestId) }, body: JSON.stringify({ quantity }) }),
    buyBusinessAdvertising: (campaign, requestId) => request("/api/enterprise/business/advertising", { method: "POST", headers: { "Content-Type": "application/json", "X-Enterprise-Request-Id": operationId(requestId) }, body: JSON.stringify({ campaign }) }),
    claimEnterpriseIncome: (system, requestId) => request(`/api/enterprise/${encodeURIComponent(system)}/claim`, { method: "POST", headers: { "X-Enterprise-Request-Id": operationId(requestId) } }),
    getBankMarket: () => request("/api/enterprise/bank/market"),
    upgradeBankAttraction: (requestId) => request("/api/enterprise/bank/attraction/upgrade", { method: "POST", headers: { "X-Bank-Request-Id": operationId(requestId) } }),
    collectBankProfit: (requestId) => request("/api/enterprise/bank/profit/collect", { method: "POST", headers: { "X-Bank-Request-Id": operationId(requestId) } }),
    processBankCustomer: (requestId) => request("/api/enterprise/bank/customer", { method: "POST", headers: { "X-Bank-Request-Id": operationId(requestId) } }),
    claimBankDividends: (requestId) => request("/api/enterprise/bank/dividends/claim", { method: "POST", headers: { "X-Bank-Request-Id": operationId(requestId) } }),
    withdrawBankProfit: (amount, requestId) => request("/api/enterprise/bank/withdraw", { method: "POST", headers: { "Content-Type": "application/json", "X-Bank-Request-Id": operationId(requestId) }, body: JSON.stringify({ amount }) }),
    tradeBankStock: (code, side, quantity, requestId) => request(`/api/enterprise/bank/stocks/${encodeURIComponent(code)}/trade`, { method: "POST", headers: { "Content-Type": "application/json", "X-Bank-Request-Id": operationId(requestId) }, body: JSON.stringify({ side, quantity }) }),
    tradeBankCrypto: (code, side, quantity, requestId) => request(`/api/enterprise/bank/crypto/${encodeURIComponent(code)}/trade`, { method: "POST", headers: { "Content-Type": "application/json", "X-Bank-Request-Id": operationId(requestId) }, body: JSON.stringify({ side, quantity: Number(quantity) }) }),
    claimEarnings: (system, requestId) => request(`/api/earnings/${encodeURIComponent(system)}/claim`, { method: "POST", headers: { "X-Earnings-Request-Id": operationId(requestId) } }),
    upgradeEarnings: (system, requestId) => request(`/api/earnings/${encodeURIComponent(system)}/upgrade`, { method: "POST", headers: { "X-Earnings-Request-Id": operationId(requestId) } }),
    startJob: (kind) => request(`/api/earnings/${encodeURIComponent(kind)}/start`, { method: "POST" }),
    completeJob: (sessionId) => request(`/api/earnings/jobs/${encodeURIComponent(sessionId)}/complete`, { method: "POST" }),
    getMarket: () => request("/api/market"), getGameMarket: (period) => request(`/api/market/game?period=${encodeURIComponent(period || "1D")}`), tradeGameMarket: (code, side, quantity, requestId) => request(`/api/market/game/${encodeURIComponent(code)}/trade`, { method: "POST", headers: { "Content-Type": "application/json", "X-Market-Request-Id": operationId(requestId) }, body: JSON.stringify({ side, quantity }) }),
    buyMarketOffer: (offerId, requestId) => request("/api/market/buy", { method: "POST", headers: { "Content-Type": "application/json", "X-Market-Request-Id": requestId }, body: JSON.stringify({ offer_id: offerId, quantity: 1 }) }),
    getWorld: () => request("/api/world"),
    getProfile: () => request("/api/profile"),
    getAchievements: () => request("/api/achievements"),
    getDaily: () => request("/api/daily"),
    claimDaily: () => request("/api/daily/claim", { method: "POST" }),
  };
}());
