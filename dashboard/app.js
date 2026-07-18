/* PSX Trade Desk SPA — hash router, 4 themes, canvas charts.
   Routes: #/board · #/ticker/SYM · #/dividends · #/news
   All data from ../state/*.json (DPS-sourced). No external deps. */

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sgn = v => (v > 0 ? "+" : "") + v;
const cls = v => v > 0.05 ? "up" : v < -0.05 ? "dn" : "";
const fmt = (v, d = 2) => v == null ? "—" : Number(v).toLocaleString("en", { maximumFractionDigits: d });

// Data source: local dev reads ../state/ ; the deployed dashboard (GitHub Pages)
// reads state/ published alongside it by the GitHub Actions pipeline every 30 min.
const LOCAL = ["localhost", "127.0.0.1", ""].includes(location.hostname);
const DATA_BASE = LOCAL ? "../state/" : "state/";

// Some browser extensions (ad/anti-fraud blockers) monkey-patch window.fetch and
// throw "TypeError: Failed to fetch" on same-origin requests unrelated to ads —
// seen in the wild breaking every state/*.json load. XHR isn't patched by those
// extensions, so it's the fallback when fetch itself throws (not just a bad response).
function xhrJson(url) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("GET", url, true);
    x.onload = () => { if (x.status >= 200 && x.status < 300) { try { resolve(JSON.parse(x.responseText)); } catch (e) { reject(e); } } else reject(new Error("HTTP " + x.status)); };
    x.onerror = () => reject(new Error("xhr network error"));
    x.send();
  });
}

const cache = {};
async function j(p, ttl = 25000) {
  const now = Date.now();
  if (cache[p] && now - cache[p].t < ttl) return cache[p].v;
  // several attempts across two transports; never cache a failure (a transient miss
  // must not blank the page for 25s) — falls back to last-known-good if all fail.
  const url = () => DATA_BASE + p + "?t=" + Date.now();
  let lastErr = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const v = attempt < 2 ? await fetch(url()).then(r => r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status)))
        : await xhrJson(url()); // last attempt: bypass a fetch() an extension may have broken
      cache[p] = { t: Date.now(), v };
      return v;
    } catch (e) { lastErr = e; /* fall through to retry */ }
    if (attempt < 2) await new Promise(res => setTimeout(res, 300));
  }
  // All 3 attempts (2x fetch + 1x XHR) failed — surface this, don't swallow it silently.
  // A "Failed to fetch" with no HTTP status usually means a browser extension or network
  // policy blocked the request before it left the browser (check the Network tab's status
  // column for "(blocked)" / "ERR_BLOCKED_BY_CLIENT"), not a server-side data problem.
  console.warn(`[psx-desk] j("${p}") failed after all attempts:`, lastErr);
  return cache[p]?.v ?? null; // serve last-known-good if we ever had it
}

/* ---------- header chips ---------- */
function marketStatus() {
  const d = new Date(), day = d.getDay(), m = d.getHours() * 60 + d.getMinutes();
  const bt = (a, b) => m >= a && m <= b;
  if (day === 0 || day === 6) return ["WEEKEND", false];
  if (day === 5) return bt(557, 720) || bt(872, 990) ? ["LIVE", true] : ["CLOSED", false];
  return bt(572, 930) ? ["LIVE", true] : ["CLOSED", false];
}
async function renderHeader() {
  const [health, quant, live, macro, dash] = await Promise.all([j("health.json"), j("quant.json"), j("live.json"), j("macro.json"), j("dashboard.json")]);
  const [mt, mo] = marketStatus();
  $("mkt").textContent = "PSX " + mt; $("mkt").className = "pill " + (mo ? "ok" : "");
  if (health) { $("health").textContent = "HEALTH " + health.status.toUpperCase(); $("health").className = "pill " + (health.status === "ok" ? "ok" : "bad"); $("health").title = (health.problems || []).join("; "); }
  const reg = macro?.regime || "—";
  $("regime").textContent = "REGIME: " + reg.toUpperCase(); $("regime").className = "pill clickable " + (reg === "risk-off" ? "bad" : reg === "risk-on" ? "ok" : "");
  $("regime").onclick = () => location.hash = "#/macro";
  const geo = dash?.geo_risk;
  const gc = $("georisk");
  if (gc && geo?.score != null) {
    gc.style.display = "";
    gc.textContent = "RISK " + geo.score;
    gc.className = "pill clickable " + (geo.band === "elevated" ? "bad" : geo.band === "calm" ? "ok" : "");
    gc.title = `Geopolitical & market-stress radar: ${geo.score}/100 (${geo.band}). Click for the factors.`;
    gc.onclick = () => location.hash = "#/macro";
  } else if (gc) { gc.style.display = "none"; }
  $("regime").title = reg === "—" ? "Macro regime — run the desk to populate" :
    `Macro regime = the desk's risk posture (${reg}). ${reg === "risk-on" ? "Full setups allowed." : reg === "risk-off" ? "Max 2 setups, defensive only." : "Neutral — normal caution."} Click for the drivers.`;
  $("updated").textContent = "quant " + (quant?.updated || "—") + " · live " + (live?.updated || "—");
}

/* ---------- canvas chart ---------- */
function drawChart(canvas, tooltip, hist, days) {
  const rows = hist.slice(-days);
  const W = canvas.clientWidth, H = canvas.clientHeight || 320;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
  const css = getComputedStyle(document.body);
  const up = css.getPropertyValue("--up").trim(), dn = css.getPropertyValue("--dn").trim();
  const accent = css.getPropertyValue("--accent").trim();
  const ink = css.color;
  const padL = 8, padR = 56, padT = 10, volH = 46, plotH = H - volH - 26;

  const closes = rows.map(r => r.close), vols = rows.map(r => r.volume);
  const lo = Math.min(...closes), hi = Math.max(...closes), span = (hi - lo) || 1;
  const vmax = Math.max(...vols) || 1;
  const X = i => padL + i / (rows.length - 1) * (W - padL - padR);
  const Y = v => padT + (1 - (v - lo) / span) * plotH;

  ctx.clearRect(0, 0, W, H);
  // gridlines + right axis labels
  ctx.globalAlpha = .35; ctx.strokeStyle = ink; ctx.lineWidth = .5;
  ctx.font = "10px sans-serif"; ctx.fillStyle = ink;
  for (let g = 0; g <= 3; g++) {
    const v = lo + span * g / 3, y = Y(v);
    ctx.globalAlpha = .12; ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
    ctx.globalAlpha = .55; ctx.fillText(fmt(v), W - padR + 6, y + 3);
  }
  ctx.globalAlpha = 1;
  // volume bars
  const pos = closes[closes.length - 1] >= closes[0];
  rows.forEach((r, i) => {
    ctx.fillStyle = (i > 0 && r.close >= rows[i - 1].close) ? up : dn;
    ctx.globalAlpha = .45;
    const bh = (r.volume / vmax) * volH;
    ctx.fillRect(X(i) - 1, H - 20 - bh, 2, bh);
  });
  ctx.globalAlpha = 1;
  // price line + soft area
  const lineC = pos ? up : dn;
  ctx.beginPath();
  rows.forEach((r, i) => i ? ctx.lineTo(X(i), Y(r.close)) : ctx.moveTo(X(i), Y(r.close)));
  ctx.strokeStyle = lineC; ctx.lineWidth = 2; ctx.stroke();
  ctx.lineTo(X(rows.length - 1), padT + plotH); ctx.lineTo(X(0), padT + plotH); ctx.closePath();
  ctx.globalAlpha = .08; ctx.fillStyle = lineC; ctx.fill(); ctx.globalAlpha = 1;
  // date ticks
  ctx.fillStyle = ink; ctx.globalAlpha = .55;
  [0, Math.floor(rows.length / 2), rows.length - 1].forEach(i => {
    ctx.fillText(rows[i].date, Math.min(X(i), W - padR - 58), H - 6);
  });
  ctx.globalAlpha = 1;

  canvas.onmousemove = e => {
    const rect = canvas.getBoundingClientRect();
    const i = Math.round((e.clientX - rect.left - padL) / (W - padL - padR) * (rows.length - 1));
    if (i < 0 || i >= rows.length) { tooltip.style.display = "none"; return; }
    const r = rows[i];
    tooltip.style.display = "block";
    tooltip.style.left = Math.min(e.clientX - rect.left + 12, W - 150) + "px";
    tooltip.style.top = "8px";
    const chg = i ? ((r.close / rows[i - 1].close - 1) * 100) : 0;
    tooltip.innerHTML = `<b>${r.date}</b><br>close ${fmt(r.close)} <span class="${cls(chg)}">${sgn(chg.toFixed(2))}%</span><br>vol ${fmt(r.volume, 0)}`;
  };
  canvas.onmouseleave = () => tooltip.style.display = "none";
}

function drawIntraday(canvas, tooltip, points, prevClose) {
  const W = canvas.clientWidth, H = canvas.clientHeight || 320, dpr = window.devicePixelRatio || 1;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
  const css = getComputedStyle(document.body);
  const up = css.getPropertyValue("--up").trim(), dn = css.getPropertyValue("--dn").trim(), ink = css.color;
  const padL = 8, padR = 56, padT = 12, plotH = H - 40;
  const prices = points.map(p => p.p);
  const lo = Math.min(prevClose, ...prices), hi = Math.max(prevClose, ...prices), span = (hi - lo) || 1;
  const X = i => padL + i / (points.length - 1) * (W - padL - padR);
  const Y = v => padT + (1 - (v - lo) / span) * plotH;
  ctx.clearRect(0, 0, W, H);
  ctx.font = "10px sans-serif"; ctx.fillStyle = ink;
  for (let g = 0; g <= 3; g++) { const v = lo + span * g / 3, y = Y(v); ctx.globalAlpha = .1; ctx.strokeStyle = ink; ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke(); ctx.globalAlpha = .55; ctx.fillText(fmt(v), W - padR + 6, y + 3); }
  ctx.globalAlpha = .5; ctx.strokeStyle = ink; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(padL, Y(prevClose)); ctx.lineTo(W - padR, Y(prevClose)); ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
  const pos = prices[prices.length - 1] >= prevClose, lineC = pos ? up : dn;
  ctx.beginPath(); points.forEach((p, i) => i ? ctx.lineTo(X(i), Y(p.p)) : ctx.moveTo(X(i), Y(p.p)));
  ctx.strokeStyle = lineC; ctx.lineWidth = 1.8; ctx.stroke();
  ctx.lineTo(X(points.length - 1), padT + plotH); ctx.lineTo(X(0), padT + plotH); ctx.closePath();
  ctx.globalAlpha = .08; ctx.fillStyle = lineC; ctx.fill(); ctx.globalAlpha = 1;
  const tlabel = t => new Date(t * 1000).toLocaleTimeString("en", { hour: "2-digit", minute: "2-digit" });
  ctx.fillStyle = ink; ctx.globalAlpha = .55;
  [0, Math.floor(points.length / 2), points.length - 1].forEach(i => ctx.fillText(tlabel(points[i].t), Math.min(X(i), W - padR - 40), H - 6));
  ctx.globalAlpha = 1;
  canvas.onmousemove = e => {
    const rect = canvas.getBoundingClientRect();
    const i = Math.round((e.clientX - rect.left - padL) / (W - padL - padR) * (points.length - 1));
    if (i < 0 || i >= points.length) { tooltip.style.display = "none"; return; }
    const p = points[i], chg = (p.p / prevClose - 1) * 100;
    tooltip.style.display = "block"; tooltip.style.left = Math.min(e.clientX - rect.left + 12, W - 140) + "px"; tooltip.style.top = "8px";
    tooltip.innerHTML = `<b>${tlabel(p.t)}</b><br>${fmt(p.p)} <span class="${cls(chg)}">${sgn(chg.toFixed(2))}%</span>`;
  };
  canvas.onmouseleave = () => tooltip.style.display = "none";
}

/* ---------- pages ---------- */
function globalStrip(gl) {
  const inst = gl?.instruments || {};
  const order = ["BZ=F", "^GSPC", "^DJI", "^VIX", "GC=F", "BTC-USD", "ETH-USD", "PKR=X", "DX-Y.NYB"];
  const items = order.filter(s => inst[s]).map(s => {
    const v = inst[s];
    return `<div class="gitem" title="${esc(v.psx_read)}"><span>${esc(v.label)}</span>
      <b class="num">${fmt(v.price)}</b><i class="num ${cls(v.chg_1d_pct)}">${sgn(v.chg_1d_pct)}%</i></div>`;
  }).join("");
  // duplicate the item run so the marquee loops seamlessly (translateX -50% wraps clean)
  return items ? `<div class="gstrip clickable" onclick="location.hash='#/macro'"><div class="gtrack">${items}${items}</div></div>` : "";
}

async function pageBoard() {
  const [quant, pred, dash, news, pos, smap, trig, live, gl] = await Promise.all([
    j("quant.json"), j("predictability.json"), j("dashboard.json"), j("newslog.json"),
    j("positions.json"), j("strategy_map.json"), j("live_triggers.json"), j("live.json"), j("global.json")]);
  const q = quant?.tickers || {};
  const lv = live?.tickers || {};

  const sigs = dash?.signals || [];
  const sigBadge = s => s.audit === "PASS" ? '<span class="tag badge-ok up">audited ✓</span>'
    : '<span class="tag" title="Triggering now, proven on this stock\'s own history. Backtest-proven, not auditor-verified. Research, not advice.">backtest-proven</span>';
  const sigHtml = sigs.length ? sigs.map(s => `
    <div class="card clickable" onclick="location.hash='#/ticker/${esc(s.ticker)}'">
      <div class="tk-head"><span class="sym">${esc(s.ticker)}</span><span class="tag">${esc(s.template || "")}</span>
      ${sigBadge(s)}${s.confidence ? `<span class="pill ${s.confidence === "high" ? "ok" : ""}">${esc(s.confidence)}</span>` : ""}</div>
      <div class="statgrid num">
        <div class="stat"><span>entry</span><b>${s.entry}</b></div>
        <div class="stat"><span>stop</span><b class="dn">${s.stop}</b></div>
        <div class="stat"><span>target</span><b class="up">${s.target}</b></div>
        <div class="stat"><span>size</span><b>${s.size_shares ?? "—"} sh</b></div>
      </div><div class="sub" style="margin-top:8px">${esc(s.thesis || "")}</div></div>`).join("")
    : `<div class="card"><div class="empty">No setups triggering right now — the desk only flags a stock when a strategy proven on its own history fires. Patience is the edge.</div></div>`;

  const tg = trig?.triggers || [];
  const trigHtml = tg.length ? `<div class="card"><h2>Live triggers</h2><div class="sub">proven patterns firing now · unvetted</div>
    <table><thead><tr><th>Ticker</th><th>Template</th><th class="r">Price</th><th class="r">Hist</th><th class="r">When</th></tr></thead><tbody>${
      tg.map(t => `<tr class="clickable" onclick="location.hash='#/ticker/${esc(t.ticker)}'"><td><b>${esc(t.ticker)}</b></td><td>${esc(t.template)}</td>
      <td class="r num">${t.price}</td><td class="r num">${Math.round(t.backtest.hit_rate * 100)}%·n${t.backtest.n}</td><td class="r num">${t.ts}</td></tr>`).join("")}</tbody></table></div>` : "";

  const heat = Object.entries(q).sort((a, b) => b[1].ret_1d - a[1].ret_1d).map(([s, v]) => {
    const a = Math.min(Math.abs(v.ret_1d) / 5, 1) * 0.5;
    const col = v.ret_1d > 0.05 ? "var(--up)" : v.ret_1d < -0.05 ? "var(--dn)" : null;
    const bg = col ? `style="background:color-mix(in srgb, ${col} ${Math.round(a * 100)}%, transparent)"` : "";
    return `<div class="cell clickable" ${bg} onclick="location.hash='#/ticker/${s}'" title="RSI ${v.rsi14} · 20d ${sgn(v.ret_20d)}%">
      <b>${s}</b><span class="px num">${fmt(lv[s]?.current ?? v.close)}</span><span class="num ${cls(v.ret_1d)}">${sgn(v.ret_1d)}%</span></div>`;
  }).join("");

  const sm = Object.entries(smap?.tickers || {}).flatMap(([s, l]) => l.map(t => ({ s, ...t })))
    .sort((a, b) => b.net_expectancy_pct - a.net_expectancy_pct).slice(0, 12);
  const pt = Object.entries(pred?.tickers || {}).sort((a, b) => b[1].score - a[1].score).slice(0, 10);
  const nn = (news || []).slice(-10).reverse();
  const aw = dash?.agent_wire || [];
  const op = pos?.open || [];

  const posCard = `<div class="card"><h2>Positions</h2><div class="sub"></div>${op.length ? `<table><thead><tr><th>Ticker</th><th class="r">Entry</th><th class="r">Last</th><th class="r">P/L</th><th>Status</th></tr></thead><tbody>${
      op.map(p => `<tr class="clickable" onclick="location.hash='#/ticker/${esc(p.ticker)}'"><td><b>${esc(p.ticker)}</b></td><td class="r num">${p.entry}</td><td class="r num">${p.last_price ?? "—"}</td><td class="r num ${cls(p.unrealized_pct || 0)}">${p.unrealized_pct != null ? sgn(p.unrealized_pct) + "%" : "—"}</td><td>${esc(p.status || "HOLD")}</td></tr>`).join("")}</tbody></table>` : '<div class="empty">Flat — no open positions.</div>'}</div>`;
  const provenCard = `<div class="card"><h2>Proven strategies</h2><div class="sub">cleared backtest + out-of-sample bars · click through</div>
      <table><thead><tr><th>Ticker</th><th>Template</th><th class="r">Hit</th><th class="r">Net</th><th class="r">n</th></tr></thead><tbody>${
      sm.map(t => `<tr class="clickable" onclick="location.hash='#/ticker/${t.s}'"><td><b>${t.s}</b></td><td><span class="tag">${esc(t.template)}</span></td><td class="r num">${Math.round(t.hit_rate * 100)}%</td><td class="r num up">${sgn(t.net_expectancy_pct)}%</td><td class="r num">${t.n}</td></tr>`).join("")}</tbody></table></div>`;
  const universeCard = `<div class="card"><h2>Universe</h2><div class="sub">day move · click any name</div><div class="heat">${heat}</div></div>`;
  const predCard = `<div class="card"><h2>Predictability</h2><div class="sub"></div><table><thead><tr><th>Ticker</th><th class="r">Score</th><th class="r">RSI</th><th class="r">20d</th></tr></thead><tbody>${
      pt.map(([s, v]) => `<tr class="clickable" onclick="location.hash='#/ticker/${s}'"><td><b>${s}</b></td><td class="r num">${v.score}</td><td class="r num">${q[s]?.rsi14 ?? "—"}</td><td class="r num ${cls(q[s]?.ret_20d || 0)}">${q[s] ? sgn(q[s].ret_20d) + "%" : "—"}</td></tr>`).join("")}</tbody></table></div>`;
  const newsCard = `<div class="card"><h2>News wire</h2><div class="sub"><a href="#/news">full wire →</a></div><div class="wire">${
      nn.length ? nn.map(n => `<p><span class="tag">${n.impact ?? ""}</span> <span class="t">${esc((n.ts || "").slice(5, 16))}</span><b>${(n.tickers || []).join(", ")}</b> ${esc(n.headline || n.summary || "")}</p>`).join("") : '<div class="empty">Wire silent.</div>'}</div></div>`;
  const agentCard = `<div class="card"><h2>Agent wire</h2><div class="sub">this cycle</div><div class="wire">${
      aw.length ? aw.map(a => `<p><b style="color:var(--accent)">${esc(a.agent)}</b> ${esc(a.summary)}</p>`).join("") : '<div class="empty">No cycle run yet.</div>'}</div></div>`;

  $("view").innerHTML = `${globalStrip(gl)}<div class="grid-board">
    <div class="cards">${sigHtml}${trigHtml}${posCard}</div>
    <div class="cards">${universeCard}${predCard}${provenCard}</div>
    <div class="cards">${newsCard}${agentCard}</div>
  </div>`;
}

async function pageValue() {
  const [fv, uni] = await Promise.all([j("fairvalue.json"), j("universe.json")]);
  const t = fv?.tickers || {};
  const rows = Object.entries(t).map(([s, v]) => ({ s, ...v, name: uni?.symbols?.[s]?.name || "" }))
    .sort((a, b) => b.mispricing_pct - a.mispricing_pct);
  const under = rows.filter(r => r.verdict === "undervalued");
  const over = rows.filter(r => r.verdict === "overvalued").reverse();
  const METHODS = { relative_pe: "Peer P/E", earnings_power: "Earnings power", graham: "Graham (revised)", ddm: "Dividend discount" };
  const fvDetail = (r) => {
    const m = r.methods || {};
    const used = Object.entries(METHODS).filter(([k]) => m[k] != null);
    const cells = used.map(([k, lbl]) => {
      const val = m[k], pct = r.price ? Math.round((val / r.price - 1) * 1000) / 10 : 0;
      return `<div class="fvm"><span>${lbl}</span><b class="num">${fmt(val)}</b><i class="num ${cls(pct)}">${sgn(pct)}%</i></div>`;
    }).join("");
    const vals = used.map(([k]) => fmt(m[k])).join(", ");
    const dir = r.verdict === "undervalued" ? "below" : "above";
    const mag = Math.abs(r.mispricing_pct);
    return `<div class="fvwork">
      <div class="fvhdr">How the fair value was built — four independent models, price vs each:</div>
      <div class="fvmethods">${cells}</div>
      <div class="fvline"><span>composite fair</span> median(${vals}) = <b class="num">Rs ${fmt(r.composite_fair)}</b></div>
      <div class="fvline"><span>inputs</span> EPS Rs ${fmt(r.eps)} · trailing P/E ${r.pe}× · growth est ${r.growth_est_pct}%</div>
      <p class="fvnote">${r.s} trades at <b class="num">Rs ${fmt(r.price)}</b> against a composite fair of <b class="num">Rs ${fmt(r.composite_fair)}</b> — about <b>${mag}% ${dir}</b> the model's blended fair value. The composite is the <b>median</b> of the four models above (median resists any single model blowing out). Model estimate on public fundamentals — research, not a price target or recommendation. <a href="#/ticker/${r.s}">full page →</a></p>
    </div>`;
  };
  const tbl = (list, cheap) => `<table><thead><tr><th>Ticker</th><th class="r">Price</th><th class="r">Fair value</th><th class="r">${cheap ? "Upside" : "Downside"}</th><th>Verdict</th></tr></thead><tbody>${
    list.map(r => `<tr class="clickable fvrow" onclick="this.classList.toggle('exp');this.nextElementSibling.classList.toggle('open')"><td><b>${r.s}</b> <span class="sub">${esc((r.name || "").slice(0, 22))}</span></td>
      <td class="r num">${fmt(r.price)}</td><td class="r num">${fmt(r.composite_fair)}</td>
      <td class="r num ${cls(r.mispricing_pct)}">${sgn(r.mispricing_pct)}%</td>
      <td><span class="pill ${r.verdict === "undervalued" ? "ok" : "bad"}">${r.verdict === "undervalued" ? "below fair" : r.verdict === "overvalued" ? "above fair" : esc(r.verdict)}</span> <span class="fvcaret">▸</span></td></tr>
      <tr class="fvdetail"><td colspan="5">${fvDetail(r)}</td></tr>`).join("")}</tbody></table>`;
  // glance row: the four numbers that answer "what does the screen say" before any prose
  const sTile = (label, val, sub, k) => `<div class="sumtile"><span class="sk">${label}</span><b class="${k || ""}">${val}</b>${sub ? `<i>${sub}</i>` : ""}</div>`;
  const fair = rows.filter(r => r.verdict === "fair");
  const widest = under[0];
  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Value screen — price vs model fair value</h2><div class="ln"></div><span class="pill">${rows.length} valued</span></div>
  <div class="sumstrip s4">
    ${sTile("Below fair value", under.length, `of ${rows.length} valued`, under.length ? "up" : "")}
    ${sTile("Above fair value", over.length, `of ${rows.length} valued`, over.length ? "dn" : "")}
    ${sTile("Near fair", fair.length, "within the model's band", "")}
    ${sTile("Widest gap", widest ? widest.s : "—", widest ? `${sgn(widest.mispricing_pct)}% vs fair` : "—", widest ? "up" : "")}
  </div>
  <div class="disclaimer">Model estimates on public fundamentals for <b>research and education</b> — not price targets, not advice, not a signal to buy or sell. A price below model fair value is not a recommendation, and a low share price never means a company is cheap. Past performance does not guarantee future results.</div>
  <details class="how"><summary><b>How the model works</b><span class="sub">four models, median wins</span><span class="dict-arrow">▾</span></summary>
    <p>Each stock is valued four ways (peer P/E, earnings-power vs bond yield, Graham, dividend discount); the median is its <b>model fair value</b> — the median resists any single model blowing out. Market median P/E ${fv?.inputs?.market_median_pe ?? "—"}, bond yield ${fv?.inputs?.bond_yield_pct ?? "—"}%. Click any row below to expand its full four-model working.</p>
  </details>
  <div class="seg"><h2 style="color:var(--up)">Priced below model fair value</h2><div class="ln"></div><span class="pill ok">${under.length}</span></div>
  <div class="card">${under.length ? tbl(isSubscribed() ? under : under.slice(0, 3), true) : '<div class="empty">none below model fair value right now</div>'}</div>
  ${isSubscribed() ? `
  <div class="seg"><h2 style="color:var(--dn)">Priced above model fair value</h2><div class="ln"></div><span class="pill bad">${over.length}</span></div>
  <div class="card">${over.length ? tbl(over, false) : '<div class="empty">none above model fair value right now</div>'}</div>`
    : planWall("The full value screen",
      `${rows.length} names valued four independent ways — all ${under.length} priced below model fair value, the ${over.length} priced above it, and every stock's full four-model working.`)}`;
}

/* What actually moves each sector — measured, not assumed. Rendered from sector_macro.json, which
   regresses 19 years of sector returns on the global tape with the same permutation machinery the
   astro test used. That symmetry IS the point: the same bar that found nothing in the sky finds
   oil in the E&P names. */
const FACTOR_LABEL = {
  oil: "oil (WTI)", gold: "gold", usdpkr: "USD/PKR", sp500: "S&P 500",
  em_equity: "EM equity flows", us10y: "US 10y yield", dollar: "dollar index",
};
const FACTOR_PLAIN = {
  oil: "crude", gold: "gold", usdpkr: "a weaker rupee", sp500: "Wall Street's last close",
  em_equity: "money moving into emerging markets", us10y: "the US cost of money",
  dollar: "a stronger dollar",
};
function sectorDriverLine(sm, sector) {
  const rec = sm?.by_sector?.[sector];
  if (!rec) return "";
  const demo = (rec.drivers || []).filter(d => d.demonstrated);
  if (!demo.length) {
    return `<span class="sub">No global factor has a demonstrated effect on ${esc(sector)} — over 19 years its days have been made locally, not on the world tape.</span>`;
  }
  const d = demo[0];
  const dir = d.corr > 0 ? "rises with" : "falls when";
  return `<span class="sub"><b>${esc(sector)}</b> ${dir} <b>${esc(FACTOR_PLAIN[d.factor] || d.factor)}</b>${d.corr > 0 ? "" : " rises"}${demo.length > 1 ? `, and also tracks ${demo.slice(1, 3).map(x => esc(FACTOR_PLAIN[x.factor] || x.factor)).join(" and ")}` : ""} — measured over 19 years, correction-survived. Even so, the whole global tape explains only <b>${rec.joint_r2_pct ?? "—"}%</b> of this sector's daily moves.</span>`;
}

async function pageMacro() {
  const [gl, macro, geo, sm] = await Promise.all([
    j("global.json"), j("macro.json"), j("georisk.json"), j("sector_macro.json")]);
  const inst = gl?.instruments || {};
  const groups = {
    energy: "Energy — oil drives Pakistan's import bill, PKR & inflation",
    risk: "Global risk appetite — frontier flows follow",
    safe_haven: "Safe haven",
    crypto: "Crypto — global liquidity / retail risk barometer",
    fx: "Currency — the biggest macro lever for PSX",
  };
  const card = (gk, title) => {
    const rows = Object.entries(inst).filter(([, v]) => v.group === gk);
    if (!rows.length) return "";
    return `<div class="card"><h2>${esc(title)}</h2><table><thead><tr><th>Instrument</th><th class="r">Price</th><th class="r">1d</th><th class="r">1mo</th><th>PSX read-through</th></tr></thead><tbody>${
      rows.map(([s, v]) => `<tr><td><b>${esc(v.label)}</b></td><td class="r num">${fmt(v.price)}</td>
        <td class="r num ${cls(v.chg_1d_pct)}">${sgn(v.chg_1d_pct)}%</td>
        <td class="r num ${cls(v.chg_1mo_pct)}">${sgn(v.chg_1mo_pct)}%</td>
        <td class="sub" style="max-width:340px">${esc(v.psx_read)}${v.stale ? ' <span class="tag">stale</span>' : ""}</td></tr>`).join("")}</tbody></table></div>`;
  };

  const m = macro || {};
  const dom = m.domestic || {};
  const drivers = m.drivers || [];
  const macroCard = `<div class="card"><h2>Pakistan macro</h2>
    <div class="sub">regime <b>${esc((m.regime || "—").toUpperCase())}</b> · ${esc(m.global_read || "")} · updated ${esc(m.updated || "—")} ${m.updated ? "" : "(run macro-agent to populate)"}</div>
    ${(() => {
      const facts = [
        ["SBP policy rate", m.sbp_rate],
        ["CPI YoY", m.cpi_yoy],
        ["FX reserves", m.reserves_usd_bn ? "$" + m.reserves_usd_bn + "bn" : null],
        ["6m T-bill", dom.tbill_6m],
        ["10y PIB", dom.pib_10y],
        ["Remittances", dom.remittances],
        ["USD/PKR", m.pkr_usd],
      ];
      const have = facts.filter(([, v]) => v != null && v !== "");
      const missing = facts.filter(([, v]) => v == null || v === "").map(([k]) => k);
      return `<div class="facts">${have.map(([k, v]) => `<div class="fact"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("")}</div>
      ${missing.length ? `<p class="sub" style="margin-top:8px;font-size:10.5px">Pending this cycle: ${missing.join(", ")} — the macro-agent fills these from SBP/PBS primary sources on the next full run.</p>` : ""}`;
    })()}
    ${dom.debt_note ? `<p class="sub" style="margin-top:10px"><b>Debt/borrowing:</b> ${esc(dom.debt_note)}</p>` : ""}
    ${drivers.length ? `<div class="sub" style="margin-top:10px"><b>Drivers:</b><ul style="margin:6px 0 0 16px">${drivers.map(d => `<li>${esc(d)}</li>`).join("")}</ul></div>` : ""}
    ${(m.next_events || []).length ? `<p class="sub" style="margin-top:8px"><b>Next:</b> ${m.next_events.map(e => `${esc(e.date)} ${esc(e.event)}`).join(" · ")}</p>` : ""}
    ${(m.sector_tilt) ? `<p class="sub" style="margin-top:8px"><b class="up">Favored:</b> ${(m.sector_tilt.favored || []).join(", ") || "—"} · <b class="dn">Avoid:</b> ${(m.sector_tilt.avoid || []).join(", ") || "—"}</p>` : ""}</div>`;

  // geo-risk radar (worldmonitor-style, from free signals)
  const geoCard = geo ? (() => {
    const band = geo.band, col = band === "elevated" ? "var(--dn)" : band === "calm" ? "var(--up)" : "var(--accent)";
    const bar = s => `<div style="height:6px;border-radius:0;background:var(--line2);overflow:hidden"><div style="height:100%;width:${s}%;background:${s >= 65 ? "var(--dn)" : s <= 40 ? "var(--up)" : "var(--accent)"};transform-origin:left"></div></div>`;
    return `<div class="card"><div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:6px">
      <h2>Geopolitical & risk radar</h2>
      <span class="pill" style="background:color-mix(in srgb,${col} 15%,transparent);color:${col}">${geo.score}/100 · ${esc(band)}</span></div>
      <div class="sub" style="color:var(--ink2);margin-bottom:14px">${esc(geo.read)} <span style="opacity:.7">· ${esc(geo.source)}</span></div>
      <table><tbody>${geo.factors.map(f => `<tr>
        <td style="width:150px"><b>${esc(f.factor)}</b></td>
        <td class="num" style="width:150px">${esc(f.value)}</td>
        <td style="width:90px" class="r num">${f.stress}</td>
        <td style="min-width:110px">${bar(f.stress)}</td>
        <td class="sub" style="color:var(--ink2)">${esc(f.read)}</td></tr>`).join("")}</tbody></table>
      ${geo.sector_pressure?.length ? `<p class="sub" style="margin-top:12px"><b>Sector read-through:</b> ${geo.sector_pressure.map(esc).join(" · ")}</p>` : ""}
      ${geo.upgrade_note ? `<p class="sub" style="margin-top:8px;opacity:.7">${esc(geo.upgrade_note)}</p>` : ""}</div>`;
  })() : "";

  // glance row: the regime and the three prices that actually move PSX, before any prose
  const sTile = (label, val, sub, k) => `<div class="sumtile"><span class="sk">${label}</span><b class="${k || ""}">${val}</b>${sub ? `<i>${sub}</i>` : ""}</div>`;
  const iTile = (label, code, why) => { const v = inst[code];
    return sTile(label, v ? fmt(v.price) : "—", v ? `${sgn(v.chg_1d_pct)}% today · ${why}` : why, v ? cls(v.chg_1d_pct) : ""); };
  // the feed writes "risk-off"; don't assume a separator — strip everything but letters
  const regime = (m.regime || "").toLowerCase().replace(/[^a-z]/g, "");
  const glanceRow = `<div class="sumstrip s4">
    ${sTile("Macro regime", (m.regime || "—").toUpperCase(), m.updated ? `desk read · ${esc(m.updated)}` : "run macro-agent to populate", regime === "riskon" ? "up" : regime === "riskoff" ? "dn" : "")}
    ${iTile("USD/PKR", "PKR=X", "the biggest lever")}
    ${iTile("Brent crude", "BZ=F", "the import bill")}
    ${geo ? sTile("Geo risk", `${geo.score}/100`, esc(geo.band || ""), geo.band === "elevated" ? "dn" : geo.band === "calm" ? "up" : "") : iTile("Global risk", "^GSPC", "frontier flows follow")}
  </div>`;

  // ---- what ACTUALLY moves each sector, measured over 19 years
  const smCard = (() => {
    if (!sm?.by_sector) return "";
    const h = sm.headline || {};
    const rows = Object.entries(sm.by_sector)
      .sort((a, b) => (b[1].joint_r2_pct ?? 0) - (a[1].joint_r2_pct ?? 0))
      .map(([sec, rec]) => {
        const demo = (rec.drivers || []).filter(d => d.demonstrated);
        const chips = demo.length
          ? demo.slice(0, 3).map(d => `<span class="mf-chip ${d.corr > 0 ? "up" : "dn"}" title="correlation ${d.corr}, p=${d.p_value}">${esc(FACTOR_LABEL[d.factor] || d.factor)} ${d.corr > 0 ? "↑" : "↓"}</span>`).join("")
          : `<span class="sub" style="opacity:.7">nothing beat chance</span>`;
        return `<tr><td><b>${esc(sec)}</b></td><td>${chips}</td>
          <td class="r num">${rec.joint_r2_pct != null ? rec.joint_r2_pct + "%" : "—"}</td></tr>`;
      }).join("");
    return `<div class="seg"><h2>What actually moves each sector</h2><div class="ln"></div><span class="pill ok">${h.survivors_bonferroni} of ${h.hypotheses_tested} measured</span></div>
    <div class="card" style="padding:0"><table><thead><tr><th>Sector</th><th>Demonstrated drivers</th><th class="r">Global tape explains</th></tr></thead><tbody>${rows}</tbody></table></div>
    <p class="sub" style="margin-top:8px">Nineteen years of daily returns regressed on the global tape — oil, gold, USD/PKR, the S&amp;P, EM flows, the US 10y, the dollar — each lagged one PSX day, because those markets close after Karachi does. Same permutation test and same correction the desk used on <a href="#/astro" style="color:var(--accent)">astrology</a>, which found nothing: here it finds <b>${h.survivors_bonferroni}</b> real relationships. That contrast is the point.</p>
    <p class="sub" style="margin-top:6px"><b>Read the last column before the second.</b> Even for the most globally-driven sector, the entire world tape explains only a few percent of a day's move — PSX is mostly made at home. A demonstrated driver says what <i>has tended</i> to move a sector, never what will.</p>`;
  })();

  $("view").innerHTML = `
    <div class="seg" style="margin-top:4px"><h2>What moves PSX</h2><div class="ln"></div></div>
    ${glanceRow}
    <p class="sub" style="margin-bottom:14px">Global markets refreshed every cycle (Yahoo Finance). Pakistan-domestic numbers verified by the macro-agent from primary sources. Hover any read-through for why it matters.</p>
    ${smCard}
    ${geoCard}
    ${macroCard}
    ${card("fx", groups.fx)}
    ${card("energy", groups.energy)}
    ${card("risk", groups.risk)}
    ${card("crypto", groups.crypto)}
    ${card("safe_haven", groups.safe_haven)}`;
}

