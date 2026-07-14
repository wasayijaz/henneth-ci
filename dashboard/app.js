/* PSX Trade Desk SPA — hash router, 4 themes, canvas charts.
   Routes: #/board · #/ticker/SYM · #/dividends · #/news
   All data from ../state/*.json (DPS-sourced). No external deps. */

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
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
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const v = attempt < 2 ? await fetch(url()).then(r => r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status)))
        : await xhrJson(url()); // last attempt: bypass a fetch() an extension may have broken
      cache[p] = { t: Date.now(), v };
      return v;
    } catch { /* fall through to retry */ }
    if (attempt < 2) await new Promise(res => setTimeout(res, 300));
  }
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
  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Value screen — price vs model fair value</h2><div class="ln"></div><span class="pill">${rows.length} valued</span></div>
  <div class="disclaimer">Model estimates on public fundamentals for <b>research and education</b> — not price targets, not advice, not a signal to buy or sell. A price below model fair value is not a recommendation, and a low share price never means a company is cheap. Past performance does not guarantee future results.</div>
  <p class="sub" style="margin-bottom:16px">Each stock is valued four ways (peer P/E, earnings-power vs bond yield, Graham, dividend discount); the median is its <b>model fair value</b>. Market median P/E ${fv?.inputs?.market_median_pe ?? "—"}, bond yield ${fv?.inputs?.bond_yield_pct ?? "—"}%. Click any row to expand the four-model working.</p>
  <div class="seg"><h2 style="color:var(--up)">Priced below model fair value</h2><div class="ln"></div><span class="pill ok">${under.length}</span></div>
  <div class="card">${under.length ? tbl(under, true) : '<div class="empty">none below model fair value right now</div>'}</div>
  <div class="seg"><h2 style="color:var(--dn)">Priced above model fair value</h2><div class="ln"></div><span class="pill bad">${over.length}</span></div>
  <div class="card">${over.length ? tbl(over, false) : '<div class="empty">none above model fair value right now</div>'}</div>`;
}

async function pageMacro() {
  const [gl, macro, geo] = await Promise.all([j("global.json"), j("macro.json"), j("georisk.json")]);
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

  $("view").innerHTML = `
    <div class="seg" style="margin-top:4px"><h2>What moves PSX</h2><div class="ln"></div></div>
    <p class="sub" style="margin-bottom:14px">Global markets refreshed every cycle (Yahoo Finance). Pakistan-domestic numbers verified by the macro-agent from primary sources. Hover any read-through for why it matters.</p>
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

  $("view").innerHTML = `
  ${globalStrip(gl)}
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
  const [bt, smap] = await Promise.all([j("backtests.json"), j("strategy_map.json")]);
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

  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Strategy library</h2><div class="ln"></div><span class="pill">${rows.length} strategies</span></div>
  <p class="sub" style="margin-bottom:16px">Every strategy is a transparent rule set backtested on each stock's own ~19-year history. A strategy is only used on a stock where it cleared the bar (win rate ≥55%, positive expectancy after costs, and still profitable out-of-sample). Click any stock chip to see it in context.</p>
  ${Object.entries(byCat).map(([cat, list]) => `<div class="card"><h2 style="font-size:13px;text-transform:capitalize">${esc(cat.replace("_", " "))}</h2>
    <table><thead><tr><th>Strategy</th><th class="r">Proven on</th><th class="r">Avg net/trade</th><th>Stocks it works on</th></tr></thead><tbody>${
    list.map(r => `<tr><td><b>${esc(r.name)}</b></td><td class="r num">${r.proven}${r.tested ? "/" + r.tested : ""}</td>
      <td class="r num ${r.avgNet > 0 ? "up" : ""}">${r.avgNet != null ? sgn(r.avgNet.toFixed(2)) + "%" : "—"}</td>
      <td>${r.provenOn.slice(0, 10).map(s => `<a class="tag clickable" onclick="event.stopPropagation();location.hash='#/ticker/${s}'">${s}</a>`).join(" ") || '<span class="sub">none yet</span>'}</td></tr>`).join("")}</tbody></table></div>`).join("")}`;
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
    <p style="margin:8px 0 10px;line-height:1.55">${esc(hv.summary || "")}</p>
    <div class="room-facts">
      <div><span>Dissent (strongest counter)</span><b>${esc(hv.dissent || "—")}</b></div>
      <div><span>TA vs FA</span><b>${esc((hv.ta_fa_alignment || "—").replace(/_/g, " "))}</b></div>
      <div><span>Broker stance</span><b>${esc(hv.broker_stance || "n/a")}</b></div>
      <div><span>Watch next</span><b>${esc(hv.watch_next || "—")}</b></div>
    </div>
  </div>

  <details class="room-transcript">
    <summary>Full debate — the technical desk, the fundamental desk, and the bull vs the bear <span class="exhint">click to expand</span></summary>
  <div class="two-col" style="margin-top:12px">
    ${memo("MC", "Meher", "The Chartist · TA", ta.technical_stance, stanceClass(ta.technical_stance), `<p class="sub" style="color:var(--ink2);line-height:1.5">${esc(ta.read || "")}</p>${ta.levels ? `<div class="sub" style="margin-top:6px">structure <b>${esc(ta.structure || "—")}</b> · momentum <b>${esc(ta.momentum || "—")}</b> · support <b>${fmt(ta.levels.support)}</b> · resistance <b>${fmt(ta.levels.resistance)}</b></div>` : ""}`)}
    ${memo("DO", "Dr. Omar", "The Fundamentalist · FA", fa.fundamental_stance, stanceClass(fa.fundamental_stance), `<p class="sub" style="color:var(--ink2);line-height:1.5">${esc(fa.read || "")}</p><div class="sub" style="margin-top:6px">valuation <b>${esc((fa.valuation_stance || "—").replace(/_/g, " "))}</b> · dividend: ${esc(fa.dividend_safety || "—")}</div>`)}
  </div>

  <div class="two-col">
    <div class="card room-memo bull"><div class="memo-top">${persona("ZB", "Zoya", "The Bull")}</div>
      <p style="line-height:1.5">${esc(bull.thesis || "")}</p><ul class="room-ul">${li(bull.pillars)}</ul>
      ${bull.what_would_break_it ? `<div class="sub" style="margin-top:6px"><b>Breaks if:</b> ${esc(bull.what_would_break_it)}</div>` : ""}</div>
    <div class="card room-memo bear"><div class="memo-top">${persona("KB", "Khurram", "The Bear")}</div>
      <p style="line-height:1.5">${esc(bear.thesis || "")}</p><ul class="room-ul">${li(bear.pillars)}</ul>
      ${bear.attack_on_bull ? `<div class="sub" style="margin-top:6px"><b>On the bull:</b> ${esc(bear.attack_on_bull)}</div>` : ""}</div>
  </div>

  ${calls.length ? `<div class="card"><h2 style="font-size:12px">Dated calls on the record</h2><div class="sub">each is scored against what actually happens — this is how the desk (and, later, the brokers) are held accountable.</div>
    <table><thead><tr><th>Analyst</th><th>Call</th><th class="r">By</th><th class="r">Status</th></tr></thead><tbody>${
    calls.map(c => `<tr><td><b>${esc(c.source)}</b></td><td>${esc(c.claim?.text || "")}</td><td class="r num">${esc(c.resolve_by)}</td><td class="r"><span class="pill ${c.status === "hit" ? "ok" : c.status === "miss" ? "bad" : ""}">${esc(c.status)}</span></td></tr>`).join("")}</tbody></table></div>` : ""}
  </details>`;
}

async function pageTicker(sym, _retry = 0) {
  sym = sym.toUpperCase();
  const [quant, bt, smap, uni, live, news, divs, fund, fscore, cal, hist, deep, intra, fvAll, roomsAll, claimsAll, researchIdx, explainAll] = await Promise.all([
    j("quant.json"), j("backtests.json"), j("strategy_map.json"), j("universe.json"),
    j("live.json"), j("newslog.json"), j("dividends.json"), j("fundamentals.json"),
    j("fundamental_scores.json"), j("earnings_calendar.json"), j("history/" + sym + ".json", 300000),
    j("history_deep/" + sym + ".json", 600000), j("intraday/" + sym + ".json", 20000), j("fairvalue.json"), j("rooms.json"), j("claims.json"), j("research_index.json"), j("explainer.json")]);
  const q = quant?.tickers?.[sym], u = uni?.symbols?.[sym], lv = live?.tickers?.[sym];
  const proven = (smap?.tickers?.[sym]) || [];
  const fsc = fscore?.tickers?.[sym];
  const fv = fvAll?.tickers?.[sym];
  const room = roomsAll?.[sym];
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
  const summaryStrip = `<div class="sumstrip">
    ${sTile("Fair value vs price", fv ? `Rs ${fmt(fv.composite_fair)}` : "—", fv ? `price Rs ${fmt(fv.price)} · ${sgn(fv.mispricing_pct)}%` : "model n/a", fv ? (fv.verdict === "undervalued" ? "up" : fv.verdict === "overvalued" ? "dn" : "") : "")}
    ${sTile("Scorecard", fsc ? ({ attractive: "Stronger", caution: "Weaker", neutral: "Mixed" }[fsc.rating] || fsc.rating) : "—", fsc ? "business quality" : "not scored", fsc ? (fsc.rating === "attractive" ? "up" : fsc.rating === "caution" ? "dn" : "") : "")}
    ${sTile("Risk grade", rg, vr != null ? `volatility ${vr.toFixed(0)}/100` : "liquidity " + liq, rgk === "hi" ? "dn" : rgk === "lo" ? "up" : "")}
    ${sTile("Next event", nextEarn ? "Results" : "—", nextEarn ? `${nextEarn.date}${daysToEarn != null ? ` · ${daysToEarn}d` : ""}` : "none scheduled", "")}
    ${sTile("House view", hvRoom ? `${esc(hvRoom.conviction || "—")} conviction` : "In queue", hvRoom ? "AI desk — see Room below" : "not yet covered", "")}
  </div>`;

  // ---- private per-ticker note (only you can see it) ----
  const noteCard = me
    ? `<div class="seg"><h2>Your private note</h2><div class="ln"></div><span class="pill">only you can see this</span></div>
    <div class="card"><textarea id="tknote" class="tknote" placeholder="Private notes on ${esc(sym)} — your own thesis, price levels you care about, reminders. Saved to your account, visible only to you.">${esc(noteFor(sym))}</textarea>
      <div class="tknote-bar"><button class="note-save" onclick="saveTickerNote('${esc(sym)}')">Save note</button><span id="tknote-status" class="sub"></span></div></div>`
    : `<div class="seg"><h2>Your private note</h2><div class="ln"></div></div>
    <div class="card"><div class="empty">Sign in to keep a private note on ${esc(sym)} — your own thesis and reminders, saved to your account and visible only to you.<br><br><button class="auth-go" style="max-width:220px" onclick="openAuth('signup')">Create a free account</button></div></div>`;

  $("view").innerHTML = `
  <a class="crumb" href="#/board">← board</a>
  <div class="disclaimer">Educational and informational research only — <b>not personalized investment advice</b>. Past performance does not guarantee future results. Investing in PSX carries risk, including the possible loss of capital. The desk never places orders; any decision and its outcome are your own.</div>
  ${summaryStrip}
  ${glance}
  <div class="card">
    <div class="tk-head">
      <span class="sym">${sym}</span>
      <span class="px num">${fmt(px)}</span>
      <span class="num ${cls(q.ret_1d)}" style="font-size:16px;font-weight:700">${sgn(q.ret_1d)}%</span>
      <span class="tag">${esc(u?.name || "")}</span>${lv?.sector && isNaN(lv.sector) ? `<span class="tag">${esc(lv.sector)}</span>` : ""}
      <span class="tag">${(u?.in || []).join(" · ")}</span>
      <a class="tag" target="_blank" href="https://www.tradingview.com/chart/?symbol=PSX%3A${sym}">TradingView ↗ (15m delayed)</a>
      ${typeof starBtn === "function" ? starBtn(sym) : ""}
    </div>
    <div class="prov">Prices in <b>Rs (PKR)</b> · ${priceSrc} · quant as of ${q.date} close · fundamentals ${f.fetched || "—"} · long-history chart is split/bonus-adjusted (Yahoo); DPS close is unadjusted.${liq === "low" ? ' · <b class="dn">low liquidity</b>' : ""}${lossmaking ? ' · <b class="dn">earnings negative</b>' : ""}</div>
    <div class="ranges" id="ranges">
      ${hasIntra ? '<button data-d="intra">1D</button>' : ""}<button data-d="63">3M</button><button data-d="126">6M</button><button class="on" data-d="252">1Y</button><button data-d="1260">5Y</button><button data-d="99999">Max${histYears >= 5 ? " (" + histYears + "y)" : ""}</button>
    </div>
    <div class="chartwrap"><canvas id="chart" style="height:340px"></canvas><div class="tooltip" id="tt"></div></div>
  </div>

  ${noteCard}

  <div class="seg"><h2>Strategies proven on ${sym}</h2><div class="ln"></div><span class="pill ok">${proven.length} proven</span></div>
  <div class="card"><div class="sub">Of the desk's ${bt?.n_strategies ?? 52} tested strategies, these cleared the bar on ${sym}'s own ~19-year history — win rate ≥55%, positive expectancy after costs, AND still profitable in the unseen last third (out-of-sample). This is what actually worked here, not theory.</div>
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

  ${fsc ? `<div class="seg"><h2>Business scorecard</h2><div class="ln"></div><span class="pill ${fsc.rating === "attractive" ? "ok" : fsc.rating === "caution" ? "bad" : ""}">${esc({ attractive: "stronger scorecard", caution: "weaker scorecard", neutral: "mixed scorecard" }[fsc.rating] || fsc.rating)}</span></div>
  <div class="card"><div class="sub" style="font-size:13px;color:var(--ink2);margin-bottom:14px">${esc(fsc.overall)}</div>
    <div class="two-col" style="gap:12px">${fsc.cards.map(c => `<div style="border:1px solid var(--line);border-radius:0;padding:12px 14px">
      <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px"><b>${esc(c[0])}</b><span class="tag">${esc(c[1])}</span></div>
      <div class="sub" style="color:var(--ink2)">${esc(c[2])}</div></div>`).join("")}</div></div>` : ""}

  ${renderRoom(room, sym)}

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

  const divHtml = divUp.length ? divUp.map(d => `
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

  <div class="seg"><h2>Past payouts</h2><div class="ln"></div></div>
  <div class="card"><div class="sub">last ${past.length} closures · cash dividends (D) as % of Rs 10 face value</div>
    <table><thead><tr><th>Ticker</th><th>Payout</th><th class="r">Rs/sh</th><th class="r">Yield@now</th><th class="r">Announced</th><th class="r">Closure start</th></tr></thead><tbody>${
    past.map(d => `<tr class="clickable" onclick="location.hash='#/ticker/${d.symbol}'"><td><b>${d.symbol}</b></td><td>${esc(d.announcement)}</td>
      <td class="r num">${d.dividend_rs ?? "—"}</td><td class="r num">${d.yield_pct_at_close ? d.yield_pct_at_close + "%" : "—"}</td>
      <td class="r num">${esc((d.announced || "").split(" ").slice(0, 3).join(" "))}</td><td class="r num">${d.bc_start}</td></tr>`).join("")}</tbody></table></div>`;
}

