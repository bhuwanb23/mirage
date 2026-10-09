-- ============================================================
-- Mirage — Supabase schema (Phase 0)
-- Run this in: Supabase Dashboard → SQL Editor → New query → Run
-- Idempotent: safe to re-run.
-- ============================================================

-- Extensions ------------------------------------------------
create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

-- Enums -----------------------------------------------------
do $$ begin
  create type risk_level as enum ('low','medium','high','critical');
exception when duplicate_object then null; end $$;

do $$ begin
  create type input_type as enum ('text','audio','image','url');
exception when duplicate_object then null; end $$;

do $$ begin
  create type alert_level as enum ('safe','suspicious','warning','critical');
exception when duplicate_object then null; end $$;

-- 1. users --------------------------------------------------
create table if not exists public.users (
  id              uuid primary key default gen_random_uuid(),
  telegram_id     bigint unique,
  username        text,
  display_name    text,
  language        text not null default 'en',
  score_before    int  not null default 0,
  score_after     int  not null default 0,
  elder_mode      boolean not null default false,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- 2. drills -------------------------------------------------
create table if not exists public.drills (
  id                     uuid primary key default gen_random_uuid(),
  user_id                uuid references public.users(id) on delete cascade,
  scam_type              text not null,
  script_text            text,
  audio_url              text,
  language               text not null default 'en',
  user_detected_scam     boolean not null default false,
  detection_time_seconds int not null default 0,
  stages_identified      text[] not null default '{}',
  stages_missed          text[] not null default '{}',
  score_before           int not null default 0,
  score_after            int not null default 0,
  debrief                text,
  created_at             timestamptz not null default now()
);
create index if not exists idx_drills_user on public.drills(user_id, created_at desc);

-- 3. scam_reports (honeypot IOC output, Phase 5) ------------
create table if not exists public.scam_reports (
  id              uuid primary key default gen_random_uuid(),
  source          text not null default 'web',   -- web | telegram | guardian | drill
  raw_content     text,
  threat_level    risk_level not null default 'medium',
  iocs            jsonb not null default '{}'::jsonb,
  extracted_by    text,                           -- model that extracted them
  neo4j_graph_id  text,                           -- id of imported subgraph
  processed       boolean not null default false,
  created_at      timestamptz not null default now()
);
create index if not exists idx_reports_created on public.scam_reports(created_at desc);

-- 4. family_groups (Memory Handshake, Phase 4) --------------
create table if not exists public.family_groups (
  id           uuid primary key default gen_random_uuid(),
  invite_code  text unique not null default upper(substr(encode(gen_random_bytes(6),'hex'),1,8)),
  created_by   uuid references public.users(id) on delete set null,
  created_at   timestamptz not null default now()
);

-- 5. family_members ----------------------------------------
create table if not exists public.family_members (
  id         uuid primary key default gen_random_uuid(),
  group_id   uuid references public.family_groups(id) on delete cascade,
  user_id    uuid references public.users(id) on delete cascade,
  role       text not null default 'member',      -- owner | member | elder
  joined_at  timestamptz not null default now(),
  unique (group_id, user_id)
);

-- 6. memory_secrets (hashed answers only — never plaintext) -
create table if not exists public.memory_secrets (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references public.users(id) on delete cascade,
  question    text not null,
  answer_hash text not null,                      -- sha256, salted server-side
  totp_secret text,                               -- optional, encrypted at rest later
  active      boolean not null default true,
  created_at  timestamptz not null default now(),
  unique (user_id, question)
);

-- updated_at trigger ---------------------------------------
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists trg_users_updated on public.users;
create trigger trg_users_updated before update on public.users
  for each row execute function public.set_updated_at();

-- Row Level Security ---------------------------------------
alter table public.users            enable row level security;
alter table public.drills           enable row level security;
alter table public.scam_reports     enable row level security;
alter table public.family_groups    enable row level security;
alter table public.family_members   enable row level security;
alter table public.memory_secrets   enable row level security;

-- Dev policy: backend uses the anon key server-side.
-- Replace with auth.uid()-scoped policies before exposing to browsers.
drop policy if exists anon_all on public.users;
create policy anon_all on public.users for all using (true) with check (true);

drop policy if exists anon_all on public.drills;
create policy anon_all on public.drills for all using (true) with check (true);

drop policy if exists anon_all on public.scam_reports;
create policy anon_all on public.scam_reports for all using (true) with check (true);

drop policy if exists anon_all on public.family_groups;
create policy anon_all on public.family_groups for all using (true) with check (true);

drop policy if exists anon_all on public.family_members;
create policy anon_all on public.family_members for all using (true) with check (true);

drop policy if exists anon_all on public.memory_secrets;
create policy anon_all on public.memory_secrets for all using (true) with check (true);
