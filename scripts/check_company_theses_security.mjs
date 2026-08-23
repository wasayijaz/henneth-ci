import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sqlPath = path.join(repoRoot, "docs", "company_theses.sql");
const sql = fs.readFileSync(sqlPath, "utf8");
const normalized = sql.replace(/\s+/g, " ").trim();
const lower = normalized.toLowerCase();

const expectedSymbols = [
  "MLCF",
  "OGDC",
  "DGKC",
  "PPL",
  "UBL",
  "PSO",
  "NBP",
  "LUCK",
  "FFC",
  "BOP",
  "HUBC",
  "MEBL",
  "HBL",
  "ATRL",
  "ENGROH",
  "MARI",
  "FCCL",
  "NRL",
  "GAL",
  "PRL",
];

const failures = [];

function check(condition, message) {
  if (!condition) failures.push(message);
}

function has(pattern) {
  return pattern.test(normalized);
}

function hasLower(pattern) {
  return pattern.test(lower);
}

check(/not applied/i.test(sql), "SQL must explicitly state it is NOT APPLIED.");
check(
  hasLower(/create or replace function public\.company_theses_jsonb_string_array_is_bounded\( value jsonb, max_items integer, max_chars integer \) returns boolean language sql immutable as \$\$/),
  "Missing immutable SQL helper for bounded JSON string arrays.",
);
check(hasLower(/jsonb_typeof\(value\) = 'array'/), "JSON helper must require array values.");
check(hasLower(/jsonb_array_length\(value\) <= max_items/), "JSON helper must bound array length.");
check(hasLower(/from jsonb_array_elements\(value\) as item\(json_value\)/), "JSON helper must inspect raw JSONB elements.");
check(hasLower(/jsonb_typeof\(item\.json_value\) <> 'string'/), "JSON helper must reject non-string elements.");
check(hasLower(/nullif\(btrim\(item\.json_value #>> '\{\}'\), ''\) is null/), "JSON helper must reject blank decoded string elements.");
check(hasLower(/length\(item\.json_value #>> '\{\}'\) > max_chars/), "JSON helper must bound decoded string element length.");
check(hasLower(/\(item\.json_value #>> '\{\}'\) ~ '\[\[:cntrl:\]\]'/), "JSON helper must reject decoded control characters.");
check(
  hasLower(/revoke execute on function public\.company_theses_jsonb_string_array_is_bounded\(jsonb, integer, integer\) from public/),
  "Helper EXECUTE must be revoked from PUBLIC.",
);
check(
  hasLower(/revoke execute on function public\.company_theses_jsonb_string_array_is_bounded\(jsonb, integer, integer\) from anon/),
  "Helper EXECUTE must be revoked from anon.",
);
check(
  hasLower(/grant execute on function public\.company_theses_jsonb_string_array_is_bounded\(jsonb, integer, integer\) to authenticated/),
  "Helper EXECUTE must be granted only to authenticated.",
);
check(hasLower(/create table if not exists public\.company_theses \(/), "Missing public.company_theses table.");
check(hasLower(/\bid uuid primary key default gen_random_uuid\(\)/), "Missing uuid id default gen_random_uuid primary key.");
check(
  hasLower(/\buser_id uuid not null default auth\.uid\(\) references auth\.users\(id\) on delete cascade/),
  "Missing owner user_id default auth.uid() auth.users cascade contract.",
);
check(hasLower(/\bsymbol text not null\b/), "Missing required symbol column.");
check(hasLower(/\bthesis text not null\b/), "Missing required thesis column.");
check(hasLower(/\bexpected_earnings_path text\b/), "Missing optional expected earnings path.");

for (const column of ["catalysts", "risks", "required_evidence", "kill_conditions"]) {
  check(
    hasLower(new RegExp(`\\b${column} jsonb not null default '\\[\\]'::jsonb`)),
    `Missing ${column} jsonb default empty array.`,
  );
}

check(hasLower(/\buser_fair_value_assumption numeric\b/), "Missing private user fair-value assumption.");
check(hasLower(/\buser_fair_value_basis text\b/), "Missing private user fair-value basis.");
check(/user-supplied/i.test(sql), "Fair-value assumption/basis must be explicitly user-supplied.");

const statusMatch = normalized.match(/status in \(([^)]+)\)/i);
check(Boolean(statusMatch), "Missing status check constraint.");
if (statusMatch) {
  const statuses = [...statusMatch[1].matchAll(/'([^']+)'/g)].map((m) => m[1]);
  check(
    JSON.stringify(statuses) === JSON.stringify(["Strengthening", "Stable", "Weakening", "Broken"]),
    `Status registry mismatch: ${statuses.join(", ")}`,
  );
}

check(hasLower(/\barchived boolean not null default false\b/), "Missing archived boolean default false.");
check(hasLower(/\bcreated_at timestamptz not null default timezone\('utc', now\(\)\)/), "Missing created_at UTC default.");
check(hasLower(/\bupdated_at timestamptz not null default timezone\('utc', now\(\)\)/), "Missing updated_at UTC default.");
check(hasLower(/create index if not exists company_theses_user_id_idx on public\.company_theses \(user_id\)/), "Missing user_id index.");
check(
  hasLower(/create index if not exists company_theses_user_id_symbol_idx on public\.company_theses \(user_id, symbol\)/),
  "Missing user_id + symbol index.",
);

check(
  hasLower(/company_theses_symbol_pilot_check check \( symbol ~ '\^\[a-z0-9\]\{2,12\}\$' and symbol in/),
  "Symbol check must require safe uppercase alphanumeric text before exact pilot match.",
);

const symbolCheckMatch = normalized.match(/company_theses_symbol_pilot_check check \( symbol ~ '\^\[A-Z0-9\]\{2,12\}\$' and symbol in \(([^)]+)\) \)/i);
check(Boolean(symbolCheckMatch), "Missing exact pilot symbol check constraint.");
if (symbolCheckMatch) {
  const symbols = [...symbolCheckMatch[1].matchAll(/'([^']+)'/g)].map((m) => m[1]);
  check(symbols.length === 20, `Expected 20 pilot symbols, found ${symbols.length}.`);
  check(
    JSON.stringify(symbols) === JSON.stringify(expectedSymbols),
    `Pilot symbol registry mismatch: ${symbols.join(", ")}`,
  );
}

check(
  hasLower(/company_theses_thesis_text_check check \( nullif\(btrim\(thesis\), ''\) is not null and length\(thesis\) <= 5000 and thesis !~ '\[\[:cntrl:\]\]' \)/),
  "Thesis text must be nonblank, bounded to 5000 chars, and reject control characters.",
);
check(
  hasLower(/company_theses_expected_earnings_path_check check \( expected_earnings_path is null or \( nullif\(btrim\(expected_earnings_path\), ''\) is not null and length\(expected_earnings_path\) <= 2000 and expected_earnings_path !~ '\[\[:cntrl:\]\]' \) \)/),
  "Expected earnings path must be optional but nonblank, bounded, and control-character-safe when present.",
);
check(
  hasLower(/company_theses_json_arrays_check check \( public\.company_theses_jsonb_string_array_is_bounded\(catalysts, 50, 500\) and public\.company_theses_jsonb_string_array_is_bounded\(risks, 50, 500\) and public\.company_theses_jsonb_string_array_is_bounded\(required_evidence, 50, 500\) and public\.company_theses_jsonb_string_array_is_bounded\(kill_conditions, 50, 500\) \)/),
  "JSON arrays must be bounded arrays of bounded nonblank strings.",
);
check(
  hasLower(/company_theses_user_fair_value_assumption_check check \( user_fair_value_assumption is null or \( user_fair_value_assumption > 0 and user_fair_value_assumption <= 1000000 \) \)/),
  "Fair-value assumption must be optional, positive, and bounded.",
);
check(
  hasLower(/company_theses_user_fair_value_basis_text_check check \( user_fair_value_basis is null or \( nullif\(btrim\(user_fair_value_basis\), ''\) is not null and length\(user_fair_value_basis\) <= 1000 and user_fair_value_basis !~ '\[\[:cntrl:\]\]' \) \)/),
  "Fair-value basis must be optional but nonblank, bounded, and control-character-safe when present.",
);
check(
  hasLower(/company_theses_user_fair_value_basis_check check \( user_fair_value_assumption is null or nullif\(btrim\(user_fair_value_basis\), ''\) is not null \)/),
  "Fair-value assumption must require a user-supplied basis.",
);

check(hasLower(/alter table public\.company_theses enable row level security/), "RLS is not enabled.");
check(hasLower(/revoke all on table public\.company_theses from public, anon/), "Missing explicit PUBLIC revoke.");
check(
  hasLower(/grant select, insert, update, delete on table public\.company_theses to authenticated/),
  "Missing authenticated CRUD grant.",
);
check(!hasLower(/\bgrant\b[^;]*\banon\b/), "Anon must not receive a grant.");
check(!hasLower(/\bservice_role\b/), "SQL must not mention service_role.");
check(!hasLower(/\bsecurity\s+definer\b/), "SQL must not use SECURITY DEFINER.");
check(!hasLower(/\buser_metadata\b/), "SQL must not reference user_metadata.");

const policyChecks = [
  ["company_theses_select_own", /create policy company_theses_select_own on public\.company_theses for select to authenticated using \(user_id = \(select auth\.uid\(\)\)\)/],
  ["company_theses_insert_own", /create policy company_theses_insert_own on public\.company_theses for insert to authenticated with check \(user_id = \(select auth\.uid\(\)\)\)/],
  ["company_theses_update_own", /create policy company_theses_update_own on public\.company_theses for update to authenticated using \(user_id = \(select auth\.uid\(\)\)\) with check \(user_id = \(select auth\.uid\(\)\)\)/],
  ["company_theses_delete_own", /create policy company_theses_delete_own on public\.company_theses for delete to authenticated using \(user_id = \(select auth\.uid\(\)\)\)/],
];

for (const [name, pattern] of policyChecks) {
  check(hasLower(pattern), `Missing or unsafe policy: ${name}.`);
  check(
    hasLower(new RegExp(`drop policy if exists ${name} on public\\.company_theses`)),
    `Policy must be safely rerunnable with explicit drop: ${name}.`,
  );
}

const authUidUses = lower.match(/\(select auth\.uid\(\)\)/g) ?? [];
check(authUidUses.length >= 5, "Policies must use the (select auth.uid()) pattern.");

if (failures.length > 0) {
  console.error("company_theses security check failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("company_theses security check passed.");
