# Phase 4A — HTTP API над services (autonomous orchestrator)

Ты — **orchestrator Phase 4A**. Главный архитектор сессии. Спавнишь команду разработчиков через TeamCreate, **не пишешь код сам**. Если в твоём харнессе TeamCreate/Agent недоступны — fallback: пишешь код напрямую через Read/Edit/Write/Bash, по 5 коммитам, **одну итерацию за раз, коммит-перед-следующим**.

## Required reads (в первый ход)

1. `/Users/markdekker/.claude/plans/imperative-stirring-dove.md` — секция **«Phase 4 — Admin Mini App + WebApp HTTP API»** → подсекция **«4A. HTTP API над уже существующими services»** (~строки 1071–1112).
2. `docs/GIT.md` — Conventional Commits, ≤72 в заголовке, 1 logical step = 1 commit.
3. `current_changes.md` — что было в Phase 3+3.5 (для понимания готового surface).
4. `services/analytics.py` — все 5 функций готовы, **переиспользуем как есть**.
5. `agent/nodes/admin_ask.py` — admin_ask agent, **переиспользуем**.
6. `config.py` — паттерн добавления env vars через pydantic Settings.
7. `pyproject.toml` — пакет-менеджмент через `uv add <pkg>`.

## Текущее состояние (стартовая точка)

- Ветка: `autonomous/phase-4a` (НЕ main; launcher создал/переиспользовал).
- `main` содержит Phase 3 + 3.5 (analytics services, admin_ask agent, mode toggle, categorical_distribution).
- `git log main..HEAD --oneline` пустой (свежий старт).
- 333 тестов baseline, ruff/mypy clean.

## Time budget

- Старт: NOW
- Soft deadline: START + 1h 30m — после этого новых TeamCreate нет, wind-down
- Hard deadline: START + 2h
- `START_TS=$(date +%s)` в scratchpad, проверяй elapsed перед каждой новой командой/коммитом

🚨 **Soft-deadline gate** — лучше 4 чистых коммитов чем 5 в панике.

## Goal

