-- =============================================================================
-- 0001_init.sql — Initial schema for telegram-waiter v1
-- Feedback collector + adaptive interview MVP.
--
-- Tables:
--   clients          — Telegram users who interacted with the guest bot
--   admin_users      — whitelist for the admin bot
--   questions        — pool of interview questions managed via admin bot
--   sessions         — one row per guest dialog
--   session_messages — transcript (every utterance)
--   session_answers  — answers to questions with marked metrics
--   client_cards     — per-session free-text profile (mirrors Pinecone vector)
--
-- RLS включён на всех таблицах БЕЗ политик: сервис ходит с service_role_key,
-- который обходит RLS; никакого публичного доступа.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Extensions
-- -----------------------------------------------------------------------------
create extension if not exists "uuid-ossp";

-- -----------------------------------------------------------------------------
-- updated_at trigger function (general)
-- -----------------------------------------------------------------------------
create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

-- -----------------------------------------------------------------------------
-- clients
-- -----------------------------------------------------------------------------
create table if not exists clients (
    telegram_id bigint primary key,
    name        text,
    created_at  timestamptz not null default now()
);
comment on table clients is 'Telegram users who interacted with the guest bot';

-- -----------------------------------------------------------------------------
-- admin_users (source of truth for admin auth; bootstrap via /claim)
-- -----------------------------------------------------------------------------
create table if not exists admin_users (
    telegram_id bigint primary key,
    name        text,
    invited_by  bigint references admin_users(telegram_id) on delete set null,
    created_at  timestamptz not null default now()
);
comment on table admin_users is 'Whitelist for admin bot. Bootstrap via /claim ADMIN_BOOTSTRAP_TOKEN.';

-- -----------------------------------------------------------------------------
-- questions
-- -----------------------------------------------------------------------------
create table if not exists questions (
    id            uuid primary key default uuid_generate_v4(),
    text          text not null,
    metric_key    text not null,
    expected_type text not null check (expected_type in ('text', 'number', 'enum', 'boolean')),
    enum_values   jsonb,
    is_active     boolean not null default true,
    created_by    bigint references admin_users(telegram_id) on delete set null,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);
comment on table questions is 'Interview question pool managed via admin bot';
comment on column questions.metric_key is 'Stable key for analytics aggregation, e.g. "service_speed"';
comment on column questions.enum_values is 'Populated only when expected_type = enum';

create unique index if not exists idx_questions_metric_key on questions(metric_key);
create index if not exists idx_questions_active on questions(is_active) where is_active = true;

drop trigger if exists trg_questions_updated_at on questions;
create trigger trg_questions_updated_at
    before update on questions
    for each row execute function set_updated_at();

-- -----------------------------------------------------------------------------
-- sessions
-- -----------------------------------------------------------------------------
create table if not exists sessions (
    id                uuid primary key default uuid_generate_v4(),
    client_id         bigint not null references clients(telegram_id) on delete cascade,
    started_at        timestamptz not null default now(),
    ended_at          timestamptz,
    feedback_raw_text text,
    feedback_source   text check (feedback_source in ('text', 'voice')),
    feedback_summary  jsonb,
    language          text
);
comment on table sessions is 'One row per guest dialog (feedback collection + interview)';
comment on column sessions.feedback_summary is 'JSON: {summary, sentiment, topics[], emotion}';

create index if not exists idx_sessions_client on sessions(client_id);
create index if not exists idx_sessions_ended_at on sessions(ended_at);

-- -----------------------------------------------------------------------------
-- session_messages (transcript)
-- -----------------------------------------------------------------------------
create table if not exists session_messages (
    id         bigserial primary key,
    session_id uuid not null references sessions(id) on delete cascade,
    role       text not null check (role in ('user', 'bot')),
    content    text not null,
    created_at timestamptz not null default now()
);
comment on table session_messages is 'Per-message transcript of a session';

create index if not exists idx_session_messages_session on session_messages(session_id, created_at);

-- -----------------------------------------------------------------------------
-- session_answers
-- -----------------------------------------------------------------------------
create table if not exists session_answers (
    id           bigserial primary key,
    session_id   uuid not null references sessions(id) on delete cascade,
    question_id  uuid not null references questions(id) on delete restrict,
    answer_text  text not null,
    marked_value jsonb,
    created_at   timestamptz not null default now()
);
comment on table session_answers is 'Structured answers extracted from the interview';
comment on column session_answers.marked_value is 'Extracted value matching question.expected_type';

create index if not exists idx_session_answers_session on session_answers(session_id);
create index if not exists idx_session_answers_question on session_answers(question_id);

-- -----------------------------------------------------------------------------
-- client_cards (per-session, mirror of Pinecone vector)
-- -----------------------------------------------------------------------------
create table if not exists client_cards (
    id                 uuid primary key default uuid_generate_v4(),
    client_id          bigint not null references clients(telegram_id) on delete cascade,
    session_id         uuid not null unique references sessions(id) on delete cascade,
    summary_text       text not null,
    pinecone_vector_id text not null,
    created_at         timestamptz not null default now()
);
comment on table client_cards is 'Per-session free-text profile (mirror of Pinecone vector)';
comment on column client_cards.pinecone_vector_id is 'Typically equals session_id::text';

create index if not exists idx_client_cards_client on client_cards(client_id);

-- -----------------------------------------------------------------------------
-- Row-Level Security: enable on all tables, no policies = service_role only
-- -----------------------------------------------------------------------------
alter table clients          enable row level security;
alter table admin_users      enable row level security;
alter table questions        enable row level security;
alter table sessions         enable row level security;
alter table session_messages enable row level security;
alter table session_answers  enable row level security;
alter table client_cards     enable row level security;
