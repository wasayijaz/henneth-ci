#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const APP_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "app.js");
const CSS_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "styles.css");
const SLICE_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "data", "company_intelligence.json");
let checks = 0;

function assert(condition, message) {
  checks += 1;
  if (!condition) throw new Error(message);
}

function requireObject(value, label) {
  assert(value && typeof value === "object" && !Array.isArray(value), `${label} must be an object`);
}

function requireArray(value, label) {
  assert(Array.isArray(value), `${label} must be an array`);
}

function requireString(value, label) {
  assert(typeof value === "string" && value.length > 0, `${label} must be a non-empty string`);
}

function requireNumber(value, label) {
  assert(typeof value === "number" && Number.isFinite(value), `${label} must be a finite number`);
}

function rendererBlock(app) {
  const start = app.indexOf("function renderConditionalBenchmarks");
  const end = app.indexOf("function causalPolicyStatus", start);
  assert(start >= 0 && end > start, "conditional renderer block must exist before causal renderer");
  return app.slice(start, end);
}

function helperBlock(app) {
  const start = app.indexOf("function conditionalText");
  const end = app.indexOf("function causalPolicyStatus", start);
  assert(start >= 0 && end > start, "conditional helper block must exist before causal renderer");
  return app.slice(start, end);
}

function candidateId(candidate) {
  return candidate.candidate_id || candidate.event_id || candidate.id;
}

function assertCandidate(candidate, label) {
  requireObject(candidate, label);
  requireString(candidateId(candidate), `${label}: candidate/event id`);
  requireString(candidate.symbol, `${label}: symbol`);
  requireString(candidate.effective_date || candidate.event_date || candidate.date, `${label}: date`);
  requireString(candidate.classification || candidate.event_class || candidate.event_type, `${label}: class`);
}

function assertAggregate(row, label) {
  requireObject(row, label);
  assert(Number.isInteger(row.n) && row.n >= 0, `${label}: n must be a non-negative integer`);
  requireString(row.status, `${label}: status`);
  assert(row.reason === null || typeof row.reason === "string", `${label}: reason must be null or string`);
  if (row.n < 3) {
    assert(!row.stats || Object.values(row.stats).every(value => value === null), `${label}: stats must be suppressed when n < 3`);
  } else {
    requireObject(row.stats, `${label}: stats`);
    for (const [key, value] of Object.entries(row.stats)) {
      requireNumber(value, `${label}: stats.${key}`);
    }
  }
}

function assertBlockedStates(blocked, label) {
  requireObject(blocked, label);
  for (const key of ["peer", "international", "financial", "causal"]) {
    const row = blocked[key];
    requireObject(row, `${label}.${key}`);
    assert(row.status === "blocked", `${label}.${key}: status must be blocked`);
    requireString(row.reason, `${label}.${key}: reason`);
  }
}

