# CLAUDE.md — telegram-waiter

Операционные инструкции для Claude (и куратора-человека) по работе с проектом.

> **TL;DR:** на крупных задачах не пиши «давай обсудим план». Сразу спавни команду через `TeamCreate` с готовыми промтами для ролей и следи через `TaskList`. Длинные сессии — через `scripts/run_autonomous.sh`.

---

## Локация и стек

- Корень: `/Users/markdekker/Need eat bot/telegram-waiter`
- Питон: 3.12, pyproject + uv (lockfile `uv.lock`, sync — `uv sync --frozen`)
- Stores: **Supabase** (Postgres) + **Pinecone** (vectors)
- LLM: **OpenAI** (chat + Whisper + embeddings) через LangChain/LangGraph

Модули (по слоям):

```
bot_guest/    — гость пишет фидбэк → интервью → карточка
bot_admin/    — управление вопросами, /statistics, /topics
api/          — FastAPI thin layer для Mini App (auth + 7 admin endpoint'ов)
services/    — бизнес-логика (analytics, statistics, sessions, clients, questions)
agent/nodes/  — LLM-узлы (analyze, dialogue, card, extract, admin_ask, ...)
tools/        — LangChain-обёртки над services (для LLM tool-calling)
integrations/ — openai_chat, openai_embed, whisper, pinecone
db/           — Supabase client + миграции
tests/        — unit-тесты под каждый модуль
deploy/       — systemd units + install.sh + CI deploy на VPS
scripts/      — автономный launcher + фазовые промты + seed_demo_data
```

---

## Workflow для имплементации (новый дефолт)

Claude в основном чате — **lead architect + curator**, не «писарь плана». Для крупных задач не оформляй «давай обсудим, я предлагаю A/B/C» — сразу разбивай на роли и спавни команду. Решения внутри согласованного scope принимай сам, спрашивай только то, что в списке «спрашиваю» ниже.

### Когда команда (`TeamCreate`)

Создавай команду, если задача попадает хотя бы под одно:

- ≥ 3 независимых шагов, которые могут идти параллельно
- ≥ 2 разные области (code + tests + migration; backend + frontend; etc.)
- > 30 минут работы (по оценке) или ≥ 150 строк диффа
- Хочешь явное разделение «писать код» / «писать тесты» / «ревьюить»

Если задача меньше — делай в основном диалоге сам.

### Шаблон спавна команды

```js
TeamCreate({
  team_name: "feat-<slug>",       // короткий kebab-case
  agent_type: "claude",
  description: "<одна строка цели>"
})

// 4 параллельных Agent-вызова в одном сообщении
Agent({ team_name: "feat-<slug>", name: "team-lead",
        subagent_type: "claude",          prompt: "<см. шаблон ниже>" })
Agent({ team_name: "feat-<slug>", name: "implementer",
        subagent_type: "general-purpose", prompt: "<см. шаблон ниже>" })
Agent({ team_name: "feat-<slug>", name: "tester",
        subagent_type: "general-purpose", prompt: "<см. шаблон ниже>" })
Agent({ team_name: "feat-<slug>", name: "reviewer",
        subagent_type: "Explore",         prompt: "<см. шаблон ниже>" })
```

Создавай команду **в одном сообщении** — иначе агенты не увидят друг друга в `config.json` команды.

### Промты ролей (шаблоны)

**team-lead** — оркестрирует, делит задачи через `TaskCreate`, раздаёт через `TaskUpdate owner`, коммитит, даёт sign-off:

```
Ты — team-lead команды feat-<slug>. Цель: <одно предложение>.

Контекст (читай в первый ход):
- CLAUDE.md в корне проекта (architectural invariants, что НЕ трогать)
- <конкретные файлы / docs / прошлые коммиты, релевантные задаче>

Твоя работа:
1. Раздели цель на 3-5 TaskCreate'ов. Заведи блокировки через addBlockedBy
   (тесты блокирует код, код блокирует ревью).
2. Раздай TaskUpdate({owner: "implementer" | "tester" | "reviewer"}).
3. Жди завершения; не лезь сам в чужие зоны.
4. Когда implementer закончил — попроси tester'а добавить тесты;
   когда tester'а — попроси reviewer'а проверить инварианты.
5. Сам делаешь только коммит и финальный отчёт.
6. Финальный отчёт куратору: branch, # коммитов, файлы, тесты до/после,
   ruff/mypy clean, next step одной строкой.

Инварианты:
- Conventional Commits (см. docs/GIT.md), 1 функция = 1 коммит.
- Никогда git push, никогда --no-verify.
- При красном pre-commit hook'е → новый коммит, не --amend.
```

**implementer** — пишет код:

