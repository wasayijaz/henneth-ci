-- Private company thesis storage contract.
-- Reference-only SQL: this file is NOT APPLIED by the desk. Apply manually only after review.
-- Scope: authenticated owner-only notes for the exact 20-company PSX pilot.
-- Activation receipt: this contract was applied to the dedicated Henneth CI project
-- (ref `wexonytulckejkynncvv`) as migration `activate_private_company_theses` on
-- 2026-08-27. The legacy desk project remains unchanged; retain this repeatable
-- contract and the NOT APPLIED wording above for its separate activation path.

create or replace function public.company_theses_jsonb_string_array_is_bounded(
  value jsonb,
  max_items integer,
  max_chars integer
)
returns boolean
language sql
immutable
as $$
  select
    jsonb_typeof(value) = 'array'
    and jsonb_array_length(value) <= max_items
    and not exists (
      select 1
      from jsonb_array_elements(value) as item(json_value)
      where
        jsonb_typeof(item.json_value) <> 'string'
        or nullif(btrim(item.json_value #>> '{}'), '') is null
        or length(item.json_value #>> '{}') > max_chars
        or (item.json_value #>> '{}') ~ '[[:cntrl:]]'
    )
$$;

revoke execute on function public.company_theses_jsonb_string_array_is_bounded(jsonb, integer, integer) from public;
revoke execute on function public.company_theses_jsonb_string_array_is_bounded(jsonb, integer, integer) from anon;
grant execute on function public.company_theses_jsonb_string_array_is_bounded(jsonb, integer, integer) to authenticated;

create table if not exists public.company_theses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  symbol text not null,
  thesis text not null,
  expected_earnings_path text,
  catalysts jsonb not null default '[]'::jsonb,
  risks jsonb not null default '[]'::jsonb,
  required_evidence jsonb not null default '[]'::jsonb,
  kill_conditions jsonb not null default '[]'::jsonb,
  user_fair_value_assumption numeric,
  user_fair_value_basis text,
  status text not null default 'Stable',
  archived boolean not null default false,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint company_theses_symbol_pilot_check check (
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
  constraint company_theses_status_check check (
    status in ('Strengthening', 'Stable', 'Weakening', 'Broken')
  ),
  constraint company_theses_thesis_text_check check (
    nullif(btrim(thesis), '') is not null
    and length(thesis) <= 5000
    and thesis !~ '[[:cntrl:]]'
  ),
  constraint company_theses_expected_earnings_path_check check (
    expected_earnings_path is null
    or (
      nullif(btrim(expected_earnings_path), '') is not null
      and length(expected_earnings_path) <= 2000
      and expected_earnings_path !~ '[[:cntrl:]]'
    )
  ),
  constraint company_theses_json_arrays_check check (
    public.company_theses_jsonb_string_array_is_bounded(catalysts, 50, 500)
    and public.company_theses_jsonb_string_array_is_bounded(risks, 50, 500)
    and public.company_theses_jsonb_string_array_is_bounded(required_evidence, 50, 500)
    and public.company_theses_jsonb_string_array_is_bounded(kill_conditions, 50, 500)
  ),
  constraint company_theses_user_fair_value_assumption_check check (
    user_fair_value_assumption is null
    or (
      user_fair_value_assumption > 0
      and user_fair_value_assumption <= 1000000
    )
  ),
  constraint company_theses_user_fair_value_basis_text_check check (
    user_fair_value_basis is null
    or (
      nullif(btrim(user_fair_value_basis), '') is not null
      and length(user_fair_value_basis) <= 1000
      and user_fair_value_basis !~ '[[:cntrl:]]'
    )
  ),
  constraint company_theses_user_fair_value_basis_check check (
    user_fair_value_assumption is null or nullif(btrim(user_fair_value_basis), '') is not null
  )
);

comment on table public.company_theses is
  'Private authenticated-user thesis notes for the exact 20-company pilot. Reference-only SQL; not applied by the desk.';
comment on column public.company_theses.user_fair_value_assumption is
  'Private user-supplied fair-value assumption. Not desk data and not model output.';
comment on column public.company_theses.user_fair_value_basis is
  'Private user-supplied basis for the fair-value assumption. Required when an assumption is present.';

create index if not exists company_theses_user_id_idx
  on public.company_theses (user_id);

create index if not exists company_theses_user_id_symbol_idx
  on public.company_theses (user_id, symbol);

alter table public.company_theses enable row level security;

revoke all on table public.company_theses from public, anon;
grant select, insert, update, delete on table public.company_theses to authenticated;

drop policy if exists company_theses_select_own on public.company_theses;
create policy company_theses_select_own
  on public.company_theses
  for select
  to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists company_theses_insert_own on public.company_theses;
create policy company_theses_insert_own
  on public.company_theses
  for insert
  to authenticated
  with check (user_id = (select auth.uid()));

drop policy if exists company_theses_update_own on public.company_theses;
create policy company_theses_update_own
  on public.company_theses
  for update
  to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

drop policy if exists company_theses_delete_own on public.company_theses;
create policy company_theses_delete_own
  on public.company_theses
  for delete
  to authenticated
  using (user_id = (select auth.uid()));
