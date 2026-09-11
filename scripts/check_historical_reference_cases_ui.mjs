#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const APP_PATH = path.join(ROOT, "ci-app", "app.js");
const CSS_PATH = path.join(ROOT, "ci-app", "styles.css");
const SLICE_PATH = path.join(ROOT, "ci-app", "data", "company_intelligence.json");
const ASSUMPTIONS_PATH = path.join(ROOT, "state", "company_intel", "financial_engine_assumptions.json");

const app = fs.readFileSync(APP_PATH, "utf8");
const css = fs.readFileSync(CSS_PATH, "utf8");
const slice = JSON.parse(fs.readFileSync(SLICE_PATH, "utf8"));
const assumptions = JSON.parse(fs.readFileSync(ASSUMPTIONS_PATH, "utf8"));
let checks = 0;

function assert(condition, message) {
  checks += 1;
  if (!condition) throw new Error(message);
}

function functionBlock(source, name, nextName) {
  const start = source.indexOf(`function ${name}`);
  const end = nextName ? source.indexOf(`function ${nextName}`, start + 1) : -1;
  assert(start >= 0, `${name} renderer missing`);
  return source.slice(start, end >= 0 ? end : undefined);
}

function sourceFacts(record) {
  return Array.isArray(record?.source_facts) ? record.source_facts : [];
}

function main() {
  const rows = Array.isArray(slice.tickers) ? slice.tickers : [];
  const symbols = rows.map(row => row?.symbol).filter(Boolean);
  assert(symbols.length === 20 && new Set(symbols).size === 20, "CI slice must contain exactly 20 unique pilot companies");

  const emittedReferenceRows = (assumptions.records || []).filter(record =>
    record?.record_type === "derived_reference_case" && record?.case_type === "reference_case"
  );
  assert(emittedReferenceRows.length > 0, "financial_engine_assumptions must have emitted derived reference-case records");
  for (const record of emittedReferenceRows) {
    assert(record.approved === false, `${record.symbol} ${record.metric} must remain not owner-approved`);
    assert(!Object.hasOwn(record, "value"), `${record.symbol} ${record.metric} must not expose formal-engine value`);
    assert(typeof record.derived_value === "number" && Number.isFinite(record.derived_value), `${record.symbol} ${record.metric} derived_value missing`);
    assert(Array.isArray(record.period_ends) && record.period_ends.length >= 3, `${record.symbol} ${record.metric} period_ends missing`);
    assert(record.available_on, `${record.symbol} ${record.metric} availability missing`);
    assert(record.formula && typeof record.formula === "object" && !Array.isArray(record.formula), `${record.symbol} ${record.metric} formula missing`);
    assert(sourceFacts(record).length > 0, `${record.symbol} ${record.metric} source facts missing`);
    for (const fact of sourceFacts(record)) {
      assert(/^https?:\/\//i.test(String(fact.source_url || "")), `${record.symbol} ${record.metric} source fact must carry official http(s) URL`);
    }
  }

  const sliceReferenceRows = rows.flatMap(row => Array.isArray(row?.historical_reference_cases?.cases) ? row.historical_reference_cases.cases.map(record => ({ row, record })) : []);
  assert(sliceReferenceRows.length === emittedReferenceRows.length, `slice reference case count mismatch: ${sliceReferenceRows.length} vs ${emittedReferenceRows.length}`);
  for (const { row, record } of sliceReferenceRows) {
    assert(record.metric && Object.hasOwn(record, "derived_value"), `${row.symbol} slice reference case metric/value missing`);
    assert(Array.isArray(record.period_ends), `${row.symbol} slice reference case period_ends missing`);
    assert(record.available_on, `${row.symbol} slice reference case available_on missing`);
    assert(record.formula && typeof record.formula === "object" && !Array.isArray(record.formula), `${row.symbol} slice reference case formula missing`);
    assert(sourceFacts(record).every(fact => /^https?:\/\//i.test(String(fact.source_url || ""))), `${row.symbol} slice reference case source links must be http(s)`);
  }

  assert(app.includes("${renderHistoricalReferenceCases(r)}"), "Historical reference cases must render inside Financial Baseline");
  assert(app.includes("function renderHistoricalReferenceCases(r)"), "Historical reference cases renderer missing");
  assert(app.includes("function referenceCaseRows(r)") && app.includes("r?.historical_reference_cases?.cases"), "renderer must read row.historical_reference_cases.cases");
  const block = functionBlock(app, "renderHistoricalReferenceCases", "function renderFinancialBaseline");
  assert(block.includes("reported-history-derived reference cases only"), "reported-history boundary copy missing");
  assert(block.includes("not forecasts") && block.includes("not formal valuations") && block.includes("not targets") && block.includes("not recommendations") && block.includes("not advice"), "no forecast/valuation/target/advice copy missing");
  assert(block.includes("record.metric") && block.includes("record.derived_value"), "metric and derived_value must be displayed");
  assert(block.includes("referenceCasePeriods(record)") && app.includes("period_ends"), "covered period ends must be displayed");
  assert(block.includes("record.available_on") && block.includes("record.assumption_status"), "availability/status must be displayed");
  assert(block.includes("referenceCaseFormula(record)") && app.includes("record?.formula"), "formula must be displayed");
  assert(block.includes("referenceCaseSourceLinks(record)") && app.includes("safeHref(fact?.source_url)"), "official source links must use safeHref");
  assert(block.includes("No historical_reference_cases rows were emitted"), "empty state must name missing emitted rows");
  assert(!/fetch\(|companyThesisRequest|financial_engine_assumptions|state\/company_intel/.test(block), "browser renderer must not fetch or read builder state paths");
  assert(!/\b(?:buy|sell|hold|recommend|should buy|should sell)\b/i.test(block.replace("not recommendations", "")), "renderer must not contain advice language");

  assert(css.includes(".historical-reference-cases") && css.includes(".reference-case-card") && css.includes(".reference-case-sources"), "Historical reference case styles missing");
  assert(/@media \(max-width:900px\)[\s\S]*?\.reference-case-card/.test(css), "Historical reference case responsive styles missing");

  console.log(`historical_reference_cases_ui: PASS (${checks} UI assertions, ${emittedReferenceRows.length} emitted reference rows, ${sliceReferenceRows.length} slice rows)`);
}

try {
  main();
} catch (error) {
  console.error(`historical_reference_cases_ui: FAIL - ${error.message}`);
  process.exitCode = 1;
}
