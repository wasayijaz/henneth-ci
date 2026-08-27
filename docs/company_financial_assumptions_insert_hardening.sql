-- Manual hardening for private owner financial-assumption drafts.
-- Applied only to the dedicated Henneth CI project `wexonytulckejkynncvv` as
-- migration `harden_owner_financial_assumption_drafts` on 2026-08-27.
-- Retain this reviewable contract; it is not an instruction to alter the legacy desk project.
-- Scope: keep authenticated browser inserts as inert drafts. Server-side approval appends a
-- separate approved copy through the private backend credential, which bypasses RLS.

begin;

drop policy if exists company_financial_assumptions_insert_own
  on public.company_financial_assumptions;

create policy company_financial_assumptions_insert_own
  on public.company_financial_assumptions
  for insert
  to authenticated
  with check (
    user_id = (select auth.uid())
    and approved is false
    and approved_at is null
  );

commit;
