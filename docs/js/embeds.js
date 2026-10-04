var BOLTFORGE_EMBEDS = {
  salesiqWidgetCode: "siqe62211ac8f26ff97ebbc0fff63048a1399ac0f63725b2b8517f08967f046a335"
};

(function () {
  if (window.__boltforgeEmbeds) return;
  window.__boltforgeEmbeds = true;

  var config = BOLTFORGE_EMBEDS;

  function isPlaceholder(value, token) {
    return typeof value !== "string" || value.trim() === "" || value.indexOf(token) !== -1;
  }

  function loadSalesIq() {
    var code = config.salesiqWidgetCode;
    if (isPlaceholder(code, "SALESIQ_WIDGET_CODE") || document.getElementById("zsiqscript")) return;
    var start = function () {
      if (document.getElementById("zsiqscript")) return;
      window.$zoho = window.$zoho || {};
      $zoho.salesiq = $zoho.salesiq || { ready: function () {} };
      var script = document.createElement("script");
      script.id = "zsiqscript";
      script.defer = true;
      script.src = "https://salesiq.zohopublic.com/widget?wc=" + encodeURIComponent(code);
      document.body.appendChild(script);
    };
    if ("requestIdleCallback" in window) requestIdleCallback(start, { timeout: 3000 });
    else window.addEventListener("load", start);
  }

  function setMenuOpen(nav, open) {
    var toggle = nav.querySelector(".nav-toggle");
    nav.classList.toggle("is-open", open);
    if (!toggle) return;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  }

  function bindMenu() {
    document.addEventListener("click", function (event) {
      var origin = event.target;
      if (!origin || !origin.closest) return;
      var toggle = origin.closest(".nav-toggle");
      if (toggle) {
        var nav = toggle.closest(".nav");
        if (!nav) return;
        setMenuOpen(nav, toggle.getAttribute("aria-expanded") !== "true");
        return;
      }
      var openNav = document.querySelector(".nav.is-open");
      if (!openNav || openNav.contains(origin)) return;
      setMenuOpen(openNav, false);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      var openNav = document.querySelector(".nav.is-open");
      if (openNav) setMenuOpen(openNav, false);
    });
  }

  function boot() {
    bindMenu();
    loadSalesIq();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
