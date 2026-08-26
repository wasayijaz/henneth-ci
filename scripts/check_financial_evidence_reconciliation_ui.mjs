#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const APP = fs.readFileSync(path.join(ROOT, "Henneth Desk 2.CI.0", "app.js"), "utf8");
const SLICE = JSON.parse(fs.readFileSync(path.join(ROOT, "Henneth Desk 2.CI.0", "data", "company_intelligence.json"), "utf8"));
const STATE = JSON.parse(fs.readFileSync(path.join(ROOT, "state", "company_intel", "financial_evidence_reconciliation.json"), "utf8"));
let checks = 0;
const assert = (condition, message) => { checks += 1; if (!condition) throw new Error(message); };

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
  assert(APP.includes("${renderFinancialEvidenceReconciliation(r)}"), "Earnings route must render financial reconciliation");
  const renderer = block("renderFinancialEvidenceReconciliation", "renderCompanyValuation");
  for (const token of ["r.financial_evidence_reconciliation", "eligible_fact_count", "audit_only_fact_count", "quarantined_fact_count", "missing_slot_count", "source_conflict_count", "earnings_bridge_status", "forecast_readiness_status", "Unavailable: not generated", "does not qualify facts"]) {
    assert(renderer.includes(token), `financial reconciliation renderer missing ${token}`);
  }
  assert(!/filter\(|find\(|reduce\(|match\(/.test(renderer), "financial reconciliation renderer must not infer or match evidence");
  assert(renderer.includes("Bounded backend fact-row preview"), "fact preview must identify its bounded display scope");
  const linkRenderer = block("reconciliationSourceLink", "reconciliationFactRow");
  assert(linkRenderer.includes("safeHref") && linkRenderer.includes("source_url"), "financial source links must use safeHref");
  assert(STATE.pilot_symbols?.join(",") === symbols.join(","), "financial reconciliation state/slice pilot mismatch");
  for (const row of rows) {
    const recon = row.financial_evidence_reconciliation;
    const expected = STATE.companies?.[row.symbol];
    assert(recon && typeof recon === "object" && !Array.isArray(recon), `${row.symbol} reconciliation missing`);
    assert(JSON.stringify(recon) === JSON.stringify(expected), `${row.symbol} reconciliation slice stale`);
    for (const count of ["eligible_fact_count", "audit_only_fact_count", "quarantined_fact_count", "missing_slot_count", "source_conflict_count"]) assert(Number.isInteger(recon[count]) && recon[count] >= 0, `${row.symbol} invalid ${count}`);
    assert(recon.readiness?.forecast === "blocked_insufficient_qualified_history", `${row.symbol} forecast must remain blocked`);
    assert(recon.readiness?.valuation === "blocked_insufficient_qualified_history", `${row.symbol} valuation must remain blocked`);
    for (const fact of recon.facts || []) {
      assert(["eligible", "audit_only", "quarantined"].includes(fact.status), `${row.symbol} invalid fact status`);
      if (fact.status === "eligible") assert(/^https:\/\/dps\.psx\.com\.pk\/download\/document\/\d+\.pdf$/.test(String(fact.source?.source_url || "")), `${row.symbol} eligible fact lacks exact PSX source`);
    }
  }
  console.log(`financial_evidence_reconciliation_ui: PASS (${checks} UI/data assertions, ${symbols.length} company rows)`);
} catch (error) {
  console.error(`financial_evidence_reconciliation_ui: FAIL - ${error.message}`);
  process.exitCode = 1;
}
