-- =============================================================================
-- 0003_admin_settings.sql — per-admin Mini App preferences.
--
-- One row per admin (FK → admin_users) holding the settings the admin Mini App
-- reads/writes: theme, language, notifications toggle. Column defaults match the
-- service defaults in core/services/settings.py, so a missing row is equivalent
-- to "all defaults" — the service never forces a write on read.
--
-- RLS enabled without policies: the service ходит с service_role_key (bypasses
-- RLS); no public access. Mirrors the convention in 0001_init.sql.
-- =============================================================================

create table if not exists admin_settings (
    telegram_id           bigint primary key references admin_users(telegram_id) on delete cascade,
    theme                 text not null default 'system'
                              check (theme in ('light', 'dark', 'system')),
    language              text not null default 'ru'
                              check (language in ('ru', 'en')),
    notifications_enabled boolean not null default true,
    created_at            timestamptz not null default now(),
    updated_at            timestamptz not null default now()
);
comment on table admin_settings is 'Per-admin Mini App preferences (theme/language/notifications)';

drop trigger if exists trg_admin_settings_updated_at on admin_settings;
create trigger trg_admin_settings_updated_at
    before update on admin_settings
    for each row execute function set_updated_at();

alter table admin_settings enable row level security;
