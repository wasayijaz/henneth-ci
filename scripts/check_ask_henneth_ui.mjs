#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const APP_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "app.js");
const CSS_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "styles.css");
const SLICE_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "data", "company_intelligence.json");
const app = fs.readFileSync(APP_PATH, "utf8");
const css = fs.readFileSync(CSS_PATH, "utf8");
const slice = JSON.parse(fs.readFileSync(SLICE_PATH, "utf8"));
let checks = 0;

function assert(condition, message) {
  checks += 1;
  if (!condition) throw new Error(message);
}

function count(text, pattern) {
  return (text.match(pattern) || []).length;
}

function main() {
  const rows = Array.isArray(slice.tickers) ? slice.tickers : [];
  const symbols = rows.map((row) => row?.symbol).filter(Boolean);
  assert(symbols.length === 20 && new Set(symbols).size === 20, "company slice must contain exactly 20 unique rows");
  assert(rows.every((row) => typeof row.symbol === "string" && row.name), "all 20 company rows have symbols and names");

  // Authenticated, same-origin network behavior; no client-side provider or secret path.
  assert(app.includes('fetch("api/ask"'), "Ask uses the relative api/ask path");
  assert(app.includes("Authorization: `Bearer ${currentToken}`"), "Ask sends the current bearer token");
  assert(app.includes('"content-type": "application/json"'), "Ask sends JSON content type");
  assert(count(app, /res\.status !== 401/g) === 1 && app.includes("await refreshSession()"), "Ask refreshes once on 401");
  assert(!app.includes("state.ask.busy"), "Ask does not use a global busy flag");
  assert(app.includes("state.ask.pending[symbol]") && app.includes("requestId"), "Ask tracks pending requests per symbol");
  assert(app.includes("state.ask.pending[symbol] !== requestId"), "stale Ask responses are discarded by request id");
  assert(app.includes("state.ask.pending = {}") && app.includes("state.ask.nextId += 1"), "sign-out invalidates pending Ask responses");
  assert(app.includes("state.selected === symbol"), "Ask focus is retained only for the active symbol");
  assert(!/process\.env|GROQ_API_KEY|service_role|(?:^|[^a-z])sk-[A-Za-z0-9]{10,}/i.test(app), "Ask UI contains no backend secret/provider reference");

  // Request bounds and non-leaking failures.
  assert(app.includes("ASK_MAX_QUESTION_BYTES = 4096"), "question byte cap matches the contract");
  assert(/id="askInput"[^>]+maxlength="4096"/.test(app), "Ask input exposes the contract bound");
  assert(app.includes("new TextEncoder().encode"), "Ask input enforces a UTF-8 byte bound");
  assert(app.includes('return map[error] || "Ask could not return a validated answer. Try again shortly."'), "unknown backend errors are generalized");
  assert(app.includes("role=\"status\" aria-live=\"polite\""), "Ask loading status is announced");
  assert(app.includes("role=\"alert\""), "Ask errors are announced");
  assert(app.includes("aria-describedby=\"askHelp\""), "Ask input has an accessible status description");

  // Nine deterministic server-owned sections, in contract order.
  const expected = ["conclusion", "evidence", "mechanism", "historical_benchmark", "financial_impact", "scenarios", "valuation_readiness", "confidence", "what_to_watch"];
  const block = /const ASK_SECTION_LABELS = \{([\s\S]*?)\n\};/.exec(app)?.[1] || "";
  const actual = [...block.matchAll(/^\s*([a-z_]+):/gm)].map((match) => match[1]);
  assert(JSON.stringify(actual) === JSON.stringify(expected), "Ask section order matches the deterministic contract");
  assert(app.includes("Object.keys(ASK_SECTION_LABELS)"), "renderer uses the deterministic section registry");
  for (const key of ["evidence", "historical_benchmark", "scenarios", "valuation_readiness", "confidence"]) {
    assert(app.includes(`key === "${key}"`), `${key} has a dedicated renderer path`);
  }
  assert(app.includes('section.text || "Unknown."'), "qualitative sections have a generic renderer path");
  assert(app.includes("unknown_or_missing" ) || app.includes('>Unknown.</p>'), "missing sections render an honest unknown state");
  assert(app.includes("blocked_not_implemented"), "blocked readiness states remain visible");

  // Citation safety and escaping: only server citation URLs can become links.
  assert(/function renderAskCitation[\s\S]*?safeHref\(citation\.source_url\)/.test(app), "Ask citations pass through safeHref");
  assert(/const safeHref = value =>[\s\S]*?\^https\?:\\\/\\\//.test(app), "safeHref allows only http(s)");
  assert(/function renderAskCitation[\s\S]*?esc\(label\)/.test(app), "citation labels are escaped");
  assert(/function renderAskCitation[\s\S]*?esc\(page\)/.test(app), "citation page labels are escaped");

  // Desktop/mobile layout and the three essential states.
  assert(css.includes(".ask-shell") && css.includes(".ask-answer") && css.includes(".ask-error"), "Ask desktop styles exist");
  assert(/@media \(max-width:900px\)[\s\S]*?\.ask-answer\{grid-template-columns:1fr\}/.test(css), "Ask answer collapses on mobile");
  assert(/@media \(max-width:560px\)[\s\S]*?\.ask-form>div\{grid-template-columns:1fr\}/.test(css), "Ask form stacks on narrow screens");
  assert(app.includes("The Ask endpoint could not be reached."), "Ask network error state exists");
  assert(app.includes("No Ask answer has been requested"), "Ask empty state exists");
  assert(app.includes("Reading retained evidence and validating the answer."), "Ask loading state exists");

  console.log(`ask_henneth_ui: PASS (${checks} UI assertions, ${symbols.length} company rows)`);
}

try { main(); } catch (error) {
  console.error(`ask_henneth_ui: FAIL — ${error.message}`);
  process.exitCode = 1;
}
