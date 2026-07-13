/* PSX Trade Desk — accounts + onboarding (Supabase Auth).
   Security model: the publishable key below is CLIENT-SAFE by design — all authority
   lives server-side in Row-Level Security (a user can only touch their own profiles row).
   Passwords are never handled by our code; Supabase Auth does hashing/JWT/rate limits.
   The shared research data stays public; only the per-user layer needs an account. */

const SB_URL = "https://qteoncckohuoatbjjykb.supabase.co";
const SB_KEY = "sb_publishable_aQu8P4yrAY7l8Y0AcLth5g_Z3VceUnw";
const sb = window.supabase ? window.supabase.createClient(SB_URL, SB_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
}) : null;

let me = null;        // auth user
let myProfile = null; // profiles row

/* ---------- tiny helpers ---------- */
const el = (h) => { const d = document.createElement("div"); d.innerHTML = h.trim(); return d.firstChild; };
const authMsg = (t, bad) => { const m = document.getElementById("authmsg"); if (m) { m.textContent = t || ""; m.className = "authmsg" + (bad ? " bad" : ""); } };

/* ---------- account button in the topbar ---------- */
function renderAccountButton() {
  const holder = document.getElementById("acctSlot");
  if (!holder) return;
  if (me) {
    const initial = (me.email || "?")[0].toUpperCase();
    holder.innerHTML = `<button class="acct-btn" id="acctBtn" title="${me.email}">${initial}</button>
      <div class="acct-menu" id="acctMenu" hidden>
        <div class="acct-email">${me.email}</div>
        <button id="acctTour">Replay the tour</button>
        <button id="acctOut">Sign out</button>
      </div>`;
    document.getElementById("acctBtn").onclick = () => { const m = document.getElementById("acctMenu"); m.hidden = !m.hidden; };
    document.getElementById("acctOut").onclick = async () => { await sb.auth.signOut(); location.reload(); };
    document.getElementById("acctTour").onclick = () => { document.getElementById("acctMenu").hidden = true; startWizard(true); };
    document.addEventListener("click", (e) => { const m = document.getElementById("acctMenu"); if (m && !holder.contains(e.target)) m.hidden = true; });
  } else {
    holder.innerHTML = `<button class="acct-signin" id="acctIn">Sign in</button>`;
    document.getElementById("acctIn").onclick = () => openAuth("signin");
  }
}

/* ---------- auth modal (sign in / create account / reset) ---------- */
function openAuth(mode) {
  closeAuth();
  const box = el(`<div class="authbox" id="authbox">
    <div class="authpanel">
      <div class="auth-head"><b>PSX <em>Trade Desk</em></b><button class="auth-x" id="authX">✕</button></div>
      <div class="auth-tabs">
        <button data-m="signin" class="${mode === "signin" ? "on" : ""}">Sign in</button>
        <button data-m="signup" class="${mode === "signup" ? "on" : ""}">Create account</button>
      </div>
      <form id="authform" autocomplete="on">
        <label>Email<input type="email" id="authEmail" required autocomplete="email" placeholder="you@example.com"></label>
        <label id="pwRow">Password<input type="password" id="authPw" minlength="8" required autocomplete="${mode === "signup" ? "new-password" : "current-password"}" placeholder="min 8 characters"></label>
        <button type="submit" class="auth-go" id="authGo">${mode === "signup" ? "Create account" : "Sign in"}</button>
      </form>
      <div class="authmsg" id="authmsg"></div>
      <div class="auth-foot">
        ${mode === "signin" ? '<a id="authForgot">Forgot password?</a>' : '<span class="sub">Free account — saves your watchlist and preferences.</span>'}
      </div>
      <div class="auth-legal">Research &amp; analytics tool, not an investment adviser. By continuing you accept that nothing here is personalized advice.</div>
    </div></div>`);
  document.body.appendChild(box);
  box.addEventListener("click", (e) => { if (e.target.id === "authbox") closeAuth(); });
  document.getElementById("authX").onclick = closeAuth;
  box.querySelectorAll(".auth-tabs button").forEach(b => b.onclick = () => openAuth(b.dataset.m));

  const forgot = document.getElementById("authForgot");
  if (forgot) forgot.onclick = async () => {
    const email = document.getElementById("authEmail").value.trim();
    if (!email) return authMsg("Enter your email above first, then click reset.", true);
    authMsg("Sending reset link…");
    const { error } = await sb.auth.resetPasswordForEmail(email, { redirectTo: location.origin + location.pathname });
    authMsg(error ? error.message : "Reset link sent — check your email.", !!error);
  };

  document.getElementById("authform").onsubmit = async (e) => {
    e.preventDefault();
    const email = document.getElementById("authEmail").value.trim();
    const pw = document.getElementById("authPw").value;
    const go = document.getElementById("authGo");
    go.disabled = true; authMsg(mode === "signup" ? "Creating your account…" : "Signing in…");
    try {
      if (mode === "signup") {
        const { data, error } = await sb.auth.signUp({ email, password: pw });
        if (error) throw error;
        if (!data.session) { authMsg("Almost there — we sent a confirmation link to your email. Click it to activate your account."); return; }
      } else {
        const { error } = await sb.auth.signInWithPassword({ email, password: pw });
        if (error) throw error;
      }
      closeAuth();
    } catch (err) {
      authMsg(err.message || String(err), true);
    } finally { go.disabled = false; }
  };
}
function closeAuth() { document.getElementById("authbox")?.remove(); }

