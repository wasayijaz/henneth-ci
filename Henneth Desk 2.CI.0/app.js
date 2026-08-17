const SB_URL = "https://qteoncckohuoatbjjykb.supabase.co";
const SB_KEY = "sb_publishable_aQu8P4yrAY7l8Y0AcLth5g_Z3VceUnw";
const SESSION_KEY = "henneth-ci-session";

const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
const fmt = (value, digits = 2) => value == null ? "unknown" : Number(value).toLocaleString("en", { maximumFractionDigits: digits });
const pct = value => value == null ? "unknown" : `${value > 0 ? "+" : ""}${fmt(value, 1)}%`;

let state = { session: null, data: null, selected: null, filter: "" };

const SCHEME_CYCLE = { system: "light", light: "dark", dark: "system" };

function deskScheme() {
  try {
    const value = localStorage.getItem("deskScheme");
    return value === "light" || value === "dark" ? value : "system";
  } catch { return "system"; }
}

function applyDeskScheme(choice) {
  document.documentElement.setAttribute("data-scheme-switching", "");
  if (choice === "light" || choice === "dark") {
    document.documentElement.setAttribute("data-scheme", choice);
    try { localStorage.setItem("deskScheme", choice); } catch {}
  } else {
    document.documentElement.removeAttribute("data-scheme");
    try { localStorage.removeItem("deskScheme"); } catch {}
  }
  const button = $("schemeToggle");
  if (button) {
    button.textContent = `Scheme: ${choice}`;
    button.setAttribute("aria-label", `Colour scheme: ${choice}. Activate to change.`);
  }
  const clearSwitch = () => document.documentElement.removeAttribute("data-scheme-switching");
  requestAnimationFrame(() => requestAnimationFrame(clearSwitch));
  setTimeout(clearSwitch, 150);
}

function setAccessState(label, fileLabel) {
  $("authState").textContent = label;
  if ($("fileStatus")) $("fileStatus").textContent = fileLabel;
}

function storedSession() {
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) || "null"); }
  catch { return null; }
}

function saveSession(session) {
  state.session = session;
  try {
    if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else localStorage.removeItem(SESSION_KEY);
  } catch {}
}