```
Ты — implementer в команде feat-<slug>. Твоя зона: <конкретные файлы / модули>.

Перед написанием прочитай 2-3 соседних файла в той же папке — соблюдай
существующие конвенции (имена, порядок аргументов, async/sync, типизация).

Что делать:
1. Сигнатура: <если задана — здесь>. Если нет — выбери и опиши в комментарии.
2. Пиши минимум кода под задачу. Не добавляй обработку случаев, которых нет.
3. Type hints обязательно (mypy strict для services/* api/*).
4. Никаких "for future use", "just in case" абстракций.
5. Закончил — обнови свою TaskUpdate({status: "completed"}).

Зона ответственности — только <X>. Не пиши тесты (это tester).
```

**tester** — пишет unit-тесты:

```
Ты — tester в команде feat-<slug>. Покрываешь: <модуль/функция>.

Образец стиля: tests/test_services_statistics.py, tests/test_api_admin_routes_more.py.

Правила:
- Один тест-файл на модуль (test_<module>.py).
- Mock на уровне service-функций, НЕ на уровне db.client.
- Покрытие: happy path + 2-3 edge cases + 1 error case.
- Запусти: uv run pytest tests/test_<module>.py -q, потом весь pytest -q.
- Если есть mypy/ruff проблемы — исправь сразу.

Когда зелёное — TaskUpdate({status: "completed"}) + отчёт team-lead'у.
```

**reviewer** — только чтение, проверяет инварианты:

```
Ты — reviewer в команде feat-<slug>. Tools: All tools except Agent, Edit,
Write, NotebookEdit (Explore agent).

Прочитай диф (git diff main..HEAD --stat и потом по файлам). Проверь:
1. Соблюдены ли инварианты из CLAUDE.md (services async, тонкие handler'ы и т.д.)
2. Не дублируется ли уже существующий код в services/.
3. Нет ли лишних абстракций / "just in case" handling.
4. Тесты покрывают happy + edge + error пути.

Если всё ок → SendMessage to team-lead с "LGTM + одна строка".
Если найдено → SendMessage to team-lead с "<file>:<line> — <issue>".
НИЧЕГО не правь сам.
```

### Координация через TaskList

- `TaskList` показывает прогресс команды (TaskList привязан к команде 1:1).
- Куратор-человек может в любой момент `TaskList`/`TaskGet` и понять статус.
- team-lead раздаёт через `TaskUpdate({owner: "<name>"})`.
- Идлящие teammate'ы — норма, не сигнал «всё сломалось».

### Завершение команды

Когда все задачи completed и финальный отчёт получен:

```js
// graceful shutdown каждому teammate'у
SendMessage({to: "implementer", message: {type: "shutdown_request"}})
SendMessage({to: "tester",      message: {type: "shutdown_request"}})
SendMessage({to: "reviewer",    message: {type: "shutdown_request"}})
SendMessage({to: "team-lead",   message: {type: "shutdown_request"}})

TeamDelete()  // когда все завершились
```

---

## Когда команда НЕ нужна

| Сценарий | Делай |
|---|---|
| 1-3 файла, маленький патч | сам в основном диалоге |
| Чистый research («где определён X?») | одиночный `Agent({subagent_type: "Explore"})` |
| Архитектурный вопрос без кода | одиночный `Agent({subagent_type: "Plan"})` |
| Конкретный баг с локализованной причиной | сам в основном диалоге |

---

## Autonomous launcher (длинные сессии без человека)

`scripts/run_autonomous.sh` — обёртка для запуска Claude в tmux с 2-часовым бюджетом и слоями защиты.

### Запуск

```bash
# Generic 2h сессия по autonomous_session.md промту
./scripts/run_autonomous.sh --interactive

# То же, но headless (для CI / без терминала)
./scripts/run_autonomous.sh --headless

# Короткий smoke 5 мин (проверить инфру)
./scripts/run_autonomous.sh --smoke

# Фазовый промт (заранее подготовленный сценарий)
./scripts/run_autonomous.sh --phase-3       # admin analytics backend
./scripts/run_autonomous.sh --phase-4a      # HTTP API
./scripts/run_autonomous.sh --phase-4b      # Mini App template (в отд. репо)
./scripts/run_autonomous.sh --phase-4c      # Mini App instance (в отд. репо)

# Продолжить прошлую сессию (на её ветке)
./scripts/run_autonomous.sh --interactive --resume autonomous/<TS>
```

### Слои защиты

1. **Pre-session git tag** `pre-autonomous-<TS>` — точка отката на main.
2. **Isolation branch** `autonomous/<TS>` — Claude работает там, main не трогается.
3. **`--permission-mode dontAsk`** + ограниченный allowlist (см. `EXTRA_ALLOW` в `_autonomous_inner.sh`).
4. **`trap`** восстанавливает `.claude/settings.local.json` на любом выходе (Ctrl+C, kill, exit).
5. **Hard timeout 2h15m** в headless-режиме.

### Управление tmux

```bash
tmux attach -t waiter-auto       # подключиться (Ctrl+B затем D — отключиться)
tmux kill-session -t waiter-auto # прибить (settings восстановятся trap'ом)
```

### После сессии — review и merge

