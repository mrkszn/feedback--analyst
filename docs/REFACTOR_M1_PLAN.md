# Refactor Plan — M1 Modular Architecture

> **Цель:** перевести проект из «единого telegram-waiter» в **layered + template-based** структуру, чтобы (а) онбординг нового клиента занимал часы а не дни, (б) core-багфиксы автоматически попадали ко всем клиентам, (в) код-стрyктура декларировала возможности кастомизации.

**Решённые архитектурные предпосылки** (из обсуждения куратор ↔ Claude):
- **M1 — Monorepo + overrides** (НЕ packages NPM/PyPI стиля, НЕ fork-per-client)
- **Per-client deploy** (НЕ shared multi-tenant с RLS)
- **4 фазы с checkpoint sign-off'ом** куратора после каждой
- **Hard break** на путях импорта (без backward-compat шимов)
- **YAML** для конфигов

## Phase progress

- ✅ **R1 — Structural rename** — committed `fa62669` (137 files, +957/-489, 462 tests passing)
- ✅ **R2 — StorageAdapter Protocol** — committed `64231ac` (17 files, +1179/-442, 462 tests passing). 3 ratified deviations: backward-compat `db: Client | None` parameter, `get_supabase` import retained as test patch-target, data-access Protocol granularity.
- 🔄 **R3 — Template loader** — in flight (team `feat-m1-r3`)
- ⏸  **R4 — Docs + tg-clinic** — pending

**Live status:** see `STATUS.md` at repo root (updated by team-lead per change).

## Coordination rules (mandatory for all M1 teams)

Learned the hard way during R1/R2 — these are non-negotiable for R3 onward:

1. **STATUS.md is the source of truth for curator visibility.** Update `STATUS.md` after every phase change, deviation, or open question. Do NOT spam curator with SendMessage status. Curator reads `STATUS.md`, not your inbox.
2. **`pytest --collect-only` ≠ `pytest -q`.** Collect catches import errors only. Full run catches runtime errors (e.g., string-literal `patch("...")` targets pointing at deleted modules). Always run full `pytest -q` before claiming done.
3. **Patch-target grep covers 4 call forms:** `patch("...")`, `patch.object("...", ...)`, `mocker.patch("...")`, `monkeypatch.setattr("...", ...)`. Import-grep alone misses these. Permanent gate must check all four.
4. **Backward-compat retention is acceptable** when it preserves existing tests without massive fixture rewrites. Document trade-off in commit body as "ratified deviation".
5. **Curator commits from main loop.** Subagents hit permission denial on `git commit`. Don't retry — escalate to curator via STATUS.md "Open questions" or single SendMessage.
6. **Idle notifications are normal, not blockers.** Do not react to teammate idle pings unless they impact your work.
7. **Verify live task state before acting on stale assignments.** Stale "start work" messages can arrive after a task is completed by a different agent in the same team.
8. **One implementer per file at a time.** When a phase touches the same module from multiple angles, serialize edits or split file ownership explicitly.

---

## Финальная структура (после R1)

```
telegram-waiter/
├── core/                          ← неизменное ядро (от клиента к клиенту)
│   ├── agent/                     ← было agent/
│   │   ├── nodes/                 (analyze, dialogue, card, extract, ...)
│   │   ├── analytics_agent/       (interpret, execute, synthesize, runner)
│   │   └── prompts.py
│   ├── services/                  ← было services/
│   ├── integrations/              ← было integrations/  (openai_chat, openai_embed, whisper, pinecone)
│   ├── storage/                   ← было db/  (+ StorageAdapter Protocol после R2)
│   ├── tools/                     ← было tools/
│   └── utils/                     ← было utils/
│
├── channels/                      ← capture layer (как данные приходят)
│   └── telegram/
│       ├── guest_bot/             ← было bot_guest/
│       └── common/                ← было bot_common/
│
├── presentations/                 ← admin-facing UI (как данные показываются)
│   ├── telegram_admin/            ← было bot_admin/
│   └── http_api/                  ← было api/
│
├── templates/                     ← готовые bundle'ы под индустрию
│   ├── tg-restaurant/             ← наш текущий setup (первый template)
│   │   ├── config.yaml
│   │   ├── prompts/               (override-able LLM-prompts)
│   │   ├── question_seed.json     (default questions для индустрии)
│   │   └── README.md
│   └── tg-clinic/                 ← stub второго template (доказательство extraction'а)
│       ├── config.yaml
│       └── README.md
│
├── clients/                       ← инстансы (git-ignored либо в private-репо)
│   └── _example/
│       ├── config.yaml            (template: tg-restaurant + overrides)
│       ├── .env.example
│       └── overrides/             (custom prompts/assets per client)
│
├── tests/                         ← остаётся как есть (но импорты обновлены)
├── docs/
│   ├── ARCHITECTURE.md            ← новый: диаграмма слоёв
│   ├── ONBOARDING_CLIENT.md       ← новый: как добавить клиента
│   ├── TEMPLATE_AUTHORING.md      ← новый: как создать template
│   └── REFACTOR_M1_PLAN.md        ← этот файл
└── ... (pyproject.toml, deploy/, scripts/, etc. — не трогаем)
```

