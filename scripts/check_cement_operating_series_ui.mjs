#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const APP_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "app.js");
const SLICE_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "data", "company_intelligence.json");
const STATE_PATH = path.join(ROOT, "state", "company_intel", "cement_operating_series.json");

const app = fs.readFileSync(APP_PATH, "utf8");
const slice = JSON.parse(fs.readFileSync(SLICE_PATH, "utf8"));
const state = JSON.parse(fs.readFileSync(STATE_PATH, "utf8"));
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

function sourceBlock(source, startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start + startMarker.length);
  assert(start >= 0, `${startMarker} missing`);
  assert(end > start, `${endMarker} missing after ${startMarker}`);
  return source.slice(start, end);
}

function observations(row) {
  const metrics = row?.metrics || {};
  return Object.values(metrics).flatMap(value => Array.isArray(value) ? value : []);
}

function main() {
  const rows = Array.isArray(slice.tickers) ? slice.tickers : [];
  assert(rows.length === 20, "CI slice must keep the exact 20-company boundary");
  for (const row of rows) {
    assert(row && typeof row === "object", "slice row must be an object");
    assert(row.cement_operating_series && typeof row.cement_operating_series === "object", `${row.symbol} cement_operating_series missing`);
  }

  for (const sym of ["DGKC", "MLCF", "LUCK"]) {
    const sliceRow = rows.find(row => row.symbol === sym)?.cement_operating_series;
    const stateRow = state.companies?.[sym];
    assert(JSON.stringify(sliceRow) === JSON.stringify(stateRow), `${sym} cement operating row must match state exactly`);
  }

  const dgkc = rows.find(row => row.symbol === "DGKC")?.cement_operating_series;
  assert(dgkc.status === "audit_only_series_available", "DGKC audit-only status missing");
  assert(dgkc.observation_count >= 30, "DGKC operating observations not exposed");
  const dgkcObservations = observations(dgkc);
  assert(dgkcObservations.length === dgkc.observation_count, "DGKC observation count mismatch");
  for (const observation of dgkcObservations) {
    assert(observation.readiness === "audit_only", `${observation.observation_id} must stay audit_only`);
    assert(observation.model_eligibility === "not_model_loadable", `${observation.observation_id} must stay not model-loadable`);
    assert(observation.approval_status === "not_owner_approved_forecast_input", `${observation.observation_id} approval boundary missing`);
    const source = observation.source || {};
    assert(/^https?:\/\//i.test(String(source.source_url || "")), `${observation.observation_id} source URL missing`);
    assert(Number.isInteger(source.page) && source.page > 0, `${observation.observation_id} source page missing`);
    assert(source.document_id && source.content_sha256 && source.text, `${observation.observation_id} source evidence incomplete`);
    assert(source.available_on == null, `${observation.observation_id} must not promote retained/retrieved date to official availability`);
    assert(source.status === "publication_date_not_retained_audit_only", `${observation.observation_id} missing publication-date audit label`);
  }

  assert(rows.find(row => row.symbol === "MLCF")?.cement_operating_series?.status === "insufficient_aligned_annual_operating_history", "MLCF missing-history status not exposed");
  assert(rows.find(row => row.symbol === "LUCK")?.cement_operating_series?.status === "missing_retained_cement_operating_history", "LUCK missing-history status not exposed");
  for (const row of rows.filter(item => !["DGKC", "MLCF", "LUCK"].includes(item.symbol))) {
    assert(row.cement_operating_series.status === "unknown", `${row.symbol} non-cement row should remain unknown`);
    assert(row.cement_operating_series.observation_count === 0, `${row.symbol} non-cement row must not fabricate observations`);
    assert(Object.keys(row.cement_operating_series.metrics || {}).length === 0, `${row.symbol} non-cement metrics must stay empty`);
  }

  assert(app.includes("function renderCementOperatingSeries(r)"), "cement operating renderer missing");
  assert(app.includes("renderCementOperatingSeries(r)"), "Operating Intelligence view must render cement operating section");
  const block = sourceBlock(app, "function renderCementOperatingSeries", "const BENCHMARK_HORIZONS");
  assert(block.includes("r.cement_operating_series"), "renderer must read row.cement_operating_series");
  assert(block.includes("audit-only") && block.includes("not model-loadable"), "audit/model-loadable labels missing");
  assert(block.includes("source.available_on") && block.includes("publication date not retained"), "official availability boundary missing");
  assert(block.includes("safeHref(source.source_url)"), "official source links must use safeHref");
  assert(block.includes("financial_model_inputs") && block.includes("forecast") && block.includes("valuation"), "downstream blocked state must be displayed");
  assert(!/\b(?:forecast|valuation|market_expectations|financial_model_inputs)\s*=/.test(block), "renderer must not activate downstream products");
  const markupSafeBlock = block.replaceAll('target="_blank"', "");
  assert(!/\b(?:buy|sell|hold|upside|downside|fair value|recommend)\b/i.test(markupSafeBlock), "renderer contains advice language");

  console.log(`cement_operating_series_ui: PASS (${checks} UI assertions, ${rows.length} company rows)`);
}

try {
  main();
} catch (error) {
  console.error(`cement_operating_series_ui: FAIL - ${error.message}`);
  process.exitCode = 1;
}
