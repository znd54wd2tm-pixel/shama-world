(function () {
  "use strict";
  const host = document.querySelector("#enterprise-detail");
  if (!host) return;
  const colors = ["#d7b45d", "#8b6d32", "#f4edda", "#6c542a", "#ad955b", "#56482f"];
  let panel = null, market = null, savings = null, transactions = [];
  let selectedAsset = "PORTFOLIO", selectedPeriod = "1D", sequence = 0;
  const requestIds = new Map();

  function money(value) { return Math.floor(Number(value) || 0).toLocaleString("ru-RU"); }
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char];
    });
  }
  function requestId(key) {
    if (requestIds.has(key)) return requestIds.get(key);
    const storageKey = "shama-bank-request:" + key;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) return saved;
    } catch (_) { /* Keep the retry key in memory when storage is unavailable. */ }
    const id = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() :
      Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
    requestIds.set(key, id);
    try { localStorage.setItem(storageKey, id); } catch (_) { /* Private browsing may disable storage. */ }
    return id;
  }
  function clearRequestId(key) {
    requestIds.delete(key);
    try { localStorage.removeItem("shama-bank-request:" + key); } catch (_) { /* Private browsing may disable storage. */ }
  }
  async function api(path, options) {
    options = options || {};
    const telegram = window.Telegram && window.Telegram.WebApp;
    const headers = Object.assign({}, options.headers || {});
    if (telegram && telegram.initData) headers.Authorization = "tma " + telegram.initData;
    const response = await fetch(path, Object.assign({}, options, { headers: headers }));
    let payload = {};
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(payload.detail || payload.error || "BANK REQUEST FAILED");
    return payload;
  }
  function bankPanel() {
    const item = host.querySelector(".enterprise-panel");
    const title = item && item.querySelector(".enterprise-panel-head h2");
    return title && title.textContent.trim() === "BANK" ? item : null;
  }
  function assets() {
    if (!market) return [];
    return (market.companies || []).map(function (a) { return Object.assign({ kind: "stock" }, a); })
      .concat((market.crypto || []).map(function (a) { return Object.assign({ kind: "crypto" }, a); }));
  }
  function selected() {
    return selectedAsset === "PORTFOLIO" ? null : assets().find(function (a) { return a.code === selectedAsset; }) || null;
  }
  function periods(asset) {
    return asset && asset.kind === "crypto" ? ["1H", "1D", "1W", "1M", "1Y"] : ["1D", "1W", "1M", "3M", "1Y"];
  }
  function points() {
    const asset = selected();
    return asset ? (asset.history_points || []) : ((market.portfolio && market.portfolio.history) || []);
  }
  function drawChart(target, rows) {
    target.replaceChildren();
    if (!rows || rows.length < 2) {
      const empty = document.createElement("p");
      empty.className = "bank-chart-empty";
      empty.textContent = "График заполнится по мере накопления серверной истории.";
      target.appendChild(empty);
      return;
    }
    const w = 720, h = 190, left = 32, right = 10, top = 14, bottom = 23;
    const values = rows.map(function (x) { return Number(x.value) || 0; });
    const low = Math.min.apply(null, values), high = Math.max.apply(null, values);
    const spread = high - low || Math.max(1, Math.abs(high) * .02);
    const xy = rows.map(function (row, i) {
      return { x: left + i * (w - left - right) / (rows.length - 1), y: top + (high - Number(row.value)) * (h - top - bottom) / spread, row: row };
    });
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 " + w + " " + h);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "История стоимости актива");
    const grid = document.createElementNS(ns, "path");
    grid.setAttribute("d", "M" + left + " " + (h - bottom) + "H" + (w - right) + "M" + left + " " + h / 2 + "H" + (w - right));
    grid.setAttribute("class", "bank-chart-grid");
    svg.appendChild(grid);
    const line = document.createElementNS(ns, "path");
    line.setAttribute("d", xy.map(function (p, i) { return (i ? "L" : "M") + p.x.toFixed(2) + " " + p.y.toFixed(2); }).join(" "));
    line.setAttribute("class", "bank-chart-line");
    svg.appendChild(line);
    xy.forEach(function (p) {
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("cx", p.x.toFixed(2));
      circle.setAttribute("cy", p.y.toFixed(2));
      circle.setAttribute("r", rows.length > 80 ? "1.8" : "3.2");
      circle.setAttribute("class", "bank-chart-point");
      const title = document.createElementNS(ns, "title");
      const date = new Date(p.row.time);
      title.textContent = (isNaN(date.getTime()) ? p.row.time : date.toLocaleString("ru-RU")) + " · " + money(p.row.value) + " SH";
      circle.appendChild(title);
      svg.appendChild(circle);
    });
    target.appendChild(svg);
    const range = document.createElement("div");
    range.className = "bank-chart-range";
    range.innerHTML = "<span>" + esc(new Date(rows[0].time).toLocaleString("ru-RU")) + "</span><b>" + money(high) + " SH</b><span>" + esc(new Date(rows[rows.length - 1].time).toLocaleString("ru-RU")) + "</span>";
    target.appendChild(range);
  }
  function gradient(list) {
    let cursor = 0;
    const stops = [];
    (list || []).filter(function (a) { return Number(a.value) > 0; }).forEach(function (a, i) {
      const next = Math.min(100, cursor + Number(a.percent || 0));
      stops.push(colors[i % colors.length] + " " + cursor + "% " + next + "%");
      cursor = next;
    });
    if (!stops.length) return "conic-gradient(#302b20 0 100%)";
    if (cursor < 100) stops.push("#302b20 " + cursor + "% 100%");
    return "conic-gradient(" + stops.join(",") + ")";
  }
  function render() {
    if (!panel || !market || !savings) return;
    const widget = panel.querySelector("[data-bank-widget]");
    if (!widget) return;
    const p = market.portfolio || {}, account = savings.account || {}, chosen = selected();
    const allocation = p.allocation || [];
    const allocationHtml = allocation.map(function (a, i) {
      return '<div class="bank-allocation-row"><i class="allocation-dot allocation-dot--' + (i % 6) + '"></i><span>' + esc(a.name) + '</span><b>' + Number(a.percent || 0).toFixed(1) + "%</b></div>";
    }).join("") || '<small class="muted">Портфель появится после первых инвестиций.</small>';
    const periodHtml = periods(chosen).map(function (period) {
      return '<button type="button" data-bank-period="' + period + '" class="' + (period === selectedPeriod ? "is-active" : "") + '">' + period + "</button>";
    }).join("");
    const assetHtml = '<button type="button" data-bank-asset="PORTFOLIO" class="' + (selectedAsset === "PORTFOLIO" ? "is-active" : "") + '">PORTFOLIO</button>' +
      assets().map(function (a) { return '<button type="button" data-bank-asset="' + esc(a.code) + '" class="' + (selectedAsset === a.code ? "is-active" : "") + '">' + esc(a.code) + "</button>"; }).join("");
    const source = chosen ? (chosen.source || (chosen.kind === "stock" ? "DEMO" : p.crypto_source || "CACHED")) : "SAVED SNAPSHOTS";
    const name = chosen ? chosen.name : "PORTFOLIO VALUE";
    const price = chosen ? chosen.price : p.total_assets;
    const savingsRate = (Number(account.rate || .042) * 100).toFixed(1);
    const txHtml = transactions.slice(0, 12).map(function (t) {
      return '<div class="bank-transaction"><span><b>' + esc(String(t.entry_type || "").replaceAll("_", " ")) + '</b><small>' + esc(t.description) + " · " + esc(t.created_at) + '</small></span><strong>' + money(t.amount) + " SH</strong></div>";
    }).join("") || '<p class="muted">История операций пока пуста.</p>';

    widget.innerHTML =
      '<section class="bank-dashboard"><div class="bank-dashboard-hero"><span class="eyebrow">TOTAL ASSETS · VIRTUAL ECONOMY</span><strong>' + money(p.total_assets) + ' <small>SH</small></strong><span class="bank-pnl">P&amp;L ' + (Number(p.total_pnl) >= 0 ? "+" : "") + money(p.total_pnl) + " SH</span></div>" +
      '<div class="bank-dashboard-metrics"><div><small>CLIENT MONEY</small><b>' + money(p.client_money) + ' SH</b></div><div><small>OWN CAPITAL</small><b>' + money(p.own_capital) + ' SH</b></div><div><small>AVAILABLE CASH</small><b>' + money(p.available_cash) + ' SH</b></div><div><small>INVESTMENTS</small><b>' + money(p.portfolio_value) + ' SH</b></div></div>' +
      '<div class="bank-portfolio-overview"><div class="bank-donut" style="background:' + gradient(allocation) + '" role="img" aria-label="Распределение активов"></div><div class="bank-allocation-legend">' + allocationHtml + "</div></div>" +
      '<div class="bank-market-status"><span><i class="status-dot is-demo"></i>STOCKS · DEMO</span><span><i class="status-dot ' + (p.crypto_source === "LIVE" ? "is-live" : "is-demo") + '"></i>CRYPTO · ' + esc(p.crypto_source || "DEMO") + "</span></div></section>" +
      '<section class="bank-chart-card"><div class="bank-chart-heading"><div><span class="eyebrow">MARKET HISTORY · ' + esc(source) + "</span><h3>" + esc(name) + '</h3></div><strong>' + money(price) + " SH</strong></div><div class=\"bank-chart-assets\">" + assetHtml + '</div><div class="bank-chart-periods">' + periodHtml + '</div><div class="bank-chart-plot" data-bank-chart></div></section>' +
      '<section class="bank-accounts"><article class="bank-account-card"><div><span class="eyebrow">CURRENT ACCOUNT</span><strong>' + money(account.current_account) + ' SH</strong><small>Свободный баланс игрока</small></div><div><span class="eyebrow">SAVINGS</span><strong>' + money(account.balance) + ' SH</strong><small>' + savingsRate + "% годовых · +" + money(account.estimated_daily) + ' SH / день</small></div><div><span class="eyebrow">EST. MONTHLY</span><strong>+' + money(account.estimated_monthly) + ' SH</strong><small>Начисление рассчитывает сервер</small></div></article><div class="bank-savings-actions"><input type="number" min="1" step="1" value="100" inputmode="numeric" data-bank-amount aria-label="Сумма перевода на накопительный счёт"/><button type="button" class="button button-primary" data-bank-move="deposit">ПОПОЛНИТЬ НАКОПИТЕЛЬНЫЙ</button><button type="button" class="button button-secondary" data-bank-move="withdraw" ' + (Number(account.available_balance || 0) < 1 ? "disabled" : "") + '>ВЫВЕСТИ НАКОПЛЕНИЯ</button><span class="bank-savings-status" aria-live="polite"></span></div></section>' +
      '<section class="bank-transactions"><div class="enterprise-section-title"><span class="eyebrow">BANK TRANSACTIONS</span></div>' + txHtml + "</section>";
    drawChart(widget.querySelector("[data-bank-chart]"), chosen ? chosen.history_points : p.history);
  }
  async function loadData(target, period) {
    const id = ++sequence;
    selectedPeriod = period || selectedPeriod;
    const result = await Promise.all([
      api("/api/enterprise/bank/market?period=" + encodeURIComponent(selectedPeriod)),
      api("/api/enterprise/bank/savings"),
      api("/api/enterprise/bank/transactions")
    ]);
    if (id !== sequence || panel !== target || !target.isConnected) return;
    market = result[0]; savings = result[1]; transactions = result[2].transactions || [];
    render();
  }
  async function moveSavings(button) {
    const target = panel, status = target && target.querySelector(".bank-savings-status");
    const input = target && target.querySelector("[data-bank-amount]");
    const amount = Math.trunc(Number(input && input.value) || 0);
    const direction = button.getAttribute("data-bank-move");
    if (!target || amount < 1 || button.disabled) return;
    const requestKey = direction + ":" + amount;
    button.disabled = true;
    if (status) status.textContent = "ОБРАБОТКА…";
    try {
      const result = await api("/api/enterprise/bank/savings/" + direction, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Bank-Request-Id": requestId(requestKey) },
        body: JSON.stringify({ amount: amount })
      });
      const balance = document.querySelector("#global-balance");
      if (balance) balance.textContent = "◈ " + money(result.current_account) + " SH";
      if (status) status.textContent = "ОПЕРАЦИЯ ВЫПОЛНЕНА";
      await loadData(target, selectedPeriod);
      clearRequestId(requestKey);
    } catch (error) {
      if (status) status.textContent = error.message || "ОПЕРАЦИЯ НЕ ВЫПОЛНЕНА";
    } finally {
      if (button.isConnected) button.disabled = false;
    }
  }
  async function enhance(target) {
    if (target.dataset.bankEnhanced === "1") return;
    target.dataset.bankEnhanced = "1";
    panel = target;
    target.querySelectorAll("[data-trade-price]").forEach(function (input) { input.remove(); });
    target.querySelectorAll("[data-stock-trade], [data-crypto-trade]").forEach(function (button) {
      const buy = button.dataset.stockTrade === "buy" || button.dataset.cryptoTrade === "buy";
      button.textContent = buy ? "BUY AT MARKET" : "SELL AT MARKET";
    });
    const head = target.querySelector(".enterprise-panel-head");
    if (!head) return;
    const widget = document.createElement("div");
    widget.className = "bank-enhanced-ui";
    widget.setAttribute("data-bank-widget", "");
    head.insertAdjacentElement("afterend", widget);
    widget.addEventListener("click", function (event) {
      const period = event.target.closest("[data-bank-period]");
      if (period) { loadData(target, period.getAttribute("data-bank-period")).catch(showError); return; }
      const asset = event.target.closest("[data-bank-asset]");
      if (asset) {
        selectedAsset = asset.getAttribute("data-bank-asset");
        const options = periods(selected());
        if (options.indexOf(selectedPeriod) < 0) selectedPeriod = "1D";
        render();
        return;
      }
      const move = event.target.closest("[data-bank-move]");
      if (move) moveSavings(move);
    });
    try { await loadData(target, "1D"); } catch (error) { widget.textContent = error.message; }
  }
  function showError(error) {
    const plot = panel && panel.querySelector("[data-bank-chart]");
    if (plot) plot.textContent = error.message || "BANK DATA UNAVAILABLE";
  }
  const observer = new MutationObserver(function () {
    const target = bankPanel();
    if (!target) { panel = null; return; }
    if (target !== panel && target.dataset.bankEnhanced !== "1") enhance(target);
  });
  observer.observe(host, { childList: true, subtree: true });
  const initial = bankPanel();
  if (initial) enhance(initial);
})();