/* ---------- password recovery (arrives via email link) ---------- */
function openRecovery() {
  closeAuth();
  const box = el(`<div class="authbox" id="authbox"><div class="authpanel">
    <div class="auth-head"><b>Set a new password</b></div>
    <form id="recform"><label>New password<input type="password" id="recPw" minlength="8" required autocomplete="new-password"></label>
    <button type="submit" class="auth-go">Save password</button></form>
    <div class="authmsg" id="authmsg"></div></div></div>`);
  document.body.appendChild(box);
  document.getElementById("recform").onsubmit = async (e) => {
    e.preventDefault();
    const { error } = await sb.auth.updateUser({ password: document.getElementById("recPw").value });
    authMsg(error ? error.message : "Password updated — you're signed in.", !!error);
    if (!error) setTimeout(closeAuth, 1200);
  };
}

/* ---------- profile ---------- */
async function loadProfile() {
  if (!me) return null;
  const { data } = await sb.from("profiles").select("*").eq("id", me.id).maybeSingle();
  myProfile = data;
  return data;
}
async function saveProfile(patch) {
  if (!me) return;
  patch.id = me.id;
  const { error } = await sb.from("profiles").upsert(patch);
  if (!error) myProfile = { ...(myProfile || {}), ...patch };
  return error;
}

/* ---------- onboarding wizard: quiz + product tour ---------- */
const WIZ = [
  { kind: "welcome", title: "Welcome to the desk", body: "PSX Trade Desk is a research terminal that makes Pakistani stocks understandable — plain-English company reads, tested strategies, fair-value models, and AI analysts who debate every name in the open. Two minutes, and you'll know your way around. Nothing here is investment advice — you always decide." },
  { kind: "quiz", key: "experience", title: "How much investing experience do you have?", opts: [["new", "I'm new to this"], ["some", "I've bought a few stocks"], ["experienced", "I trade regularly"]] },
  { kind: "quiz", key: "goal", title: "What are you mostly here for?", opts: [["income", "Dividend income"], ["growth", "Long-term growth"], ["swing", "Active swing ideas"], ["learning", "Learning the market"]] },
  { kind: "quiz", key: "risk", title: "A stock you hold drops 20% in a month. You…", opts: [["conservative", "Lose sleep — I prefer stability"], ["moderate", "Feel it, but hold if the story's intact"], ["aggressive", "See it as a chance to buy more"]] },
  { kind: "quiz", key: "sectors", multi: true, title: "Which sectors interest you? (pick any)", opts: [["banks", "Banks"], ["fertilizer", "Fertilizer"], ["e_and_p", "Oil & Gas"], ["cement", "Cement"], ["power", "Power"], ["tech", "Technology"], ["autos", "Autos"]] },
  { kind: "tour", route: "#/today", title: "Today — your morning read", body: "Every trading day the desk writes a plain-English note: the mood, which sectors look favoured, and a short watchlist with reasons. Start your day here." },
  { kind: "tour", route: "#/board", title: "Board — the whole market at a glance", body: "The live pulse: every stock's day move, signals that fired from tested strategies, and the news wire. Green is up, red is down — click any name to go deep." },
  { kind: "tour", route: "#/ticker/FFC", title: "Stock pages — 'At a glance' first", body: "Every stock opens with the questions that matter: is the company healthy, is the price reasonable, which way is it moving, does it pay income — then the AI analysts' debate, risk profile, and what the brokers say. All sourced, never advice." },
  { kind: "tour", route: "#/value", title: "Value — is the price fair?", body: "Every stock valued four independent ways. Click a row to see the full working — no black boxes. Remember: below model fair value is a screen, not a recommendation." },
  { kind: "tour", route: "#/leaderboard", title: "Scores — everyone's on the record", body: "Every dated call — the desk's own AI analysts AND the brokerage houses — is timestamped and graded against what actually happened. Losses included. Nobody else grades PSX brokers." },
  { kind: "done", title: "You're set", body: "Explore freely — the search (top right, or press /) jumps to any stock. Everything updates automatically through the trading day. Research, not advice: the decisions are always yours." },
];

