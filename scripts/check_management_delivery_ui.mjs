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

function main() {
  const rows = Array.isArray(slice.tickers) ? slice.tickers : [];
  const symbols = rows.map(row => row?.symbol).filter(Boolean);
  assert(symbols.length === 20 && new Set(symbols).size === 20, "CI slice must contain exactly 20 unique pilot companies");
  const generatedRows = rows.filter(row => row && Object.prototype.hasOwnProperty.call(row, "management_delivery"));

  assert(app.includes("${renderManagementDelivery(r)}"), "Management Delivery is rendered inside the deterministic Thesis Monitor panel");
  assert(app.indexOf("${renderPrivateTheses(r)}") < app.indexOf("${renderManagementDelivery(r)}"), "Management Delivery stays separate from the private thesis notebook");
  assert(app.includes("function renderManagementDelivery(r)"), "Management Delivery renderer exists");
  const block = app.slice(app.indexOf("function renderManagementDelivery"), app.indexOf("function renderThesisCard"));

  assert(block.includes("r.management_delivery"), "renderer reads row.management_delivery");
  assert(block.includes("unavailable_not_generated"), "absent generated data renders unavailable/not generated");
  assert(!/delivery\?\.status\s*\|\|\s*"blocked_no_guidance_objects"/.test(block), "absent data must not infer blocked_no_guidance_objects");
  assert(block.includes("delivery.status") && block.includes("delivery.active_thesis_count") && block.includes("delivery.delivery_record_count"), "company-level emitted fields are displayed");
  assert(block.includes("Array.isArray(delivery.records) ? delivery.records : []"), "per-thesis records are read from records[]");
  assert(block.includes("record.status"), "record emitted status is displayed");
  assert(block.includes("record.reasons"), "record emitted reasons are displayed");
  assert(block.includes("record.thesis_id") && block.includes("record.assertion_key") && block.includes("record.conflict_key"), "record assertion linkage is displayed");
  assert(block.includes("source.linked_event_ids"), "source assertion linked event IDs are displayed");
  assert(block.includes("match?.event_id") && block.includes("match?.available_at") && block.includes("match?.effective_date"), "matched event ID and later evidence dates are displayed");
  assert(block.includes("record.confidence_link") && block.includes("confidence.confidence_id") && block.includes("confidence.source_cluster_id") && block.includes("confidence.band"), "confidence link object is displayed");
  assert(block.includes("record.limitations"), "record limitations are displayed");
  assert(block.includes("Read-only backend output"), "panel states the backend owns this output");
  assert(block.includes("does not match assertions, score delivery, forecast results, value the company, or turn this into advice"), "panel forbids browser matching/scoring/forecast/valuation/advice");
  assert(!/guidance_assertion_ids|linked_assertion_ids|later_event_ids|latest_evidence_date|confidence_url/.test(block), "renderer does not use speculative management-delivery aliases");

  assert(!/\b(score|scoring|forecast|valuation|advice)\s*[=:+\-*/]/i.test(block), "renderer does not calculate scores, forecasts, valuation, or advice");
  assert(!/match\(|filter\(.*assertion|filter\(.*event|reduce\(/i.test(block), "renderer does not browser-match assertions/events");

  for (const row of generatedRows) {
    const delivery = row.management_delivery;
    assert(delivery && typeof delivery === "object" && !Array.isArray(delivery), `${row.symbol} management_delivery must be an object`);
    assert(["tracked", "no_active_thesis"].includes(delivery.status), `${row.symbol} company status must match backend vocabulary`);
    assert(Array.isArray(delivery.records), `${row.symbol} records must be an array`);
    for (const record of delivery.records) {
      assert(["confirmed", "contradicted", "not_observed", "blocked_no_guidance_objects"].includes(record.status), `${row.symbol} record status must match backend vocabulary`);
      assert(record.source_assertion && Array.isArray(record.source_assertion.linked_event_ids), `${row.symbol} record source assertion link is missing`);
      assert(Array.isArray(record.reasons), `${row.symbol} record reasons must be an array`);
      assert(Array.isArray(record.limitations), `${row.symbol} record limitations must be an array`);
      assert(record.matched_event === null || typeof record.matched_event === "object", `${row.symbol} matched_event must be null or object`);
      assert(record.confidence_link === null || typeof record.confidence_link === "object", `${row.symbol} confidence_link must be null or object`);
    }
  }

  assert(css.includes(".management-delivery") && css.includes(".delivery-grid") && css.includes(".delivery-record"), "Management Delivery styles exist");
  assert(/@media \(max-width:900px\)[\s\S]*?\.delivery-grid/.test(css), "Management Delivery has mobile layout");

  console.log(`management_delivery_ui: PASS (${checks} UI assertions, ${symbols.length} company rows, ${generatedRows.length} generated management rows)`);
}

try { main(); } catch (error) {
  console.error(`management_delivery_ui: FAIL - ${error.message}`);
  process.exitCode = 1;
}
