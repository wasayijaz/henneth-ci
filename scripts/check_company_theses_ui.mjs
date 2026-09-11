#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const APP_PATH = path.join(ROOT, "ci-app", "app.js");
const CSS_PATH = path.join(ROOT, "ci-app", "styles.css");
const SLICE_PATH = path.join(ROOT, "ci-app", "data", "company_intelligence.json");

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

  assert(symbols.length === 20 && new Set(symbols).size === 20, "company slice must contain exactly 20 unique pilot rows");
  assert(app.includes("company_theses"), "company_theses table is referenced by the UI");
  assert(app.includes("THESIS_COLUMNS"), "company thesis REST select list is explicit");

  assert(app.includes("fetch(`${SB_URL}/rest/v1/company_theses${path}`"), "thesis CRUD uses Supabase REST v1");
  assert(app.includes("apikey: SB_KEY"), "REST helper sends the existing publishable key");
  assert(app.includes("Authorization: `Bearer ${token}`"), "REST helper sends the signed-in bearer token");
  assert(/res\.status === 401[\s\S]*?refreshSession\(\)[\s\S]*?companyThesisRequest\(path, options, true\)/.test(app), "REST helper refreshes once on 401");
  assert(!/service_role|SUPABASE_SERVICE|process\.env|CI_OWNER_USER_ID|GROQ_API_KEY|(?:^|[^a-z])sk-[A-Za-z0-9]{10,}/i.test(app), "UI must not contain backend secrets or owner env values");

  assert(app.includes("schema_unavailable"), "schema-unavailable state is explicit");
  assert(app.includes("Private thesis storage is not activated yet"), "schema-unavailable copy is user-visible");
  assert(app.includes("network_unavailable") && app.includes("request_failed"), "network and generic request error states exist");
  assert(app.includes('payload?.code === "PGRST205"'), "schema detection names the missing-table schema-cache code");
  assert(!/PGRST\|schema cache/.test(app), "schema detection must not classify every PGRST error as schema unavailable");
  assert(!/payload\.(?:message|details|hint)/.test(app.replace(/function thesisErrorCode[\s\S]*?\n\}/, "")), "raw backend error fields are not rendered outside classifier");
  assert(app.includes("private_thesis_storage"), "secret-free private thesis storage receipt summary is rendered from the CI slice");
  assert(app.includes("Live completion is not verified. Cross-user RLS proof is still required before this storage is complete."), "UI keeps the cross-user RLS completion boundary visible");
  assert(app.includes("Owner-session read check"), "UI exposes owner-session smoke check state");
  assert(app.includes("Check live storage"), "UI exposes a manual live storage check button");
  assert(app.includes("Read check passed") && app.includes("company_theses was reachable with this bearer token"), "smoke check success copy is scoped to the current bearer token");

  assert(app.includes('method: "GET"') || app.includes("options.method || \"GET\""), "GET path exists");
  assert(app.includes('method: "POST"'), "create path exists");
  assert(app.includes('method: "PATCH"'), "edit/archive path exists");
  assert(app.includes('method: "DELETE"'), "hard delete path exists");
  const smokeBlock = app.slice(app.indexOf("async function runPrivateThesisSmokeCheck"), app.indexOf("function renderPrivateTheses"));
  assert(smokeBlock.includes('method: "GET"'), "live storage smoke check must be read-only GET");
  assert(smokeBlock.includes("id,symbol,updated_at") && smokeBlock.includes("limit=1"), "live storage smoke check must use a bounded non-sensitive select");
  assert(!/method:\s*"(POST|PATCH|DELETE)"/.test(smokeBlock), "live storage smoke check must not mutate rows");
  assert(!/cross-user RLS proof is (?:confirmed|proven|verified)/i.test(smokeBlock), "owner-session smoke check must not claim cross-user isolation");
  assert(app.includes("setPrivateThesisArchived(id, true)"), "archive is a normal reversible action");
  assert(app.includes("setPrivateThesisArchived(id, false)"), "restore path exists");
  assert(/window\.confirm\("Permanently delete this private thesis\? This cannot be undone\."\)/.test(app), "hard delete requires explicit confirmation");

  assert(app.includes('state.view === "thesis" ? renderThesisMonitor(r)'), "private thesis UI stays in the Thesis tab");
  assert(app.includes("Private thesis notebook"), "private thesis notebook renders");
  assert(app.includes("deterministic thesis monitoring below"), "private theses are separated from deterministic monitoring");
  assert(app.includes("They do not change Henneth's deterministic thesis monitoring below."), "UI preserves deterministic monitoring boundary");
  assert(app.includes("currentPilotSymbols().has(payload.symbol)"), "saves are limited to the exact pilot symbols loaded in the CI slice");
  assert(app.includes("Private user fair value"), "private fair-value input is labelled");
  assert((app.match(/Private user input, never Henneth output/g) || []).length >= 2, "fair value display states private user input and never Henneth output");
  assert(app.includes("never Henneth output, a target price, or advice"), "private fair value is explicitly not a target price or advice");

  assert(app.includes("THESIS_LIMITS = { thesis: 5000, expected: 2000, basis: 1000, fairValueMax: 1000000, listItems: 50, listItem: 500 }"), "JS limits mirror the company_theses table contract");
  assert(/id="privateThesisText"[^>]+maxlength="5000"/.test(app), "thesis text has a 5000 char limit");
  assert(/id="privateThesisEarnings"[^>]+maxlength="2000"/.test(app), "expected earnings path has a 2000 char limit");
  assert(/id="privateThesisFairValue"[^>]+min="0\.01"[^>]+max="1000000"/.test(app), "fair value is constrained above 0 and at or below 1,000,000");
  assert(/id="privateThesisFairValueBasis"[^>]+maxlength="1000"/.test(app), "fair-value basis has a 1000 char limit");
  assert((app.match(/data-list-limit="50" data-line-limit="500"/g) || []).length === 4, "all four list fields expose 50 item / 500 char line limits");
  assert(app.includes("listLimitError(items)") && app.includes("THESIS_LIMITS.listItems") && app.includes("THESIS_LIMITS.listItem"), "list limits are enforced before save");
  const saveBlock = app.slice(app.indexOf("async function savePrivateThesis"), app.indexOf("async function setPrivateThesisArchived"));
  assert(saveBlock.includes("state.theses.drafts[symbol] = payloadToDraft(payload, draft.id)") && saveBlock.indexOf("state.theses.drafts[symbol] = payloadToDraft(payload, draft.id)") < saveBlock.indexOf("await companyThesisRequest"), "draft is preserved before the network save");

  assert(css.includes(".private-thesis") && css.includes(".private-thesis-form") && css.includes(".private-thesis-card"), "private thesis styles exist");
  assert(css.includes(".private-thesis-verification"), "private thesis live verification styles exist");
  assert(/@media \(max-width:900px\)[\s\S]*?\.private-thesis-form/.test(css), "private thesis UI has a mobile layout");

  console.log(`company_theses_ui: PASS (${checks} UI/security assertions, ${symbols.length} company rows)`);
}

try { main(); } catch (error) {
  console.error(`company_theses_ui: FAIL - ${error.message}`);
  process.exitCode = 1;
}
