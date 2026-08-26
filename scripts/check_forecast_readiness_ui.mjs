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

function functionBlock(source, name, nextName) {
  const start = source.indexOf(`function ${name}`);
  const end = nextName ? source.indexOf(`function ${nextName}`, start + 1) : -1;
  assert(start >= 0, `${name} renderer missing`);
  return source.slice(start, end >= 0 ? end : undefined);
}

function candidateRefs(row) {
  const readiness = row.forecast_readiness || {};
  return readiness.qualification_candidate_document_refs || readiness.qualification_candidate_documents || [];
}

function main() {
  const rows = Array.isArray(slice.tickers) ? slice.tickers : [];
  const symbols = rows.map(row => row?.symbol).filter(Boolean);
  assert(symbols.length === 20 && new Set(symbols).size === 20, "CI slice must contain exactly 20 unique pilot companies");

  const readinessRows = rows.filter(row => row && Object.hasOwn(row, "forecast_readiness"));
  assert(readinessRows.length === 20, "row.forecast_readiness must be emitted for all 20 pilot companies");

  for (const row of rows) {
    const readiness = row.forecast_readiness;
    assert(readiness && typeof readiness === "object" && !Array.isArray(readiness), `${row.symbol} forecast_readiness missing`);
    if (row.symbol === "MLCF") {
      assert(readiness.status === "input_ready", "MLCF forecast readiness must reflect qualified live inputs");
      assert(readiness.qualified_period_count === 3, "MLCF qualified period count must be three");
      assert(readiness.missing_requirements.length === 0, "MLCF input-ready row must not name missing input requirements");
    } else {
      assert(typeof readiness.status === "string" && readiness.status.startsWith("blocked"), `${row.symbol} forecast readiness must remain blocked without qualified inputs`);
      assert(readiness.missing_requirements.length > 0, `${row.symbol} blocked row must name missing requirements`);
    }
    assert(readiness.model_registry && typeof readiness.model_registry === "object" && !Array.isArray(readiness.model_registry), `${row.symbol} model_registry missing`);
    assert(readiness.model_registry.status === "supported", `${row.symbol} model registry must be supported`);
    assert(typeof readiness.model_version === "string" && readiness.model_version.length > 0, `${row.symbol} model_version missing`);
    assert(Number.isInteger(readiness.qualified_period_count), `${row.symbol} qualified_period_count missing`);
    assert(Array.isArray(readiness.missing_requirements), `${row.symbol} missing_requirements missing`);
    assert(Array.isArray(candidateRefs(row)), `${row.symbol} qualification candidate document refs missing`);
    for (const doc of candidateRefs(row)) {
      assert(doc && typeof doc === "object" && !Array.isArray(doc), `${row.symbol} candidate ref must be object`);
      assert(doc.document_id || doc.doc_id || doc.ref_id, `${row.symbol} candidate ref must carry official document id`);
      assert(/^https?:\/\//i.test(String(doc.source_url || doc.url || "")), `${row.symbol} candidate ref must carry official http(s) source`);
    }
    const downstream = readiness.downstream_status || {};
    for (const key of ["forecast", "valuation", "market_expectations", "numeric_impact"]) {
      assert(typeof downstream[key] === "string" && downstream[key].startsWith("blocked"), `${row.symbol} ${key} must remain blocked`);
    }
    assert(readiness.policy && typeof readiness.policy === "object" && !Array.isArray(readiness.policy), `${row.symbol} policy missing`);
    assert(Array.isArray(readiness.limitations), `${row.symbol} limitations missing`);
  }

  assert(app.includes('["forecast", "Forecast readiness"]'), "Forecast Readiness tab missing");
  assert(app.includes('state.view === "forecast" ? renderForecastReadiness(r)'), "Forecast Readiness tab is not wired");
  assert(app.includes("function renderForecastReadiness(r)"), "Forecast Readiness renderer missing");
  const block = functionBlock(app, "renderForecastReadiness", "renderFinancialCoverage");
  assert(block.includes("r.forecast_readiness"), "renderer must read row.forecast_readiness");
  assert(block.includes("readiness.status"), "exact backend status must be displayed");
  assert(block.includes("readiness.model_registry"), "model_registry must be displayed");
  assert(block.includes("readiness.model_version"), "model_version must be displayed");
  assert(block.includes("readiness.qualified_period_count"), "qualified_period_count must be displayed");
  assert(block.includes("readiness.missing_requirements"), "missing requirements must be displayed");
  assert(block.includes("qualification_candidate_document_refs") && block.includes("readinessDocLink(doc)"), "qualification candidate refs must be displayed as official refs");
  assert(block.includes("downstream_status") && block.includes("numeric_impact"), "downstream blocked states must include numeric impact");
  assert(block.includes("readiness.policy") && block.includes("readiness.limitations"), "policy and limitations must be displayed");
  assert(block.includes("does not infer qualification, calculate projections, value the company, estimate odds, emit targets, or turn this into advice"), "read-only no-forecast boundary copy missing");
  assert(app.includes("function readinessDocLink(doc)") && app.includes("safeHref(doc?.source_url || doc?.url)"), "candidate document links must use safeHref");

  const forbidden = [
    /\b(?:eps|price|revenue|income|cashflow|cash_flow|fcf|ebitda)\s*[*+\-/]/i,
    /\b(?:target|upside|downside|fair value|buy|sell|hold|recommend|should buy|should sell)\b/i,
    /\b(?:probability|odds|chance)\s*[:=]/i,
    /\b(?:forecast|valuation|projection|numeric impact)\s*[:=]\s*(?!.*blocked)/i,
    /\b(?:calculate|compute|infer|derive|project|predict|estimate|valueCompany)\s*\(/i,
    /\bfetch\s*\(/i,
  ];
  const sanitized = block
    .replace("does not infer qualification, calculate projections, value the company, estimate odds, emit targets, or turn this into advice", "")
    .replaceAll("Forecast / valuation readiness", "")
    .replaceAll("Forecast Readiness", "");
  for (const pattern of forbidden) assert(!pattern.test(sanitized), `renderer contains forbidden calculation/advice pattern: ${pattern}`);

  assert(css.includes(".forecast-readiness-shell") && css.includes(".forecast-readiness-summary") && css.includes(".forecast-readiness-docs"), "Forecast Readiness styles missing");
  assert(/@media \(max-width:900px\)[\s\S]*?\.forecast-readiness-summary/.test(css), "Forecast Readiness responsive styles missing");

  console.log(`forecast_readiness_ui: PASS (${checks} UI assertions, ${symbols.length} company rows)`);
}

try {
  main();
} catch (error) {
  console.error(`forecast_readiness_ui: FAIL - ${error.message}`);
  process.exitCode = 1;
}
