/* In-world SH Market. Every price, chart point and trade comes from the backend. */
(function () {
  "use strict";
  const root = document.querySelector("#game-market-root");
  if (!root || !window.api) return;
  let market = null;
  let selectedCode = "SHX";
  let period = "1D";
  let loading = false;
  const ids = new Map();
  const money = (value) => Math.floor(Number(value) || 0).toLocaleString("ru-RU");
  const esc = (value) => String(value ?? "").replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));
  const requestId = (key) => { if (!ids.has(key)) ids.set(key, window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`); return ids.get(key); };

  function chart(points) {
    if (!points || points.length < 2) return '<div class="game-chart-empty">История игрового актива собирается на сервере.</div>';
    const width = 640, height = 150, left = 8, top = 12, bottom = 18;
    const values = points.map((point) => Number(point.value) || 0); const min = Math.min(...values); const max = Math.max(...values); const spread = max - min || Math.max(1, max * .05);
    const coordinates = points.map((point, index) => ({ x: left + index * (width - left * 2) / (points.length - 1), y: top + (max - Number(point.value)) * (height - top - bottom) / spread, point }));
    const d = coordinates.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ");
    const dots = coordinates.filter((_, index) => index === 0 || index === coordinates.length - 1 || index % Math.ceil(coordinates.length / 8) === 0).map((point) => `<circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="3"><title>${new Date(point.point.time).toLocaleString("ru-RU")} · ${money(point.point.value)} SH</title></circle>`).join("");
    return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="График игровой цены"><path class="game-chart-grid" d="M${left} ${height - bottom}H${width - left} M${left} ${height / 2}H${width - left}"/><path class="game-chart-line" d="${d}"/>${dots}</svg><div class="game-chart-range"><span>${money(min)} SH</span><strong>${money(max)} SH</strong></div>`;
  }

  function render() {
    if (!market) return;
    const asset = market.assets.find((row) => row.code === selectedCode) || market.assets[0];
    if (!asset) { root.innerHTML = ""; return; }
    selectedCode = asset.code;
    const change = Number(asset.change_percent || 0); const sign = change >= 0 ? "+" : "";
    root.innerHTML = `<section class="game-market card"><div class="game-market-head"><div><span class="eyebrow">SH MARKET · ${esc(market.source)}</span><h2>Игровые активы</h2></div><span>UPDATED ${new Date(market.updated_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</span></div><div class="game-assets">${market.assets.map((row) => `<button type="button" class="game-asset ${row.code === asset.code ? "is-active" : ""}" data-game-asset="${row.code}"><strong>${row.code}</strong><small>${esc(row.name)}</small><b>${money(row.price)} SH</b><i class="${Number(row.change_percent) >= 0 ? "is-up" : "is-down"}">${Number(row.change_percent) >= 0 ? "▲" : "▼"} ${Math.abs(Number(row.change_percent)).toFixed(2)}%</i></button>`).join("")}</div><article class="game-market-focus"><div class="game-market-price"><span>${esc(asset.name)} · ${esc(asset.category)}</span><strong>${money(asset.price)} <i>SH</i></strong><b class="${change >= 0 ? "is-up" : "is-down"}">${sign}${change.toFixed(2)}%</b></div><div class="game-market-periods">${["1D", "7D", "1M"].map((item) => `<button type="button" data-game-period="${item}" class="${item === period ? "is-active" : ""}">${item}</button>`).join("")}</div><div class="game-chart">${chart(asset.history)}</div><div class="game-holding"><span>ТВОЯ ПОЗИЦИЯ <b>${asset.holding} шт.</b></span><span>AVG ${asset.average_price ? `${money(asset.average_price)} SH` : "—"}</span><span class="${Number(asset.pnl) >= 0 ? "is-up" : "is-down"}">P&amp;L ${Number(asset.pnl) >= 0 ? "+" : ""}${money(asset.pnl)} SH</span></div><div class="game-trade"><input id="game-market-quantity" type="number" inputmode="numeric" min="1" value="1" aria-label="Количество игровых активов"/><button type="button" class="button button-primary" data-game-trade="buy">BUY ${asset.code}</button><button type="button" class="button button-secondary" data-game-trade="sell" ${asset.holding < 1 ? "disabled" : ""}>SELL ${asset.code}</button></div></article><p class="game-market-note">Цены, графики и активы являются игровой симуляцией SHAMA WORLD. Реальные финансовые активы здесь не используются.</p></section>`;
  }

  async function load(nextPeriod) {
    if (loading) return;
    loading = true;
    if (nextPeriod) period = nextPeriod;
    try { market = await window.api.getGameMarket(period); render(); }
    catch (error) { root.innerHTML = `<p class="works-error">${esc(error.message || "SH Market недоступен")}</p>`; }
    finally { loading = false; }
  }

  root.addEventListener("click", (event) => {
    const asset = event.target.closest("[data-game-asset]");
    if (asset) { selectedCode = asset.dataset.gameAsset; render(); return; }
    const nextPeriod = event.target.closest("[data-game-period]");
    if (nextPeriod) { load(nextPeriod.dataset.gamePeriod); return; }
    const trade = event.target.closest("[data-game-trade]");
    if (!trade || trade.disabled || !market) return;
    const active = market.assets.find((row) => row.code === selectedCode); if (!active) return;
    const quantity = Math.max(1, Math.trunc(Number(root.querySelector("#game-market-quantity")?.value) || 1));
    const side = trade.dataset.gameTrade; const key = `${active.code}:${side}:${quantity}`;
    trade.disabled = true; const text = trade.textContent; trade.textContent = "ОБРАБОТКА…";
    window.api.tradeGameMarket(active.code, side.toUpperCase(), quantity, requestId(key)).then((result) => {
      ids.delete(key); const balance = document.querySelector("#global-balance"); if (balance) balance.textContent = `◈ ${money(result.balance)} SH`; if (window.shamaToast) window.shamaToast(`${result.side} ${result.asset_code} · ${money(result.total)} SH`); return load();
    }).catch((error) => { trade.disabled = false; trade.textContent = text; if (window.shamaToast) window.shamaToast(error.message || "Операция не выполнена", "error"); });
  });

  const page = document.querySelector("#page-market");
  new MutationObserver(() => { if (page.classList.contains("is-active")) load(); }).observe(page, { attributes: true, attributeFilter: ["class"] });
  document.addEventListener("DOMContentLoaded", () => { if (page.classList.contains("is-active")) load(); });
})();
