-- =============================================================================
-- 0007_gamification.sql — Phase C of the guest webapp v2.
--
-- The targeted product mode gamifies feedback: points per meaningful answer,
-- a prize wheel at the end, and a captured guest identity (email required to
-- claim). non_targeted sessions stay a plain emoji ribbon but also capture a
-- name. Both are computed/stored server-side at finalize.
--
-- Additive + idempotent:
--   1. sessions: points / prize_tier + guest identity (name/email/phone).
--   2. session_beats: a write-time UK transcription of the emoji mood.
--   3. prize_tiers: a small config table the restaurant owner edits in the
--      admin app (code + label per tier) — prizes are configured in-app, not
--      via env. Seeded with three empty-code defaults so /guest/prize works
--      before the owner sets anything.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- sessions: gamification + identity
-- -----------------------------------------------------------------------------
alter table sessions
    add column if not exists points int not null default 0,
    add column if not exists prize_tier text,
    add column if not exists guest_name text,
    add column if not exists guest_email text,
    add column if not exists guest_phone text;

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'sessions_prize_tier_check') then
        alter table sessions
            add constraint sessions_prize_tier_check
            check (prize_tier in ('small', 'medium', 'large'));
    end if;
end$$;

create index if not exists idx_sessions_mode on sessions(mode);

-- -----------------------------------------------------------------------------
-- session_beats: per-beat emoji → UK phrase (write-time, no LLM)
-- -----------------------------------------------------------------------------
alter table session_beats
    add column if not exists emoji_transcription_uk text;

-- -----------------------------------------------------------------------------
-- prize_tiers: in-app prize configuration (one row per tier)
-- -----------------------------------------------------------------------------
create table if not exists prize_tiers (
    tier        text primary key check (tier in ('small', 'medium', 'large')),
    code        text not null default '',
    label_uk    text not null default '',
    label_en    text not null default '',
    updated_at  timestamptz not null default now()
);
comment on table prize_tiers is 'Owner-configured prize code + label per gamification tier.';

drop trigger if exists trg_prize_tiers_updated_at on prize_tiers;
create trigger trg_prize_tiers_updated_at
    before update on prize_tiers
    for each row execute function set_updated_at();

alter table prize_tiers enable row level security;

insert into prize_tiers (tier, code, label_uk, label_en) values
    ('small',  '', 'Невеличкий бонус', 'Small bonus'),
    ('medium', '', 'Приємний приз',    'Nice prize'),
    ('large',  '', 'Головний приз',    'Top prize')
on conflict (tier) do nothing;
