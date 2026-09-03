/* Sidebar chrome shared on every page: presentation mode toggle + keyboard
 * navigation across the 12 MAIN screens, and the reset-filters shortcut.
 * window.MAIN_SCREENS / window.CURRENT_SLUG are injected by base.html.
 */
(function () {
  const PRESO_KEY = "sscm_presentation_mode";

  function resizeAllCharts() {
    if (typeof Plotly === "undefined") return;
    document.querySelectorAll(".js-plotly-plot").forEach((el) => {
      try {
        Plotly.Plots.resize(el);
      } catch (e) {}
    });
  }

  function applyPresentationMode(on) {
    document.body.classList.toggle("presentation-mode", on);
    const btn = document.getElementById("presentation-toggle");
    if (btn) btn.textContent = on ? "Exit Presentation" : "Presentation Mode";
    // Chart containers change size on this CSS-only toggle; give layout a
    // moment to settle, then force Plotly to redraw at the new dimensions.
    window.dispatchEvent(new Event("resize"));
    setTimeout(resizeAllCharts, 60);
    setTimeout(resizeAllCharts, 300);
  }

  function initPresentationMode() {
    let on = false;
    try {
      on = sessionStorage.getItem(PRESO_KEY) === "1";
    } catch (e) {}
    applyPresentationMode(on);

    const btn = document.getElementById("presentation-toggle");
    if (btn) {
      btn.addEventListener("click", () => {
        const next = !document.body.classList.contains("presentation-mode");
        applyPresentationMode(next);
        try {
          sessionStorage.setItem(PRESO_KEY, next ? "1" : "0");
        } catch (e) {}
      });
    }

    document.addEventListener("keydown", (e) => {
      if (!document.body.classList.contains("presentation-mode")) return;
      const tag = (document.activeElement && document.activeElement.tagName) || "";
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;

      const screens = window.MAIN_SCREENS || [];
      const idx = screens.findIndex((s) => s.slug === window.CURRENT_SLUG);

      if (e.key === "Escape") {
        applyPresentationMode(false);
        try {
          sessionStorage.setItem(PRESO_KEY, "0");
        } catch (err) {}
      } else if (e.key === "ArrowRight" && idx >= 0 && idx < screens.length - 1) {
        window.location.href = "/" + screens[idx + 1].slug;
      } else if (e.key === "ArrowLeft" && idx > 0) {
        window.location.href = "/" + screens[idx - 1].slug;
      }
    });
  }

  function initResetFilters() {
    const btn = document.getElementById("reset-filters");
    if (!btn) return;
    btn.addEventListener("click", () => {
      try {
        localStorage.removeItem("sscm_assumptions");
      } catch (e) {}
      const url = new URL(window.location.href);
      url.search = "";
      window.location.href = url.toString();
    });
  }

  function initDownloadReport() {
    const btn = document.getElementById("download-report");
    if (!btn) return;
    btn.addEventListener("click", () => {
      window.print();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initPresentationMode();
    initResetFilters();
    initDownloadReport();
  });
})();
