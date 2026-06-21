# HTTP Guest API — public guest webapp backend (Phase 5)

Тонкий HTTP-слой над `core/services/guest_journey` и `core/agent/nodes/dig`.
Здесь нет бизнес-логики — только pydantic-схемы, маппинг ошибок и JWT-auth.

Гостевой webapp **живёт в отдельном репозитории** (Vite + React, деплой на
Vercel) — этот репозиторий держит только бэкенд. UX «вечер як стрічка»:
гость проходит ленту тактов вечера, ставит mood-оценки и теги, на слабых
тактах ИИ предлагает 2–3 карточки-гипотезы.

Mounted в основной uvicorn-процесс (`presentations.http_api.main:app`) под
префиксом `/guest`. Делит порт с админским API, но идёт через **независимый**
JWT-домен.

## Запуск

Тот же сервис, что и админ-API (`voice-api.service`):

```bash
uv run python -m presentations.http_api
# host/port — через env: API_HOST=0.0.0.0 API_PORT=8200
```

Минимально нужные env (см. `.env.example`):

- `GUEST_SESSION_SECRET` — секрет для подписи JWT гостевых сессий (32+ байт).
  Отдельный от админского `MINI_APP_SESSION_SECRET`.
- `ALLOWED_GUEST_ORIGINS` — CORS allowlist гостевого webapp (comma-separated;
  никогда `*`). Объединяется с `ALLOWED_MINI_APP_ORIGINS` в общий CORS-allowlist
  всего процесса.
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — для чтения journey + записи
  session_beats / session_digs.
- `OPENAI_API_KEY` — нужен `core/agent/nodes/dig` (структурированные гипотезы)
  и `core/agent/nodes/analyze` (вызывается на финализации сессии).

## Auth flow

JWT гостя — отдельный домен доверия от админа.

1. Гость открывает webapp (anonymous): `POST /guest/sessions` → бэк создаёт
   запись `sessions(feedback_source='web_anon', client_id=NULL)` и выдаёт JWT
   с `session_id`-claim (TTL 7 дней, чтобы можно было вернуться и продолжить).
2. Все остальные `/guest/*` ждут `Authorization: Bearer <jwt>`.
3. Дополнительно: путь `/guest/sessions/{session_id}/...` обязан совпадать с
   `session_id` из токена, иначе **403**. Утёкший токен не может оперировать
   чужой сессией.

`POST /guest/auth` (обмен magic-link токена с QR-кода) — **501** в MVP;
фронт пока всегда стартует anonymous.

## Endpoints

```bash
# 1) Старт анонимной гостевой сессии (без auth) — возвращает JWT
curl -X POST http://localhost:8200/guest/sessions

# 2) Magic-link обмен (NOT IMPLEMENTED — 501)
curl -X POST http://localhost:8200/guest/auth -d '{"t":"..."}'

# 3) Шаблон ленты (template + ordered beats + tags), i18n уже включён
curl http://localhost:8200/guest/journey -H "Authorization: Bearer $JWT"

# 4) Снимок состояния сессии (для restore при перезаходе)
curl http://localhost:8200/guest/sessions/<id> -H "Authorization: Bearer $JWT"

# 5) Сохранить такт (mood-score / chip-теги / skip). Любое из трёх полей.
curl -X PATCH "http://localhost:8200/guest/sessions/<id>/beats/<beat_id>" \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $JWT" \
  -d '{"score": 2, "tags": ["cold"]}'

# 6) Попросить ИИ-карточки-гипотезы для слабого такта
curl -X POST "http://localhost:8200/guest/sessions/<id>/dig" \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $JWT" \
  -d '{"beat_id": "<beat_id>"}'

# 7) Зафиксировать ответ гостя на гипотезу (или free_text)
curl -X POST "http://localhost:8200/guest/sessions/<id>/dig/answer" \
  -H 'Content-Type: application/json' -H "Authorization: Bearer $JWT" \
  -d '{"dig_id": "<dig_id>", "accepted_guess_id": "g1"}'

# 8) Голосовая запись (NOT IMPLEMENTED — 501)
curl -X POST "http://localhost:8200/guest/sessions/<id>/voice" ...

# 9) Финализация: синтезирует фидбэк из ленты + digs, прогоняет через analyze,
#    апдейтит `feedback_summary` сессии — после этого она появится в админских
#    дриллдаунах.
curl -X POST "http://localhost:8200/guest/sessions/<id>/finalize" \
  -H "Authorization: Bearer $JWT"
```

## Сценарий гостя

1. Web-app откинут от QR на столе (fallback — anonymous): открывает сессию
   через `POST /guest/sessions`.
2. Фетчит `GET /guest/journey` — рисует ленту тактов.
3. По мере свайпов автосейвит каждый такт: `PATCH …/beats/{beat_id}` с
   `score` / `tags` / `skipped`.
4. На recap-экране выделяет 1–2 слабых такта; по кнопке «помоги нам понять»
   зовёт `POST …/dig` → отрисовывает карточки-гипотезы.
5. Гость тапает «да, это» (`accepted_guess_id`) или «расскажу сам»
   (`free_text`) → `POST …/dig/answer`.
6. Финал: `POST …/finalize` (202 Accepted) — фон-задача синтезирует текст
   фидбэка и прогоняет через `analyze_feedback`.

## Контракты ответов (TypedDict, see `presentations/http_guest_api/schemas/guest.py`)

```python
StartSessionResponse: { session_id, token }
JourneyResponse: { template: {id,name,label_uk,label_en},
                   beats: [{ id, beat_key, position, label_uk, label_en, icon,
                             input_type, tags: [{id,tag_key,position,label_uk,label_en}] }] }
BeatPatch: { score?: 1..5, tags?: list[str], skipped?: bool }    # ≥1 поле
BeatStateOut: { beat_id, score?, tags, skipped }
DigStartResponse: { dig_id, beat_id, guesses: [{id,text_uk,text_en,emoji}] }
DigAnswerRequest: { dig_id, accepted_guess_id? | free_text? }   # XOR
DigAnswerResponse: { dig_id, accepted_guess_id?, free_text?, next_dig?: ... }
SessionStateOut: { session_id, feedback_source, started_at, ended_at,
                   beats: [...], digs: [...] }
FinalizeResponse: { status: "accepted" }
```

## Out of scope сейчас

- Magic-link auth по QR (POST /guest/auth — 501)
- Голосовой ввод (POST .../voice — 501); фронт пока шлёт только `free_text`.
- Multi-journey (delivery / restaurant): схема поддерживает несколько
  templates, но `GET /guest/journey` возвращает дефолтный. Делается через
  `is_default` флаг в `journey_templates` — добавить второй шаблон = config-
  INSERT, не код.
- Card generation (`client_cards`) для web-сессий — `finalize_session`
  обновляет только `feedback_summary` + `ended_at`. Клиентская карточка
  делается на следующей итерации.
