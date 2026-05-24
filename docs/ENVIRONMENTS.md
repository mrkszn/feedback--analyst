# Окружения — справочник

Источник правды для всех вопросов «куда коммитить ключи», «как переключиться на prod», «откуда брать креды для дев-окружения».

---

## Стратегия: 2 окружения сейчас, 3 — потом

| Окружение | Когда нужно | Где живёт | Назначение |
|-----------|-------------|-----------|------------|
| `local`   | С первого дня | Твой ноут | Свободно ломать, эксперименты с промптами, регрессы агента |
| `prod`    | Когда выходим на ресторан | Fly.io / Railway / VPS | Реальные клиенты, реальные деньги OpenAI |
| `staging` | Когда: >1 разработчика / CI/CD / >1 ресторана | Та же платформа, отдельная app | Pre-prod без живого трафика |

**Сейчас делаем `local`.** Шаги для `prod` — в разделе «Прод-деплой» ниже, как чек-лист к моменту, когда понадобится.

---

## Как переключается окружение

В коде — через env var `ENV=local|staging|prod`. Грузит `pydantic-settings` из `.env` (local) или из platform secrets (prod/staging).

```python
# config.py — единая точка
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    env: Literal["local", "staging", "prod"] = "local"
    ...
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

Никаких `if env == "prod":` по коду — настройки разруливаются значениями vars, не ветками. Если ветка нужна (например, отключить какой-то фейл-фаст на local) — единственное допустимое место это `config.py` через производное свойство.

---

## Что разделяется между окружениями

| Слой | local | prod | Изоляция |
|------|-------|------|----------|
| Telegram-боты | `@waiter_dev_bot`, `@admin_dev_bot` | `@waiter_bot`, `@admin_bot` | **Разные токены обязательно** — один токен не может polling из двух мест |
| Supabase | проект `waiter-dev` (free) | проект `waiter-prod` (Pro $25/мес) | Разные проекты, миграции тестим на dev первыми |
| Pinecone | namespace `dev` в индексе `client-cards` | namespace `prod` (или отдельный index) | Free tier — namespace; на росте — отдельный index |
| OpenAI | один ключ + `OPENAI_USAGE_TAG=local-dev` | тот же ключ + `OPENAI_USAGE_TAG=prod` | По желанию — отдельные ключи в OpenAI org для разделения биллинга |
| Запуск | `uv run python -m bot_guest` | контейнер на Fly/Railway | platform-secrets, не файлы |
| Данные | синтетика, твои тестовые отзывы | реальные клиенты | **prod → local НИКОГДА без анонимизации** |

---

## Локальное окружение — как поднять с нуля

Один раз:

```bash
cd telegram-waiter

# 1. Виртуалка (.venv) — uv создаёт автоматически при первой синке
uv sync                                # ставит deps из uv.lock в .venv/
                                       # или: uv add <pkg> для нового deps

# 2. Конфиг
cp .env.example .env                   # заполни значения вручную
                                       # см. чек-лист «Откуда брать креды» ниже

# 3. (Опционально) pre-commit
uv run pre-commit install              # если есть pre-commit в deps (см. GIT.md)

# 4. Проверка
uv run pytest                          # должно отработать без deps-проблем
                                       # (тестов пока нет — увидим "no tests ran")
