// Runs on desk.henneth.app only. Reads the dashboard's Supabase session token
// without hard-coding the project's storage key or URL, then hands it to the
// extension so panel fetches carry the same Authorization header. The token
// never leaves chrome.storage.local.
(function () {
  function send() {
    let token = null;
    for (let i = 0; i < localStorage.length && !token; i++) {
      const key = localStorage.key(i) || "";
      if (!/^sb-[a-z0-9]+-auth-token$/.test(key)) continue;
      try {
        const parsed = JSON.parse(localStorage.getItem(key) || "null");
        token = (parsed && (parsed.access_token || (parsed.session && parsed.session.access_token))) || null;
      } catch (_) {}
    }
    if (token) chrome.runtime.sendMessage({ type: "TOKEN", token: token });
  }
  send();
  // Re-send on changes (login, refresh) so the extension never rides a stale token.
  window.addEventListener("storage", send);
  setInterval(send, 15 * 60 * 1000);
})();
