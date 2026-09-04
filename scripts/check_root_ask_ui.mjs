/* Offline behavioural checks for dashboard/app.js's root Ask section.
 * The section is evaluated in a tiny VM with DOM/auth/network doubles; no provider call is made.
 */
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const source = fs.readFileSync("dashboard/app.js", "utf8");
const start = source.indexOf("let _ask =");
const sectorMarker = source.indexOf("SECTOR DEBATES", start);
const end = source.lastIndexOf("/*", sectorMarker);
assert(start >= 0 && end > start, "Ask section boundaries found");

function harness({ fetchImpl, token = "old-token", feature = true } = {}) {
  const elements = {};
  let sampleButtons = [];
  const makeButton = (attrs = {}) => ({ disabled: false, listeners: {}, getAttribute(name) { return attrs[name] ?? null; }, addEventListener(name, fn) { this.listeners[name] = fn; } });
  const view = {
    _html: "",
    set innerHTML(value) {
      this._html = value;
      elements["ask-in"] = { value: "", disabled: false, setAttribute() {} };
      elements["ask-out"] = { innerHTML: "", scrollTop: 0 };
      elements["ask-send"] = makeButton();
      sampleButtons = [...String(value).matchAll(/data-ask-sample="([^"]*)"/g)].map(m => makeButton({ "data-ask-sample": m[1].replace(/&quot;/g, '"').replace(/&#39;/g, "'") }));
    },
    get innerHTML() { return this._html; },
    querySelectorAll(selector) { return selector.includes("data-ask-sample") ? sampleButtons : []; },
  };
  elements.view = view;
  const context = {
    console,
    Date,
    Promise,
    Error,
    JSON,
    Math,
    String,
    Object,
    Number,
    Set,
    URL,
    AbortController,
    TextEncoder,
    localStorage: { getItem: () => JSON.stringify({ access_token: token }) },
    location: { hostname: "desk.example", pathname: "/ask" },
    document: { querySelectorAll: selector => selector.includes("data-ask") ? [elements["ask-send"], ...sampleButtons].filter(Boolean) : [], getElementById: id => elements[id] || null },
    window: { renderRailAsk: () => {} },
    LOCAL: false,
    hasFeature: () => feature,
    authToken: async () => token,
    refreshSession: async () => null,
    fetch: fetchImpl || (async () => ({ ok: true, status: 200, json: async () => ({ ok: true, answer: "Answer" }) })),
    // Make deadline tests fast while preserving ordinary short timers.
    setTimeout: (fn, ms) => globalThis.setTimeout(fn, ms > 1000 ? 0 : ms),
    clearTimeout: id => globalThis.clearTimeout(id),
  };
  context.$ = id => id === "view" ? view : elements[id] || null;
  context.esc = value => String(value ?? "").replace(/[&<>\"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '\"': "&quot;", "'": "&#39;" }[c]));
  vm.runInNewContext(`${source.slice(start, end)}\n;globalThis.__ask={get state(){return _ask},ASK_SAMPLES,askSend,askRetry,askHistoryPayload,askThreadHtml,pageAsk,renderAsk};`, context);
  return { context, elements, view, samples: () => sampleButtons };
}

async function successChecks() {
  const calls = [];
  const h = harness({ fetchImpl: async (_url, options) => {
    calls.push(JSON.parse(options.body));
    return { ok: true, status: 200, json: async () => ({ ok: true, answer: "A useful answer" }) };
  }});
  const ask = h.context.__ask;
  await ask.pageAsk();
  assert.match(h.view.innerHTML, /data-ask-sample=/);
  assert.doesNotMatch(h.view.innerHTML, /askSend\('\s*What/);
  const sample = h.samples().find(b => b.getAttribute("data-ask-sample") === "What's happening in cement?");
  assert(sample, "apostrophe sample is represented as data, not executable string syntax");
  await sample.listeners.click();
  assert.equal(calls[0].question, "What's happening in cement?");

  ask.state.history = [{ role: "user", content: "Old" }, { role: "assistant", content: "x".repeat(1200) }];
  await ask.askSend("Follow up");
  const payload = calls.at(-1);
  assert.equal(payload.history.length, 2);
  assert.equal(payload.history[1].content.length, 500, "long assistant history is capped to the server's per-turn limit");
  assert.equal(JSON.stringify(ask.askHistoryPayload([
    { role: "user", content: "failed" }, { role: "assistant", content: "error", error: true },
    { role: "user", content: "ok" }, { role: "assistant", content: "good" },
  ])), JSON.stringify([{ role: "user", content: "ok" }, { role: "assistant", content: "good" }]));
}

async function failureChecks() {
  for (const [label, fetchImpl] of [
    ["network", async () => { throw new Error("offline"); }],
    ["invalid json", async () => ({ ok: true, status: 200, json: async () => { throw new Error("bad json"); } })],
    ["timeout", async () => new Promise(() => {})],
  ]) {
    const h = harness({ fetchImpl });
    const ask = h.context.__ask;
    await ask.askSend("Question");
    assert.equal(ask.state.busy, false, `${label} clears busy in finally`);
    assert.equal(ask.state.history.at(-1).error, true, `${label} renders a friendly error`);
    assert.equal(ask.state.history.at(-1).retry, true, `${label} exposes retry control`);
  }

  let count = 0, refreshed = 0;
  const h401 = harness({ fetchImpl: async (_url, options) => {
    count++;
    if (count === 1) return { ok: false, status: 401, json: async () => ({ ok: false, error: "account_required" }) };
    assert.equal(options.headers.Authorization, "Bearer fresh-token");
    return { ok: true, status: 200, json: async () => ({ ok: true, answer: "Recovered" }) };
  }});
  h401.context.refreshSession = async () => { refreshed++; return "fresh-token"; };
  await h401.context.__ask.askSend("401 once");
  assert.equal(count, 2, "only one automatic retry is made, for 401");
  assert.equal(refreshed, 1);
}

async function guardAndRetryChecks() {
  let release;
  let calls = 0;
  const pending = new Promise(resolve => { release = resolve; });
  const h = harness({ fetchImpl: async () => { calls++; return pending; } });
  const ask = h.context.__ask;
  h.elements["ask-in"] = { value: "keep this draft", disabled: false };
  const first = ask.askSend("Only once");
  await new Promise(resolve => globalThis.setTimeout(resolve, 0));
  assert.equal(h.elements["ask-in"].disabled, false, "page input remains editable while request is busy");
  await ask.askSend("Dropped while busy");
  assert.equal(calls, 1, "busy guard prevents duplicate paid requests");
  assert.equal(h.elements["ask-in"].value, "keep this draft", "busy guard preserves a page draft");
  release({ ok: true, status: 200, json: async () => ({ ok: true, answer: "Done" }) });
  await first;
  assert.equal(ask.state.busy, false);

  let sequence = 0;
  const hs = harness({ fetchImpl: async () => {
    sequence++;
    if (sequence === 1) throw new Error("offline");
    return { ok: true, status: 200, json: async () => ({ ok: true, answer: "New answer" }) };
  }});
  const as = hs.context.__ask;
  await as.askSend("First failure");
  assert.equal(as.state.history.at(-1).retry, true);
  await as.askSend("New question");
  assert.equal(as.state.history.some(x => x.retry), false, "a new success clears obsolete retry controls");

  let failures = 0;
  const hf = harness({ fetchImpl: async () => { failures++; throw new Error("offline"); } });
  const af = hf.context.__ask;
  await af.askSend("Failure one");
  await af.askSend("Failure two");
  assert.equal(af.state.history.filter(x => x.retry).length, 1, "only the latest failure remains retryable");
  assert.equal((af.askThreadHtml().match(/ask-retry/g) || []).length, 1, "only the latest error renders a retry button");

  let retryCalls = 0, retryBodies = [];
  const hr = harness({ fetchImpl: async (_url, options) => {
    retryCalls++; retryBodies.push(JSON.parse(options.body));
    if (retryCalls === 1) throw new Error("offline");
    return { ok: true, status: 200, json: async () => ({ ok: true, answer: "Retried" }) };
  }});
  const ar = hr.context.__ask;
  await ar.askSend("Retry me");
  await ar.askRetry();
  assert.equal(retryCalls, 2);
  assert.equal(JSON.stringify(retryBodies[0]), JSON.stringify(retryBodies[1]), "retry reuses the original question/history");
  assert.equal(ar.state.history.filter(x => x.error).length, 0, "retry removes the failed exchange before resending");
}

await successChecks();
await failureChecks();
await guardAndRetryChecks();
console.log("root Ask UI checks passed (samples, bounded follow-ups, failure recovery, 401 refresh, busy/retry guards)");
