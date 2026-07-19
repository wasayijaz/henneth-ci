/* PSX Trade Desk — service worker (Web Push only).
   INERT BY DESIGN: nothing registers this file today. It is installed only when
   push.js is explicitly enabled AND a VAPID public key exists (see docs/OPERATIONS.md §11).

   Deliberately minimal: no fetch handler, no caching, no offline shell. The desk serves a
   static site whose freshness is the whole point (Cache-Control: must-revalidate) — a caching
   SW would be a way to show users stale prices, so this worker never intercepts fetch. */

/* Take over promptly so a stale worker can't linger with old click behaviour. */
self.addEventListener("install", (e) => e.waitUntil(self.skipWaiting()));
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

/* Payload shape the sender (scripts/push_send.py) writes:
   { title, body, symbol, url, tag }  — every field optional, all defended below. */
function parsePayload(event) {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch (e) {
    try { d = { body: event.data.text() }; } catch (e2) { d = {}; }
  }
  const sym = typeof d.symbol === "string" ? d.symbol.trim().toUpperCase() : "";
  // Only ever navigate to our own hash routes — never to a URL taken verbatim from the payload.
  const safeSym = /^[A-Z0-9.&-]{1,20}$/.test(sym) ? sym : "";
  return {
    title: String(d.title || "PSX Trade Desk").slice(0, 120),
    body: String(d.body || "").slice(0, 400),
    tag: String(d.tag || (safeSym ? "watch:" + safeSym : "desk")).slice(0, 60),
    route: safeSym ? "#/ticker/" + safeSym : "#/watchlist",
  };
}

self.addEventListener("push", (event) => {
  const d = parsePayload(event);
  event.waitUntil(self.registration.showNotification(d.title, {
    body: d.body,
    tag: d.tag,
    renotify: false,
    data: { route: d.route },
    icon: "/icon-192.png",
    badge: "/icon-192.png",
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const route = (event.notification.data && event.notification.data.route) || "#/watchlist";
  const target = new URL("/" + route, self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      // Reuse an already-open desk tab rather than piling up windows.
      for (const w of wins) {
        if (w.url.indexOf(self.location.origin) === 0 && "focus" in w) {
          if ("navigate" in w) { try { w.navigate(target); } catch (e) { /* cross-doc nav blocked */ } }
          return w.focus();
        }
      }
      return self.clients.openWindow ? self.clients.openWindow(target) : undefined;
    })
  );
});
