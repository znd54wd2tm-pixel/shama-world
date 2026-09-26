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
  window.api = {
    health: () => request("/api/health"), getMe: () => request("/api/me"), getCases: () => request("/api/cases"),
    getCase: (id) => request(`/api/cases/${id}`), openCase: (id, requestId) => request(`/api/cases/${id}/open`, { method: "POST", headers: { "X-Opening-Request-Id": requestId } }),
    getInventory: () => request("/api/inventory"), getInventoryItem: (id) => request(`/api/inventory/${id}`), getBalance: () => request("/api/balance"),
    sellItem: (itemId, quantity, requestId) => request("/api/inventory/sell", { method: "POST", headers: { "Content-Type": "application/json", "X-Sell-Request-Id": requestId }, body: JSON.stringify({ item_id: itemId, quantity }) }),
    getTransactions: () => request("/api/transactions"),
    getUpgradeTargets: (sourceId) => request(`/api/upgrade/targets?source_item_id=${encodeURIComponent(sourceId)}`),
    previewUpgrade: (sourceId, targetId) => request("/api/upgrade/preview", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_item_id: sourceId, target_item_id: targetId }) }),
    executeUpgrade: (sourceId, targetId, requestId) => request("/api/upgrade/execute", { method: "POST", headers: { "Content-Type": "application/json", "X-Upgrade-Request-Id": requestId }, body: JSON.stringify({ source_item_id: sourceId, target_item_id: targetId }) }),
    getUpgradeHistory: () => request("/api/upgrade/history"),
    getEarnings: () => request("/api/earnings"),
    claimEarnings: (system) => request(`/api/earnings/${encodeURIComponent(system)}/claim`, { method: "POST" }),
    upgradeEarnings: (system) => request(`/api/earnings/${encodeURIComponent(system)}/upgrade`, { method: "POST" }),
    startJob: (kind) => request(`/api/earnings/${encodeURIComponent(kind)}/start`, { method: "POST" }),
    completeJob: (sessionId) => request(`/api/earnings/jobs/${encodeURIComponent(sessionId)}/complete`, { method: "POST" }),
    getMarket: () => request("/api/market"),
    buyMarketOffer: (offerId, requestId) => request("/api/market/buy", { method: "POST", headers: { "Content-Type": "application/json", "X-Market-Request-Id": requestId }, body: JSON.stringify({ offer_id: offerId, quantity: 1 }) }),
    getWorld: () => request("/api/world"),
    getProfile: () => request("/api/profile"),
    getAchievements: () => request("/api/achievements"),
    getDaily: () => request("/api/daily"),
    claimDaily: () => request("/api/daily/claim", { method: "POST" }),
  };
}());