async function pageToday() {
  const [dr, gl, quant, live, uni] = await Promise.all([j("daily_read.json"), j("global.json"), j("quant.json"), j("live.json"), j("universe.json")]);
  if (!dr) { $("view").innerHTML = `<div class="seg" style="margin-top:4px"><h2>Daily read</h2><div class="ln"></div></div><div class="card"><div class="empty">The daily read is written by the market-analyst agent in the pre-market cycle. Run a full cycle to generate today's note.</div></div>`; return; }
  const toneClass = { constructive: "ok", defensive: "bad", cautious: "bad" }[dr.tone] || "";
  const stanceTag = s => `<span class="pill ${s === "favoured" ? "ok" : s === "avoid" ? "bad" : ""}">${esc(s)}</span>`;
  const q = quant?.tickers || {}, lv = live?.tickers || {};

  // ---- personal layer: your watchlist surfaces first (same desk read for everyone) ----
  const wl = (typeof watchlist === "function" ? watchlist() : []).filter(s => q[s]);
  const myWatch = (me && wl.length) ? `
  <div class="seg" style="margin-top:4px"><h2>On your watchlist</h2><div class="ln"></div><span class="pill ok">${wl.length}</span></div>
  <div class="card" style="padding:0"><table class="wl-mini"><tbody>${wl.map(s => {
    const qq = q[s], px = lv[s]?.current ?? qq.close;
    return `<tr class="clickable" onclick="location.hash='#/ticker/${s}'"><td><b>${s}</b> <span class="sub">${esc((uni?.symbols?.[s]?.name || "").slice(0, 24))}</span></td><td class="r num">${fmt(px)}</td><td class="r num ${cls(qq.ret_1d)}">${sgn(qq.ret_1d)}%</td></tr>`;
  }).join("")}</tbody></table></div>` : "";

  // radar names: the ones you watch float to the top, badged
  const iw = typeof isWatched === "function" ? isWatched : () => false;
  const radar = (dr.watchlist || []).slice().sort((a, b) => (iw(b.ticker) ? 1 : 0) - (iw(a.ticker) ? 1 : 0));

  // glance row: the day in four hard items, before the read
  const sTile = (label, val, sub, k) => `<div class="sumtile"><span class="sk">${label}</span><b class="${k || ""}">${val}</b>${sub ? `<i>${sub}</i>` : ""}</div>`;
  const fav = (dr.sectors || []).filter(s => s.stance === "favoured"), avoid = (dr.sectors || []).filter(s => s.stance === "avoid");
  const nextCat = (dr.catalysts || [])[0];
  const glanceRow = `<div class="sumstrip s4">
    ${sTile("The desk's tone", (dr.tone || "—").toUpperCase(), esc(dr.date || ""), toneClass === "ok" ? "up" : toneClass === "bad" ? "dn" : "")}
    ${sTile("Favoured", fav.length ? esc(fav.map(s => s.name).slice(0, 2).join(", ")) : "none", fav.length > 2 ? `+${fav.length - 2} more sectors` : "sectors", fav.length ? "up" : "")}
    ${sTile("Avoiding", avoid.length ? esc(avoid.map(s => s.name).slice(0, 2).join(", ")) : "none", avoid.length > 2 ? `+${avoid.length - 2} more sectors` : "sectors", avoid.length ? "dn" : "")}
    ${sTile("Next catalyst", nextCat ? esc(nextCat.date) : "—", nextCat ? esc(String(nextCat.event).slice(0, 34)) : "none dated", "")}
  </div>`;

  // the astro hook, surfaced where visitors actually land. Only for those without a chart yet —
  // once cast, it's replaced by their own reading in the sidebar, so this never nags.
  const astroTease = natalChart() ? "" : `
  <div class="card mc-tease" onclick="location.hash='#/cast'">
    <div class="mc-tease-glyphs">${["Sun", "Moon", "Jupiter", "Saturn"].map(b => pixelGlyph(b, 22)).join("")}</div>
    <div class="mc-tease-txt">
      <b>Read the whole exchange against your birth chart</b>
      <span class="sub">Vedic astrology has always matched two charts. The desk turns that on the market — cast yours free, in your browser, in about a minute.</span>
    </div>
    <span class="mc-tease-go">Cast my chart →</span>
  </div>`;

  $("view").innerHTML = `
  ${globalStrip(gl)}
  ${glanceRow}
  ${astroTease}
  ${myWatch}
  <div class="card">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px"><span class="pill ${toneClass}">${esc((dr.tone || "").toUpperCase())}</span><span class="sub">${esc(dr.date || "")}</span></div>
    <h2 style="font-size:22px;line-height:1.3;margin-bottom:12px">${esc(dr.headline || "")}</h2>
    <p style="font-size:14.5px;line-height:1.65;color:var(--ink2)">${esc(dr.summary || "")}</p>
  </div>
  <div class="two-col">
    <div class="card"><h2>Sectors to watch</h2><div class="sub"></div>
      <table><tbody>${(dr.sectors || []).map(s => `<tr><td><b>${esc(s.name)}</b></td><td>${stanceTag(s.stance)}</td><td class="sub" style="color:var(--ink2)">${esc(s.why)}</td></tr>`).join("") || '<tr><td class="empty">—</td></tr>'}</tbody></table></div>
    <div class="card"><h2>Key risks</h2><div class="sub">what would spoil the read</div>
      <ul style="margin:6px 0 0 16px;line-height:1.7">${(dr.risks || []).map(r => `<li>${esc(r)}</li>`).join("") || "<li class='sub'>none flagged</li>"}</ul>
      ${(dr.catalysts || []).length ? `<div class="sub" style="margin-top:12px"><b>Catalysts:</b> ${dr.catalysts.map(c => `${esc(c.date)} ${esc(c.event)}`).join(" · ")}</div>` : ""}</div>
  </div>
  <div class="seg"><h2>Names on the desk's radar</h2><div class="ln"></div></div>
  ${radar.length ? `<div class="card" style="padding:0"><table><thead><tr><th>Ticker</th><th>The desk's angle</th><th>Key risk</th></tr></thead><tbody>${
    radar.map(w => `<tr class="clickable" onclick="location.hash='#/ticker/${esc(w.ticker)}'">
      <td style="white-space:nowrap"><b>${esc(w.ticker)}</b>${iw(w.ticker) ? ' <span class="wbadge">★ yours</span>' : ""}</td>
      <td class="sub" style="color:var(--ink2)">${esc(w.angle)}</td>
      <td class="sub"><b class="dn">Risk:</b> ${esc(w.risk)}</td></tr>`).join("")}</tbody></table></div>`
      : '<div class="card"><div class="empty">Patient today — nothing stacks up strongly enough to flag.</div></div>'}
  <p class="sub" style="margin-top:14px">${esc(dr.disclaimer || "Research, not advice.")}</p>`;
}

async function pageStrategies() {
  const [bt, smap, lib, uni] = await Promise.all([
    j("backtests.json"), j("strategy_map.json"), j("strategy_library.json"), j("universe.json")]);
  const tpls = bt?.templates || {};
  let rows;
  if (Object.keys(tpls).length) {
    // full roll-up from backtests: proven count + tested count + stocks
    rows = Object.entries(tpls).map(([id, per]) => {
      const all = Object.values(per);
      const elig = all.filter(t => t.eligible);
      const avgNet = elig.length ? elig.reduce((a, t) => a + t.net_expectancy_pct, 0) / elig.length : null;
      return { id, name: all[0]?.name || id, cat: all[0]?.category || "", tested: all.length,
        proven: elig.length, avgNet, provenOn: Object.entries(per).filter(([, t]) => t.eligible).map(([s]) => s) };
    });
  } else {
    // bundled/snapshot fallback: derive from strategy_map (per-ticker proven lists)
    const agg = {};
    Object.entries(smap?.tickers || {}).forEach(([sym, list]) => list.forEach(p => {
      const a = agg[p.id] || (agg[p.id] = { id: p.id, name: p.name, cat: p.category, nets: [], provenOn: [] });
      a.nets.push(p.net_expectancy_pct); a.provenOn.push(sym);
    }));
    rows = Object.values(agg).map(a => ({ id: a.id, name: a.name, cat: a.cat, tested: null,
      proven: a.provenOn.length, avgNet: a.nets.reduce((x, y) => x + y, 0) / a.nets.length, provenOn: a.provenOn }));
  }
  rows.sort((a, b) => b.proven - a.proven);
  const byCat = {};
  rows.forEach(r => (byCat[r.cat] = byCat[r.cat] || []).push(r));
  const descs = {};
  (lib?.strategies || []).forEach(s => { descs[s.id] = s; });

  const names = uni?.symbols || {};
  const nStrat = bt?.n_strategies || rows.length || 52;
  const provenPairs = Object.values(smap?.tickers || {}).reduce((a, l) => a + l.length, 0);
  const nCovered = Object.keys(smap?.tickers || {}).length;
  const sTile = (label, val, sub, k) => `<div class="sumtile"><span class="sk">${label}</span><b class="${k || ""}">${val}</b>${sub ? `<i>${sub}</i>` : ""}</div>`;

  // ---- your board: pick stocks, run the whole library across them ----
  // Nothing is revealed on adding — a stock sits "waiting for a run" until the library
  // actually runs on it. The work has to be seen to be worth anything.
  const board = stratBoard();
  const pending = board.filter(s => !stratRunOn(s));
  const anyRan = board.some(stratRunOn);
  const provenCount = s => (smap?.tickers?.[s] || []).length;
  const tiles = board.map(s => { const ranS = stratRunOn(s);
    return `<div class="sb-tile clickable" onclick="if(!event.target.closest('.sb-x'))location.hash='#/ticker/${esc(s)}'">
      <button class="sb-x" data-sbdel="${esc(s)}" title="Remove ${esc(s)} from the board" aria-label="remove ${esc(s)}">✕</button>
      <b>${esc(s)}</b><span class="sb-nm">${esc((names[s]?.name || "").slice(0, 24))}</span>
      <span class="pill ${ranS && provenCount(s) ? "ok" : ranS ? "" : "wait"}">${ranS ? provenCount(s) + " of " + nStrat + " proven" : "waiting for a run"}</span>
    </div>`; }).join("");
  const addTile = `<div class="sb-tile sb-add">
      <span class="sk">Add a stock</span>
      <input id="sb-tkr" class="ph-in combo" placeholder="e.g. FFC" autocomplete="off" onkeydown="if(event.key==='Enter'&&!document.querySelector('.combo-opt.on'))addBoardTicker()">
      <button class="note-save" onclick="addBoardTicker()">Add to board</button>
    </div>`;

  const runBar = pending.length ? `<button class="run-desk run-strat" onclick="playBoardRun()">
    <span class="run-ico">▶</span>
    <span class="run-txt"><b>Run the strategy library on ${anyRan ? `your ${pending.length} new stock${pending.length > 1 ? "s" : ""}` : `your ${board.length} stock${board.length > 1 ? "s" : ""}`}</b><i>Backtests all ${nStrat} of the desk's strategies across ${pending.length === 1 ? "its" : "each stock's"} ~19-year history — costs included, out-of-sample checked — then ranks every stock–strategy pair that survived.</i></span>
    <span class="run-meta">${bt?.updated ? `<span class="run-last">Library updated · ${esc(String(bt.updated).slice(0, 10))}</span>` : ""}<span class="run-go">Run ›</span></span>
  </button>` : board.length ? `<button class="run-desk run-strat ran" onclick="playBoardRun()">
    <span class="run-ico">▶</span>
    <span class="run-txt"><b>Run the strategy library again on your ${board.length} stock${board.length > 1 ? "s" : ""}</b><i>The desk re-backtests all ${nStrat} strategies across every stock on your board and re-ranks what survives. Worth re-running as the library and the price history move on.</i></span>
    <span class="run-meta">${bt?.updated ? `<span class="run-last">Library updated · ${esc(String(bt.updated).slice(0, 10))}</span>` : ""}<span class="run-go">Run again ›</span></span>
  </button>` : "";

  // ---- results: per board stock. A stock shows NOTHING until the library has actually run on it. ----
  const results = !board.length ? "" : board.map(s => {
    const list = smap?.tickers?.[s] || [];
    const head = `<div class="sb-res-head clickable" onclick="location.hash='#/ticker/${esc(s)}'"><b>${esc(s)}</b><span class="sub">${esc((names[s]?.name || "").slice(0, 30))}</span><span class="pill ${stratRunOn(s) ? (list.length ? "ok" : "") : "wait"}">${stratRunOn(s) ? list.length + " proven" : "not run yet"}</span></div>`;
    if (!stratRunOn(s)) return `<div class="card" style="padding:0">${head}
      <div class="empty" style="padding:14px 17px">The desk hasn't run the library on <b>${esc(s)}</b> yet — hit <b>Run ›</b> above and it backtests all ${nStrat} strategies across ${esc(s)}'s own ~19 years of price history, then shows what actually held up right here.</div></div>`;
    return `<div class="card" style="padding:0">${head}
      ${list.length ? `<table><thead><tr><th>Strategy</th><th class="r">Win rate</th><th class="r">Avg net/trade</th><th class="r">Trades</th><th class="r">Out-of-sample</th></tr></thead><tbody>${
        list.map(t => `<tr><td><b>${esc(t.name)}</b> <span class="tag">${esc((t.category || "").replace(/_/g, " "))}</span></td>
          <td class="r num">${Math.round(t.hit_rate * 100)}%</td><td class="r num up">${sgn(t.net_expectancy_pct)}%</td>
          <td class="r num">${t.n}</td><td class="r num">${t.oos_hit != null ? Math.round(t.oos_hit * 100) + "% · n" + t.oos_n : "—"}</td></tr>`).join("")}</tbody></table>`
        : `<div class="empty" style="padding:14px 17px">No strategy cleared the bar on ${esc(s)} — none held win rate ≥55%, positive expectancy after costs, AND out-of-sample. The desk wouldn't signal it. That's a finding, not a gap.</div>`}</div>`;
  }).join("");

  // ---- the dictionary: every strategy the desk runs, in plain English ----
  const dict = `<details class="dict"><summary><b>What's in the library</b><span class="sub">every strategy the desk runs, and how each one works</span><span class="dict-arrow">▾</span></summary>
    ${Object.entries(byCat).map(([cat, list]) => `<div class="dict-cat">${esc((cat || "other").replace(/_/g, " "))}</div>
      ${list.map(r => { const d = descs[r.id] || {};
        return `<div class="dict-row"><div><b>${esc(r.name)}</b>${d.target_pct != null ? `<span class="dict-meta">target +${d.target_pct}% · stop −${d.stop_pct}% · max ${d.hold} sessions</span>` : ""}</div>
        <p>${esc(d.description || "")}</p>
        <span class="dict-proven ${r.proven ? "" : "none"}">${r.proven ? `proven on ${r.proven} stock${r.proven === 1 ? "" : "s"}` : "hasn't cleared the bar anywhere yet"}</span></div>`; }).join("")}`).join("")}
  </details>`;

  // ---- request a strategy (signed-in; stored in the desk's request queue) ----
  const reqForm = `<div class="seg"><h2>Request a strategy</h2><div class="ln"></div><span class="pill">the desk tests it</span></div>
  <div class="card">
    <p class="sub" style="margin-bottom:12px">Trade by a rule set that isn't in the library? Explain it below — the desk codes it, backtests it on ~19 years of history the same way, and if it clears the bar it joins the library.</p>
    ${me ? `<div class="rq-form">
      <div class="ph-row"><input id="rq-title" class="ph-in" placeholder="Name it (e.g. Monday gap fade)" maxlength="80">
      <input id="rq-tkr" class="ph-in combo" style="flex:0 1 150px" placeholder="Ticker (optional)" autocomplete="off"></div>
      <textarea id="rq-desc" class="tknote" style="min-height:88px" placeholder="Explain the rules in plain English: when it buys, when it exits, any filters (volume, trend, day of week…)."></textarea>
      <div class="tknote-bar"><button class="note-save" onclick="submitStratRequest()">Send to the desk</button><span id="rq-msg" class="sub"></span></div></div>`
    : `<div class="empty">Sign in to send the desk a strategy to test.<br><br><button class="auth-go" style="max-width:220px" onclick="openAuth('signup')">Create a free account</button></div>`}
  </div>`;

  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Strategies</h2><div class="ln"></div><span class="pill">${nStrat} strategies</span></div>
  <p class="sub" style="margin-bottom:14px">Every strategy is a transparent rule set backtested on each stock's own ~19-year history — it only counts on a stock where it cleared the bar (win rate ≥55%, positive expectancy after costs, still profitable out-of-sample). Research, not advice.</p>
  <div class="sumstrip s4">
    ${sTile("Strategies", nStrat, "transparent rule sets", "")}
    ${sTile("Proven pairs", provenPairs, "strategy × stock, after costs + OOS", provenPairs ? "up" : "")}
    ${sTile("Stocks with a proven edge", nCovered, "across the universe", "")}
    ${sTile("Library updated", bt?.updated ? String(bt.updated).slice(0, 10) : "—", "full re-backtest", "")}
  </div>

  <div class="seg"><h2>Your board</h2><div class="ln"></div><span class="pill">${board.length ? board.length + " stock" + (board.length > 1 ? "s" : "") : "empty"}</span></div>
  <div class="card">
    <div class="sb-grid">${tiles}${addTile}</div>
    <span id="sb-msg" class="sub" style="display:block;margin-top:8px"></span>
    ${!me && board.length ? `<span class="sub" style="display:block;margin-top:4px">Your board lives in this session only — <a style="color:var(--accent);cursor:pointer" onclick="openAuth('signup')">sign in</a> to keep it.</span>` : ""}
  </div>
  ${isSubscribed() ? runBar + results
    : planWall("Run the desk on your board",
      "Pick your stocks above, then run every strategy in the library on each — ~19 years of that stock's own history per rule, win rate, expectancy after costs and out-of-sample honesty, revealed live. The rule sets below are open; running them is the desk's work.")}

  <div class="seg"><h2>The library</h2><div class="ln"></div></div>
  ${dict}
  ${reqForm}`;
}

/* ==========================================================================================
   PERSONAL ASTRO — a user casts their own birth chart in the browser, and the tradition reads it
   against every PSX chart. This is a financial-astrology EXPLORATION, not investment advice: it
   speaks in "the tradition reads / your chart resonates", never "buy" or "this will be profitable".
   The desk's own tests found astro has no measurable edge on PSX (published on /astro); this feature
   is the engaging, honest interpretation layer, and its calls are scored in public like any other.
   ========================================================================================== */
const D2R = Math.PI / 180, R2D = 180 / Math.PI;
const NAK = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya",
  "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
  "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
  "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"];
const SIGN12 = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
  "Sagittarius", "Capricorn", "Aquarius", "Pisces"];
const NEPH_BODIES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"];

let _ephem = null;
async function loadEphem() {
  if (_ephem) return _ephem;
  const hdr = await j("natal_ephem.json");
  const buf = await fetch(DATA_BASE + "natal_ephem.bin?t=" + Date.now()).then(r => r.ok ? r.arrayBuffer() : Promise.reject(new Error("ephem HTTP " + r.status)));
  _ephem = { hdr, dv: new DataView(buf), start: Date.UTC(...hdr.start.split("-").map((x, i) => i === 1 ? +x - 1 : +x)) };
  return _ephem;
}
function _lahiri(jd) { return 23.853 + 0.0139686 * ((jd - 2451545.0) / 365.25); }   // matches the derived table
function _toJD(y, m, d, hourUT) {
  if (m <= 2) { y -= 1; m += 12; }
  const A = Math.floor(y / 100), B = 2 - A + Math.floor(A / 4);
  return Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + d + B - 1524.5 + hourUT / 24;
}
function _lerpLon(a, b, f) { const d = ((b - a + 540) % 360) - 180; return (a + d * f + 360) % 360; }
function nakOf(lon) { const s = 360 / 27, i = Math.floor(lon / s) % 27, p = Math.floor((lon % s) / (s / 4)) + 1; return { nak: NAK[i], pada: p, i }; }

/* Compute a sidereal (Lahiri) birth chart in the browser from date/time/place.
   grahas from the shipped daily table (interpolated to the birth minute); ascendant computed live
   from local sidereal time + latitude. Returns positions + a moon-cusp honesty flag. */
async function computeNatal(bd) {
  const { date, time, tz, lat, lon } = bd;
  // The wizard persists this as `time_known` (snake_case, matching the Supabase column); accept both
  // spellings. Reading only `timeKnown` meant every chart silently fell back to Chandra lagna and no
  // ascendant was ever computed, however exact the birth time given.
  const timeKnown = bd.timeKnown ?? bd.time_known ?? false;
  const e = await loadEphem();
  const [Y, M, D] = date.split("-").map(Number);
  const [hh, mm] = (time || "12:00").split(":").map(Number);
  const localH = (hh || 0) + (mm || 0) / 60;
  const utH = localH - (tz || 0);                             // local clock -> UT
  // day index into the table, plus fraction of day (UT), spilling across midnight if utH<0 or >=24
  let dayMs = Date.UTC(Y, M - 1, D) + utH * 3600000;
  const dayIdx = Math.floor((dayMs - e.start) / 86400000);
  const frac = (dayMs - e.start) / 86400000 - dayIdx;
  const grahas = {};
  if (dayIdx < 0 || dayIdx >= e.hdr.n_days - 1) return { error: "birth date outside the ephemeris range (1950–2035)" };
  const readRow = (di) => NEPH_BODIES.map((_, b) => e.dv.getUint16((di * 9 + b) * 2, true) / 10);
  const r0 = readRow(dayIdx), r1 = readRow(dayIdx + 1);
  let moonCusp = false;
  NEPH_BODIES.forEach((body, b) => {
    const lonv = _lerpLon(r0[b], r1[b], frac);
    const si = Math.floor(lonv / 30) % 12, nk = nakOf(lonv);
    if (body === "Moon") { const s = 360 / 27, edge = Math.min(lonv % s, s - (lonv % s)); if (edge < 0.5) moonCusp = true; }
    grahas[body] = { lon: +lonv.toFixed(2), sign: SIGN12[si], sign_i: si, deg_in_sign: +(lonv % 30).toFixed(2), nakshatra: nk.nak, pada: nk.pada };
  });
  // ascendant (needs the exact minute + place)
  let ascend = null;
  if (timeKnown) {
    const jd = _toJD(Y, M, D, utH);
    const T = (jd - 2451545.0) / 36525;
    let gmst = 280.46061837 + 360.98564736629 * (jd - 2451545.0) + 0.000387933 * T * T - T * T * T / 38710000;
    const lst = (((gmst + lon) % 360) + 360) % 360;
    const eps = (23.4392911 - 0.0130042 * T) * D2R;
    const ramc = lst * D2R, phi = lat * D2R;
    let asc = Math.atan2(Math.cos(ramc), -(Math.sin(ramc) * Math.cos(eps) + Math.tan(phi) * Math.sin(eps))) * R2D;
    asc = ((asc % 360) + 360) % 360;
    const sid = ((asc - _lahiri(jd)) % 360 + 360) % 360;
    ascend = { lon: +sid.toFixed(2), sign: SIGN12[Math.floor(sid / 30) % 12], deg_in_sign: +(sid % 30).toFixed(2), nakshatra: nakOf(sid).nak };
  }
  return { grahas, ascendant: ascend, moon_cusp: moonCusp,
    dasha: vimshottariFor(grahas.Moon.lon, date), computed_at: new Date().toISOString() };
}

/* Vimshottari maha-dasha sequence for a person, from the natal Moon's nakshatra. Birth time known,
   so unlike the stock charts these dates are honest (no first-trade-time ambiguity). */
const _DORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"];
const _DYEARS = { Ketu: 7, Venus: 20, Sun: 6, Moon: 10, Mars: 7, Rahu: 18, Jupiter: 16, Saturn: 19, Mercury: 17 };
function vimshottariFor(moonLon, birthISO) {
  const span = 360 / 27, nakI = Math.floor(moonLon / span) % 27, lord = _DORDER[nakI % 9];
  const fracDone = (moonLon % span) / span, YD = 365.2425;
  let cursor = new Date(birthISO + "T12:00:00Z").getTime() - fracDone * _DYEARS[lord] * YD * 86400000;
  const start = _DORDER.indexOf(lord), seq = [];
  for (let k = 0; k < 9; k++) {
    const g = _DORDER[(start + k) % 9], end = cursor + _DYEARS[g] * YD * 86400000;
    seq.push({ lord: g, from: new Date(cursor).toISOString().slice(0, 10), to: new Date(end).toISOString().slice(0, 10), years: _DYEARS[g] });
    cursor = end;
  }
  const now = Date.now();
  const cur = seq.find(d => new Date(d.from).getTime() <= now && now < new Date(d.to).getTime()) || seq[0];
  // antardasha: the sub-period inside the running maha-dasha. Each maha of L years splits into 9
  // antardashas of L*antarYears/120 years, in the same graha order starting from the maha lord.
  const antar = antardashaOf(cur, now);
  return { current: { ...cur, ...antar }, antar_sequence: antardashaSeq(cur), sequence: seq };
}
function antardashaSeq(maha) {
  const YD = 365.2425, si = _DORDER.indexOf(maha.lord);
  let s = new Date(maha.from + "T12:00:00Z").getTime(), out = [];
  for (let k = 0; k < 9; k++) {
    const g = _DORDER[(si + k) % 9], e = s + _DYEARS[maha.lord] * _DYEARS[g] / 120 * YD * 86400000;
    out.push({ lord: g, from: new Date(s).toISOString().slice(0, 10), to: new Date(e).toISOString().slice(0, 10) });
    s = e;
  }
  return out;
}
function antardashaOf(maha, at) {
  const cur = antardashaSeq(maha).find(a => new Date(a.from).getTime() <= at && at < new Date(a.to).getTime());
  return cur ? { antar: cur.lord, antar_from: cur.from, antar_to: cur.to } : {};
}

/* ---------- the natal orrery: a 2D SVG that reads as 3D — nine grahas on tilted concentric
   orbits (foreshortened ellipses = perspective), each at its true sidereal longitude, with depth
   from layered shadows and a light gradient. Pure inline SVG (CSP-safe), pixel-glyph planets. */
const ORBIT_ORDER = ["Moon", "Mercury", "Venus", "Sun", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"];
function natalOrrery(grahas, ascendant, transits) {
  const W = 440, H = 300, cx = W / 2, cy = H / 2 + 8, TILT = 0.46;   // ry/rx foreshorten
  const rings = ORBIT_ORDER.length;
  const rMin = 30, rMax = 196;
  // zodiac ring (outermost) with 12 sign spokes
  const rxZ = rMax + 16, ryZ = rxZ * TILT;
  let spokes = "", signLbls = "";
  for (let s = 0; s < 12; s++) {
    const a = (s * 30) * Math.PI / 180, a2 = (s * 30 + 30) * Math.PI / 180;
    const x1 = cx + rxZ * Math.cos(a), y1 = cy - ryZ * Math.sin(a);
    spokes += `<line x1="${cx + (rMin - 8) * Math.cos(a)}" y1="${cy - (rMin - 8) * TILT * Math.sin(a)}" x2="${x1.toFixed(1)}" y2="${y1.toFixed(1)}" class="orr-spoke"/>`;
    const am = (s * 30 + 15) * Math.PI / 180;
    signLbls += `<text x="${(cx + (rxZ + 12) * Math.cos(am)).toFixed(1)}" y="${(cy - (ryZ + 12) * Math.sin(am)).toFixed(1)}" class="orr-sign">${["ARI", "TAU", "GEM", "CAN", "LEO", "VIR", "LIB", "SCO", "SAG", "CAP", "AQU", "PIS"][s]}</text>`;
  }
  // concentric orbit ellipses (back-to-front for depth)
  let orbits = "";
  ORBIT_ORDER.forEach((b, i) => {
    const rx = rMin + (rMax - rMin) * (i / (rings - 1)), ry = rx * TILT;
    orbits += `<ellipse cx="${cx}" cy="${cy}" rx="${rx.toFixed(1)}" ry="${ry.toFixed(1)}" class="orr-orbit" style="opacity:${0.28 + 0.05 * i}"/>`;
  });
  // ascendant ray
  let ascRay = "";
  if (ascendant) {
    const a = ascendant.lon * Math.PI / 180;
    ascRay = `<line x1="${cx}" y1="${cy}" x2="${(cx + rxZ * Math.cos(a)).toFixed(1)}" y2="${(cy - ryZ * Math.sin(a)).toFixed(1)}" class="orr-asc"/>
      <text x="${(cx + (rxZ + 6) * Math.cos(a)).toFixed(1)}" y="${(cy - (ryZ + 6) * Math.sin(a)).toFixed(1)}" class="orr-asc-lbl">ASC</text>`;
  }
  // planets — placed on their orbit at true longitude, drawn front-to-back so nearer ones overlap
  const placed = ORBIT_ORDER.map((b, i) => {
    const g = grahas[b]; if (!g) return null;
    const rx = rMin + (rMax - rMin) * (i / (rings - 1)), ry = rx * TILT;
    const a = g.lon * Math.PI / 180;
    const x = cx + rx * Math.cos(a), y = cy - ry * Math.sin(a);
    return { b, x, y, depth: y };
  }).filter(Boolean).sort((p, q) => p.depth - q.depth);
  const planets = placed.map(p => `<g class="orr-planet">
      <ellipse cx="${p.x.toFixed(1)}" cy="${(p.y + 11).toFixed(1)}" rx="9" ry="2.5" class="orr-shadow"/>
      <g class="orr-g">${pixelRects(p.b, 19, p.x, p.y)}</g></g>`).join("");
  // today's sky — the same nine grahas as they stand RIGHT NOW, faint on the outermost ring.
  // The natal chart is fixed; this ring drifts a little every day, which is the whole point.
  let transitMarks = "";
  if (transits) transitMarks = NEPH_BODIES.map(b => {
    const t = transits[b]; if (!t) return "";
    const a = t.lon * Math.PI / 180;
    return `<g class="orr-transit">${pixelRects(b, 11, cx + rxZ * Math.cos(a), cy - ryZ * Math.sin(a))}</g>`;
  }).join("");
  return `<div class="orrery"><svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="xMidYMid meet">
    <defs><radialGradient id="orrBg" cx="50%" cy="46%" r="62%"><stop offset="0%" stop-color="var(--panel2)"/><stop offset="100%" stop-color="var(--panel)"/></radialGradient></defs>
    <ellipse cx="${cx}" cy="${cy}" rx="${rxZ + 26}" ry="${(rxZ + 26) * TILT + 10}" fill="url(#orrBg)"/>
    ${orbits}${spokes}${ascRay}
    <g class="orr-earth"><circle cx="${cx}" cy="${cy}" r="4"/><text x="${cx}" y="${cy + 15}" class="orr-earth-lbl">you</text></g>
    ${planets}${transitMarks}${signLbls}
  </svg></div>`;
}

/* ==========================================================================================
   GOCHARA — the moving sky read against the user's natal Moon, recomputed every day from the same
   ephemeris table the natal cast uses. The natal chart is static; THIS is what changes daily, and
   the dated "worth another look" shifts are the reason a reading is worth returning to.
   ========================================================================================== */
const GOCHARA_FAV = {   // classical favourable houses counted from the natal Moon
  Sun: [3, 6, 10, 11], Moon: [1, 3, 6, 7, 10, 11], Mars: [3, 6, 11],
  Mercury: [2, 4, 6, 8, 10, 11], Jupiter: [2, 5, 7, 9, 11],
  Venus: [1, 2, 3, 4, 5, 8, 9, 11, 12], Saturn: [3, 6, 11], Rahu: [3, 6, 11], Ketu: [3, 6, 11],
};

/* sidereal longitudes of the nine grahas for any instant inside the table (1950–2035) */
async function skyOn(dateMs) {
  const e = await loadEphem();
  const di = Math.floor((dateMs - e.start) / 86400000);
  if (di < 0 || di >= e.hdr.n_days - 1) return null;
  const frac = (dateMs - e.start) / 86400000 - di;
  const read = k => NEPH_BODIES.map((_, b) => e.dv.getUint16(((di + k) * 9 + b) * 2, true) / 10);
  const r0 = read(0), r1 = read(1), out = {};
  NEPH_BODIES.forEach((body, b) => {
    const lo = _lerpLon(r0[b], r1[b], frac), si = Math.floor(lo / 30) % 12;
    out[body] = { lon: lo, sign_i: si, sign: SIGN12[si] };
  });
  return out;
}

function gocharaRead(nc, sky, amap) {
  const moonI = nc.grahas.Moon.sign_i ?? Math.floor(nc.grahas.Moon.lon / 30) % 12;
  const tiles = NEPH_BODIES.map(g => {
    const t = sky[g];
    const house = ((t.sign_i - moonI + 12) % 12) + 1;
    const fav = (GOCHARA_FAV[g] || []).includes(house);
    // "testing" is reserved for the classical hard Saturn seats (Sade Sati houses + the 8th);
    // everything else non-favourable is simply neutral — gochara is weather, not doom.
    const tag = fav ? "favourable" : (g === "Saturn" && [12, 1, 2, 8].includes(house)) ? "testing" : "neutral";
    let conj = null;
    for (const ng of NEPH_BODIES) {
      const d = Math.abs(((t.lon - nc.grahas[ng].lon + 540) % 360) - 180);
      if (d <= 2.5) { conj = ng; break; }
    }
    const domains = (amap?.grahas?.[g]?.domains || []).slice(0, 2).join(", ");
    return { g, sign: t.sign, house, fav, tag, conj, domains };
  });
  return { tiles, sadeSati: [12, 1, 2].includes(tiles.find(t => t.g === "Saturn").house) };
}

/* The comeback calendar: scan the ephemeris forward for the dates the sky re-deals THIS chart —
   sign ingresses (house-from-Moon changes) for everything but the too-fast Moon and mirror Ketu,
   plus the user's own dasha/antardasha turnovers. Sorted, dated, honest. */
async function upcomingShifts(nc, horizon = 400) {
  const e = await loadEphem();
  const t0 = Date.now();
  const di0 = Math.floor((t0 - e.start) / 86400000);
  if (di0 < 0) return [];
  const moonI = Math.floor(nc.grahas.Moon.lon / 30) % 12;
  const bodies = ["Sun", "Mars", "Mercury", "Venus", "Jupiter", "Saturn", "Rahu"];
  const bi = bodies.map(b => NEPH_BODIES.indexOf(b));
  const maxDi = Math.min(di0 + horizon, e.hdr.n_days - 1);
  const out = [];
  let prev = bi.map(b => Math.floor((e.dv.getUint16((di0 * 9 + b) * 2, true) / 10) / 30) % 12);
  for (let di = di0 + 1; di <= maxDi; di++) {
    bi.forEach((b, k) => {
      const si = Math.floor((e.dv.getUint16((di * 9 + b) * 2, true) / 10) / 30) % 12;
      if (si !== prev[k]) {
        const house = ((si - moonI + 12) % 12) + 1;
        out.push({ date: new Date(e.start + di * 86400000).toISOString().slice(0, 10),
          kind: "ingress", body: bodies[k], sign: SIGN12[si], house, fav: (GOCHARA_FAV[bodies[k]] || []).includes(house) });
        prev[k] = si;
      }
    });
  }
  const cur = nc.dasha?.current || {};
  for (const [d, kind, body] of [[cur.antar_to, "antar", cur.antar], [cur.to, "maha", cur.lord]]) {
    const t = d && new Date(d).getTime();
    if (t && t > t0 && t - t0 < horizon * 86400000) out.push({ date: String(d).slice(0, 10), kind, body });
  }
  out.sort((a, b) => a.date.localeCompare(b.date));
  return out;
}

/* ---------- the dasha timeline: the "when". The user's Vimshottari maha-dasha ribbon with the
   current period + sub-period marked, and which market each period's lord favours. This is the
   map of TIME the owner asked for — framed as tradition's rhythm, never "invest on this date". */
function dashaTimeline(chart, amap) {
  const seq = chart.dasha?.sequence || [];
  if (!seq.length) return "";
  const now = Date.now();
  const t0 = new Date(seq[0].from).getTime(), t1 = new Date(seq[seq.length - 1].to).getTime(), span = t1 - t0;
  const nowPct = Math.max(0, Math.min(100, (now - t0) / span * 100));
  const segs = seq.map(d => {
    const a = new Date(d.from).getTime(), b = new Date(d.to).getTime();
    const active = a <= now && now < b;
    return `<div class="dt-seg ${active ? "on" : ""}" style="flex:${b - a}" title="${d.lord} ${d.from}–${d.to}">
      <span class="dt-glyph">${pixelGlyph(d.lord, 16)}</span><span class="dt-lord">${esc(d.lord)}</span><span class="dt-yr">${d.from.slice(0, 4)}</span></div>`;
  }).join("");
  const cur = chart.dasha?.current || {};
  const domains = b => ((amap?.grahas?.[b] || {}).domains || []).slice(0, 3).join(", ");
  const future = seq.filter(d => new Date(d.to).getTime() > now).slice(0, 3);
  return `<div class="dt-wrap">
    <div class="dt-ribbon">${segs}<div class="dt-now" style="left:${nowPct}%"><span>now</span></div></div>
    <div class="dt-legend">${future.map((d, i) => `<div class="dt-leg ${i === 0 ? "cur" : ""}"><b>${pixelGlyph(d.lord, 14)} ${esc(d.lord)} period</b><span class="sub">${d.from.slice(0, 4)}–${d.to.slice(0, 4)} · tradition lights up ${esc(domains(d.lord)) || "—"}</span></div>`).join("")}</div>
  </div>`;
}

/* The sub-period (antardasha) ribbon inside the running maha-dasha — the nearer, finer "when". */
function antardashaStrip(chart, amap) {
  const seq = chart.dasha?.antar_sequence || [];
  const maha = chart.dasha?.current;
  if (!seq.length || !maha) return "";
  const now = Date.now();
  const t0 = new Date(seq[0].from).getTime(), t1 = new Date(seq[seq.length - 1].to).getTime(), span = t1 - t0 || 1;
  const nowPct = Math.max(0, Math.min(100, (now - t0) / span * 100));
  const segs = seq.map(d => {
    const a = new Date(d.from).getTime(), b = new Date(d.to).getTime();
    return `<div class="dt-seg sm ${a <= now && now < b ? "on" : ""}" style="flex:${b - a}" title="${d.lord} ${d.from}–${d.to}">
      <span class="dt-glyph">${pixelGlyph(d.lord, 12)}</span><span class="dt-lord">${esc(d.lord)}</span></div>`;
  }).join("");
  const cur = seq.find(d => new Date(d.from).getTime() <= now && now < new Date(d.to).getTime());
  const domains = b => ((amap?.grahas?.[b] || {}).domains || []).slice(0, 3).join(", ");
  return `<div class="dt-sub"><div class="dt-sub-lbl">Sub-periods within your ${esc(maha.lord)} maha</div>
    <div class="dt-ribbon sub">${segs}<div class="dt-now" style="left:${nowPct}%"><span>now</span></div></div>
    ${cur ? `<p class="sub" style="margin-top:8px">Now: <b>${esc(maha.lord)} / ${esc(cur.lord)}</b> to ~${esc(String(cur.to).slice(0, 7))} — tradition colours these months with ${esc(domains(cur.lord)) || "—"}.</p>` : ""}</div>`;
}

/* Which of the user's own periods a given stock brightens under — the per-stock "when". */
function stockTiming(user, stock, sector, amap) {
  const seq = user.dasha?.sequence || [];
  const now = Date.now();
  const target = stock && stock.natal ? SIGN_LORD[Math.floor((stock.natal.Moon.lon % 360) / 30) % 12]
    : (sector ? (amap?.sector_significators?.[sector] || {}).primary : null);
  if (!target) return null;
  const horizon = now + 25 * 365.25 * 86400000;   // within a working lifetime, not centuries out
  const windows = seq.filter(d => new Date(d.to).getTime() > now && new Date(d.from).getTime() < horizon)
    .map(d => ({ ...d, rel: d.lord === target ? "peak" : (FRIEND[d.lord]?.f || []).includes(target) ? "warm" : (FRIEND[d.lord]?.e || []).includes(target) ? "cool" : "neutral" }))
    .filter(d => d.rel === "peak" || d.rel === "warm").slice(0, 2);
  if (!windows.length) return null;
  return { target, windows };
}

/* ---------- synastry: how the tradition reads a person's chart against a stock's.
   Uses classical Vedic techniques (Tara koota on the Moon nakshatras, planetary friendship of the
   sign lords, dasha resonance) — the same methods used for personal compatibility, applied to the
   market chart. A resonance score 0–100 with an explained breakdown. This is astrological
   interpretation, presented as such; it is never a recommendation to buy or a profit forecast. */
const SIGN_LORD = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"];
const FRIEND = {
  Sun: { f: ["Moon", "Mars", "Jupiter"], e: ["Venus", "Saturn"] },
  Moon: { f: ["Sun", "Mercury"], e: [] },
  Mars: { f: ["Sun", "Moon", "Jupiter"], e: ["Mercury"] },
  Mercury: { f: ["Sun", "Venus"], e: ["Moon"] },
  Jupiter: { f: ["Sun", "Moon", "Mars"], e: ["Mercury", "Venus"] },
  Venus: { f: ["Mercury", "Saturn"], e: ["Sun", "Moon"] },
  Saturn: { f: ["Mercury", "Venus"], e: ["Sun", "Moon", "Mars"] },
  Rahu: { f: ["Venus", "Saturn"], e: ["Sun", "Moon"] },
  Ketu: { f: ["Mars", "Jupiter"], e: ["Moon"] },
};
const NAT_BENEFIC = { Jupiter: 1, Venus: 1, Moon: 1, Mercury: 0.5 };
const NAT_MALEFIC = { Saturn: 1, Mars: 1, Rahu: 1, Ketu: 1, Sun: 0.5 };
function friendship(a, b) {
  if (a === b) return "same";
  const r = FRIEND[a] || { f: [], e: [] };
  if (r.f.includes(b)) return "friend";
  if (r.e.includes(b)) return "enemy";
  return "neutral";
}
// Tara koota: count person's Moon nakshatra -> stock's, the classical 9-fold auspiciousness
function taraKoota(userNakI, stockNakI) {
  const cnt = ((stockNakI - userNakI + 27) % 27) + 1, r = cnt % 9;
  const good = { 2: "Sampat (wealth)", 4: "Kshema (well-being)", 6: "Sadhaka (accomplishment)", 8: "Maitra (friendship)", 0: "Mitra (ally)" };
  const bad = { 3: "Vipat (loss)", 5: "Pratyari (obstacle)", 7: "Vadha (harm)" };
  if (good[r]) return { band: "harmonious", tara: good[r], w: 1 };
  if (bad[r]) return { band: "discordant", tara: bad[r], w: -1 };
  return { band: "mixed", tara: "Janma (the self)", w: 0 };
}

/* Commodities carry their own traditional rulerships in financial astrology — the metals, energy and
   crops a Pakistani investor actually watches. Scored against the user's chart the same way a
   chartless stock is: through the ruling graha. */
const COMMODITIES = [
  { name: "Gold", sig: "Sun", note: "the Sun's metal — kingship and store of value", glyph: "Sun" },
  { name: "Silver", sig: "Moon", note: "the Moon's metal — liquidity and the public's hoard", glyph: "Moon" },
  { name: "Crude oil", sig: "Saturn", note: "Saturn's — what is dug from deep underground", glyph: "Saturn" },
  { name: "Natural gas", sig: "Rahu", note: "Rahu's — the volatile and the piped", glyph: "Rahu" },
  { name: "Copper", sig: "Venus", note: "Venus's metal — wiring, comfort, industry", glyph: "Venus" },
  { name: "Wheat", sig: "Moon", note: "the Moon's — the staple crop and its rains", glyph: "Moon" },
  { name: "Cotton", sig: "Venus", note: "Venus's fibre — cloth and its trade", glyph: "Venus" },
  { name: "Sugar", sig: "Venus", note: "Venus's sweetness — cane and refinery", glyph: "Venus" },
];
/* Resonance of the user's chart with a single ruling graha — the shared core behind both the
   chartless-stock and commodity readings. Returns a 0-100 score + explained reasons. */
function resonanceWithGraha(user, target, label) {
  if (!target) return { score: null, reasons: [] };
  const uMoon = user.grahas.Moon, uLord = SIGN_LORD[Math.floor((uMoon.lon % 360) / 30) % 12];
  const uDasha = user.dasha?.current?.lord, uAntar = user.dasha?.current?.antar;
  let score = 50; const reasons = [];
  const fr = friendship(uLord, target);
  const fw = fr === "friend" || fr === "same" ? 1 : fr === "enemy" ? -1 : 0;
  score += fw * 14;
  reasons.push({ k: `You & ${target}`, v: fr, why: `${label} answers to ${target}. Your Moon-lord ${uLord} is ${fr === "same" ? "that same planet" : "traditionally its " + fr}.`, w: fw });
  if (uDasha === target) { score += 16; reasons.push({ k: "You're in its period", v: `${target} dasha`, why: `You are running a ${target} maha-dasha — the very planet that rules ${label}.`, w: 1 }); }
  else if (uDasha) { const d = friendship(uDasha, target); const dw = d === "friend" ? 1 : d === "enemy" ? -1 : 0; score += dw * 7; reasons.push({ k: "Your current period", v: `${uDasha} dasha`, why: `Your ${uDasha} period is ${d} to ${target}.`, w: dw }); }
  if (uAntar === target) { score += 10; reasons.push({ k: "And your sub-period", v: `${uAntar} antardasha`, why: `Your running sub-period is ${uAntar}'s too — a sharper, nearer window.`, w: 1 }); }
  const ug = user.grahas[target];
  if (ug && SIGN_LORD[Math.floor((ug.lon % 360) / 30) % 12] === target) { score += 8; reasons.push({ k: `Your ${target}`, v: "strong", why: `${target} sits in its own sign ${ug.sign} in your chart — a dignified placement.`, w: 1 }); }
  score = Math.max(2, Math.min(98, Math.round(score)));
  const verdict = score >= 68 ? "harmonious" : score >= 55 ? "favourable" : score >= 45 ? "neutral" : score >= 32 ? "testing" : "discordant";
  return { score, verdict, reasons };
}

