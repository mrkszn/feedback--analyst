-- =============================================================================
-- 0005_guest_journey.sql — guest web app "вечер как лента" UX.
--
-- Backend for the public guest webapp (separate repo, deployed on Vercel)
-- that runs anonymous feedback sessions through a horizontal "journey" of
-- beats (arrival → order → wait → food → service → leaving) with mood +
-- chip-tag input on each beat and an LLM "dig" follow-up on weak beats.
--
-- Changes to existing schema:
--   1. `sessions.client_id` becomes nullable (anonymous web sessions have no
--      Telegram identity). Bot/admin flows still always set it.
--   2. `sessions.feedback_source` check accepts 'web' and 'web_anon' in
--      addition to the existing 'text' and 'voice'.
--
-- New tables:
--   journey_templates  — named bundles (e.g. 'restaurant', 'delivery').
--   journey_beats      — ordered beats inside a template.
--   beat_tags          — optional chip tags surfaced on low-score beats.
--   session_beats      — per-session scores/tags/skip flag for each beat.
--   session_digs       — LLM "guess" cards offered for weak beats and the
--                        guest's reaction (accepted guess or free text).
--
-- Seeds one default 'restaurant' journey with six beats and 2–3 tags each.
-- Adding more journeys later is a config-only INSERT, not a schema change.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- sessions: nullable client_id + extended feedback_source values
-- -----------------------------------------------------------------------------
alter table sessions alter column client_id drop not null;

do $$
declare
    cname text;
begin
    select conname into cname
      from pg_constraint
     where conrelid = 'sessions'::regclass
       and contype  = 'c'
       and pg_get_constraintdef(oid) ilike '%feedback_source%';
    if cname is not null then
        execute format('alter table sessions drop constraint %I', cname);
    end if;
end$$;

alter table sessions
    add constraint sessions_feedback_source_check
    check (feedback_source in ('text', 'voice', 'web', 'web_anon'));

-- -----------------------------------------------------------------------------
-- journey_templates
-- -----------------------------------------------------------------------------
create table if not exists journey_templates (
    id          uuid primary key default uuid_generate_v4(),
    name        text unique not null,
    label_uk    text not null,
    label_en    text not null,
    is_default  boolean not null default false,
    created_at  timestamptz not null default now()
);
comment on table journey_templates is 'Named guest-journey bundles (restaurant, delivery, …).';

create unique index if not exists idx_journey_templates_single_default
    on journey_templates ((1)) where is_default = true;

alter table journey_templates enable row level security;

-- -----------------------------------------------------------------------------
-- journey_beats
-- -----------------------------------------------------------------------------
create table if not exists journey_beats (
    id           uuid primary key default uuid_generate_v4(),
    template_id  uuid not null references journey_templates(id) on delete cascade,
    position     smallint not null,
    beat_key     text not null,
    label_uk     text not null,
    label_en     text not null,
    icon         text not null,
    input_type   text not null default 'mood_slider'
                 check (input_type in ('mood_slider', 'chip_pick', 'yes_no')),
    created_at   timestamptz not null default now(),
    unique (template_id, position),
    unique (template_id, beat_key)
);
comment on table journey_beats is 'Ordered beats of a guest journey (one row per UI screen).';

create index if not exists idx_journey_beats_template on journey_beats(template_id);

alter table journey_beats enable row level security;

-- -----------------------------------------------------------------------------
-- beat_tags
-- -----------------------------------------------------------------------------
create table if not exists beat_tags (
    id         uuid primary key default uuid_generate_v4(),
    beat_id    uuid not null references journey_beats(id) on delete cascade,
    position   smallint not null,
    tag_key    text not null,
    label_uk   text not null,
    label_en   text not null,
    unique (beat_id, tag_key),
    unique (beat_id, position)
);
comment on table beat_tags is 'Chip-tag options surfaced on a beat (low-score follow-ups).';

create index if not exists idx_beat_tags_beat on beat_tags(beat_id);

alter table beat_tags enable row level security;

-- -----------------------------------------------------------------------------
-- session_beats
-- -----------------------------------------------------------------------------
create table if not exists session_beats (
    session_id  uuid not null references sessions(id) on delete cascade,
    beat_id     uuid not null references journey_beats(id) on delete cascade,
    score       smallint check (score between 1 and 5),
    tags        jsonb not null default '[]'::jsonb,
    skipped     boolean not null default false,
    updated_at  timestamptz not null default now(),
    primary key (session_id, beat_id)
);
comment on table session_beats is 'Per-session score/tags/skip flag for each beat.';

