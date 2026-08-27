-- Manual hardening for private owner financial-assumption values.
-- Reference-only SQL: this file is NOT APPLIED by the desk. Apply manually only after review.
-- Scope: align the database draft contract with the executable formal-engine contract.
-- The formal engine cannot compute with non-positive net margin, so such drafts must remain
-- invalid before approval rather than entering state and failing later in preflight.

begin;

alter table public.company_financial_assumptions
  drop constraint if exists company_financial_assumptions_value_check;

alter table public.company_financial_assumptions
  add constraint company_financial_assumptions_value_check check (
    (metric = 'revenue_growth_pct' and value > -100 and value <= 500)
    or (metric = 'net_margin_pct' and value > 0 and value <= 100)
    or (metric = 'exit_pe' and value > 0 and value <= 200)
    or (metric = 'net_debt' and value >= -10000000000000 and value <= 10000000000000)
  );

commit;