```bash
git log main..autonomous/<TS> --oneline       # что наделано
git diff main..autonomous/<TS> --stat

# принять:
git checkout main && git merge --no-ff autonomous/<TS>

# отбросить целиком:
git checkout main && git branch -D autonomous/<TS> && git tag -d pre-autonomous-<TS>

# аварийный сброс main до состояния до сессии:
git checkout main && git reset --hard pre-autonomous-<TS>
```

### Создание нового phase-промта

Когда хочешь спланировать новую крупную фазу:

1. Скопируй `scripts/phase_4a_prompt.md` как шаблон → `scripts/phase_<N>_prompt.md`.
2. Опиши в нём: задача, файлы, формат коммитов, критерии done.
3. Добавь case-ветку в `scripts/run_autonomous.sh` (около строки 22).
4. Запусти `./scripts/run_autonomous.sh --phase-<N>`.

`scripts/autonomous_session.md` — generic промт (lead architect + per-function loop). Подходит, когда конкретного плана фазы нет, но есть `docs/functions/` каталог задач.

---

## Что я (Claude) делаю сам, что спрашиваю

### Решаю сам (не спрашиваю)

- Технические детали внутри согласованной задачи: имена, паттерны, порядок коммитов.
- Какие тесты добавить.
- Какие subagent-типы использовать в команде.
- Стиль форматирования сообщений в боте.
- Внутреннюю структуру нового модуля.

### Спрашиваю один раз — потом еду

- Scope: «делаем X или сначала Y?» — после ответа НЕ переспрашиваю детали.
- Новая зависимость (`uv add ...`) — задокументировать в `current_changes.md`.
- Реальные мутации БД (Supabase prod / Pinecone prod) — для тестовых данных тоже спрашиваю.
- Удаление файлов / директорий.
- `git push` / деплой (CI деплоит сам после push, но первый раз стоит подтвердить).

### Никогда не делаю без явного запроса

- `git push --force`, `git reset --hard <pushed>`, `git commit --amend` после push.
- Правки `.env*` (кроме `.env.example`).
- Что-либо вне `/Users/markdekker/Need eat bot/telegram-waiter/`.
- `mcp__*__apply_migration`, `mcp__*__execute_sql`, любой MCP write.
- Установка системных пакетов (`brew`, `apt`).

---

## Архитектурные инварианты (для всех агентов и для меня)

1. **`services/*`** — бизнес-логика. Всё `async`. Каждая публичная функция принимает `db: Client | None = None` для тестируемости.
2. **`bot_*/handlers/*`** — тонкие aiogram-обёртки. Не содержат бизнес-логики, зовут только `services/*` и `agent/nodes/*`.
3. **`agent/nodes/*`** — LLM-узлы. Возвращают **pydantic-модель** через structured output (`response_model=...` в `chat_completion`).
4. **`tools/*`** — LangChain-обёртки над services для LLM tool-calling. Не содержат логики, только адаптация сигнатур.
5. **`api/*`** — FastAPI thin layer. Никакой бизнес-логики, только: pydantic-схемы + вызов `services.*`.
6. **Bot и api — два независимых entry point**, не зовут друг друга. Оба зовут одни и те же `services/*` напрямую через Python-import.
7. **Mock в тестах — на уровне service-функций**, не на уровне `db.client` (`patch("services.X.aggregate_metric", ...)` ✓; `patch("db.client.get_supabase", ...)` ✗ кроме редких случаев в `test_services_statistics.py`).
8. **Коммиты:** Conventional Commits, 1 логическое изменение = 1 коммит. Pre-commit hook'и обязательны (ruff + format + secrets-check).
9. **Pre-commit fail → новый коммит**, не `--amend` (см. `docs/GIT.md`).
10. **CORS / secrets:** allowlist через env (`ALLOWED_MINI_APP_ORIGINS`), никогда `*`. `MINI_APP_SESSION_SECRET` пустой → fail-loud (RuntimeError).

---

## Стандартный цикл «команда → результат»

```
1. Куратор формулирует задачу (одно сообщение).
2. Куратор сразу спавнит TeamCreate + 4 Agent (в одном сообщении).
3. team-lead раздаёт через TaskCreate/TaskUpdate.
4. implementer + tester работают параллельно (тесты блокируются кодом через addBlockedBy).
5. reviewer проверяет диф.
6. team-lead коммитит → SendMessage куратору «done, branch X, N commits».
7. Куратор проверяет, мерджит или возвращает с фидбэком.
8. Если ок — TeamDelete.
```

---

## Что почитать перед стартом крупной задачи

- `current_changes.md` — что было в прошлых autonomous-сессиях, какие решения уже приняты.
- `docs/GIT.md` — конвенции коммитов.
- `docs/ENVIRONMENTS.md` — ограничения окружения.
- `docs/HTTP_API.md` — контракт FastAPI для Mini App.
- `docs/LANGGRAPH.md` — паттерны LangGraph узлов.
- `db/migrations/0001_init.sql` — схема (источник правды по таблицам).
- `services/analytics.py` + `services/statistics.py` — текущая аналитика.
