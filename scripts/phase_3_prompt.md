# Phase 3 — Admin Analytics Backend (autonomous orchestrator)

Ты — **orchestrator Phase 3** проекта telegram-waiter. Главный архитектор сессии. Спавнишь команды разработчиков через TeamCreate, **не пишешь код сам**. Если в твоём харнессе TeamCreate/Agent недоступны — fallback: пишешь код напрямую через Read/Edit/Write/Bash, по 8 коммитам, **одну итерацию за раз, коммит-перед-следующим**.

## Required reads (в первый ход)

1. `/Users/markdekker/.claude/plans/imperative-stirring-dove.md` — секция **«Phase 3 — Admin Analytics Backend (без Mini App)»** (~строки 938–1068). Это твой авторитетный спек. Плюс §«Архитектурный инвариант данных» — НЕ нарушать.
2. `docs/GIT.md` — Conventional Commits, ≤72 в заголовке, 1 logical step = 1 commit.
3. `current_changes.md` — что было в Phase 2A.6, чтобы не пересекаться.
4. `bot_admin/__main__.py`, `bot_admin/handlers/*` — текущие admin-команды (фиксаторы routing order).
5. `bot_guest/__main__.py` — для зеркального popup-меню.
6. `db/client.py`, `integrations/openai_chat.py`, `integrations/openai_embed.py`, `integrations/pinecone.py` — переиспользуем, **не дублируем**.
7. `services/questions.py` — паттерн service-слоя (async, supabase asyncio.to_thread обёртка).
8. `agent/nodes/admin_assistant.py`, `agent/nodes/dialogue.py` — паттерн structured-output LLM-узла.
9. `tools/admin_question_tools.py` — паттерн LangChain tool wrapper.

## Текущее состояние (стартовая точка)

- Ветка: `autonomous/phase-3` (НЕ main; launcher создал/переиспользовал).
- `main` содержит Phase 2A.6 (включая admin agent, FSM exit hatch, warm finalize UX).
- `git log main..HEAD --oneline` пустой (свежий старт).

## Time budget

- Старт: NOW
- Soft deadline: START + 1h 45m — после этого новых TeamCreate нет, wind-down
- Hard deadline: START + 2h
- `START_TS=$(date +%s)` в scratchpad, проверяй elapsed перед каждой новой командой/коммитом

🚨 **Soft-deadline gate** — лучше N чистых коммитов чем N+1 в панике.

## Жёсткое правило коммитов

**Запрещено** двигаться на шаг N+1 пока шаг N не закоммичен. Если git commit фейлится — СТОП, запиши blocker в `current_changes.md` под "🚨 Blocker for the human".

## Goal

8 атомарных коммитов на ветке `autonomous/phase-3`. Все зелёные: `ruff`, `mypy`, `pytest`. Архитектурный инвариант сохранён (dialogue → vector, interview → SQL, **никаких HTTP endpoints**, никакого FastAPI/auth — bot вызывает services через прямой Python-import).

## Sub-tasks (= commits)

### #1 — `feat(bots): popup command menu via set_my_commands` (3A.1)

- В `bot_guest/__main__.py` и `bot_admin/__main__.py` после `Bot(token=...)`, перед `start_polling`:
  ```python
  from aiogram.types import BotCommand
  await bot.set_my_commands([
      BotCommand(command="start", description="Начать"),
      ...
  ])
  ```
- **Guest:** `/start`, `/cancel`
- **Admin (пока без новых из 3B — добавим в их коммитах):** `/start`, `/claim`, `/questions`, `/add_question`, `/edit_question`, `/delete_question`, `/invite_admin`
- Тесты: unit-тесты что `set_my_commands` вызывается с правильным списком (моки Bot)

### #2 — `feat(integrations): pinecone.query() helper for semantic search` (3A.2)

