(function () {
  "use strict";
  const viewport = document.getElementById("world3d-viewport");
  const scene = document.getElementById("world3d-scene");
  if (!viewport || !scene) return;

  let x = 0, y = 0, zoom = 1;
  let startX = 0, startY = 0, startTX = 0, startTY = 0;
  let dragging = false, moved = false;
  const pointers = new Map();
  let pinchStart = 0, pinchZoom = 1;
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  function limits() {
    const sw = scene.getBoundingClientRect().width;
    const sh = scene.getBoundingClientRect().height;
    const vw = viewport.clientWidth;
    const vh = viewport.clientHeight;
    const maxX = Math.max(0, (sw - vw) / 2);
    const maxY = Math.max(0, (sh - vh) / 2);
    return { maxX, maxY };
  }
  function paint() {
    const { maxX, maxY } = limits();
    x = clamp(x, -maxX, maxX); y = clamp(y, -maxY, maxY);
    scene.style.transform = `translate3d(calc(-50% + ${x}px), calc(-50% + ${y}px), 0) scale(${zoom})`;
  }
  function reset() { x = 0; y = 0; zoom = 1; paint(); }
  function distance() {
    const p = [...pointers.values()];
    if (p.length < 2) return 0;
    return Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
  }
  paint();

  viewport.addEventListener("pointerdown", (e) => {
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    try { viewport.setPointerCapture(e.pointerId); } catch (_) {}
    if (pointers.size === 1) {
      dragging = true; moved = false;
      startX = e.clientX; startY = e.clientY; startTX = x; startTY = y;
      viewport.classList.add("is-dragging");
    } else if (pointers.size === 2) {
      dragging = false; pinchStart = distance(); pinchZoom = zoom;
    }
  });
  viewport.addEventListener("pointermove", (e) => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size >= 2) {
      const d = distance();
      if (pinchStart && d) zoom = clamp(pinchZoom * d / pinchStart, .82, 1.7);
      moved = true; paint(); return;
    }
    if (!dragging) return;
    const dx = e.clientX - startX, dy = e.clientY - startY;
    if (Math.abs(dx) + Math.abs(dy) > 8) moved = true;
    x = startTX + dx; y = startTY + dy; paint();
  });
  function end(e) {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinchStart = 0;
    if (!pointers.size) {
      dragging = false; viewport.classList.remove("is-dragging");
      window.setTimeout(() => { moved = false; }, 70);
    }
  }
  viewport.addEventListener("pointerup", end);
  viewport.addEventListener("pointercancel", end);
  viewport.addEventListener("wheel", (e) => {
    e.preventDefault(); zoom = clamp(zoom - e.deltaY * .0007, .82, 1.7); paint();
  }, { passive: false });
  window.addEventListener("resize", paint);

  scene.querySelectorAll(".world-hotspot").forEach((button) => {
    button.addEventListener("click", (e) => {
      if (moved) { e.preventDefault(); return; }
      const destination = button.dataset.worldNav;
      if (destination) {
        const nav = document.querySelector(`.nav-item[data-nav="${destination}"]`) || document.querySelector(`[data-nav="${destination}"]`);
        if (nav) nav.click();
      }
    });
  });
  document.getElementById("world3d-reset")?.addEventListener("click", reset);
  document.getElementById("world3d-zoom-in")?.addEventListener("click", () => { zoom = clamp(zoom + .12, .82, 1.7); paint(); });
  document.getElementById("world3d-zoom-out")?.addEventListener("click", () => { zoom = clamp(zoom - .12, .82, 1.7); paint(); });
})();
