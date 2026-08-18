/* ============================================================
   Topbar open-tabs strip + "+" quick-open menu
   + Board-tile collapse chevron.
   Additive only. Loaded after app.js and rail.js. Never
   edits app.js/route() internals — watches #view / clean location paths
   the same way rail.js does, with its own localStorage
   keys (openTabs, boardCardCollapsed:<id>) kept separate from the
   rail's railTab/railNotes. Production script, linked from
   dashboard/index.html after app.js and rail.js.
   ============================================================ */
(function () {
  "use strict";

  var shell = document.getElementById("shell");
  if (!shell) return;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function currentPageName() {
    var h = (window.appPathname ? window.appPathname() : location.pathname || "/today").replace(/^\/+/, "");
    return h.split("/")[0] || "today";
  }
  function currentTicker() {
    var path = window.appPathname ? window.appPathname() : location.pathname;
    var m = /^\/ticker\/([A-Za-z0-9.]+)/.exec(path || "");
    return m ? m[1].toUpperCase() : null;
  }
  function labelFor(page, sym, path) {
    if (page === "ticker" && sym) return sym;
    var navEl = document.querySelector('[data-nav="' + page + '"]');
    if (navEl && navEl.getAttribute("title")) return navEl.getAttribute("title");
    return path.replace(/^\/+/, "") || "Today";
  }

  // ============================================================
  // Open-tabs strip — MRU-ish "currently open" list. The rail used to
  // keep a parallel "everything visited" log; it no longer does, so this
  // strip is the only record of where you have been, capped at TAB_CAP.
  // ============================================================
  var TAB_KEY = "openTabs", TAB_CAP = 8;
  function cleanPath(path) {
    path = String(path || "");
    if (path.indexOf("#/") === 0) path = path.slice(1);
    if (path === "/" || !path) return "/today";
    return path.charAt(0) === "/" ? path : "/" + path;
  }
  function readTabs() {
    try {
      var raw = JSON.parse(localStorage.getItem(TAB_KEY) || "[]");
      return Array.isArray(raw) ? raw.filter(function (t) { return t && t.href; }).map(function (t) {
        return { href: cleanPath(t.href), label: t.label || cleanPath(t.href).replace(/^\//, "") };
      }) : [];
    } catch (e) { return []; }
  }
  function writeTabs(arr) {
    localStorage.setItem(TAB_KEY, JSON.stringify(arr.slice(0, TAB_CAP)));
  }
  function ensureTab() {
    var path = cleanPath((window.appPathname ? window.appPathname() : location.pathname) + location.search);
    var tabs = readTabs();
    if (!tabs.some(function (t) { return t.href === path; })) {
      tabs.push({ href: path, label: labelFor(currentPageName(), currentTicker(), path) });
      if (tabs.length > TAB_CAP) tabs.shift();
      writeTabs(tabs);
    }
  }

  var stripEl = document.getElementById("tabStrip");

  // .on is purely visual, so a screen reader had no way to tell which tab is the
  // current page — aria-current="page" carries that to the a11y tree. the close
  // buttons all announced the same "Close tab" string too, which is eight
  // indistinguishable controls in a rotor; name each one by its tab label.
  function buildTab(t) {
    var el = document.createElement("span");
    el.className = "tstrip-tab";
    el.setAttribute("data-href", t.href);
    var a = document.createElement("a");
    a.setAttribute("href", t.href);
    a.textContent = t.label;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tstrip-close";
    btn.setAttribute("data-href", t.href);
    btn.setAttribute("aria-label", "Close " + t.label);
    btn.textContent = "✕";
    el.appendChild(a);
    el.appendChild(btn);
    return el;
  }

  // Reconcile, never reassign innerHTML: a wholesale rebuild re-inserts every tab
  // node on every navigation, so .tstrip-tab's entry animation replayed across the
  // whole strip each time the reader merely navigated. Reusing the existing node
  // for an href that is still open means only a genuinely NEW tab animates in.
  function renderTabs() {
    if (!stripEl) return;
    var path = cleanPath((window.appPathname ? window.appPathname() : location.pathname) + location.search);
    var tabs = readTabs();
    var existing = {};
    Array.prototype.forEach.call(stripEl.children, function (el) {
      existing[el.getAttribute("data-href")] = el;
    });

    tabs.forEach(function (t, i) {
      var el = existing[t.href];
      if (el) {
        delete existing[t.href];
        var a = el.querySelector("a");
        if (a && a.textContent !== t.label) a.textContent = t.label;
      } else {
        el = buildTab(t);
      }
      var isOn = t.href === path;
      el.classList.toggle("on", isOn);
      var link = el.querySelector("a");
      if (link) {
        if (isOn) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      }
      // move-in-place: appendChild of an already-attached node relocates it without
      // a remove/insert pair, so no animation restart for a tab that only reordered.
      if (stripEl.children[i] !== el) stripEl.insertBefore(el, stripEl.children[i] || null);
    });

    Object.keys(existing).forEach(function (href) { existing[href].remove(); });
  }
  if (stripEl) {
    stripEl.addEventListener("click", function (ev) {
      var close = ev.target.closest(".tstrip-close");
      if (!close) return;
      ev.preventDefault();
      var href = close.getAttribute("data-href");
      var tabs = readTabs();
      var idx = tabs.findIndex(function (t) { return t.href === href; });
      if (idx === -1) return;
      tabs.splice(idx, 1);
      writeTabs(tabs);
      if (cleanPath((window.appPathname ? window.appPathname() : location.pathname) + location.search) === href) {
        var next = tabs[idx] || tabs[idx - 1];
        navigate(next ? next.href : "/today");
      }
      renderTabs();
    });
  }

  function refreshTabStrip() {
    ensureTab();
    renderTabs();
  }
  function refreshOnNavigation() { setTimeout(refreshTabStrip, 0); }
  window.addEventListener("henneth:navigate", refreshOnNavigation);
  window.addEventListener("popstate", refreshOnNavigation);
  setTimeout(refreshTabStrip, 50);

  // ============================================================
  // "+" quick-open launcher — a blurred-scrim popup carrying the
  // .searchbox idiom (themes.css:1640-1642), NOT the .acct-menu
  // popover. #tabAddMenu IS the full-viewport scrim, so "outside"
  // is tested against .tabadd-panel, not against the menu root.
  // Escape/navigation guard still follows app.js's route teardown.
  // ============================================================
  var addBtn = document.getElementById("tabAddBtn");
  var addMenu = document.getElementById("tabAddMenu");
  var searchBtn = document.getElementById("searchbtn");

  function closeAddMenu() {
    if (!addMenu) return;
    var hadFocusInside = addBtn && addMenu.contains(document.activeElement);
    addMenu.hidden = true;
    if (addBtn) {
      addBtn.setAttribute("aria-expanded", "false");
      if (hadFocusInside) addBtn.focus();
    }
  }
  function openAddMenu() {
    if (!addMenu) return;
    addMenu.hidden = false;
    if (addBtn) addBtn.setAttribute("aria-expanded", "true");
  }
  if (addBtn && addMenu) {
    addBtn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (addMenu.hidden) openAddMenu(); else closeAddMenu();
    });
    addMenu.addEventListener("click", function (ev) {
      var searchItem = ev.target.closest("#tabAddSearch");
      if (searchItem) {
        ev.preventDefault();
        closeAddMenu();
        if (searchBtn) searchBtn.click();
        return;
      }
      if (ev.target.closest("a")) closeAddMenu();
    });
    if (!window.__tabAddMenuGuard) {
      window.__tabAddMenuGuard = true;
      document.addEventListener("click", function (ev) {
        var panel = addMenu.querySelector(".tabadd-panel");
        if (!addMenu.hidden && !(panel && panel.contains(ev.target)) && ev.target !== addBtn && !addBtn.contains(ev.target)) {
          closeAddMenu();
        }
      }, true);
      document.addEventListener("keydown", function (ev) {
        if (ev.key === "Escape") closeAddMenu();
      });
      window.addEventListener("henneth:navigate", closeAddMenu);
      window.addEventListener("popstate", closeAddMenu);
    }
  }

  // ============================================================
  // Board-tile collapse chevron — every .tile on the Board page,
  // as painted by board.js. The header row is .tile-head
  // and the stable name is .tile-title inside it (.tile-meta holds
  // per-cycle counts, so keying off the whole head text would give
  // a new localStorage key every time the data changes). Persists
  // per key boardCardCollapsed:<slug-of-tile-title>.
  // ============================================================
  function slugifyTile(s) {
    return (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "tile";
  }
  function wireBoardCollapse() {
    var view = document.getElementById("view");
    if (!view) return;
    var cards = view.querySelectorAll(".tile");
    cards.forEach(function (card) {
      var h2 = card.querySelector(":scope > .tile-head");
      if (!h2) return;
      if (h2.querySelector(".tile-collapse")) return; // already wired this render
      var title = h2.querySelector(".tile-title");
      var key = "boardCardCollapsed:" + slugifyTile(title ? title.textContent : h2.textContent);
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tile-collapse";
      btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>';
      var collapsed = localStorage.getItem(key) === "1";
      function apply(v) {
        card.classList.toggle("tile-collapsed", v);
        btn.setAttribute("aria-expanded", String(!v));
        btn.title = v ? "Expand section" : "Collapse section";
      }
      apply(collapsed);
      btn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        collapsed = !collapsed;
        localStorage.setItem(key, collapsed ? "1" : "0");
        apply(collapsed);
      });
      card.classList.add("tile-has-collapse");
      h2.appendChild(btn);
    });
  }

  // board.js paints .tile several levels down inside .board-view, so a
  // childList-only observer on #view never fires for them.
  var view = document.getElementById("view");
  if (view) {
    var moPending = false;
    var mo = new MutationObserver(function () {
      if (moPending) return;
      moPending = true;
      requestAnimationFrame(function () { moPending = false; wireBoardCollapse(); });
    });
    mo.observe(view, { childList: true, subtree: true });
  }
  function wireCollapseOnNavigation() { setTimeout(wireBoardCollapse, 60); }
  window.addEventListener("henneth:navigate", wireCollapseOnNavigation);
  window.addEventListener("popstate", wireCollapseOnNavigation);
  setTimeout(wireBoardCollapse, 60);

  // ============================================================
  // Statusbar — mirrors the real #mkt/#health/#updated pills, no
  // invented data. Pills are (re)written by app.js asynchronously
  // as state loads, so this polls rather than hooking one event.
  // ============================================================
  var mktEl = document.getElementById("mkt");
  var healthEl = document.getElementById("health");
  var updatedEl = document.getElementById("updated");
  var sbMkt = document.getElementById("sbMkt");
  var sbAsof = document.getElementById("sbAsof");
  var sbHealth = document.getElementById("sbHealth");
  var sbDot = document.getElementById("sbDot");
  function refreshStatusbar() {
    if (!sbMkt) return;
    // app.js:313 writes #mkt as "PSX " + mt, because that pill stands alone in the
    // topbar. Here the strip already says MARKET STATE, so repeating "PSX" reads as
    // a stutter — take the tuple straight from app.js:178 marketStatus() (top-level
    // in the same classic script) instead of string-surgering its pill text.
    // Write only when the value actually changed. This poll runs every 1.5s, and app.js's
    // enhancement MutationObserver watches document.body (not #view), so the statusbar is
    // inside its subtree: an unconditional textContent write mutates the DOM every tick and
    // re-triggers a full-document flush() — which is what read as the desk "blinking".
    // Same before/after guard app.js's setText/setClass helpers already use.
    try {
      var st = marketStatus();
      var mkt = String(st[0] || "—").toUpperCase();
      if (sbMkt.textContent !== mkt) sbMkt.textContent = mkt;
      sbMkt.className = st[1] ? "status-positive" : "status-muted";
    } catch (e) { /* app.js not parsed yet — the next poll picks it up */ }
    // #updated carries BOTH stamps ("quant <t> · live <t>"). The strip has room for
    // one; live is the fresher of the two and is what "as of" means to a reader.
    if (updatedEl) {
      var stamps = (updatedEl.textContent || "").split("·");
      var live = (stamps[stamps.length - 1] || "").replace(/^\s*(quant|live)\s*/, "").trim();
      var asof = "AS OF " + (live || "—");
      if (sbAsof.textContent !== asof) sbAsof.textContent = asof;
    }
    if (healthEl) {
      var hv = healthEl.textContent || "DATA —";
      if (sbHealth.textContent !== hv) sbHealth.textContent = hv;
      var ok = healthEl.classList.contains("ok");
      sbDot.classList.toggle("bad", !ok);
    }
  }
  setInterval(refreshStatusbar, 1500);
  setTimeout(refreshStatusbar, 80);
})();