/* Goal-tailored framing. The user's stated goal colours the LANGUAGE of the reading — which grahas
   the tradition emphasises for that aim — never the maths. */
const GOAL_LENS = {
  growth: { label: "long-term growth", lead: "Jupiter", grahas: ["Jupiter", "Sun", "Mars"], line: "Tradition ties lasting growth to Jupiter's expansion — so its houses and periods carry the most weight for you." },
  income: { label: "dividend income", lead: "Venus", grahas: ["Venus", "Moon", "Jupiter"], line: "For steady income the tradition looks to Venus and the Moon — comfort, liquidity, the recurring yield." },
  trading: { label: "active trading", lead: "Mercury", grahas: ["Mercury", "Moon", "Mars"], line: "For quick moves the tradition watches Mercury and the fast Moon — and your nearer sub-periods matter more than the long arc." },
  curious: { label: "exploration", lead: null, grahas: [], line: "" },
};
function goalLens() { return GOAL_LENS[(astroPrefs().goal || "curious")] || GOAL_LENS.curious; }

/* Score a person's chart against one stock. If the stock has a verified natal chart, the full
   technique set runs; otherwise it falls back to the sector's significator graha. */
function synastry(user, stock, sector, amap, astroNow) {
  const reasons = [];
  let score = 50;   // neutral start
  const uMoon = user.grahas.Moon, uLordUser = SIGN_LORD[uMoon.sign_i];
  const uDasha = user.dasha?.current?.lord;

  const _si = p => Math.floor((p.lon % 360) / 30) % 12;   // stock natal carries lon, not sign_i
  if (stock && stock.natal) {
    const sMoon = stock.natal.Moon;
    // 1. Tara koota on the Moon nakshatras — the heart of Vedic compatibility
    const tk = taraKoota(nakOf(uMoon.lon).i, nakOf(sMoon.lon).i);
    score += tk.w * 16;
    reasons.push({ k: "Moon compatibility (Tara)", v: tk.band, why: `Counting from your Moon star to the stock's lands on ${tk.tara}.`, w: tk.w });
    // 2. friendship of the Moon-sign lords
    const sLord = SIGN_LORD[_si(sMoon)], fr = friendship(uLordUser, sLord);
    const fw = fr === "friend" || fr === "same" ? 1 : fr === "enemy" ? -1 : 0;
    score += fw * 10;
    reasons.push({ k: "Sign-lord friendship", v: fr, why: `Your Moon rules through ${uLordUser}; the stock's through ${sLord} — ${fr === "same" ? "the same planet" : "traditionally " + fr + "s"}.`, w: fw });
    // 3. your benefics / malefics landing on the stock's Sun or Moon sign
    let bw = 0;
    ["Jupiter", "Venus", "Saturn", "Mars"].forEach(g => {
      const ug = user.grahas[g]; if (!ug) return;
      [["Sun", sMoon && stock.natal.Sun], ["Moon", sMoon]].forEach(([nm, sp]) => {
        if (sp && ug.sign_i === Math.floor(sp.lon / 30) % 12) {
          const ben = NAT_BENEFIC[g] ? 1 : -1; bw += ben;
          reasons.push({ k: `Your ${g} on its natal ${nm}`, v: ben > 0 ? "supportive" : "testing", why: `Your ${g} sits in ${ug.sign}, the stock's natal ${nm} sign — tradition reads ${g} there as ${ben > 0 ? "a blessing" : "a strain"}.`, w: ben });
        }
      });
    });
    score += Math.max(-14, Math.min(14, bw * 7));
    // 4. dasha resonance: are you running a period whose lord the stock's chart welcomes?
    if (uDasha) {
      const dfr = friendship(uDasha, sLord);
      const dw = dfr === "friend" || dfr === "same" ? 1 : dfr === "enemy" ? -1 : 0;
      score += dw * 8;
      reasons.push({ k: "Your current period", v: `${uDasha} dasha`, why: `You are in a ${uDasha} period; the stock's Moon-lord ${sLord} is ${dfr === "same" ? "the very same" : "traditionally its " + dfr}.`, w: dw });
    }
  } else {
    // no stock chart (listed pre-2000) — read against the sector's significator graha
    const sig = sector ? (amap?.sector_significators?.[sector] || {}) : {};
    const prim = sig.primary;
    if (!prim) return { score: null, verdict: "no reading", reasons: [] };
    const fr = friendship(uLordUser, prim);
    const fw = fr === "friend" || fr === "same" ? 1 : fr === "enemy" ? -1 : 0;
    score += fw * 14;
    reasons.push({ k: `You & ${prim}`, v: fr, why: `${sector} answers to ${prim}. Your Moon-lord ${uLordUser} is ${fr === "same" ? "that same planet" : "traditionally its " + fr}.`, w: fw });
    // running the significator's own dasha is the strongest resonance a chartless name can offer
    if (uDasha === prim) { score += 18; reasons.push({ k: "You're in its period", v: `${prim} dasha`, why: `You are running a ${prim} period — and ${prim} is exactly what tradition ties ${sector} to.`, w: 1 }); }
    else if (uDasha) { const dfr = friendship(uDasha, prim); const dw = dfr === "friend" ? 1 : dfr === "enemy" ? -1 : 0; score += dw * 8; reasons.push({ k: "Your current period", v: `${uDasha} dasha`, why: `Your ${uDasha} period is ${dfr} to ${sector}'s ${prim}.`, w: dw }); }
    // is the significator well-placed in YOUR chart?
    const ug = user.grahas[prim];
    if (ug) { const own = SIGN_LORD[ug.sign_i] === prim; if (own) { score += 8; reasons.push({ k: `Your ${prim}`, v: "strong", why: `${prim} sits in its own sign ${ug.sign} in your chart — a dignified placement.`, w: 1 }); } }
  }
  score = Math.max(2, Math.min(98, Math.round(score)));
  const verdict = score >= 68 ? "harmonious" : score >= 55 ? "favourable" : score >= 45 ? "neutral" : score >= 32 ? "testing" : "discordant";
  return { score, verdict, reasons };
}

/* ---------- pixel grahas: 11x11 one-bit glyphs, drawn as SVG rects in currentColor.
   The classical symbols, pixelated — Saturn's ring, Jupiter's band, the Sun's rays. ---------- */
const PIXEL_GRAHAS = {
  Sun: ["....#....", ".#..#..#.", "..#####..", ".##...##.", "#.#.#.#.#", ".##...##.", "..#####..", ".#..#..#.", "....#...."],
  Moon: ["...###...", "..##.....", ".##......", ".##......", ".##......", ".##......", ".##......", "..##.....", "...###..."],
  Mercury: [".#.....#.", "..#####..", ".##...##.", ".##...##.", "..#####..", "....#....", "..#####..", "....#....", "....#...."],
  Venus: ["..#####..", ".##...##.", ".##...##.", ".##...##.", "..#####..", "....#....", "..#####..", "....#....", "....#...."],
  Mars: [".....####", "......##.", "....##.##", "..#####..", ".##...#..", ".##......", ".##......", "..#####..", "........."],
  Jupiter: ["..#####..", ".##...##.", "#########", "#########", ".##...##.", ".##...##.", "..#####..", ".........", "........."],
  Saturn: ["..#####..", ".##...##.", ".##...##.", "###...###", "#########", "###...###", ".##...##.", "..#####..", "........."],
  Rahu: ["..#####..", ".##...##.", ".##...##.", ".##...##.", "..#...#..", "..#...#..", ".##...##.", "##.....##", "........."],
  Ketu: ["##.....##", ".##...##.", "..#...#..", "..#...#..", ".##...##.", ".##...##.", ".##...##.", "..#####..", "........."],
};
function pixelGlyph(body, px) {
  const g = PIXEL_GRAHAS[body];
  if (!g) return "";
  const n = 9, cell = Math.max(1, Math.floor(px / n));
  let rects = "";
  g.forEach((row, y) => { [...row].forEach((c, x) => { if (c === "#") rects += `<rect x="${x * cell}" y="${y * cell}" width="${cell}" height="${cell}"/>`; }); });
  return `<svg class="pxg" viewBox="0 0 ${n * cell} ${n * cell}" width="${px}" height="${px}" fill="currentColor" aria-label="${body}">${rects}</svg>`;
}
const GRAHA_AB = { Sun: "Su", Moon: "Mo", Mercury: "Me", Venus: "Ve", Mars: "Ma", Jupiter: "Ju", Saturn: "Sa", Rahu: "Ra", Ketu: "Ke" };
// raw <rect> string for embedding a glyph DIRECTLY in a parent SVG (no foreignObject — which fails
// in Safari and breaks screenshot/export renderers). Centred on (ox,oy), total size px.
function pixelRects(body, px, ox, oy, fill) {
  const g = PIXEL_GRAHAS[body]; if (!g) return "";
  const n = 9, cell = Math.max(1, px / n), o0 = -px / 2;
  let r = "";
  g.forEach((row, y) => { [...row].forEach((c, x) => { if (c === "#") r += `<rect x="${(ox + o0 + x * cell).toFixed(1)}" y="${(oy + o0 + y * cell).toFixed(1)}" width="${cell.toFixed(1)}" height="${cell.toFixed(1)}"/>`; }); });
  return `<g fill="${fill || "currentColor"}">${r}</g>`;
}

/* the zodiac strip: 12 sidereal signs as columns; transiting grahas on the top lane, the natal
   chart (when one exists) on the bottom lane — so a transit sitting on a natal point is VISIBLE
   as a vertical alignment, which is the whole thing astrologers look for. */
function zodiacStrip(transitPos, natalPos) {
  const SIGNS12 = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"];
  const lane = pos => {
    const bySign = {};
    Object.entries(pos || {}).forEach(([b, p]) => {
      const si = Math.floor((p.lon ?? 0) / 30) % 12;
      (bySign[si] = bySign[si] || []).push(b);
    });
    return SIGNS12.map((_, i) => `<div class="zs-cell">${(bySign[i] || []).map(b =>
      `<span class="zs-g" title="${b}${pos[b].retrograde ? " (retrograde)" : ""}">${pixelGlyph(b, 18)}<i>${GRAHA_AB[b]}${pos[b].retrograde ? "ᴿ" : ""}</i></span>`).join("")}</div>`).join("");
  };
  return `<div class="zstrip">
    <div class="zs-lane"><span class="zs-lbl">sky now</span>${lane(transitPos)}</div>
    ${natalPos ? `<div class="zs-lane natal"><span class="zs-lbl">at birth</span>${lane(natalPos)}</div>` : ""}
    <div class="zs-lane signs"><span class="zs-lbl"></span>${SIGNS12.map(s => `<div class="zs-cell sign">${s}</div>`).join("")}</div>
  </div>`;
}

/* ---------- the astro board (profiles.astro_board; session-only for guests) ---------- */
function astroBoard() {
  if (me) return (myProfile && myProfile.astro_board) || [];
  try { return JSON.parse(sessionStorage.getItem("astroboard") || "[]"); } catch (e) { return []; }
}
async function saveAstroBoard(list) {
  if (me) return saveProfile({ astro_board: list });
  try { sessionStorage.setItem("astroboard", JSON.stringify(list)); } catch (e) { /* private mode */ }
  return null;
}
function astroRunOn(sym) { try { return !!sessionStorage.getItem("astroran:" + sym); } catch (e) { return false; } }
async function addAstroTicker() {
  const inp = document.getElementById("ab-tkr"), msg = document.getElementById("ab-msg");
  const say = t => { if (msg) msg.textContent = t; };
  const sym = (inp?.value || "").toUpperCase().trim();
  if (!sym) return;
  const uni = await j("universe.json");
  if (!uni?.symbols?.[sym]) return say(`${sym} isn't in the desk's universe — try the suggestions as you type.`);
  const cur = astroBoard();
  if (cur.includes(sym)) return say(`${sym} is already on your board.`);
  if (cur.length >= 8) return say("The board holds 8 charts — remove one first.");
  const err = await saveAstroBoard([...cur, sym]);
  if (err) return say("Couldn't save — try again.");
  pageAstro();
}
async function removeAstroTicker(sym) {
  const err = await saveAstroBoard(astroBoard().filter(s => s !== sym));
  if (!err) pageAstro();
}

/* ---------- the reading: what the tradition says about this chart, composed strictly from the
   computed layers (astro_natal / astro / astro_map). Template prose over real data — no agent, no
   invention, and NEVER a call. The desk's tested-vs-untested status is stated inside the reading. */
