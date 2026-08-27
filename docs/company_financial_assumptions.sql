-- Private owner-approved formal financial assumption contract.
-- Reference-only SQL: this file is NOT APPLIED by the desk. Apply manually only after review.
-- Scope: authenticated owner-only inputs for the exact 20-company PSX pilot.
-- The deterministic cloud build consumes only approved rows through the server-only importer.
-- Activation receipt: this contract was applied to the dedicated Henneth CI project
-- (ref `wexonytulckejkynncvv`) as migration `create_owner_financial_assumptions` on
-- 2026-08-27. It remains a repeatable review contract; never apply it to the legacy desk
-- project as part of the CI browser cutover.

create table if not exists public.company_financial_assumptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  symbol text not null,
  metric text not null,
  value numeric not null,
  unit text not null,
  available_on date not null default current_date,
  source_label text not null,
  source_url text,
  rationale text not null,
  approved boolean not null default false,
  approved_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  constraint company_financial_assumptions_symbol_pilot_check check (
    symbol ~ '^[A-Z0-9]{2,12}$'
    and
    symbol in (
      'MLCF',
      'OGDC',
      'DGKC',
      'PPL',
      'UBL',
      'PSO',
      'NBP',
      'LUCK',
      'FFC',
      'BOP',
      'HUBC',
      'MEBL',
      'HBL',
      'ATRL',
      'ENGROH',
      'MARI',
      'CNERGY',
      'NRL',
      'GAL',
      'PRL'
    )
  ),
  constraint company_financial_assumptions_metric_check check (
    metric in ('revenue_growth_pct', 'net_margin_pct', 'exit_pe', 'net_debt')
  ),
  constraint company_financial_assumptions_unit_check check (
    (metric in ('revenue_growth_pct', 'net_margin_pct') and unit = 'pct')
    or (metric = 'exit_pe' and unit = 'x')
    or (metric = 'net_debt' and unit = 'PKR')
  ),
  constraint company_financial_assumptions_value_check check (
    (metric = 'revenue_growth_pct' and value > -100 and value <= 500)
    or (metric = 'net_margin_pct' and value >= -100 and value <= 100)
    or (metric = 'exit_pe' and value > 0 and value <= 200)
    or (metric = 'net_debt' and value >= -10000000000000 and value <= 10000000000000)
  ),
  constraint company_financial_assumptions_source_label_check check (
    nullif(btrim(source_label), '') is not null
    and length(source_label) <= 500
    and source_label !~ '[[:cntrl:]]'
  ),
  constraint company_financial_assumptions_source_url_check check (
    source_url is null
    or (
      source_url ~ '^https://'
      and length(source_url) <= 2000
      and source_url !~ '[[:cntrl:]]'
    )
  ),
  constraint company_financial_assumptions_rationale_check check (
    nullif(btrim(rationale), '') is not null
    and length(rationale) <= 2000
    and rationale !~ '[[:cntrl:]]'
  ),
  constraint company_financial_assumptions_approval_check check (
    approved is false
    or approved_at is not null
  )
);

comment on table public.company_financial_assumptions is
  'Append-only private owner inputs for formal Henneth CI forecast, valuation, and market-expectations engines.';
comment on column public.company_financial_assumptions.value is
  'Owner-supplied assumption value. The deterministic build consumes only approved rows.';
comment on column public.company_financial_assumptions.approved is
  'Only approved=true rows are eligible for server-side import into financial_engine_assumptions.json.';

create index if not exists company_financial_assumptions_user_id_idx
  on public.company_financial_assumptions (user_id);

create index if not exists company_financial_assumptions_user_symbol_metric_idx
  on public.company_financial_assumptions (user_id, symbol, metric, approved_at desc, created_at desc);

alter table public.company_financial_assumptions enable row level security;

revoke all on table public.company_financial_assumptions from public, anon;
grant select, insert on table public.company_financial_assumptions to authenticated;

drop policy if exists company_financial_assumptions_select_own on public.company_financial_assumptions;
create policy company_financial_assumptions_select_own
  on public.company_financial_assumptions
  for select
  to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists company_financial_assumptions_insert_own on public.company_financial_assumptions;
create policy company_financial_assumptions_insert_own
  on public.company_financial_assumptions
  for insert
  to authenticated
  with check (user_id = (select auth.uid()));
