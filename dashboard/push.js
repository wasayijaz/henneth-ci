/* Henneth Desk — Web Push client helper.
   ============================================================================
   INERT UNTIL KEYED. This file ships dead: with no VAPID public key present it
   registers nothing, asks for no permission, renders no UI, and makes no network
   call. `PSXPush.available()` is false and `renderToggle()` writes an empty string,
   so a caller that wires it in today changes nothing for any existing visitor.
   Activation = the owner generating VAPID keys and setting the public one
   (docs/OPERATIONS.md §11). Absent keys are the designed off-state, not a fault.

   Style note: this is a CLASSIC script like app.js (the deploy copies plain files;
   index.html loads them with <script src>, no modules). It exports one global,
   `window.PSXPush`, and touches nothing else.
   ============================================================================ */
(function () {
  "use strict";

  var SW_PATH = "/sw.js";           // must be root-scoped to receive pushes site-wide
  var TABLE = "push_subscriptions"; // see docs/push_subscriptions.sql (RLS: owner-only)

  var cfg = {
    vapidPublicKey: null, // base64url VAPID public key — null = feature off
    sb: null,             // Supabase client (app.js's `sb`)
    userId: null,         // auth user id (app.js's `me.id`)
  };

  /* Reuse app.js's escaper when it has evaluated; fall back to an identical local one so
     push.js is safe to load in either order. */
  function escHtml(s) {
    if (typeof esc === "function") return esc(s);
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function keyOf() {
    // Explicit configure() wins; otherwise a global the page may define. Neither exists today.
    return cfg.vapidPublicKey || (typeof window !== "undefined" ? window.PSX_VAPID_PUBLIC_KEY : null) || null;
  }

  function supported() {
    return typeof navigator !== "undefined" && "serviceWorker" in navigator &&
      typeof window !== "undefined" && "PushManager" in window && "Notification" in window;
  }

  /* The single gate every entry point consults. False today, and false forever on any
     browser that can't do push — callers never need to branch on the reason. */
  function available() {
    return !!(supported() && keyOf());
  }

  function urlBase64ToUint8Array(b64) {
    var pad = "=".repeat((4 - (b64.length % 4)) % 4);
    var raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function registration() {
    // Never registers unless the feature is genuinely on.
    if (!available()) return Promise.resolve(null);
    return navigator.serviceWorker.register(SW_PATH, { scope: "/" }).catch(function () { return null; });
  }

  function currentSub() {
    if (!available()) return Promise.resolve(null);
    return navigator.serviceWorker.getRegistration(SW_PATH)
      .then(function (reg) { return reg ? reg.pushManager.getSubscription() : null; })
      .catch(function () { return null; });
  }

  /* status() -> "unavailable" | "denied" | "on" | "off"
     "unavailable" covers both "no keys yet" and "browser can't" — the UI treats them alike. */
  function status() {
    if (!available()) return Promise.resolve("unavailable");
    if (Notification.permission === "denied") return Promise.resolve("denied");
    return currentSub().then(function (s) { return s ? "on" : "off"; });
  }

  function rowFor(sub) {
    var j = sub.toJSON() || {};
    var keys = j.keys || {};
    return {
      user_id: cfg.userId,
      endpoint: j.endpoint || sub.endpoint,
      p256dh: keys.p256dh || null,
      auth: keys.auth || null,
      user_agent: String(navigator.userAgent || "").slice(0, 300),
    };
  }

  /* subscribe() -> {ok:true} | {ok:false, error:"<reason>"}
     Reasons are stable strings the caller can branch on: "unavailable", "not_signed_in",
     "denied", "dismissed", "save_failed", or a browser message. Never throws. */
  function subscribe() {
    if (!available()) return Promise.resolve({ ok: false, error: "unavailable" });
    if (!cfg.sb || !cfg.userId) return Promise.resolve({ ok: false, error: "not_signed_in" });
    return Notification.requestPermission().then(function (perm) {
      if (perm === "denied") return { ok: false, error: "denied" };
      if (perm !== "granted") return { ok: false, error: "dismissed" };
      return registration().then(function (reg) {
        if (!reg) return { ok: false, error: "unavailable" };
        return reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(keyOf()),
        }).then(function (sub) {
          // Upsert on endpoint: re-subscribing on the same browser must not duplicate rows.
          return cfg.sb.from(TABLE).upsert(rowFor(sub), { onConflict: "endpoint" })
            .then(function (res) { return res && res.error ? { ok: false, error: "save_failed" } : { ok: true }; });
        });
      });
    }).catch(function (err) { return { ok: false, error: (err && err.message) || String(err) }; });
  }

  /* unsubscribe() -> {ok:true} | {ok:false, error}. Drops the browser subscription first,
     then the row, so a failed delete can never leave a live endpoint the user opted out of. */
  function unsubscribe() {
    if (!available()) return Promise.resolve({ ok: false, error: "unavailable" });
    return currentSub().then(function (sub) {
      if (!sub) return { ok: true };
      var endpoint = sub.endpoint;
      return sub.unsubscribe().then(function () {
        if (!cfg.sb || !cfg.userId) return { ok: true };
        return cfg.sb.from(TABLE).delete().eq("endpoint", endpoint)
          .then(function (res) { return res && res.error ? { ok: false, error: "save_failed" } : { ok: true }; });
      });
    }).catch(function (err) { return { ok: false, error: (err && err.message) || String(err) }; });
  }

  /* renderToggle(hostEl) — paints a hard-cornered toggle into hostEl, or NOTHING (empty
     string, no listeners) when the feature is unavailable. Safe to call unconditionally. */
  function renderToggle(host) {
    if (!host) return Promise.resolve(false);
    if (!available()) { host.innerHTML = ""; return Promise.resolve(false); }
    return status().then(function (st) {
      if (st === "denied") {
        host.innerHTML = '<div class="sub">Alerts are blocked for this site in your browser settings. ' +
          "Re-allow notifications there to turn them back on.</div>";
        return false;
      }
      var on = st === "on";
      host.innerHTML = '<button class="auth-go" id="pushToggle" style="max-width:260px">' +
        escHtml(on ? "Turn off watchlist alerts" : "Alert me about my watchlist") + "</button>" +
        '<span class="sub" id="pushMsg" style="display:block;margin-top:4px">' +
        escHtml(on ? "This browser is receiving desk alerts." :
          "A notification when something on your watchlist moves. This browser only.") + "</span>";
      var btn = host.querySelector("#pushToggle");
      var msg = host.querySelector("#pushMsg");
      btn.onclick = function () {
        btn.disabled = true;
        if (msg) msg.textContent = on ? "Turning off…" : "Asking your browser…";
        (on ? unsubscribe() : subscribe()).then(function (r) {
          btn.disabled = false;
          if (r.ok) return renderToggle(host);
          if (msg) {
            msg.textContent =
              r.error === "not_signed_in" ? "Sign in first — alerts are tied to your account." :
              r.error === "denied" ? "Your browser blocked notifications for this site." :
              r.error === "dismissed" ? "No change — the permission prompt was dismissed." :
              "Couldn't change that — try again.";
          }
        });
      };
      return true;
    });
  }

  window.PSXPush = {
    /* configure({ vapidPublicKey, sb, userId }) — call on sign-in/sign-out. Passing a null
       or absent vapidPublicKey keeps the whole feature off, which is today's state. */
    configure: function (o) {
      o = o || {};
      if ("vapidPublicKey" in o) cfg.vapidPublicKey = o.vapidPublicKey || null;
      if ("sb" in o) cfg.sb = o.sb || null;
      if ("userId" in o) cfg.userId = o.userId || null;
      return available();
    },
    available: available,
    status: status,
    subscribe: subscribe,
    unsubscribe: unsubscribe,
    renderToggle: renderToggle,
  };
})();
