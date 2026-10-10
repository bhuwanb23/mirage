-- ============================================================
-- Mirage — Memory Handshake (Phase 4)
-- Run in: Supabase Dashboard → SQL Editor → New query → Run
-- Idempotent: safe to re-run.
-- ============================================================

-- 1. Per-group rotating TOTP secret (pyotp base32) ------------
alter table public.family_groups
  add column if not exists totp_secret text;

-- 2. Group-scoped challenge questions -------------------------
-- Phase 4 stores questions per family group (the caller is verified
-- against the *group's* secrets). user_id stays for per-user rows
-- written by other phases.
alter table public.memory_secrets
  add column if not exists family_group_id uuid
    references public.family_groups(id) on delete cascade;

-- One ACTIVE copy of a question per group. Setup deactivates old rows
-- instead of deleting them (audit trail), so the constraint is partial.
create unique index if not exists uq_memq_active_group_question
  on public.memory_secrets(family_group_id, question)
  where active and family_group_id is not null;

create index if not exists idx_memq_group_active
  on public.memory_secrets(family_group_id)
  where active;