---

## Phase R1 — Структурный rename (механический move + import updates)

**Сложность:** низкая. **Риск:** низкий. **Время:** 1 день.

### File-mapping таблица (ИСТОЧНИК ПРАВДЫ)

| Старый путь | Новый путь |
|---|---|
| `agent/` | `core/agent/` |
| `agent/nodes/` | `core/agent/nodes/` |
| `agent/analytics_agent/` | `core/agent/analytics_agent/` |
| `services/` | `core/services/` |
| `integrations/` | `core/integrations/` |
| `db/` | `core/storage/` |
| `db/client.py` | `core/storage/supabase_client.py` |
| `db/migrations/` | `core/storage/migrations/` |
| `tools/` | `core/tools/` |
| `utils/` | `core/utils/` |
| `bot_guest/` | `channels/telegram/guest_bot/` |
| `bot_common/` | `channels/telegram/common/` |
| `bot_admin/` | `presentations/telegram_admin/` |
| `api/` | `presentations/http_api/` |

### Acceptance criteria для R1

1. **Все файлы перемещены** согласно таблице (через `git mv` чтобы сохранилась blame-история).
2. **Все `__init__.py`** созданы в новых пакетах (core/, channels/, presentations/ + sub-packages).
3. **Все импорты обновлены** в src + tests. Найти все вхождения старых путей:
   ```bash
   grep -rn "from agent\|from services\|from integrations\|from db\|from tools\|from utils\|from bot_guest\|from bot_admin\|from bot_common\|from api" --include="*.py" .
   ```
   После refactor'а grep должен возвращать 0.
4. **Entry points обновлены**: `bot_guest/__main__.py` → `channels/telegram/guest_bot/__main__.py`; запуск через `python -m channels.telegram.guest_bot`. Аналогично admin + api.
5. **Тесты переименованы** не обязательно — оставляем `tests/test_admin_agent.py` etc. как есть, но импорты обновляем.
6. **pyproject.toml** — обновить `[tool.setuptools.packages.find]` или явно перечислить новые пакеты.
7. **Pre-commit hooks** — обновить если что-то завязано на пути.
8. **`uv run pytest -q`** — все 462 теста зелёные.
9. **`uv run ruff check .`** + **`uv run mypy .`** — clean.
10. **Один коммит** `refactor(core): R1 — layered structure (core / channels / presentations)`.

### Не делать в R1

