-- =============================================================================
-- 0004_settings_language_uk.sql — switch admin UI language set to uk/en.
--
-- The product now ships two interface languages: Ukrainian (default) and
-- English. Russian is dropped. This migration:
--   1. drops the old language CHECK ('ru', 'en'),
--   2. remaps any stored 'ru' (or other stray value) to the new default 'uk',
--   3. sets the column default to 'uk' and re-adds the CHECK ('uk', 'en').
--
-- Idempotent: the constraint is dropped-if-exists before re-adding, and the
-- UPDATE is a no-op once every row already sits in ('uk', 'en'). Keep the
-- column default in sync with DEFAULT_SETTINGS in core/services/settings.py.
-- =============================================================================

alter table admin_settings
    drop constraint if exists admin_settings_language_check;

update admin_settings
    set language = 'uk'
    where language not in ('uk', 'en');

alter table admin_settings
    alter column language set default 'uk',
    add constraint admin_settings_language_check check (language in ('uk', 'en'));