```

Дальше каждый раз:
```bash
uv run python -m bot_guest             # стартует гостевой бот (polling)
uv run python -m bot_admin             # в отдельном терминале — админский
uv run uvicorn api.main:app --reload   # FastAPI для /health + webhooks
```

**Активация venv вручную (если нужно):**
```bash
source .venv/bin/activate              # POSIX
# или
.venv\Scripts\activate                 # Windows
```
Но если используешь `uv run` — активация не нужна, uv сам подставляет venv.

---

## Откуда брать креды для `.env`

| Переменная | Где взять | Бесплатно? |
|------------|-----------|------------|
| `TELEGRAM_GUEST_BOT_TOKEN` | @BotFather → `/newbot` → имя `waiter_dev_bot` | Да |
| `TELEGRAM_ADMIN_BOT_TOKEN` | @BotFather → `/newbot` → имя `admin_dev_bot` | Да |
| `ADMIN_TELEGRAM_IDS` | @userinfobot тебе пришлёт твой `id` | Да |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys → Create new | Платно, нужен биллинг |
| `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` | https://supabase.com → New project `waiter-dev` → Settings → API | Free tier |
| `PINECONE_API_KEY` | https://app.pinecone.io → API Keys; создать index `client-cards` (dim=1536, metric=cosine) | Free tier |

**Безопасность:** service_role_key Supabase обходит RLS — относись к нему как к root-паролю. Никогда не клади в код фронта/бота как hardcode, только через env.

---

## Прод-деплой (чек-лист к моменту запуска)

Не делать сейчас, но держать в голове.

### Telegram
- [ ] @BotFather → создать **новых** ботов (без `_dev`): `@<restaurant>_waiter_bot`, `@<restaurant>_admin_bot`
- [ ] Получить токены, положить в platform secrets

### Supabase
- [ ] Новый проект `waiter-prod` (план Pro для production reliability)
- [ ] Применить миграции: `supabase db push --project-ref <prod-ref>`
- [ ] Включить **Point-in-Time Recovery** (PITR) — критично для feedback-данных
- [ ] Установить RLS-политики (хотя сервис ходит service_role, на будущее)
- [ ] Скопировать `URL` и `service_role key` в platform secrets

### Pinecone
- [ ] Тот же index `client-cards`, namespace `prod` (или отдельный index `client-cards-prod`)
- [ ] Скопировать API key в platform secrets

### OpenAI
- [ ] Создать отдельный API key с лимитом расходов (Usage limit) — защита от runaway-расходов
- [ ] Set `OPENAI_USAGE_TAG=prod` для разделения в биллинге

### Хостинг (рекомендация: Fly.io)
- [ ] `fly launch` в `telegram-waiter/`
- [ ] `fly.toml` с двумя процессами:
  ```toml
  [processes]
  guest = "python -m bot_guest"
  admin = "python -m bot_admin"
  api   = "uvicorn api.main:app --host 0.0.0.0 --port 8080"
  ```
- [ ] `fly secrets set OPENAI_API_KEY=... TELEGRAM_GUEST_BOT_TOKEN=... ...`
- [ ] `fly deploy`
- [ ] Health-check на `/health` через Fly platform

### Observability
- [ ] Logtail / Better Stack / Grafana Cloud — куда стримим structlog
- [ ] Alert на error rate > X / минуту
- [ ] Alert на OpenAI расход > Y$ / день

---

## Когда добавлять `staging`

Триггеры:
- появилась автоматизация CI/CD
- агент-промпт меняется часто и ломает prod-сессии
- больше одного ресторана-клиента
- появился второй разработчик

До этого момента — local-dev покрывает 90% риска, а оставшиеся 10% дешевле ловить через feature flags на prod (`BETA_USERS_ONLY=[my_telegram_id]`).

---

## Anti-patterns (чего не делаем)

- ❌ Один токен Telegram-бота на dev и prod (бот «прыгает» между средами, теряет апдейты)
- ❌ Копирование prod-данных в local без анонимизации (PII клиентов)
- ❌ Hardcoded ключ в коде «временно, потом уберу» — забудешь
- ❌ Разные миграции в local и prod (расхождение схем = баги в проде)
- ❌ Использование `service_role_key` на клиенте/фронте (всегда только сервер)
- ❌ Запуск prod-ботов с твоего ноута «на минутку» (потеряешь сессии, перепутаешь акк)

---

## Команды-памятки (положить в Makefile при желании)

```bash
# Локально
uv sync                                # обновить deps по lock
uv run pytest                          # тесты
uv run ruff check . && uv run ruff format .
uv run mypy .

# Запуск
uv run python -m bot_guest             # гостевой бот (polling)
uv run python -m bot_admin             # админ-бот (polling)
uv run uvicorn api.main:app --reload   # API

# Миграции
supabase db push --project-ref <dev-ref>       # на dev
supabase db push --project-ref <prod-ref>      # на prod (с подтверждением)

# Prod (когда дойдём)
fly deploy
fly logs
fly secrets list
```
