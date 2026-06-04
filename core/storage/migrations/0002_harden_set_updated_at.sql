-- =============================================================================
-- 0002_harden_set_updated_at.sql
-- Фиксим search_path для триггер-функции set_updated_at.
-- Без этого функция уязвима к search_path hijacking (одна из категорий
-- Postgres security audit от Supabase).
-- Ref: https://supabase.com/docs/guides/database/database-linter?lint=0011
-- =============================================================================

create or replace function set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;
