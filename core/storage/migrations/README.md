# Database Migrations

Каждая миграция — отдельный SQL-файл с возрастающим номером: `NNNN_short_name.sql`. История применения линейная, без down-миграций (откат — отдельным новым SQL-файлом).

## Как применить

### Вариант 1 — CI workflow «DB migrations» (основной способ для прода) ⭐

Миграции на прод накатываются **вручную из GitHub Actions**, не на каждый push
(схемные изменения слишком рискованны для авто-деплоя):

1. GitHub → вкладка **Actions** → workflow **DB migrations** → **Run workflow**.
2. Сначала прогони с `dry_run = true` — покажет, какие файлы будут применены,
   ничего не меняя.
3. Доволен списком → запусти ещё раз с `dry_run = false`.

Workflow (`.github/workflows/migrate.yml`) дёргает `scripts/apply_migrations.sh`
с секретом `SUPABASE_DB_URL` (см. ниже).

### Вариант 2 — локально тем же раннером

```bash
# DSN из Supabase Dashboard → Connect → Session pooler (порт 5432)
export SUPABASE_DB_URL='postgresql://postgres.<ref>:<pwd>@<host>.pooler.supabase.com:5432/postgres'

scripts/apply_migrations.sh --dry-run   # превью
scripts/apply_migrations.sh             # применить
```

### Вариант 3 — Supabase Studio (для local-dev / разовых правок)
1. Открой проект в [Supabase Studio](https://supabase.com/dashboard).
2. SQL Editor → `New query`.
3. Скопируй содержимое нужного файла → `Run`.
4. Проверь Tables: должны появиться все таблицы из миграции.

## Как раннер отслеживает применённое

`scripts/apply_migrations.sh` ведёт таблицу `public.app_migrations` (одна строка
на имя файла) и применяет только те `NNNN_*.sql`, которых там ещё нет, в порядке
номеров. Каждый файл — в отдельной транзакции с `ON_ERROR_STOP`; первая ошибка
прерывает прогон. Раннер **не** использует Supabase CLI и `supabase/migrations/`
— остаёмся на конвенции `core/storage/migrations/NNNN_name.sql`.

Так как каждая миграция идемпотентна (`create … if not exists`/`create or
replace`), первый прогон против уже поднятой БД безопасен: существующие объекты
просто пере-объявляются и записываются в `app_migrations`, данные не трогаются.

### Секрет `SUPABASE_DB_URL`

Нужен для Варианта 1 (GitHub Secrets → Actions) и Варианта 2 (env локально).
Бери **Session pooler**-строку (порт `5432`), не transaction-pooler (`6543`):
DDL и функции требуют session-режим. GitHub-раннеры ходят по IPv4, поэтому
прямой `db.<ref>.supabase.co` (IPv6-only) не подойдёт — только pooler.

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
