// Detects the PSX ticker on TradingView, DPS, and PSX business-news pages,
// then notifies the extension. URL/title-first where the page structure is
// known; news sites get a text scan of headings and body against the cached
// desk universe, picking the most-mentioned known symbol.
(function () {
  const UNIVERSE_CACHE_KEY = "henneth_universe";
  const NEWS_HOSTS = ["dawn.com", "profit.pk", "brecorder.com", "tribune.com.pk", "mettisglobal.com", "thenews.com.pk"];

  function report(ticker) {
    if (!ticker) return;
    chrome.runtime.sendMessage({ type: "TICKER_FOUND", ticker: ticker.toUpperCase() });
  }

  function fromTradingView(universe) {
    // The chart legend is the primary signal: TradingView swaps symbols without
    // changing the URL or document title, so read the legend DOM directly.
    const legend = fromTradingViewLegend(universe);
    if (legend) return legend;
    const url = location.href;
    let m = url.match(/[?&]symbol=(?:PSX%3A|PSX:)([A-Za-z0-9]+)/i);
    if (m) return m[1];
    m = url.match(/\/symbols\/psx-([a-z0-9]+)\/?/i);
    if (m) return m[1];
    // Titles: "LUCK Chart — TradingView" or "LUCK Chart — PSX — TradingView".
    // Validated against the cached universe by the caller so a false grab is harmless.
    m = document.title.match(/\b([A-Z]{2,6}(?:\.[A-Z]{1,2})?)\b\s*Chart\b/);
    if (m) return m[1];
    m = document.title.match(/\b([A-Z]{2,6})\b[^—–-]*PSX/);
    if (m) return m[1];
    // Some layouts begin with the ticker but never include the word PSX.
    m = document.title.match(/^\s*([A-Z]{2,6}(?:\.[A-Z]{1,2})?)\b/);
    if (m) return m[1];
    return null;
  }

  function fromTradingViewLegend(universe) {
    // Selectors drift across TradingView builds, so scan a small candidate set
    // (the legend row and its symbol/title spans) for "PSX:SYM" or a bare
    // leading symbol. The caller validates any bare grab against the universe.
    const titleButton = document.querySelector(
      '[data-qa-id*="legend-source-title"] button[aria-label="Change symbol"], ' +
      '[data-qa-id*="legend-source-title"] [aria-label="Change symbol"]'
    );
    if (titleButton && universe) {
      const title = (titleButton.textContent || "").trim();
      const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "");
      const wanted = norm(title);
      for (const sym of Object.keys(universe)) {
        const meta = universe[sym];
        const name = meta && typeof meta === "object" ? meta.name : "";
        if (wanted && name && norm(name) === wanted) return sym;
      }
    }
    const candidates = document.querySelectorAll(
      '[data-symbol], [class*="legend"] [class*="symbol"], .chart-symbol, ' +
      '[data-qa-id*="legend-source-title"]'
    );
    for (const n of candidates) {
      const attr = n.getAttribute && n.getAttribute("data-symbol");
      if (attr) {
        const m = attr.match(/(?:PSX:)?([A-Za-z0-9._-]+)/);
        if (m) return m[1];
      }
      const text = (n.textContent || "").trim();
      if (!text || text.length > 60) continue;
      let m = text.match(/\bPSX:([A-Za-z0-9._-]+)/);
      if (m) return m[1];
      if (attr === null && n.className && String(n.className).indexOf("legend") !== -1) continue;
      m = text.match(/^([A-Z]{2,6}(?:\.[A-Z]{1,2})?)\b/);
      if (m) return m[1];
    }
    return null;
  }

  function fromDps() {
    const m = location.href.match(/[?&](?:symbol|s)=([A-Za-z0-9_.]+)/);
    return m ? m[1] : null;
  }

  // News pages: find the most-mentioned known ticker. Headings count double
  // (a headline about LUCK is about LUCK; a body mention may be incidental).
  function fromNews(universe) {
    if (!universe) return null;
    const counts = Object.create(null);
    const bump = (sym, w) => { counts[sym] = (counts[sym] || 0) + w; };
    const scan = (text, weight) => {
      if (!text) return;
      const re = /\b([A-Z]{2,6}(?:\.[A-Z]{1,2})?)\b/g;
      let m;
      while ((m = re.exec(text)) !== null) {
        const sym = m[1];
        if (Object.prototype.hasOwnProperty.call(universe, sym)) bump(sym, weight);
      }
    };
    scan(document.title, 4);
    document.querySelectorAll("h1, h2, h3").forEach((h) => scan(h.textContent, 2));
    const paras = document.querySelectorAll("p");
    const limit = Math.min(paras.length, 40);
    for (let i = 0; i < limit; i++) scan(paras[i].textContent, 1);
    let best = null, bestN = 0;
    for (const sym in counts) {
      if (counts[sym] > bestN) { best = sym; bestN = counts[sym]; }
    }
    return bestN >= 2 ? best : null;
  }

  function cachedUniverse(stored) {
    return stored && Date.now() - (stored.at || 0) < 86400000 ? stored.data : null;
  }

  function detectAndReport() {
    chrome.storage.local.get([UNIVERSE_CACHE_KEY], ({ henneth_universe }) => {
      const universe = cachedUniverse(henneth_universe);
      const host = location.hostname;
      let sym = null;
      if (host.includes("tradingview.com")) sym = fromTradingView(universe);
      else if (host.includes("dps.psx.com.pk")) sym = fromDps();
      else if (NEWS_HOSTS.some((h) => host.endsWith(h))) sym = fromNews(universe);
      sym = sym ? sym.toUpperCase() : null;
      const known = !universe || (sym && Object.prototype.hasOwnProperty.call(universe, sym));
      if (sym && known) report(sym);
    });
  }

  detectAndReport();
  let lastReported = null;
  const origReport = report;
  report = function (t) {
    if (t && t !== lastReported) { lastReported = t; origReport(t); }
  };

  // Re-check when the page changes URL without a navigation (SPAs, infinite scroll).
  let lastUrl = location.href;
  let lastTitle = document.title;
  const isTradingView = location.hostname.includes("tradingview.com");
  setInterval(() => {
    // On TradingView the legend can swap symbols while the URL and title stay
    // put, so always poll there; elsewhere only react to URL/title changes.
    if (isTradingView || location.href !== lastUrl || document.title !== lastTitle) {
      lastUrl = location.href;
      lastTitle = document.title;
      detectAndReport();
    }
  }, 1500);
})();