5 атомарных коммитов на ветке `autonomous/phase-4a`. Все зелёные: `ruff`, `mypy`, `pytest`. Архитектурный инвариант: **bot и api/* — два независимых entry points, оба зовут одни и те же services через прямой Python-import**. Никакого дублирования бизнес-логики в api/* — это **только тонкая HTTP-обёртка + auth**.

## Sub-tasks (= commits)

### #1 — `chore(deps): add fastapi + uvicorn + pyjwt for HTTP API`

- `uv add fastapi uvicorn pyjwt` (через `Bash(uv add:*)` — allowlist'нут launcher'ом).
- Проверить что `pyproject.toml` и `uv.lock` обновились.
- Никаких других правок в этом коммите.

### #2 — `feat(config): MINI_APP_SESSION_SECRET + ALLOWED_MINI_APP_ORIGINS env`

- В `config.py` (Settings): два новых поля
  - `mini_app_session_secret: str = ""` — JWT secret (для local dev можно пустую default; api должен валидировать что non-empty при запуске)
  - `allowed_mini_app_origins: str = ""` — comma-separated origins для CORS
- Обнови `.env.example` соответствующими ключами + комментарии.
- Никаких HTTP-роутов в этом коммите.

### #3 — `feat(api): Telegram initData validation + JWT issue/verify`

- Создай дерево:
  - `api/__init__.py` — пусто или с docstring
  - `api/auth/__init__.py`
  - `api/auth/telegram_webapp.py`:
    - `validate_initdata(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> TelegramUser`
    - HMAC-SHA256 по [Telegram WebApp docs](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)
    - Returns pydantic `TelegramUser(id: int, username: str | None, first_name: str | None, ...)`
    - Raises `ValueError` если подпись неверна или `auth_date` слишком старый
  - `api/auth/jwt.py`:
    - `issue_token(telegram_id: int, secret: str, ttl_seconds: int = 86400) -> str`
    - `verify_token(token: str, secret: str) -> dict` (raise ValueError на expired/bad)
    - Используй `pyjwt` (НЕ `python-jose` — `pyjwt` легче и достаточно).
- Тесты:
  - `tests/test_api_telegram_initdata.py` — мок с известным bot_token + правильно подписанной строкой → returns TelegramUser; неверный hash → ValueError; старый auth_date → ValueError
  - `tests/test_api_jwt.py` — round-trip, expired, bad-secret cases

### #4 — `feat(api): admin routes — auth, overview, metrics, topics`

- `api/main.py`:
  - FastAPI app, CORS middleware читает `settings.allowed_mini_app_origins.split(",")` (только non-empty)
  - Подключает `routes.admin.router`
- `api/deps/__init__.py`, `api/deps/auth.py`:
  - `current_admin(authorization: str = Header(...)) -> int` — парсит `Bearer <jwt>`, verify_token, проверяет в БД что telegram_id есть в `admin_users` (используй `services.admin_auth.is_admin`), возвращает telegram_id
- `api/schemas/__init__.py`, `api/schemas/admin.py`:
  - `AuthRequest(init_data: str)`, `AuthResponse(token: str)`
  - `OverviewQuery(date_from, date_to)`, `OverviewResponse(... поля из SummaryOverview)`
  - `MetricsQuery(metric_key, date_from, date_to, group_by)`, `MetricsResponse`
  - `TopicsQuery(date_from, date_to, sentiment)`, `TopicsResponse`
- `api/routes/__init__.py`, `api/routes/admin.py`:
  - `POST /admin/auth` — validate_initdata → check is_admin → issue JWT
  - `GET /admin/overview` — `Depends(current_admin)` + `summary_overview` из services
  - `GET /admin/metrics` — `aggregate_metric` или `categorical_distribution` (по expected_type, см. handlers/analytics_commands.cmd_metric pattern)
  - `GET /admin/topics` — `topic_histogram`
- Тесты с `fastapi.testclient.TestClient`:
  - 401 без Authorization header
  - 401 с невалидным JWT
  - 200 с моком services
  - CORS preflight OPTIONS returns правильные headers для allowed origin

### #5 — `feat(api): admin routes — semantic, clients, ask + uvicorn entrypoint`

- В `api/routes/admin.py` доделай:
  - `POST /admin/semantic { query, top_k }` → `semantic_search`
  - `GET /admin/clients/{telegram_id}` → `client_profile`, 404 на LookupError
  - `POST /admin/ask { question, history? }` → `answer_admin_question`
- `api/__main__.py` (или просто пример в README):
  ```python
  import uvicorn
  from api.main import app
  if __name__ == "__main__":
      uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
  ```
- Обнови `README.md` (если есть) или `docs/` коротким разделом «HTTP API: `uv run python -m api`», + curl-примеры для всех 7 endpoint'ов.
- Тесты: оставшиеся 3 endpoint'a с моками services.

## Out of scope

- ❌ Mini App frontend (Phase 4B + 4C — отдельные сессии)
- ❌ Production deploy / nginx / SSL — это потом
- ❌ Изменение `services/analytics.py` или `agent/nodes/admin_ask.py` — они уже работают, не трогаем
- ❌ WebSocket / streaming — Backlog
- ❌ Изменение admin agent CRUD (`bot_admin/handlers/admin_agent.py`) — не нужно HTTP-обёртки для него; нужно только analytics-tools (admin_ask)

## Hard rules

1. **Bash discipline:** одна Bash-call = одна команда. НИКАКИХ `&&`, `;`, `|`. Абсолютные пути внутри `telegram-waiter/`. Передавай это правило subagent'ам явно.
2. **Naming:** spawn names = `implementer`, `tester`, `reviewer` (не `lead`/`team-lead`).
3. **Commit-before-next:** каждый logical step → отдельный коммит. НИКАКОГО uncommitted WIP между шагами.
4. **NEVER discard untracked:** `git status` первым; если untracked + tests green → wip-commit, не reset.
5. **Reuse existing:** `services/analytics.py`, `services/admin_auth.py`, `agent/nodes/admin_ask.py`, паттерн `bot_admin/handlers/analytics_commands.cmd_metric` (для enum/number routing) — переиспользуй.
6. **Никаких миграций БД** — Phase 4A только HTTP layer.
7. **JWT secret** — если `mini_app_session_secret == ""` при попытке issue/verify → raise RuntimeError с понятной ошибкой (fail-loud).
8. **CORS** — strict allowlist через env; никакого `allow_origins=["*"]`.

## Verification (gate перед финальным отчётом)

1. `uv run pytest -q` — все зелёные (333+ baseline + новые ~15-20)
2. `uv run ruff check .` — clean
3. `uv run mypy .` — clean
4. Reviewer audit (если есть Explore): no business logic в api/*, services/* и agent/* нетронуты, CORS strict, JWT correct.

## Финальный отчёт

В конце сессии:
1. `git log main..HEAD --oneline` — список 5 коммитов
2. Тесты: было/стало
3. Reviewer verdict
4. Deferred / known issues + готовность к Phase 4B/4C
5. Обнови `current_changes.md` с финальным отчётом. **🚨 APPEND-ONLY:** новый отчёт ставится в начало файла (выше существующих секций), старые сессии **сохраняются** под `## Archived sessions`. Никогда не перезаписывай файл целиком — иначе теряются уроки прошлых сессий. Демоутни прошлый H1 в H3 при архивации.
6. Финальный коммит: `docs: Phase 4A autonomous session — N/5 commits completed`
