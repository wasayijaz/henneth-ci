// Opens the side panel when the toolbar icon is clicked.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((e) => console.error("side panel behavior", e));

// Remembers the latest detected ticker for panels that open later.
let lastTicker = null;
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "TICKER_FOUND") {
    lastTicker = msg.ticker;
    sendResponse({ ok: true });
  } else if (msg && msg.type === "GET_LAST_TICKER") {
    sendResponse({ ticker: lastTicker });
  } else if (msg && msg.type === "TOKEN") {
    // From auth.js on desk.henneth.app - persist the session token.
    chrome.storage.local.set({ desk_token: msg.token, desk_token_at: Date.now() });
    sendResponse({ ok: true });
  }
  return false;
});
