# HTTP API — admin Mini App backend (Phase 4A)

Этот модуль (`api/*`) — тонкая HTTP-обёртка над `services/analytics` и
`agent.nodes.admin_ask`. **Здесь нет бизнес-логики.** Бот (`bot_admin`) и
API — два независимых entry points, оба зовут одни и те же services
прямым Python-import.

Frontend admin Mini App **живёт в отдельном репозитории**
`telegram-waiter-admin-miniapp` — это инстанс, склонированный из публичного
template `telegram-miniapp-template-vite` (Phase 4B). Текущий репозиторий
содержит только backend + auth.

## Запуск

```bash
uv run python -m api
# host/port — через env: API_HOST=0.0.0.0 API_PORT=8000
```

Минимально нужные env (см. `.env.example`):

- `MINI_APP_SESSION_SECRET` — секрет для подписи JWT (32+ байт)
- `ALLOWED_MINI_APP_ORIGINS` — CORS allowlist (comma-separated; никогда `*`)
- `TELEGRAM_ADMIN_BOT_TOKEN` — нужен для валидации Telegram initData
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — для проверки `admin_users`

## Auth flow

1. Mini App открывается из Telegram → получает `window.Telegram.WebApp.initData`
2. `POST /admin/auth { init_data }` → backend валидирует HMAC по
   bot-token, проверяет наличие telegram_id в `admin_users`, выдаёт JWT
3. Все остальные `/admin/*` ждут `Authorization: Bearer <jwt>`

JWT TTL = 24 ч (см. `api/auth/jwt.py`). При revoke админа из таблицы
`admin_users` — следующий же запрос вернёт 401 (проверка живёт в
`current_admin` dependency).

## Endpoints

```bash
# 1) Auth — обменять initData на JWT
curl -X POST http://localhost:8000/admin/auth \
  -H 'Content-Type: application/json' \
  -d '{"init_data": "auth_date=...&user=...&hash=..."}'

# 2) Overview — сводка за период
curl 'http://localhost:8000/admin/overview?date_from=2026-01-01&date_to=2026-01-31' \
  -H "Authorization: Bearer $JWT"

# 3) Metrics — динамика метрики (number → avg/min/max, enum/boolean → распределение)
curl 'http://localhost:8000/admin/metrics?metric_key=service_rating&date_from=2026-01-01&date_to=2026-01-31&group_by=day' \
  -H "Authorization: Bearer $JWT"

# 4) Topics — гистограмма топиков
curl 'http://localhost:8000/admin/topics?date_from=2026-01-01&date_to=2026-01-31&sentiment=negative' \
  -H "Authorization: Bearer $JWT"

# 5) Semantic search — естественный поиск по сессиям
curl -X POST http://localhost:8000/admin/semantic \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $JWT" \
  -d '{"query": "жалобы на ожидание", "top_k": 10}'

# 6) Client profile — карточка клиента по telegram_id
curl 'http://localhost:8000/admin/clients/123456' \
  -H "Authorization: Bearer $JWT"

# 7) Ask — естественный вопрос через admin_ask agent (tool-calling)
curl -X POST http://localhost:8000/admin/ask \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $JWT" \
  -d '{"question": "Что чаще всего жалуются за последнюю неделю?"}'

# 8) Settings — настройки текущего админа (theme/language/notifications)
curl 'http://localhost:8000/admin/settings' \
  -H "Authorization: Bearer $JWT"

# 9) Settings update — частичный PATCH (присылай только меняющиеся поля)
curl -X PUT http://localhost:8000/admin/settings \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $JWT" \
  -d '{"theme": "dark", "language": "en", "notifications_enabled": false}'

# 10) Sessions — список сессий за период (+ optional sentiment, пагинация)
curl 'http://localhost:8000/admin/sessions?date_from=2026-01-01&date_to=2026-01-31&sentiment=negative&limit=50&offset=0' \
  -H "Authorization: Bearer $JWT"

# 11) Session detail — полный таймлайн сессии (transcript + answers + card)
curl 'http://localhost:8000/admin/sessions/<session_id>' \
  -H "Authorization: Bearer $JWT"

# 12) Topic → clients — клиенты по теме
curl 'http://localhost:8000/admin/topics/сервис/clients?date_from=2026-01-01&date_to=2026-01-31' \
  -H "Authorization: Bearer $JWT"

# 13) Category → clients — клиенты по значению enum-метрики
curl 'http://localhost:8000/admin/metrics/visit_recency/clients?value=Больше%20года&date_from=2026-01-01&date_to=2026-01-31' \
  -H "Authorization: Bearer $JWT"

# 14) Clients — поиск по имени/id ИЛИ мультифильтр по темам
curl 'http://localhost:8000/admin/clients?query=Alice' -H "Authorization: Bearer $JWT"
curl 'http://localhost:8000/admin/clients?topics=сервис&topics=еда&match=and' -H "Authorization: Bearer $JWT"
```

`GET/PUT /admin/settings` — на текущего админа (telegram_id берётся из JWT,
тело параметра не несёт). `theme ∈ {light, dark, system}`, `language ∈ {uk, en}`,
`notifications_enabled: bool`. Отсутствие строки в `admin_settings` = дефолты
(`system` / `uk` / `true`); PUT — partial update, незаданные поля не трогаются.

**Drill-down (10–14)** — навигация вглубь агрегатов для Mini App:

- `GET /admin/sessions` → `{sessions: [{id, client_id, client_name, started_at,
  ended_at, sentiment, topics[], source}]}`. `sentiment ∈ {positive, neutral,
  negative}` (optional), пагинация `limit` (1..200, def 50) + `offset`.
- `GET /admin/sessions/{id}` → то же + `summary, messages[] (role/content/
  created_at), answers[] (question_text/answer_text/marked_value), card_summary`
  — всё, что произошло в сессии. 404, если сессии нет.
- `GET /admin/topics/{topic}/clients` и
  `GET /admin/metrics/{metric_key}/clients?value=…` →
  `{clients: [{telegram_id, name, sessions_count, last_session_at,
  avg_sentiment}]}`. Деталь клиента — `GET /admin/clients/{telegram_id}` (#6).
  Category-эндпоинт отдаёт 404 на несуществующий `metric_key`.
- `GET /admin/clients` — `?query=` (имя или telegram_id) **или**
  `?topics=a&topics=b&match=and|or` (мультифильтр; `and` = пересечение, сужает;
  default `and`). Ровно один из `query`/`topics` обязателен, иначе 400.

## Out of scope сейчас

- WebSocket / streaming
- Production deploy / nginx / SSL termination
- Admin agent CRUD (`bot_admin/handlers/admin_agent.py`) — HTTP-обёртки
  пока нет, MVP-фокус только на analytics
