#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { buildAnswerSections, projectCompany } from "../Henneth Desk 2.CI.0/api/ask_contract.js";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const SLICE_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "data", "company_intelligence.json");
const APP_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "app.js");
const CSS_PATH = path.join(ROOT, "Henneth Desk 2.CI.0", "styles.css");
let checks = 0;

function assert(condition, message) {
  checks += 1;
  if (!condition) throw new Error(message);
}

function loadJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function fixtureConfidence() {
  const components = Array.from({ length: 7 }, (_, index) => ({
    name: `component_${index + 1}`,
    normalized_score: 10 + index,
    weighted_points: 1.5 + index,
    rationale: `rationale ${index + 1}`,
  }));
  return {
    status: "available",
    assessment_count: 6,
    aggregate_score: 72.5,
    aggregate_band: "medium",
    assessments: Array.from({ length: 6 }, (_, index) => ({
      confidence_id: `conf_${index + 1}`,
      source_cluster_id: `cluster_${index + 1}`,
      score: 60 + index,
      band: index % 2 ? "medium" : "high",
      components,
      provenance_refs: [
        { source_url: "https://example.com/private.pdf", text: "raw evidence excerpt" },
        "doc_1:p1",
      ],
    })),
  };
}

function assertNoLeak(value, label) {
  const text = JSON.stringify(value).toLowerCase();
  for (const token of [
    "source_url",
    "https://",
    "raw evidence",
    "excerpt",
    "provenance_refs",
    "current_price",
    "forecast",
    "advice",
    "recommend",
    "buy",
    "sell",
  ]) {
    assert(!text.includes(token), `${label} leaked ${token}`);
  }
}

function main() {
  const data = loadJson(SLICE_PATH);
  assert(Array.isArray(data.tickers), "CI slice tickers missing");
  assert(data.tickers.length === 20, "CI slice must have exact 20 rows");

  const app = fs.readFileSync(APP_PATH, "utf8");
  const css = fs.readFileSync(CSS_PATH, "utf8");
  for (const token of [
    "renderIntelligenceConfidence",
    "intelligence_confidence",
    "confidenceComponentRows",
    "provenance reference",
  ]) {
    assert(app.includes(token), `app missing ${token}`);
  }
  for (const token of [".confidence-panel", ".confidence-summary", ".confidence-components"]) {
    assert(css.includes(token), `css missing ${token}`);
  }

  const row = clone(data.tickers[0]);
  row.intelligence_confidence = fixtureConfidence();
  const context = projectCompany(row, { symbol: row.symbol });
  assert(context.intelligence_confidence.assessments.length === 4, "Ask context assessment cap");
  assert(context.intelligence_confidence.assessment_count === 6, "Ask context preserves source count");
  for (const assessment of context.intelligence_confidence.assessments) {
    assert(assessment.components.length === 7, "Ask context component count");
    for (const component of assessment.components) {
      assert(Object.keys(component).sort().join(",") === "name,normalized_score,weighted_points", "component leaked fields");
    }
    assertNoLeak(assessment, "projected assessment");
  }

  const answer = buildAnswerSections(context, {});
  const confidence = answer.sections.confidence;
  assert(confidence.assessments.length === 4, "answer assessment cap");
  assert(confidence.aggregate_score === 72.5, "answer aggregate score");
  assert(confidence.aggregate_band === "medium", "answer aggregate band");
  assertNoLeak(confidence, "answer confidence");

  console.log(`intelligence_confidence_ui: PASS (${checks} assertions)`);
}

main();
