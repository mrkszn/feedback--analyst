-- =============================================================================
-- 0006_journeys_and_capture.sql — Phase A of the guest webapp v2.
--
-- Two independent capabilities, both additive and idempotent:
--
--   1. Capture columns on `sessions`. The guest webapp now opens via
--      differentiated QR codes (restaurant vs delivery) and will later split
--      into two product modes (non_targeted vs targeted). We persist that
--      context from the very first request so analytics already accumulate:
--        journey_template_name — which journey the guest walked (FK by name).
--        mode                  — non_targeted | targeted (behaviour wired in
--                                Phase C; column exists now so data collects).
--        meal_occasion         — breakfast | lunch | dinner | other; only
--                                meaningful for the restaurant journey.
--
--   2. Seed a second journey template, 'delivery', with five beats and chip
--      tags — mirrors the 'restaurant' seed in 0005. Adding journeys is a
--      config-only INSERT, never a schema change.
--
-- `restaurant` stays the single default (is_default = true from 0005);
-- 'delivery' is reached explicitly via GET /guest/journey?name=delivery.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- sessions: capture journey / mode / meal_occasion
-- -----------------------------------------------------------------------------
alter table sessions
    add column if not exists journey_template_name text,
    add column if not exists mode text not null default 'non_targeted',
    add column if not exists meal_occasion text;

do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'sessions_journey_template_name_fkey'
    ) then
        alter table sessions
            add constraint sessions_journey_template_name_fkey
            foreign key (journey_template_name) references journey_templates(name);
    end if;

    if not exists (select 1 from pg_constraint where conname = 'sessions_mode_check') then
        alter table sessions
            add constraint sessions_mode_check check (mode in ('non_targeted', 'targeted'));
    end if;

    if not exists (select 1 from pg_constraint where conname = 'sessions_meal_occasion_check') then
        alter table sessions
            add constraint sessions_meal_occasion_check
            check (meal_occasion in ('breakfast', 'lunch', 'dinner', 'other'));
    end if;
end$$;

-- =============================================================================
-- Seed: 'delivery' journey (not default).
-- =============================================================================

insert into journey_templates (name, label_uk, label_en, is_default)
    values ('delivery', 'Доставка', 'Delivery', false)
on conflict (name) do nothing;

insert into journey_beats (template_id, position, beat_key, label_uk, label_en, icon, input_type)
select t.id, v.position, v.beat_key, v.label_uk, v.label_en, v.icon, 'mood_slider'
from journey_templates t
cross join (values
    (1::smallint, 'order',    'Замовлення', 'Order',      '🛒'),
    (2::smallint, 'wait',     'Очікування', 'Wait',       '⏳'),
    (3::smallint, 'courier',  'Кур''єр',     'Courier',    '🛵'),
    (4::smallint, 'food',     'Їжа',        'Food',       '🍽️'),
    (5::smallint, 'overall',  'Враження',   'Impression', '✨')
) as v(position, beat_key, label_uk, label_en, icon)
where t.name = 'delivery'
on conflict (template_id, beat_key) do nothing;

with beat as (
    select b.id as beat_id, b.beat_key
    from journey_beats b
    join journey_templates t on t.id = b.template_id
    where t.name = 'delivery'
)
insert into beat_tags (beat_id, position, tag_key, label_uk, label_en)
select beat.beat_id, v.position, v.tag_key, v.label_uk, v.label_en
from beat
join (values
    -- order
    ('order',   1::smallint, 'app_buggy',     'Глючний застосунок',    'Buggy app'),
    ('order',   2::smallint, 'menu_unclear',  'Незрозуміле меню',      'Menu unclear'),
    ('order',   3::smallint, 'items_missing', 'Не було позицій',       'Items missing'),
    -- wait
    ('wait',    1::smallint, 'too_long',      'Довго чекав',           'Too long'),
    ('wait',    2::smallint, 'eta_wrong',     'Час не збігся',         'ETA off'),
    ('wait',    3::smallint, 'no_updates',    'Не сповіщали',          'No updates'),
    -- courier
    ('courier', 1::smallint, 'rude',          'Грубий',                'Rude'),
    ('courier', 2::smallint, 'lost',          'Заблукав',              'Got lost'),
    ('courier', 3::smallint, 'no_contact',    'Не виходив на зв''язок', 'No contact'),
    -- food
    ('food',    1::smallint, 'cold',          'Холодна',               'Cold'),
    ('food',    2::smallint, 'spilled',       'Розлилось',             'Spilled'),
    ('food',    3::smallint, 'wrong_order',   'Переплутали',           'Wrong order'),
    ('food',    4::smallint, 'small_portion', 'Мала порція',           'Small portion'),
    -- overall
    ('overall', 1::smallint, 'expensive',     'Дорого',                'Expensive'),
    ('overall', 2::smallint, 'packaging',     'Погана упаковка',       'Bad packaging')
) as v(beat_key, position, tag_key, label_uk, label_en)
  on v.beat_key = beat.beat_key
on conflict (beat_id, tag_key) do nothing;
