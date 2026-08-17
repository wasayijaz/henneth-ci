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
  $("authState").textContent = "Loading private file";
  const res = await fetch("data/company_intelligence.json", {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (res.status === 401 && !retried) {
    const fresh = await refreshSession();
    if (fresh) return loadData(true);
  }
  if (!res.ok) {
    $("authState").textContent = "Access blocked";
    return renderGate(res.status === 401
      ? "The data gate rejected this account. Owner access is required."
      : `Could not load the company file (${res.status}).`);
  }
  state.data = await res.json();
  state.selected = state.data?.tickers?.[0]?.symbol || null;
  $("authState").textContent = "Private file open";
  $("signOut").hidden = false;
  renderDesk();
}

function renderGate(message) {
  $("signOut").hidden = true;
  $("authState").textContent = "Signed out";
  $("app").innerHTML = `
    <section class="gate" aria-labelledby="gateTitle">
      <div>
        <p class="eyebrow">Private research workspace</p>
        <h1 id="gateTitle">Company context, one layer deeper.</h1>
        <p>Sign in with the existing Henneth account. This surface reads one private JSON file and keeps execution out of the product.</p>
      </div>
      <form id="loginForm" class="login">
        <label>Email<input id="email" type="email" autocomplete="email" required></label>
        <label>Password<input id="password" type="password" autocomplete="current-password" required></label>
        <button type="submit">Sign in</button>
        <p id="loginMsg" class="muted">${esc(message || "No signup here. Access is owner-only at the data gate.")}</p>
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

function renderDesk() {
  const list = rows();
  if (!state.selected && list.length) state.selected = list[0].symbol;
  const row = list.find(r => r.symbol === state.selected) || list[0];
  $("app").innerHTML = `
    <aside class="rail">
      <div class="toolbar">
        <input id="search" class="search" placeholder="Search symbol, company, sector" value="${esc(state.filter)}">
        <button id="clearFilter" type="button">Clear</button>
        <span class="muted">${esc(state.data?.meta?.count || 0)} companies. Built ${esc(state.data?.meta?.built || "unknown")}.</span>
      </div>
      <div class="list">${list.map(r => `
        <button class="row ${r.symbol === row?.symbol ? "active" : ""}" data-symbol="${esc(r.symbol)}">
          <span><b>${esc(r.symbol)}</b><small>${esc(r.name || "Name unavailable")}</small></span>
          <em>${fmt(r.liquidity?.adtv_m, 0)}M</em>
        </button>`).join("") || `<div class="empty">No companies match that filter.</div>`}
      </div>
    </aside>
    <section class="detail">${row ? detail(row) : `<div class="empty">No company intelligence rows are available yet.</div>`}</section>`;
  $("search").oninput = event => { state.filter = event.target.value; renderDesk(); };
  $("clearFilter").onclick = () => { state.filter = ""; renderDesk(); };
  document.querySelectorAll("[data-symbol]").forEach(btn => {
    btn.onclick = () => pick(btn.dataset.symbol);
  });
  enhanceMotion();
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
  if (!window.gsap) return;
  try {
    if (window.ScrollTrigger) gsap.registerPlugin(ScrollTrigger);
    gsap.fromTo(".hero h1, .hero p, .metric, .panel", {
      autoAlpha: 0,
      y: 14,
    }, {
      autoAlpha: 1,
      y: 0,
      duration: 0.55,
      ease: "power2.out",
      stagger: 0.035,
      overwrite: true,
    });
    if (window.ScrollTrigger) {
      gsap.utils.toArray(".panel").forEach((panel, i) => {
        gsap.to(panel, {
          y: -Math.min(i, 3) * 4,
          scrollTrigger: {
            trigger: panel,
            start: "top 80%",
            end: "bottom 40%",
            scrub: true,
          },
        });
      });
    }
  } catch {
    /* Motion is decorative; the data surface must work without it. */
  }
}

$("signOut").onclick = () => {
  saveSession(null);
  state.data = null;
  renderGate("Signed out.");
};

state.session = storedSession();
if (state.session) loadData();
else renderGate();
