#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const app = fs.readFileSync(path.join(ROOT, "ci-app", "app.js"), "utf8");
const css = fs.readFileSync(path.join(ROOT, "ci-app", "styles.css"), "utf8");
const slice = JSON.parse(fs.readFileSync(path.join(ROOT, "ci-app", "data", "company_intelligence.json"), "utf8"));
let checks = 0;
const assert = (condition, message) => { checks += 1; if (!condition) throw new Error(message); };

try {
  assert(slice.tickers.length === 20, "exact 20-company boundary");
  for (const row of slice.tickers) {
    const brain = row.company_brain;
    assert(brain?.identity?.symbol === row.symbol, `${row.symbol}: identity`);
    assert(Object.keys(brain.domains || {}).length === 21, `${row.symbol}: domain matrix`);
    assert(brain.domains.forecasts?.status === "blocked" && brain.domains.valuation?.status === "blocked", `${row.symbol}: blocked downstream`);
    assert(Array.isArray(brain.intelligence_objects) && Array.isArray(brain.timeline), `${row.symbol}: typed products`);
  }
  assert(app.includes('["snapshot", "Investor snapshot"]') && app.includes('state.view === "snapshot" ? renderInvestorSnapshot(r)'), "snapshot tab/dispatch");
  assert(app.includes("function renderInvestorSnapshot(r)") && app.includes("What the business does") && app.includes("Current situation") && app.includes("What changed") && app.includes("Earnings direction") && app.includes("Valuation readiness") && app.includes("Catalysts") && app.includes("Risks") && app.includes("Hidden signals") && app.includes("Henneth scenarios"), "nine snapshot sections");
  assert(app.includes("r.company_brain?.timeline") && app.includes("objectTypeLabel(item.type)"), "unified typed timeline");
  assert(app.includes("Unknown —") && app.includes("blocked"), "visible unknown/blocked states");
  assert(css.includes(".brain-snapshot") && css.includes(".brain-timeline") && css.includes("@media (max-width:560px)"), "responsive Brain styles");
  console.log(`company_brain_ui: PASS (${checks} assertions, 20 company rows)`);
} catch (error) {
  console.error(`company_brain_ui: FAIL — ${error.message}`);
  process.exitCode = 1;
}
