#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const APP = fs.readFileSync(path.join(ROOT, "ci-app", "app.js"), "utf8");
const SLICE = JSON.parse(fs.readFileSync(path.join(ROOT, "ci-app", "data", "company_intelligence.json"), "utf8"));
const STATE = JSON.parse(fs.readFileSync(path.join(ROOT, "state", "company_intel", "monitoring.json"), "utf8"));
let checks = 0;
const assert = (condition, message) => { checks += 1; if (!condition) throw new Error(message); };

function renderer(name, next) {
  const start = APP.indexOf(`function ${name}`);
  const end = APP.indexOf(`function ${next}`, start + 1);
  assert(start >= 0 && end > start, `${name} renderer missing`);
  return APP.slice(start, end);
}

try {
  const rows = Array.isArray(SLICE.tickers) ? SLICE.tickers : [];
  const symbols = rows.map(row => row?.symbol).filter(Boolean);
  assert(symbols.length === 20 && new Set(symbols).size === 20, "CI slice must contain the exact 20-company pilot");
  assert(APP.includes('state.view === "monitoring" ? renderCiMonitoring(r)'), "CI monitoring route is not wired");
  assert(APP.includes('["monitoring", `Monitoring ${r.monitoring?.alert_count ?? "unknown"}`]'), "monitoring tab must use emitted row.monitoring count");
  const block = renderer("renderCiMonitoring", "renderCiMonitoringAlert");
  for (const token of ["r.monitoring", "status_reason", "latest_source_at", "latest_change_at", "latest_event_at", "source_health", "activity", "alerts", "Unavailable: the CI slice has not emitted", "does not calculate status"]) {
    assert(block.includes(token), `monitoring renderer missing ${token}`);
  }
  assert(APP.includes("${renderCiEventWindows(r)}"), "CI monitoring view must include event-window extension");
  const windowBlock = renderer("renderCiEventWindows", "renderCiMonitoring");
  for (const token of ["r.event_review_windows", "row.event_review_windows", "known_events", "confirmed_events", "expected_reporting_windows", "review_windows", "does not schedule AI tasks", "infer a filing", "Known retained calendar events", "Conservative expected reporting windows", "3-5-day intensified deterministic review window"]) {
    assert(windowBlock.includes(token), `event-window renderer missing ${token}`);
  }
  assert(windowBlock.includes("Unavailable: the CI slice has not emitted row.event_review_windows"), "event-window renderer must expose unknown missing state");
  assert(windowBlock.includes("No event-window object was emitted"), "event-window renderer must show emitted-object absence");
  const cardBlock = renderer("renderEventWindowCard", "renderEventWindowGroup");
  assert(cardBlock.includes("Event date") && cardBlock.includes("Window start") && cardBlock.includes("Window end"), "event-window cards must display emitted event/review dates");
  const sourceBlock = renderer("renderEventWindowSource", "renderEventWindowCard");
  assert(sourceBlock.includes("safeHref"), "event-window sources must use safe source links");
  assert(!/new Date|Date\.now|setTimeout|setInterval|fetch\(|\.sort\(|\.filter\(|\.find\(|\.reduce\(|\.match\(/.test(windowBlock), "event-window renderer must not infer dates, schedule work, fetch, or transform emitted state");
  const alertBlock = renderer("renderCiMonitoringAlert", "renderThesisCard");
  assert(alertBlock.includes("safeHref") && alertBlock.includes("source.source_url"), "monitoring alert renderer must use safe source links");
  assert(!/filter\(|find\(|reduce\(|match\(/.test(block), "monitoring renderer must not infer, filter, or match backend monitoring state");
  assert(block.includes('monitoring.alert_count ?? "unknown"'), "monitoring renderer must display the emitted alert count or unknown");
  assert(Array.isArray(STATE.pilot_symbols) && STATE.pilot_symbols.join(",") === symbols.join(","), "monitoring state/slice pilot order mismatch");
  for (const row of rows) {
    const monitor = row.monitoring;
    const expected = STATE.companies?.[row.symbol];
    assert(monitor && typeof monitor === "object" && !Array.isArray(monitor), `${row.symbol} missing emitted monitoring row`);
    assert(JSON.stringify(monitor) === JSON.stringify(expected), `${row.symbol} monitoring slice is stale`);
    assert(["healthy", "degraded", "stale", "unknown"].includes(monitor.status), `${row.symbol} invalid emitted monitoring status`);
    assert(Number.isInteger(monitor.alert_count) && monitor.alert_count >= 0, `${row.symbol} alert count is invalid`);
    assert(Array.isArray(monitor.alerts) && monitor.alerts.length === monitor.alert_count, `${row.symbol} alert array/count mismatch`);
    for (const alert of monitor.alerts) {
      assert(/^https?:\/\//i.test(String(alert?.source?.source_url || "")), `${row.symbol} monitoring alert lacks an http(s) source`);
      assert(typeof alert.alert_id === "string" && alert.alert_id.length > 0, `${row.symbol} monitoring alert lacks an ID`);
    }
  }
  console.log(`ci_monitoring_ui: PASS (${checks} UI/data assertions, ${symbols.length} company rows)`);
} catch (error) {
  console.error(`ci_monitoring_ui: FAIL - ${error.message}`);
  process.exitCode = 1;
}
