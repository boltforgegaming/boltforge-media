var BOLTFORGE_EMBEDS = {
  bookingsUrl: "BOOKINGS_URL",
  salesiqWidgetCode: "SALESIQ_WIDGET_CODE"
};

(function () {
  var config = BOLTFORGE_EMBEDS;

  function isPlaceholder(value, token) {
    return typeof value !== "string" || value.trim() === "" || value.indexOf(token) !== -1;
  }

  function mountBookings() {
    var mount = document.querySelector("[data-bookings]");
    if (!mount || mount.querySelector("iframe")) return;
    var url = config.bookingsUrl;
    if (isPlaceholder(url, "BOOKINGS_URL") || url.indexOf("https://") !== 0) return;
    var frame = document.createElement("iframe");
    frame.className = "bookings-frame";
    frame.src = url;
    frame.title = "Book a showroom visit";
    frame.loading = "lazy";
    var fallback = mount.querySelector("[data-bookings-fallback]");
    if (fallback) fallback.hidden = true;
    mount.appendChild(frame);
  }

  function loadSalesIq() {
    var code = config.salesiqWidgetCode;
    if (isPlaceholder(code, "SALESIQ_WIDGET_CODE") || document.getElementById("zsiqscript")) return;
    var start = function () {
      if (document.getElementById("zsiqscript")) return;
      var zoho = window.$zoho = window.$zoho || {};
      zoho.salesiq = zoho.salesiq || { widgetcode: code, values: {}, ready: function () {} };
      zoho.salesiq.widgetcode = code;
      var script = document.createElement("script");
      script.id = "zsiqscript";
      script.defer = true;
      script.src = "https://salesiq.zoho.com/widget";
      document.body.appendChild(script);
    };
    if ("requestIdleCallback" in window) requestIdleCallback(start, { timeout: 3000 });
    else window.addEventListener("load", start);
  }

  function bindMenu() {
    var nav = document.querySelector(".nav");
    var toggle = document.querySelector(".nav-toggle");
    var links = document.getElementById("site-nav");
    if (!nav || !toggle || !links || toggle.dataset.bound === "true") return;
    toggle.dataset.bound = "true";
    var setOpen = function (open) {
      nav.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    };
    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });
    links.addEventListener("click", function () { setOpen(false); });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setOpen(false);
    });
  }

  function boot() {
    mountBookings();
    loadSalesIq();
    bindMenu();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
