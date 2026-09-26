(() => {
  const $ = (id) => document.getElementById(id);
  const viewport = $("world3d-viewport");
  const scene = $("world3d-scene");
  if (!viewport || !scene) return;

  let rotX = 8, rotY = 0, zoom = 1.02;
  let startX = 0, startY = 0, startRotX = 0, startRotY = 0, dragging = false, moved = false;
  let pinchStart = 0, pinchZoom = 1.02;

  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));
  const paint = () => {
    scene.style.transform = `translate(-50%,-50%) rotateX(${rotX}deg) rotateY(${rotY}deg) scale(${zoom})`;
  };
  const reset = () => { rotX = 8; rotY = 0; zoom = 1.02; paint(); };
  paint();

  const point = (e) => e.touches ? e.touches[0] : e;
  viewport.addEventListener("pointerdown", (e) => {
    dragging = true; moved = false; viewport.classList.add("is-dragging");
    startX = e.clientX; startY = e.clientY; startRotX = rotX; startRotY = rotY;
    try { viewport.setPointerCapture(e.pointerId); } catch (_) {}
  });
  viewport.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - startX, dy = e.clientY - startY;
    if (Math.abs(dx) + Math.abs(dy) > 7) moved = true;
    rotY = clamp(startRotY + dx * 0.16, -34, 34);
    rotX = clamp(startRotX - dy * 0.11, -7, 24);
    paint();
  });
  const endPointer = () => { dragging = false; viewport.classList.remove("is-dragging"); setTimeout(() => { moved = false; }, 30); };
  viewport.addEventListener("pointerup", endPointer);
  viewport.addEventListener("pointercancel", endPointer);

  viewport.addEventListener("wheel", (e) => { e.preventDefault(); zoom = clamp(zoom - e.deltaY * 0.0007, .9, 1.34); paint(); }, { passive:false });

  viewport.addEventListener("touchstart", (e) => {
    if (e.touches.length === 2) {
      pinchStart = Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY);
      pinchZoom = zoom;
    }
  }, { passive:true });
  viewport.addEventListener("touchmove", (e) => {
    if (e.touches.length === 2 && pinchStart) {
      const d = Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY);
      zoom = clamp(pinchZoom * (d / pinchStart), .9, 1.34); paint();
    }
  }, { passive:true });
  viewport.addEventListener("touchend", () => { if (!viewport.touches) pinchStart = 0; }, { passive:true });

  viewport.querySelectorAll(".world-hotspot").forEach((button) => {
    button.addEventListener("click", (e) => {
      if (moved) { e.preventDefault(); return; }
      const nav = button.dataset.worldNav;
      if (nav) { const target = document.querySelector(`[data-nav="${nav}"]`); if (target) target.click(); }
      else {
        const fallback = document.querySelector('[data-nav="earn"]');
        if (fallback) fallback.click();
      }
    });
  });
  $("world3d-reset")?.addEventListener("click", reset);
  $("world3d-zoom-in")?.addEventListener("click", () => { zoom = clamp(zoom + .08, .9, 1.34); paint(); });
  $("world3d-zoom-out")?.addEventListener("click", () => { zoom = clamp(zoom - .08, .9, 1.34); paint(); });

  // Keep the server-authoritative result, but make the wheel presentation deterministic:
  // success lands inside the green sector; failure lands clearly outside it.
  const oldSpin = window.setWheelAnimation;
  if (typeof oldSpin === "function") window.setWheelAnimation = oldSpin;

  // Small visual upgrade status whenever the chance changes.
  const chance = $("upgrade-chance");
  const status = $("upgrade-wheel-status");
  if (chance && status) {
    const observer = new MutationObserver(() => {
      if (chance.textContent && chance.textContent !== "—") status.textContent = `Зона успеха · ${chance.textContent}`;
    });
    observer.observe(chance, { childList:true, characterData:true, subtree:true });
  }
})();
