(function () {
  const content = document.getElementById("content");
  const healthPill = document.getElementById("healthPill");
  const authNote = document.getElementById("authNote");
  const tickerInput = document.getElementById("tickerInput");
  const loadBtn = document.getElementById("loadBtn");
  const openDesk = document.getElementById("openDesk");
  const schemeBtn = document.getElementById("schemeBtn");
  const tabs = document.querySelectorAll(".tab");

  let health = null;
  let currentSym = null;
  let activeTab = "read";
  let myProfile = null;
  let readRequest = 0;
  let thinkingTimer = null;
  let askHistory = [];
  let askBusy = false;

  // ---- scheme toggle (persisted, mirrors palette.css behaviour) ----
  chrome.storage.local.get(["scheme"], ({ scheme }) => {
    if (scheme) document.documentElement.dataset.scheme = scheme;
  });
  schemeBtn.addEventListener("click", () => {
    const cur = document.documentElement.dataset.scheme ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.scheme = next;
    chrome.storage.local.set({ scheme: next });
  });

  // ---- tabs ----
  tabs.forEach((t) => t.addEventListener("click", () => {
    if (activeTab === "ask" && t.dataset.tab !== "ask") unmountAskLoaders();
    activeTab = t.dataset.tab;
    tabs.forEach((x) => x.classList.toggle("on", x === t));
    render();
  }));

  // ---- ticker wiring ----
  function readTicker() {
    const next = tickerInput.value.trim().toUpperCase();
    if (!next) {
      tickerInput.classList.remove("shake");
      void tickerInput.offsetWidth;
      tickerInput.classList.add("shake");
      tickerInput.focus();
      return;
    }
    loadBtn.classList.remove("reading");
    void loadBtn.offsetWidth;
    loadBtn.classList.add("reading");
    setTimeout(() => loadBtn.classList.remove("reading"), 500);
    showThinkingOverlay();
    currentSym = next;
    render();
  }
  loadBtn.addEventListener("click", readTicker);
  tickerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") readTicker();
  });
  chrome.runtime.sendMessage({ type: "GET_LAST_TICKER" }, ({ ticker }) => {
    if (ticker) { tickerInput.value = ticker; currentSym = ticker; render(); }
  });
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg && msg.type === "TICKER_FOUND" && msg.ticker) {
      if (msg.ticker === currentSym) return; // no symbol change — do not re-render
      tickerInput.value = msg.ticker;
      currentSym = msg.ticker;
      if (activeTab === "read" || activeTab === "ask") render();
    }
  });

  function el(html) {
    const d = document.createElement("div");
    d.innerHTML = html;
    return d.firstElementChild;
  }
  function stat(label, value, cls) {
    return '<div class="stat"><b class="num ' + (cls || "") + '">' + value + "</b><span>" + label + "</span></div>";
  }
  // horizontal meter: pct 0-100, cls good/mid/bad
  function meter(label, pct, cls, right) {
    const p = Math.max(0, Math.min(100, pct));
    return '<div class="meter ' + (cls || "") + '"><div class="lbl"><span>' + label + '</span><span>' + (right || "") +
      '</span></div><div class="track"><div class="fill" style="width:' + p.toFixed(1) + '%"></div></div></div>';
  }

  function clampPct(n) {
    return Math.max(0, Math.min(100, Number(n) || 0));
  }
  function showThinkingOverlay() {
    if (thinkingTimer) clearTimeout(thinkingTimer);
    const existing = document.getElementById("thinkingOverlay");
    if (existing) {
      if (window.HennethInlineLoaderBundle && typeof window.HennethInlineLoaderBundle.unmount === "function") {
        window.HennethInlineLoaderBundle.unmount();
      }
      existing.remove();
    }
    const duration = 1000 + Math.floor(Math.random() * 3000);
    const overlay = el(
      '<div id="thinkingOverlay" class="thinking-overlay" aria-live="polite" aria-label="Thinking">' +
        '<div class="thinking-center">' +
          '<div id="thinkingLoaderMount" class="thinking-loader-mount" aria-hidden="true"></div>' +
          '<div class="thinking-word">thinking<span class="thinking-dots">...</span></div>' +
        '</div>' +
      '</div>'
    );
    document.body.appendChild(overlay);
    if (window.HennethInlineLoaderBundle && typeof window.HennethInlineLoaderBundle.mount === "function") {
      window.HennethInlineLoaderBundle.mount(document.getElementById("thinkingLoaderMount"));
    }
    requestAnimationFrame(() => overlay.classList.add("show"));
    thinkingTimer = setTimeout(() => {
      if (window.HennethInlineLoaderBundle && typeof window.HennethInlineLoaderBundle.unmount === "function") {
        window.HennethInlineLoaderBundle.unmount();
      }
      overlay.classList.remove("show");
      setTimeout(() => { if (overlay.isConnected) overlay.remove(); }, 220);
      thinkingTimer = null;
    }, duration);
  }
  function taGauge(label, value, state, pct, cls, axis) {
    return '<div class="ta-block"><div class="ta-head"><span>' + label + '</span><span class="ta-value ' + (cls || "") + '">' +
      value + (state ? ' <small>' + state + '</small>' : "") + '</span></div>' +
      '<div class="ta-track"><i class="ta-fill ' + (cls || "") + '" style="width:' + clampPct(pct).toFixed(1) +
      '%"></i><b class="ta-marker" style="left:' + clampPct(pct).toFixed(1) + '%"></b></div>' +
      (axis ? '<div class="ta-axis">' + axis + '</div>' : '') + '</div>';
  }
  function taZero(label, value, maxAbs, cls) {
    const n = Number(value) || 0;
    const half = clampPct(Math.abs(n) / Math.max(1, maxAbs) * 50);
    const left = n >= 0 ? 50 : 50 - half;
    return '<div class="ta-block ta-zero"><div class="ta-head"><span>' + label + '</span><span class="ta-value ' +
      (cls || "") + '">' + fmtPct(n) + '</span></div><div class="ta-zero-track">' +
      '<i class="ta-zero-fill ' + (n >= 0 ? "pos" : "neg") + '" style="left:' + left.toFixed(1) +
      '%;width:' + half.toFixed(1) + '%"></i><b class="ta-zero-line"></b></div></div>';
  }

  // Lightweight MV3 equivalent of the requested TextLoader variants. The
  // extension is plain HTML/CSS, so no React runtime or remote package is
  // needed for the same focus/redact/terminal loading hierarchy.
  function loaderText(text, variant, tag) {
    return '<' + (tag || "span") + ' class="loader-text ' + variant + '">' + esc(text) + '</' + (tag || "span") + '>';
  }
  function renderDeskLoading(sym) {
    content.innerHTML =
      '<div class="desk-loading" aria-live="polite">' +
      '<div class="load-primary">' + loaderText("HENNETH DESK / " + sym, "focus", "div") + '</div>' +
      '<div class="load-subtitle">' + loaderText("CALCULATING THE READ", "focus", "div") + '</div>' +
      '<div class="load-grid">' +
      '<div class="load-block secondary">' + loaderText("PRICE & MOMENTUM", "terminal", "div") +
        '<div class="load-visual redact"></div><div class="load-visual short redact"></div></div>' +
      '<div class="load-block secondary">' + loaderText("TECHNICAL PROFILE", "terminal", "div") +
        '<div class="load-visual redact"></div><div class="load-visual short redact"></div></div>' +
      '<div class="load-block secondary">' + loaderText("VALUATION & LIQUIDITY", "terminal", "div") +
        '<div class="load-visual redact"></div><div class="load-visual short redact"></div></div>' +
      '<div class="load-block secondary">' + loaderText("SETUP EVIDENCE", "terminal", "div") +
        '<div class="load-visual redact"></div><div class="load-visual short redact"></div></div>' +
      '</div></div>';
  }

  function render() {
    if (activeTab === "notes") renderNotes();
    else if (activeTab === "ask") renderAsk();
    else if (currentSym) renderRead(currentSym);
    else content.innerHTML = '<div class="empty">Open a PSX ticker on TradingView, DPS or a PSX news page,<br>or search a symbol above.</div>';
  }

  function unmountAskLoaders() {
    if (!window.HennethInlineLoaderBundle) return;
    content.querySelectorAll(".ask-answer-mount, #askBusyMount").forEach((node) => {
      if (typeof window.HennethInlineLoaderBundle.unmountText === "function") {
        window.HennethInlineLoaderBundle.unmountText(node);
      }
    });
  }

  function mountAskAnswers() {
    if (!window.HennethInlineLoaderBundle || typeof window.HennethInlineLoaderBundle.mountText !== "function") return;
    content.querySelectorAll(".ask-answer-mount").forEach((node) => {
      window.HennethInlineLoaderBundle.mountText(node, node.dataset.answer || "");
    });
    const busy = content.querySelector("#askBusyMount");
    if (busy) window.HennethInlineLoaderBundle.mountText(busy, "reading the desk...");
  }

  function renderAsk() {
    unmountAskLoaders();
    const tickerLabel = currentSym ? "Context: " + esc(currentSym) : "Ask across the desk";
    const thread = askHistory.map((m) => {
      if (m.role === "user") {
        return '<div class="ask-turn user"><div class="ask-role">you</div><div class="ask-user-text">' +
          esc(m.display || m.content) + "</div></div>";
      }
      if (m.error) {
        return '<div class="ask-turn assistant error"><div class="ask-role">desk</div><div class="ask-error">' +
          esc(m.content) + "</div></div>";
      }
      return '<div class="ask-turn assistant"><div class="ask-role">desk</div><div class="ask-answer-mount" data-answer="' +
        esc(m.content) + '"></div></div>';
    }).join("");
    content.innerHTML = '<div class="card ask-card"><div class="ask-head"><div><h3>Ask the desk</h3>' +
      '<div class="ask-context">' + tickerLabel + '</div></div><span class="pill ok">GROQ · GROUNDED</span></div>' +
      '<div class="ask-thread">' + (thread || '<div class="ask-empty">Ask about a ticker, a sector, valuation, momentum, or today\'s market read.</div>') +
      (askBusy ? '<div class="ask-turn assistant"><div class="ask-role">desk</div><div id="askBusyMount"></div></div>' : "") +
      '</div><div class="ask-compose"><textarea id="askInput" rows="2" placeholder="' +
      (currentSym ? "Ask about " + esc(currentSym) + "…" : "Ask the desk a research question…") +
      '" aria-label="Ask the desk"></textarea><button id="askSend" class="key ask-send">' +
      (askBusy ? "Reading…" : "Ask the desk ↗") + '</button></div>' +
      '<div class="ask-foot">Answers use the desk\'s own data. Unknown figures stay unknown. Research and education, never advice.</div></div>';
    mountAskAnswers();
    const input = document.getElementById("askInput");
    const send = document.getElementById("askSend");
    if (input) {
      input.focus();
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          askSend();
        }
      });
    }
    if (send) send.addEventListener("click", askSend);
    const threadEl = content.querySelector(".ask-thread");
    if (threadEl) threadEl.scrollTop = threadEl.scrollHeight;
  }

  async function askSend() {
    if (askBusy) return;
    const input = document.getElementById("askInput");
    const text = input && input.value.trim();
    if (!text) { if (input) input.focus(); return; }
    const prior = askHistory.slice(-4).map((m) => ({ role: m.role, content: m.content }));
    askHistory.push({ role: "user", content: currentSym ? currentSym + ": " + text : text, display: text });
    askBusy = true;
    renderAsk();
    try {
      const body = await askDesk(currentSym ? currentSym + ": " + text : text, prior);
      askHistory.push({ role: "assistant", content: body.answer || "No answer came back." });
    } catch (e) {
      askHistory.push({
        role: "assistant",
        content: e.message === "AUTH"
          ? "Sign in at desk.henneth.app to ask the desk."
          : (e.message || "The desk could not answer right now."),
        error: true,
      });
    } finally {
      askBusy = false;
      askHistory = askHistory.slice(-12);
      renderAsk();
    }
  }

  async function renderRead(sym) {
    const request = ++readRequest;
    openDesk.href = "https://desk.henneth.app/#/ticker/" + encodeURIComponent(sym);
    renderDeskLoading(sym);

    const [jobs] = await Promise.all([
      Promise.allSettled([
        deskFetch("/state/health.json"), deskFetch("/state/universe.json"),
        deskFetch("/state/quant.json"), deskFetch("/state/live.json"),
        deskFetch("/state/predictability.json"), deskFetch("/state/fairvalue.json"),
        deskFetch("/state/liquidity.json"), deskFetch("/state/dividends.json"),
        deskFetch("/state/earnings_calendar.json"), deskFetch("/state/signals.json"),
        deskFetch("/state/strategy_map.json"), deskFetch("/state/desk_rules.json"),
      ]),
      new Promise((resolve) => setTimeout(resolve, 680)),
    ]);
    if (request !== readRequest || currentSym !== sym || activeTab !== "read") return;
    const v = jobs.map((j) => (j.status === "fulfilled" ? j.value : null));
    const authFail = jobs.some((j) => j.status === "rejected" && j.reason && j.reason.message === "AUTH");

    if (authFail) {
      authNote.textContent = "Not signed in — open desk.henneth.app and log in, then reopen this panel.";
      authNote.style.color = "var(--dn)";
    } else {
      const { desk_token } = await chrome.storage.local.get("desk_token");
      authNote.textContent = desk_token ? "" : "Sign in at desk.henneth.app to load desk data.";
    }

    health = v[0];
    renderHealth();
    drawRead(sym, v);

    // Seed the content-script universe cache so detector.js can validate
    // symbols it reads from TradingView legends and PSX news pages.
    if (v[1] && v[1].symbols) {
      chrome.storage.local.set({ henneth_universe: { at: Date.now(), data: v[1].symbols } });
    }
  }

  function renderHealth() {
    if (!health) { healthPill.textContent = "HEALTH —"; healthPill.className = "pill"; return; }
    const ok = health.status === "ok";
    healthPill.textContent = "HEALTH " + health.status.toUpperCase();
    healthPill.className = "pill " + (ok ? "ok" : "warn");
    healthPill.title = (health.problems || []).join("; ") || "data layer healthy";
  }

  function drawRead(sym, v) {
    const uni = v[1], quant = v[2], live = v[3], pred = v[4], fv = v[5],
      liq = v[6], div = v[7], cal = v[8], sig = v[9], smap = v[10], rules = v[11];
    content.innerHTML = "";

    const meta = uni && uni.symbols ? uni.symbols[sym] : null;
    if (!meta) {
      content.appendChild(el('<div class="card"><h3>' + esc(sym) + '</h3>' +
        '<div class="note">Not in the desk universe — no coverage for this symbol.</div></div>'));
      return;
    }

    const q = quant && quant.tickers ? quant.tickers[sym] : null;
    const lq = live && live.tickers ? live.tickers[sym] : null;
    const price = (lq && lq.current) || (q && q.close) || null;
    const p = pred && pred.tickers ? pred.tickers[sym] : null;
    const f = fv && fv.tickers ? fv.tickers[sym] : null;
    const L = liq && liq.tickers ? liq.tickers[sym] : null;
    const strats = smap && smap.tickers ? smap.tickers[sym] || [] : [];
    const healthOk = health && health.status === "ok";
    const active = sig && sig.active ? sig.active.filter((s) => s.ticker === sym) : [];

    // ---- hero ----
    let hero = '<div class="card hero"><div class="row1"><span class="sym">' + esc(sym) + "</span>" +
      (active.length ? '<span class="pill ' + (healthOk ? "ok" : "warn") + '">SETUP ' + (healthOk ? "LIVE" : "DEGRADED") + "</span>" : "") +
      '<span class="px num">' + (price != null ? fmtNum(price) : "—") + "</span>" +
      (q ? '<span class="chg num ' + (q.ret_1d >= 0 ? "pos" : "neg") + '">' + fmtPct(q.ret_1d) + " 1d</span>" : "") +
      "</div>" +
      '<div class="name">' + esc(meta.name || "") + "</div>" +
      '<div class="idx">' + esc((meta.in || []).join(" · ")) + " · tier " + esc(meta.tier || "?") +
      (q ? " · EOD " + pktLabel(q.date) : "") + "</div>";
    if (q) {
      hero += '<div class="stats" style="margin-top:10px">' +
        stat("5d", fmtPct(q.ret_5d), q.ret_5d > 0 ? "pos" : q.ret_5d < 0 ? "neg" : "") +
        stat("20d", fmtPct(q.ret_20d), q.ret_20d > 0 ? "pos" : q.ret_20d < 0 ? "neg" : "") +
        stat("off 20d high", fmtNum(q.dist_to_20d_high_pct, 1) + "%") +
        stat("adtv", fmtCr(q.avg_daily_traded_value)) +
        "</div>";
    }
    hero += "</div>";
    content.appendChild(el(hero));

    // ---- verdict strip ----
    const trendTxt = q ? (q.above_sma20 && q.above_sma50 ? "uptrend" : !q.above_sma20 && !q.above_sma50 ? "downtrend" : "mixed") : "—";
    const trendCls = q ? (q.above_sma20 && q.above_sma50 ? "pos" : !q.above_sma20 && !q.above_sma50 ? "neg" : "") : "";
    let strip = '<div class="verdict">' +
      '<div><b class="' + trendCls + '">' + trendTxt + "</b><span>trend</span></div>" +
      '<div><b>' + (f ? esc(f.verdict || "—") : "—") + "</b><span>valuation</span></div>" +
      '<div><b class="grade-chip' + (L ? " g" + esc(L.grade || "") : "") + '">' + (L ? esc(L.grade || "—") : "—") + "</b><span>liquidity</span></div>" +
      '<div><b>' + (p ? fmtNum(p.score, 0) : "—") + "</b><span>predictability</span></div>" +
      "</div>";
    content.appendChild(el(strip));

    // ---- signals + health card ----
    if (active.length) {
      const s = active[0];
      const b = s.backtest || {};
      content.appendChild(el('<div class="card sig' + (healthOk ? "" : " degraded") + '"><h3>Active setup — ' +
        (healthOk ? "backtest-proven, unaudited" : "data degraded — no fresh signal weight") + "</h3>" +
        "<div><b>" + esc(s.template || s.strategy) + "</b> · " + esc(s.category || "") + " · hold " +
        esc(s.hold_sessions) + " sessions · confidence " + esc(s.confidence || "—") + "</div>" +
        '<div class="thesis">' + esc(s.thesis || "") + "</div>" +
        '<div class="meta">On its own history: hit ' + fmtPct((b.hit_rate || 0) * 100, 1) +
        " over " + (b.n || 0) + " trades · net " + fmtPct(b.net_expectancy_pct, 2) +
        "/trade · OOS hit " + fmtPct((b.oos_hit || 0) * 100, 0) + "</div>" +
        '<div class="meta">Research only — the Auditor has not verified this setup.</div></div>'));
    }

    // ---- meters card ----
    let meters = '<div class="card"><h3>Desk context</h3>';
    if (p) meters += meter("predictability — how reliably patterns resolve on " + esc(sym), p.score,
      p.score >= 60 ? "good" : p.score >= 50 ? "mid" : "bad", fmtNum(p.score, 1) + "/100");
    if (f && f.mispricing_pct != null) {
      const mp = Math.max(-50, Math.min(50, f.mispricing_pct));
      const w = Math.abs(mp) / 50 * 50; // half-width bar
      meters += '<div class="meter mid0"><div class="lbl"><span>mispricing vs desk fair value</span><span>' +
        fmtPct(f.mispricing_pct, 1) + '</span></div><div class="track">' +
        '<div class="fill ' + (mp >= 0 ? "" : "neg0") + '" style="width:' + w.toFixed(1) + '%; background:' +
        (mp >= 0 ? "var(--up)" : "var(--dn)") + '"></div>' +
        '<div class="tick" style="left:50%"></div></div></div>';
    }
    meters += "</div>";
    content.appendChild(el(meters));

    // ---- technical read ----
    // Keep this card as a quick visual scan: one primary oscillator meter,
    // one trend meter, and four compact context meters.
    if (q) {
      const px = price != null ? price : q.close;
      const rsiCls = q.rsi14 > 70 ? "bad" : q.rsi14 < 30 ? "mid" : "good";
      const rsiState = q.rsi14 > 70 ? "OVERBOUGHT" : q.rsi14 < 30 ? "OVERSOLD" : "NEUTRAL";
      const ma20Gap = q.sma20 ? (px - q.sma20) / q.sma20 * 100 : 0;
      const ma50Gap = q.sma50 ? (px - q.sma50) / q.sma50 * 100 : 0;
      const trendState = q.above_sma20 && q.above_sma50 ? "UPTREND" :
        !q.above_sma20 && !q.above_sma50 ? "DOWNTREND" : "MIXED";
      const trendCls = trendState === "UPTREND" ? "good" : trendState === "DOWNTREND" ? "bad" : "mid";
      const highDist = Math.max(0, Number(q.dist_to_20d_high_pct) || 0);
      const highProximity = clampPct(100 - highDist);
      const maxRet = Math.max(10, Math.abs(q.ret_5d || 0), Math.abs(q.ret_20d || 0));
      const volRank = q.volatility_rank == null ? null : Number(q.volatility_rank);
      const volCls = volRank == null ? "" : volRank >= 80 ? "bad" : volRank <= 20 ? "good" : "mid";
      const surge = q.vol_surge == null ? null : Number(q.vol_surge);
      const surgeCls = surge == null ? "" : surge >= 2 ? "good" : surge < 0.75 ? "bad" : "mid";
      const atrPct = q.atr14_proxy != null && px ? q.atr14_proxy / px * 100 : null;
      const atrCls = atrPct == null ? "" : atrPct >= 4 ? "bad" : atrPct <= 1 ? "good" : "mid";

      let ta = '<div class="card ta-card"><div class="ta-title"><h3>Technical read</h3>' +
        '<span class="ta-date">EOD ' + pktLabel(q.date) + '</span></div>';
      ta += taGauge("RSI 14", fmtNum(q.rsi14, 1), rsiState, q.rsi14, rsiCls,
        '<span>oversold 30</span><span>neutral 50</span><span>overbought 70</span>');

      ta += '<div class="ta-section trend-meter"><div class="ta-section-head"><span>Trend vs averages</span><b class="ta-state ' +
        trendCls + '">' + trendState + '</b></div><div class="ta-trend-track">' +
        '<i class="ta-trend-mid"></i><i class="ta-trend-fill ' + trendCls + '" style="width:' +
        (trendState === "UPTREND" ? "100" : trendState === "DOWNTREND" ? "0" : "50") + '%"></i></div>' +
        '<div class="ta-trend-labels"><span>MA20 ' + (q.above_sma20 ? "↑" : "↓") + ' ' + fmtPct(ma20Gap, 1) +
        '</span><span>MA50 ' + (q.above_sma50 ? "↑" : "↓") + ' ' + fmtPct(ma50Gap, 1) + '</span></div></div>';

      ta += '<div class="ta-compact-grid">';
      ta += '<div class="ta-section"><div class="ta-section-head"><span>20d high</span><b class="ta-value ' +
        (highDist <= 5 ? "good" : highDist >= 20 ? "bad" : "mid") + '">' + fmtNum(highDist, 1) + '% off</b></div>' +
        '<div class="ta-track"><i class="ta-fill ' + (highDist <= 5 ? "good" : highDist >= 20 ? "bad" : "mid") +
        '" style="width:' + highProximity.toFixed(1) + '%"></i></div><div class="ta-axis"><span>far</span><span>near high</span></div></div>';
      ta += '<div class="ta-section"><div class="ta-section-head"><span>Volatility</span><b class="ta-value ' +
        volCls + '">' + (volRank == null ? "—" : fmtNum(volRank, 0) + "/100") + '</b></div>' +
        '<div class="ta-track"><i class="ta-fill ' + volCls + '" style="width:' + clampPct(volRank) + '%"></i></div>' +
        '<div class="ta-axis"><span>quiet</span><span>high</span></div></div>';
      ta += '<div class="ta-section"><div class="ta-section-head"><span>Volume</span><b class="ta-value ' +
        surgeCls + '">' + (surge == null ? "—" : fmtNum(surge, 2) + "×") + '</b></div><div class="ta-track">' +
        '<i class="ta-fill ' + surgeCls + '" style="width:' + clampPct(surge == null ? 0 : surge / 3 * 100) + '%"></i><b class="ta-benchmark" style="left:33.3%"></b></div>' +
        '<div class="ta-axis"><span>0×</span><span>1× norm</span><span>3×</span></div></div>';
      ta += '<div class="ta-section"><div class="ta-section-head"><span>Daily move</span><b class="ta-value ' +
        atrCls + '">' + (atrPct == null ? "—" : "Rs " + fmtNum(q.atr14_proxy) + " · " + fmtNum(atrPct, 1) + "%") + '</b></div><div class="ta-track">' +
        '<i class="ta-fill ' + atrCls + '" style="width:' + clampPct(atrPct == null ? 0 : atrPct / 5 * 100) + '%"></i></div>' +
        '<div class="ta-axis"><span>0%</span><span>2.5%</span><span>5%+</span></div></div>';
      ta += '</div>';

      ta += '<div class="ta-section ta-returns"><div class="ta-section-head"><span>Recent returns</span><span class="ta-scale">scale ±' +
        fmtNum(maxRet, 1) + '%</span></div>' + taZero("5d", q.ret_5d, maxRet, q.ret_5d >= 0 ? "pos" : "neg") +
        taZero("20d", q.ret_20d, maxRet, q.ret_20d >= 0 ? "pos" : "neg") + '</div>';

      ta += '<div class="ta-footnote">Quant layer · EOD ' + pktLabel(q.date) + ' · descriptive only</div></div>';
      content.appendChild(el(ta));
    }

    // ---- liquidity card ----
    if (L) {
      content.appendChild(el('<div class="card"><h3>Liquidity reality check</h3>' +
        '<div class="stats">' +
        stat("adtv", fmtCr(L.adtv_pkr)) +
        stat("spread est.", L.spread_pct != null ? fmtNum(L.spread_pct, 2) + "%" : "—", L.spread_pct > 1.5 ? "neg" : "") +
        stat("days to exit*", fmtNum(L.days_to_liquidate_stress, 2), L.days_to_liquidate_stress > 5 ? "neg" : "") +
        stat("signal eligible", L.signal_eligible ? "yes" : "no", L.signal_eligible ? "pos" : "neg") +
        stat("zero-vol days", fmtNum(L.zero_volume_days_pct, 1) + "%", L.zero_volume_days_pct > 10 ? "neg" : "") +
        "</div>" +
        '<div class="note">*stressed variant (10% participation). Grade from 60-session spread/ADTV profile. ' +
        (L.research_eligible ? "" : "Below the desk research threshold — treat quotes with caution.") + "</div></div>"));
    }

    // ---- dividend / events card ----
    const dv = div && div.upcoming ? div.upcoming.filter((d) => d.symbol === sym) : [];
    const ev = cal && cal.events ? cal.events.filter((e) => e.ticker === sym) : [];
    if (dv.length || ev.length) {
      let h = '<div class="card"><h3>Dividends & dates</h3>';
      dv.slice(0, 2).forEach((d) => {
        h += '<div style="margin-bottom:6px"><b>' + esc(d.announcement || "dividend") + "</b> — Rs " +
          fmtNum(d.dividend_rs) + ' <span class="sub">(~' + fmtNum(d.yield_pct_at_close, 2) + "% at close)</span></div>" +
          '<div class="sub">Book closure ' + pktLabel(d.bc_start) + " → " + pktLabel(d.bc_end) +
          (d.buy_by ? " · buy by " + pktLabel(d.buy_by) : "") + "</div>";
      });
      ev.slice(0, 2).forEach((e) => {
        h += '<div style="margin-top:6px"><b>Results ' + pktLabel(e.date) + "</b>" +
          (e.confirmed ? "" : ' <span class="sub">(unconfirmed date)</span>') + "</div>";
      });
      h += "</div>";
      content.appendChild(el(h));
    }

    // ---- strategy evidence card ----
    if (strats.length) {
      const maxExp = Math.max.apply(null, strats.map((s) => s.net_expectancy_pct || 0));
      const top = strats.slice().sort((a, b2) => (b2.net_expectancy_pct || 0) - (a.net_expectancy_pct || 0)).slice(0, 6);
      let h = '<div class="card"><h3>Strategy evidence — ' + strats.length + " proven on " + esc(sym) + "</h3><table><tr>" +
        "<th>pattern</th><th class='r'>hit</th><th class='r'>net/trade</th><th class='r'>n</th></tr>";
      top.forEach((s, i) => {
        const bw = maxExp > 0 ? ((s.net_expectancy_pct || 0) / maxExp * 100).toFixed(0) : 0;
        h += "<tr" + (i === 0 ? ' class="pop"' : "") + "><td>" + esc(s.name) + '</td><td class="r num">' + fmtPct((s.hit_rate || 0) * 100, 0) +
          '</td><td class="r num">' + fmtPct(s.net_expectancy_pct, 1) + ' <span class="ebar"><i style="width:' + bw + '%"></i></span></td><td class="r num">' + (s.n || 0) + "</td></tr>";
      });
      h += "</table><div class='note'>Historical performance of rule patterns on this name — evidence, not a recommendation.</div></div>";
      content.appendChild(el(h));
    }

    // ---- position size calculator ----
    content.appendChild(buildCalc(rules));
  }

  function buildCalc(rules) {
    const R = (rules && rules.rules) || {};
    const riskPct = R.risk_per_trade_pct != null ? R.risk_per_trade_pct : 1;
    const capPct = R.max_pct_per_trade != null ? R.max_pct_per_trade : 8;
    const card = el('<div class="card calc"><h3>Position size — desk Rule 4</h3>' +
      '<div class="sub">Your own inputs; desk constants (risk ' + fmtNum(riskPct, 1) + "%/trade, " +
      capPct + "% max position value) applied locally.</div>" +
      '<label>Capital (PKR)<input id="cCap" type="number" min="1" step="any"></label>' +
      '<label>Entry<input id="cEnt" type="number" min="0" step="any"></label>' +
      '<label>Stop<input id="cStop" type="number" min="0" step="any"></label>' +
      '<div class="out" id="cOut">Enter capital, entry, stop.</div>' +
      '<div class="note">shares = floor(min(risk_budget/(entry−stop), capital×' + capPct + "%/entry)) — long only.</div></div>");
    const upd = () => {
      const cap = Number(card.querySelector("#cCap").value);
      const ent = Number(card.querySelector("#cEnt").value);
      const stp = Number(card.querySelector("#cStop").value);
      const out = card.querySelector("#cOut");
      if (!cap || !ent || !stp) { out.textContent = "Enter capital, entry, stop."; out.className = "out"; return; }
      if (ent <= stp) { out.textContent = "Invalid: entry must exceed stop."; out.className = "out err"; return; }
      const shares = Math.floor(Math.min((cap * riskPct / 100) / (ent - stp), (cap * capPct / 100) / ent));
      if (!shares || shares <= 0) { out.textContent = "Invalid: size rounds to zero."; out.className = "out err"; return; }
      const val = shares * ent;
      const risk = shares * (ent - stp);
      out.innerHTML = "<b>" + shares.toLocaleString() + " shares</b> · value Rs " + fmtCr(val) +
        " (" + fmtNum((val / cap) * 100, 1) + "% of capital) · risk Rs " + fmtCr(risk) +
        " (" + fmtNum((risk / cap) * 100, 2) + "%)";
      out.className = "out";
    };
    card.querySelectorAll("input").forEach((i) => i.addEventListener("input", upd));
    return card;
  }

  // ================= NOTES TAB =================
  async function renderNotes() {
    content.innerHTML = '<div class="loading">Loading your notes…</div>';
    try {
      myProfile = await fetchProfile();
    } catch (e) {
      content.innerHTML = "";
      content.appendChild(el('<div class="card"><h3>Notes</h3><div class="note">' +
        (e.message === "AUTH"
          ? "Sign in at desk.henneth.app first — notes sync to your account."
          : "Could not load notes (" + esc(e.message) + "). Try again shortly.") + "</div></div>"));
      return;
    }
    const notes = (myProfile && myProfile.notes) || {};
    const { pinned_notes } = await chrome.storage.local.get("pinned_notes");
    const pinned = new Set(pinned_notes || []);
    const syms = Object.keys(notes).sort((a, b) =>
      (pinned.has(b) - pinned.has(a)) || a.localeCompare(b));

    content.innerHTML = "";
    const wrap = el('<div class="card"><h3>Your notes — synced to your account</h3>' +
      '<div id="newNoteRow"><input id="newSym" placeholder="TICKER" maxlength="10"><button class="btn primary" id="newBtn">New note</button></div>' +
      '<div id="noteList"></div><div id="syncNote"></div></div>');
    content.appendChild(wrap);

    const list = wrap.querySelector("#noteList");
    if (!syms.length) {
      list.innerHTML = '<div class="empty">No notes yet. Start one for a ticker you are watching.</div>';
    }
    syms.forEach((sym) => list.appendChild(noteItem(sym, notes[sym])));
    wrap.querySelector("#newBtn").addEventListener("click", () => {
      const s = wrap.querySelector("#newSym").value.trim().toUpperCase();
      if (!s) return;
      if (list.querySelector('.empty')) list.innerHTML = "";
      if (!list.querySelector('[data-sym="' + s + '"]')) {
        // New notes (and pinned ones) sit above the rest.
        const firstUnpinned = list.querySelector('.noteitem:not(.pinned)');
        const item = noteItem(s, "");
        pinned.has(s) ? item.classList.add("pinned") : null;
        firstUnpinned ? list.insertBefore(item, firstUnpinned) : list.appendChild(item);
      }
      list.querySelector('[data-sym="' + s + '"]').scrollIntoView({ block: "nearest" });
    });
  }

  function noteItem(sym, text) {
    const item = el('<div class="noteitem" data-sym="' + esc(sym) + '">' +
      '<div class="nh"><span class="nsym">' + esc(sym) + '</span><span class="npin" title="pin to top">▲</span>' +
      '<span class="ndate"></span></div>' +
      '<div class="ntext"></div>' +
      '<textarea placeholder="Your thesis, levels, reminders…"></textarea>' +
      '<div class="nacts"><button class="btn primary nsave">Save</button>' +
      '<button class="btn ncancel">Cancel</button></div>' +
      '<div class="nhover"><button class="hbtn nedit" title="Edit">edit</button>' +
      '<button class="hbtn npin-t" title="Pin to top">pin</button>' +
      '<button class="hbtn ndel" title="Delete">delete</button></div></div>');
    const ta = item.querySelector("textarea");
    const view = item.querySelector(".ntext");
    const status = item.querySelector(".ndate");
    const acts = item.querySelector(".nacts");
    const hover = item.querySelector(".nhover");

    function setMode(editing) {
      ta.style.display = editing ? "" : "none";
      acts.style.display = editing ? "" : "none";
      view.style.display = editing ? "none" : "";
      hover.style.display = editing ? "none" : "";
      if (editing) { ta.focus(); }
    }

    function show(text2) {
      view.textContent = text2;
      ta.value = text2;
    }
    show(text || "");

    // A saved note opens in view mode; a brand-new one opens in the editor.
    setMode(!text);

    item.querySelector(".nsym").addEventListener("click", () => {
      currentSym = sym; tickerInput.value = sym;
      activeTab = "read";
      tabs.forEach((x) => x.classList.toggle("on", x.dataset.tab === "read"));
      render();
    });

    item.querySelector(".nedit").addEventListener("click", () => setMode(true));
    item.querySelector(".ncancel").addEventListener("click", () => {
      if (!view.textContent) { item.remove(); return; }   // brand-new, unsaved
      show(view.textContent);
      setMode(false);
    });

    item.querySelector(".npin-t").addEventListener("click", async () => {
      const { pinned_notes } = await chrome.storage.local.get("pinned_notes");
      const set = new Set(pinned_notes || []);
      const list = item.parentNode;
      if (set.has(sym)) {
        set.delete(sym); item.classList.remove("pinned");
        item.querySelector(".npin").classList.remove("on");
      } else {
        set.add(sym); item.classList.add("pinned");
        item.querySelector(".npin").classList.add("on");
        list.insertBefore(item, list.firstChild);
      }
      chrome.storage.local.set({ pinned_notes: Array.from(set) });
    });

    // Pin marker reflects stored state on load.
    chrome.storage.local.get("pinned_notes", ({ pinned_notes }) => {
      if ((pinned_notes || []).includes(sym)) {
        item.classList.add("pinned");
        item.querySelector(".npin").classList.add("on");
      }
    });

    item.querySelector(".nsave").addEventListener("click", async () => {
      status.textContent = "saving…";
      try {
        const notes = Object.assign({}, (myProfile && myProfile.notes) || {});
        const v = ta.value.trim();
        if (v) notes[sym] = v; else delete notes[sym];
        await saveNotes(notes);
        myProfile = myProfile || {};
        myProfile.notes = notes;
        show(v);
        setMode(false);
        status.textContent = "saved ✓";
        setTimeout(() => { if (status.isConnected) status.textContent = ""; }, 2500);
      } catch (e) {
        status.textContent = e.message === "AUTH" ? "sign in at desk.henneth.app" : "save failed — retry";
      }
    });
    item.querySelector(".ndel").addEventListener("click", async () => {
      try {
        const notes = Object.assign({}, (myProfile && myProfile.notes) || {});
        delete notes[sym];
        await saveNotes(notes);
        myProfile = myProfile || {};
        myProfile.notes = notes;
        const { pinned_notes } = await chrome.storage.local.get("pinned_notes");
        chrome.storage.local.set({ pinned_notes: (pinned_notes || []).filter((x) => x !== sym) });
        item.remove();
      } catch (e) {
        status.textContent = "delete failed — retry";
      }
    });
    return item;
  }

  // Initial health check on open.
  deskFetch("/state/health.json").then((h) => { health = h; renderHealth(); }).catch(() => {});
})();
