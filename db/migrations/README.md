# Database Migrations

Каждая миграция — отдельный SQL-файл с возрастающим номером: `NNNN_short_name.sql`. История применения линейная, без down-миграций (откат — отдельным новым SQL-файлом).

## Как применить

### Вариант 1 — Supabase Studio (для local-dev)
1. Открой проект в [Supabase Studio](https://supabase.com/dashboard).
2. SQL Editor → `New query`.
3. Скопируй содержимое нужного файла → `Run`.
4. Проверь Tables: должны появиться все таблицы из миграции.

### Вариант 2 — Supabase CLI (когда настроишь)
```bash
# Линковка с проектом (один раз)
supabase link --project-ref <YOUR_PROJECT_REF>

# Применение всех новых миграций
supabase db push
```

CLI читает файлы из `supabase/migrations/`. У нас они в `db/migrations/`, поэтому либо настрой `supabase/config.toml` указывать на нашу папку, либо положи symlink `supabase/migrations → ../db/migrations`.

### Вариант 3 — Прямой psql / asyncpg (когда будет `SUPABASE_DB_URL`)
```bash
psql "$SUPABASE_DB_URL" -f db/migrations/0001_init.sql
```

## Порядок и инварианты

- Файлы применяются по возрастанию `NNNN`.
- Один файл = одна логически атомарная миграция (несколько связанных DDL — ОК).
- `create table if not exists` / `create index if not exists` — чтобы повторное применение было идемпотентно (но не злоупотреблять: лучше отдельная миграция для изменений схемы).
- **Никогда не редактируем уже применённый файл.** Изменение — новый файл `NNNN+1_...sql`.

## Что есть сейчас

| Файл | Что добавляет |
|---|---|
| `0001_init.sql` | 7 таблиц v1, индексы, триггер `updated_at`, RLS enabled (no policies) |
| `0002_harden_set_updated_at.sql` | Фикс `set_updated_at`: явный `search_path = ''` (защита от search-path hijacking) |

## Архитектурное решение: RLS без политик — намеренно

Supabase advisor выдаёт INFO-лiнт `rls_enabled_no_policy` на все наши таблицы. **Это не баг.**

Архитектура v1: оба бота (`bot_guest`, `bot_admin`) — серверные процессы, которые ходят с `SUPABASE_SERVICE_ROLE_KEY`. Этот ключ **обходит RLS** by design. Пользовательский Telegram-клиент **не имеет прямого доступа к Supabase** — общение идёт только через бота.

Раскладка по умолчанию:
- RLS включён → без service_role_key никто ничего не прочтёт/не запишет
- Политик нет → ни одна роль `authenticated`/`anon` не имеет доступа
- Service_role обходит RLS → бот работает без проблем

**Когда добавлять политики:**
- Появится PostgREST/REST-эндпоинт для клиентов мимо бота
- Подключим `authenticated` role (Supabase Auth для админ-веб-панели)
- Любой кейс, где клиент с публичным ключом должен читать таблицу

Сейчас этого нет, поэтому политик нет. Не добавлять «для красоты» — без конкретного use-case политика создаст ложное чувство безопасности.
