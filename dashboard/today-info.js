/* Today heading explainers.  Deliberately small, plain DOM, and scoped to one .today-page root. */
(function () {
  "use strict";

  const COPY = Object.freeze({
    stance: "The desk’s overall research outlook for this cycle. It is a research view, not a trading instruction.",
    index: "KSE-100 is a benchmark of major PSX companies. The move compares dated closes from the supplied index history; it is not a live quote.",
    changed: "What changed compares the latest available snapshot with the prior dated snapshot. Other tiles show current counts, not changes.",
    radar: "Research Radar lists names flagged for further research. The plot compares historical net expectancy and win rate; it is evidence, not a recommendation.",
    favoured: "A favoured sector has a more positive briefing outlook, with risks still recorded. This is not a buy or sell instruction.",
    avoiding: "An avoiding sector has a more cautious briefing outlook because of its risks. This is not a buy or sell instruction.",
    catalyst: "A catalyst is a dated research event. Dates may be estimates; the desk does not predict a price move from them.",
    timeline: "The catalyst timeline lists dated research events, including events that may be estimated or unconfirmed.",
    breadth: "Sector breadth counts qualifying names that rose, were flat, or fell. It is not the whole market and is not index-weighted.",
    watchlist: "Watchlist names are saved by the account. Prices and mini-charts can come from different data timestamps.",
    confidence: "Confidence is the supplied research confidence label. It is not a probability of profit.",
    expectancy: "Expectancy is the average historical net result per tested trade, shown as a percentage. It is not a forecast.",
    hit_rate: "Hit rate is the share of historical tested trades that were profitable; it is not sufficient on its own to judge a strategy.",
    sample: "Sample is the number of tested trades. Small samples provide less evidence.",
    out_of_sample: "Out of sample is the historical hit rate on data outside development. It is not a guarantee.",
    lesson: "The next unfinished educational lesson is separate from the desk’s research read.",
    setup: "Desk setup opens research-workspace settings. It does not change the desk’s research output.",
    chart_index: "The line shows KSE-100 benchmark levels across the supplied dated closes. The latest point is not a live quote.",
    chart_radar: "Each point compares historical net expectancy with historical win rate. Sample size and out-of-sample status are supporting evidence, not a recommendation.",
    chart_breadth: "ADV counts names above +0.05%, FLAT includes −0.05% through +0.05%, and DEC is below −0.05%. AVG is the simple average daily move of names with data, not index-weighted.",
    metrics: "Confidence — supplied research label, not profit probability.\nExpectancy — average historical net result per trade, not a forecast.\nHit rate — share of profitable tested trades.\nSample — tested-trade count; small samples are weaker evidence.\nOut of sample — historical hit rate outside development, not a guarantee.",
  });

  const states = new WeakMap();
  let active = null;
  let panelId = 0;

  function norm(value) {
    return String(value || "").toLowerCase().replace(/[·:()]/g, " ").replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
  }
  function keyFor(el) {
    const explicit = el.getAttribute("data-info-key");
    if (explicit && COPY[explicit]) return explicit;
    const parentClass = String(el.parentElement?.getAttribute?.("class") || "");
    if (parentClass.includes("today-radar-card-head")) return "confidence";
    if (parentClass.includes("today-radar-oos")) return "out_of_sample";
    if (parentClass.includes("today-lesson") || el.closest?.(".today-lesson")) return "lesson";
    const label = norm(el.textContent);
    const map = [
      ["today s stance", "stance"], ["kse 100", "index"], ["what changed", "changed"], ["research radar", "radar"],
      ["favoured", "favoured"], ["avoiding", "avoiding"], ["next catalyst", "catalyst"], ["catalyst timeline", "timeline"],
      ["sector breadth", "breadth"], ["watchlist", "watchlist"], ["confidence", "confidence"], ["expectancy", "expectancy"],
      ["hit rate", "hit_rate"], ["sample", "sample"], ["out of sample", "out_of_sample"], ["lesson", "lesson"], ["desk setup", "setup"],
    ];
    return map.find(([needle]) => label === needle || label.startsWith(needle + " "))?.[1] || null;
  }
  function labelFor(key, el) {
    const text = String(el.textContent || "").replace(/\s+/g, " ").trim();
    if (key === "chart_index") return "KSE-100 chart";
    if (key === "chart_radar") return "Research Radar chart";
    if (key === "chart_breadth") return "Sector breadth chart";
    return text.replace(/[·].*$/, "").trim() || key.replace(/_/g, " ");
  }
  function close(state) {
    if (!state || !state.panel) return;
    state.panel.hidden = true;
    state.button.setAttribute("aria-expanded", "false");
    if (active === state) active = null;
  }
  function position(state) {
    const panel = state.panel, rect = state.button.getBoundingClientRect();
    panel.style.left = "8px"; panel.style.top = "8px";
    const box = panel.getBoundingClientRect(), vw = window.innerWidth || document.documentElement.clientWidth || 1024, vh = window.innerHeight || document.documentElement.clientHeight || 768;
    let left = Math.min(Math.max(8, rect.left), Math.max(8, vw - box.width - 8));
    let top = rect.bottom + 8;
    if (top + box.height > vh - 8) top = rect.top - box.height - 8;
    top = Math.min(Math.max(8, top), Math.max(8, vh - box.height - 8));
    panel.style.left = `${Math.round(left)}px`; panel.style.top = `${Math.round(top)}px`;
  }
  function open(state, reason = "manual") {
    if (active && active !== state) close(active);
    if (state.closeTimer) { clearTimeout(state.closeTimer); state.closeTimer = null; }
    active = state; state.openReason = reason; state.panel.hidden = false; state.button.setAttribute("aria-expanded", "true"); position(state);
  }
  function scheduleClose(state) {
    if (state.closeTimer) clearTimeout(state.closeTimer);
    state.closeTimer = setTimeout(() => { state.closeTimer = null; if ((state.openReason === "hover" || state.openReason === "focus") && !state.hoveringButton && !state.hoveringPanel && document.activeElement !== state.button && !state.panel.contains(document.activeElement)) close(state); }, 140);
  }
  function addOne(root, el, key, label) {
    if (el.querySelector(":scope > .today-info-trigger")) return null;
    const button = document.createElement("button");
    button.type = "button"; button.className = "today-info-trigger"; button.textContent = "i";
    button.setAttribute("aria-label", `About ${label}`); button.setAttribute("aria-expanded", "false");
    const panel = document.createElement("div"); panel.className = "today-info-popover"; panel.hidden = true; panel.id = `today-info-${++panelId}`; panel.setAttribute("role", "dialog"); panel.setAttribute("aria-label", `About ${label}`);
    const copy = document.createElement("p"); copy.textContent = COPY[key]; panel.appendChild(copy); document.body.appendChild(panel);
    button.setAttribute("aria-controls", panel.id);
    const state = { root, button, panel, hoveringButton: false, hoveringPanel: false, closeTimer: null };
    button.addEventListener("click", event => { event?.stopPropagation(); if (active === state && !panel.hidden) { if (state.openReason === "hover" || state.openReason === "focus") state.openReason = "manual"; else close(state); } else open(state, "manual"); });
    button.addEventListener("pointerenter", event => { state.hoveringButton = true; if (event?.pointerType !== "touch") open(state, "hover"); });
    button.addEventListener("pointerleave", () => { state.hoveringButton = false; scheduleClose(state); });
    button.addEventListener("focus", () => { if (state.ignoreFocus) { state.ignoreFocus = false; return; } open(state, "focus"); });
    button.addEventListener("blur", () => scheduleClose(state));
    panel.addEventListener("pointerenter", () => { state.hoveringPanel = true; if (state.closeTimer) clearTimeout(state.closeTimer); });
    panel.addEventListener("pointerleave", () => { state.hoveringPanel = false; scheduleClose(state); });
    const interactive = el.closest?.("button, a");
    if (interactive?.parentElement) {
      const parentClass = String(interactive.parentElement.getAttribute?.("class") || "");
      if (parentClass.includes("today-info-disclosure-wrap")) interactive.parentElement.appendChild(button);
      else if (String(interactive.getAttribute?.("class") || "").includes("today-disclosure")) {
        const wrap = document.createElement("div"); wrap.className = "today-info-disclosure-wrap";
        interactive.parentElement.insertBefore(wrap, interactive); wrap.appendChild(interactive); wrap.appendChild(button);
      } else interactive.parentElement.insertBefore(button, interactive.nextSibling);
    } else el.appendChild(button);
    return state;
  }
  function addChartGuide(root, canvas, key) {
    if (key === "chart_index" || key === "chart_radar") return null;
    const parent = canvas.parentElement;
    if (!parent || parent.querySelector(":scope > .today-info-chart-guide")) return null;
    const button = document.createElement("button"); button.type = "button"; button.className = "today-info-trigger today-info-chart-guide"; button.textContent = "i";
    const label = labelFor(key, canvas); button.setAttribute("aria-label", `About ${label}`); button.setAttribute("aria-expanded", "false");
    const panel = document.createElement("div"); panel.className = "today-info-popover"; panel.hidden = true; panel.id = `today-info-${++panelId}`; panel.setAttribute("role", "dialog"); panel.setAttribute("aria-label", `About ${label}`);
    const copy = document.createElement("p"); copy.textContent = COPY[key]; panel.appendChild(copy); document.body.appendChild(panel); button.setAttribute("aria-controls", panel.id);
    const state = { root, button, panel, hoveringButton: false, hoveringPanel: false, closeTimer: null };
    button.addEventListener("click", event => { event?.stopPropagation(); if (active === state && !panel.hidden) { if (state.openReason === "hover" || state.openReason === "focus") state.openReason = "manual"; else close(state); } else open(state, "manual"); });
    button.addEventListener("pointerenter", event => { state.hoveringButton = true; if (event?.pointerType !== "touch") open(state, "hover"); }); button.addEventListener("pointerleave", () => { state.hoveringButton = false; scheduleClose(state); }); button.addEventListener("focus", () => { if (state.ignoreFocus) { state.ignoreFocus = false; return; } open(state, "focus"); }); button.addEventListener("blur", () => scheduleClose(state));
    panel.addEventListener("pointerenter", () => { state.hoveringPanel = true; if (state.closeTimer) clearTimeout(state.closeTimer); }); panel.addEventListener("pointerleave", () => { state.hoveringPanel = false; scheduleClose(state); });
    const heading = parent.querySelector?.(".hn-chart-heading");
    if (heading) heading.appendChild(button); else parent.insertBefore(button, canvas);
    return state;
  }
  function addMetricsGuide(root, cards) {
    const parent = cards?.parentElement;
    if (!parent || parent.querySelector?.(":scope > .today-info-metrics-guide")) return null;
    const button = document.createElement("button"); button.type = "button"; button.className = "today-info-trigger today-info-metrics-guide";
    button.appendChild(document.createTextNode("Metrics guide")); const glyph = document.createElement("span"); glyph.className = "today-info-glyph"; glyph.textContent = "i"; button.appendChild(glyph);
    const label = "Metrics guide"; button.setAttribute("aria-label", `About ${label}`); button.setAttribute("aria-expanded", "false");
    const panel = document.createElement("div"); panel.className = "today-info-popover"; panel.hidden = true; panel.id = `today-info-${++panelId}`; panel.setAttribute("role", "dialog"); panel.setAttribute("aria-label", `About ${label}`);
    const copy = document.createElement("p"); copy.textContent = COPY.metrics; panel.appendChild(copy); document.body.appendChild(panel); button.setAttribute("aria-controls", panel.id);
    const state = { root, button, panel, hoveringButton: false, hoveringPanel: false, closeTimer: null };
    button.addEventListener("click", event => { event?.stopPropagation(); if (active === state && !panel.hidden) { if (state.openReason === "hover" || state.openReason === "focus") state.openReason = "manual"; else close(state); } else open(state, "manual"); });
    button.addEventListener("pointerenter", event => { state.hoveringButton = true; if (event?.pointerType !== "touch") open(state, "hover"); }); button.addEventListener("pointerleave", () => { state.hoveringButton = false; scheduleClose(state); }); button.addEventListener("focus", () => { if (state.ignoreFocus) { state.ignoreFocus = false; return; } open(state, "focus"); }); button.addEventListener("blur", () => scheduleClose(state));
    panel.addEventListener("pointerenter", () => { state.hoveringPanel = true; if (state.closeTimer) clearTimeout(state.closeTimer); }); panel.addEventListener("pointerleave", () => { state.hoveringPanel = false; scheduleClose(state); });
    parent.insertBefore(button, cards);
    return state;
  }
  function enhance(root) {
    if (!root || !root.querySelectorAll) return;
    const page = root.matches?.(".today-page") ? root : root.querySelector(".today-page");
    if (!page) return;
    const old = states.get(root); if (old) old.forEach(state => { if (state.closeTimer) clearTimeout(state.closeTimer); if (active === state) active = null; state.panel.remove(); state.button.remove(); });
    const added = [];
    const selectors = ["[data-info-key]", ".today-kicker", ".today-disclosure small", ".today-strip-label"];
    const seen = new Set();
    page.querySelectorAll(selectors.concat(".today-change-strip > b").join(",")).forEach(el => { if (seen.has(el)) return; seen.add(el); const key = keyFor(el); if (key && COPY[key] && !(key === "breadth" && el.closest?.(".today-breadth"))) { const state = addOne(page, el, key, labelFor(key, el)); if (state) added.push(state); } });
    page.querySelectorAll("[data-hn-today-index] canvas, canvas.hn-desk-radar-canvas, canvas.hn-sector-matrix-canvas").forEach(canvas => {
      const key = canvas.matches("canvas.hn-desk-radar-canvas") ? "chart_radar" : canvas.matches("canvas.hn-sector-matrix-canvas") ? "chart_breadth" : "chart_index";
      const state = addChartGuide(root, canvas, key); if (state) added.push(state);
    });
    const metricsState = addMetricsGuide(page, page.querySelector(".today-radar-cards"));
    if (metricsState) added.push(metricsState);
    states.set(root, added);
  }
  document.addEventListener("keydown", event => { if (event.key === "Escape" && active) { const state = active, button = state.button; close(state); state.ignoreFocus = true; button.focus(); } });
  document.addEventListener("pointerdown", event => { if (active && event.target !== active.button && !active.button.contains(event.target) && !active.panel.contains(event.target)) close(active); });
  window.HennethTodayInfo = { enhance };
})();