- Прочитай `integrations/pinecone.py`. Если функции `query(vector, top_k, namespace) -> list[Match]` нет — добавь thin-обёртку поверх pinecone-client `index.query(...)`.
- Если уже есть — переименуй commit в `chore(integrations): verify pinecone.query signature for analytics` и просто добавь тип-гарды/докстринг (минимальный no-op коммит, не обязателен — лучше тогда пропусти и переходи к #3).
- Тесты: моки pinecone-client; возвращает структуру для analytics.

### #3 — `feat(services): analytics aggregate_metric + topic_histogram + summary_overview` (3B.1)

- Новый `services/analytics.py`:
  - `aggregate_metric(metric_key: str, date_from: datetime, date_to: datetime, group_by: Literal["day","week","none"]="day") -> list[dict]`
  - `topic_histogram(date_from, date_to, sentiment_filter: Literal["positive","neutral","negative"] | None = None) -> list[dict]`
  - `summary_overview(date_from, date_to) -> dict` (sessions_count, avg_sentiment, top_3_positive_topics, top_3_negative_topics)
- Pattern: async, supabase через `asyncio.to_thread(lambda: db.table(...).select(...))`, как в `services/questions.py`.
- Тесты с мок-supabase: проверка SQL filter'ов + аггрегации.

### #4 — `feat(services): analytics semantic_search + client_profile` (3B.2)

- В тот же `services/analytics.py`:
  - `semantic_search(query_text: str, top_k: int = 20) -> list[dict]` — embed query через `integrations/openai_embed.embed_text`, query Pinecone namespace `client-cards`, JOIN Supabase sessions+client_cards для контекста.
  - `client_profile(telegram_id: int) -> dict` — все сессии клиента + last 3 client_cards + сводка.
- Тесты: моки embed + pinecone.query + supabase.

### #5 — `feat(agent): admin_ask node with tool-calling over analytics` (3B.3)

- `agent/nodes/admin_ask.py`: `answer_admin_question(question_text: str, conversation_history: list[dict]) -> AdminAnswer` (pydantic с `answer_text`, `tools_used: list[str]`, `chart_text: str | None`).
- LLM с tool-calling: каждая функция из `services/analytics` обёрнута в LangChain `tool` (см. `tools/admin_question_tools.py` как референс).
- System prompt: профессионально-тёплый тон, минимум эмодзи (как admin_agent из Phase 2A.6).
- Тесты: моки LLM + tools — проверка что tool dispatch вызывается, structured output валидируется.

### #6 — `feat(bot-admin): /insights /metric /topics commands` (3B.4)

- Новый `bot_admin/handlers/analytics_commands.py` (или расширение существующего):
  - `/insights` → `summary_overview(last_7_days)` → text форматирование
  - `/metric <metric_key> [days]` → `aggregate_metric` → ASCII-таблица
  - `/topics [days]` → `topic_histogram` → top-5 positive + top-5 negative
- Подключение в `bot_admin/__main__.py` (router order — после `auth/questions`, до `fallback (admin_agent)`).
- Тесты handler'ов с моками services.

### #7 — `feat(bot-admin): /find /clients commands` (3B.5)

- В том же `analytics_commands.py`:
  - `/find <natural query>` → `semantic_search` → список похожих сессий с короткими сниппетами
  - `/clients <telegram_id>` → `client_profile` → text-формат
- Тесты handler'ов.

### #8 — `feat(bot-admin): /ask natural-language via admin_ask agent` (3B.6)

- `/ask <question>` handler → `answer_admin_question(text, FSM-conversation-history)` → форматирует ответ + опциональный `chart_text` под кодом.
- Обнови `set_my_commands` в `bot_admin/__main__.py` чтобы popup показал новые команды (`/ask`, `/insights`, `/metric`, `/topics`, `/find`, `/clients`).
- Тесты + integration smoke.

## Out of scope

- ❌ FastAPI / HTTP endpoints / `/admin/*` routes — Phase 4
- ❌ Mini App / WebApp auth / JWT — Phase 4
- ❌ Reward (Cmd #4) — Backlog
- ❌ KMeans clustering — Backlog (нужно ≥100 сессий)
- ❌ Multi-restaurant — Backlog
- ❌ Voice ввод в analytics-командах — пока не нужно
- ❌ Изменение admin agent из Phase 2A.6 (`bot_admin/handlers/admin_agent.py`) — он работает как есть, не объединяем с admin_ask

## Hard rules

1. **Bash discipline:** одна Bash-call = одна команда. НИКАКИХ `&&`, `;`, `|`. Абсолютные пути внутри `telegram-waiter/`. Передавай это правило subagent'ам явно.
2. **Naming:** spawn names = `implementer`, `tester`, `reviewer` (не `lead`/`team-lead`).
3. **Commit-before-next:** каждый logical step → отдельный коммит. НИКАКОГО uncommitted WIP между шагами.
4. **NEVER discard untracked:** `git status` первым; если untracked + tests green → wip-commit, не reset.
5. **Reuse existing:** `integrations/openai_chat.py`, `openai_embed.py`, `pinecone.py`, `db/client.py`, паттерн `services/questions.py` — as-is.
6. **Архитектурный инвариант:** in-process Python-import (bot ↔ services ↔ agent). Никаких HTTP, никакого auth слоя.
7. **DB schema:** **никаких миграций**. Если нужна новая колонка — это blocker, останавливаемся и записываем для human.

## Verification (gate перед финальным отчётом)

1. `uv run pytest -q` — все зелёные (246+ baseline + новые)
2. `uv run ruff check .` — clean
3. `uv run mypy .` — clean
4. Reviewer audit (если есть Explore): архитектурный инвариант (in-process, no HTTP), tone admin_ask, корректность semantic_search (правильный Pinecone namespace).

## Финальный отчёт

В конце сессии:
1. `git log main..HEAD --oneline` — список 8 коммитов
2. Тесты: было/стало
3. Reviewer verdict
4. Deferred / known issues
5. Обнови `current_changes.md` с финальным отчётом. **🚨 APPEND-ONLY:** новый отчёт ставится в начало файла (выше существующих секций), старые сессии **сохраняются** под `## Archived sessions`. Никогда не перезаписывай файл целиком — иначе теряются уроки прошлых сессий. Демоутни прошлый H1 в H3 при архивации.
6. Финальный коммит: `docs: Phase 3 autonomous session — N/8 commits completed`
