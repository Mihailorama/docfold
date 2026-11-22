// Site analytics (owner rule 2026-11-22): Umami counts visits without cookies and loads for every
// visitor; Google Analytics 4 sets cookies, so it loads only after the visitor clicks Accept.
// Config comes from this script tag: data-umami (Umami website id) and data-ga4 (measurement id).
(function () {
  var me = document.currentScript, KEY = "analytics-consent";
  var get = function () { try { return localStorage.getItem(KEY); } catch (e) { return null; } };
  var set = function (v) { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch (e) {} };

  var umami = document.createElement("script");
  umami.defer = true;
  umami.src = "https://web-analytics.aiagentlbs.app/script.js";
  umami.setAttribute("data-website-id", me.dataset.umami);
  document.head.appendChild(umami);

  function startGA() {
    if (window.gtag) return;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    window.gtag("config", me.dataset.ga4);
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + me.dataset.ga4;
    document.head.appendChild(s);
  }

  function dropGACookies() {
    document.cookie.split(";").forEach(function (c) {
      var name = c.split("=")[0].trim();
      if (name.indexOf("_ga") === 0) {
        [location.hostname, "." + location.hostname.split(".").slice(-2).join(".")].forEach(function (d) {
          document.cookie = name + "=; Max-Age=0; path=/; domain=" + d;
        });
        document.cookie = name + "=; Max-Age=0; path=/";
      }
    });
  }

  function banner() {
    var old = document.getElementById("analytics-consent");
    if (old) old.remove();
    var b = document.createElement("div");
    b.id = "analytics-consent";
    b.setAttribute("role", "dialog");
    b.setAttribute("aria-label", "Analytics cookies");
    b.style.cssText = "position:fixed;left:16px;right:16px;bottom:16px;max-width:560px;margin:0 auto;padding:14px 16px;" +
      "background:#16181d;color:#f3f4f6;font:14px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;border-radius:10px;" +
      "box-shadow:0 6px 24px rgba(0,0,0,.28);z-index:2147483000";
    var btn = "margin:10px 8px 0 0;padding:6px 14px;border-radius:6px;border:1px solid #6b7280;font:inherit;cursor:pointer;";
    b.innerHTML = "May we use Google Analytics cookies to see how this page is used? Visit counts without cookies (Umami) run either way." +
      "<br><button type=\"button\" data-v=\"yes\" style=\"" + btn + "background:#f3f4f6;color:#111\">Accept</button>" +
      "<button type=\"button\" data-v=\"no\" style=\"" + btn + "background:transparent;color:#f3f4f6\">Reject</button>";
    b.addEventListener("click", function (e) {
      var v = e.target.getAttribute && e.target.getAttribute("data-v");
      if (!v) return;
      var was = get();
      set(v);
      b.remove();
      if (v === "yes") startGA();
      else if (was === "yes") {
        if (window.gtag) window.gtag("consent", "update", { analytics_storage: "denied" });
        dropGACookies();
        location.reload();
      }
    });
    document.body.appendChild(b);
    b.querySelector("button").focus();
  }

  if (get() === "yes") startGA();
  else if (!get()) banner();
  document.addEventListener("click", function (e) {
    if (e.target && e.target.id === "cookie-settings") { e.preventDefault(); banner(); }
  });
})();