function composeAstroReading(sym, data) {
  const { natal, sky, amap, sectors, uni } = data;
  const subj = natal?.subjects?.[sym];
  const name = uni?.symbols?.[sym]?.name || "";
  const sect = (sectors?.tickers?.[sym] || {}).sector;
  const domains = b => ((amap?.grahas?.[b] || {}).domains || []).slice(0, 3).join(", ");
  const skyPos = sky?.positions || {};
  const events14 = (sky?.events || []).filter(e => e.importance >= 3 && e.date <= new Date(Date.now() + 14 * 86400000).toISOString().slice(0, 10)).slice(0, 3);

  if (subj) {
    const moon = subj.natal?.Moon || {};
    const das = subj.dasha?.current || {};
    const ts = subj.time_sensitivity || {};
    const ss = subj.sade_sati || {};
    const hits = (subj.transits_to_natal || []).slice(0, 3);
    const natPos = subj.natal;
    return `
      <div class="ar-head"><b>${esc(sym)}</b><span class="sub">${esc(name.slice(0, 34))}</span>
        <span class="pill ok">natal chart</span></div>
      <div class="ar-birth sub">${esc(sym)}'s chart, cast for its first trade on ${esc(subj.birth?.date)}. Sidereal, Lahiri.</div>
      ${zodiacStrip(skyPos, natPos)}
      <div class="ar-grid">
        <div class="ar-cell"><span class="ark">Natal Moon</span><b>${esc(moon.sign)} · ${esc(moon.nakshatra)}</b>
          <i>Read from the Moon — the Chandra lagna, the mind of the chart.</i></div>
        <div class="ar-cell"><span class="ark">The period (dasha)</span><b>${pixelGlyph(das.maha, 16)} ${esc(das.maha || "—")}${das.antar ? ` / ${esc(das.antar)}` : ""}</b>
          <i>${das.maha ? `A ${esc(das.maha)} maha-dasha, running to ~${esc(String(das.maha_to || "").slice(0, 7))}. Tradition ties ${esc(das.maha)} to ${esc(domains(das.maha))}.` : "—"}</i></div>
        <div class="ar-cell"><span class="ark">Saturn's passage</span><b>${ss.active ? "SADE SATI · " + esc((ss.phase || "").split(" (")[0]) : ss.phase ? esc(ss.phase.split(" (")[0]) : "quiet"}</b>
          <i>${ss.active ? "Saturn is crossing the natal Moon's neighbourhood — the seven-and-a-half-year passage the tradition treats as its heaviest weather." : "No Sade Sati running on this chart."}</i></div>
        <div class="ar-cell"><span class="ark">On this chart now</span><b>${hits.length ? hits.map(h => `${GRAHA_AB[h.transiting]}→${GRAHA_AB[h.over_natal]}`).join(" · ") : "no tight contacts"}</b>
          <i>${hits.length ? hits.map(h => `transiting ${esc(h.transiting)} sits on natal ${esc(h.over_natal)} (${h.orb_deg}°)`).join("; ") + "." : "No transiting graha within 3° of a natal point today."}</i></div>
      </div>
      <div class="ar-read">
        <p><b>The days ahead:</b> ${events14.length ? `the sky's next marks are ${events14.map(e => `${esc(e.text)} (${esc(e.date)})`).join("; ")}.` : "no high-rank sky events in the next two weeks."} ${hits.length ? `Tradition would watch the ${esc(hits[0].transiting)}–natal-${esc(hits[0].over_natal)} contact most closely.` : ""}</p>
        <p><b>The months:</b> ${das.antar ? `the running sub-period is ${esc(das.antar)} (to ~${esc(String(das.antar_to || "").slice(0, 7))}) — tradition colours these months with ${esc(domains(das.antar))}.` : ""}</p>
        <p><b>The years:</b> ${das.maha ? `the ${esc(das.maha)} maha-dasha frames the longer arc.` : "—"}</p>
        <p class="ar-caveat">The tradition's reading of ${esc(sym)}'s chart — for exploration, not advice.</p>
      </div>`;
  }
  // read through the sector's ruling planet — a mundane-astrology technique in its own right
  const sig = sect ? (amap?.sector_significators?.[sect] || {}) : {};
  const prim = sig.primary;
  const p = prim ? skyPos[prim] : null;
  const mkt = natal?.subjects?.KSE100;
  const mdas = mkt?.dasha?.current || {};
  return `
    <div class="ar-head"><b>${esc(sym)}</b><span class="sub">${esc(name.slice(0, 34))}</span>
      <span class="pill">sector reading</span></div>
    <div class="ar-birth sub">${prim ? `The tradition reads ${esc(sym)} through ${esc(sect)}, and its ruling planet ${esc(prim)}.` : `${esc(sym)} read against the market's own chart.`}</div>
    ${zodiacStrip(skyPos, null)}
    <div class="ar-grid">
      ${prim ? `<div class="ar-cell"><span class="ark">Ruling planet</span><b>${pixelGlyph(prim, 16)} ${esc(prim)}</b>
        <i>${esc(prim)} governs ${esc(sect)} — ${esc(domains(prim))}. Right now it moves through ${esc(p?.sign || "—")}, ${esc(p?.nakshatra || "—")}${p?.retrograde ? ", retrograde" : ""}.</i></div>` : ""}
      <div class="ar-cell"><span class="ark">The market's chart</span><b>KSE-100 · ${esc(mdas.maha || "—")}${mdas.antar ? "/" + esc(mdas.antar) : ""} period</b>
        <i>The index's chart, born 1991, is the weather every PSX name trades inside${mkt?.sade_sati?.active ? " — and it is running Sade Sati" : ""}.</i></div>
    </div>
    <div class="ar-read">
      <p class="ar-caveat">A sector-level astrological reading of ${esc(sym)} — for exploration, not advice.</p>
    </div>`;
}

/* ---------- the run: 10–20s of real computation narrated, then the readings reveal ---------- */
async function playAstroBoardRun() {
  const board = astroBoard();
  if (!board.length) return;
  const [natal, sky, amap, sectors, uni] = await Promise.all([
    j("astro_natal.json"), j("astro.json"), j("astro_map.json"), j("sectors.json"), j("universe.json")]);
  const data = { natal, sky, amap, sectors, uni };
  const verified = board.filter(s => natal?.subjects?.[s]);
  const ayan = sky?.system?.ayanamsa_deg;

  const steps = [
    `Computing the sidereal sky — Lahiri ayanamsa <b>${esc(ayan)}°</b>, derived from Spica`,
    ...board.map(s => natal?.subjects?.[s]
      ? `Casting <b>${esc(s)}</b>'s birth chart — first trade ${esc(natal.subjects[s].birth?.date)}, Karachi open`
      : `<b>${esc(s)}</b> — reading through its sector's ruling planet`),
    ...verified.slice(0, 3).map(s => `Vimshottari — balancing the ${esc(natal.subjects[s].dasha?.current?.maha || "")} period from the natal Moon's nakshatra`),
    `Checking Saturn against every natal Moon — Sade Sati scan`,
    `Scanning transits to natal points (3° orb)`,
    `Composing the readings — tradition's words, the desk's tests attached`,
  ];

  runRevealModal({
    sym: "", kicker: "The astro desk · your charts",
    title: `Casting ${board.length} chart${board.length > 1 ? "s" : ""} against today's sky`,
    sub: `Real ephemeris math — sidereal positions, Vimshottari periods, Saturn's passage — for every name on your board, read the way the tradition would.`,
    steps,
    onReveal: () => { try { board.forEach(s => sessionStorage.setItem("astroran:" + s, "1")); } catch (e) { /* private */ } },
    onClose: () => { if (location.hash.replace(/^#\/?/, "").startsWith("astro")) pageAstro(); },
    renderReveal: (bodyEl) => {
      bodyEl.innerHTML = `<div class="rp-reveal">
        <div class="rp-reveal-head"><b>Your charts · ${board.map(esc).join(" · ")}</b><span>read sidereal, Lahiri ${esc(ayan)}° — the tradition's reading of each name</span></div>
        ${board.map(s => `<div class="card ar-card" style="margin-top:10px">${composeAstroReading(s, data)}</div>`).join("")}
        <div class="rp-reveal-foot"><span>The tradition's reading — for exploration, not advice.</span>
          <span class="rp-foot-btns"><button class="rp-btn2" data-a="replay">↻ Run again</button></span></div>
      </div>`;
    },
  });
}

/* ==========================================================================================
   YOUR CHART — the personal financial-astrology journey. A user casts their own birth chart and
   the tradition reads the whole PSX universe against it. Framed throughout as astrological
   exploration, never advice: "the tradition finds your chart harmonious with X", never "buy X".
   ========================================================================================== */
/* --- the funnel: casting a chart needs NO account. computeNatal() is pure client-side math over
   an ephemeris table the browser already fetches, so a guest can cast, see their real chart and a
   taste of the market read. The account is what PERSISTS it; the subscription is what unlocks the
   full map and the daily sky against it. A guest chart lives in localStorage and is migrated up to
   the profile on sign-in (GUEST_KEY), so nobody ever types their birth details twice. --- */
const GUEST_KEY = "psx_guest_chart";
function guestChart() {
  try { return JSON.parse(localStorage.getItem(GUEST_KEY) || "null"); } catch { return null; }
}
function setGuestChart(o) {
  try { o ? localStorage.setItem(GUEST_KEY, JSON.stringify(o)) : localStorage.removeItem(GUEST_KEY); } catch { /* private mode */ }
}
function birthData() { return (me && myProfile && myProfile.birth_data) || guestChart()?.birth_data || null; }
function natalChart() { return (me && myProfile && myProfile.natal_chart) || guestChart()?.natal_chart || null; }
function astroPrefs() { return (me && myProfile && myProfile.astro_prefs) || guestChart()?.astro_prefs || {}; }

/* ==========================================================================================
   PLANS — three desks for three kinds of user, plus the free tier everyone starts on.
   Payment is NOT wired: there is no Stripe in Pakistan, so a local gateway (PayFast or similar)
   comes later. Until then `plan` is set by the desk owner and the DB refuses client writes to it
   (see the freeze_plan / force_free_plan triggers). BILLING_LIVE is the ONE switch: while false,
   any signed-in account reads as subscribed, so gating cannot strip access from existing accounts.
   ========================================================================================== */
const BILLING_LIVE = false;
const FREE_MATCHES = 3;                       // how many resonance cards a guest sees in full
const PLANS = {
  free: { label: "Free", tag: "", blurb: "Cast your chart, read the daily desk note, and follow the public track record.",
    features: [] },
  // NOT "Learner" — a paid tier should be named for what the user becomes, not for what they lack.
  investor: { label: "Investor", tag: "start here",
    blurb: "Become an investor who reads for themselves. A guided path through real PSX filings — annual reports, statements, announcements — at your own pace.",
    features: ["learn", "astro_full", "dividends_full", "earnings_full"] },
  pro: { label: "Pro", tag: "TA & FA",
    blurb: "The full desk. Tested strategies, model fair value, the research library, and every lens the desk runs.",
    features: ["learn", "astro_full", "dividends_full", "earnings_full", "value_full", "strategies_run", "research_full"] },
  broker: { label: "Broker", tag: "coming soon", soon: true,
    blurb: "Everything in Pro, plus your own desk's calls scored in public on the same bar as everyone else.",
    features: ["learn", "astro_full", "dividends_full", "earnings_full", "value_full", "strategies_run", "research_full", "broker_tools"] },
};
const PLAN_ORDER = ["free", "investor", "pro", "broker"];
/* Owner-only: preview the product as any plan without changing the stored plan. Set from the Plans
   page; lives in memory only, so a reload returns you to your real plan. */
let _previewPlan = null;
function realPlan() { return (me && myProfile && myProfile.plan) || "free"; }
function isOwner() { return !!(me && (me.email || "").toLowerCase() === "mwasayi@gmail.com"); }
function planOf() { return (_previewPlan && isOwner()) ? _previewPlan : realPlan(); }
/* While BILLING_LIVE is false every signed-in account behaves as Pro — nobody loses what they have
   today. Once it flips, access is decided purely by the plan's feature list. */
function hasFeature(key) {
  if (!me) return false;
  // While previewing, judge by the previewed plan — that is the entire point of the preview.
  if (!BILLING_LIVE && !(_previewPlan && isOwner())) return true;
  return (PLANS[planOf()]?.features || []).includes(key);
}
function isSubscribed() {
  if (!me) return false;
  if (_previewPlan && isOwner()) return planOf() !== "free";
  return !BILLING_LIVE || planOf() !== "free";
}
/* Which product shell to render. The Investor desk is a different information architecture, not a
   reskin, so it gets its own nav and home. Pros/brokers see the full desk. */
function deskMode() {
  if (!me) return "pro";
  if (planOf() === "investor") return "learn";
  return (myProfile && myProfile.ui_mode === "learn") ? "learn" : "pro";
}

/* The one paywall card, used on every gated page. Language is fixed: the thing sits in "the paid
   plan" (plans being drawn for three desks — new investors, pros, brokers). Never scare copy;
   always name exactly what's behind the wall. Returns "" for subscribers so call sites can inline it. */
function planWall(what, teaser) {
  if (isSubscribed()) return "";
  return `<div class="card plan-wall">
    <div class="mc-lock-kick">part of the paid plan</div>
    <h3>${what}</h3>
    <p class="sub">${teaser}</p>
    <p class="sub">${me
      ? "This sits in the paid plan. Plans are being drawn for three desks — new investors, pros, and brokers."
      : "Create a free account to start exploring — the paid plan unlocks this in full. Plans are being drawn for three desks: new investors, pros, and brokers."}</p>
    <button class="bw-go" style="max-width:250px" onclick="${me ? "location.hash='#/settings'" : "openAuth('signup')"}">${me ? "See plans →" : "Create a free account →"}</button>
  </div>`;
}

/* Called on sign-in: lift a guest's chart into their profile so the details survive the account
   boundary. Never clobbers a chart already on the profile. */
async function migrateGuestChart() {
  const g = guestChart();
  if (!me || !g || !g.natal_chart) return false;
  if (myProfile && myProfile.birth_data) { setGuestChart(null); return false; }  // profile wins
  const patch = { birth_data: g.birth_data, natal_chart: g.natal_chart, astro_prefs: g.astro_prefs || {} };
  const err = await saveProfile(patch);
  if (!err) { setGuestChart(null); return true; }
  return false;
}

const _bw = { step: 0, data: {} };
const BW_STEPS = ["intro", "date", "time", "place", "goals", "cast"];
function openBirthWizard() {
  _bw.step = 0; _bw.data = { ...(birthData() || {}) };
  renderBirthWizard();
}
function bwClose() { document.querySelector(".bw-overlay")?.remove(); }
async function clearBirthData() {
  if (!confirm("Remove your birth details and chart? You can add them again any time.")) return;
  setGuestChart(null);
  if (me) {
    myProfile = { ...(myProfile || {}), birth_data: null, natal_chart: null };
    await saveProfile({ birth_data: null, natal_chart: null });
  }
  if (typeof pageSettings === "function") pageSettings();
}
function bwNext() { if (_bw.step < BW_STEPS.length - 1) { _bw.step++; renderBirthWizard(); } }
function bwBack() { if (_bw.step > 0) { _bw.step--; renderBirthWizard(); } }
function bwSet(k, v) { _bw.data[k] = v; }

function renderBirthWizard() {
  let ov = document.querySelector(".bw-overlay");
  if (!ov) { ov = document.createElement("div"); ov.className = "bw-overlay"; document.body.appendChild(ov);
    ov.addEventListener("click", e => { if (e.target === ov) bwClose(); }); }
  const s = BW_STEPS[_bw.step], d = _bw.data;
  const dots = BW_STEPS.slice(1, 5).map((_, i) => `<span class="bw-dot ${_bw.step - 1 === i ? "on" : _bw.step - 1 > i ? "did" : ""}"></span>`).join("");
  let body = "";
  if (s === "intro") body = `
    <div class="bw-kick">Your chart × the market</div>
    <h2 class="bw-h">The sky you were born under, read against every stock on the exchange.</h2>
    <p class="bw-p">Give the desk your birth details and it casts your Vedic (sidereal) chart, then reads the whole PSX universe against it the way the tradition would — which names your chart runs <b>harmonious</b> with, which it finds <b>testing</b>, and the periods your own dasha lights up.</p>
    <p class="bw-note">A note in plain sight: this is <b>astrological exploration</b>, not investment advice — a lens to explore, never a reason to buy. ${me
      ? "Your birth details stay private to your account."
      : "No account needed — your chart is cast in your browser and your birth details stay on this device until you choose to save them."}</p>
    <button class="bw-go" onclick="bwNext()">Begin →</button>`;
  else if (s === "date") body = `
    <div class="bw-kick">Step 1 of 4 · ${dots}</div>
    <h2 class="bw-h">When were you born?</h2>
    <p class="bw-p">The date sets your planets. Everything else refines it.</p>
    <input type="date" class="bw-in" id="bw-date" min="1950-01-01" max="2035-12-31" value="${esc(d.date || "")}" onchange="bwSet('date',this.value)">
    <div class="bw-nav"><button class="bw-back" onclick="bwBack()">← back</button><button class="bw-go" onclick="if(document.getElementById('bw-date').value){bwSet('date',document.getElementById('bw-date').value);bwNext()}">Next →</button></div>`;
  else if (s === "time") body = `
    <div class="bw-kick">Step 2 of 4 · ${dots}</div>
    <h2 class="bw-h">What time?</h2>
    <p class="bw-p">Your birth time sets the fast-moving Moon and your rising sign (ascendant). The more exact, the sharper the reading.</p>
    <input type="time" class="bw-in" id="bw-time" value="${esc(d.time || "")}" ${d.time_known === false ? "disabled" : ""} onchange="bwSet('time',this.value);bwSet('time_known',true)">
    <label class="bw-check"><input type="checkbox" ${d.time_known === false ? "checked" : ""} onchange="bwSet('time_known',!this.checked);const t=document.getElementById('bw-time');t.disabled=this.checked;if(this.checked){bwSet('time','12:00')}"> I don't know my birth time</label>
    <p class="bw-note">${d.time_known === false ? "No problem — your Moon sign anchors the reading, the way Vedic astrology reads a chart from the Moon (Chandra lagna)." : "Even an approximate time sharpens your rising sign. If you don't know it, tick the box above."}</p>
    <div class="bw-nav"><button class="bw-back" onclick="bwBack()">← back</button><button class="bw-go" onclick="bwNext()">Next →</button></div>`;
  else if (s === "place") body = `
    <div class="bw-kick">Step 3 of 4 · ${dots}</div>
    <h2 class="bw-h">Where?</h2>
    <p class="bw-p">Your birthplace fixes the horizon for your rising sign.</p>
    <input class="bw-in combo-city" id="bw-place" placeholder="Start typing a city…" autocomplete="off" value="${esc(d.place || "")}">
    <div id="bw-place-pop" class="bw-city-pop"></div>
    <div class="bw-tzrow"><label>UTC offset at birth <input type="number" step="0.5" class="bw-tz" id="bw-tz" value="${d.tz ?? 5}" onchange="bwSet('tz',+this.value)"></label>
      <span class="bw-note" style="margin:0">set from the city; adjust if you were born during daylight-saving</span></div>
    <div class="bw-nav"><button class="bw-back" onclick="bwBack()">← back</button><button class="bw-go" onclick="if(_bw.data.lat!=null){bwNext()}else{document.getElementById('bw-place').focus()}">Next →</button></div>`;
  else if (s === "goals") body = `
    <div class="bw-kick">Almost there</div>
    <h2 class="bw-h">What are you here to explore?</h2>
    <p class="bw-p">This only colours the language of your reading — pick what fits, or skip.</p>
    <div class="bw-opts">${[["growth", "Long-term growth"], ["income", "Dividend income"], ["trading", "Active trading"], ["curious", "Just curious"]].map(([k, l]) => `<button class="bw-opt ${d.goal === k ? "on" : ""}" onclick="bwSet('goal','${k}');document.querySelectorAll('.bw-opt').forEach(b=>b.classList.remove('on'));this.classList.add('on')">${l}</button>`).join("")}</div>
    <div class="bw-nav"><button class="bw-back" onclick="bwBack()">← back</button><button class="bw-go" onclick="bwNext()">See my chart →</button></div>`;
  else if (s === "cast") { renderBirthCast(ov); return; }
  ov.innerHTML = `<div class="bw-box"><button class="bw-x" onclick="bwClose()">✕</button>${body}</div>`;
  if (s === "place") wireCityCombo();
  if (s === "date") setTimeout(() => document.getElementById("bw-date")?.focus(), 40);
}

async function wireCityCombo() {
  const cd = await j("cities.json");
  const inp = document.getElementById("bw-place"), pop = document.getElementById("bw-place-pop");
  if (!inp) return;
  const render = q => {
    q = (q || "").toLowerCase().trim();
    const hits = (q ? (cd.cities || []).filter(c => c.name.toLowerCase().includes(q)) : (cd.cities || [])).slice(0, 30);
    pop.innerHTML = hits.map(c => `<div class="bw-city" data-name="${esc(c.name)}" data-lat="${c.lat}" data-lon="${c.lon}" data-tz="${c.tz}"><b>${esc(c.name)}</b><span>${esc(c.cc)}</span></div>`).join("");
    pop.style.display = hits.length ? "block" : "none";
  };
  inp.addEventListener("focus", () => render(inp.value));
  inp.addEventListener("input", () => render(inp.value));
  pop.addEventListener("click", e => {
    const it = e.target.closest(".bw-city"); if (!it) return;
    inp.value = it.dataset.name; bwSet("place", it.dataset.name); bwSet("lat", +it.dataset.lat); bwSet("lon", +it.dataset.lon); bwSet("tz", +it.dataset.tz);
    const tz = document.getElementById("bw-tz"); if (tz) tz.value = it.dataset.tz;
    pop.style.display = "none";
  });
}

async function renderBirthCast(ov) {
  const d = _bw.data;
  // compute the chart UP FRONT (it's fast, <100ms) so the success reveal has real values to show
  // and myProfile is set the instant the loader lands — the loader is theatre over ready data.
  const cast = await computeNatal(d);
  const castErr = cast.error || null;
  if (!castErr) {
    const rec = { birth_data: d, natal_chart: cast, astro_prefs: { goal: d.goal } };
    if (me) { myProfile = { ...(myProfile || {}), ...rec }; saveProfile(rec); }  // persist in background
    else setGuestChart(rec);                                                     // guest: this device only
  }
  const steps = [
    `Placing the nine grahas — sidereal, Lahiri ayanamsa`,
    d.time_known === false ? `Reading your Moon and its nakshatra` : `Rising sign from ${esc(d.place)} at ${esc(d.time)}`,
    `Balancing your Vimshottari dasha from the Moon's nakshatra`,
    `Reading all ${103} PSX charts against yours — Tara, friendship, dasha`,
    `Ranking the market by resonance with your chart`,
  ];
  runRevealModal({
    sym: "", kicker: "Casting your chart", title: "Reading the market against your stars",
    sub: "Real sidereal math on your birth chart, then the tradition's compatibility techniques across every name on the exchange.",
    steps, flagKey: null,
    // the ONE exit: navigate to the reading (myProfile already holds the chart)
    onClose: () => { if (location.hash.replace(/^#\/?/, "").startsWith("mychart")) pageMyChart(); else location.hash = "#/mychart"; },
    renderReveal: (bodyEl) => {
      if (castErr) {
        bodyEl.innerHTML = `<div class="rp-reveal"><div class="rp-reveal-head"><b>Couldn't cast the chart</b><span>${esc(castErr)}</span></div>
          <div class="empty" style="padding:16px">Check your birth date is between 1950 and 2035, then try again.</div>
          <div class="rp-reveal-foot"><span></span><span class="rp-foot-btns"><button class="rp-btn2" onclick="this.closest('.replay-overlay').querySelector('.replay-x').click();openBirthWizard()">Edit details</button></span></div></div>`;
        return;
      }
      const moon = cast?.grahas?.Moon, cur = cast?.dasha?.current;
      bodyEl.innerHTML = `<div class="rp-reveal cast-done">
        <div class="cast-tick">✓</div>
        <h2 class="cast-h">Your chart is cast, and the market is matched.</h2>
        <p class="cast-p">The desk placed your nine grahas${moon ? `, found your Moon in <b>${esc(moon.sign)} · ${esc(moon.nakshatra)}</b>` : ""}${cur ? `, balanced your <b>${esc(cur.lord)}</b> period` : ""}, and read all 104 PSX names against your stars.</p>
        <div class="cast-stats">
          <div><span>${moon ? esc(moon.sign) : "—"}</span><i>your Moon sign</i></div>
          <div><span>${cur ? esc(cur.lord) : "—"}</span><i>your current period</i></div>
          <div><span>104</span><i>names matched</i></div>
        </div>
        <button class="bw-go cast-go" onclick="this.closest('.replay-overlay').querySelector('.replay-x').click()">See my reading →</button>
        <p class="cast-note">Astrological exploration, not advice. ${me
          ? "Saved privately to your account — edit any time in Settings."
          : "Your chart is on this device only. Create a free account to keep it and read it from anywhere."}</p>
      </div>`;
    },
  });
  ov.remove();
}

async function pageMyChart() {
  // yield one microtask: the initial route() runs before `let me` initializes further down the
  // file, and unlike other pages this one reads `me` before its first data await. This defers that
  // read past the synchronous module evaluation, avoiding a temporal-dead-zone error on cold load.
  await Promise.resolve();
  const bd = birthData(), nc = natalChart();
  if (!bd || !nc || nc.error) {
    $("view").innerHTML = `<div class="seg" style="margin-top:4px"><h2>Your chart</h2><div class="ln"></div><span class="pill">personal</span></div>
      <div class="disclaimer">Astrological exploration, not investment advice. A lens to read your own chart against the market — never a reason to buy.</div>
      <div class="card mychart-cta">
        <div class="mc-hero">${["Sun", "Moon", "Jupiter", "Saturn"].map(b => pixelGlyph(b, 30)).join("")}</div>
        <h2>Read the whole market against your birth chart</h2>
        <p class="sub">Vedic astrology has always matched two charts for compatibility. The desk turns that on the market: give it your birth details and it reads every PSX name against your stars — which your chart runs harmonious with, which it finds testing, and the periods your own dasha lights up.</p>
        <button class="bw-go" onclick="openBirthWizard()">Cast my birth chart →</button>
        <p class="sub" style="margin-top:10px;opacity:.7">Takes a minute. Your birth details stay private to your account.</p>
      </div>`;
    return;
  }
  const [uni, sectors, amap, natalAll, astroNow] = await Promise.all([
    j("universe.json"), j("sectors.json"), j("astro_map.json"), j("astro_natal.json"), j("astro.json")]);
  const names = uni?.symbols || {};
  const cur = nc.dasha?.current || {};
  const locked = !isSubscribed();
  // the daily layer: today's sky over this chart, and the dates it next re-deals
  const sky = await skyOn(Date.now()).catch(() => null);
  const goch = sky ? gocharaRead(nc, sky, amap) : null;
  const shifts = (goch && !locked) ? await upcomingShifts(nc).catch(() => []) : [];
  // score every ticker
  const scored = Object.keys(names).map(sym => {
    const stock = natalAll?.subjects?.[sym];
    const sector = (sectors?.tickers?.[sym] || {}).sector;
    const r = synastry(nc, stock, sector, amap, astroNow);
    return { sym, name: names[sym]?.name || "", sector, hasChart: !!stock, timing: stockTiming(nc, stock, sector, amap), ...r };
  }).filter(x => x.score != null).sort((a, b) => b.score - a.score);
  // curated slices, not threshold dumps — the strongest handful each way, so "harmonious" stays meaningful
  const harmon = scored.filter(x => x.score >= 58).slice(0, 8);
  const testing = scored.filter(x => x.score <= 44).slice(-6).reverse();
  const moon = nc.grahas.Moon, asc = nc.ascendant;
  const gl = goalLens();
  // commodities, scored against the chart the same way chartless stocks are
  const comm = COMMODITIES.map(c => ({ ...c, ...resonanceWithGraha(nc, c.sig, c.name) }))
    .filter(c => c.score != null).sort((a, b) => b.score - a.score);

  // The wall lands where desire peaks: a guest reads their real chart and their strongest few
  // matches in full, then sees that a ranked map of the whole exchange exists behind it.
  const lockCard = (kicker, what) => `<div class="card mc-lock">
    <div class="mc-lock-blur" aria-hidden="true">${scored.slice(FREE_MATCHES, FREE_MATCHES + 4).map(x =>
      `<div class="mc-lock-row"><b>${esc(x.sym)}</b><span class="sub">${esc((x.sector || "").slice(0, 18))}</span><span class="num">${x.score}</span></div>`).join("")}</div>
    <div class="mc-lock-face">
      <div class="mc-lock-kick">${esc(kicker)}</div>
      <h3>${esc(what)}</h3>
      <p class="sub">${me
        ? "Your full reading — every name on the exchange ranked against your chart, your commodities, your timing windows, and the sky read against your chart each day."
        : "Create a free account to keep the chart you just cast. Unlock the full reading to see every name on the exchange ranked against it, your commodities, your timing windows, and the sky read against your chart each day."}</p>
      <button class="bw-go" style="max-width:260px" onclick="${me ? "location.hash='#/settings'" : "openAuth('signup')"}">${me ? "Unlock my full reading →" : "Create a free account →"}</button>
      ${me ? "" : `<p class="sub" style="margin-top:8px;opacity:.7">Already have one? <a href="#" onclick="openAuth('signin');return false" style="color:var(--accent)">Sign in</a></p>`}
    </div></div>`;

  const rowCard = (x) => {
    const tm = x.timing;
    return `<div class="card syn-card"><div class="syn-head clickable" onclick="location.hash='#/ticker/${esc(x.sym)}'">
      <span class="syn-score s-${x.verdict.replace(/\s/g, "")}">${x.score}</span>
      <div><b>${esc(x.sym)}</b> <span class="sub">${esc((x.name || "").slice(0, 26))}</span><div class="sub">${esc(x.sector || "")}${x.hasChart ? "" : " · sector reading"}</div></div>
      <span class="pill ${x.verdict === "harmonious" || x.verdict === "favourable" ? "ok" : x.verdict === "testing" || x.verdict === "discordant" ? "bad" : ""}">${esc(x.verdict)}</span></div>
    <div class="syn-why">${x.reasons.slice(0, 3).map(r => `<div class="syn-r ${r.w > 0 ? "up" : r.w < 0 ? "dn" : ""}"><b>${esc(r.k)}</b> ${esc(r.why)}</div>`).join("")}
    ${tm ? `<div class="syn-time"><span class="dt-glyph">${pixelGlyph(tm.windows[0].lord, 14)}</span> <b>The tradition's timing:</b> your ${esc(tm.windows[0].lord)} period (${tm.windows[0].from.slice(0, 4)}–${tm.windows[0].to.slice(0, 4)}) is when your chart most resonates with ${esc(x.sym)}${tm.windows[1] ? `, again under ${esc(tm.windows[1].lord)} from ${tm.windows[1].from.slice(0, 4)}` : ""}. A rhythm, not a date to act on.</div>` : ""}</div></div>`;
  };

  // ---- "Today, against your chart" — the section that is different every single day ----
  const ord = n => n === 1 ? "1st" : n === 2 ? "2nd" : n === 3 ? "3rd" : n + "th";
  let todaySection = "";
  if (goch) {
    const gTile = t => `<div class="goch-tile ${t.tag === "favourable" ? "up" : t.tag === "testing" ? "dn" : ""}">
      <div class="goch-top"><span class="dt-glyph">${pixelGlyph(t.g, 16)}</span><b>${esc(t.g)}</b><span class="pill ${t.tag === "favourable" ? "ok" : t.tag === "testing" ? "bad" : ""}">${t.tag}</span></div>
      <div class="sub">in ${esc(t.sign)} — your ${ord(t.house)} from the Moon${t.conj ? ` · <b>crossing your natal ${esc(t.conj)}</b>` : ""}${t.domains ? ` · ${esc(t.domains)}` : ""}</div></div>`;
    const shiftLine = s => s.kind === "antar" ? `your sub-period turns to <b>${esc(s.body || "")}</b> — your readings and commodities re-rank`
      : s.kind === "maha" ? `your <b>${esc(s.body || "")}</b> maha-dasha closes — a new long chapter opens`
      : `<b>${esc(s.body)}</b> enters ${esc(s.sign)} — your ${ord(s.house)} from the Moon, traditionally ${s.fav ? "favourable" : "a quieter seat"}`;
    const big = shifts.find(s => s.kind === "ingress" && ["Jupiter", "Saturn", "Rahu"].includes(s.body));
    const list = shifts.slice(0, 4);
    if (big && !list.includes(big)) list.push(big);
    todaySection = `
  <div class="seg"><h2>Today, against your chart</h2><div class="ln"></div><span class="pill">${new Date().toISOString().slice(0, 10)} · refreshes daily</span></div>
  <p class="sub" style="margin-bottom:12px">Gochara — the tradition reads the moving sky from your natal Moon. The nine grahas that stood still the moment you were born have kept moving; this is where each stands over your chart <b>today</b>. A daily lens for exploration, never a signal.</p>
  ${locked
    ? `<div class="goch-grid">${goch.tiles.filter(t => t.g === "Moon").map(gTile).join("")}</div>
       ${planWall("The daily sky, read against your chart",
      "All nine grahas placed from your Moon and refreshed every day, the days they cross your natal points — and the dates the sky next re-deals your chart, so you know exactly when to look again.")}`
    : `<div class="goch-grid">${goch.tiles.map(gTile).join("")}</div>
       ${goch.sadeSati ? `<div class="disclaimer">Saturn is moving through the signs around your natal Moon — the stretch tradition calls <b>Sade Sati</b> and reads as slow-earned lessons. A weather report from the tradition, not a verdict.</div>` : ""}
       ${list.length ? `<div class="card next-look"><div class="mc-lock-kick">worth another look</div>
        ${list.map(s => `<div class="nl-row"><b class="num">${esc(s.date)}</b><span>${shiftLine(s)}</span></div>`).join("")}
        <p class="sub" style="margin-top:8px">The sky re-deals a little every day — these are the dates it re-deals <b>your</b> chart meaningfully. Each is worth a fresh read.</p></div>` : ""}`}`;
  }

  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Your chart</h2><div class="ln"></div><span class="pill">${esc(bd.place || "")} · ${esc(bd.date || "")}</span></div>
  <div class="disclaimer">Astrological exploration, <b>not investment advice</b>. A lens to read your chart against the market as the tradition would — never a recommendation to buy or a forecast of profit.</div>

  <div class="card">
    <div class="mc-chart-top"><div>
      <div class="ark">Your Moon</div><b style="font-size:18px">${esc(moon.sign)} · ${esc(moon.nakshatra)}</b>
      <div class="sub">${asc ? `Rising sign ${esc(asc.sign)}` : "Chandra lagna · a Moon-led chart"}</div>
    </div>
    <div><div class="ark">Your current period</div><b style="font-size:18px">${pixelGlyph(cur.lord, 18)} ${esc(cur.lord || "—")}${cur.antar ? ` / ${esc(cur.antar)}` : ""} dasha</b>
      <div class="sub">${cur.antar ? `${esc(cur.antar)} sub-period to ~${esc(String(cur.antar_to || "").slice(0, 7))} · ` : ""}${esc(cur.lord || "")} maha to ~${esc(String(cur.to || "").slice(0, 7))}</div></div>
    </div>
    ${natalOrrery(nc.grahas, asc, sky)}
    <p class="sub" style="margin-top:6px;text-align:center">Your birth sky — the nine grahas at the moment you were born${sky ? ", with <b>today's sky</b> faint on the outer ring. It drifts a little every day" : ""}. Sidereal, Lahiri.</p>
    ${gl.line ? `<p class="sub goal-line" style="text-align:center;margin-top:4px">You're here for <b>${esc(gl.label)}</b>. ${esc(gl.line)}</p>` : ""}
  </div>
  ${todaySection}

  <div class="seg"><h2>Your timing — the map of when</h2><div class="ln"></div><span class="pill">Vimshottari</span></div>
  <p class="sub" style="margin-bottom:12px">Vedic astrology divides a life into planetary periods (dashas), and each into sub-periods (antardashas). Each, tradition says, colours the time it rules. This is your ribbon — the long arc above, the nearer sub-periods below. A rhythm to understand your chart by, <b>never</b> a schedule to trade on.</p>
  <div class="card">${dashaTimeline(nc, amap)}${antardashaStrip(nc, amap)}</div>

  <div class="seg"><h2>The market your chart favours</h2><div class="ln"></div><span class="pill ok">your strongest</span></div>
  <p class="sub" style="margin-bottom:12px">The names the tradition reads as most in tune with your chart — by Moon-star compatibility (Tara), the friendship of your ruling planets, and your running dasha. High resonance means astrological harmony, <b>not</b> a prediction of gains.</p>
  ${(locked ? harmon.slice(0, FREE_MATCHES) : harmon).map(rowCard).join("") || '<div class="card"><div class="empty">Nothing scores strongly harmonious — your chart sits neutral to most of the market.</div></div>'}
  ${locked ? lockCard("the rest of your map", `${scored.length - FREE_MATCHES} more names, ranked against your chart`) : ""}

  ${locked ? "" : `<div class="seg"><h2>The names that test your chart</h2><div class="ln"></div><span class="pill bad">most friction</span></div>
  <p class="sub" style="margin-bottom:12px">Where the tradition reads friction between your chart and the stock's. Not "avoid" — friction, in astrology, is simply a harder resonance to work with.</p>
  ${testing.map(rowCard).join("") || '<div class="card"><div class="empty">Nothing scores strongly discordant.</div></div>'}

  <div class="seg"><h2>Commodities &amp; metals</h2><div class="ln"></div><span class="pill">${comm.length} read</span></div>
  <p class="sub" style="margin-bottom:12px">Gold, silver, oil and the crops carry their own rulers in the tradition — read against your chart the same way. ${gl.grahas.length ? `For <b>${esc(gl.label)}</b>, the tradition would look first to ${gl.grahas.map(esc).join(", ")}.` : ""}</p>
  <div class="comm-grid">${comm.map(c => `<div class="comm-card ${c.verdict === "harmonious" || c.verdict === "favourable" ? "up" : c.verdict === "testing" || c.verdict === "discordant" ? "dn" : ""}">
    <div class="comm-top"><span class="comm-glyph">${pixelGlyph(c.glyph, 20)}</span><b>${esc(c.name)}</b><span class="comm-score">${c.score}</span></div>
    <div class="sub comm-note">${esc(c.note)}. <b>${esc(c.verdict)}</b> with your chart — ${esc((c.reasons[0] || {}).why || "")}</div></div>`).join("")}</div>

  <div class="seg"><h2>Your whole-market map</h2><div class="ln"></div><span class="pill">${scored.length} names ranked</span></div>
  <div class="card" style="padding:0"><table><thead><tr><th>Stock</th><th>Sector</th><th class="r">Resonance</th><th>Tradition's read</th></tr></thead><tbody>${
    scored.map(x => `<tr class="clickable" onclick="location.hash='#/ticker/${esc(x.sym)}'"><td><b>${esc(x.sym)}</b></td><td class="sub">${esc((x.sector || "").slice(0, 20))}</td>
      <td class="r num ${x.score >= 60 ? "up" : x.score <= 40 ? "dn" : ""}">${x.score}</td><td class="sub">${esc(x.verdict)}</td></tr>`).join("")}</tbody></table></div>`}

  <p class="sub" style="margin-top:14px"><button class="note-save" onclick="openBirthWizard()">Edit my birth details</button> · Your resonance map is astrological interpretation — a lens for exploration and your own decisions, never advice.</p>`;
}

/* ---------- Astro: the sky, computed — and the test that says it doesn't predict anything.
   The null result LEADS. The calendar is the secondary thing, offered as calendar, not signal.
   This page exists because we tested it, not because we believe it. ---------- */
async function pageAstro() {
  const [a, natal, amap, sectors, uni] = await Promise.all([
    j("astro.json"), j("astro_natal.json"), j("astro_map.json"),
    j("sectors.json"), j("universe.json")]);
  if (!a || a.status !== "ok") {
    $("view").innerHTML = `<div class="seg" style="margin-top:4px"><h2>Astro</h2><div class="ln"></div></div>
      <div class="card"><div class="empty">The sky is unavailable this cycle${a?.error ? ` (${esc(a.error)})` : ""}. Check back shortly.</div></div>`;
    return;
  }
  const sys = a.system || {};

  // ---- your charts: the board. Nothing shows until the desk is RUN on it (same discipline
  // as the strategy board) — the casting is the experience.
  const board = astroBoard();
  const names = uni?.symbols || {};
  const verifiedOf = s => !!natal?.subjects?.[s];
  const tiles = board.map(s => { const ran = astroRunOn(s);
    return `<div class="sb-tile clickable" onclick="if(!event.target.closest('.sb-x'))location.hash='#/ticker/${esc(s)}'">
      <button class="sb-x" data-abdel="${esc(s)}" title="Remove ${esc(s)}" aria-label="remove ${esc(s)}">✕</button>
      <b>${esc(s)}</b><span class="sb-nm">${esc((names[s]?.name || "").slice(0, 24))}</span>
      <span class="pill ${ran ? (verifiedOf(s) ? "ok" : "") : "wait"}">${ran ? (verifiedOf(s) ? "natal chart" : "sector reading") : "waiting for a cast"}</span>
    </div>`; }).join("");
  const addTile = `<div class="sb-tile sb-add">
      <span class="sk">Add a stock</span>
      <input id="ab-tkr" class="ph-in combo" placeholder="e.g. UBL" autocomplete="off" onkeydown="if(event.key==='Enter'&&!document.querySelector('.combo-opt.on'))addAstroTicker()">
      <button class="note-save" onclick="addAstroTicker()">Add to board</button>
    </div>`;
  const pendingA = board.filter(s => !astroRunOn(s));
  const runBarA = board.length ? `<button class="run-desk run-strat ${pendingA.length ? "" : "ran"}" onclick="playAstroBoardRun()">
    <span class="run-ico">▶</span>
    <span class="run-txt"><b>${pendingA.length ? `Cast the charts for your ${board.length} stock${board.length > 1 ? "s" : ""}` : `Cast your ${board.length} chart${board.length > 1 ? "s" : ""} again`}</b><i>Real ephemeris math against today's sky — birth charts, Vimshottari periods, Saturn's passage, transits to natal points. The tradition's reading of each name.</i></span>
    <span class="run-meta"><span class="run-last">Sky as of · ${esc((a.updated || "").slice(0, 10))}</span><span class="run-go">${pendingA.length ? "Cast ›" : "Cast again ›"}</span></span>
  </button>` : "";
  const dataPack = { natal, sky: a, amap, sectors, uni };
  const readings = board.filter(astroRunOn).map(s =>
    `<div class="card ar-card">${composeAstroReading(s, dataPack)}</div>`).join("");
  const boardStub = board.length && pendingA.length === board.length
    ? `<div class="card"><div class="empty">Your readings land here — hit <b>Cast ›</b> above and the desk works each chart against today's sky.</div></div>` : "";
  const sTile = (label, val, sub, k) => `<div class="sumtile"><span class="sk">${label}</span><b class="${k || ""}">${val}</b>${sub ? `<i>${sub}</i>` : ""}</div>`;

  // today's sky — the almanac
  const pos = a.positions || {};
  const skyRows = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"].map(b => {
    const p = pos[b]; if (!p) return "";
    return `<tr><td><b>${esc(b)}</b></td><td>${esc(p.sign)} <span class="sub">${p.deg_in_sign}°</span></td>
      <td class="sub">${esc(p.nakshatra)} <span style="opacity:.6">pada ${p.pada}</span></td>
      <td class="r">${p.retrograde ? '<span class="tag">retrograde</span>' : ""}</td></tr>`;
  }).join("");

  const evs = (a.events || []).filter(e => e.importance >= 3).slice(0, 14);
  const evRows = evs.map(e => `<tr><td class="num">${esc(e.date)}</td>
    <td><b>${esc(e.text)}</b></td>
    <td class="r"><span class="pill ${e.importance >= 5 ? "bad" : ""}">${e.importance >= 5 ? "rare" : e.importance >= 4 ? "material" : "notable"}</span></td></tr>`).join("");

  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Astro</h2><div class="ln"></div><span class="pill">the sky, read</span></div>
  <div class="disclaimer">Real charts and real sidereal ephemeris math. Astrological exploration — never a signal, a prediction, or advice.</div>

  <div class="seg"><h2>Your charts</h2><div class="ln"></div><span class="pill">${board.length ? board.length + " on the board" : "empty"}</span></div>
  <div class="card">
    <div class="sb-grid">${tiles}${addTile}</div>
    <span id="ab-msg" class="sub" style="display:block;margin-top:8px"></span>
    ${!me && board.length ? `<span class="sub" style="display:block;margin-top:4px">Your board lives in this session only — <a style="color:var(--accent);cursor:pointer" onclick="openAuth('signup')">sign in</a> to keep it.</span>` : ""}
  </div>
  ${runBarA}
  ${boardStub}
  ${readings}

  <div class="sumstrip" style="grid-template-columns:repeat(4,1fr);margin-top:16px">
    ${sTile("Zodiac", "Sidereal", "Lahiri (Chitrapaksha)", "")}
    ${sTile("Ayanamsa", (sys.ayanamsa_deg ?? "—") + "°", "the current precession", "")}
    ${sTile("Grahas", "9", "the classical set", "")}
    ${sTile("Sky as of", esc((a.updated || "").slice(0, 10)), "recomputed every day", "")}
  </div>

  <div class="seg"><h2>The sky right now</h2><div class="ln"></div><span class="pill">sidereal · Lahiri</span></div>
  <div class="card" style="padding:0"><table><thead><tr><th>Graha</th><th>Sign</th><th>Nakshatra</th><th class="r"></th></tr></thead><tbody>${skyRows}</tbody></table></div>
  <p class="sub" style="margin-top:8px">Where the nine grahas stand today — sidereal positions, Lahiri ayanamsa.</p>

  ${evs.length ? `<div class="seg"><h2>What the sky does next</h2><div class="ln"></div><span class="pill">${a.horizon_days} days</span></div>
  <div class="card" style="padding:0"><table><thead><tr><th>Date</th><th>Event</th><th class="r">Rank</th></tr></thead><tbody>${evRows}</tbody></table></div>
  <p class="sub" style="margin-top:8px">The dated turns in the sky over the coming weeks — ingresses, stations, eclipses and moons, ranked by weight. An almanac.</p>` : ""}`;
}

function maxDrawdown(bars) {
  // returns {mdd%, peakDate, troughDate} over the given bars
  let peak = bars[0]?.close || 0, peakDate = bars[0]?.date, mdd = 0, pk = peak, pkd = peakDate, td = peakDate;
  for (const b of bars) {
    if (b.close > pk) { pk = b.close; pkd = b.date; }
    const dd = b.close / pk - 1;
    if (dd < mdd) { mdd = dd; peakDate = pkd; td = b.date; }
  }
  return { mdd: mdd * 100, peakDate, troughDate: td };
}
function behaviorStats(hist) {
  const c = hist.map(h => h.close);
  const rets = c.slice(1).map((v, i) => v / c[i] - 1);
  const upDays = rets.filter(r => r > 0).length;
  const full = maxDrawdown(hist);
  // recent-era drawdown (last ~10 years) — the number that actually describes today's risk,
  // separate from a decades-old crisis extreme
  const cutoff = new Date(); cutoff.setFullYear(cutoff.getFullYear() - 10);
  const cut = cutoff.toISOString().slice(0, 10);
  const recentBars = hist.filter(b => b.date >= cut);
  const recent = recentBars.length > 30 ? maxDrawdown(recentBars) : full;
  return {
    total: (c[c.length - 1] / c[0] - 1) * 100,
    mdd: full.mdd, mddPeak: full.peakDate, mddTrough: full.troughDate,
    mddRecent: recent.mdd, mddRecentTrough: recent.troughDate,
    upPct: upDays / rets.length * 100,
    avgAbs: rets.reduce((a, r) => a + Math.abs(r), 0) / rets.length * 100,
    best: Math.max(...rets) * 100,
    worst: Math.min(...rets) * 100,
  };
}
function yr(d) { return (d || "").slice(0, 4); }

/* The test log — every strategy tested on a ticker written out in plain English, pass AND fail,
   with the exact reason each one made or missed the bar. Composed from backtests.json + the
   library's own descriptions, so it can never claim more than the numbers say. */
function renderTestLog(sym, allTested, lib, cfg) {
  if (!allTested.length) return "";
  const descs = {}; (lib?.strategies || []).forEach(s => { descs[s.id] = s; });
  const c = cfg || {};
  const minHit = (c.min_hit_rate ?? 0.55) * 100, minNet = c.min_net_expectancy_pct ?? 0.5,
    fric = c.friction_pct ?? 0.6, minN = c.min_trades ?? 8;
  // one decimal, trailing .0 dropped — rounding to whole percent made the verdict read as a
  // contradiction ("54.9% rejected for being below the 55% bar" showed as "55% below 55%")
  const pct = v => v == null ? "—" : (Math.round(v * 1000) / 10).toFixed(1).replace(/\.0$/, "") + "%";
  const entry = t => {
    const d = descs[t.id] || {}, oos = t.oos || {};
    const oosNet = (oos.avg_return_pct ?? 0) - fric;
    const why = [];
    if (t.n < minN) why.push(`it only triggered ${t.n} time${t.n === 1 ? "" : "s"} — under the ${minN}-trade minimum, too thin a sample to trust`);
    if ((t.hit_rate ?? 0) < minHit / 100) why.push(`its ${pct(t.hit_rate)} win rate is below the ${minHit.toFixed(0)}% bar`);
    if ((t.net_expectancy_pct ?? -99) < minNet) why.push(`after ${fric}% costs each trade averages ${sgn(t.net_expectancy_pct)}%, short of the +${minNet}% the desk demands`);
    if (!(oos.n >= 3 && oosNet > 0)) why.push(oos.n >= 3 ? `it stopped working out-of-sample (${sgn(oosNet.toFixed(2))}% net on the unseen last third)` : `it left only ${oos.n || 0} out-of-sample trades — not enough to prove it still works on unseen data`);
    return `<div class="tl-row ${t.eligible ? "pass" : "fail"}">
      <div class="tl-head"><b>${esc(t.name || t.id)}</b><span class="tag">${esc((t.category || "").replace(/_/g, " "))}</span>
        <span class="tl-verdict ${t.eligible ? "up" : ""}">${t.eligible ? "PROVEN" : "rejected"}</span></div>
      ${d.description ? `<p class="tl-rule"><i>The rule:</i> ${esc(d.description)}${d.target_pct != null ? ` Takes profit at +${d.target_pct}%, stops out at −${d.stop_pct}%, gives up after ${d.hold} sessions.` : ""}</p>` : ""}
      <p class="tl-p">On ${esc(sym)}'s own history this triggered <b>${t.n}</b> time${t.n === 1 ? "" : "s"} and won <b>${pct(t.hit_rate)}</b> of them. The average trade made <b>${sgn(t.avg_return_pct)}%</b> before costs — <b class="${(t.net_expectancy_pct ?? 0) > 0 ? "up" : "dn"}">${sgn(t.net_expectancy_pct)}%</b> after the desk's ${fric}% friction assumption.${t.payoff_ratio != null ? ` Its average win was <b>${t.payoff_ratio}×</b> its average loss.` : ""}${t.worst_pct != null ? ` The worst single trade lost <b>${Math.abs(t.worst_pct)}%</b>.` : ""} Out-of-sample — the last third of the history, which the rule never saw while being judged — it took <b>${oos.n || 0}</b> trade${oos.n === 1 ? "" : "s"}${oos.n ? ` and won <b>${pct(oos.hit_rate)}</b>` : ""}.</p>
      <p class="tl-why">${t.eligible
        ? `<b class="up">Cleared every bar</b> — win rate above ${minHit.toFixed(0)}%, positive expectancy after costs, and still profitable on data it had never seen. The desk will use it on ${esc(sym)}.`
        : `<b>Rejected</b> because ${why.slice(0, 2).join(", and ")}. The desk won't signal ${esc(sym)} on this rule — a strategy that works elsewhere doesn't get a pass here.`}</p>
    </div>`;
  };
  const passed = allTested.filter(t => t.eligible), failed = allTested.filter(t => !t.eligible);
  return `<details class="testlog">
    <summary><b>The full test log</b><span class="sub">all ${allTested.length} strategies tested on ${esc(sym)} — what each rule is, what it did, and exactly why it passed or failed</span><span class="dict-arrow">▾</span></summary>
    <div class="tl-wrap">
      <p class="tr-intro">Every rule below was run bar-by-bar across ${esc(sym)}'s own price history — no peeking ahead, costs deducted, and then re-checked on the last third of the data it had never seen. The failures are published for the same reason as the passes: a library that only shows its winners is a sales pitch, not a test.</p>
      ${passed.length ? `<div class="tl-sec">${passed.length} cleared the bar</div>${passed.map(entry).join("")}` : ""}
      ${failed.length ? `<div class="tl-sec">${failed.length} rejected</div>${failed.map(entry).join("")}` : ""}
    </div>
  </details>`;
}

/* The full session transcript — every analyst's turn, in the order they spoke, with everything
   they actually wrote (including the fields the summary view leaves out). For people who want to
   read the desk's working rather than its verdict. Pure render of the stored session: no agent runs. */
function renderTranscript(room, sym) {
  const ta = room.ta_memo || {}, fa = room.fa_memo || {}, bull = room.bull_case || {}, bear = room.bear_case || {};
  const stanceClass = s => ({ constructive: "up", cautious: "dn", neutral: "", unclear: "", near_fair: "" }[s] || "");
  const P = t => t ? `<p class="tr-p">${esc(t)}</p>` : "";
  const UL = a => (a || []).length ? `<ul class="tr-ul">${a.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : "";
  const NOTE = (label, t) => t ? `<div class="tr-note"><span>${label}</span>${esc(t)}</div>` : "";
  const facts = arr => { const f = arr.filter(x => x[1] != null && x[1] !== "" && x[1] !== "—");
    return f.length ? `<div class="tr-facts">${f.map(([k, v]) => `<span><i>${k}</i> <b>${esc(String(v).replace(/_/g, " "))}</b></span>`).join("")}</div>` : ""; };
  const claimOf = m => m?.claim && (m.claim.text || m.claim.direction)
    ? `<div class="tr-claim"><span>On the record</span>${esc(m.claim.text || `${sym} ${m.claim.direction}${m.claim.horizon_days ? ` within ${m.claim.horizon_days} sessions` : ""}`)}${m.claim.hist_hit_rate ? ` <i>(this pattern has worked ${esc(m.claim.hist_hit_rate)} of the time historically)</i>` : ""}</div>` : "";
  const turn = (av, name, role, stance, body) => `<div class="tr-turn">
    <div class="tr-rail"><span class="tr-av">${av}</span></div>
    <div class="tr-body"><div class="tr-head"><b>${name}</b><span class="tr-role">${role}</span>${stance ? `<span class="stance ${stanceClass(stance)}">${esc(stance)}</span>` : ""}</div>${body}</div>
  </div>`;

  return `<details class="room-transcript">
    <summary>The full transcript — read the desk's actual working, turn by turn <span class="exhint">click to expand</span></summary>
    <div class="tr-wrap">
      <p class="tr-intro">The session ran on <b>${esc(String(room.built || room.dossier_asof || "").slice(0, 16))}</b> against ${esc(sym)}'s dossier at Rs ${fmt(room.price_at_session)}. The two desks work <b>in isolation</b> — the chartist never sees the fundamentals, and the fundamentalist never sees the chart — so when they agree, they agree independently. Then a bull and a bear are told to argue, hard. Nothing below is edited.</p>

      ${turn("MC", "Meher", "The Chartist · technical desk · spoke first", ta.technical_stance,
        P(ta.read) + facts([["structure", ta.structure], ["momentum", ta.momentum], ["support", ta.levels?.support != null ? fmt(ta.levels.support) : null], ["resistance", ta.levels?.resistance != null ? fmt(ta.levels.resistance) : null]])
        + NOTE("On liquidity", ta.liquidity_note)
        + ((ta.proven_now || []).length ? `<div class="tr-note"><span>Proven patterns firing on this bar</span>${ta.proven_now.map(esc).join(" · ")}</div>` : "")
        + claimOf(ta))}

      ${turn("DO", "Dr. Omar", "The Fundamentalist · fundamental desk · spoke second", fa.fundamental_stance,
        P(fa.read) + facts([["valuation", fa.valuation_stance]])
        + NOTE("Earnings quality", fa.earnings_quality) + NOTE("Dividend safety", fa.dividend_safety)
        + NOTE("Balance-sheet flags", Array.isArray(fa.balance_sheet_flags) ? fa.balance_sheet_flags.join(" · ") : fa.balance_sheet_flags)
        + NOTE("On the brokers", fa.broker_view) + claimOf(fa))}

      ${turn("ZB", "Zoya", "The Bull · argued the case FOR", "constructive",
        P(bull.thesis) + UL(bull.pillars) + NOTE("Her strongest evidence", bull.best_evidence)
        + NOTE("What would break her case", bull.what_would_break_it) + claimOf(bull))}

      ${turn("KB", "Khurram", "The Bear · argued the case AGAINST", "cautious",
        P(bear.thesis) + UL(bear.pillars) + NOTE("His attack on the bull", bear.attack_on_bull)
        + NOTE("His strongest evidence", bear.best_evidence)
        + NOTE("What would break his case", bear.what_would_break_it) + claimOf(bear))}

      ${room.qa ? turn("QA", "The Verifier", "QA · fact-checked the session against the data and live sources", "",
        `<div class="tr-note"><span>Verdict</span><b class="${room.qa.verdict === "clean" ? "up" : "dn"}">${esc(room.qa.verdict)}</b>${room.qa.checked ? ` · checked ${esc(room.qa.checked)}` : ""}</div>` + P(room.qa.note)) : ""}

      <div class="tr-close">↑ The Chair then weighed all of it into the <b>house view above</b> — with the dissent kept in, not smoothed away.</div>
    </div>
  </details>`;
}

/* The Desk Room — named AI-analyst personas debate a ticker (from state/rooms.json). */
function renderRoom(room, sym) {
  const head = `<div class="seg"><h2>The Desk Room</h2><div class="ln"></div><span class="pill">AI analysts · research, not advice</span></div>`;
  if (!room || !room.house_view) {
    return `${head}<div class="card"><div class="empty">No Room session for ${esc(sym)} yet. The desk's AI analysts — a technical desk, a fundamental desk, a bull, a bear and a chair — cover names in rotation (results, high-impact news and signals jump the queue). ${esc(sym)} is in the queue.</div></div>`;
  }
  const hv = room.house_view, ta = room.ta_memo || {}, fa = room.fa_memo || {}, bull = room.bull_case || {}, bear = room.bear_case || {};
  const convIdx = { low: 1, medium: 2, high: 3 }[hv.conviction] || 1;
  const convMeter = [1, 2, 3].map(i => `<span class="cvseg ${i <= convIdx ? "on" : ""}"></span>`).join("");
  const persona = (init, name, role) => `<div class="phead"><span class="pav">${init}</span><div><b>${name}</b><span class="prole">${role}</span></div></div>`;
  const memo = (init, name, role, stanceLabel, stance, body) =>
    `<div class="card room-memo"><div class="memo-top">${persona(init, name, role)}${stance ? `<span class="stance ${stance}">${esc(stanceLabel)}</span>` : ""}</div>${body}</div>`;
  const li = arr => (arr || []).map(x => `<li>${esc(x)}</li>`).join("");
  const stanceClass = s => ({ constructive: "up", cautious: "dn", neutral: "", unclear: "", near_fair: "" }[s] || "");

  const calls = (room.claims_ledger || []);
  return `${head}
  <p class="sub" style="margin:-4px 0 12px">Named AI analyst personas research and debate <b>${esc(sym)}</b>. The technical and fundamental desks work <b>separately</b>; a bull and a bear argue the case; the Chair synthesizes a house view with an explicit dissent. Every dated call below is scored against what actually happens. This is research, not advice.</p>

  <div class="card room-house">
    <div class="memo-top"><b style="font-size:12px;letter-spacing:.06em;text-transform:uppercase">The Chair — house view</b>
      <span class="conv">${room.qa ? `<span class="qabadge ${room.qa.verdict === "clean" ? "ok" : "warn"}" title="${esc(room.qa.note || "verified by the QA agent")}">QA ${esc(room.qa.verdict)}</span> · ` : ""}conviction <span class="cvmeter">${convMeter}</span> ${esc(hv.conviction || "")}</span></div>
    <p class="hv-summary">${esc(hv.summary || "")}</p>
    <div class="room-facts">
      <div><span>Dissent — the strongest case against this view</span><b>${esc(hv.dissent || "—")}</b></div>
      <div><span>Do the charts &amp; the fundamentals agree?</span><b>${esc((hv.ta_fa_alignment || "—").replace(/_/g, " "))}</b></div>
      <div><span>Do the brokers agree?</span><b>${esc((hv.broker_stance || "n/a").replace(/_/g, " "))}</b></div>
      <div><span>What to watch next</span><b>${esc(hv.watch_next || "—")}</b></div>
    </div>
  </div>

  ${renderTranscript(room, sym)}

  ${calls.length ? `<div class="card"><h2 style="font-size:12px">Dated calls on the record</h2><div class="sub">each is scored against what actually happens — this is how the desk (and, later, the brokers) are held accountable.</div>
    <table><thead><tr><th>Analyst</th><th>Call</th><th class="r">By</th><th class="r">Status</th></tr></thead><tbody>${
    calls.map(c => `<tr><td><b>${esc(c.source)}</b></td><td>${esc(c.claim?.text || "")}</td><td class="r num">${esc(c.resolve_by)}</td><td class="r"><span class="pill ${c.status === "hit" ? "ok" : c.status === "miss" ? "bad" : ""}">${esc(c.status)}</span></td></tr>`).join("")}</tbody></table></div>` : ""}`;
}

async function pageTicker(sym, _retry = 0) {
  sym = sym.toUpperCase();
  const [quant, bt, smap, uni, live, news, divs, fund, fscore, cal, hist, deep, intra, fvAll, roomsAll, claimsAll, researchIdx, explainAll, sigAll, stratLib, sectAll, smAll] = await Promise.all([
    j("quant.json"), j("backtests.json"), j("strategy_map.json"), j("universe.json"),
    j("live.json"), j("newslog.json"), j("dividends.json"), j("fundamentals.json"),
    j("fundamental_scores.json"), j("earnings_calendar.json"), j("history/" + sym + ".json", 300000),
    j("history_deep/" + sym + ".json", 600000), j("intraday/" + sym + ".json", 20000), j("fairvalue.json"), j("rooms.json"), j("claims.json"), j("research_index.json"), j("explainer.json"), j("signals.json"), j("strategy_library.json"), j("sectors.json"), j("sector_macro.json")]);
  const q = quant?.tickers?.[sym], u = uni?.symbols?.[sym], lv = live?.tickers?.[sym];
  const proven = (smap?.tickers?.[sym]) || [];
  const fsc = fscore?.tickers?.[sym];
  const fv = fvAll?.tickers?.[sym];
  const room = roomsAll?.[sym];
  // real PSX sector name — the feed only carries a numeric code ("0809"), so the old
  // `isNaN(lv.sector)` guard meant this tag never rendered for any ticker
  const mySector = (sectAll?.tickers?.[sym] || {}).sector || "";
  if (room) room.claims_ledger = (claimsAll?.claims || []).filter(c => c.ticker === sym);
  // broker calls on this ticker (from the weekly harvest) — the "real picture" from the houses
  const brokerDocs = ((researchIdx?.by_ticker?.[sym]) || []).filter(d => d.doc_type === "broker call");
  const brokerClaims = (claimsAll?.claims || []).filter(c => c.ticker === sym && c.source_type === "broker");
  const ex = explainAll?.[sym];
  const glance = ex ? (() => {
    const tile = (label, o) => o ? `<div class="glance-tile"><span class="glance-q">${label}</span><b>${esc(o.verdict)}</b><div class="sub">${esc(o.one_line)}</div></div>` : "";
    const rets = ex.return_by_year || [];
    const spark = rets.length ? `<div class="glance-tile"><span class="glance-q">Yearly price change</span>
      <div class="yearbars">${rets.map(r => `<div class="yb"><span class="ybbar ${r.ret_pct >= 0 ? "up" : "dn"}" style="height:${Math.min(100, Math.abs(r.ret_pct) / 2.2 + 6)}%"></span><i class="${cls(r.ret_pct)}">${r.ret_pct >= 0 ? "+" : ""}${Math.round(r.ret_pct)}%</i><em>${r.year.slice(2)}</em></div>`).join("")}</div></div>` : "";
    return `<div class="seg" style="margin-top:2px"><h2>At a glance</h2><div class="ln"></div><span class="pill">plain english</span></div>
    <div class="card"><div class="sub">The quick read for ${esc(sym)}${ex.name ? " (" + esc(ex.name) + ")" : ""} — is it healthy, is the price reasonable, and what changed. Educational, not advice.</div>
      <div class="glance-grid">
        ${tile("Is it healthy?", ex.health)}
        ${tile("Is the price reasonable?", ex.value)}
        ${tile("Which way is it moving?", ex.momentum)}
        ${tile("Does it pay income?", ex.income)}
        ${spark}
        <div class="glance-tile"><span class="glance-q">What changed recently</span>${(ex.what_changed || []).map(c => `<div class="sub" style="margin-bottom:3px">• ${esc(c)}</div>`).join("")}</div>
      </div></div>`;
  })() : "";
  // deep history (Yahoo, ~18y) preferred for chart + behavior; DPS as fallback
  const series = (deep && deep.length > (hist?.length || 0)) ? deep : hist;
  const yearsSpan = series ? ((new Date(series[series.length - 1].date) - new Date(series[0].date)) / 3.156e10) : 0;
  const f = fund?.tickers?.[sym] || {};
  const nextEarn = (cal?.events || []).find(e => e.ticker === sym && e.type === "results");
  const daysTo = d => d ? Math.ceil((new Date(d) - new Date()) / 86400000) : null;
  if (!series || !q) {
    // Almost always a transient fetch miss (the files exist server-side) — never dead-end.
    // Auto-retry a few times, and always give a manual Retry so the page can self-heal.
    const missing = !q ? "market data" : "price history";
    $("view").innerHTML = `<div class="card"><div class="empty">Couldn't load ${missing} for ${esc(sym)} just now.<br>
      <button class="acct-signin" id="tkretry" style="margin-top:12px">Retry</button></div></div>`;
    const btn = document.getElementById("tkretry");
    if (btn) btn.onclick = () => pageTicker(sym, 0);
    if (_retry < 3) setTimeout(() => { if (location.hash.toUpperCase().includes(sym)) pageTicker(sym, _retry + 1); }, 1200);
    return;
  }

  const px = lv?.current ?? q.close;
  const b = behaviorStats(series);
  const histYears = Math.max(1, Math.round(yearsSpan));
  const tickerNews = (news || []).filter(n => (n.tickers || []).includes(sym)).slice(-10).reverse();
  const dHist = (divs?.history || []).filter(d => d.symbol === sym);
  const dUp = (divs?.upcoming || []).filter(d => d.symbol === sym);
  const allTested = Object.entries(bt?.templates || {}).map(([id, per]) => ({ id, ...(per[sym] || {}) })).filter(t => t.n).sort((a, b) => (b.net_expectancy_pct ?? -99) - (a.net_expectancy_pct ?? -99));
  const provenIds = new Set(proven.map(p => p.id));
  const hasIntra = intra && intra.date === (live?.updated || "").slice(0, 10) && intra.points?.length > 3;

  // ---- educational / risk layer (all from the data layer; no advice language) ----
  const NUM = s => { const n = parseFloat(String(s).replace(/[^0-9.\-]/g, "")); return isNaN(n) ? null : n; };
  const epsN = NUM(f.eps), peN = NUM(f.pe), fpeN = NUM(f.forward_pe), betaN = NUM(f.beta),
    dyN = NUM(f.div_yield), payN = NUM(f.payout_ratio), niN = NUM(f.net_income);
  const tvv = q.avg_daily_traded_value || 0;
  const liq = tvv < 20e6 ? "low" : tvv < 150e6 ? "moderate" : "adequate";
  const vr = q.volatility_rank;
  const vol = vr == null ? null : vr < 20 ? "low" : vr < 50 ? "moderate" : "high";
  const peerFair = fv?.methods?.relative_pe;
  const peerRich = (peerFair != null && fv?.price) ? peerFair < fv.price : null;   // fair-vs-peers below price ⇒ priced above peers
  const mddAbs = Math.abs(b.mdd);
  const mddRecentAbs = Math.abs(b.mddRecent);
  const mddIsOld = yr(b.mddTrough) && (new Date().getFullYear() - +yr(b.mddTrough)) >= 6;
  const mddContext = `${mddAbs.toFixed(0)}% (peak ${yr(b.mddPeak)}→trough ${yr(b.mddTrough)}${mddIsOld ? `, an old extreme` : ""})${mddIsOld && mddRecentAbs > 5 ? `; ${mddRecentAbs.toFixed(0)}% in the last decade` : ""}`;
  const lossmaking = epsN != null && epsN <= 0;
  const priceSrc = lv?.current != null ? "DPS official feed · intraday (~real-time)" : "end-of-day close " + q.date;

  // "What the data flags" — factual observations, not predictions
  const pros = [], cons = [];
  if (proven.length) pros.push(`${proven.length} strateg${proven.length > 1 ? "ies have" : "y has"} been historically profitable on ${sym}`);
  if (fv && fv.mispricing_pct > 0) pros.push(`Trades ${Math.abs(fv.mispricing_pct)}% below the model's blended fair value`);
  if (fpeN != null && peN != null && fpeN < peN) pros.push(`Market expects earnings to grow (forward P/E ${f.forward_pe} below trailing ${f.pe})`);
  if (dyN != null && dyN >= 5 && payN != null && payN < 85) pros.push(`Above-average dividend yield (${f.div_yield}), covered by earnings`);
  if (betaN != null && betaN < 0.7) pros.push(`Historically calmer than the market (beta ${f.beta})`);
  if (payN != null && payN > 90) cons.push(`Dividend payout is stretched (${f.payout_ratio} of earnings)`);
  if (vol === "high") cons.push(`High price volatility (rank ${vr.toFixed(0)}/100)`);
  if (liq === "low") cons.push(`Low trading liquidity — can be hard to buy or sell quickly`);
  if (peerRich === true) cons.push(`Valued above sector peers on P/E`);
  if (mddRecentAbs >= 45) cons.push(`Has fallen ${mddRecentAbs.toFixed(0)}% peak-to-trough within the last decade`);
  if (betaN != null && betaN > 1.3) cons.push(`Amplifies market swings (beta ${f.beta})`);
  if (lossmaking) cons.push(`Currently lossmaking (EPS ${f.eps})`);
  const flagList = (arr, kind) => arr.length
    ? arr.map(t => `<div class="flag ${kind}"><span>${kind === "pro" ? "▲" : "▼"}</span>${esc(t)}</div>`).join("")
    : `<div class="sub" style="padding:6px 0">No notable data flags on this measure.</div>`;

  // Questions before buying — data-answered, informational
  const qmark = (s, label, ans) => `<div class="qrow"><div class="qmark ${s}">${s === "ok" ? "✓" : s === "warn" ? "!" : "?"}</div><div><b>${label}</b><div class="sub">${ans}</div></div></div>`;
  const checklist = [
    lossmaking ? qmark("warn", "Is profit positive and growing?", `Reported a net loss — earnings are currently negative (EPS ${f.eps}).`)
      : niN != null ? qmark(fpeN != null && peN != null && fpeN < peN ? "ok" : "info", "Is profit positive and growing?",
        `Reported positive net income (${f.net_income}).${fpeN != null && peN != null && fpeN < peN ? ` Forward P/E ${f.forward_pe} below trailing ${f.pe} — the market expects earnings to rise.` : " Multi-year growth trend isn't in the feed — check the latest results."}`)
      : qmark("info", "Is profit positive and growing?", "Earnings data unavailable in the feed right now."),
    qmark(niN != null && niN > 0 ? "info" : "warn", "Is the company generating cash?",
      `Net income is ${f.net_income || "—"}. The feed has no cash-flow statement, so treat net income only as a proxy — confirm operating cash flow before relying on it.`),
    qmark("info", "Is debt manageable?", "Balance-sheet debt isn't in the desk's feed. Don't assume leverage is safe — open the company's latest financials."),
    peerRich === true ? qmark("warn", "Is the stock expensive versus peers?", `On the peer-P/E model it screens above sector peers (model fair ~Rs ${fmt(peerFair)} vs price Rs ${fmt(fv.price)}).`)
      : peerRich === false ? qmark("ok", "Is the stock expensive versus peers?", "In line with or below sector peers on the peer-P/E model.")
        : qmark("info", "Is the stock expensive versus peers?", "Peer valuation unavailable for this name."),
    payN == null || (dyN != null && dyN === 0) ? qmark("info", "Is the dividend sustainable?", "Pays no dividend on record right now.")
      : payN > 90 ? qmark("warn", "Is the dividend sustainable?", `Payout ratio ${f.payout_ratio} — most of earnings are paid out, leaving little buffer if profits dip. ${dHist.length} payouts on record.`)
        : qmark("ok", "Is the dividend sustainable?", `Payout ratio ${f.payout_ratio}, yield ${f.div_yield || "—"} — covered by earnings. ${dHist.length} payouts on record.`),
    qmark(mddRecentAbs >= 30 ? "warn" : "info", "Can I tolerate a 30–50% decline?",
      `${sym}'s worst drop in the last decade was ${mddRecentAbs.toFixed(0)}% (to ${yr(b.mddRecentTrough)})${mddIsOld ? `; its all-time worst was ${mddAbs.toFixed(0)}% back in the ${yr(b.mddTrough)} era` : ""}. Only commit money you can hold through a fall like that.`),
    qmark("info", "What is my time horizon?", "This desk is daily-timeframe swing research — not day-trading, and not a buy-and-forget rating. Match any position to your own horizon and risk tolerance."),
  ].join("");

  // Risk profile — more than volatility; honest gaps
  const rl = (k, t) => `<span class="rlvl ${k}">${t}</span>`;
  const NA = '<span class="sub">not scored</span>';
  const rrow = (factor, chip, text) => `<tr><td style="width:180px;vertical-align:top"><b>${factor}</b></td><td style="width:96px;vertical-align:top">${chip}</td><td class="sub">${text}</td></tr>`;
  const riskRows = [
    rrow("Price volatility", vol ? rl(vol === "high" ? "hi" : vol === "moderate" ? "md" : "lo", vol) : NA,
      `Average daily move ±${b.avgAbs.toFixed(1)}%${vr != null ? ` (volatility rank ${vr.toFixed(0)}/100 across the universe)` : ""}.`),
    rrow("Maximum decline", rl(mddRecentAbs > 60 ? "hi" : mddRecentAbs > 35 ? "md" : "lo", mddRecentAbs > 60 ? "severe" : mddRecentAbs > 35 ? "large" : "moderate"),
      `Worst drawdown ${mddContext}. A drop of this size can recur.`),
    rrow("Liquidity", rl(liq === "low" ? "hi" : liq === "moderate" ? "md" : "lo", liq === "adequate" ? "adequate" : liq),
      `~Rs ${fmt(tvv / 1e6, 0)}M traded per day. ${liq === "low" ? "Thin — exiting quickly may move the price against you." : liq === "moderate" ? "Moderate depth." : "Deep enough to enter and exit readily."}`),
    rrow("Market sensitivity", betaN != null ? rl(betaN > 1.3 ? "hi" : betaN > 0.8 ? "md" : "lo", "beta " + f.beta) : NA,
      betaN != null ? `${betaN > 1 ? "Tends to move more than" : "Tends to move less than"} the broad market.` : "Beta not available."),
    rrow("Valuation", fv ? (fv.verdict === "overvalued" ? rl("hi", "above fair") : fv.verdict === "undervalued" ? rl("lo", "below fair") : rl("md", "near fair")) : NA,
      fv ? `Blended model fair value Rs ${fmt(fv.composite_fair)} vs price Rs ${fmt(fv.price)} (${sgn(fv.mispricing_pct)}%). A low share price does not mean a cheap company — value depends on earnings, not the rupee price.` : "Fair-value model unavailable."),
    rrow("Dividend reliability", dHist.length >= 4 ? rl("lo", "established") : dHist.length ? rl("md", "limited") : NA,
      dHist.length ? `${dHist.length} dividends on record; most recent closure ${dHist[0]?.bc_start || "—"}.` : "No payout on record."),
    rrow("Debt / leverage", NA, "Balance-sheet debt is not in the desk's data feed — review the latest financial statements before relying on any leverage assumption."),
    rrow("Earnings stability", NA, "A multi-year earnings series isn't in the feed yet, so year-to-year stability can't be scored here."),
  ].join("");

  // ---- 5-item summary strip: the whole story in one glance, before anything else ----
  let rg = "Moderate", rgk = "md";
  if (vr != null) { if (vr < 20) { rg = "Lower"; rgk = "lo"; } else if (vr >= 50) { rg = "Higher"; rgk = "hi"; } }
  if (liq === "low" || mddRecentAbs >= 55) { rg = "Higher"; rgk = "hi"; }
  const daysToEarn = nextEarn ? daysTo(nextEarn.date) : null;
  const hvRoom = room && room.house_view ? room.house_view : null;
  const sTile = (label, val, sub, k) => `<div class="sumtile"><span class="sk">${label}</span><b class="${k || ""}">${val}</b>${sub ? `<i>${sub}</i>` : ""}</div>`;
  // hard facts only — the lens verdicts live in the Signal Stack, and the desk's own view stays
  // behind its run (a tile here would spoil it)
  const summaryStrip = `<div class="sumstrip s4">
    ${sTile("Fair value vs price", fv ? `Rs ${fmt(fv.composite_fair)}` : "—", fv ? `price Rs ${fmt(fv.price)} · ${sgn(fv.mispricing_pct)}%` : "model n/a", fv ? (fv.verdict === "undervalued" ? "up" : fv.verdict === "overvalued" ? "dn" : "") : "")}
    ${sTile("Scorecard", fsc ? ({ attractive: "Stronger", caution: "Weaker", neutral: "Mixed", mixed: "Mixed" }[fsc.rating] || fsc.rating) : "—", fsc ? "business quality" : "not scored", fsc ? (fsc.rating === "attractive" ? "up" : fsc.rating === "caution" ? "dn" : "") : "")}
    ${sTile("Risk grade", rg, vr != null ? `volatility ${vr.toFixed(0)}/100` : "liquidity " + liq, rgk === "hi" ? "dn" : rgk === "lo" ? "up" : "")}
    ${sTile("Next event", nextEarn ? "Results" : "—", nextEarn ? `${nextEarn.date}${daysToEarn != null ? ` · ${daysToEarn}d` : ""}` : "none scheduled", "")}
  </div>`;

  // ---- private per-ticker note (only you can see it) ----
  const noteCard = me
    ? `<div class="seg"><h2>Your private note</h2><div class="ln"></div><span class="pill">only you can see this</span></div>
    <div class="card"><textarea id="tknote" class="tknote" placeholder="Private notes on ${esc(sym)} — your own thesis, price levels you care about, reminders. Saved to your account, visible only to you.">${esc(noteFor(sym))}</textarea>
      <div class="tknote-bar"><button class="note-save" onclick="saveTickerNote('${esc(sym)}')">Save note</button><span id="tknote-status" class="sub"></span></div></div>`
    : `<div class="seg"><h2>Your private note</h2><div class="ln"></div></div>
    <div class="card"><div class="empty">Sign in to keep a private note on ${esc(sym)} — your own thesis and reminders, saved to your account and visible only to you.<br><br><button class="auth-go" style="max-width:220px" onclick="openAuth('signup')">Create a free account</button></div></div>`;

  // ---- prominent "Run the desk" bar: gates the Desk Room analysis. Running it reveals the
  // results (in a modal + inline on the page) and shows the last-run date, so users come back
  // as the desk's analysis refreshes on the backend. ----
  const lastRun = room ? String(room.built || room.dossier_asof || "").slice(0, 16) : "";
  const deskRan = (() => { try { return !!sessionStorage.getItem("deskran:" + sym); } catch (e) { return false; } })();
  const runDeskBar = hvRoom ? `<button class="run-desk ${deskRan ? "ran" : ""}" onclick="playDeskReplay('${esc(sym)}')">
    <span class="run-ico">▶</span>
    <span class="run-txt"><b>Run the desk on ${esc(sym)}</b><i>A chartist, a fundamentalist, a bull, a bear and a chair debate ${esc(sym)}'s conviction and settle on a house view. Watch them work through it.</i></span>
    <span class="run-meta">${lastRun ? `<span class="run-last">Last run · ${esc(lastRun)}</span>` : ""}<span class="run-go">${deskRan ? "Run again ›" : "Run ›"}</span></span>
  </button>` : "";
  const deskStub = `<div class="seg"><h2>The Desk Room</h2><div class="ln"></div><span class="pill">AI analysts · research, not advice</span></div>
    <div class="card"><div class="empty">Run the desk on ${esc(sym)} — use the <b>Run ›</b> button near the top ↑. Once it finishes, the full analyst debate and house view appear right here.</div></div>`;

  // ---- "run the strategy library" bar: gates the backtest results the same way ----
  const stratRan = stratRunOn(sym);
  const runStratBar = `<button class="run-desk run-strat ${stratRan ? "ran" : ""}" onclick="playStrategyRun('${esc(sym)}')">
    <span class="run-ico">▶</span>
    <span class="run-txt"><b>Run the strategy library on ${esc(sym)}</b><i>Backtest all ${bt?.n_strategies ?? 52} of the desk's strategies across ${esc(sym)}'s ~19-year history and see which actually held up — win rate, expectancy, out-of-sample.</i></span>
    <span class="run-meta"><span class="run-go">${stratRan ? "Run again ›" : "Run ›"}</span></span></button>`;
  const stratStub = `<div class="card"><div class="empty">Run the strategy library on ${esc(sym)} — the <b>Run ›</b> button above ↑. It backtests all ${bt?.n_strategies ?? 52} strategies on ${esc(sym)}'s history and shows which ones held up here.</div></div>`;

  /* ---- The Signal Stack: every lens the desk has on this name, in ONE grammar
     (lean · conviction · why), so they can be read against each other in five seconds.
     Every lean is computed mechanically from the data layer — nothing here is invented,
     and the note always names exactly what drove it. Lenses the user hasn't run stay
     locked, because the desk's own view is worth watching happen. ---- */
  const liveSig = ((sigAll?.active) || []).find(s => s.ticker === sym);
  const stanceVal = s => /constructive|positive|bullish/i.test(s || "") ? 1 : /cautious|negative|bearish/i.test(s || "") ? -1 : 0;
  const leanChip = n => n > 0 ? { k: "up", v: "Bullish" } : n < 0 ? { k: "dn", v: "Bearish" } : { k: "", v: "Neutral" };

  // 1. Charts (quant layer — booleans straight off the indicator file)
  const taLean = (q.above_sma20 ? 1 : -1) + (q.above_sma50 ? 1 : -1);
  const rsiTxt = q.rsi14 != null ? `RSI14 ${q.rsi14.toFixed(0)}${q.rsi14 >= 70 ? " overbought" : q.rsi14 <= 30 ? " oversold" : ""}` : "RSI n/a";
  const taLens = { ...leanChip(taLean), conv: Math.abs(taLean) === 2 ? "medium" : "low",
    note: `${q.above_sma50 ? "above" : "below"} SMA50 · ${q.above_sma20 ? "above" : "below"} SMA20 · ${rsiTxt} · 20-day ${sgn(q.ret_20d)}%` };

  // 2. Value (fair-value composite, corroborated by the business scorecard)
  const fvLean = fv ? (fv.verdict === "undervalued" ? 1 : fv.verdict === "overvalued" ? -1 : 0) : 0;
  const fsLean = fsc ? (fsc.rating === "attractive" ? 1 : fsc.rating === "caution" ? -1 : 0) : 0;
  const fscWord = fsc ? ({ attractive: "stronger", caution: "weaker" }[fsc.rating] || "mixed") + " scorecard" : "not scored";
  const faLens = !fv ? { k: "", v: "No model", conv: "", note: "The fair-value model can't price this name — earnings data is missing or negative." }
    : { ...leanChip(fvLean), v: fvLean > 0 ? "Bullish" : fvLean < 0 ? "Bearish" : "Fair",
      conv: fvLean !== 0 && fsLean === fvLean ? "high" : fvLean !== 0 ? "medium" : "low",
      note: `${Math.abs(fv.mispricing_pct)}% ${fv.mispricing_pct > 0 ? "below" : "above"} the model's blended fair value · ${fscWord}` };

  // 3. The Desk Room (gated — the debate is the product)
  const taSt = room?.ta_memo?.technical_stance, faSt = room?.fa_memo?.fundamental_stance;
  const deskLean = stanceVal(taSt) + stanceVal(faSt);
  const roomLens = !hvRoom ? { k: "", v: "In queue", conv: "", note: `${esc(sym)} hasn't been through the Desk Room yet — the analysts cover names in rotation, and results or high-impact news jump the queue.` }
    : !deskRan ? { locked: true, run: `playDeskReplay('${esc(sym)}')`, note: "A chartist, a fundamentalist, a bull and a bear argue it out; the Chair settles it. Run the desk to see where they land." }
      : { ...leanChip(deskLean), v: deskLean > 0 ? "Bullish" : deskLean < 0 ? "Bearish" : "Split",
        conv: hvRoom.conviction || "", note: `charts ${esc(taSt || "—")} · fundamentals ${esc(faSt || "—")}${hvRoom.ta_fa_alignment ? " · the two desks " + esc(String(hvRoom.ta_fa_alignment).replace(/_/g, " ")) : ""}` };

  // 4. Strategies (gated — directional only when a proven rule is actually firing today)
  const topProven = proven[0];
  const stratLens = !stratRan ? { locked: true, run: `playStrategyRun('${esc(sym)}')`, note: `Backtest all ${bt?.n_strategies ?? 52} of the desk's strategies on ${esc(sym)}'s own ~19 years and see which held up.` }
    : liveSig ? { k: "up", v: "Firing now", conv: esc(liveSig.confidence || "medium"),
      note: `${esc(liveSig.template)} triggered today · won ${Math.round((liveSig.backtest?.hit_rate || 0) * 100)}% over ${liveSig.backtest?.n} past trades on ${esc(sym)}` }
      : proven.length ? { k: "", v: "Edge, not firing", conv: "",
        note: `${proven.length} rule set${proven.length > 1 ? "s have" : " has"} held up here — ${esc(topProven.name)} leads (${Math.round(topProven.hit_rate * 100)}% win, ${sgn(topProven.net_expectancy_pct)}%/trade) — but none is triggering today.` }
        : { k: "", v: "No edge", conv: "", note: `Not one of the ${bt?.n_strategies ?? 52} strategies cleared the bar on ${esc(sym)}'s history. That's a finding, not a gap.` };

  // 5. Brokers (public calls on the record — evidence to weigh, and every one of them is scored)
  const brokDir = brokerClaims.map(c => c.claim?.direction).filter(Boolean);
  const brokUp = brokDir.filter(d => /up|buy|overweight/i.test(d)).length;
  const brokDn = brokDir.filter(d => /down|sell|underweight/i.test(d)).length;
  const brokLens = !brokerClaims.length ? { k: "", v: "None on record", conv: "", note: "No PSX research house has a public call on this name in the desk's log." }
    : { ...leanChip(brokUp - brokDn), conv: brokerClaims.length >= 3 ? "medium" : "low",
      note: `${brokUp} positive · ${brokDn} negative of ${brokerClaims.length} on record — latest: ${esc(brokerClaims[brokerClaims.length - 1].source)}${brokerClaims[brokerClaims.length - 1].claim?.target_price ? ", target Rs " + fmt(brokerClaims[brokerClaims.length - 1].claim.target_price) : ""}` };

  // 6. Astro — a pointer to the immersive astrological reading, not a tested signal. Kept out of the
  // confluence (it makes no edge claim); framed as an exploration lens, never desk analytics.
  const astroLens = { k: "", v: "reading", conv: "",
    note: `The tradition's read of ${esc(sym)}'s chart — explore it on the <a href="#/astro" style="color:var(--accent)">Astro</a> board, or against your own in <a href="#/mychart" style="color:var(--accent)">Your Chart</a>.` };

  const LENSES = [
    ["Charts · TA", taLens], ["Value · FA", faLens], ["The Desk Room", roomLens],
    ["Strategies", stratLens], ["Brokers", brokLens], ["Astro", astroLens],
  ];
  // confluence counts only lenses that are BOTH revealed and directional — an honest denominator
  const revealed = LENSES.filter(([, o]) => !o.locked && (o.k === "up" || o.k === "dn"));
  const bullN = revealed.filter(([, o]) => o.k === "up").length, bearN = revealed.filter(([, o]) => o.k === "dn").length;
  const lockedN = LENSES.filter(([, o]) => o.locked).length;
  const oneWay = (n, word, k) => n === 1
    ? `<b class="${k}">The only lens that leans, leans ${word}.</b> One lens is a hint, not a case.`
    : `<b class="${k}">All ${n} lenses that lean, lean ${word}.</b> Agreement is not proof — they can be wrong together.`;
  const confTxt = !revealed.length ? `Nothing leans either way yet${lockedN ? ` — ${lockedN} lens${lockedN > 1 ? "es are" : " is"} still unrun` : ""}.`
    : bullN && !bearN ? oneWay(bullN, "bullish", "up")
      : bearN && !bullN ? oneWay(bearN, "bearish", "dn")
        : `<b>${bullN} bullish vs ${bearN} bearish</b> — the lenses disagree. That's information: the case isn't settled.`;
  const sigRow = (lens, o) => o.locked
    ? `<div class="sig-row locked clickable" onclick="${o.run}"><span class="sig-lens">${lens}</span>
        <span class="sig-chip lock">▶ Run to reveal</span><span class="sig-conv"></span><span class="sig-note">${o.note}</span></div>`
    : `<div class="sig-row"><span class="sig-lens">${lens}</span>
        <span class="sig-chip ${o.k}">${o.v}</span><span class="sig-conv">${o.conv ? esc(o.conv) + " conviction" : ""}</span><span class="sig-note">${o.note}</span></div>`;
  const sigStack = `<div class="seg" style="margin-top:2px"><h2>The Signal Stack</h2><div class="ln"></div><span class="pill">every lens · one view</span></div>
    <div class="card sigstack">
      ${LENSES.map(([n, o]) => sigRow(n, o)).join("")}
      <div class="sig-conf"><span class="sig-lens">Confluence</span><span class="sig-note">${confTxt}${lockedN ? ` <span class="sig-locknote">${lockedN} lens${lockedN > 1 ? "es" : ""} still to run.</span>` : ""}</span></div>
    </div>`;
  const stratCards = `<div class="card"><div class="sub">Of the desk's ${bt?.n_strategies ?? 52} tested strategies, these cleared the bar on ${sym}'s own ~19-year history — win rate ≥55%, positive expectancy after costs, AND still profitable in the unseen last third (out-of-sample). This is what actually worked here, not theory.</div>
    ${proven.length ? `<table><thead><tr><th>Strategy</th><th>Type</th><th class="r">Win rate</th><th class="r">Avg net/trade</th><th class="r">Trades</th><th class="r">Out-of-sample</th></tr></thead><tbody>${
      proven.map(t => `<tr><td><b>${esc(t.name)}</b></td><td><span class="tag">${esc(t.category.replace("_", " "))}</span></td>
        <td class="r num">${Math.round(t.hit_rate * 100)}%</td><td class="r num up">${sgn(t.net_expectancy_pct)}%</td>
        <td class="r num">${t.n}</td><td class="r num">${t.oos_hit != null ? Math.round(t.oos_hit * 100) + "% · n" + t.oos_n : "—"}</td></tr>`).join("")}</tbody></table>`
      : '<div class="empty">No strategy cleared the bar on this name — the desk would not signal it. That is a finding, not a gap: its history is too choppy for these rules.</div>'}</div>
  ${allTested.length > proven.length ? `<div class="card"><h2 style="font-size:13px">All ${allTested.length} strategies tested here</h2><div class="sub">full transparency — including the ones that failed. <span class="pill ok">proven</span> = made the cut.</div>
    <table><thead><tr><th>Strategy</th><th class="r">Win</th><th class="r">Net</th><th class="r">n</th><th class="r">Verdict</th></tr></thead><tbody>${
    allTested.slice(0, 20).map(t => `<tr><td>${esc(t.name || t.id)}</td><td class="r num">${t.hit_rate != null ? Math.round(t.hit_rate * 100) + "%" : "—"}</td>
      <td class="r num ${(t.net_expectancy_pct || 0) > 0 ? "up" : "dn"}">${sgn(t.net_expectancy_pct ?? 0)}%</td><td class="r num">${t.n}</td>
      <td class="r">${provenIds.has(t.id) ? '<span class="pill ok">proven</span>' : '<span style="opacity:.45">rejected</span>'}</td></tr>`).join("")}</tbody></table></div>` : ""}
  ${renderTestLog(sym, allTested, stratLib, bt?.bars)}`;

  $("view").innerHTML = `
  <a class="crumb" href="#/board">← board</a>
  <div class="disclaimer">Educational and informational research only — <b>not personalized investment advice</b>. Past performance does not guarantee future results. Investing in PSX carries risk, including the possible loss of capital. The desk never places orders; any decision and its outcome are your own.</div>
  ${sigStack}
  ${runDeskBar}
  ${summaryStrip}
  ${glance}
  <div class="card">
    <div class="tk-head">
      <span class="sym">${sym}</span>
      <span class="px num">${fmt(px)}</span>
      <span class="num ${cls(q.ret_1d)}" style="font-size:16px;font-weight:700">${sgn(q.ret_1d)}%</span>
      <span class="tag">${esc(u?.name || "")}</span>${mySector ? `<span class="tag">${esc(mySector)}</span>` : ""}
      <span class="tag">${(u?.in || []).join(" · ")}</span>
      <a class="tag" target="_blank" href="https://www.tradingview.com/chart/?symbol=PSX%3A${sym}">TradingView ↗ (15m delayed)</a>
      ${typeof starBtn === "function" ? starBtn(sym) : ""}
    </div>
    <div class="prov">Prices in <b>Rs (PKR)</b> · ${priceSrc} · quant as of ${q.date} close · fundamentals ${f.fetched || "—"} · long-history chart is split/bonus-adjusted (Yahoo); DPS close is unadjusted.${liq === "low" ? ' · <b class="dn">low liquidity</b>' : ""}${lossmaking ? ' · <b class="dn">earnings negative</b>' : ""}</div>
    ${mySector ? `<div class="tk-driver">${sectorDriverLine(smAll, mySector)}</div>` : ""}
    <div class="ranges" id="ranges">
      ${hasIntra ? '<button data-d="intra">1D</button>' : ""}<button data-d="63">3M</button><button data-d="126">6M</button><button class="on" data-d="252">1Y</button><button data-d="1260">5Y</button><button data-d="99999">Max${histYears >= 5 ? " (" + histYears + "y)" : ""}</button>
    </div>
    <div class="chartwrap"><canvas id="chart" style="height:340px"></canvas><div class="tooltip" id="tt"></div></div>
  </div>

  ${noteCard}

  <div class="seg"><h2>Strategies proven on ${sym}</h2><div class="ln"></div><span class="pill ok">${proven.length} proven</span></div>
  ${runStratBar}
  ${stratRan ? stratCards : stratStub}

  ${fsc ? `<div class="seg"><h2>Business scorecard</h2><div class="ln"></div><span class="pill ${fsc.rating === "attractive" ? "ok" : fsc.rating === "caution" ? "bad" : ""}">${esc({ attractive: "stronger scorecard", caution: "weaker scorecard", neutral: "mixed scorecard" }[fsc.rating] || fsc.rating)}</span></div>
  <div class="card"><div class="sub" style="font-size:13px;color:var(--ink2);margin-bottom:14px">${esc(fsc.overall)}</div>
    <div class="two-col" style="gap:12px">${fsc.cards.map(c => `<div style="border:1px solid var(--line);border-radius:0;padding:12px 14px">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px"><b>${esc(c[0])}</b><span class="tag">${esc(c[1])}</span></div>
      <div class="sub" style="color:var(--ink2)">${esc(c[2])}</div></div>`).join("")}</div></div>` : ""}

  ${!hvRoom ? renderRoom(room, sym) : (deskRan ? renderRoom(room, sym) : deskStub)}

  ${brokerClaims.length ? `<div class="seg"><h2>What the brokers say</h2><div class="ln"></div><span class="pill">${brokerClaims.length}</span></div>
  <div class="card"><div class="sub">public calls from PSX research houses on ${sym}, on the record — <b>evidence to weigh, not advice to follow</b>. Each is scored on the <a href="#/leaderboard" style="color:var(--accent)">Scores</a> board when it resolves.</div>
    <table><thead><tr><th>House</th><th>Call</th><th class="r">By</th><th class="r">Status</th></tr></thead><tbody>${
    brokerClaims.map(c => `<tr><td><b>${esc(c.source)}</b></td><td>${esc(c.claim?.text || c.claim?.rating || "")}${c.source_url ? ` <a href="${esc(c.source_url)}" target="_blank" style="color:var(--accent)">↗</a>` : ""}</td><td class="r num">${esc(c.resolve_by || "—")}</td><td class="r"><span class="pill ${c.status === "hit" ? "ok" : c.status === "miss" ? "bad" : ""}">${esc(c.status)}</span></td></tr>`).join("")}</tbody></table></div>` : ""}

  ${fv ? (() => {
    const vcol = fv.verdict === "undervalued" ? "var(--up)" : fv.verdict === "overvalued" ? "var(--dn)" : "var(--ink2)";
    const vlabel = { undervalued: "below model fair value", overvalued: "above model fair value", fair: "near model fair value" }[fv.verdict] || fv.verdict;
    const mlabel = { relative_pe: "Peer P/E (priced like sector)", earnings_power: "Earnings power (vs bond yield)", graham: "Graham value (earnings + growth)", ddm: "Dividend discount model" };
    return `<div class="seg"><h2>Fair value model</h2><div class="ln"></div>
      <span class="pill" style="background:color-mix(in srgb,${vcol} 15%,transparent);color:${vcol}">${vlabel} · ${sgn(fv.mispricing_pct)}%</span></div>
    <div class="card"><div class="sub" style="margin-bottom:14px">The desk values ${sym} four ways, then takes the middle (median) estimate. Today it trades at <b>${fmt(fv.price)}</b>; the blended model fair value is <b style="color:${vcol}">${fmt(fv.composite_fair)}</b> — ${fv.mispricing_pct >= 0 ? "the price sits <b>below</b> the model's blended fair value" : "the price sits <b>above</b> the model's blended fair value"} by ${Math.abs(fv.mispricing_pct)}%. This is a model estimate on public fundamentals — <b>not a price target or a recommendation</b>, and a low share price never means a company is cheap.</div>
      <table><thead><tr><th>Method</th><th class="r">Fair value</th><th class="r">vs price</th></tr></thead><tbody>${
      Object.entries(fv.methods).map(([k, val]) => { const up = (val / fv.price - 1) * 100; return `<tr><td>${esc(mlabel[k] || k)}</td><td class="r num">${fmt(val)}</td><td class="r num ${cls(up)}">${sgn(up.toFixed(0))}%</td></tr>`; }).join("")}
        <tr style="border-top:2px solid var(--line)"><td><b>Composite (median)</b></td><td class="r num"><b>${fmt(fv.composite_fair)}</b></td><td class="r num ${cls(fv.mispricing_pct)}"><b>${sgn(fv.mispricing_pct)}%</b></td></tr>
      </tbody></table>
      <div class="sub" style="margin-top:8px">EPS ${fv.eps} · growth est ${fv.growth_est_pct}% · P/E ${fv.pe ?? "—"}. A wide spread between methods means the models disagree — treat as a rough screen, not a precise number.</div></div>`;
  })() : ""}

  <div class="seg"><h2>What the data flags</h2><div class="ln"></div></div>
  <div class="card"><div class="sub" style="margin-bottom:12px">Factual observations pulled from the desk's data — not predictions and not advice. The absence of a flag is not a green light.</div>
    <div class="two-col" style="gap:14px">
      <div><div class="flaghdr up">What could go right</div>${flagList(pros, "pro")}</div>
      <div><div class="flaghdr dn">What could go wrong</div>${flagList(cons, "con")}</div>
    </div></div>

  <div class="seg"><h2>Questions to ask before buying</h2><div class="ln"></div></div>
  <div class="card"><div class="sub" style="margin-bottom:12px">A checklist, answered from the data where the desk has it — and honest about where it doesn't. This is a thinking aid, not a recommendation.</div>
    <div class="checklist">${checklist}</div></div>

  <div class="seg"><h2>Risk profile</h2><div class="ln"></div></div>
  <div class="card"><div class="sub" style="margin-bottom:12px">Risk is more than volatility. A low rupee price does <b>not</b> mean a stock is cheap — a Rs 20 share can be dearer than a Rs 500 one depending on earnings.</div>
    <table class="risktbl"><tbody>${riskRows}</tbody></table></div>

  <div class="card"><h2>Key facts</h2><div class="sub">fundamentals · stockanalysis.com${f.fetched ? " · " + f.fetched : ""}</div>
    <div class="facts">
      <div class="fact"><span>Market cap</span><b>${esc(f.market_cap || "—")}</b></div>
      <div class="fact"><span>P/E (TTM)</span><b>${lossmaking ? '<span class="sub" style="font-size:11px">n/a · earnings negative</span>' : esc(f.pe || "—")}</b></div>
      <div class="fact"><span>Forward P/E</span><b>${esc(f.forward_pe || "—")}</b></div>
      <div class="fact"><span>EPS (TTM)</span><b>${esc(f.eps || "—")}</b></div>
      <div class="fact"><span>Div yield</span><b>${esc(f.div_yield || "—")}</b></div>
      <div class="fact"><span>Payout ratio</span><b>${esc(f.payout_ratio || "—")}</b></div>
      <div class="fact"><span>Beta</span><b>${esc(f.beta || "—")}</b></div>
      <div class="fact"><span>Revenue</span><b>${esc(f.revenue || "—")}</b></div>
      <div class="fact"><span>Net income</span><b>${esc(f.net_income || "—")}</b></div>
      <div class="fact"><span>Shares out</span><b>${esc(f.shares_out || "—")}</b></div>
      <div class="fact"><span>Next results</span><b>${nextEarn ? esc(nextEarn.date) + ` <span class="cd ${daysTo(nextEarn.date) <= 7 ? "soon" : ""}">${daysTo(nextEarn.date)}d</span>` : esc(f.next_earnings || "—")}</b></div>
      <div class="fact"><span>Ex-dividend</span><b>${esc(f.ex_div_date || "—")}</b></div>
    </div></div>
  <div class="card"><h2>Quant snapshot</h2><div class="sub">as of ${q.date} close</div>
    <div class="statgrid num">
      <div class="stat"><span>RSI 14</span><b>${q.rsi14}</b></div>
      <div class="stat"><span>SMA 20</span><b class="${q.above_sma20 ? "up" : "dn"}">${q.sma20}</b></div>
      <div class="stat"><span>SMA 50</span><b class="${q.above_sma50 ? "up" : "dn"}">${q.sma50}</b></div>
      <div class="stat"><span>ATR proxy</span><b>${q.atr14_proxy}</b></div>
      <div class="stat"><span>5d / 20d</span><b><span class="${cls(q.ret_5d)}">${sgn(q.ret_5d)}%</span> / <span class="${cls(q.ret_20d)}">${sgn(q.ret_20d)}%</span></b></div>
      <div class="stat"><span>vol surge</span><b>${q.vol_surge ?? "—"}×</b></div>
      <div class="stat"><span>vola rank</span><b>${q.volatility_rank ?? "—"}</b></div>
      <div class="stat"><span>to 20d high</span><b>${sgn(q.dist_to_20d_high_pct)}%</b></div>
      <div class="stat"><span>avg traded/day</span><b>${fmt(q.avg_daily_traded_value / 1e6, 0)}M</b></div>
      <div class="stat"><span>index weight</span><b>${u?.weight_pct ?? "—"}%</b></div>
    </div></div>
  <div class="two-col">
    <div class="card"><h2>${histYears}-year behavior</h2><div class="sub">${series[0].date} → ${series[series.length - 1].date}${series === deep ? " · Yahoo history" : ""}</div>
      <div class="statgrid num">
        <div class="stat"><span>total return</span><b class="${cls(b.total)}">${sgn(b.total.toFixed(0))}%</b></div>
        <div class="stat"><span>max drawdown</span><b class="dn">${b.mdd.toFixed(0)}%</b></div>
        <div class="stat"><span>up days</span><b>${b.upPct.toFixed(0)}%</b></div>
        <div class="stat"><span>avg daily move</span><b>±${b.avgAbs.toFixed(2)}%</b></div>
        <div class="stat"><span>best day</span><b class="up">+${b.best.toFixed(1)}%</b></div>
        <div class="stat"><span>worst day</span><b class="dn">${b.worst.toFixed(1)}%</b></div>
      </div></div>
    <div class="card"><h2>Dividends</h2><div class="sub">face value Rs 10 assumed · buy BEFORE ex-date (~2 sessions pre-closure)</div>${
      dUp.length ? `<p style="margin-bottom:10px"><b class="up">UPCOMING:</b> ${dUp.map(d => `${esc(d.announcement)} — closure ${d.bc_start}, buy by <b>${d.buy_by}</b>`).join("; ")}</p>` : ""}
      <table><thead><tr><th>Announced</th><th>Payout</th><th class="r">Rs/sh</th><th class="r">Yield@now</th><th class="r">Closure</th></tr></thead><tbody>${
      dHist.length ? dHist.slice(0, 8).map(d => `<tr><td>${esc((d.announced || "").split(" ").slice(0, 3).join(" "))}</td><td>${esc(d.announcement)}</td>
        <td class="r num">${d.dividend_rs ?? "—"}</td><td class="r num">${d.yield_pct_at_close ? d.yield_pct_at_close + "%" : "—"}</td><td class="r num">${d.bc_start || "—"}</td></tr>`).join("") : '<tr><td colspan="5" class="empty">no payout records</td></tr>'}</tbody></table></div>
  </div>
  <div class="card"><h2>News & developments</h2><div class="sub">sentinel-tagged for ${sym}</div><div class="wire">${
    tickerNews.length ? tickerNews.map(n => `<p><span class="tag">${n.impact}</span> <span class="t">${esc((n.ts || "").slice(0, 16))}</span>${esc(n.headline || "")} ${n.url ? `<a href="${esc(n.url)}" target="_blank" style="color:var(--accent)">source ↗</a>` : ""}<br><span class="t">${esc(n.summary || "")}</span></p>`).join("") : '<div class="empty">Nothing tagged yet — sentinel populates this each cycle.</div>'}</div></div>`;

  const redraw = d => {
    if (d === "intra") drawIntraday($("chart"), $("tt"), intra.points, q.close);
    else drawChart($("chart"), $("tt"), series, +d);
  };
  $("ranges").addEventListener("click", e => {
    if (!e.target.dataset.d) return;
    $("ranges").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === e.target));
    redraw(e.target.dataset.d);
  });
  redraw(252);
}

function daysFromNow(d) { return d ? Math.ceil((new Date(d) - new Date()) / 86400000) : null; }
function cdBadge(d) { const n = daysFromNow(d); return n == null ? "" : `<span class="cd ${n <= 3 ? "soon" : ""}">${n >= 0 ? n + "d" : "past"}</span>`; }

async function pageDividends() {
  const [cal, divs] = await Promise.all([j("earnings_calendar.json"), j("dividends.json")]);
  const ev = cal?.events || [];
  const divUp = ev.filter(e => e.type === "ex_dividend" || e.type === "book_closure");
  const past = (divs?.history || []).filter(d => d.bc_start && !d.upcoming)
    .sort((a, b) => b.bc_start.localeCompare(a.bc_start)).slice(0, 40);

  const dvLocked = !isSubscribed();
  const divShown = dvLocked ? divUp.slice(0, 3) : divUp;
  const divHtml = divUp.length ? divShown.map(d => `
    <tr class="clickable" onclick="location.hash='#/ticker/${d.ticker}'">
      <td><b>${d.ticker}</b></td>
      <td>${esc(d.announcement || d.type.replace("_", " "))}</td>
      <td class="r num">${d.dividend_rs ?? "—"}</td>
      <td class="r num">${d.yield_pct || (d.div_yield ? esc(d.div_yield) : "—")}</td>
      <td class="r num up"><b>${d.buy_by || "—"}</b> ${cdBadge(d.buy_by)}</td>
      <td class="r num">${d.sell_ok_from || d.date}</td>
    </tr>`).join("")
    : `<tr><td colspan="6" class="empty">No <b>announced</b> ex-dividend / book-closure dates yet — this is data, not a gap. PSX payouts cluster right after results (Jul–Aug); the desk lists a date only once a company files it, never a guess. The <b>${past.length} recent payouts below</b> show what these names actually pay and their yields.</td></tr>`;

  $("view").innerHTML = `
  <div class="timing">
    <div><span>How to collect a dividend</span><b>Buy before → hold through → sell after</b></div>
    <div><span>① Buy by</span><b>the last session before the ex-date</b></div>
    <div><span>② Sell on / after</span><b>the ex-date — you keep the full payout</b></div>
  </div>

  <div class="seg"><h2>Upcoming dividends & book closures</h2><div class="ln"></div></div>
  <div class="card"><div class="sub">own the share BEFORE the ex-dividend date to receive the cash · updated ${esc(cal?.updated || "—")}</div>
    <table><thead><tr><th>Ticker</th><th>Payout</th><th class="r">Rs/sh</th><th class="r">Yield</th><th class="r">Buy by</th><th class="r">Ex / sell-after</th></tr></thead><tbody>${divHtml}</tbody></table></div>

  ${dvLocked ? planWall("The full dividend desk",
    `Every announced payout with its buy-by and sell-after dates${divUp.length > 3 ? ` (${divUp.length - 3} more upcoming right now)` : ""}, plus the last ${past.length} real payouts with the yields they actually delivered — what these names truly pay, on the record.`) : `
  <div class="seg"><h2>Past payouts</h2><div class="ln"></div></div>
  <div class="card"><div class="sub">last ${past.length} closures · cash dividends (D) as % of Rs 10 face value</div>
    <table><thead><tr><th>Ticker</th><th>Payout</th><th class="r">Rs/sh</th><th class="r">Yield@now</th><th class="r">Announced</th><th class="r">Closure start</th></tr></thead><tbody>${
    past.map(d => `<tr class="clickable" onclick="location.hash='#/ticker/${d.symbol}'"><td><b>${d.symbol}</b></td><td>${esc(d.announcement)}</td>
      <td class="r num">${d.dividend_rs ?? "—"}</td><td class="r num">${d.yield_pct_at_close ? d.yield_pct_at_close + "%" : "—"}</td>
      <td class="r num">${esc((d.announced || "").split(" ").slice(0, 3).join(" "))}</td><td class="r num">${d.bc_start}</td></tr>`).join("")}</tbody></table></div>`}`;
}

async function pageCalendar() {
  const cal = await j("earnings_calendar.json");
  const earnings = (cal?.events || []).filter(e => e.type === "results");
  const byMonth = {};
  earnings.forEach(e => { const m = e.date.slice(0, 7); (byMonth[m] = byMonth[m] || []).push(e); });

  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Earnings calendar</h2><div class="ln"></div></div>
  <p class="sub" style="margin-bottom:16px">${earnings.length} upcoming results dates across the universe · <span class="pill ok">verified</span> = confirmed against a company/PSX board-meeting notice · <span class="tag">estimate</span> = scraped, pending verification. The desk won't open a swing into an unconfirmed results date inside its hold window (earnings gaps blow through stops).</p>
  ${(isSubscribed() ? Object.keys(byMonth).sort() : Object.keys(byMonth).sort().slice(0, 1)).map(m => {
    const label = new Date(m + "-01").toLocaleDateString("en", { month: "long", year: "numeric" });
    return `<div class="card"><h2 style="font-size:13px">${label}</h2>
      <table><thead><tr><th>Date</th><th class="r">In</th><th>Ticker</th><th>Event</th><th class="r">Status</th></tr></thead><tbody>${
      byMonth[m].map(e => `<tr class="clickable" onclick="location.hash='#/ticker/${e.ticker}'">
        <td class="num">${e.date}</td><td class="r">${cdBadge(e.date)}</td><td><b>${e.ticker}</b></td>
        <td class="sub">${esc(e.note || "results")}</td>
        <td class="r">${e.confirmed ? '<span class="pill ok">verified</span>' : '<span class="tag">estimate</span>'}</td></tr>`).join("")}</tbody></table></div>`;
  }).join("") || '<div class="card"><div class="empty">Calendar builds on the first full cycle.</div></div>'}
  ${Object.keys(byMonth).length > 1 ? planWall("The full earnings calendar",
    `${earnings.length} dated results across the coming months, each verified against a board-meeting notice — the dates that gap prices, known before they land.`) : ""}`;
}

let newsFilter = { imp: 0, q: "" };
async function pageNews() {
  const news = (await j("newslog.json")) || [];
  const rows = news.filter(n => (n.impact || 0) >= newsFilter.imp
    && (!newsFilter.q || (n.tickers || []).join(" ").toUpperCase().includes(newsFilter.q) || (n.headline || "").toUpperCase().includes(newsFilter.q)))
    .slice(-80).reverse();
  $("view").innerHTML = `
  <div class="card"><h2>News wire</h2><div class="sub">${news.length} items logged · nothing is ever deleted — this is the desk's memory</div>
    <div class="ranges">
      ${[0, 3, 4, 5].map(i => `<button data-imp="${i}" class="${newsFilter.imp === i ? "on" : ""}">${i ? "impact ≥" + i : "all"}</button>`).join("")}
      <input id="nq" placeholder="filter ticker/text" value="${esc(newsFilter.q)}" style="font:inherit;padding:4px 10px;border:1px solid currentColor;opacity:.7;background:transparent;color:inherit;border-radius:0">
    </div>
    <div class="wire">${rows.length ? rows.map(n => `<p><span class="tag">${n.impact}</span> <span class="t">${esc((n.ts || "").slice(0, 16))}</span>
      ${(n.tickers || []).map(t => `<a href="#/ticker/${esc(t)}" style="color:var(--accent);font-weight:700">${esc(t)}</a>`).join(" ")}
      <b>${esc(n.headline || "")}</b> ${n.url ? `<a href="${esc(n.url)}" target="_blank" style="color:var(--accent)">↗</a>` : ""}<br>
      <span class="t">${esc(n.summary || "")} · ${esc(n.source || "")}</span></p>`).join("") : '<div class="empty">Wire silent — sentinel runs every cycle during market hours.</div>'}</div></div>`;
  $("view").querySelector(".ranges").addEventListener("click", e => {
    if (e.target.dataset.imp != null) { newsFilter.imp = +e.target.dataset.imp; pageNews(); }
  });
  $("nq").addEventListener("change", e => { newsFilter.q = e.target.value.toUpperCase(); pageNews(); });
}

/* ---------- Research library (broker notes + filings, digested) ---------- */
async function pageResearch() {
  const idx = await j("research_index.json");
  const docs = Object.values(idx?.documents || {}).sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  const followed = new Set(followedBrokers());
  // followed broker desks surface first on the wire, then by date
  const brokers = docs.filter(d => d.source_type === "broker")
    .sort((a, b) => (followed.has(b.source) ? 1 : 0) - (followed.has(a.source) ? 1 : 0));
  const filings = docs.filter(d => d.source_type !== "broker");
  const dtLabel = { corporate_briefing: "corporate briefing", agm: "AGM", results: "results", board_meeting: "board meeting", filing: "filing", morning_note: "morning note", company_note: "broker note" };
  const docRow = d => `<div class="rdoc">
    <div class="rdoc-top"><span class="tag">${esc(dtLabel[d.doc_type] || d.doc_type)}</span>
      <span class="rdoc-src">${esc(d.source)}${followed.has(d.source) ? ' <span class="wbadge">★ following</span>' : ""}${d.digest_level === "headline" ? ' · <span class="sub">headline only</span>' : ""}</span>
      <span class="t">${esc(d.date || "")}</span>
      ${(d.tickers || []).slice(0, 4).map(t => `<a href="#/ticker/${esc(t)}" class="tag clickable">${esc(t)}</a>`).join(" ")}</div>
    <div class="rdoc-digest">${esc(d.digest || "")}${d.url ? ` <a href="${esc(d.url)}" target="_blank" style="color:var(--accent)">source ↗</a>` : ""}</div>
    ${(d.claims || []).length ? `<div class="sub" style="margin-top:4px"><b>Claims (scored later):</b> ${d.claims.map(c => esc(c.claim?.text || "")).join(" · ")}</div>` : ""}
    ${d.omissions ? `<div class="sub" style="margin-top:4px"><b class="dn">What it glosses over:</b> ${esc(d.omissions)}</div>` : ""}</div>`;
  // glance row: what's in the library and how much of it is on the record
  const sTile = (label, val, sub, k) => `<div class="sumtile"><span class="sk">${label}</span><b class="${k || ""}">${val}</b>${sub ? `<i>${sub}</i>` : ""}</div>`;
  const nClaims = docs.reduce((a, d) => a + ((d.claims || []).length), 0);
  const houses = new Set(docs.filter(d => d.source_type === "broker").map(d => d.source));
  const latest = docs[0]?.date || "—";
  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Research library</h2><div class="ln"></div><span class="pill">${docs.length} documents</span></div>
  <div class="sumstrip s4">
    ${sTile("Broker notes", brokers.length, `${houses.size} house${houses.size === 1 ? "" : "s"}${followed.size ? ` · ${followed.size} you follow` : ""}`, "")}
    ${sTile("Filings & briefings", filings.length, "results · AGM · board", "")}
    ${sTile("Claims on the record", nClaims, "each scored when it resolves", nClaims ? "up" : "")}
    ${sTile("Latest document", esc(latest), "the wire updates weekly", "")}
  </div>
  <div class="disclaimer">Broker research and company filings are <b>evidence the desk cross-examines, never takes at face value</b>. Brokers miss things, carry sector bias, and are often wrong — every broker claim here is extracted, scored against what actually happens, and ranked on the <a href="#/leaderboard" style="color:inherit;text-decoration:underline">broker leaderboard</a>. Educational, not advice.</div>
  <div class="seg"><h2>Broker notes</h2><div class="ln"></div><span class="pill">${brokers.length}</span></div>
  <div class="card">${brokers.length ? (isSubscribed() ? brokers : brokers.slice(0, 2)).map(docRow).join("") : '<div class="empty">No broker notes digested yet. Add public sources in config/broker_sources.json; the desk digests each once and scores its calls. Until then, the desk forms its own view without leaning on brokers.</div>'}</div>
  <div class="seg"><h2>Company filings & briefings</h2><div class="ln"></div><span class="pill">${filings.length}</span></div>
  <div class="card">${filings.length ? (isSubscribed() ? filings : filings.slice(0, 2)).map(docRow).join("") : '<div class="empty">No filings tagged yet — the news sentinel surfaces results, board-meeting and corporate-briefing notices here as companies file them.</div>'}</div>
  ${docs.length > 4 ? planWall("The full research library",
    `${docs.length} digested documents — broker notes with every claim extracted for public scoring, results filings and corporate briefings — each cross-examined, never taken at face value.`) : ""}`;
}

/* ---------- Leaderboards: our analysts + the brokers, scored on real outcomes ---------- */
async function pageLeaderboard() {
  const [lb, bs, claimsAll] = await Promise.all([j("leaderboard.json"), j("broker_scorecard.json"), j("claims.json")]);
  const personas = lb?.personas || {};
  const brokers = bs?.brokers || {};
  const allClaims = claimsAll?.claims || [];
  const pending = allClaims.filter(c => c.status === "pending");
  const resolved = allClaims.filter(c => c.status === "hit" || c.status === "miss");
  const claimDates = allClaims.map(c => (c.made_on || c.made_at || "")).filter(Boolean).sort();
  const since = claimDates.length ? claimDates[0].slice(0, 10) : null;
  const daysSince = since ? Math.max(0, Math.round((Date.now() - new Date(since)) / 86400000)) : null;
  const clkTile = (label, val, sub) => `<div class="clk-tile"><span>${label}</span><b>${val}</b>${sub ? `<i>${sub}</i>` : ""}</div>`;
  const trackClock = `<div class="trackclock">
    ${clkTile("Scoring calls since", since || "—", daysSince != null ? `${daysSince} day${daysSince === 1 ? "" : "s"} on the record` : "the clock starts with the first dated call")}
    ${clkTile("Calls on the record", allClaims.length, "desk analysts + brokers")}
    ${clkTile("Resolved", resolved.length, "graded against real outcomes")}
    ${clkTile("Pending", pending.length, "awaiting their horizon")}
  </div>`;
  const pendBroker = pending.filter(c => c.source_type === "broker");
  const pendByBroker = {};
  pendBroker.forEach(c => (pendByBroker[c.source] = pendByBroker[c.source] || []).push(c));
  const pRow = (name, r) => `<tr><td><b>${esc(name)}</b></td><td class="r num">${r.calls}</td><td class="r num ${r.hit_rate >= 0.55 ? "up" : r.hit_rate != null && r.hit_rate < 0.45 ? "dn" : ""}">${r.hit_rate != null ? Math.round(r.hit_rate * 100) + "%" : "—"}</td><td class="r num">${r.avg_target_err_pct != null ? r.avg_target_err_pct + "%" : "—"}</td></tr>`;
  const sectorRow = (sect, s) => `<tr><td style="padding-left:22px" class="sub">${esc(sect.replace(/_/g, " "))}</td><td class="r num">${s.calls}</td><td class="r num ${!s.ranked ? "" : s.hit_rate >= 0.55 ? "up" : "dn"}">${s.hit_rate != null ? Math.round(s.hit_rate * 100) + "%" : "—"}${!s.ranked ? ' <span class="sub">unranked</span>' : ""}</td><td class="r num">${s.avg_target_err_pct != null ? s.avg_target_err_pct + "%" : "—"}</td></tr>`;
  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Track records</h2><div class="ln"></div></div>
  ${trackClock}
  <div class="disclaimer">Every dated call — the desk's own AI analysts <b>and</b> the brokers — is scored against what prices actually did. This is accountability, not advice. A thin record (below ${bs?._meta?.min_sample_to_rank ?? 5} calls) is shown <b>unranked</b> so no one is over-trusted on luck.</div>

  <div class="seg"><h2>The desk's AI analysts</h2><div class="ln"></div><span class="pill">${Object.keys(personas).length}</span></div>
  <div class="card"><div class="sub">the desk holds itself to the same standard it holds the brokers.</div>
    ${Object.keys(personas).length ? `<table><thead><tr><th>Analyst</th><th class="r">Calls</th><th class="r">Hit rate</th><th class="r">Avg target err</th></tr></thead><tbody>${Object.entries(personas).map(([n, r]) => pRow(n, r)).join("")}</tbody></table>` : '<div class="empty">No resolved calls yet — the desk\'s dated calls score after their horizons pass (first ones resolve from early August). Pending calls appear on each ticker\'s Desk Room.</div>'}</div>

  <div class="seg"><h2>Brokers — ranked on what came true</h2><div class="ln"></div><span class="pill">${Object.keys(brokers).length}</span></div>
  <div class="card"><div class="sub">overall and per sector — a broker's bank desk and E&P desk have different records, so they're scored separately.</div>
    ${Object.keys(brokers).length ? Object.entries(brokers).map(([n, r]) => `<table style="margin-bottom:14px"><thead><tr><th>${esc(n)}</th><th class="r">Calls</th><th class="r">Hit rate</th><th class="r">Avg target err</th></tr></thead><tbody>${pRow("overall", r)}${Object.entries(r.by_sector || {}).map(([s, sv]) => sectorRow(s, sv)).join("")}</tbody></table>`).join("") : '<div class="empty">No broker calls have <b>resolved</b> yet — rankings appear once a call reaches its horizon. Calls already on the record are shown below and will be graded when they resolve.</div>'}</div>

  ${pendBroker.length ? `<div class="seg"><h2>Broker calls on the record — pending</h2><div class="ln"></div><span class="pill">${pendBroker.length}</span></div>
  <div class="card"><div class="sub">harvested from public research; each will be scored against what actually happens by its horizon. Recorded to grade the house, not to follow it.</div>
    <table><thead><tr><th>House</th><th>Ticker</th><th>Call</th><th class="r">Resolves</th></tr></thead><tbody>${
    pendBroker.slice(0, 40).map(c => `<tr><td><b>${esc(c.source)}</b></td><td><a href="#/ticker/${esc(c.ticker)}" style="color:var(--accent);font-weight:700">${esc(c.ticker)}</a></td><td class="sub">${esc(c.claim?.text || c.claim?.rating || "")}</td><td class="r num">${esc(c.resolve_by || "—")}</td></tr>`).join("")}</tbody></table></div>` : ""}`;
}

/* ---------- legal pages (Terms / Privacy / Risk) — content from state/legal.json ---------- */
async function pageLegal() {
  const doc = await j("legal.json");
  const which = location.hash.split("/")[2] || "terms";
  const tabs = [["terms", "Terms of Service"], ["privacy", "Privacy Policy"], ["risk", "Risk Disclosure"]];
  const tabBar = `<div class="legal-tabs">${tabs.map(([k, t]) => `<a href="#/legal/${k}" class="${k === which ? "on" : ""}">${t}</a>`).join("")}</div>`;
  const L = doc && doc[which];
  if (!L) { $("view").innerHTML = `<div class="seg" style="margin-top:4px"><h2>Legal</h2><div class="ln"></div></div>${tabBar}<div class="card"><div class="empty">Loading…</div></div>`; return; }
  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>${esc(L.title)}</h2><div class="ln"></div><span class="pill">updated ${esc(L.updated)}</span></div>
  ${tabBar}
  <div class="card legal-doc">
    <p class="legal-intro">${esc(L.intro)}</p>
    ${(L.sections || []).map(([h, b]) => `<h3>${esc(h)}</h3><p>${esc(b)}</p>`).join("")}
    <p class="sub" style="margin-top:20px">Contact: <a href="mailto:${esc(doc.contact || "")}" style="color:var(--accent)">${esc(doc.contact || "")}</a>${doc.jurisdiction ? ` · Governed by the laws of ${esc(doc.jurisdiction)}.` : ""}</p>
  </div>`;
}

/* ---------- Shared "run" modal: a ~10–20s loader that streams REAL precomputed steps, then a
   reveal. Zero agents run per view — it animates already-computed data. Used by both the Desk
   Room run and the strategy-library run so the loader/orchestration lives in ONE place. ---------- */
function runRevealModal(opts) {
  // opts: { sym, kicker, title, sub, steps:[html], flagKey, renderReveal(bodyEl, {runLoader}) }
  const ov = document.createElement("div");
  ov.className = "replay-overlay";
  ov.innerHTML = `<div class="replay-box">
    <div class="replay-head"><span class="replay-kicker">${esc(opts.kicker)}</span>
      <button class="replay-x" aria-label="close" style="margin-left:auto">✕</button></div>
    <div class="replay-body" id="rpBody"></div>
  </div>`;
  document.body.appendChild(ov);
  const body = ov.querySelector("#rpBody");
  let raf = null, done = false;

  function close() {
    cancelAnimationFrame(raf); ov.remove(); document.removeEventListener("keydown", key);
    // reveal the results inline on the page (reveal() sets the session flag once the run finishes)
    if (opts.onClose) opts.onClose();
    else if (opts.sym && typeof pageTicker === "function" && location.hash.toUpperCase().includes(opts.sym)) pageTicker(opts.sym);
  }
  function key(e) { if (e.key === "Escape") close(); }
  ov.addEventListener("click", e => {
    if (e.target === ov || e.target.classList.contains("replay-x")) return close();
    const b = e.target.closest("[data-a]");
    if (b && b.dataset.a === "replay") runLoader();
    // "read the full transcript / test log" — close out to the page and open the deep dive there
    if (b && b.dataset.a === "deep") { const t = b.dataset.target; close(); setTimeout(() => {
      const d = document.querySelector("." + t);
      if (d) { d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" }); }
    }, 300); }
  });
  document.addEventListener("keydown", key);

  function runLoader() {
    done = false;
    body.innerHTML = `<div class="rp-load">
      <div class="rp-load-title">${esc(opts.title)}</div>
      <div class="rp-load-sub">${opts.sub}</div>
      <div class="rp-prog"><div class="rp-prog-fill" id="rpFill"></div></div>
      <div class="rp-pct" id="rpPct">0<span>%</span></div>
      <div class="rp-steps" id="rpSteps"></div></div>`;
    const fill = ov.querySelector("#rpFill"), pctEl = ov.querySelector("#rpPct"), stepsEl = ov.querySelector("#rpSteps"), subEl = ov.querySelector(".rp-load-sub");
    const total = 10000 + Math.floor(Math.random() * 10000), longRun = total > 15500, t0 = performance.now();  // 10–20s, varied for anticipation
    let shown = 0;
    function tick(now) {
      const p = Math.min(100, (now - t0) / total * 100);
      fill.style.width = p + "%";
      pctEl.innerHTML = Math.floor(p) + "<span>%</span>";
      if (longRun && p > 52 && !subEl.dataset.longed) { subEl.dataset.longed = "1"; subEl.textContent = "Taking a little longer than usual on this one — the desk is being thorough."; }
      const want = Math.round(p / 100 * opts.steps.length);
      while (shown < want && shown < opts.steps.length) {
        if (shown > 0) { const prev = stepsEl.children[shown - 1]; if (prev) prev.classList.add("did"); }
        stepsEl.insertAdjacentHTML("beforeend", `<div class="rp-step-line"><span class="rp-step-mk">▸</span><span class="rp-step-tx">${opts.steps[shown]}</span></div>`);
        stepsEl.lastChild.scrollIntoView({ block: "nearest" });
        shown++;
      }
      if (p < 100 && !done) { raf = requestAnimationFrame(tick); }
      else if (!done) { [...stepsEl.children].forEach(c => c.classList.add("did")); setTimeout(reveal, 550); }
    }
    raf = requestAnimationFrame(tick);
  }
  function reveal() {
    if (done) return;
    done = true; cancelAnimationFrame(raf);
    try { if (opts.flagKey) sessionStorage.setItem(opts.flagKey, "1"); } catch (e) { /* private mode */ }
    if (opts.onReveal) opts.onReveal();
    opts.renderReveal(body, { runLoader });
    body.scrollTop = 0;
  }
  runLoader();
}

/* ---------- Desk Room run: streams the REAL steps the desk ran (RSI/SMA/fair-value from the data
   layer) then lands on the parallel split-desk view with the Chair's verdict highlighted. ---------- */
async function playDeskReplay(sym) {
  sym = (sym || "").toUpperCase();
  const [rooms, uni, quant, fund, fvAll] = await Promise.all([
    j("rooms.json"), j("universe.json"), j("quant.json"), j("fundamentals.json"), j("fairvalue.json")]);
  const s = rooms && rooms[sym];
  if (!s || !s.house_view) return;
  const name = uni?.symbols?.[sym]?.name || "";
  const q = quant?.tickers?.[sym] || {}, f = fund?.tickers?.[sym] || {}, fv = fvAll?.tickers?.[sym] || {};
  const ta = s.ta_memo || {}, fa = s.fa_memo || {}, bull = s.bull_case || {}, bear = s.bear_case || {}, hv = s.house_view || {};
  const li = arr => (arr || []).slice(0, 3).map(x => `<li>${esc(x)}</li>`).join("");
  const stance = v => ({ constructive: "up", cautious: "dn", bullish: "up", bearish: "dn", positive: "up", negative: "dn" }[v] || "");
  const convIdx = { low: 1, medium: 2, high: 3 }[hv.conviction] || 1;
  const nz = v => (v == null || v === "") ? "—" : (typeof v === "number" ? fmt(v) : esc(v));

  const steps = [
    `Loading price history — <b>${esc(sym)}</b>${name ? " · " + esc(name) : ""}`,
    `Technicals · RSI14 <b>${nz(q.rsi14)}</b> · SMA20 <b>${nz(q.sma20)}</b> · SMA50 <b>${nz(q.sma50)}</b>`,
    `Fundamentals · P/E <b>${esc(f.pe || "—")}</b> · yield <b>${esc(f.div_yield || "—")}</b> · beta <b>${esc(f.beta || "—")}</b>`,
    `Fair value · 4 models → composite <b>Rs ${nz(fv.composite_fair)}</b> (${esc(fv.verdict || "—")})`,
    `Strategies · scanned 52 → <b>${(ta.proven_now || []).length}</b> firing on ${esc(sym)}`,
    `Technical desk (Meher) &amp; fundamental desk (Dr. Omar) — memos in`,
    `Bull (Zoya) vs Bear (Khurram) — stress-testing both sides`,
    `The Chair — weighing it into a house view`,
  ];
  if (s.qa) steps.push(`QA agent — cross-examined the numbers · <b>${esc(s.qa.verdict)}</b>`);

  const panel = (av, nm, role, st, read, facts) => `<div class="rp-panel ${st ? "accent-" + st : ""}">
    <div class="rp-panel-head"><span class="rp-av sm">${av}</span><div><b>${esc(nm)}</b><span class="rp-role">${role}</span></div></div>
    <p class="rp-panel-read">${esc(read || "—")}</p>${facts ? `<div class="rp-facts">${facts}</div>` : ""}</div>`;

  runRevealModal({
    sym, kicker: `Desk Room · ${esc(sym)}`, flagKey: "deskran:" + sym,
    title: `Running the desk on ${esc(sym)}`,
    sub: `Working through ${esc(sym)} the way the desk does — pulling the price history, the technicals and the valuation, then letting the analysts debate it out to a house view.`,
    steps,
    renderReveal: (bodyEl) => {
      const cvm = `<div class="cvmeter2" role="img" aria-label="conviction: ${esc(hv.conviction || "low")}">
        <span class="cvm ${convIdx === 1 ? "act lvl-low" : ""}">Low</span>
        <span class="cvm ${convIdx === 2 ? "act lvl-med" : ""}">Medium</span>
        <span class="cvm ${convIdx === 3 ? "act lvl-high" : ""}">High</span></div>
        <div class="cvcap">how sure the desk is about this read</div>`;
      bodyEl.innerHTML = `<div class="rp-reveal">
        <div class="rp-reveal-head"><b>${esc(sym)}${name ? " · " + esc(name) : ""}</b><span>the whole desk, at a glance — computed ${esc(s.dossier_asof || "")} at Rs ${nz(s.price_at_session)}</span></div>
        <div class="rp-desk">
          ${panel("MC", "Meher", "the chartist · TA", stance(ta.technical_stance), ta.read, ta.levels ? `support <b>${nz(ta.levels.support)}</b> · resistance <b>${nz(ta.levels.resistance)}</b> · momentum <b>${esc(ta.momentum || "—")}</b>` : "")}
          ${panel("DO", "Dr. Omar", "the fundamentalist · FA", stance(fa.fundamental_stance), fa.read, `valuation <b>${esc((fa.valuation_stance || "—").replace(/_/g, " "))}</b> · dividend <b>${esc(fa.dividend_safety || "—")}</b>`)}
          ${panel("ZB", "Zoya", "the bull · case FOR", "up", bull.thesis, bull.pillars ? `<ul class="rp-ul">${li(bull.pillars)}</ul>` : "")}
          ${panel("KB", "Khurram", "the bear · case AGAINST", "dn", bear.thesis, bear.pillars ? `<ul class="rp-ul">${li(bear.pillars)}</ul>` : "")}
        </div>
        <div class="rp-chair">
          <div class="rp-chair-top"><span class="rp-chair-tag">The Chair · house view</span>${s.qa ? `<span class="qabadge ${s.qa.verdict === "clean" ? "ok" : "warn"}">QA ${esc(s.qa.verdict)}</span>` : ""}</div>
          <p class="rp-chair-summary">${esc(hv.summary || "")}</p>
          ${cvm}
          <div class="rp-chair-facts">
            ${hv.dissent ? `<div><span>The strongest case against this view</span><b>${esc(hv.dissent)}</b></div>` : ""}
            ${hv.watch_next ? `<div><span>What settles it next</span><b>${esc(hv.watch_next)}</b></div>` : ""}
          </div>
        </div>
        <div class="rp-reveal-foot"><span>Dated, falsifiable, and scored on the <b>Scores</b> board when its horizon passes. Research, not advice.</span>
          <span class="rp-foot-btns"><button class="rp-btn2" data-a="replay">↻ Run again</button><button class="rp-btn2" data-a="deep" data-target="room-transcript">Read the full transcript ›</button><button class="rp-btn2" onclick="location.hash='#/leaderboard'">Scores ›</button></span></div>
      </div>`;
    },
  });
}

/* ---------- Strategy-library run: replays the REAL backtest of all ~52 strategies on this ticker
   and reveals which ones cleared the bar, ranked. Animates precomputed backtests.json. ---------- */
async function playStrategyRun(sym) {
  sym = (sym || "").toUpperCase();
  const [smap, bt, uni] = await Promise.all([j("strategy_map.json"), j("backtests.json"), j("universe.json")]);
  const proven = ((smap?.tickers?.[sym]) || []).slice().sort((a, b) => (b.net_expectancy_pct ?? -99) - (a.net_expectancy_pct ?? -99));
  const nTested = bt?.n_strategies || 52;
  const allTested = Object.entries(bt?.templates || {}).map(([id, per]) => ({ id, ...(per[sym] || {}) })).filter(t => t.n);
  const name = uni?.symbols?.[sym]?.name || "";
  const top = proven[0];
  const pct = h => h != null ? Math.round(h * 100) + "%" : "—";

  const steps = [
    `Loading <b>${esc(sym)}</b>'s full price history — ~19 years`,
    `Backtesting <b>${nTested}</b> strategies bar-by-bar`,
    `Applying trading costs &amp; slippage on every trade`,
    `Filter · win rate ≥ 55% and positive expectancy after costs`,
    `Out-of-sample check · must still work on the unseen last third`,
    `Ranking survivors by net expectancy per trade`,
    `<b>${proven.length}</b> of ${allTested.length || nTested} strategies cleared the bar on ${esc(sym)}`,
  ];

  runRevealModal({
    sym, kicker: `Strategy library · ${esc(sym)}`, flagKey: "stratran:" + sym,
    title: `Running the strategy library on ${esc(sym)}`,
    sub: `Backtesting all ${nTested} of the desk's strategies across ${esc(sym)}'s own ~19 years of price history — costs included, then checked on data the strategy never saw.`,
    steps,
    renderReveal: (bodyEl) => {
      bodyEl.innerHTML = `<div class="rp-reveal">
        <div class="rp-reveal-head"><b>${esc(sym)}${name ? " · " + esc(name) : ""}</b><span>what actually worked — ${proven.length} of ${allTested.length || nTested} strategies cleared win-rate ≥55%, positive expectancy, and out-of-sample</span></div>
        ${proven.length ? `<div class="rp-strat-top"><div class="rp-strat-rank">#1</div>
          <div style="flex:1;min-width:0"><b>${esc(top.name)}</b><span class="rp-role">${esc((top.category || "").replace(/_/g, " "))} · the strongest on ${esc(sym)}</span>
            <div class="rp-facts" style="margin-top:6px">win rate <b>${pct(top.hit_rate)}</b> · net/trade <b class="up">${sgn(top.net_expectancy_pct)}%</b> · trades <b>${top.n}</b> · out-of-sample <b>${pct(top.oos_hit)}</b></div></div></div>
        <div class="card" style="margin-top:10px;padding:0"><table><thead><tr><th>Strategy</th><th class="r">Win</th><th class="r">Net/trade</th><th class="r">Trades</th><th class="r">OOS</th></tr></thead><tbody>${
          proven.map(t => `<tr><td><b>${esc(t.name)}</b> <span class="tag">${esc((t.category || "").replace(/_/g, " "))}</span></td><td class="r num">${pct(t.hit_rate)}</td><td class="r num up">${sgn(t.net_expectancy_pct)}%</td><td class="r num">${t.n}</td><td class="r num">${pct(t.oos_hit)}</td></tr>`).join("")}</tbody></table></div>`
          : `<div class="card"><div class="empty">No strategy cleared the bar on ${esc(sym)} — none held win rate ≥55%, positive expectancy after costs, AND profitability out-of-sample. The desk wouldn't signal it. That's a finding, not a gap.</div></div>`}
        <div class="rp-reveal-foot"><span>Backtested on ${esc(sym)}'s own ~19-year history, costs included, checked on unseen data. Past performance does not predict future results. Research, not advice.</span>
          <span class="rp-foot-btns"><button class="rp-btn2" data-a="replay">↻ Run again</button><button class="rp-btn2" data-a="deep" data-target="testlog">Read the full test log ›</button><button class="rp-btn2" onclick="location.hash='#/strategies'">All strategies ›</button></span></div>
      </div>`;
    },
  });
}

/* Has the strategy library actually been run on this ticker this session? One flag, shared by the
   ticker page and the board — running it in either place counts, so the product never contradicts
   itself. Adding a stock to the board does NOT set it: the work has to be watched to mean anything. */
function stratRunOn(sym) { try { return !!sessionStorage.getItem("stratran:" + sym); } catch (e) { return false; } }

/* ---------- strategy board (profiles.strategy_board; session-only for guests) ---------- */
function stratBoard() {
  if (me) return (myProfile && myProfile.strategy_board) || [];
  try { return JSON.parse(sessionStorage.getItem("stratboard") || "[]"); } catch (e) { return []; }
}
async function saveStratBoard(list) {
  if (me) return saveProfile({ strategy_board: list });
  try { sessionStorage.setItem("stratboard", JSON.stringify(list)); } catch (e) { /* private mode: board just won't persist */ }
  return null;
}
async function addBoardTicker() {
  const inp = document.getElementById("sb-tkr"), msg = document.getElementById("sb-msg");
  const say = t => { if (msg) msg.textContent = t; };
  const sym = (inp?.value || "").toUpperCase().trim();
  if (!sym) return;
  const uni = await j("universe.json");
  if (!uni?.symbols?.[sym]) return say(`${sym} isn't in the desk's universe — try the suggestions as you type.`);
  const cur = stratBoard();
  if (cur.includes(sym)) return say(`${sym} is already on your board.`);
  if (cur.length >= 12) return say("The board holds 12 stocks — remove one first.");
  const err = await saveStratBoard([...cur, sym]);
  if (err) return say("Couldn't save — try again.");
  pageStrategies();
}
async function removeBoardTicker(sym) {
  const err = await saveStratBoard(stratBoard().filter(s => s !== sym));
  if (!err) pageStrategies();
}

/* ---------- board run: backtests the whole library across every stock on the board and
   ranks the surviving stock–strategy pairs. Animates precomputed backtests, zero agents. ---------- */
async function playBoardRun() {
  const board = stratBoard();
  if (!board.length) return;
  const [smap, bt, uni] = await Promise.all([j("strategy_map.json"), j("backtests.json"), j("universe.json")]);
  const nT = bt?.n_strategies || 52;
  const pct = h => h != null ? Math.round(h * 100) + "%" : "—";
  const pairs = board.flatMap(s => (smap?.tickers?.[s] || []).map(t => ({ sym: s, ...t })))
    .sort((a, b) => (b.net_expectancy_pct ?? -99) - (a.net_expectancy_pct ?? -99));
  const blanks = board.filter(s => !(smap?.tickers?.[s] || []).length);
  const top = pairs[0];

  const steps = [
    `Loading ~19 years of price history for <b>${board.length}</b> stock${board.length > 1 ? "s" : ""}`,
    ...board.map(s => `Backtesting <b>${nT}</b> strategies on <b>${esc(s)}</b> bar-by-bar`),
    `Applying trading costs &amp; slippage on every trade`,
    `Filter · win rate ≥ 55% and positive expectancy after costs`,
    `Out-of-sample check · must still work on the unseen last third`,
    `Ranking <b>${pairs.length}</b> surviving stock–strategy pairs by net expectancy`,
  ];

  runRevealModal({
    sym: "", kicker: "Strategy library · your board",
    title: `Running ${nT} strategies on your ${board.length}-stock board`,
    sub: `Backtesting the desk's whole library across every stock on your board — costs included, then checked on data each strategy never saw — and ranking what actually held up.`,
    steps,
    // per-ticker flags: only the stocks this run actually covered unlock — anywhere in the product
    onReveal: () => { try { board.forEach(s => sessionStorage.setItem("stratran:" + s, "1")); } catch (e) { /* private mode */ } },
    onClose: () => { if (location.hash.replace(/^#\/?/, "").startsWith("strategies")) pageStrategies(); },
    renderReveal: (bodyEl) => {
      bodyEl.innerHTML = `<div class="rp-reveal">
        <div class="rp-reveal-head"><b>Your board · ${board.map(esc).join(" · ")}</b><span>what actually worked — ${pairs.length} stock–strategy pair${pairs.length === 1 ? "" : "s"} cleared win-rate ≥55%, positive expectancy after costs, and out-of-sample</span></div>
        ${top ? `<div class="rp-strat-top"><div class="rp-strat-rank">#1</div>
          <div style="flex:1;min-width:0"><b>${esc(top.name)} on ${esc(top.sym)}</b><span class="rp-role">${esc((top.category || "").replace(/_/g, " "))} · the strongest pair on your board</span>
            <div class="rp-facts" style="margin-top:6px">win rate <b>${pct(top.hit_rate)}</b> · net/trade <b class="up">${sgn(top.net_expectancy_pct)}%</b> · trades <b>${top.n}</b> · out-of-sample <b>${pct(top.oos_hit)}</b></div></div></div>` : ""}
        ${pairs.length ? `<div class="card" style="margin-top:10px;padding:0"><table><thead><tr><th>Stock</th><th>Strategy</th><th class="r">Win</th><th class="r">Net/trade</th><th class="r">Trades</th><th class="r">OOS</th></tr></thead><tbody>${
          pairs.slice(0, 20).map(t => `<tr><td><b>${esc(t.sym)}</b></td><td>${esc(t.name)} <span class="tag">${esc((t.category || "").replace(/_/g, " "))}</span></td><td class="r num">${pct(t.hit_rate)}</td><td class="r num up">${sgn(t.net_expectancy_pct)}%</td><td class="r num">${t.n}</td><td class="r num">${pct(t.oos_hit)}</td></tr>`).join("")}</tbody></table>${pairs.length > 20 ? `<div class="sub" style="padding:10px 17px">…and ${pairs.length - 20} more — the full list is on the page behind this.</div>` : ""}</div>`
          : `<div class="card"><div class="empty">No strategy cleared the bar on ${board.length === 1 ? "this stock" : "any of these stocks"} — none held win rate ≥55%, positive expectancy after costs, AND profitability out-of-sample. The desk wouldn't signal them. That's a finding, not a gap.</div></div>`}
        ${blanks.length && pairs.length ? `<div class="sub" style="margin-top:10px">Nothing cleared the bar on <b>${blanks.map(esc).join(", ")}</b> — their histories are too choppy for these rules.</div>` : ""}
        <div class="rp-reveal-foot"><span>Backtested on each stock's own ~19-year history, costs included, checked on unseen data. Past performance does not predict future results. Research, not advice.</span>
          <span class="rp-foot-btns"><button class="rp-btn2" data-a="replay">↻ Run again</button></span></div>
      </div>`;
    },
  });
}

/* ---------- request a strategy → strategy_requests (RLS: own rows only) ---------- */
async function submitStratRequest() {
  if (!me || !sb) { openAuth("signup"); return; }
  const v = id => (document.getElementById(id)?.value || "").trim();
  const msg = document.getElementById("rq-msg");
  const say = t => { if (msg) msg.textContent = t; };
  const title = v("rq-title"), desc = v("rq-desc"), tkr = v("rq-tkr").toUpperCase();
  if (!title) return say("Give it a name first.");
  if (desc.length < 20) return say("Explain the rules — a few sentences, so the desk can code it faithfully.");
  say("Sending…");
  const { error } = await sb.from("strategy_requests").insert({ title, description: desc, ticker: tkr || null });
  if (error) return say("Couldn't send — try again.");
  ["rq-title", "rq-desc", "rq-tkr"].forEach(id => { const el = document.getElementById(id); if (el) el.value = ""; });
  say("Received ✓ — the desk backtests it, and if it clears the bar it joins the library.");
}

/* ---------- router ---------- */
/* ---------- followed brokers + digest preferences (profiles.followed_brokers / digest_prefs) ---------- */
function followedBrokers() { return (myProfile && myProfile.followed_brokers) || []; }
function digestPrefs() { return (myProfile && myProfile.digest_prefs) || {}; }
async function toggleBroker(name) {
  if (!me) { openAuth("signup"); return; }
  const s = new Set(followedBrokers());
  s.has(name) ? s.delete(name) : s.add(name);
  await saveProfile({ followed_brokers: [...s] });
  pageSettings();
}
async function saveDigest(patch) {
  await saveProfile({ digest_prefs: { ...digestPrefs(), ...patch } });
  pageSettings();
}
async function toggleDigestInc(key) {
  const inc = { ...(digestPrefs().include || {}) };
  inc[key] = !inc[key];
  await saveDigest({ include: inc });
}

async function pageSettings() {
  const [bs, claimsAll] = await Promise.all([j("broker_scorecard.json"), j("claims.json")]);
  if (!me) {
    $("view").innerHTML = `<div class="seg" style="margin-top:4px"><h2>Settings</h2><div class="ln"></div></div>
      <div class="card"><div class="empty">Sign in to set your preferences — follow the broker desks you care about and choose your digest.<br><br>
      <button class="auth-go" style="max-width:220px" onclick="openAuth('signup')">Create a free account</button></div></div>`;
    return;
  }
  const brokerSet = new Set(Object.keys(bs?.brokers || {}));
  (claimsAll?.claims || []).forEach(c => { if (c.source_type === "broker" && c.source) brokerSet.add(c.source); });
  const brokers = [...brokerSet].sort();
  const fb = new Set(followedBrokers());
  const dp = digestPrefs();
  const freq = dp.frequency || "off";
  const inc = dp.include || {};
  const freqBtn = (v, label) => `<button class="seg-opt ${freq === v ? "on" : ""}" onclick="saveDigest({frequency:'${v}'})">${label}</button>`;
  const incRow = (key, label) => `<label class="chk-row"><input type="checkbox" ${inc[key] ? "checked" : ""} onchange="toggleDigestInc('${key}')"> <span>${label}</span></label>`;

  const bd = birthData();
  const birthRow = (l, v) => `<div class="bd-row"><span>${l}</span><b>${esc(v || "—")}</b></div>`;

  const pl = PLANS[planOf()];
  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Settings</h2><div class="ln"></div><span class="pill">${esc(me.email || "")}</span></div>

  <div class="seg"><h2>Your plan</h2><div class="ln"></div><span class="pill ${planOf() === "free" ? "" : "ok"}">${esc(pl.label)}</span></div>
  <div class="card">
    <div class="pc-top"><b style="font-size:16px">${esc(pl.label)} plan</b>${pl.tag ? `<span class="pill">${esc(pl.tag)}</span>` : ""}</div>
    <p class="sub" style="margin:4px 0 10px">${esc(pl.blurb)}</p>
    <div class="bd-bar"><button class="note-save" onclick="location.hash='#/plans'">See all plans</button>
      <button class="note-save" onclick="setDeskMode('${deskMode() === "learn" ? "pro" : "learn"}')">Switch to the ${deskMode() === "learn" ? "Pro" : "Learner"} desk</button></div>
    <p class="sub" style="margin-top:10px">Payments aren't open yet — card processing through international providers isn't available in Pakistan, so billing will run through a local gateway. Nothing is charged, and plans are set manually until then.</p>
  </div>

  <div class="seg"><h2>Your birth details</h2><div class="ln"></div><span class="pill">${bd ? "on file" : "not set"}</span></div>
  <div class="card">
    <p class="sub" style="margin-bottom:12px">The date, time and place that cast your chart on <a href="#/mychart" style="color:var(--accent)">Your Chart</a>. Made a mistake? Edit it and the desk recasts everything. Private to your account.</p>
    ${bd ? `<div class="bd-grid">
      ${birthRow("Date", bd.date)}
      ${birthRow("Time", bd.time_known === false ? "unknown (read from Moon)" : bd.time)}
      ${birthRow("Place", bd.place)}
      ${birthRow("UTC offset", bd.tz != null ? (bd.tz >= 0 ? "+" : "") + bd.tz : "—")}
    </div>
    <div class="bd-bar"><button class="note-save" onclick="openBirthWizard()">Edit birth details</button>
      <button class="bd-clear" onclick="clearBirthData()">Remove</button></div>`
    : `<button class="note-save" onclick="openBirthWizard()">Add my birth details</button>`}
  </div>

  <div class="seg"><h2>Your digest</h2><div class="ln"></div></div>
  <div class="card">
    <p class="sub" style="margin-bottom:12px">A periodic email of what changed on your watchlist and the desk. <b>Delivery isn't switched on yet</b> — we're saving your preference so it's ready the moment email sending goes live.</p>
    <div class="sk" style="margin-bottom:6px">Frequency</div>
    <div class="seg-opts">${freqBtn("off", "Off")}${freqBtn("daily", "Daily")}${freqBtn("weekly", "Weekly")}</div>
    <div class="sk" style="margin:14px 0 6px">Include</div>
    ${incRow("watchlist", "What moved on my watchlist")}
    ${incRow("dailyread", "The desk's daily read")}
    ${incRow("calls", "Newly resolved calls (hits / misses)")}
    ${incRow("brokers", "New broker calls on names I follow")}
  </div>

  <div class="seg"><h2>Followed broker desks</h2><div class="ln"></div><span class="pill">${fb.size} followed</span></div>
  <div class="card">
    <p class="sub" style="margin-bottom:12px">Pick the research houses you want surfaced first on your Research wire. The desk still audits and scores every broker — following one never means trusting it. Research, not advice.</p>
    ${brokers.length ? `<div class="follow-grid">${brokers.map(n => `<button class="follow-chip ${fb.has(n) ? "on" : ""}" data-broker="${esc(n)}">${fb.has(n) ? "✓ " : ""}${esc(n)}</button>`).join("")}</div>`
      : '<div class="empty">No broker desks tracked yet — they appear here as the weekly harvest records their public calls.</div>'}
  </div>

  <div class="seg"><h2>Legal</h2><div class="ln"></div></div>
  <div class="card"><div class="follow-grid">
    <a class="follow-chip" href="#/legal/terms">Terms of Service</a>
    <a class="follow-chip" href="#/legal/privacy">Privacy Policy</a>
    <a class="follow-chip" href="#/legal/risk">Risk Disclosure</a>
  </div></div>`;
}

/* ---------- Plans: what each desk includes. Payment is not wired (no Stripe in Pakistan — a local
   gateway follows), so this page states plainly where things stand rather than dangling a dead
   checkout button. ---------- */
const FEATURE_LABEL = {
  learn: "The guided learning path",
  astro_full: "Your full astro reading + the daily sky",
  dividends_full: "Every announced payout + buy-by dates",
  earnings_full: "The full earnings calendar",
  value_full: "Model fair value on every stock",
  strategies_run: "Run the strategy library on your board",
  research_full: "The full research library",
  broker_tools: "Your desk's calls scored in public",
};
async function pagePlans() {
  await Promise.resolve();
  const cur = planOf();
  const rank = k => PLAN_ORDER.indexOf(k);
  const card = (k) => {
    const p = PLANS[k], on = me && cur === k;
    const isUp = me && !p.soon && rank(k) > rank(cur);          // a plan above the one you're on
    return `<div class="plan-card ${on ? "on" : ""} ${p.soon ? "soon" : ""}">
      <div class="pc-top"><b>${esc(p.label)}</b>${p.tag ? `<span class="pill ${p.soon ? "" : "ok"}">${esc(p.tag)}</span>` : ""}${on ? '<span class="pill ok">your plan</span>' : ""}</div>
      <p class="sub">${esc(p.blurb)}</p>
      <div class="pc-feats">${(p.features.length ? p.features : ["Cast your birth chart", "The daily desk note", "The public track record"])
        .map(f => `<div class="pc-f">${esc(FEATURE_LABEL[f] || f)}</div>`).join("")}</div>
      ${on
        ? `<div class="pc-cta"><button class="pc-btn ghost" disabled>Your current plan</button></div>`
        : p.soon ? `<div class="pc-cta"><button class="pc-btn ghost" disabled>Coming soon</button></div>`
          : isUp ? `<div class="pc-cta"><button class="pc-btn" onclick="notifyUpgrade('${k}')">Upgrade to ${esc(p.label)} →</button>
              <div class="pc-price sub">Pricing announced when payments open</div></div>`
            : k === "free" ? "" : `<div class="pc-cta"><div class="pc-price sub">Included in your plan</div></div>`}
    </div>`;
  };
  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Plans</h2><div class="ln"></div>${me ? `<span class="pill ${cur === "free" ? "" : "ok"}">${esc(PLANS[cur].label)}</span>` : ""}</div>
  <p class="sub" style="margin-bottom:14px">One data layer, read three ways. <b>Investor</b> teaches you to read the market for yourself; <b>Pro</b> is the full analytical desk; <b>Broker</b> adds public scoring for a research house's own calls.</p>
  <div class="disclaimer"><b>Payments aren't open yet.</b> Card processing through international providers isn't available in Pakistan, so billing will run through a local gateway. Until that's live, nothing is charged and everything currently available to your account stays available.</div>
  <div class="plan-grid">${PLAN_ORDER.map(card).join("")}</div>
  <div id="upgmsg" class="sub" style="margin-top:10px"></div>
  ${isOwner() ? `<div class="card owner-preview"><div class="ark">owner · preview as</div>
    <p class="sub" style="margin:6px 0 10px">See exactly what each plan's product looks like. This changes only what <b>you</b> see, never your stored plan — reload to return to ${esc(PLANS[realPlan()].label)}.</p>
    <div class="mode-row">${PLAN_ORDER.map(k => `<button class="seg-opt ${planOf() === k ? "on" : ""}" onclick="previewAs('${k}')">${esc(PLANS[k].label)}</button>`).join("")}
      ${_previewPlan ? `<button class="seg-opt" onclick="previewAs(null)">Exit preview</button>` : ""}</div></div>` : ""}
  ${me ? `<div class="card" style="margin-top:12px"><div class="ark">how you're reading the desk</div>
    <p class="sub" style="margin:6px 0 10px">The Learner desk reorders everything around the lessons. You can switch view at any time — it doesn't change your plan.</p>
    <div class="mode-row">
      <button class="seg-opt ${deskMode() === "pro" ? "on" : ""}" onclick="setDeskMode('pro')">Pro desk</button>
      <button class="seg-opt ${deskMode() === "learn" ? "on" : ""}" onclick="setDeskMode('learn')">Learner desk</button>
    </div></div>` : ""}`;
}
/* No checkout to send anyone to yet, so record the interest honestly instead of faking a flow. */
function notifyUpgrade(k) {
  const m = document.getElementById("upgmsg");
  if (!me) { openAuth("signup"); return; }
  if (m) m.innerHTML = `<b>Noted — ${esc(PLANS[k].label)}.</b> Payments open once the local gateway is live; nothing has been charged. Your account keeps everything it has today.`;
}
function previewAs(k) {
  if (!isOwner()) return;
  _previewPlan = k;
  applyDeskMode();
  renderAccountButton();
  pagePlans();
}
async function setDeskMode(m) {
  if (!me) { openAuth("signup"); return; }
  if (planOf() === "investor" && m !== "learn") return;   // the Investor plan is the Investor desk
  myProfile = { ...(myProfile || {}), ui_mode: m };
  await saveProfile({ ui_mode: m });
  applyDeskMode();
  location.hash = m === "learn" ? "#/learn" : "#/today";
  route(true);
}
/* The nav is declared once in HTML; the shell just flips which group is visible, so there is one
   source of truth for routes and no second menu to keep in sync. */
function applyDeskMode() {
  document.body.dataset.desk = deskMode();
  const badge = document.getElementById("planBadge");
  if (badge) { badge.textContent = PLANS[planOf()].label; badge.hidden = !me; }
}

/* ==========================================================================================
   THE LEARNER DESK — a guided path for people who have never invested. Same data layer, different
   information architecture: lessons in order, each taught on real PSX filings and real desk numbers
   rather than toy examples. Educational only — CLAUDE.md Rule 5 applies here hardest of all: this
   teaches how to read the market, never what to buy.
   ========================================================================================== */
function learnProgress() { return (me && myProfile && myProfile.learn_progress) || {}; }
async function markLesson(stageId, lessonId, done) {
  if (!me) { openAuth("signup"); return; }
  const p = { ...learnProgress() };
  const key = stageId + "/" + lessonId;
  if (done) p[key] = new Date().toISOString(); else delete p[key];
  myProfile = { ...(myProfile || {}), learn_progress: p };
  await saveProfile({ learn_progress: p });
  pageLearn();
}
function lessonDone(stageId, lessonId) { return !!learnProgress()[stageId + "/" + lessonId]; }

/* Each lesson can pull one real slice of the desk into itself, so nothing is taught abstractly. */
async function lessonLive(kind) {
  try {
    if (kind === "dividends") {
      const d = await j("dividends.json");
      const rows = (d?.history || []).filter(x => x.dividend_rs).slice(-3).reverse();
      if (!rows.length) return "";
      return `<div class="ll-live"><b>Real payouts on the desk right now</b>
        ${rows.map(r => `<div class="ll-row"><span>${esc(r.symbol)}</span><span class="sub">${esc(r.announcement || "cash dividend")}</span><b class="num">Rs ${esc(String(r.dividend_rs))}/sh</b></div>`).join("")}
        <a href="#/dividends" class="ll-go">See every announced payout, with its buy-by date →</a></div>`;
    }
    if (kind === "earnings") {
      const c = await j("earnings_calendar.json");
      const ev = (c?.events || []).filter(e => e.type === "results").slice(0, 3);
      if (!ev.length) return "";
      return `<div class="ll-live"><b>Results dates the desk already knows about</b>
        ${ev.map(e => `<div class="ll-row"><span>${esc(e.ticker)}</span><span class="sub">${esc(e.note || "results")}</span><b class="num">${esc(e.date)}</b></div>`).join("")}
        <a href="#/calendar" class="ll-go">See the full earnings calendar →</a></div>`;
    }
    if (kind === "value") {
      const fv = await j("fairvalue.json");
      const rows = Object.entries(fv?.tickers || {}).slice(0, 3);
      if (!rows.length) return "";
      return `<div class="ll-live"><b>The same ratios, on real companies</b>
        ${rows.map(([s, v]) => `<div class="ll-row"><span>${esc(s)}</span><span class="sub">P/E ${esc(String(v.pe ?? "—"))}× · EPS Rs ${esc(String(v.eps ?? "—"))}</span><b class="num">Rs ${fmt(v.price)}</b></div>`).join("")}
        <a href="#/value" class="ll-go">See how the desk values every stock four ways →</a></div>`;
    }
    if (kind === "research") {
      const idx = await j("research_index.json");
      const docs = Object.values(idx?.documents || {}).slice(0, 3);
      if (!docs.length) return "";
      return `<div class="ll-live"><b>Filings the desk has digested</b>
        ${docs.map(d => `<div class="ll-row"><span>${esc(d.source || "")}</span><span class="sub">${esc((d.digest || "").slice(0, 70))}…</span><b class="num">${esc(d.date || "")}</b></div>`).join("")}
        <a href="#/research" class="ll-go">Read the research library →</a></div>`;
    }
    if (kind === "strategies") {
      const bt = await j("backtest.json");
      const n = Object.keys(bt?.results || bt?.strategies || {}).length;
      return `<div class="ll-live"><b>The bar, applied</b>
        <p class="sub">The desk holds every rule to win rate ≥55%, positive expectancy after costs, and profitability out-of-sample${n ? ` across ${n} tested sets` : ""} — and publishes the ones that failed too.</p>
        <a href="#/strategies" class="ll-go">See which rules actually cleared it →</a></div>`;
    }
    if (kind === "astro") {
      return `<div class="ll-live"><b>Your own chart</b>
        <p class="sub">Cast your birth chart in your browser and read the tradition against the market — framed as exploration, with the test result stated plainly.</p>
        <a href="#/mychart" class="ll-go">Open Your Chart →</a></div>`;
    }
  } catch { /* a lesson must never fail to render because a data file is missing */ }
  return "";
}

/* ---------- the lesson player: one idea per card, not a wall of text ----------
   A lesson is played in a focused overlay. Every card type gets its own visual treatment so it is
   never ambiguous whether you are being taught, shown real data, or tested. */
let _pl = null;   // {levelId, lesson, i, answered}

async function openLesson(levelId, lessonId) {
  const cur = await j("curriculum.json");
  const lv = (cur?.levels || []).find(l => l.id === levelId);
  const lesson = lv?.lessons.find(l => l.id === lessonId);
  if (!lesson) return;
  // Fetch the real anchor figures ONCE, before the first paint. renderPlayer must stay synchronous:
  // awaiting inside it let a second render interleave and leave stale .anatomy nodes in the DOM,
  // so clicks bound to a detached copy did nothing.
  const anchor = (lesson.cards || []).some(c => c.type === "anatomy" && c.doc === "income_statement")
    ? await anatomyAnchor() : null;
  _pl = { levelId, lesson, i: 0, answered: false, cur, anchor };
  renderPlayer();
}
function closePlayer() { _pl = null; document.querySelector(".pl-overlay")?.remove(); document.body.style.overflow = ""; pageLearn(); }
function plGo(d) {
  if (!_pl) return;
  const total = _pl.lesson.cards.length + (_pl.lesson.check ? 1 : 0);
  _pl.i = Math.max(0, Math.min(total - 1, _pl.i + d));
  renderPlayer();
}
function plAnswer(btn, correct) {
  const wrap = btn.closest(".pl-quiz");
  const picked = +btn.dataset.i;
  wrap.querySelectorAll(".ls-opt").forEach(b => b.disabled = true);
  btn.classList.add(picked === correct ? "right" : "wrong");
  if (picked !== correct) wrap.querySelector(`.ls-opt[data-i="${correct}"]`)?.classList.add("right");
  wrap.querySelector(".ls-explain").hidden = false;
  _pl.answered = true;
  const f = document.querySelector(".pl-foot-next");
  if (f) f.hidden = false;
}

/* An interactive, labelled financial statement. Structure is general accounting form; any figure
   shown as real is pulled from the desk's own fundamentals for a real company and labelled with
   its source. Lines the desk does not hold are marked "find this in the filing" — never invented. */
function anatomyHtml(kind, cur, anchor) {
  const a = cur?.anatomies?.[kind];
  if (!a) return "";
  const rows = a.lines.map((ln, i) => {
    if (ln.head) return `<div class="an-head">${esc(ln.l)}</div>`;
    const val = ln.field && anchor?.vals?.[ln.field];
    return `<button class="an-row ${ln.bold ? "b" : ""} ${val ? "has" : ""}" data-i="${i}" onclick="anaPick(this)">
      <span class="an-l" style="padding-left:${(ln.ind || 0) * 16}px">${esc(ln.l)}</span>
      <span class="an-v ${ln.neg ? "neg" : ""}">${val ? esc(val) : `<i>in the filing</i>`}</span>
      <span class="an-i">?</span></button>`;
  }).join("");
  return `<div class="anatomy" data-kind="${esc(kind)}">
    <div class="an-top"><b>${esc(a.title)}</b><span class="sub">${esc(a.subtitle)}</span></div>
    ${anchor ? `<div class="an-src">Real reported figures for <b>${esc(anchor.sym)}</b>${anchor.name ? ` — ${esc(anchor.name)}` : ""}, from the desk's data layer. The lines marked <i>in the filing</i> are the ones to go find in the company's own annual report — the desk does not hold them, so it does not show a number.</div>` : ""}
    <div class="an-rows">${rows}</div>
    <div class="an-detail" id="anDetail"><span class="sub">Tap any line to learn what it is and what to watch for.</span></div>
  </div>`;
}
function anaPick(btn) {
  const i = +btn.dataset.i, kind = btn.closest(".anatomy")?.dataset.kind;
  const a = _pl?.cur?.anatomies?.[kind]; if (!a) return;
  const ln = a.lines[i];
  document.querySelectorAll(".anatomy .an-row").forEach(b => b.classList.remove("on"));
  btn.classList.add("on");
  const d = document.getElementById("anDetail");
  if (d) d.innerHTML = `<div class="an-d-t">${esc(ln.l)}</div>
    <p>${esc(ln.what)}</p>
    <div class="an-d-w"><span class="ark">what to watch</span>${esc(ln.watch)}</div>`;
}

function docmapHtml(cur) {
  return `<div class="docmap">${(cur?.docmap || []).map((d, i) => `<button class="dm-item" data-i="${i}" onclick="dmPick(this)">
    <b>${esc(d.k)}</b><span class="sub">${esc(d.when)}</span></button>`).join("")}
    <div class="dm-detail" id="dmDetail"><span class="sub">Tap a document to see what it is and what to look for.</span></div></div>`;
}
function dmPick(btn) {
  const d = _pl?.cur?.docmap?.[+btn.dataset.i]; if (!d) return;
  document.querySelectorAll(".dm-item").forEach(b => b.classList.remove("on"));
  btn.classList.add("on");
  const el = document.getElementById("dmDetail");
  if (el) el.innerHTML = `<div class="an-d-t">${esc(d.k)} <span class="pill">${esc(d.when)}</span></div>
    <p>${esc(d.what)}</p><div class="an-d-w"><span class="ark">what to look for</span>${esc(d.look)}</div>`;
}

const DIV_TIMELINE = [
  { k: "Announcement", d: "The board declares a dividend.", n: "Nothing is owed to anyone yet." },
  { k: "Ex-dividend date", d: "From this day the share trades WITHOUT the dividend.", n: "You must already own it before this date. This is the one that decides whether you are paid.", hot: true },
  { k: "Book closure", d: "The register is frozen to determine who gets paid.", n: "Transfers are not processed during this window." },
  { k: "Payment date", d: "Cash actually reaches you.", n: "Withholding tax is deducted at this point." },
];
function timelineHtml() {
  return `<div class="divtl">${DIV_TIMELINE.map((s, i) => `<div class="dt-step ${s.hot ? "hot" : ""}">
    <div class="dt-dot">${i + 1}</div><div class="dt-c"><b>${esc(s.k)}</b><span class="sub">${esc(s.d)}</span>
    <div class="dt-n">${esc(s.n)}</div></div></div>`).join("")}</div>`;
}

function renderPlayer() {
  if (!_pl) return;
  let ov = document.querySelector(".pl-overlay");
  if (!ov) {
    ov = document.createElement("div"); ov.className = "pl-overlay"; document.body.appendChild(ov);
    document.body.style.overflow = "hidden";
    ov.addEventListener("click", e => { if (e.target === ov) closePlayer(); });
  }
  const { lesson, levelId } = _pl;
  const cards = lesson.cards || [];
  const total = cards.length + (lesson.check ? 1 : 0);
  const isQuiz = _pl.i >= cards.length;
  const c = cards[_pl.i];
  const KIND = { text: "lesson", warn: "watch out", key: "the point", anatomy: "interactive", docmap: "interactive", timeline: "interactive" };

  let body = "";
  if (isQuiz) {
    body = `<div class="pl-card k-q">
      <div class="pl-kind k-quiz">check yourself</div>
      <div class="pl-q">${esc(lesson.check.q)}</div>
      <div class="pl-quiz">
        ${lesson.check.options.map((o, i) => `<button class="ls-opt" data-i="${i}" onclick="plAnswer(this,${lesson.check.answer})">${esc(o)}</button>`).join("")}
        <div class="ls-explain" hidden>${esc(lesson.check.explain)}</div>
      </div></div>`;
  } else {
    const inner = c.type === "anatomy" ? anatomyHtml(c.doc, _pl.cur, c.doc === "income_statement" ? _pl.anchor : null)
      : c.type === "docmap" ? docmapHtml(_pl.cur)
        : c.type === "timeline" ? timelineHtml() : "";
    // card-kind classes are namespaced (k-*): a bare `anatomy` class would collide with the
    // .anatomy component rendered inside the card and inherit its border.
    body = `<div class="pl-card k-${c.type}">
      <div class="pl-kind k-${c.type}">${esc(KIND[c.type] || "lesson")}</div>
      ${c.h ? `<h2 class="pl-h">${esc(c.h)}</h2>` : ""}
      ${(c.p || []).map(p => `<p>${esc(p)}</p>`).join("")}
      ${inner}
    </div>`;
  }

  ov.innerHTML = `<div class="pl-box">
    <div class="pl-top">
      <div class="pl-title"><span class="ark">${esc((_pl.cur.levels.find(l => l.id === levelId) || {}).title || "")}</span><b>${esc(lesson.title)}</b></div>
      <button class="pl-x" onclick="closePlayer()">✕</button>
    </div>
    <div class="pl-dots">${Array.from({ length: total }, (_, i) =>
    `<span class="pl-dot ${i === _pl.i ? "on" : i < _pl.i ? "did" : ""}"></span>`).join("")}</div>
    <div class="pl-body">${body}</div>
    <div class="pl-foot">
      <button class="pl-back" onclick="plGo(-1)" ${_pl.i === 0 ? "disabled" : ""}>← back</button>
      <span class="pl-count">${_pl.i + 1} / ${total}</span>
      ${isQuiz
      ? `<button class="bw-go pl-foot-next" ${_pl.answered ? "" : "hidden"} onclick="finishLesson()">Complete lesson →</button>`
      : `<button class="bw-go" onclick="plGo(1)">Next →</button>`}
    </div>
  </div>`;

}

/* Pick a well-known name the desk actually holds figures for, and format them honestly. */
async function anatomyAnchor() {
  try {
    const [f, uni] = await Promise.all([j("fundamentals.json"), j("universe.json")]);
    const t = f?.tickers || {};
    const pref = ["FFC", "OGDC", "LUCK", "MCB", "ENGRO", "PPL", "HUBC"];
    const sym = pref.find(s => t[s]?.revenue && t[s]?.net_income && t[s]?.eps)
      || Object.keys(t).find(s => t[s]?.revenue && t[s]?.net_income && t[s]?.eps);
    if (!sym) return null;
    const d = t[sym];
    return { sym, name: uni?.symbols?.[sym]?.name || "",
      vals: { revenue: "Rs " + d.revenue, net_income: "Rs " + d.net_income, eps: "Rs " + d.eps } };
  } catch { return null; }
}

async function finishLesson() {
  if (!_pl) return;
  const { levelId, lesson } = _pl;
  closePlayer();
  await markLesson(levelId, lesson.id, true);
}

async function pageLearn() {
  await Promise.resolve();
  const cur = await j("curriculum.json");
  const levels = cur?.levels || [];
  if (!levels.length) {
    $("view").innerHTML = `<div class="seg" style="margin-top:4px"><h2>Learn</h2><div class="ln"></div></div>
      <div class="card"><div class="empty">The syllabus is being prepared.</div></div>`;
    return;
  }
  const all = levels.flatMap(v => v.lessons.map(l => ({ s: v.id, l: l.id })));
  const doneN = all.filter(x => lessonDone(x.s, x.l)).length;
  const pct = Math.round(doneN / all.length * 100);
  const totalMins = levels.flatMap(v => v.lessons).reduce((a, l) => a + (l.mins || 0), 0);
  const doneIn = v => v.lessons.filter(l => lessonDone(v.id, l.id)).length;
  // a level opens when the one before it is finished — progression, but never a dead end:
  // the first unfinished level is always open, so nobody can get stuck.
  const unlocked = i => i === 0 || doneIn(levels[i - 1]) === levels[i - 1].lessons.length;
  const nextUp = all.find(x => !lessonDone(x.s, x.l));

  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Become an investor</h2><div class="ln"></div><span class="pill">${levels.length} levels · ${all.length} lessons · ~${totalMins} min</span></div>
  <div class="disclaimer">Education, <b>not investment advice</b>. This teaches you to read companies, prices and payouts for yourself — it never tells you what to buy, and nothing here is a recommendation or a forecast.</div>

  <div class="card learn-hero">
    <div class="lh-top">
      <div><div class="ark">your progress</div><b style="font-size:22px">${doneN} of ${all.length}</b><span class="sub"> lessons complete</span></div>
      <div class="lh-pct"><b>${pct}%</b></div>
    </div>
    <div class="lh-bar"><span style="width:${pct}%"></span></div>
    ${nextUp ? `<button class="bw-go" style="max-width:300px;margin-top:14px" onclick="openLesson('${esc(nextUp.s)}','${esc(nextUp.l)}')">${doneN ? "Continue where you left off" : "Start level 1"} →</button>`
      : `<p class="sub" style="margin-top:12px"><b>You've finished every level.</b> The market keeps teaching — the News wire and Earnings calendar are where the next lessons come from.</p>`}
  </div>

  ${levels.map((v, i) => {
    const dn = doneIn(v), open = unlocked(i), full = dn === v.lessons.length;
    return `<div class="lvl ${open ? "" : "locked"} ${full ? "full" : ""}">
      <div class="lvl-head">
        <span class="lvl-n">${full ? "✓" : v.n}</span>
        <div class="lvl-t"><b>Level ${v.n} · ${esc(v.title)}</b><span class="sub">${esc(v.blurb)}</span></div>
        <span class="pill ${full ? "ok" : ""}">${dn}/${v.lessons.length}</span>
      </div>
      ${open ? `<div class="lvl-lessons">${v.lessons.map((l, k) => {
      const d = lessonDone(v.id, l.id);
      return `<button class="lsn ${d ? "done" : ""}" onclick="openLesson('${esc(v.id)}','${esc(l.id)}')">
          <span class="lsn-n">${d ? "✓" : k + 1}</span>
          <span class="lsn-t"><b>${esc(l.title)}</b><span class="sub">${esc(l.why)}</span></span>
          <span class="lsn-m">${l.mins} min</span></button>`;
    }).join("")}</div>`
        : `<div class="lvl-locked"><span class="sub">Finish Level ${v.n - 1} to open this — the lessons build on each other.</span></div>`}
    </div>`;
  }).join("")}`;
}

/* Shareable entry point for the astro funnel: /#/cast drops you straight into the wizard.
   The reading itself lives at /#/mychart, which this hands off to. */
async function pageCast() {
  await pageMyChart();
  if (!natalChart()) setTimeout(openBirthWizard, 60);
}
const PAGES = { learn: pageLearn, plans: pagePlans, cast: pageCast, today: pageToday, board: pageBoard, watchlist: pageWatchlist, portfolio: pagePortfolio, settings: pageSettings, strategies: pageStrategies, value: pageValue, macro: pageMacro, astro: pageAstro, mychart: pageMyChart, dividends: pageDividends, calendar: pageCalendar, research: pageResearch, leaderboard: pageLeaderboard, news: pageNews, legal: pageLegal };
let lastPage = null;

function animateIn() {
  const v = $("view");
  v.classList.remove("enter"); void v.offsetWidth; v.classList.add("enter");
}

async function route(isPoll) {
  // Supabase auth callbacks (email confirm / password reset) arrive in the hash —
  // they're not routes; auth.js consumes them and then navigates.
  if (/access_token=|error_code=|type=recovery|type=signup/.test(location.hash)) return;
  const h = location.hash || "#/today";
  const [, page, arg] = h.split("/");
  document.querySelectorAll("[data-nav]").forEach(a => a.classList.toggle("on", a.dataset.nav === (page || "today")));
  renderHeader();
  const key = page + (arg || "");
  try {
    if (page === "ticker" && arg) { await pageTicker(arg); }
    else { await (PAGES[page] || pageBoard)(); }
  } catch (err) {
    // a page render must NEVER leave a blank screen — show the failure instead
    console.error("page render failed:", page, arg, err);
    const v = $("view");
    if (v && (!v.innerHTML || v.innerText.trim().length < 40)) {
      v.innerHTML = `<a class="crumb" href="#/board">← board</a>
        <div class="card"><div class="empty">Couldn't render ${esc((page || "this page") + (arg ? " " + arg : ""))} — a data file may still be loading or unavailable this cycle.<br><br>
        <b>Try:</b> reload the page (Ctrl+Shift+R to bypass cache). If it persists, the desk's data for this name may be missing this cycle.<br>
        <span class="sub">${esc(String(err && err.message || err)).slice(0, 160)}</span></div></div>`;
    }
  }
  // animate only on a real navigation (not the 30s silent refresh of the same page)
  if (!isPoll && key !== lastPage) { animateIn(); if (window.scrollTo) window.scrollTo(0, 0); }
  lastPage = key;
}
window.addEventListener("hashchange", () => route(false));
// NOTE: do NOT call applyDeskMode() here — this line runs before `let me` is initialized further
// down the file, and deskMode() reads it, which throws a TDZ error and aborts the whole module.
// index.html ships data-desk="pro" as the default; initAuth re-stamps it once the plan is known.
route(false);
// Keep only the top status pills current on a gentle cadence — do NOT re-render the whole
// page body (that caused a jarring full-page refresh/flicker every cycle). Header-only, and
// paused while a modal is open. The body updates on navigation or a manual reload.
setInterval(() => {
  if (document.querySelector(".replay-overlay, #authbox, .wizbox:not([hidden])")) return;
  Object.keys(cache).forEach(k => delete cache[k]);   // let the header refetch fresh pills
  if (typeof renderHeader === "function") renderHeader();
}, 60000);

/* ---------- ticker search ---------- */
let searchIndex = null;
async function loadSearchIndex() {
  if (searchIndex) return searchIndex;
  const uni = await j("universe.json");
  searchIndex = Object.entries(uni?.symbols || {}).map(([s, v]) => ({ s, name: (v.name || "").toLowerCase(), disp: v.name || "" }));
  return searchIndex;
}

/* ---------- themed ticker combobox: replaces the native <datalist>, which browsers render
   unstyled (the raw grey popup). One delegated instance serves every input with class "combo";
   it filters the universe, is keyboard-navigable, and matches the terminal's hard-cornered look. */
let _comboEl = null, _comboInput = null, _comboIdx = -1;
function _comboClose() { if (_comboEl) { _comboEl.remove(); _comboEl = null; _comboInput = null; _comboIdx = -1; } }
async function _comboOpen(input) {
  const idx = await loadSearchIndex();
  _comboInput = input;
  if (!_comboEl) { _comboEl = document.createElement("div"); _comboEl.className = "combo-pop"; document.body.appendChild(_comboEl); }
  _comboRender(idx, input.value);
  _comboPosition();
}
function _comboPosition() {
  if (!_comboEl || !_comboInput) return;
  const r = _comboInput.getBoundingClientRect();
  _comboEl.style.left = r.left + window.scrollX + "px";
  _comboEl.style.top = r.bottom + window.scrollY + "px";
  _comboEl.style.width = Math.max(180, r.width) + "px";
}
function _comboRender(idx, q) {
  q = (q || "").trim().toUpperCase();
  const hits = (q
    ? idx.filter(x => x.s.startsWith(q)).concat(idx.filter(x => !x.s.startsWith(q) && (x.s.includes(q) || x.name.includes(q.toLowerCase()))))
    : idx.slice()).slice(0, 40);
  _comboIdx = -1;
  _comboEl.innerHTML = hits.length
    ? hits.map((h, i) => `<div class="combo-opt" data-sym="${h.s}" data-i="${i}"><b>${h.s}</b><span>${esc((h.disp || "").slice(0, 30))}</span></div>`).join("")
    : `<div class="combo-empty">No match for "${esc(q)}"</div>`;
}
function _comboPick(sym) {
  if (_comboInput) {
    _comboInput.value = sym;
    _comboInput.dispatchEvent(new Event("input", { bubbles: true }));
    const btn = _comboInput.closest(".sb-add, .ph-form, .ph-row, .rq-form")?.querySelector(".note-save");
    _comboInput.focus();
  }
  _comboClose();
}
document.addEventListener("focusin", e => { const el = e.target.closest("input.combo"); if (el) _comboOpen(el); });
document.addEventListener("input", e => { if (e.target.closest("input.combo") && _comboEl) loadSearchIndex().then(idx => _comboRender(idx, e.target.value)); });
document.addEventListener("click", e => {
  const opt = e.target.closest(".combo-opt");
  if (opt) { e.preventDefault(); _comboPick(opt.dataset.sym); return; }
  if (!e.target.closest("input.combo") && !e.target.closest(".combo-pop")) _comboClose();
});
document.addEventListener("keydown", e => {
  if (!_comboEl || !_comboInput || document.activeElement !== _comboInput) return;
  const opts = [..._comboEl.querySelectorAll(".combo-opt")];
  if (!opts.length) return;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    _comboIdx = (_comboIdx + (e.key === "ArrowDown" ? 1 : -1) + opts.length) % opts.length;
    opts.forEach((o, i) => o.classList.toggle("on", i === _comboIdx));
    opts[_comboIdx].scrollIntoView({ block: "nearest" });
  } else if (e.key === "Enter" && _comboIdx >= 0) {
    e.preventDefault(); _comboPick(opts[_comboIdx].dataset.sym);
  } else if (e.key === "Escape") { _comboClose(); }
});
window.addEventListener("scroll", _comboPosition, true);
window.addEventListener("resize", _comboPosition);
function openSearch() {
  const box = $("searchbox"); box.hidden = false;
  const inp = $("searchinput"); inp.value = ""; $("searchresults").innerHTML = "";
  loadSearchIndex(); setTimeout(() => inp.focus(), 30);
}
function closeSearch() { const b = $("searchbox"); if (b) b.hidden = true; }
function goTicker(sym) { closeSearch(); location.hash = "#/ticker/" + sym; }
async function runSearch(q) {
  q = q.trim().toUpperCase();
  const res = $("searchresults");
  if (!q) { res.innerHTML = ""; return; }
  const idx = await loadSearchIndex();
  const hits = idx.filter(x => x.s.startsWith(q)).concat(
    idx.filter(x => !x.s.startsWith(q) && (x.s.includes(q) || x.name.includes(q.toLowerCase())))
  ).slice(0, 12);
  res.innerHTML = hits.length
    ? hits.map(h => `<div class="searchitem" data-sym="${h.s}"><b>${h.s}</b><span>${esc(h.name)}</span></div>`).join("")
    : `<div class="searchitem" style="opacity:.6">No match for "${esc(q)}"</div>`;
}
document.addEventListener("DOMContentLoaded", () => {
  const btn = $("searchbtn");
  if (btn) btn.addEventListener("click", openSearch);
});
// header exists at load (script is at end of body), so wire immediately too:
$("searchbtn")?.addEventListener("click", openSearch);
$("searchinput")?.addEventListener("input", e => runSearch(e.target.value));
$("searchinput")?.addEventListener("keydown", e => {
  if (e.key === "Escape") closeSearch();
  if (e.key === "Enter") { const first = document.querySelector(".searchitem[data-sym]"); if (first) goTicker(first.dataset.sym); }
});
$("searchresults")?.addEventListener("click", e => {
  const it = e.target.closest(".searchitem[data-sym]"); if (it) goTicker(it.dataset.sym);
});
$("searchbox")?.addEventListener("click", e => { if (e.target.id === "searchbox") closeSearch(); });
$("searchclose")?.addEventListener("click", closeSearch);
// closing whenever the route changes (e.g. after picking a ticker) and on Escape anywhere
window.addEventListener("hashchange", closeSearch);
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeSearch();
  if (e.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) { e.preventDefault(); openSearch(); }
});

/* ---------- sidebar: collapse (desktop) + drawer (mobile) ---------- */
const shell = $("shell");
if (shell && localStorage.getItem("sideCollapsed") === "1") shell.classList.add("collapsed");
$("sideToggle")?.addEventListener("click", () => {
  const c = shell.classList.toggle("collapsed");
  localStorage.setItem("sideCollapsed", c ? "1" : "0");
});
const openDrawer = () => shell.classList.add("drawer");
const closeDrawer = () => shell.classList.remove("drawer");
$("sideOpen")?.addEventListener("click", openDrawer);
$("sideBackdrop")?.addEventListener("click", closeDrawer);
// close the mobile drawer after navigating or on Escape
window.addEventListener("hashchange", closeDrawer);
document.addEventListener("keydown", e => { if (e.key === "Escape") closeDrawer(); });

/* drag-to-resize the sidebar (desktop, expanded only), clamped + persisted */
const SIDE_MIN = 168, SIDE_MAX = 380;
if (shell) {
  const savedW = parseInt(localStorage.getItem("sideW"), 10);
  if (savedW >= SIDE_MIN && savedW <= SIDE_MAX) shell.style.setProperty("--side-w", savedW + "px");
}
$("sideResize")?.addEventListener("mousedown", e => {
  if (shell.classList.contains("collapsed")) return;
  e.preventDefault();
  shell.classList.add("resizing");
  const move = ev => {
    const w = Math.min(SIDE_MAX, Math.max(SIDE_MIN, ev.clientX));
    shell.style.setProperty("--side-w", w + "px");
  };
  const up = () => {
    shell.classList.remove("resizing");
    const w = parseInt(getComputedStyle(shell).getPropertyValue("--side-w"), 10);
    if (w) localStorage.setItem("sideW", w);
    document.removeEventListener("mousemove", move);
    document.removeEventListener("mouseup", up);
  };
  document.addEventListener("mousemove", move);
  document.addEventListener("mouseup", up);
});


/* ================= ACCOUNTS + ONBOARDING (merged from auth.js: the deploy workflow only ships app.js) ================= */
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
    const plan = PLANS[planOf()];
    // account menu, in the shape people already know: identity at the top, the plan you're on
    // stated plainly under it, then actions.
    holder.innerHTML = `<button class="acct-btn" id="acctBtn" title="${me.email}">${initial}</button>
      <div class="acct-menu" id="acctMenu" hidden>
        <div class="acct-id"><span class="acct-av">${initial}</span><div><div class="acct-email">${me.email}</div>
          <div class="acct-plan">${esc(plan.label)} plan</div></div></div>
        <div class="acct-sep"></div>
        <button id="acctPlans"><span>Plans</span><span class="acct-chip ${planOf() === "free" ? "" : "on"}">${esc(plan.label)}</span></button>
        <button id="acctSettings">Settings</button>
        <button id="acctMode">${deskMode() === "learn" ? "Switch to the Pro desk" : "Switch to the Learner desk"}</button>
        <button id="acctTour">Replay the tour</button>
        <div class="acct-sep"></div>
        <button id="acctOut">Sign out</button>
      </div>`;
    const menu = document.getElementById("acctMenu");
    document.getElementById("acctBtn").onclick = (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; };
    document.getElementById("acctOut").onclick = async () => { await sb.auth.signOut(); location.reload(); };
    document.getElementById("acctSettings").onclick = () => { menu.hidden = true; location.hash = "#/settings"; };
    document.getElementById("acctPlans").onclick = () => { menu.hidden = true; location.hash = "#/plans"; };
    document.getElementById("acctMode").onclick = () => { menu.hidden = true; setDeskMode(deskMode() === "learn" ? "pro" : "learn"); };
    document.getElementById("acctTour").onclick = () => { menu.hidden = true; startWizard(true); };
  } else {
    holder.innerHTML = `<button class="acct-signin" id="acctIn">Sign in</button>`;
    document.getElementById("acctIn").onclick = () => openAuth("signin");
  }
}

// Close the account menu on any outside click / Escape / navigation. Registered ONCE,
// in the CAPTURE phase so a stopPropagation() elsewhere in the SPA can't keep it stuck open.
if (!window.__acctMenuGuard) {
  window.__acctMenuGuard = true;
  const closeAcct = () => { const m = document.getElementById("acctMenu"); if (m) m.hidden = true; };
  document.addEventListener("click", (e) => {
    const m = document.getElementById("acctMenu"), holder = document.getElementById("acctSlot");
    if (m && !m.hidden && holder && !holder.contains(e.target)) m.hidden = true;
  }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeAcct(); });
  window.addEventListener("hashchange", closeAcct);
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
      <div class="auth-legal">Research &amp; analytics tool, not an investment adviser. By continuing you agree to the <a href="#/legal/terms" onclick="closeAuth()">Terms</a>, <a href="#/legal/privacy" onclick="closeAuth()">Privacy Policy</a> and <a href="#/legal/risk" onclick="closeAuth()">Risk Disclosure</a> — nothing here is personalized advice.</div>
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
  if (!me) return "not_signed_in";   // distinguishable from success (falsy) — never silently equated with it
  patch.id = me.id;
  const { error } = await sb.from("profiles").upsert(patch);
  if (!error) myProfile = { ...(myProfile || {}), ...patch };
  return error;
}

/* ---------- watchlist (per-user, persisted to profiles.watchlist) ---------- */
function watchlist() { return (myProfile && myProfile.watchlist) || []; }
function isWatched(sym) { return watchlist().includes(sym); }

/* ---------- private per-ticker notes (persisted to profiles.notes, RLS-scoped) ---------- */
function noteFor(sym) { return ((myProfile && myProfile.notes) || {})[sym] || ""; }
async function saveTickerNote(sym) {
  const ta = document.getElementById("tknote"); if (!ta) return;
  const st = document.getElementById("tknote-status");
  if (!me) { if (st) st.textContent = "Signed out — sign in to save"; openAuth("signin"); return; }
  const notes = { ...((myProfile && myProfile.notes) || {}) };
  const v = ta.value.trim(); if (v) notes[sym] = v; else delete notes[sym];
  if (st) st.textContent = "Saving…";
  const err = await saveProfile({ notes });
  if (st) { st.textContent = err ? "Save failed — try again" : "Saved ✓"; setTimeout(() => { if (st) st.textContent = ""; }, 2500); }
}
async function toggleWatch(sym, btn) {
  if (!me) { openAuth("signup"); return; }               // must be signed in to save
  const cur = new Set(watchlist());
  cur.has(sym) ? cur.delete(sym) : cur.add(sym);
  const next = [...cur];
  if (btn) { btn.classList.toggle("on", cur.has(sym)); btn.disabled = true; }
  await saveProfile({ watchlist: next });
  if (btn) btn.disabled = false;
  if (location.hash === "#/watchlist") pageWatchlist();   // live-refresh the list view
}
// star button markup (used on ticker pages). onclick wired via delegation below.
function starBtn(sym) {
  return `<button class="starbtn ${isWatched(sym) ? "on" : ""}" data-watch="${esc(sym)}" title="${me ? "Add to / remove from your watchlist" : "Sign in to save to a watchlist"}" aria-label="watchlist">
    <svg viewBox="0 0 24 24"><path d="M12 3l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 18l-5.9 3 1.2-6.5L2.5 9.9 9.1 9z"/></svg></button>`;
}
// one delegated handler for every star on the page
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-watch]");
  if (b) { e.preventDefault(); e.stopPropagation(); toggleWatch(b.dataset.watch, b); }
  const bk = e.target.closest("[data-broker]");
  if (bk) { e.preventDefault(); e.stopPropagation(); toggleBroker(bk.dataset.broker); }
  const sd = e.target.closest("[data-sbdel]");
  if (sd) { e.preventDefault(); e.stopPropagation(); removeBoardTicker(sd.dataset.sbdel); }
  const ad = e.target.closest("[data-abdel]");
  if (ad) { e.preventDefault(); e.stopPropagation(); removeAstroTicker(ad.dataset.abdel); }
});

/* ---------- portfolio: read-only holdings tracker (profiles.portfolio, RLS-scoped) ---------- */
function portfolio() { return (myProfile && myProfile.portfolio) || []; }
async function addHolding(sym, shares, avgCost) {
  if (!me) { openAuth("signup"); return "sign in first"; }
  sym = (sym || "").toUpperCase().trim();
  shares = +shares; avgCost = +avgCost;
  if (!sym || !(shares > 0) || !(avgCost > 0)) return "enter a ticker, a share count and an average cost";
  const p = portfolio().filter(h => h.ticker !== sym);   // one row per ticker; re-adding overwrites
  p.push({ ticker: sym, shares, avg_cost: avgCost, added: new Date().toISOString().slice(0, 10) });
  const saveErr = await saveProfile({ portfolio: p });
  return saveErr ? "couldn't save — try again" : null;
}
async function removeHolding(sym) {
  await saveProfile({ portfolio: portfolio().filter(h => h.ticker !== (sym || "").toUpperCase()) });
  if (location.hash.startsWith("#/portfolio")) pagePortfolio();
}
async function submitHolding() {
  const t = document.getElementById("ph-tkr"), s = document.getElementById("ph-sh"), c = document.getElementById("ph-cost");
  const msg = document.getElementById("ph-msg");
  const err = await addHolding(t.value, s.value, c.value);
  if (err) { if (msg) { msg.textContent = err; msg.className = "sub dn"; } return; }
  t.value = s.value = c.value = "";
  pagePortfolio();
}

async function pagePortfolio() {
  const [quant, uni, live, divs, sectAll] = await Promise.all([j("quant.json"), j("universe.json"), j("live.json"), j("dividends.json"), j("sectors.json")]);
  if (!me) {
    $("view").innerHTML = `<div class="seg" style="margin-top:4px"><h2>Your portfolio</h2><div class="ln"></div></div>
      <div class="card"><div class="empty">Sign in to track your holdings — enter what you own and the desk shows your live value, profit/loss, position weights and estimated dividend income. Private to you, read-only: the desk never trades. Research, not advice.<br><br>
      <button class="auth-go" style="max-width:220px" onclick="openAuth('signup')">Create a free account</button></div></div>`;
    return;
  }
  const q = quant?.tickers || {}, lv = live?.tickers || {}, names = uni?.symbols || {};
  const dHist = divs?.history || [];
  const rows = portfolio().map(h => {
    const qq = q[h.ticker];
    const px = lv[h.ticker]?.current ?? qq?.close ?? null;
    const mv = px != null ? px * h.shares : null;
    const cost = h.avg_cost * h.shares;
    const pl = mv != null ? mv - cost : null;
    const plPct = (mv != null && cost > 0) ? (mv / cost - 1) * 100 : null;
    const lastDiv = dHist.filter(d => d.symbol === h.ticker).sort((a, b) => (b.bc_start || "").localeCompare(a.bc_start || ""))[0];
    const annualDiv = lastDiv?.dividend_rs ? lastDiv.dividend_rs * h.shares : null;
    return { ...h, px, mv, cost, pl, plPct, annualDiv, name: names[h.ticker]?.name || "", known: !!qq,
      sector: (sectAll?.tickers?.[h.ticker] || {}).sector || null };
  });
  const totMv = rows.reduce((a, r) => a + (r.mv || 0), 0);
  const totCost = rows.reduce((a, r) => a + r.cost, 0);
  const totPl = totMv - totCost;
  const totPlPct = totCost > 0 ? (totMv / totCost - 1) * 100 : null;
  const totDiv = rows.reduce((a, r) => a + (r.annualDiv || 0), 0);
  const withW = rows.map(r => ({ ...r, w: totMv > 0 ? (r.mv || 0) / totMv * 100 : 0 })).sort((a, b) => b.w - a.w);
  const top = withW[0], top3 = withW.slice(0, 3).reduce((a, r) => a + r.w, 0);
  const concFlag = !withW.length ? "" :
    top.w >= 40 ? `Your largest position, <b>${esc(top.ticker)}</b>, is <b>${top.w.toFixed(0)}%</b> of the portfolio.`
      : top3 >= 65 && withW.length >= 3 ? `Your top 3 positions make up <b>${top3.toFixed(0)}%</b> of the portfolio.`
        : `Your largest position is <b>${top.w.toFixed(0)}%</b> — reasonably spread across ${withW.length} name${withW.length === 1 ? "" : "s"}.`;

  // ---- sector concentration: the exposure that actually bites. Two banks are one bet on rates,
  // however different their tickers look. (This used to say sectors weren't in the feed — they are now.)
  const secW = {};
  withW.forEach(r => { const k = r.sector || "Unclassified"; secW[k] = (secW[k] || 0) + r.w; });
  const secRows = Object.entries(secW).sort((a, b) => b[1] - a[1]);
  const topSec = secRows[0];
  const secFlag = !secRows.length ? "" :
    secRows.length === 1 ? `Every rupee you hold is in <b>${esc(topSec[0])}</b>. One sector shock moves your whole portfolio at once.`
      : topSec[1] >= 50 ? `<b>${topSec[1].toFixed(0)}%</b> of your portfolio sits in <b>${esc(topSec[0])}</b> — those names tend to rise and fall together, whatever their tickers say.`
        : `Your biggest sector is <b>${esc(topSec[0])}</b> at <b>${topSec[1].toFixed(0)}%</b>, spread across ${secRows.length} sectors.`;
  const sTile = (label, val, sub, k) => `<div class="sumtile"><span class="sk">${label}</span><b class="${k || ""}">${val}</b>${sub ? `<i>${sub}</i>` : ""}</div>`;

  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Your portfolio</h2><div class="ln"></div><span class="pill">${rows.length} holding${rows.length === 1 ? "" : "s"}</span></div>
  <div class="disclaimer">A private, <b>read-only</b> tracker of what you own — the desk never places orders and holds no money. Every figure below is a <b>fact about your holdings</b>, computed from desk prices; none of it is advice or a recommendation to buy or sell.</div>

  <div class="card ph-form">
    <div class="ph-row">
      <input id="ph-tkr" placeholder="Ticker (e.g. FFC)" class="ph-in combo" autocomplete="off">
      <input id="ph-sh" type="number" placeholder="Shares" class="ph-in" min="0" step="1">
      <input id="ph-cost" type="number" placeholder="Avg cost (Rs)" class="ph-in" min="0" step="0.01">
      <button class="note-save" onclick="submitHolding()">Add holding</button>
    </div>
    <span id="ph-msg" class="sub"></span>
  </div>

  ${rows.length ? `<div class="sumstrip s4">
    ${sTile("Portfolio value", "Rs " + fmt(totMv, 0), "at desk prices", "")}
    ${sTile("Total profit / loss", (totPl >= 0 ? "+" : "") + "Rs " + fmt(totPl, 0), totPlPct != null ? sgn(totPlPct) + "% on cost" : "", totPl >= 0 ? "up" : "dn")}
    ${sTile("Est. annual dividend", "Rs " + fmt(totDiv, 0), "from last declared payouts", "")}
    ${sTile("Positions", rows.length, "one row per ticker", "")}
  </div>

  <div class="card"><table><thead><tr><th>Ticker</th><th class="r">Shares</th><th class="r">Avg cost</th><th class="r">Price</th><th class="r">Value</th><th class="r">P/L</th><th class="r">Weight</th><th></th></tr></thead><tbody>${
    withW.map(r => `<tr>
      <td class="clickable" onclick="location.hash='#/ticker/${esc(r.ticker)}'"><b>${esc(r.ticker)}</b> <span class="sub">${esc((r.name || "").slice(0, 16))}</span>${r.known ? "" : ' <span class="sub dn">not in universe</span>'}${r.sector ? `<div class="sub" style="opacity:.7">${esc(r.sector)}</div>` : ""}</td>
      <td class="r num">${fmt(r.shares)}</td><td class="r num">${fmt(r.avg_cost)}</td>
      <td class="r num">${r.px != null ? fmt(r.px) : "—"}</td>
      <td class="r num">${r.mv != null ? fmt(r.mv, 0) : "—"}</td>
      <td class="r num ${r.pl == null ? "" : r.pl >= 0 ? "up" : "dn"}">${r.plPct != null ? sgn(r.plPct) + "%" : "—"}${r.pl != null ? `<div class="sub">${(r.pl >= 0 ? "+" : "") + fmt(r.pl, 0)}</div>` : ""}</td>
      <td class="r num">${r.w.toFixed(0)}%</td>
      <td class="r"><button class="ph-del" onclick="removeHolding('${esc(r.ticker)}')" title="Remove holding">✕</button></td></tr>`).join("")}
  </tbody><tfoot><tr><td><b>Total</b></td><td></td><td></td><td></td><td class="r num"><b>${fmt(totMv, 0)}</b></td>
    <td class="r num ${totPl >= 0 ? "up" : "dn"}"><b>${totPlPct != null ? sgn(totPlPct) + "%" : "—"}</b></td><td></td><td></td></tr></tfoot></table></div>

  <div class="seg"><h2>Concentration</h2><div class="ln"></div><span class="pill">fact, not advice</span></div>
  <div class="card">
    <p class="sub" style="line-height:1.6;margin-bottom:12px">${concFlag} Concentration means your portfolio rises and falls with fewer bets; diversification spreads that risk across more names. Whether that's right for you depends on your own goals and risk tolerance — the desk states the fact and the general principle, and never tells you to buy or sell.</p>
    <div class="ph-bars">${withW.map(r => `<div class="ph-bar-row"><span class="ph-bar-lbl">${esc(r.ticker)}</span><span class="ph-bar-track"><span class="ph-bar-fill" style="width:${Math.max(2, r.w).toFixed(0)}%"></span></span><span class="ph-bar-val num">${r.w.toFixed(0)}%</span></div>`).join("")}</div>
  </div>

  <div class="seg"><h2>Sector concentration</h2><div class="ln"></div><span class="pill">${secRows.length} sector${secRows.length === 1 ? "" : "s"}</span></div>
  <div class="card">
    <p class="sub" style="line-height:1.6;margin-bottom:12px">${secFlag} This is the exposure position weights hide: two banks are one bet on interest rates, and two cement names are one bet on construction — however different the tickers look. Sectors are PSX's own classification. Stated as a fact about your holdings, not as advice.</p>
    <div class="ph-bars">${secRows.map(([s, pct]) => `<div class="ph-bar-row"><span class="ph-bar-lbl" title="${esc(s)}">${esc(s.length > 22 ? s.slice(0, 21) + "…" : s)}</span><span class="ph-bar-track"><span class="ph-bar-fill" style="width:${Math.max(2, pct).toFixed(0)}%"></span></span><span class="ph-bar-val num">${pct.toFixed(0)}%</span></div>`).join("")}</div>
  </div>

  <p class="sub" style="margin-top:14px">Estimated dividend income is each holding's most recent declared dividend × your shares — an estimate from past payouts, not a promise; companies can cut or skip dividends. Prices are desk end-of-day/live figures and may differ from your broker. Research, not advice.</p>`
    : `<div class="card"><div class="empty">No holdings yet. Add one above — enter a ticker, how many shares, and your average cost, and the desk tracks your live value, profit/loss and position weights here.</div></div>`}`;
}

async function pageWatchlist() {
  const [quant, uni, fvAll, fscore, live] = await Promise.all([
    j("quant.json"), j("universe.json"), j("fairvalue.json"), j("fundamental_scores.json"), j("live.json")]);
  if (!me) {
    $("view").innerHTML = `<div class="seg" style="margin-top:4px"><h2>Your watchlist</h2><div class="ln"></div></div>
      <div class="card"><div class="empty">Sign in to build a watchlist — star any stock and it follows you here with its price, valuation and health at a glance.<br><br>
      <button class="auth-go" style="max-width:220px" onclick="openAuth('signup')">Create a free account</button></div></div>`;
    return;
  }
  const wl = watchlist();
  const q = quant?.tickers || {}, fv = fvAll?.tickers || {}, fs = fscore?.tickers || {}, lv = live?.tickers || {};
  const rows = wl.map(s => ({ s, name: uni?.symbols?.[s]?.name || "", q: q[s], fv: fv[s], fs: fs[s], px: lv[s]?.current ?? q[s]?.close }))
    .filter(r => r.q);
  const verdictLabel = { undervalued: "below fair", overvalued: "above fair", fair: "near fair" };
  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Your watchlist</h2><div class="ln"></div><span class="pill">${rows.length}</span></div>
  <p class="sub" style="margin-bottom:14px">The stocks you follow, with the four things that matter at a glance. Star toggles on any stock page. Research, not advice.</p>
  ${rows.length ? `<div class="card"><table><thead><tr><th>Ticker</th><th class="r">Price</th><th class="r">Day</th><th class="r">Valuation</th><th>Health</th><th></th></tr></thead><tbody>${
    rows.map(r => `<tr class="clickable" onclick="location.hash='#/ticker/${r.s}'">
      <td><b>${r.s}</b> <span class="sub">${esc((r.name || "").slice(0, 20))}</span></td>
      <td class="r num">${fmt(r.px)}</td>
      <td class="r num ${cls(r.q.ret_1d)}">${sgn(r.q.ret_1d)}%</td>
      <td class="r">${r.fv ? `<span class="pill ${r.fv.verdict === "undervalued" ? "ok" : r.fv.verdict === "overvalued" ? "bad" : ""}">${verdictLabel[r.fv.verdict] || r.fv.verdict}</span>` : "—"}</td>
      <td>${r.fs ? `<span class="tag">${esc(r.fs.rating === "attractive" ? "stronger" : r.fs.rating === "caution" ? "weaker" : "mixed")}</span>` : "—"}</td>
      <td class="r">${starBtn(r.s)}</td></tr>`).join("")}</tbody></table></div>`
    : `<div class="card"><div class="empty">No stocks yet. Open any stock and tap the ★ to add it — try <a href="#/board">the Board</a> or search (top right).</div></div>`}`;
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
    await migrateGuestChart();   // a chart cast before signing up follows the user into their account
    applyDeskMode();
    // the initial route() already ran (before auth resolved), so pages that depend on the signed-in
    // user — Your Chart, Portfolio, Watchlist, Settings — rendered their signed-out state. Re-render
    // the current page now that `me` and the profile are known.
    if (typeof route === "function") route(true);
    if (myProfile && !myProfile.onboarded) startWizard(false);
  }
  sb.auth.onAuthStateChange(async (event, sess) => {
    me = sess?.user || null;
    renderAccountButton();
    if (event === "PASSWORD_RECOVERY") return openRecovery();
    if (event === "SIGNED_IN") {
      closeAuth();
      await loadProfile();
      await migrateGuestChart();   // the whole point of the funnel: never ask for birth details twice
      applyDeskMode();
      if (typeof route === "function") route(true);   // re-render the page you're on with your account
      if (myProfile && !myProfile.onboarded) startWizard(false);
    }
    if (event === "SIGNED_OUT") { myProfile = null; applyDeskMode(); if (typeof route === "function") route(true); }
  });
}
initAuth();
