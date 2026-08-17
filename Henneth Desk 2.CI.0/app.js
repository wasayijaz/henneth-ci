const SB_URL = "https://qteoncckohuoatbjjykb.supabase.co";
const SB_KEY = "sb_publishable_aQu8P4yrAY7l8Y0AcLth5g_Z3VceUnw";
const SESSION_KEY = "henneth-ci-session";

const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
const fmt = (value, digits = 2) => value == null ? "unknown" : Number(value).toLocaleString("en", { maximumFractionDigits: digits });
const pct = value => value == null ? "unknown" : `${value > 0 ? "+" : ""}${fmt(value, 1)}%`;
const short = (value, limit = 80) => {
  const text = String(value ?? "");
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
};

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
      ${metric("Financial facts", intel.financial_fact_count ?? 0, `${r.financial_series?.coverage?.period_count ?? 0} explicit periods`)}
      ${metric("Change digest", intel.change_item_count ?? 0, `${r.change_intelligence?.latest_change_at || "no dated change"}`)}
      ${metric("Graph links", intel.graph_edge_count ?? 0, `${intel.graph_node_count ?? 0} nodes mapped`)}
    </div>
    ${renderViewNav(r)}
    ${state.view === "timeline" ? renderTimeline(r)
      : state.view === "changes" ? renderChangeIntelligence(r)
      : state.view === "trends" ? renderFinancials(r)
      : state.view === "graph" ? renderGraph(r)
      : state.view === "coverage" ? renderCoverage(r)
      : state.view === "filings" ? renderFilings(r)
      : state.view === "sources" ? renderSources(r)
      : state.view === "brief" ? renderBrief(r)
      : renderOverview(r, { f, v, p, liq, source, inc })}`;
}

function renderViewNav(r) {
  const tabs = [
    ["overview", "Overview"],
    ["timeline", `Timeline ${r.timeline?.length || 0}`],
    ["changes", `Changes ${r.change_intelligence?.items?.length || 0}`],
    ["trends", `Trends ${r.financial_series?.facts?.length || 0}`],
    ["graph", `Graph ${r.graph?.edges?.length || 0}`],
    ["coverage", "Coverage"],
    ["filings", `Filings ${r.filings?.length || 0}`],
    ["sources", `Sources ${(r.sources?.sources?.length || 0) + (r.sources?.documents?.length || 0)}`],
    ["brief", r.brief?.current ? "Brief" : "Brief queue"],
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
    </div>
    <div class="panel span9">
      <span class="kicker">Intelligence map</span>
      <h2>What the official file currently proves</h2>
      ${renderGraphSummary(r)}
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

function renderChangeIntelligence(r) {
  const digest = r.change_intelligence || {};
  const items = digest.items || [];
  const counts = digest.counts || {};
  return `<section class="panel span9">
    <span class="kicker">Official-source change intelligence</span><h2>What changed in the company file</h2>
    <p class="section-note">Built deterministically from official filings, monitored issuer pages, source-linked financial facts and event classifications. This is a research queue, not advice.</p>
    <div class="change-summary">
      ${metric("Status", digest.status || "quiet", `latest ${digest.latest_change_at || "unknown"}`)}
      ${metric("Documents", counts.document ?? 0, `${counts.issuer_document ?? 0} issuer PDFs`)}
      ${metric("Events", counts.event ?? 0, `${counts.financial ?? 0} financial movements`)}
      ${metric("Source pages", counts.source ?? 0, "same-domain hash changes")}
    </div>
    <div class="change-list">${items.length ? items.map(renderChangeItem).join("") : `<div class="empty">No source-backed change digest item is available for this company yet.</div>`}</div>
  </section>`;
}

function renderChangeItem(item) {
  const evidence = item.evidence || {};
  const page = Number(evidence.page) > 0 ? `p.${Number(evidence.page)}` : "source";
  const source = item.source_url ? `<a href="${esc(item.source_url)}" target="_blank" rel="noopener">${esc(page)}</a>` : esc(page);
  const delta = item.kind === "financial" ? renderChangeDelta(item) : "";
  return `<article class="change-card severity-${esc(item.severity || "routine")}">
    <header><div><time>${esc(item.date || "undated")}</time><h3>${esc(item.title || item.kind || "change")}</h3></div><span class="pill">${esc(item.severity || "routine")}</span></header>
    <p>${esc(item.summary || "Source-backed change retained for review.")}</p>
    ${delta}
    <footer><span>${esc(item.kind || "change")}${item.document_id ? ` · ${esc(item.document_id)}` : ""}</span><span>${source}</span></footer>
    ${evidence.text ? `<blockquote>${esc(evidence.text)}</blockquote>` : ""}
  </article>`;
}

function renderChangeDelta(item) {
  const pctText = item.delta_pct == null ? "" : ` · ${pct(item.delta_pct)}`;
  const period = item.previous_period_end && item.period_end ? `${item.previous_period_end} → ${item.period_end}` : item.period_end || "period unknown";
  return `<div class="change-delta"><b>${esc(fmt(item.delta, 2))}${esc(pctText)}</b><span>${esc(period)} · ${esc(item.consolidation || "basis unknown")}</span></div>`;
}

function renderFactDelta(delta) {
  if (!delta) return "";
  const parts = [
    ["added", delta.added], ["changed", delta.changed], ["removed", delta.removed],
  ].filter(([, value]) => Array.isArray(value) && value.length);
  return parts.length ? `<ul class="delta">${parts.map(([label, value]) => `<li>${esc(label)}: ${esc(value.length)}</li>`).join("")}</ul>` : "";
}

function renderFinancials(r) {
  const series = r.financial_series || {};
  const facts = series.facts || [];
  const coverage = series.coverage || {};
  const conflicts = series.conflicts || [];
  const trends = buildTrends(facts);
  return `<section class="panel span9">
    <span class="kicker">Period-aware extraction</span><h2>Financial facts from official PDFs</h2>
    <p class="section-note">Only labelled values with document/page evidence are shown. Unknown period, unit, basis or currency stays flagged instead of being guessed.</p>
    <div class="series-health">
      ${metric("Facts", coverage.fact_count ?? facts.length, `${coverage.source_documents ?? 0} source documents`)}
      ${metric("Model-loadable", coverage.model_loadable_count ?? 0, `${coverage.audit_only_count ?? facts.length} audit-only`)}
      ${metric("Conflicts", coverage.conflict_count ?? conflicts.length, "same metric/period/basis")}
    </div>
    ${conflicts.length ? `<div class="extract-error">Conflicts need review: ${esc(conflicts.map(c => `${c.metric || "metric"} ${c.period_end || "period unknown"}`).join(", "))}</div>` : ""}
    ${trends.length ? `<div class="trend-grid">${trends.map(renderTrend).join("")}</div>` : `<div class="empty">At least two comparable, explicitly dated facts are required before a trend is drawn.</div>`}
    <div class="fact-table" role="table" aria-label="Extracted financial facts">
      <div role="row" class="fact-table-head"><span>Metric</span><span>Period</span><span>Value</span><span>Basis</span><span>Evidence</span><span>Flags</span></div>
      ${facts.length ? facts.map(fact => {
        const cite = (fact.evidence || [])[0] || {};
        const page = Number(cite.page) > 0 ? `p.${Number(cite.page)}` : "page?";
        const evidence = fact.source_url ? `<a href="${esc(fact.source_url)}" target="_blank" rel="noopener">${esc(page)}</a>` : esc(page);
        const flags = (fact.quality_flags || []).length ? fact.quality_flags.join(", ") : "clean";
        return `<div role="row" class="fact-table-row">
          <span>${esc(fact.metric || "other")}</span>
          <span>${esc(fact.period_end || "unknown")}<small>${esc(fact.period_type || "period type unknown")}</small></span>
          <span><b>${esc(fact.raw_value ?? "unknown")}</b><small>${esc(fact.currency || "currency unknown")} · x${esc(fact.unit_multiplier ?? "?")}</small></span>
          <span>${esc(fact.consolidation || "basis unknown")}<small>${esc(fact.readiness || "audit_only")}</small></span>
          <span>${evidence}</span>
          <span>${esc(flags)}</span>
        </div>`;
      }).join("") : `<div class="empty">No source-linked financial fact has been normalized for this company yet.</div>`}
    </div>
  </section>`;
}

function buildTrends(facts) {
  const groups = new Map();
  facts.forEach(fact => {
    const value = Number(fact.normalized_value);
    if (!fact.period_end || !Number.isFinite(value) || (fact.quality_flags || []).includes("conflict")) return;
    const key = [fact.metric, fact.consolidation, fact.currency, fact.unit_multiplier].join("|");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(fact);
  });
  return [...groups.values()].map(points => points.sort((a, b) => String(a.period_end).localeCompare(String(b.period_end))))
    .filter(points => points.length >= 2).sort((a, b) => b.length - a.length).slice(0, 6);
}

function renderTrend(points) {
  const values = points.map(point => Number(point.normalized_value));
  const low = Math.min(...values), high = Math.max(...values), spread = high - low || 1;
  const coords = values.map((value, index) => {
    const x = points.length === 1 ? 120 : 8 + index * (224 / (points.length - 1));
    const y = 56 - ((value - low) / spread) * 48;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const latest = points.at(-1);
  return `<article class="trend-card">
    <header><div><span>${esc(latest.metric || "metric")}</span><b>${esc(latest.raw_value ?? "unknown")}</b></div><em>${esc(latest.consolidation || "basis unknown")}</em></header>
    <svg viewBox="0 0 240 64" role="img" aria-label="${esc(latest.metric || "metric")} across ${esc(points.length)} explicitly dated periods"><polyline points="${coords}"></polyline>${coords.split(" ").map(pair => { const [cx, cy] = pair.split(","); return `<circle cx="${cx}" cy="${cy}" r="2.4"></circle>`; }).join("")}</svg>
    <footer><span>${esc(points[0].period_end)}</span><span>${esc(latest.period_end)}</span></footer>
  </article>`;
}

function renderGraphSummary(r) {
  const graph = r.graph || {};
  const summary = graph.summary || {};
  return `<div class="graph-summary">
    <div><b>${esc(summary.document ?? 0)}</b><span>official documents</span></div>
    <div><b>${esc(summary.fact ?? 0)}</b><span>financial fact nodes</span></div>
    <div><b>${esc(summary.period ?? 0)}</b><span>explicit periods</span></div>
    <div><b>${esc(summary.event ?? 0)}</b><span>document events</span></div>
    <div><b>${esc(summary.source ?? 0)}</b><span>issuer/source links</span></div>
  </div>`;
}

function renderGraph(r) {
  const graph = r.graph || {};
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const byId = Object.fromEntries(nodes.map(node => [node.id, node]));
  const layout = layoutGraph(nodes);
  const visibleIds = new Set(layout.map(item => item.node.id));
  const visibleEdges = edges.filter(edge => visibleIds.has(edge.from) && visibleIds.has(edge.to));
  const positions = Object.fromEntries(layout.map(item => [item.node.id, item]));
  const rows = visibleEdges.slice(0, 40);
  return `<section class="panel span9">
    <span class="kicker">Knowledge graph</span><h2>Issuer relationships</h2>
    <p class="section-note">This is a deterministic relationship map over official documents, extracted events, financial facts, periods and monitored issuer sources.</p>
    ${renderGraphSummary(r)}
    ${layout.length ? `<div class="graph-canvas" role="img" aria-label="Evidence-backed company relationship graph">
      <svg viewBox="0 0 1000 540" aria-hidden="true">${visibleEdges.map(edge => {
        const from = positions[edge.from], to = positions[edge.to];
        return `<line x1="${from.x * 10}" y1="${from.y * 5.4}" x2="${to.x * 10}" y2="${to.y * 5.4}"></line>`;
      }).join("")}</svg>
      ${layout.map(({node, x, y}) => renderGraphNode(node, x, y)).join("")}
    </div>` : `<div class="empty">No graph nodes have been built for this company yet.</div>`}
    <div class="edge-list">${rows.length ? rows.map(edge => {
      const left = byId[edge.from]?.label || edge.from;
      const right = byId[edge.to]?.label || edge.to;
      const evidence = edge.evidence || {};
      const provenance = evidence.source_url
        ? `<a href="${esc(evidence.source_url)}" target="_blank" rel="noopener">${evidence.page ? `p.${esc(evidence.page)}` : "source"}</a>`
        : "source unavailable";
      return `<div class="edge-row"><span>${esc(short(left, 30))}</span><b>${esc(edge.type || "linked")}</b><span>${esc(short(right, 30))}</span><em>${provenance}</em></div>`;
    }).join("") : `<div class="empty">No graph edges have been built for this company yet.</div>`}</div>
  </section>`;
}

function layoutGraph(nodes) {
  const layerFor = { company: 0, document: 1, source: 1, event: 2, fact: 2, change: 2, period: 3 };
  const layers = [[], [], [], []];
  nodes.forEach(node => layers[layerFor[node.type] ?? 2].push(node));
  const x = [8, 34, 64, 90];
  return layers.flatMap((layer, layerIndex) => layer.slice(0, layerIndex === 0 ? 1 : 9).map((node, index) => ({
    node, x: x[layerIndex], y: layer.length === 1 ? 50 : 8 + index * (84 / Math.max(1, Math.min(layer.length, 9) - 1)),
  })));
}

function renderGraphNode(node, x, y) {
  const body = `<b>${esc(short(node.label || node.id, 32))}</b><span>${esc(node.type || "node")}</span>`;
  const style = `left:${x}%;top:${y}%`;
  return node.source_url || node.url
    ? `<a class="graph-node kind-${esc(node.type || "other")}" style="${style}" href="${esc(node.source_url || node.url)}" target="_blank" rel="noopener">${body}</a>`
    : `<div class="graph-node kind-${esc(node.type || "other")}" style="${style}">${body}</div>`;
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

function renderCoverage(r) {
  const quality = r.source_quality || {};
  const financial = r.financial_series?.coverage || {};
  const intel = r.intelligence || {};
  const flags = quality.quality_flags || [];
  return `
    <section class="panel span5"><span class="kicker">Evidence coverage</span><h2>What is currently usable</h2>
      <div class="coverage-grid">
        ${metric("Extracted filings", intel.document_count ?? 0, `${intel.event_count ?? 0} events classified`)}
        ${metric("Financial facts", financial.fact_count ?? 0, `${financial.model_loadable_count ?? 0} model-loadable`)}
        ${metric("Issuer documents", quality.document_link_count ?? 0, `${quality.monitored_page_count ?? 0} monitored pages`)}
        ${metric("Pending synthesis", intel.pending_synthesis ?? 0, "owner approval required")}
      </div>
    </section>
    <section class="panel span4"><span class="kicker">Source QA</span><h2>Known limitations</h2>
      <p>Status: <b>${esc(quality.status || "unknown")}</b>. Missing required source: <b>${quality.missing_required_source ? "yes" : "no"}</b>.</p>
      ${flags.length ? `<ul class="quality-flags">${flags.map(flag => `<li>${esc(flag.replaceAll("_", " "))}</li>`).join("")}</ul>` : `<p>No source-registry flag is active for this company.</p>`}
      ${financial.missing_period_count ? `<p>${esc(financial.missing_period_count)} extracted fact${financial.missing_period_count === 1 ? "" : "s"} remain audit-only because the reporting period was not explicit.</p>` : ""}
      ${financial.conflict_count ? `<p>${esc(financial.conflict_count)} comparable period/basis conflict${financial.conflict_count === 1 ? "" : "s"} require review.</p>` : ""}
    </section>`;
}

function renderBrief(r) {
  const current = r.brief?.current;
  if (!current) {
    return `<section class="panel span9"><span class="kicker">Training mode</span><h2>No owner-approved brief yet</h2>
      <p class="section-note">Model synthesis is intentionally paused here. Candidates are written to ignored local cache, independently verified, then approved by the owner before anything becomes durable state.</p>
      <div class="queue-panel">
        <div><b>${esc(r.intelligence?.pending_synthesis ?? 0)}</b><span>pending queue items</span></div>
        <div><b>${esc(r.intelligence?.brief_status || "training_only")}</b><span>publication state</span></div>
        <div><b>${esc(r.brief?.history_count ?? 0)}</b><span>approved history rows</span></div>
      </div>
    </section>`;
  }
  const sections = current.sections || {};
  return `<section class="panel span9"><span class="kicker">Owner-approved synthesis</span><h2>${esc(current.headline || "Company brief")}</h2>
    <p class="section-note">This brief passed deterministic citation validation and independent verifier review before owner approval.</p>
    ${["what_changed", "financial_read", "management_and_capital", "open_questions"].map(key => `<section class="brief-section">
      <h3>${esc(key.replaceAll("_", " "))}</h3>
      ${(sections[key] || []).length ? sections[key].map(item => `<p>${esc(item.text || "")} ${renderBriefEvidence(item.evidence)}</p>`).join("") : `<p class="muted">No approved statements in this section.</p>`}
    </section>`).join("")}
    ${(current.limitations || []).length ? `<div class="limitations"><b>Limitations</b><ul>${current.limitations.map(item => `<li>${esc(item)}</li>`).join("")}</ul></div>` : ""}
  </section>`;
}

function renderBriefEvidence(refs) {
  if (!Array.isArray(refs) || !refs.length) return "";
  return `<small class="brief-cites">${refs.map(ref => {
    const label = `${esc(ref.doc_id || "doc")} p.${esc(ref.page || "?")}`;
    return ref.source_url ? `<a href="${esc(ref.source_url)}" target="_blank" rel="noopener">${label}</a>` : label;
  }).join(" · ")}</small>`;
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