async function pageCalendar() {
  const cal = await j("earnings_calendar.json");
  const earnings = (cal?.events || []).filter(e => e.type === "results");
  const byMonth = {};
  earnings.forEach(e => { const m = e.date.slice(0, 7); (byMonth[m] = byMonth[m] || []).push(e); });

  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Earnings calendar</h2><div class="ln"></div></div>
  <p class="sub" style="margin-bottom:16px">${earnings.length} upcoming results dates across the universe · <span class="pill ok">verified</span> = confirmed against a company/PSX board-meeting notice · <span class="tag">estimate</span> = scraped, pending verification. The desk won't open a swing into an unconfirmed results date inside its hold window (earnings gaps blow through stops).</p>
  ${Object.keys(byMonth).sort().map(m => {
    const label = new Date(m + "-01").toLocaleDateString("en", { month: "long", year: "numeric" });
    return `<div class="card"><h2 style="font-size:13px">${label}</h2>
      <table><thead><tr><th>Date</th><th class="r">In</th><th>Ticker</th><th>Event</th><th class="r">Status</th></tr></thead><tbody>${
      byMonth[m].map(e => `<tr class="clickable" onclick="location.hash='#/ticker/${e.ticker}'">
        <td class="num">${e.date}</td><td class="r">${cdBadge(e.date)}</td><td><b>${e.ticker}</b></td>
        <td class="sub">${esc(e.note || "results")}</td>
        <td class="r">${e.confirmed ? '<span class="pill ok">verified</span>' : '<span class="tag">estimate</span>'}</td></tr>`).join("")}</tbody></table></div>`;
  }).join("") || '<div class="card"><div class="empty">Calendar builds on the first full cycle.</div></div>'}`;
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
  const brokers = docs.filter(d => d.source_type === "broker");
  const filings = docs.filter(d => d.source_type !== "broker");
  const dtLabel = { corporate_briefing: "corporate briefing", agm: "AGM", results: "results", board_meeting: "board meeting", filing: "filing", morning_note: "morning note", company_note: "broker note" };
  const docRow = d => `<div class="rdoc">
    <div class="rdoc-top"><span class="tag">${esc(dtLabel[d.doc_type] || d.doc_type)}</span>
      <span class="rdoc-src">${esc(d.source)}${d.digest_level === "headline" ? ' · <span class="sub">headline only</span>' : ""}</span>
      <span class="t">${esc(d.date || "")}</span>
      ${(d.tickers || []).slice(0, 4).map(t => `<a href="#/ticker/${esc(t)}" class="tag clickable">${esc(t)}</a>`).join(" ")}</div>
    <div class="rdoc-digest">${esc(d.digest || "")}${d.url ? ` <a href="${esc(d.url)}" target="_blank" style="color:var(--accent)">source ↗</a>` : ""}</div>
    ${(d.claims || []).length ? `<div class="sub" style="margin-top:4px"><b>Claims (scored later):</b> ${d.claims.map(c => esc(c.claim?.text || "")).join(" · ")}</div>` : ""}
    ${d.omissions ? `<div class="sub" style="margin-top:4px"><b class="dn">What it glosses over:</b> ${esc(d.omissions)}</div>` : ""}</div>`;
  $("view").innerHTML = `
  <div class="seg" style="margin-top:4px"><h2>Research library</h2><div class="ln"></div><span class="pill">${docs.length} documents</span></div>
  <div class="disclaimer">Broker research and company filings are <b>evidence the desk cross-examines, never takes at face value</b>. Brokers miss things, carry sector bias, and are often wrong — every broker claim here is extracted, scored against what actually happens, and ranked on the <a href="#/leaderboard" style="color:inherit;text-decoration:underline">broker leaderboard</a>. Educational, not advice.</div>
  <div class="seg"><h2>Broker notes</h2><div class="ln"></div><span class="pill">${brokers.length}</span></div>
  <div class="card">${brokers.length ? brokers.map(docRow).join("") : '<div class="empty">No broker notes digested yet. Add public sources in config/broker_sources.json; the desk digests each once and scores its calls. Until then, the desk forms its own view without leaning on brokers.</div>'}</div>
  <div class="seg"><h2>Company filings & briefings</h2><div class="ln"></div><span class="pill">${filings.length}</span></div>
  <div class="card">${filings.length ? filings.map(docRow).join("") : '<div class="empty">No filings tagged yet — the news sentinel surfaces results, board-meeting and corporate-briefing notices here as companies file them.</div>'}</div>`;
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

/* ---------- router ---------- */
const PAGES = { today: pageToday, board: pageBoard, watchlist: pageWatchlist, strategies: pageStrategies, value: pageValue, macro: pageMacro, dividends: pageDividends, calendar: pageCalendar, research: pageResearch, leaderboard: pageLeaderboard, news: pageNews, legal: pageLegal };
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
route(false);
setInterval(() => { Object.keys(cache).forEach(k => delete cache[k]); route(true); }, 30000);

/* ---------- ticker search ---------- */
let searchIndex = null;
async function loadSearchIndex() {
  if (searchIndex) return searchIndex;
  const uni = await j("universe.json");
  searchIndex = Object.entries(uni?.symbols || {}).map(([s, v]) => ({ s, name: (v.name || "").toLowerCase() }));
  return searchIndex;
}
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
    holder.innerHTML = `<button class="acct-btn" id="acctBtn" title="${me.email}">${initial}</button>
      <div class="acct-menu" id="acctMenu" hidden>
        <div class="acct-email">${me.email}</div>
        <button id="acctTour">Replay the tour</button>
        <button id="acctOut">Sign out</button>
      </div>`;
    const menu = document.getElementById("acctMenu");
    document.getElementById("acctBtn").onclick = (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; };
    document.getElementById("acctOut").onclick = async () => { await sb.auth.signOut(); location.reload(); };
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

/* ---------- watchlist (per-user, persisted to profiles.watchlist) ---------- */
function watchlist() { return (myProfile && myProfile.watchlist) || []; }
function isWatched(sym) { return watchlist().includes(sym); }

/* ---------- private per-ticker notes (persisted to profiles.notes, RLS-scoped) ---------- */
function noteFor(sym) { return ((myProfile && myProfile.notes) || {})[sym] || ""; }
async function saveTickerNote(sym) {
  const ta = document.getElementById("tknote"); if (!ta) return;
  const st = document.getElementById("tknote-status");
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
});

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
