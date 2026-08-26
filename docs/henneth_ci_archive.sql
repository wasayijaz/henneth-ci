-- Henneth CI append-only archive contract.
-- Applied to dedicated Supabase project `wexonytulckejkynncvv` on 2026-08-27 as
-- migration `create_append_only_ci_archive`. This file is the reviewable source
-- contract; it contains no credentials and does not expose research to browsers.

create table if not exists public.ci_sync_runs (
  id uuid primary key default gen_random_uuid(),
  run_key text not null unique,
  producer text not null,
  started_at timestamptz not null,
  completed_at timestamptz,
  status text not null check (status in ('running', 'completed', 'failed', 'skipped')),
  payload_sha256 text not null check (payload_sha256 ~ '^[a-f0-9]{64}$'),
  counts jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.ci_source_documents (
  id uuid primary key default gen_random_uuid(),
  document_key text not null unique,
  symbol text not null,
  source_url text not null,
  source_system text not null,
  document_type text,
  title text,
  published_at timestamptz,
  available_at timestamptz,
  source_sha256 text not null check (source_sha256 ~ '^[a-f0-9]{64}$'),
  metadata jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create table if not exists public.ci_document_facts (
  id uuid primary key default gen_random_uuid(),
  fact_key text not null unique,
  document_key text not null references public.ci_source_documents(document_key),
  symbol text not null,
  fact_type text not null,
  fact_payload jsonb not null,
  available_at timestamptz,
  payload_sha256 text not null check (payload_sha256 ~ '^[a-f0-9]{64}$'),
  created_at timestamptz not null default now()
);

create table if not exists public.ci_state_snapshots (
  id uuid primary key default gen_random_uuid(),
  snapshot_key text not null unique,
  state_name text not null,
  symbol text,
  available_at timestamptz,
  payload jsonb not null,
  payload_sha256 text not null check (payload_sha256 ~ '^[a-f0-9]{64}$'),
  created_at timestamptz not null default now()
);

create table if not exists public.ci_document_blobs (
  id uuid primary key default gen_random_uuid(),
  document_key text not null unique references public.ci_source_documents(document_key),
  storage_path text not null unique,
  content_sha256 text not null check (content_sha256 ~ '^[a-f0-9]{64}$'),
  content_type text not null,
  byte_size bigint not null check (byte_size >= 0),
  created_at timestamptz not null default now()
);

create index if not exists ci_source_documents_symbol_available_idx
  on public.ci_source_documents (symbol, available_at desc);
create index if not exists ci_document_facts_symbol_type_idx
  on public.ci_document_facts (symbol, fact_type);
create index if not exists ci_state_snapshots_name_symbol_idx
  on public.ci_state_snapshots (state_name, symbol, available_at desc);

alter table public.ci_sync_runs enable row level security;
alter table public.ci_source_documents enable row level security;
alter table public.ci_document_facts enable row level security;
alter table public.ci_state_snapshots enable row level security;
alter table public.ci_document_blobs enable row level security;

revoke all on table public.ci_sync_runs, public.ci_source_documents,
  public.ci_document_facts, public.ci_state_snapshots, public.ci_document_blobs
  from public, anon, authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('ci-documents', 'ci-documents', false, 52428800, array['application/pdf'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
