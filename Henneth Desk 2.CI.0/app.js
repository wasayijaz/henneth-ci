const SB_URL = "https://qteoncckohuoatbjjykb.supabase.co";
const SB_KEY = "sb_publishable_aQu8P4yrAY7l8Y0AcLth5g_Z3VceUnw";
const SESSION_KEY = "henneth-ci-session";

const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
const fmt = (value, digits = 2) => value == null ? "unknown" : Number(value).toLocaleString("en", { maximumFractionDigits: digits });
const pct = value => value == null ? "unknown" : `${value > 0 ? "+" : ""}${fmt(value, 1)}%`;

let state = { session: null, data: null, selected: null, filter: "", view: "overview" };

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
  let res;
  try {
    res = await fetch("data/company_intelligence.json", {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch {
    $("app").removeAttribute("aria-busy");
    setAccessState("Connection failed", "private file unavailable");
    return renderGate("The private file could not be reached. Your session is retained; sign in again to retry.");
  }
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
  try {
    state.data = await res.json();
  } catch {
    $("app").removeAttribute("aria-busy");
    setAccessState("File invalid", "private file unavailable");
    return renderGate("The private company file was not valid JSON. The last-good deployment remains required.");
  }
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
  document.querySelectorAll("[data-view]").forEach(btn => {
    btn.onclick = () => {
      state.view = btn.dataset.view;
      renderDesk();
    };
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
  const intel = r.intelligence || {};
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
      ${metric("Official filings", intel.document_count ?? 0, `${intel.event_count ?? 0} classified events`)}
      ${metric("Document changes", intel.change_count ?? 0, intel.last_event_at ? `latest event ${String(intel.last_event_at).slice(0, 10)}` : "no event extracted yet")}
      ${metric("Synthesis queue", intel.pending_synthesis ?? 0, "approval required · training mode")}
      ${metric("Issuer monitor", intel.source_status || "unknown", "official website layer")}
    </div>
    ${renderViewNav(r)}
    ${state.view === "timeline" ? renderTimeline(r) : state.view === "filings" ? renderFilings(r) : state.view === "sources" ? renderSources(r) : renderOverview(r, { f, v, p, liq, source, inc })}`;
}

function renderViewNav(r) {
  const tabs = [
    ["overview", "Overview"],
    ["timeline", `Timeline ${r.timeline?.length || 0}`],
    ["filings", `Filings ${r.filings?.length || 0}`],
    ["sources", `Sources ${(r.sources?.sources?.length || 0) + (r.sources?.documents?.length || 0)}`],
  ];
  return `<nav class="viewnav" aria-label="Company intelligence views" role="tablist">${tabs.map(([key, label]) => `
    <button type="button" role="tab" aria-selected="${state.view === key}" class="${state.view === key ? "active" : ""}" data-view="${key}">${esc(label)}</button>`).join("")}</nav>`;
}

function renderOverview(r, ctx) {
  const { f, v, p, liq, source, inc } = ctx;
  return `
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
        <div class="fact"><span class="label">Fair-value model</span><span>${esc(v.verdict || "unknown")}${v.mispricing_pct == null ? "" : ` · ${esc(pct(v.mispricing_pct))} versus blended fair value`}</span></div>
      </div>
    </div>
    <div class="panel span9">
      <span class="kicker">Recent evidence</span>
      <h2>Research notes and tape</h2>
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

function evidenceLink(item) {
  if (!item) return "";
  const page = Number(item.page) > 0 ? `page ${Number(item.page)}` : "source excerpt";
  const excerpt = item.text ? `<blockquote>${esc(item.text)}</blockquote>` : "";
  const link = item.source_url ? `<a href="${esc(item.source_url)}" target="_blank" rel="noopener">${page}</a>` : esc(page);
  return `<div class="evidence"><span>${link} · extracted evidence</span>${excerpt}</div>`;
}

function renderTimeline(r) {
  const events = r.timeline || [];
  const changes = r.changes || [];
  return `
    <section class="panel span6"><span class="kicker">Evidence-linked chronology</span><h2>Company timeline</h2>
      <p class="section-note">Deterministically classified from official documents. Priority is an extraction-routing weight, not an investment score.</p>
      <div class="timeline">${events.length ? events.map(event => `<article class="timeline-row">
        <time>${esc(String(event.date || "undated").slice(0, 10))}</time>
        <div><span class="pill">${esc(event.type || "other")}</span><span class="priority">priority ${esc(event.priority_weight ?? "unknown")}</span>
        ${(event.evidence || []).map(evidenceLink).join("")}</div>
      </article>`).join("") : `<div class="empty">No official-document event has been extracted for this company yet.</div>`}</div>
    </section>
    <aside class="panel span3"><span class="kicker">Revision ledger</span><h2>Document changes</h2>
      ${changes.length ? changes.map(change => `<div class="change-row"><b>${esc(String(change.date || "undated").slice(0, 16))}</b><span>${esc(change.type || "document revision")}</span>${renderFactDelta(change.fact_delta)}</div>`).join("") : `<p>No content-hash revision is recorded yet.</p>`}
    </aside>`;
}

function renderFactDelta(delta) {
  if (!delta) return "";
  const parts = [
    ["added", delta.added], ["changed", delta.changed], ["removed", delta.removed],
  ].filter(([, value]) => Array.isArray(value) && value.length);
  return parts.length ? `<ul class="delta">${parts.map(([label, value]) => `<li>${esc(label)}: ${esc(value.length)}</li>`).join("")}</ul>` : "";
}

function renderFilings(r) {
  const filings = r.filings || [];
  return `<section class="panel span9"><span class="kicker">Official PSX / PUCARS record</span><h2>Filings and announcements</h2>
    <p class="section-note">Facts below are machine-extracted and always paired with their source page. Agent synthesis remains paused for owner approval.</p>
    <div class="filings">${filings.length ? filings.map(doc => `<article class="filing">
      <header><div><time>${esc(String(doc.date || "undated").slice(0, 10))}</time><h3>${esc(doc.title || doc.type || "Official document")}</h3></div><span class="pill ${doc.status === "ready" ? "good" : ""}">${esc(doc.status || "unknown")}</span></header>
      <p class="filing-meta">${esc(doc.type || "unclassified")} · ${doc.url ? `<a href="${esc(doc.url)}" target="_blank" rel="noopener">open official source</a>` : "source unavailable"} · synthesis ${esc(doc.synthesis?.approval_status || "not queued")}</p>
      ${doc.error ? `<p class="extract-error">Extraction retained for retry: ${esc(doc.error)}</p>` : ""}
      ${renderFacts(doc.facts)}
      ${(doc.evidence || []).map(evidenceLink).join("")}
    </article>`).join("") : `<div class="empty">No official PDF has completed extraction for this company yet.</div>`}</div>
  </section>`;
}

function renderFacts(facts) {
  if (!facts?.length) return `<p class="muted">No labelled financial fact was extracted from this document.</p>`;
  return `<div class="fact-grid">${facts.map(fact => {
    const citation = fact.evidence?.[0];
    const page = Number(citation?.page) > 0 ? `page ${Number(citation.page)}` : "page unknown";
    const source = citation?.source_url ? `<a href="${esc(citation.source_url)}" target="_blank" rel="noopener">${esc(page)}</a>` : esc(page);
    return `<div><span>${esc(fact.type || "fact")}</span><b>${esc(fact.raw_value ?? "unknown")}</b><small>${esc(fact.unit || "reported units")} · ${source}</small></div>`;
  }).join("")}</div>`;
}

function renderSources(r) {
  const registry = r.sources || {};
  const pages = registry.sources || [];
  const docs = registry.documents || [];
  return `
    <section class="panel span5"><span class="kicker">Issuer-owned web estate</span><h2>Monitored sources</h2>
      <p class="section-note">Discovered from the official DPS company profile, then restricted to the same issuer domain.</p>
      ${registry.issuer_url ? `<p><a href="${esc(registry.issuer_url)}" target="_blank" rel="noopener">Open issuer website</a></p>` : ""}
      ${pages.length ? pages.map(page => `<div class="source-row"><div><b>${esc(page.title || page.kind || "Issuer page")}</b><span>${esc(page.kind || "page")} · ${esc(page.status || "unknown")}${page.changed ? " · changed" : ""}</span></div><a href="${esc(page.url)}" target="_blank" rel="noopener">open</a></div>`).join("") : `<div class="empty">No issuer page has been verified yet.</div>`}
    </section>
    <section class="panel span4"><span class="kicker">Issuer document index</span><h2>Reports and presentations</h2>
      ${docs.length ? docs.map(doc => `<div class="source-row"><div><b>${esc(doc.title || doc.type || "Issuer document")}</b><span>${esc(doc.type || "document")}${doc.first_seen ? ` · first seen ${esc(String(doc.first_seen).slice(0, 10))}` : ""}</span></div><a href="${esc(doc.url)}" target="_blank" rel="noopener">open</a></div>`).join("") : `<div class="empty">No same-domain report link has been indexed yet.</div>`}
    </section>`;
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