async function authRequest(path, body) {
  const res = await fetch(`${SB_URL}/auth/v1/${path}`, {
    method: "POST",
    headers: { apikey: SB_KEY, "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.error_description || payload.msg || `HTTP ${res.status}`);
  return payload;
}

async function refreshSession() {
  if (!state.session?.refresh_token) return null;
  try {
    const next = await authRequest("token?grant_type=refresh_token", { refresh_token: state.session.refresh_token });
    saveSession(next);
    return next.access_token;
  } catch {
    saveSession(null);
    return null;
  }
}

async function signIn(email, password) {
  const session = await authRequest("token?grant_type=password", { email, password });
  saveSession(session);
  await loadData();
}

async function loadData(retried = false) {
  const token = state.session?.access_token;
  if (!token) return renderGate("Sign in to open the private company file.");
  setAccessState("Loading private file", "checking private file");
  $("app").setAttribute("aria-busy", "true");
  const res = await fetch("data/company_intelligence.json", {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (res.status === 401 && !retried) {
    const fresh = await refreshSession();
    if (fresh) return loadData(true);
  }
  if (!res.ok) {
    setAccessState("Access blocked", "private file blocked");
    $("app").removeAttribute("aria-busy");
    return renderGate(res.status === 401
      ? "The data gate rejected this account. Owner access is required."
      : `Could not load the company file (${res.status}).`);
  }
  state.data = await res.json();
  state.selected = state.data?.tickers?.[0]?.symbol || null;
  setAccessState("Private file open", "private file open");
  $("app").removeAttribute("aria-busy");
  $("signOut").hidden = false;
  renderDesk();
}

function renderGate(message) {
  $("signOut").hidden = true;
  setAccessState("Signed out", "private file closed");
  if ($("companyStatus")) $("companyStatus").textContent = "Company Intelligence";
  $("app").removeAttribute("aria-busy");
  $("app").innerHTML = `
    <section class="gate" aria-labelledby="gateTitle">
      <div>
        <p class="eyebrow">Private research workspace</p>
        <h1 id="gateTitle">Company context,<br>one layer deeper.</h1>
        <p>Sign in with the existing Henneth account. This surface reads one private JSON file and keeps execution out of the product.</p>
      </div>
      <form id="loginForm" class="login">
        <p class="form-title">Owner access</p>
        <label><span>Email</span><input id="email" type="email" autocomplete="email" required></label>
        <label><span>Password</span><input id="password" type="password" autocomplete="current-password" required></label>
        <button class="submit-btn" type="submit">Sign in</button>
        <p id="loginMsg" class="muted" role="status" aria-live="polite">${esc(message || "No signup here. Access is owner-only at the data gate.")}</p>
      </form>
    </section>`;
  bindLogin();
}

function rows() {
  const q = state.filter.trim().toUpperCase();
  return (state.data?.tickers || []).filter(r => {
    if (!q) return true;
    return r.symbol.includes(q)
      || String(r.name || "").toUpperCase().includes(q)
      || String(r.sector || "").toUpperCase().includes(q);
  });
}

function pick(symbol) {
  state.selected = symbol;
  renderDesk();
}

function renderDesk(searchState) {
  const list = rows();
  if (!state.selected && list.length) state.selected = list[0].symbol;
  const row = list.find(r => r.symbol === state.selected) || list[0];
  if (row) state.selected = row.symbol;
  $("app").innerHTML = `
    <aside class="rail" aria-label="Company directory">
      <div class="rail-head"><strong>Company directory</strong><span>${esc(list.length)} shown</span></div>
      <div class="toolbar">
        <input id="search" class="search" type="search" aria-label="Search companies" aria-controls="companyList" placeholder="Search symbol, company, sector" value="${esc(state.filter)}">
        <button id="clearFilter" type="button" aria-label="Clear company search">Clear</button>
        <span class="muted">${esc(state.data?.meta?.count || 0)} companies. Built ${esc(state.data?.meta?.built || "unknown")}.</span>
      </div>
      <div id="companyList" class="list" role="listbox" aria-label="Companies">${list.map(r => `
        <button class="row ${r.symbol === row?.symbol ? "active" : ""}" type="button" role="option" aria-selected="${r.symbol === row?.symbol}" tabindex="${r.symbol === row?.symbol ? "0" : "-1"}" data-symbol="${esc(r.symbol)}">
          <span><b>${esc(r.symbol)}</b><small>${esc(r.name || "Name unavailable")}</small></span>
          <em>${fmt(r.liquidity?.adtv_m, 0)}M</em>
        </button>`).join("") || `<div class="empty" role="option" aria-disabled="true">No companies match that filter.</div>`}
      </div>
      <span class="sr-only" role="status" aria-live="polite">${esc(list.length)} companies match.</span>
    </aside>
    <section class="detail" aria-label="${row ? `${esc(row.symbol)} company intelligence` : "Company intelligence"}">${row ? detail(row) : `<div class="empty">No company intelligence rows are available yet.</div>`}</section>`;
  if ($("companyStatus")) $("companyStatus").textContent = row ? `${row.symbol} · company intelligence` : "Company Intelligence";
  $("search").oninput = event => {
    const start = event.target.selectionStart;
    const end = event.target.selectionEnd;
    state.filter = event.target.value;
    renderDesk({ focus: true, start, end });
  };
  $("clearFilter").onclick = () => {
    state.filter = "";
    renderDesk({ focus: true, start: 0, end: 0 });
  };
  document.querySelectorAll("[data-symbol]").forEach(btn => {
    btn.onclick = () => pick(btn.dataset.symbol);
    btn.onkeydown = event => moveCompanyFocus(event, btn);
  });
  if (searchState?.focus) {
    const input = $("search");
    input.focus({ preventScroll: true });
    input.setSelectionRange(searchState.start, searchState.end);
  }
  if (!searchState) enhanceMotion();
}

function moveCompanyFocus(event, button) {
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  const options = [...document.querySelectorAll("[data-symbol]")];
  if (!options.length) return;
  event.preventDefault();
  let index = options.indexOf(button);
  if (event.key === "ArrowDown") index = (index + 1) % options.length;
  if (event.key === "ArrowUp") index = (index - 1 + options.length) % options.length;
  if (event.key === "Home") index = 0;
  if (event.key === "End") index = options.length - 1;
  state.selected = options[index].dataset.symbol;
  renderDesk();
  document.querySelector(`[data-symbol="${CSS.escape(state.selected)}"]`)?.focus({ preventScroll: true });
}

function metric(label, value, note) {
  return `<div class="metric"><span>${esc(label)}</span><b>${esc(value)}</b><small class="muted">${esc(note || "")}</small></div>`;
}

function detail(r) {
  const f = r.fundamentals || {};
  const v = r.valuation || {};
  const p = r.profile || {};
  const liq = r.liquidity || {};
  const source = p.source_url ? `<a href="${esc(p.source_url)}" target="_blank" rel="noopener">DPS company page</a>` : "DPS company page";
  const inc = p.incorporation?.value || p.incorporation?.matched_text || "unknown";
  return `
    <div class="hero">
      <div>
        <p class="eyebrow">${esc(r.sector || "Sector unknown")}</p>
        <h1>${esc(r.symbol)}${r.name ? `, ${esc(r.name)}` : ""}</h1>
        <p>${esc(p.business_description || "The desk has not captured a business description for this company yet.")}</p>
      </div>
      <div class="stamp">
        <span class="kicker">Price</span>
        <b>Rs ${esc(fmt(r.price?.current))}</b>
        <span class="muted">${esc(pct(r.price?.ret_20d))} over 20 sessions. Research, not advice.</span>
      </div>
    </div>
    <div class="grid4">
      ${metric("Fair-value read", v.verdict || "unknown", v.mispricing_pct == null ? "model unavailable" : `${pct(v.mispricing_pct)} versus blended fair value`)}
      ${metric("Financial rating", f.rating || "unknown", f.overall || "scorecard unavailable")}
      ${metric("Liquidity", liq.adtv_m == null ? "unknown" : `Rs ${fmt(liq.adtv_m, 0)}M`, liq.signal_eligible ? "inside signal liquidity gate" : "research context only")}
      ${metric("Dividend", f.div_yield || "unknown", f.payout_ratio ? `payout ${f.payout_ratio}` : "payout unknown")}
    </div>
    <div class="panel span5">
      <span class="kicker">Company profile</span>
      <h2>Issuer context</h2>
      <div class="facts">
        <div class="fact"><span class="label">Incorporation</span><span>${esc(inc)}</span></div>
        <div class="fact"><span class="label">Source</span><span>${source}${p.fetched ? `, fetched ${esc(p.fetched)}` : ""}${p.stale ? " (stale retained row)" : ""}</span></div>
        <div class="fact"><span class="label">Indices</span><span>${esc((r.indices || []).join(", ") || "unknown")}</span></div>
      </div>
    </div>
    <div class="panel span4">
      <span class="kicker">Accounting snapshot</span>
      <h2>Numbers on file</h2>
      <div class="facts">
        <div class="fact"><span class="label">Market cap</span><span>${esc(f.market_cap || "unknown")}</span></div>
        <div class="fact"><span class="label">EPS</span><span>${esc(f.eps || "unknown")}</span></div>
        <div class="fact"><span class="label">P/E</span><span>${esc(f.pe || "unknown")}</span></div>
        <div class="fact"><span class="label">Forward P/E</span><span>${esc(f.forward_pe || "unknown")}</span></div>
      </div>
    </div>
    <div class="panel span9">
      <span class="kicker">Recent evidence</span>
      <h2>Documents and tape notes</h2>
      ${renderDocs(r)}
    </div>
    <div class="panel span5">
      <span class="kicker">Filings metadata</span>
      <h2>Insider/substantial-holder notices</h2>
      ${r.insider_filings?.length ? r.insider_filings.map(d => `<div class="docrow"><b>${esc(d.date || "undated")} ${esc(d.title || "Filing")}</b><span>${d.pdf_url ? `<a href="${esc(d.pdf_url)}" target="_blank" rel="noopener">PDF</a>` : "PDF unavailable"}; parsed transactions ${esc(d.parsed_transactions)}</span></div>`).join("") : `<p>No recent metadata rows in the retained file.</p>`}
    </div>
    <div class="panel span4">
      <span class="kicker">Off-market</span>
      <h2>Retained activity</h2>
      ${r.offmarket ? `<p>Rs ${esc(fmt(r.offmarket.value_pkr, 0))} across ${esc(fmt(r.offmarket.shares, 0))} shares and ${esc(r.offmarket.days)} day${r.offmarket.days === 1 ? "" : "s"} in the retained ${esc(r.offmarket.retention_days || "unknown")}-day window.</p>` : `<p>No off-market rows in the retained window.</p>`}
      <span class="pill ${liq.research_eligible ? "good" : ""}">research ${liq.research_eligible ? "eligible" : "not eligible"}</span>
      <span class="pill ${liq.signal_eligible ? "good" : "bad"}">signal ${liq.signal_eligible ? "eligible" : "not eligible"}</span>
    </div>`;
}

function renderDocs(r) {
  const docs = [...(r.news || []), ...(r.documents || [])];
  if (!docs.length) return `<p>No tagged documents or high-impact tape notes in the current slice.</p>`;
  return docs.map(d => `<div class="docrow">
    <b>${esc(d.date || "")} ${esc(d.headline || d.title || "Document")}</b>
    <span>${esc(d.type || (d.impact ? `impact ${d.impact}` : "news"))}${d.url ? `, <a href="${esc(d.url)}" target="_blank" rel="noopener">source</a>` : ""}</span>
  </div>`).join("");
}

function bindLogin() {
  const form = $("loginForm");
  if (!form) return;
  form.onsubmit = async event => {
    event.preventDefault();
    $("loginMsg").textContent = "Signing in";
    try {
      await signIn($("email").value.trim(), $("password").value);
    } catch (err) {
      $("loginMsg").textContent = err.message || "Sign-in failed.";
    }
  };
}

function enhanceMotion() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const app = $("app");
  app.classList.remove("is-entering");
  requestAnimationFrame(() => app.classList.add("is-entering"));
}

$("signOut").onclick = () => {
  saveSession(null);
  state.data = null;
  renderGate("Signed out.");
};

$("schemeToggle").onclick = () => applyDeskScheme(SCHEME_CYCLE[deskScheme()]);
applyDeskScheme(deskScheme());

state.session = storedSession();
if (state.session) loadData();
else renderGate();
