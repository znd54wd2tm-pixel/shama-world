/* Final navigation guard: keeps the Mini App usable even if a secondary renderer fails. */
(function () {
  "use strict";
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".nav-item").forEach((button) => {
      button.addEventListener("pointerup", () => button.classList.add("nav-tap"), { passive: true });
      button.addEventListener("animationend", () => button.classList.remove("nav-tap"), { passive: true });
    });
  });
})();
