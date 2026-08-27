#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const APP = fs.readFileSync(path.join(ROOT, "Henneth Desk 2.CI.0", "app.js"), "utf8");
const SLICE = JSON.parse(fs.readFileSync(path.join(ROOT, "Henneth Desk 2.CI.0", "data", "company_intelligence.json"), "utf8"));
const STATE = JSON.parse(fs.readFileSync(path.join(ROOT, "state", "company_intel", "earnings_bridges.json"), "utf8"));
let checks = 0;
const assert = (condition, message) => { checks += 1; if (!condition) throw new Error(message); };
const PSX_PDF_RE = /^https:\/\/dps\.psx\.com\.pk\/download\/document\/\d+\.pdf$/;

function block(name, next) {
  const start = APP.indexOf(`function ${name}`);
  const end = APP.indexOf(`function ${next}`, start + 1);
  assert(start >= 0 && end > start, `${name} renderer missing`);
  return APP.slice(start, end);
}

try {
  const rows = Array.isArray(SLICE.tickers) ? SLICE.tickers : [];
  const symbols = rows.map(row => row?.symbol).filter(Boolean);
  assert(symbols.length === 20 && new Set(symbols).size === 20, "CI slice must contain exact pilot companies");
  assert(STATE.policy?.historical_descriptive_only === true, "earnings bridge state must be historical only");
  assert(STATE.policy?.formal_engine_eligibility_unchanged === true, "earnings bridge must not alter formal-engine eligibility");

  const route = block("renderCompanyEarnings", "earningsBridgeSourceLink");
  const sourceLink = block("earningsBridgeSourceLink", "earningsBridgeMetricRow");
  const metricRow = block("earningsBridgeMetricRow", "earningsBridgeRow");
  const bridgeRow = block("earningsBridgeRow", "reconciliationSourceLink");

  for (const token of ["earningsBridgeRow", "Historical earnings bridge", "No conflict-free annual bridge emitted", "does not infer earnings direction", "renderFinancialEvidenceReconciliation"]) {
    assert(route.includes(token), `earnings route missing ${token}`);
  }
  for (const token of ["safeHref", "source_url", "document_id", "fact_id", "page", "available_on", "target=\"_blank\"", "rel=\"noopener\""]) {
    assert(sourceLink.includes(token), `earnings source link missing ${token}`);
  }
  for (const token of ["previous_source", "current_source", "previous_value", "current_value", "change_amount", "change_pct", "unit"]) {
    assert(metricRow.includes(token), `earnings metric row missing ${token}`);
  }
  assert(bridgeRow.includes("not a forecast") || bridgeRow.includes("Descriptive history only"), "earnings bridge row must declare non-forecast status");
  assert(!/state\.data\?\.tickers[\s\S]*filter/.test(route), "earnings route must not derive bridge rows from browser-wide ticker data");

  assert(STATE.pilot_symbols?.join(",") === symbols.join(","), "earnings bridge state/slice pilot mismatch");
  let availableCompanies = 0;
  let bridgeCount = 0;
  for (const row of rows) {
    const bridge = row.earnings_bridges;
    const expected = STATE.companies?.[row.symbol];
    assert(bridge && typeof bridge === "object" && !Array.isArray(bridge), `${row.symbol}: earnings bridge row missing`);
    assert(JSON.stringify(bridge) === JSON.stringify(expected), `${row.symbol}: earnings bridge slice stale`);
    assert(bridge.formal_engine_status?.forecast === "not_activated", `${row.symbol}: forecast must remain not activated`);
    assert(bridge.formal_engine_status?.valuation === "not_activated", `${row.symbol}: valuation must remain not activated`);
    assert(bridge.formal_engine_status?.market_expectations === "not_activated", `${row.symbol}: market expectations must remain not activated`);
    if (bridge.bridge_count > 0) availableCompanies += 1;
    bridgeCount += bridge.bridge_count || 0;
    if (!bridge.bridge_count) {
      assert(bridge.status === "blocked_insufficient_conflict_free_aligned_history", `${row.symbol}: blocked rows must name the history gate`);
    }
    for (const item of bridge.bridges || []) {
      assert(item.status === "historical_descriptive_only", `${row.symbol}: bridge must stay descriptive`);
      assert(item.available_on <= STATE.as_of, `${row.symbol}: bridge available_on exceeds state cutoff`);
      for (const metric of ["revenue", "profit_after_tax_attributable", "basic_eps"]) {
        const data = item.metrics?.[metric];
        assert(data, `${row.symbol}: ${metric} bridge metric missing`);
        for (const key of ["previous_source", "current_source"]) {
          const source = data[key] || {};
          assert(source.fact_id && source.document_id && source.content_sha256, `${row.symbol}: ${metric} ${key} lacks id/hash provenance`);
          assert(PSX_PDF_RE.test(String(source.source_url || "")), `${row.symbol}: ${metric} ${key} source must be official PSX PDF`);
          assert(Number.isInteger(source.page) && source.page > 0, `${row.symbol}: ${metric} ${key} page missing`);
          assert(source.available_on && source.available_on <= STATE.as_of, `${row.symbol}: ${metric} ${key} availability invalid`);
        }
      }
    }
  }
  assert(availableCompanies === STATE.summary?.company_with_bridge_count, "available company summary mismatch");
  assert(bridgeCount === STATE.summary?.bridge_count, "bridge count summary mismatch");
  console.log(`earnings_bridges_ui: PASS (${checks} UI/data assertions, ${bridgeCount} historical bridges)`);
} catch (error) {
  console.error(`earnings_bridges_ui: FAIL - ${error.message}`);
  process.exitCode = 1;
}
