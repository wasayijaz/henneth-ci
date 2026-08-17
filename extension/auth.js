// Runs on desk.henneth.app only. Reads the Supabase session token from the
// dashboard's own localStorage key and hands it to the extension so panel
// fetches to /state/*.json carry the same Authorization header the dashboard
// sends. The token never leaves chrome.storage.local.
(function () {
  const SB_KEY = "sb-qteoncckohuoatbjjykb-auth-token";
  function send() {
    let token = null;
    try {
      const raw = localStorage.getItem(SB_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      token = (parsed && (parsed.access_token || (parsed.session && parsed.session.access_token))) || null;
    } catch (_) {
      token = null;
    }
    if (token) chrome.runtime.sendMessage({ type: "TOKEN", token: token });
  }
  send();
  // Re-send on changes (login, refresh) so the extension never rides a stale token.
  window.addEventListener("storage", send);
  setInterval(send, 15 * 60 * 1000);
})();