let wizIdx = 0, wizAnswers = {};
function startWizard(replayOnly) {
  wizIdx = replayOnly ? WIZ.findIndex(s => s.kind === "tour") : 0;
  wizAnswers = (myProfile && myProfile.quiz) || {};
  renderWizard(!!replayOnly);
}
function renderWizard(replayOnly) {
  document.getElementById("wizbox")?.remove();
  const s = WIZ[wizIdx];
  if (!s) return finishWizard(replayOnly);
  if (s.kind === "tour" && s.route) location.hash = s.route;

  const qSteps = WIZ.filter(x => x.kind === "quiz").length;
  const prog = Math.round(((wizIdx + 1) / WIZ.length) * 100);
  let inner = "";
  if (s.kind === "quiz") {
    const cur = wizAnswers[s.key];
    inner = `<div class="wiz-opts">${s.opts.map(([v, label]) => {
      const on = s.multi ? (cur || []).includes(v) : cur === v;
      return `<button class="wiz-opt ${on ? "on" : ""}" data-v="${v}">${label}</button>`;
    }).join("")}</div>`;
  }
  const isTour = s.kind === "tour" || s.kind === "done" || s.kind === "welcome";
  const box = el(`<div class="wizbox ${s.kind === "quiz" || s.kind === "welcome" ? "center" : "corner"}" id="wizbox">
    <div class="wizcard">
      <div class="wiz-prog"><span style="width:${prog}%"></span></div>
      <b class="wiz-title">${s.title}</b>
      ${s.body ? `<p class="wiz-body">${s.body}</p>` : ""}
      ${inner}
      <div class="wiz-nav">
        ${wizIdx > 0 ? '<button class="wiz-back" id="wizBack">Back</button>' : ""}
        <button class="wiz-skip" id="wizSkip">Skip tour</button>
        <button class="wiz-next" id="wizNext">${s.kind === "done" ? "Start exploring" : "Next"}</button>
      </div>
    </div></div>`);
  document.body.appendChild(box);

  box.querySelectorAll(".wiz-opt").forEach(b => b.onclick = () => {
    const v = b.dataset.v;
    if (s.multi) {
      const cur = new Set(wizAnswers[s.key] || []);
      cur.has(v) ? cur.delete(v) : cur.add(v);
      wizAnswers[s.key] = [...cur];
      b.classList.toggle("on");
    } else {
      wizAnswers[s.key] = v;
      box.querySelectorAll(".wiz-opt").forEach(x => x.classList.toggle("on", x === b));
      setTimeout(() => { wizIdx++; renderWizard(replayOnly); }, 180); // auto-advance feels snappy
    }
  });
  const back = document.getElementById("wizBack");
  if (back) back.onclick = () => { wizIdx--; renderWizard(replayOnly); };
  document.getElementById("wizNext").onclick = () => { wizIdx++; renderWizard(replayOnly); };
  document.getElementById("wizSkip").onclick = () => finishWizard(replayOnly);
}
async function finishWizard(replayOnly) {
  document.getElementById("wizbox")?.remove();
  if (!replayOnly && me) await saveProfile({ onboarded: true, quiz: wizAnswers });
  location.hash = "#/today";
}

/* ---------- boot ---------- */
async function initAuth() {
  if (!sb) return; // CDN blocked — the shared research still works, accounts just hidden
  const { data: { session } } = await sb.auth.getSession();
  me = session?.user || null;
  renderAccountButton();
  if (me) {
    await loadProfile();
    if (myProfile && !myProfile.onboarded) startWizard(false);
  }
  sb.auth.onAuthStateChange(async (event, sess) => {
    me = sess?.user || null;
    renderAccountButton();
    if (event === "PASSWORD_RECOVERY") return openRecovery();
    if (event === "SIGNED_IN") {
      closeAuth();
      await loadProfile();
      if (myProfile && !myProfile.onboarded) startWizard(false);
    }
  });
}
initAuth();
