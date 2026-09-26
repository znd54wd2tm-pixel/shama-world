(() => {
  const viewport = document.getElementById('world3d-viewport');
  const scene = document.getElementById('world3d-scene');
  if (!viewport || !scene) return;

  let rotX = 58, rotY = -22, zoom = 0.92;
  let startX = 0, startY = 0, startRotX = 58, startRotY = -22;
  let dragging = false, moved = false;
  const pointers = new Map();
  let pinchStart = 0, pinchZoom = zoom;
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  function paint() {
    scene.style.transform = `translate(-50%,-50%) rotateX(${rotX}deg) rotateZ(${rotY}deg) scale(${zoom})`;
  }
  function reset() { rotX = 58; rotY = -22; zoom = 0.92; paint(); }
  function distance() {
    const p = [...pointers.values()];
    if (p.length < 2) return 0;
    return Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
  }
  paint();

  viewport.addEventListener('pointerdown', (e) => {
    pointers.set(e.pointerId, {x:e.clientX, y:e.clientY});
    try { viewport.setPointerCapture(e.pointerId); } catch (_) {}
    if (pointers.size === 1) {
      dragging = true; moved = false;
      startX = e.clientX; startY = e.clientY;
      startRotX = rotX; startRotY = rotY;
      viewport.classList.add('is-dragging');
    } else if (pointers.size === 2) {
      dragging = false;
      pinchStart = distance(); pinchZoom = zoom;
    }
  });

  viewport.addEventListener('pointermove', (e) => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, {x:e.clientX, y:e.clientY});
    if (pointers.size >= 2) {
      const d = distance();
      if (pinchStart && d) { zoom = clamp(pinchZoom * (d / pinchStart), .72, 1.65); paint(); }
      moved = true;
      return;
    }
    if (!dragging) return;
    const dx = e.clientX - startX, dy = e.clientY - startY;
    if (Math.abs(dx) + Math.abs(dy) > 7) moved = true;
    rotY = startRotY + dx * .24;
    rotX = clamp(startRotX - dy * .16, 38, 78);
    paint();
  });

  function endPointer(e) {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinchStart = 0;
    if (pointers.size === 0) {
      dragging = false;
      viewport.classList.remove('is-dragging');
      window.setTimeout(() => { moved = false; }, 50);
    }
  }
  viewport.addEventListener('pointerup', endPointer);
  viewport.addEventListener('pointercancel', endPointer);
  viewport.addEventListener('wheel', (e) => {
    e.preventDefault();
    zoom = clamp(zoom - e.deltaY * .0008, .72, 1.65);
    paint();
  }, {passive:false});

  viewport.querySelectorAll('.world-hotspot').forEach((button) => {
    button.addEventListener('click', (e) => {
      if (moved) { e.preventDefault(); return; }
      const type = button.dataset.worldType;
      const destination = ({market:'market',stadium:'earn',farm:'earn',business:'earn',bank:'earn',courier:'earn',factory:'earn',profile:'profile'})[type] || button.dataset.worldNav;
      if (destination) document.querySelector(`[data-nav="${destination}"]`)?.click();
    });
  });
  document.getElementById('world3d-reset')?.addEventListener('click', reset);
  document.getElementById('world3d-zoom-in')?.addEventListener('click', () => { zoom = clamp(zoom + .08, .72, 1.65); paint(); });
  document.getElementById('world3d-zoom-out')?.addEventListener('click', () => { zoom = clamp(zoom - .08, .72, 1.65); paint(); });

  const chance = document.getElementById('upgrade-chance');
  const status = document.getElementById('upgrade-wheel-status');
  if (chance && status) {
    const observer = new MutationObserver(() => {
      if (chance.textContent && chance.textContent !== '—') status.textContent = `Зона успеха · ${chance.textContent}`;
    });
    observer.observe(chance, {childList:true, characterData:true, subtree:true});
  }
})();
