-- Henneth AI — push_subscriptions
-- Per-user Web Push endpoints. Same ownership model as `profiles` (OPERATIONS.md §6):
-- per-user, row-level-secured, reachable by the client publishable key ONLY for the
-- signed-in user's own rows. Never holds research data.
--
-- NOT APPLIED. Run this by hand in the Supabase SQL editor when activating Web Push
-- (OPERATIONS.md §11). Until then the table does not exist and nothing references it.

create table if not exists public.push_subscriptions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  endpoint    text not null unique,          -- the push service URL; identifies one browser
  p256dh      text,                          -- client public key (payload encryption)
  auth        text,                          -- client auth secret (payload encryption)
  user_agent  text,                          -- so a user can tell their devices apart
  created_at  timestamptz not null default now(),
  last_sent   timestamptz,
  fail_count  int not null default 0         -- sender bumps this; 404/410 deletes the row
);

create index if not exists push_subscriptions_user_id_idx
  on public.push_subscriptions (user_id);

alter table public.push_subscriptions enable row level security;

-- Four explicit policies, all scoped to the owner. No policy grants cross-user visibility;
-- there is deliberately no "read all" path for the client key. The sender reads every row,
-- but it authenticates with the service-role key, which bypasses RLS server-side only.
drop policy if exists "own subs: select" on public.push_subscriptions;
create policy "own subs: select" on public.push_subscriptions
  for select using (auth.uid() = user_id);

drop policy if exists "own subs: insert" on public.push_subscriptions;
create policy "own subs: insert" on public.push_subscriptions
  for insert with check (auth.uid() = user_id);

drop policy if exists "own subs: update" on public.push_subscriptions;
create policy "own subs: update" on public.push_subscriptions
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own subs: delete" on public.push_subscriptions;
create policy "own subs: delete" on public.push_subscriptions
  for delete using (auth.uid() = user_id);

-- The client upserts on `endpoint` (push.js), so re-subscribing the same browser updates
-- one row rather than accumulating dead endpoints. `on delete cascade` means deleting an
-- account takes its push endpoints with it.