try {
  const app = fs.readFileSync(APP_PATH, "utf8");
  const css = fs.readFileSync(CSS_PATH, "utf8");
  const slice = JSON.parse(fs.readFileSync(SLICE_PATH, "utf8"));
  const rows = Array.isArray(slice.tickers) ? slice.tickers : [];
  const symbols = rows.map(row => row?.symbol).filter(Boolean);
  assert(symbols.length === 20 && new Set(symbols).size === 20, "CI slice must contain exactly 20 unique pilot companies");

  assert(app.includes('state.view === "conditional" ? renderConditionalBenchmarks(r)'), "conditional tab dispatch is missing");
  assert(app.includes('["conditional", `Conditional benchmarks ${r.conditional_benchmarks?.benchmarks?.length || 0}`]'), "conditional tab label is missing");
  for (const token of [
    "function conditionalText",
    "function renderConditionalCandidates",
    "function renderConditionalHorizons",
    "function renderConditionalBlockedStates",
    "function renderConditionalBenchmarks",
  ]) {
    assert(app.includes(token), `app missing ${token}`);
  }

  const block = rendererBlock(app);
  const helpers = helperBlock(app);
  for (const token of [
    "r.conditional_benchmarks",
    "conditional_benchmarks",
    "benchmarks",
    "target_event",
    "matching_policy",
    "same_company_exact",
    "same_sector_exact",
    "horizon_aggregates",
    "blocked_states",
    "peer",
    "international",
    "financial",
    "causal",
    "descriptive",
    "does not match events, calculate benchmarks, infer causality, forecast, value the company, or provide advice",
  ]) {
    assert(block.includes(token) || helpers.includes(token), `conditional renderer missing ${token}`);
  }
  assert(!block.includes("r.event_studies"), "conditional renderer must not derive from event_studies");
  assert(!block.includes("r.operating_events"), "conditional renderer must not derive from operating_events");
  assert(!block.includes("r.causal_foundations"), "conditional renderer must not derive from causal_foundations");
  assert(!/\b(Math|parseFloat|parseInt|reduce\s*\([^)]*mean|filter\s*\([^)]*same_sector|filter\s*\([^)]*same_company)\b/.test(block), "conditional renderer must not calculate or match benchmark sets");
  assert(!/\b(price|shares|entry|stop|target_price)\b\s*[+\-*/=]/i.test(block), "conditional renderer must not calculate trading or valuation values");

  for (const token of [
    ".conditional-shell",
    ".conditional-summary",
    ".conditional-card",
    ".conditional-candidate-grid",
    ".conditional-horizons",
    ".conditional-blocked",
    ".conditional-policy",
    "@media (max-width:900px)",
    "@media (max-width:560px)",
  ]) {
    assert(css.includes(token), `css missing ${token}`);
  }

  let benchmarkCount = 0;
  let suppressedAggregates = 0;
  let statsAggregates = 0;
  for (const row of rows) {
    const conditional = row.conditional_benchmarks;
    requireObject(conditional, `${row.symbol}: conditional_benchmarks`);
    assert(conditional.symbol === row.symbol, `${row.symbol}: conditional symbol mismatch`);
    requireString(conditional.status, `${row.symbol}: status`);
    requireArray(conditional.benchmarks, `${row.symbol}: benchmarks`);
    requireObject(conditional.policy, `${row.symbol}: policy`);
    requireArray(conditional.limitations, `${row.symbol}: limitations`);
    assertBlockedStates(conditional.blocked_states, `${row.symbol}: blocked_states`);

    for (const benchmark of conditional.benchmarks) {
      benchmarkCount += 1;
      requireObject(benchmark, `${row.symbol}: benchmark`);
      requireString(benchmark.benchmark_id, `${row.symbol}: benchmark_id`);
      requireString(benchmark.status, `${row.symbol}: benchmark status`);
      requireObject(benchmark.target_event, `${row.symbol}: target_event`);
      requireString(benchmark.target_event.event_id, `${row.symbol}: target event_id`);
      requireString(benchmark.target_event.effective_date, `${row.symbol}: target effective_date`);
      requireString(benchmark.target_event.event_class || benchmark.target_event.event_type, `${row.symbol}: target event class`);
      requireObject(benchmark.context, `${row.symbol}: context`);
      requireArray(benchmark.context.conditions, `${row.symbol}: context conditions`);
      requireObject(benchmark.matching_policy, `${row.symbol}: matching_policy`);
      requireObject(benchmark.candidates, `${row.symbol}: candidates`);
      requireArray(benchmark.candidates.same_company_exact, `${row.symbol}: same_company_exact`);
      requireArray(benchmark.candidates.same_sector_exact, `${row.symbol}: same_sector_exact`);
      for (const candidate of benchmark.candidates.same_company_exact) assertCandidate(candidate, `${row.symbol}: same_company_exact candidate`);
      for (const candidate of benchmark.candidates.same_sector_exact) assertCandidate(candidate, `${row.symbol}: same_sector_exact candidate`);
      requireObject(benchmark.horizon_aggregates, `${row.symbol}: horizon_aggregates`);
      assert(Object.keys(benchmark.horizon_aggregates).length > 0, `${row.symbol}: at least one horizon aggregate required`);
      for (const [horizon, aggregate] of Object.entries(benchmark.horizon_aggregates)) {
        assertAggregate(aggregate, `${row.symbol}:${benchmark.benchmark_id}:${horizon}`);
        if (aggregate.n < 3) suppressedAggregates += 1;
        else statsAggregates += 1;
      }
      assertBlockedStates(benchmark.blocked_states, `${row.symbol}: benchmark blocked_states`);
      const text = JSON.stringify(benchmark).toLowerCase();
      for (const phrase of ["you should buy", "you should sell", "caused by", "will lead to"]) {
        assert(!text.includes(phrase), `${row.symbol}: benchmark contains forbidden causal/advice phrase ${phrase}`);
      }
    }
  }

  assert(benchmarkCount === 16, `conditional benchmark count must be exactly 16, got ${benchmarkCount}`);
  assert(suppressedAggregates > 0, "current slice must include suppressed aggregates");
  console.log(`conditional_benchmarks_ui: PASS (${checks} assertions, ${symbols.length} company rows, ${benchmarkCount} benchmarks, ${suppressedAggregates} suppressed aggregates, ${statsAggregates} stats aggregates)`);
} catch (error) {
  console.error(`conditional_benchmarks_ui: FAIL - ${error.message}`);
  process.exitCode = 1;
}
