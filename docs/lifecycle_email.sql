-- Henneth — lifecycle email schema
-- Activation tracking + email send log. Same ownership model as `profiles`/`push_subscriptions`
-- (OPERATIONS.md §6): per-user, row-level-secured. `lifecycle_email_log` and `lifecycle_queue`
-- are service-role-only — the runner (scripts/lifecycle_email.py) authenticates with the
-- service key, which bypasses RLS server-side only. No policy here grants the client key
-- cross-user visibility or an email address.
--
-- NOT APPLIED. Run this by hand in the Supabase SQL editor when activating the lifecycle email
-- flow (docs/PRODUCT-ROADMAP.md §1/§1a; plan: onboarding rebuild + lifecycle email). Until then
-- these columns/tables do not exist and nothing references them.

-- ── profiles: activation + unsubscribe columns ─────────────────────────────────────────
alter table public.profiles
  add column if not exists activated_at    timestamptz,
  add column if not exists activation_type text,
  add column if not exists signup_at       timestamptz not null default now(),
  add column if not exists email_optout    boolean not null default false,
  add column if not exists unsub_token     uuid not null default gen_random_uuid();

-- `activated_at`/`activation_type`/`signup_at`/`unsub_token` are written ONCE, server-side only.
-- `saveProfile()` (app.js) is an open upsert on `profiles` — without this revoke, a signed-in
-- client could forge its own activation event. Ordinary profile fields (watchlist, digest_prefs,
-- quiz, onboarded, theme, lang, etc.) are untouched and remain client-writable.
revoke update (activated_at, activation_type, signup_at, unsub_token) on public.profiles from authenticated;

-- Write-once activation RPC. `coalesce` means the first call wins — a second activation type
-- (e.g. a later Desk Room lookup after an earlier watchlist add) never overwrites the first.
-- SECURITY DEFINER so it can write columns the client role above no longer can.
create or replace function public.mark_activated(p_type text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.profiles
     set activated_at    = coalesce(activated_at, now()),
         activation_type = coalesce(activation_type, p_type)
   where id = auth.uid();
end;
$$;

revoke all on function public.mark_activated(text) from public;
grant execute on function public.mark_activated(text) to authenticated;

-- Anonymous, token-scoped unsubscribe RPC — backs the ungated `/unsubscribe?t=<uuid>` route.
-- Returns a boolean only; never leaks whether a token exists via error text vs silent no-op.
-- p_scope: 'all' (sets email_optout) or a specific email_key (reserved for future per-type
-- opt-out; v1 only implements 'all').
create or replace function public.email_unsubscribe(p_token uuid, p_scope text default 'all')
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_found boolean;
begin
  update public.profiles
     set email_optout = true
   where unsub_token = p_token
  returning true into v_found;

  return coalesce(v_found, false);
end;
$$;

revoke all on function public.email_unsubscribe(uuid, text) from public;
grant execute on function public.email_unsubscribe(uuid, text) to anon, authenticated;

-- ── handle_new_user: seed a profiles row at signup ──────────────────────────────────────
-- Email confirmation is ON, so a `profiles` row may not exist yet when a user first appears
-- in `auth.users`. Without this trigger, activation/lifecycle columns above have nowhere to
-- default onto until the client's own first profile write — which the lifecycle runner cannot
-- wait on (it needs `signup_at` from the moment of signup, not first app open).
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, signup_at)
  values (new.id, now())
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ── lifecycle_email_log: idempotent send ledger ─────────────────────────────────────────
-- unique(user_id, email_key) is the ONLY idempotency guarantee under cron retry — a double-send
-- is structurally impossible because the second insert 409s before any Resend call is made.
-- A jsonb read-modify-write on `profiles` could not offer the same guarantee (two concurrent
-- cron runs could both read "not sent yet").
create table if not exists public.lifecycle_email_log (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users (id) on delete cascade,
  email_key  text not null,          -- 'welcome' | 'nudge_24h' | 'activated' | 'nudge_7d' | 'digest_2026-W31'
  resend_id  text,                   -- Resend's message id, once sent
  status     text not null default 'queued',  -- queued | sent | failed | bounced
  created_at timestamptz not null default now(),
  unique (user_id, email_key)
);

create index if not exists lifecycle_email_log_user_id_idx
  on public.lifecycle_email_log (user_id);

alter table public.lifecycle_email_log enable row level security;
-- Zero policies, deliberately. RLS on with no policy = no row is visible/writable to `anon` or
-- `authenticated`. Only the service-role key (bypasses RLS) — i.e. the runner — touches this table.

-- ── lifecycle_queue: service-role-only view exposing the email address ──────────────────
-- `profiles` never stores an email; the runner has no other way to reach a user for sending.
-- This view is the one place that join happens, and it is unreachable except via service key
-- (no grants to anon/authenticated below).
create or replace view public.lifecycle_queue
with (security_invoker = false) as
select
  p.id as user_id,
  u.email,
  p.signup_at,
  p.activated_at,
  p.activation_type,
  p.email_optout,
  p.unsub_token,
  p.digest_prefs
from public.profiles p
join auth.users u on u.id = p.id
where u.email is not null
  and u.email_confirmed_at is not null
  and p.email_optout = false;

revoke all on public.lifecycle_queue from public, anon, authenticated;
-- No grant statement for service_role: the service key bypasses grants/RLS entirely, same as
-- push_subscriptions' sender pattern.