create index if not exists idx_session_beats_session on session_beats(session_id);

drop trigger if exists trg_session_beats_updated_at on session_beats;
create trigger trg_session_beats_updated_at
    before update on session_beats
    for each row execute function set_updated_at();

alter table session_beats enable row level security;

-- -----------------------------------------------------------------------------
-- session_digs
-- -----------------------------------------------------------------------------
create table if not exists session_digs (
    id                 uuid primary key default uuid_generate_v4(),
    session_id         uuid not null references sessions(id) on delete cascade,
    beat_id            uuid not null references journey_beats(id) on delete cascade,
    guesses            jsonb not null,
    accepted_guess_id  text,
    free_text          text,
    voice_object_key   text,
    created_at         timestamptz not null default now()
);
comment on table session_digs is 'LLM guess cards offered for a weak beat and the guest reaction.';

create index if not exists idx_session_digs_session on session_digs(session_id);

alter table session_digs enable row level security;

-- =============================================================================
-- Seed: default 'restaurant' journey.
-- =============================================================================

insert into journey_templates (name, label_uk, label_en, is_default)
    values ('restaurant', 'Ресторан', 'Restaurant', true)
on conflict (name) do nothing;

insert into journey_beats (template_id, position, beat_key, label_uk, label_en, icon, input_type)
select t.id, v.position, v.beat_key, v.label_uk, v.label_en, v.icon, 'mood_slider'
from journey_templates t
cross join (values
    (1::smallint, 'arrival',  'Прихід',     'Arrival', '🚪'),
    (2::smallint, 'order',    'Замовлення', 'Order',   '📝'),
    (3::smallint, 'wait',     'Очікування', 'Wait',    '⏳'),
    (4::smallint, 'food',     'Їжа',        'Food',    '🍽️'),
    (5::smallint, 'service',  'Сервіс',     'Service', '💁'),
    (6::smallint, 'leaving',  'Прощання',   'Leaving', '👋')
) as v(position, beat_key, label_uk, label_en, icon)
where t.name = 'restaurant'
on conflict (template_id, beat_key) do nothing;

with beat as (
    select b.id as beat_id, b.beat_key
    from journey_beats b
    join journey_templates t on t.id = b.template_id
    where t.name = 'restaurant'
)
insert into beat_tags (beat_id, position, tag_key, label_uk, label_en)
select beat.beat_id, v.position, v.tag_key, v.label_uk, v.label_en
from beat
join (values
    -- arrival
    ('arrival', 1::smallint, 'crowded',          'Натовп',           'Crowded'),
    ('arrival', 2::smallint, 'waited_for_table', 'Чекали на стіл',   'Waited for table'),
    ('arrival', 3::smallint, 'unwelcoming',      'Не привітали',     'Unwelcoming'),
    -- order
    ('order',   1::smallint, 'slow_to_take',     'Повільно прийняли','Slow to take order'),
    ('order',   2::smallint, 'menu_unclear',     'Незрозуміле меню', 'Menu unclear'),
    ('order',   3::smallint, 'no_recommendation','Не порадили',      'No recommendation'),
    -- wait
    ('wait',    1::smallint, 'too_long',         'Довго чекали',     'Too long'),
    ('wait',    2::smallint, 'no_updates',       'Не сповіщали',     'No updates'),
    -- food
    ('food',    1::smallint, 'cold',             'Холодна',          'Cold'),
    ('food',    2::smallint, 'small_portion',    'Мала порція',      'Small portion'),
    ('food',    3::smallint, 'taste',            'Не сподобався смак','Taste off'),
    ('food',    4::smallint, 'not_as_expected',  'Не як очікував',   'Not as expected'),
    -- service
    ('service', 1::smallint, 'inattentive',      'Неуважні',         'Inattentive'),
    ('service', 2::smallint, 'rude',             'Грубість',         'Rude'),
    ('service', 3::smallint, 'mistakes',         'Помилки в замовленні','Order mistakes'),
    -- leaving
    ('leaving', 1::smallint, 'slow_bill',        'Повільний рахунок','Slow bill'),
    ('leaving', 2::smallint, 'no_goodbye',       'Не попрощались',   'No goodbye')
) as v(beat_key, position, tag_key, label_uk, label_en)
  on v.beat_key = beat.beat_key
on conflict (beat_id, tag_key) do nothing;
