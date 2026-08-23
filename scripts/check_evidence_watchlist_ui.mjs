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

function rendererBlock(startName, endName) {
  const start = app.indexOf(`function ${startName}`);
  const end = app.indexOf(`function ${endName}`, start + 1);
  assert(start >= 0, `${startName} renderer missing`);
  assert(end > start, `${startName} renderer block end missing`);
  return app.slice(start, end);
}

function hasOwn(row, key) {
  return Object.prototype.hasOwnProperty.call(row, key);
}

function validSourceList(value, symbol, key) {
  assert(Array.isArray(value), `${symbol} ${key} must be an array`);
  for (const item of value) {
    if (typeof item === "string") {
      assert(/^https?:\/\//i.test(item), `${symbol} ${key} string entries must be http(s) official links`);
      continue;
    }
    assert(item && typeof item === "object" && !Array.isArray(item), `${symbol} ${key} entries must be objects or http(s) strings`);
    const url = item.source_url || item.url;
    if (url != null && url !== "") assert(/^https?:\/\//i.test(String(url)), `${symbol} ${key} link must be http(s)`);
  }
}

function main() {
  const rows = Array.isArray(slice.tickers) ? slice.tickers : [];
  const symbols = rows.map(row => row?.symbol).filter(Boolean);
  assert(symbols.length === 20 && new Set(symbols).size === 20, "CI slice must contain exactly 20 unique pilot companies");

  assert(app.includes('state.view === "watchlist" ? renderEvidenceWatchlist(r)'), "Watchlist route is wired");
  assert(app.includes('["watchlist", `Watchlist ${r.evidence_watchlist?.active_watch_count ?? "unknown"}`]'), "Watchlist tab is registered from row.evidence_watchlist");
  const block = rendererBlock("renderEvidenceWatchlist", "renderThesisCard");

  for (const token of [
    "r.evidence_watchlist",
    "row.evidence_watchlist",
    "What would confirm or break this signal",
    "active_watch_count",
    "status_counts",
    "monitored_assertion",
    "status_reason",
    "confirmation_check",
    "break_check",
    "next_evidence",
    "confidence",
    "financial_readiness",
    "source_evidence",
    "matched_evidence",
    "policy_flags",
    "safeHref",
    "No active evidence watch is open",
    "will not create checks from other state",
  ]) {
    assert(block.includes(token), `Watchlist renderer missing ${token}`);
  }

  assert(!/signal_clusters|thesis_monitoring|management_delivery|operating_events|causal_foundations|company_brain|price|valuation|forecast|probability|odds|advice/i.test(block.replace(/What would confirm or break this signal/g, "")), "Watchlist renderer reads outside its object or includes blocked policy language");
  assert(!/filter\(|find\(|reduce\(|match\(/.test(block), "Watchlist renderer must not infer or match evidence in the browser");
  assert(css.includes(".evidence-watchlist") && css.includes(".watchlist-card") && css.includes(".watchlist-sources"), "Watchlist styles exist");
  assert(/@media \(max-width:900px\)[\s\S]*?\.watchlist-status/.test(css), "Watchlist has mobile layout");

  const generatedRows = rows.filter(row => hasOwn(row, "evidence_watchlist"));
  assert(generatedRows.length === 20, `row.evidence_watchlist missing from ${20 - generatedRows.length} of 20 CI rows; run the backend slice builder before this UI check can pass`);

  let inactive = 0;
  let active = 0;
  for (const row of generatedRows) {
    const watch = row.evidence_watchlist;
    assert(watch && typeof watch === "object" && !Array.isArray(watch), `${row.symbol} evidence_watchlist must be an object`);
    assert(Number.isInteger(watch.active_watch_count) && watch.active_watch_count >= 0, `${row.symbol} active_watch_count must be a non-negative integer`);
    assert(typeof watch.status === "string" && watch.status.length > 0, `${row.symbol} status must be a non-empty string`);
    assert(typeof watch.status_reason === "string" && watch.status_reason.length > 0, `${row.symbol} status_reason must be a non-empty string`);
    assert(watch.status_counts && typeof watch.status_counts === "object" && !Array.isArray(watch.status_counts), `${row.symbol} status_counts must be an object`);
    assert(Array.isArray(watch.items), `${row.symbol} items must be an array`);
    if (watch.active_watch_count === 0 && watch.items.length === 0) inactive += 1;
    if (watch.active_watch_count > 0) active += 1;
    assert(watch.items.length === watch.active_watch_count, `${row.symbol} items length must equal active_watch_count`);
    for (const item of watch.items) {
      for (const key of ["monitored_assertion", "status", "status_reason", "confirmation_check", "break_check", "next_evidence", "confidence", "financial_readiness", "source_evidence", "matched_evidence", "policy_flags"]) {
        assert(hasOwn(item, key), `${row.symbol} watch item missing ${key}`);
      }
      assert(typeof item.monitored_assertion === "string" && item.monitored_assertion.length > 0, `${row.symbol} monitored_assertion must be non-empty`);
      assert(typeof item.status === "string" && item.status.length > 0, `${row.symbol} item status must be non-empty`);
      assert(typeof item.status_reason === "string" && item.status_reason.length > 0, `${row.symbol} item status_reason must be non-empty`);
      validSourceList(item.source_evidence, row.symbol, "source_evidence");
      validSourceList(item.matched_evidence, row.symbol, "matched_evidence");
      assert(Array.isArray(item.policy_flags), `${row.symbol} policy_flags must be an array`);
    }
  }
  assert(active === 5, `expected 5 active evidence-watchlist companies, found ${active}`);
  assert(inactive === 15, `expected honest empty state for 15 inactive companies, found ${inactive}`);

  console.log(`evidence_watchlist_ui: PASS (${checks} UI/data assertions, ${symbols.length} company rows, ${active} active, ${inactive} inactive)`);
}

try { main(); } catch (error) {
  console.error(`evidence_watchlist_ui: FAIL - ${error.message}`);
  process.exitCode = 1;
}