- НЕ менять логику ни в одной функции.
- НЕ менять сигнатуры.
- НЕ добавлять Protocol'ы (это R2).
- НЕ трогать docs/* кроме обновления import-references если есть.

---

## Phase R2 — Storage abstraction (StorageAdapter Protocol)

**Сложность:** средняя. **Риск:** средний. **Время:** 1-2 дня.

### Цель

Формализовать **StorageAdapter** как Protocol, чтобы services не звали Supabase напрямую. Это даёт:
- Замену хранилища без изменения services (`Postgres`, `Iiko API`, `Bitrix24 CRM` и т.д.)
- Чистые юнит-тесты с `InMemoryStorage` вместо `_FakeDB`
- Подготовку к sync-out adapter'ам (Bitrix24, webhooks)

### Структура R2

```
core/storage/
├── protocol.py              ← StorageAdapter (Protocol) + типы
├── supabase_client.py       ← было db/client.py
├── adapters/
│   ├── __init__.py
│   ├── supabase.py          ← SupabaseStorage(StorageAdapter)  — default
│   └── in_memory.py         ← InMemoryStorage  — для тестов
└── vector/
    ├── protocol.py          ← VectorStore (Protocol)
    └── pinecone.py          ← PineconeVectorStore
```

### Protocol скелет

```python
# core/storage/protocol.py
from typing import Protocol, TypedDict
from uuid import UUID
from datetime import datetime

class ClientRow(TypedDict):
    telegram_id: int
    name: str | None
    created_at: str

class SessionRow(TypedDict):
    id: str
    client_id: int
    started_at: str
    ended_at: str | None
    # ... (см. db/migrations/0001_init.sql для актуальной схемы)

class StorageAdapter(Protocol):
    # ─── Clients ───
    async def upsert_client(self, *, telegram_id: int, name: str | None) -> ClientRow: ...
    async def get_client(self, telegram_id: int) -> ClientRow | None: ...

    # ─── Sessions ───
    async def start_session(self, *, client_id: int) -> UUID: ...
    async def end_session(self, session_id: UUID) -> None: ...
    async def save_feedback_summary(self, session_id: UUID, *, raw_text: str, source: str, summary: dict, language: str | None) -> None: ...
    async def append_message(self, session_id: UUID, *, role: str, content: str) -> int: ...

    # ─── Answers ───
    async def save_answer(self, *, session_id: UUID, question_id: UUID, answer_text: str, marked_value: dict | None) -> int: ...

    # ─── Cards ───
    async def save_client_card(self, *, client_id: int, session_id: UUID, summary_text: str, pinecone_vector_id: str) -> UUID: ...

    # ─── Questions ───
    async def list_questions(self, *, active_only: bool) -> list[dict]: ...
    async def create_question(self, *, text: str, metric_key: str, expected_type: str, enum_values: list[str] | None, created_by: int | None) -> dict: ...
    async def update_question(self, question_id: UUID, *, text: str | None = None, enum_values: list[str] | None = None, is_active: bool | None = None) -> dict: ...

    # ─── Admin auth ───
    async def is_admin(self, telegram_id: int) -> bool: ...
    async def add_admin(self, *, telegram_id: int, name: str | None, invited_by: int | None) -> None: ...

    # ─── Analytics queries ───
    async def query_sessions_window(self, *, date_from: datetime | None, date_to: datetime) -> list[SessionRow]: ...
    async def query_answers_for_metric(self, *, metric_key: str, date_from: datetime, date_to: datetime) -> list[dict]: ...
    # ... (рост по мере refactor'а services/analytics.py)
```

### Migration strategy

1. **Внутри R2** — не менять API services-функций. Они продолжают экспортироваться с теми же сигнатурами, но внутри зовут `storage.X()` вместо `get_supabase().table(...).execute()`.
2. **Bootstrap** — entry points (`channels/.../__main__.py`, `presentations/.../__main__.py`) создают `SupabaseStorage()` и передают в services через **module-level singleton** или через `contextvars.ContextVar`.
3. **Тесты** — постепенно мигрируют с `_FakeDB` на `InMemoryStorage`. **Этот мигрейшен не обязателен в R2** — можно отложить. R2 считается завершённой когда production-код использует Protocol, а тесты могут оставаться как есть (`_FakeDB` будет всё ещё работать через старый shim).
4. **VectorStore** — тот же паттерн для Pinecone.

### Acceptance criteria для R2

1. `core/storage/protocol.py` существует и экспортирует `StorageAdapter` Protocol.
2. `SupabaseStorage(StorageAdapter)` имплементация в `core/storage/adapters/supabase.py`.
3. Все функции в `core/services/*` принимают `storage: StorageAdapter` через DI (либо явный параметр, либо ContextVar).
4. Нет ни одного прямого вызова `get_supabase()` или `.table(...)` за пределами `core/storage/adapters/supabase.py`.
5. Аналогично для Pinecone: `VectorStore` Protocol + `PineconeVectorStore` impl. Все вызовы Pinecone вне adapter'а — удалены.
6. `uv run pytest -q` зелёный (462+ тестов).
7. `uv run ruff check .` + `uv run mypy .` clean.
8. Один коммит `refactor(storage): R2 — StorageAdapter Protocol + Supabase/Pinecone adapters`.

### Не делать в R2

- НЕ имплементировать другие adapter'ы (Iiko, Bitrix24, etc.) — это для конкретных клиентов, не сейчас.
- НЕ мигрировать тесты с `_FakeDB` на `InMemoryStorage` — отдельная задача.
- НЕ менять схему БД.

---

## Phase R3 — Template system + bootstrap loader

**Сложность:** средняя. **Риск:** средний. **Время:** 1-2 дня.

### Цель

Сделать `python -m waiter clients/<name>` точкой запуска, которая читает `config.yaml`, выбирает template, бутстрапит storage + channels + presentations, и запускает приложение.

### Структура

```
core/bootstrap/
├── __init__.py
├── loader.py            ← load_client(client_dir) -> AppContext
├── context.py           ← AppContext dataclass
└── registry.py          ← регистр channels/presentations factory-функций

templates/tg-restaurant/
├── config.yaml          ← default config
├── prompts/             ← override-able LLM prompts (jinja-able)
│   ├── dialogue.txt
│   ├── analyze.txt
│   └── card.txt
├── question_seed.json   ← seed для пустого admin_users
└── README.md

clients/_example/
├── config.yaml          ← клиентский config (template ref + overrides)
├── .env.example         ← клиентские env-переменные
└── overrides/           ← пользовательские overrides (опц.)
    ├── prompts/
    └── assets/
```

### Config schema

```yaml
# templates/tg-restaurant/config.yaml — DEFAULT для индустрии
name: "Telegram Restaurant Feedback"
version: "1.0"

channels:
  - id: telegram_guest
    token_env: TELEGRAM_GUEST_BOT_TOKEN

presentations:
  - id: telegram_admin
    token_env: TELEGRAM_ADMIN_BOT_TOKEN
  - id: http_api
    port_env: API_PORT
    cors_origins_env: ALLOWED_MINI_APP_ORIGINS

storage:
  primary:
    type: supabase
    url_env: SUPABASE_URL
    key_env: SUPABASE_SERVICE_ROLE_KEY
  vector:
    type: pinecone
    api_key_env: PINECONE_API_KEY
    index_env: PINECONE_INDEX
    namespace_env: PINECONE_NAMESPACE

prompts:
  dialogue: prompts/dialogue.txt
  analyze: prompts/analyze.txt
  card: prompts/card.txt

question_seed: question_seed.json
```

```yaml
# clients/_example/config.yaml — клиентский config
template: tg-restaurant
name: "Example Restaurant"

# любые поля из template можно перекрыть здесь
branding:
  bot_name: "Example Bot"

# или указать другие пути к промтам
overrides:
  prompts:
    dialogue: overrides/prompts/dialogue.txt
```

### Bootstrap entry point

```python
# core/bootstrap/__main__.py — запуск:
#   python -m core.bootstrap clients/example

import sys
from pathlib import Path
from core.bootstrap.loader import load_client

if __name__ == "__main__":
    client_dir = Path(sys.argv[1])
    ctx = load_client(client_dir)
    ctx.run()  # запускает все registered channels + presentations
```

### Acceptance criteria для R3

1. `core/bootstrap/loader.py` существует с `load_client(client_dir) -> AppContext`.
2. `templates/tg-restaurant/config.yaml` — текущий setup как первый template.
3. `templates/tg-restaurant/prompts/*.txt` — извлечённые LLM-prompts (из `core/agent/prompts.py` константы).
4. `clients/_example/` — пример client'а, который ссылается на `tg-restaurant` template и не имеет overrides.
5. `python -m core.bootstrap clients/_example` запускает все каналы и presentations (если есть env-переменные).
6. **Существующие entry points** (`channels/telegram/guest_bot/__main__.py` и т.д.) — продолжают работать как есть для backward-compat в dev.
7. Один или два коммита: `refactor(bootstrap): R3 — template loader + config schema` + `refactor(bootstrap): R3 — extract tg-restaurant template`.

### Не делать в R3

- НЕ удалять старые entry points в `channels/telegram/guest_bot/__main__.py` etc.
- НЕ создавать `clients/<реальный_клиент>/` — только `_example/`.
- НЕ делать sync-out adapter'ы.

---

## Phase R4 — Documentation + второй template (extraction proof)

**Сложность:** низкая. **Риск:** низкий. **Время:** 0.5 дня.

### Дельверы

1. **`docs/ARCHITECTURE.md`** — high-level overview:
   - Диаграмма слоёв (core / channels / presentations / templates / clients)
   - Что НЕ меняется (core) vs что меняется (channels, presentations, storage adapters, prompts)
   - Поток данных: feedback → core → storage; analytics: storage ← core ← admin
   - Список «модулей» сейчас (telegram channel, supabase storage, http_api presentation, ...)

2. **`docs/ONBOARDING_CLIENT.md`** — пошагово как добавить нового клиента (создать `clients/X/`, заполнить env, deploy).

3. **`docs/TEMPLATE_AUTHORING.md`** — как создать новый template (когда копировать `tg-restaurant`, что переопределять, где жить).

4. **`templates/tg-clinic/`** — stub второго template для индустрии «клиники / салоны». Минимум:
   - `config.yaml` с другими дефолтными вопросами / другой prompt-tone
   - `prompts/dialogue.txt` с «эстетично-медицинским» tone
   - `question_seed.json` с релевантными вопросами (5-7 шт.)
   - `README.md` с описанием
   - Это доказывает что R3 extraction работает.

5. **Update top-level `README.md`** в проекте: краткий рассказ про template-based архитектуру, ссылка на `docs/ARCHITECTURE.md`.

### Acceptance criteria для R4

1. 4 doc-файла + 1 template-stub.
2. `templates/tg-clinic/` запускается через `clients/_example_clinic/` (если создать минимальный config).
3. Один коммит `docs(architecture): R4 — M1 architecture docs + tg-clinic template stub`.

---

## Архитектурные инварианты (для всех фаз)

1. **Hard break** — не оставляем backward-compat шимы импортов. Тесты обновляем разом.
2. **services/* всё async**, принимают `storage: StorageAdapter` через DI (после R2).
3. **Никаких прямых вызовов `get_supabase()` / Pinecone из бизнес-логики** — только через Protocol.
4. **Templates НЕ содержат secrets** — только refs на env-переменные.
5. **Clients/ — НЕ в основной репо публично** (gitignored либо в private-репозитории).
6. **Conventional Commits** — каждая фаза = один коммит (R3 может быть 2 коммитами: bootstrap + template extraction).
7. **`uv run pytest -q` + `uv run ruff check .` + `uv run mypy .`** должны быть зелёные ПОСЛЕ КАЖДОЙ ФАЗЫ.
8. **Pre-commit hooks** обязательны.
9. **Pre-commit fail → новый коммит**, не `--amend` (см. `docs/GIT.md`).

---

## Workflow выполнения — phase checkpoint sign-off

После КАЖДОЙ фазы (R1, R2, R3, R4):

1. **team-lead** делает финальный self-check: suite зелёный + ruff + mypy clean.
2. **team-lead** коммитит фазу одним коммитом.
3. **team-lead** SendMessage'ит куратору с отчётом: SHA, файлы, тесты до/после, ratification дрейфов.
4. **team-lead** ЖДЁТ sign-off куратора прежде чем переходить к следующей фазе.
5. **Куратор** делает Read коммита, проверяет, отвечает «GO R<N+1>» либо корректировки.

Это даёт 4 контролируемые точки. Если что-то пошло не так на фазе R1 — последствия минимальны.

---

## Out of scope (отдельные задачи, потом)

- Sync-out adapter'ы (Bitrix24, webhooks, Slack) — нужны конкретному клиенту, не сейчас.
- Multi-tenant shared-infra (RLS) — решено идти per-client deploy.
- Pricing/billing layer — Q4 отложен.
- Marketing-сайт — следующий этап.
- Mini App — после завершения R4.
- Тестовая миграция `_FakeDB` → `InMemoryStorage` — отдельная задача, не блокирует R2.
