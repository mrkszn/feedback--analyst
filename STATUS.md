# STATUS — telegram-waiter

> Single source of truth для куратора. Где сейчас стоит проект, что задеплоено, что в работе.

**Last update:** 2026-06-05 ~10:30 UTC

---

## TL;DR

**MVP полностью в продакшене и работает.** Все фазы 0-4 (бэкенд, боты, HTTP API, Mini App template, Mini App instance) закрыты. Сейчас — пост-MVP полировка фронта + подготовка ко второй итерации.

| Поверхность | Состояние |
|---|---|
| guest-бот (сбор фидбэка) | ✅ live, polling, systemd на VPS |
| admin-бот (`/statistics`, `/topics`, `/miniapp`) | ✅ live, polling, systemd на VPS |
| FastAPI HTTP API | ✅ live, systemd на VPS, публичный HTTPS через Caddy + nip.io |
| Admin Mini App (template) | ✅ GitHub Template repo, Vite skeleton ship'нут |
| Admin Mini App (instance) | ✅ live на Vercel, 5 страниц подключены к prod backend |
| CI/CD | ✅ auto-deploy на push в main для backend; Vercel auto-deploy для frontend |

---

## Архитектура (high-level)

```
Telegram ──┐
           │  (guest bot) ─────► bot-guest.service (aiogram polling)
           │
           │  (admin bot) ─────► bot-admin.service (aiogram polling)
           │
           │  (Mini App WebView)
           │       ▼
           │  https://telegram-admin-miniapp.vercel.app
           │       │ (Vite SPA, Geist + InsightFlow palette)
           │       │
           │       │ axios + JWT
           │       ▼
           │  https://api-waiter.178-105-54-29.nip.io  (Caddy 2 + Let's Encrypt)
           │       │ reverse_proxy 172.20.0.1:8200
           │       ▼
           │  voice-api.service (uvicorn @ 127.0.0.1:8200)
           │       │
           │       ▼
           └─► presentations.http_api.main:app (FastAPI)
                   │
                   ├─► core.services.* (analytics, sessions, clients, ...)
                   │       │
                   │       ▼
                   │   StorageAdapter Protocol
                   │       │
                   │       ├─► Supabase (Postgres) ── облако
                   │       └─► Pinecone (vectors)  ── облако
                   │
                   └─► OpenAI (chat / Whisper / embeddings) ── облако
```

VPS: Hetzner CPX21 (`178.105.54.29`, Ubuntu 24.04), общий с двумя другими проектами (`landing`, `n8n + Backstage`). Caddy 2 в Docker compose стека n8n владеет 80/443 и проксирует все vhost'ы.

---

## Репозитории

| Репо | Где | HEAD | Назначение |
|---|---|---|---|
| **`mrkszn/feedback--analyst`** (`telegram-waiter`) | [github](https://github.com/mrkszn/feedback--analyst) | `98c42a1` | Backend monorepo: 2 бота + FastAPI + core services. CI auto-deploy на VPS. |
| **`mrkszn/telegram-miniapp-template-vite`** | [github](https://github.com/mrkszn/telegram-miniapp-template-vite) | `2d2dd1f` + e2e fix | Generic Vite+React skeleton для admin Mini App'ов. `is_template: true` — «Use this template» работает. |
| **`mrkszn/telegram-admin-miniapp`** | [github](https://github.com/mrkszn/telegram-admin-miniapp) | `5128d97` | Domain instance для telegram-waiter. Клонирован из template, 5 страниц подключены к prod backend. Vercel auto-deploy. |

---

## Production-инфраструктура

### VPS `178.105.54.29`
```
bot-guest.service   active   (python -m channels.telegram.guest_bot)
bot-admin.service   active   (python -m presentations.telegram_admin)
voice-api.service   active   (uvicorn presentations.http_api.main:app --host 0.0.0.0 --port 8200)
```
Каждый рестартится через `sudo -n systemctl restart` от CI после rsync кода.

### Публичные URL
- **Backend API:** https://api-waiter.178-105-54-29.nip.io
  - `/docs` → Swagger UI 200
  - `/health` → `{"status":"ok"}` 200
  - 8 admin endpoints (`/admin/auth`, `/admin/overview`, `/admin/metrics`, `/admin/topics`, `/admin/semantic`, `/admin/clients/{id}`, `/admin/ask`, `/admin/questions`)
  - TLS: Let's Encrypt автообновляемый (Caddy)
- **Mini App SPA:** https://telegram-admin-miniapp.vercel.app
  - 5 routes: `/dashboard`, `/metrics`, `/topics`, `/clients`, `/ask`
  - Build hash после polish: `index-CVnvYToh.js` (Vercel ребилдит при каждом push)
- **BotFather config:** admin-бот → Mini App URL = выше Vercel domain

### Облако
- Supabase: `mkhalqkrpkluhtskoybi.supabase.co` (dev пока используется и в prod)
- Pinecone: namespace `prod`
- OpenAI: единый ключ, usage_tag=`prod`

---

## Фазы — done log

### Phase 0 — guest-бот + анкета (M0 baseline)
✅ aiogram polling, LangGraph узлы (analyze / dialogue / card), Whisper для voice. Pre-M1.

### Phase 1 — admin-бот + аналитика
✅ `/statistics`, `/topics`, `/questions` CRUD. Free-text → analytics agent v2 (interpret → execute → synthesize, два phase'а).

### Phase 2 — seed данные
✅ 50 fake-клиентов, ~75 сессий, реальные embeddings в Pinecone (`a0babf0 chore(scripts): seed_demo_data`).

### Phase 3 — analytics agent v2
✅ Two-phase ReAct (`f0cab96`), wired into bot и HTTP API (`6ab51ab`).

### Phase 4A — FastAPI HTTP API
✅ 7 admin endpoints + Telegram initData валидация + JWT issue/verify + CORS. Pre-этой conversation. (`api/*` → переехало в `presentations/http_api/*` в R1.)

### M1 рефакторинг — modular template architecture
✅ Закрыто 4 июня этой conversation.
- R1 (`fa62669`): layered структура `core / channels / presentations` (137 файлов, 462 pytest)
- R2 (`64231ac`): StorageAdapter Protocol + Supabase/Pinecone адаптеры (17 файлов, 462 pytest)
- R3 (`6c20b70`): `core/bootstrap/` template loader + `templates/tg-restaurant/` + `clients/_example/` (15 новых файлов, 475 pytest)
- R4 (`752c8aa`): `docs/{ARCHITECTURE, ONBOARDING_CLIENT, TEMPLATE_AUTHORING}.md` + `templates/tg-clinic/` stub (11 файлов)
- Финальные тесты: 475 passed, ruff/mypy clean.

### Phase 4B — generic Mini App template (Vite + React)
✅ Закрыто в отдельной сессии (не в этой conversation).
- Репо `telegram-miniapp-template-vite` подготовлен с design/ + BUILD_PLAN.md.
- 7 атомарных коммитов: bootstrap → design tokens → telegram SDK → auth → API client → AppShell → primitives.
- Vite 5 + React 19 + TS strict + Tailwind + shadcn/ui + Tremor + Geist + Instrument Serif.
- `is_template: true` поставлен на GitHub.

### Phase 4C — domain instance `telegram-admin-miniapp`
✅ Закрыто в отдельной сессии (не в этой conversation).
- Клонирован из template через «Use this template».
- 6 атомарных коммитов: scaffold + dashboard + metrics + topics + clients + ask.
- Подключён к https://api-waiter.178-105-54-29.nip.io через JWT axios interceptor.
- Vercel deploy под именем `telegram-admin-miniapp.vercel.app`.

### Production deploy (этой conversation)
✅ Backend HTTP API экспонирован публично:
- `voice-api.service` поднят (`b5b05b5`), unit ExecStart исправлен (`5530fcf`), poll-loop вместо flat sleep (`ccd986b`, `3b91365`).
- Caddy 2 уже стоял в n8n compose stack — добавили vhost `api-waiter.178-105-54-29.nip.io` в Caddyfile через bootstrap скрипт.
- Подводные камни: ufw default-deny блокировал bridge → uvicorn (`6847357`), Docker `host-gateway` резолвится в dead docker0 (`98c42a1`). Оба зафиксированы идемпотентно в `deploy/install-voice-api.sh` для будущих хостов.
- Backward-compat шим `bot_guest/__main__.py` + `bot_admin/__main__.py` остаётся в репо для свежих VPS, у которых systemd unit ещё не обновили (`018df12`).

### UI polish после 4C (текущая сессия)
✅ Commit `5128d97` в `telegram-admin-miniapp`:
- Theme switcher (auto/light/dark, циклит) в хедере, persist в localStorage
- Шрифт заголовков Instrument Serif italic → Geist Sans 600 weight (длинные русские слова перестали выезжать)
- KPICard overflow guards: `min-w-0 overflow-hidden`, `break-words`, `--kpi-size` 38→30 px

---

## Что сейчас в работе

Ничего блокирующего. Жду визуальный smoke от куратора после Vercel редеплоя (commit `5128d97` → ~30s).

---

## Backlog (приоритизированный)

### A — perf / observability
- **Bundle split** для charts (842 KB → lazy chunk уже есть, но instance подгружает на старте). Эффект: KPI экраны откроются в ~2× быстрее на slow Telegram WebView.
- **UptimeRobot** пинг каждые 5 мин на `/health` и Vercel `/` → email/Telegram при downtime
- **Sentry** для FastAPI и Vite SPA (free 5k events)

### B — UX
- Дашборд: вывести «Recent feedback» list (сейчас пусто, был помечен TODO в 4C #2)
- Brand color picker (InsightFlow Tweaks panel имеет 3 палитры — violet/indigo/teal) — можно в Settings tab
- Density toggle (comfortable/compact) — токены `.density-compact` уже готовы
- Skeleton state улучшить (shadcn shimmer вместо `opacity-50`)

### C — модульность (M2/M3 в plan'е)
- Второй template из `templates/tg-clinic/` стаба — реальный второй проект (e.g. для парикмахерских / клиник)
- Per-tenant deploy через `core/bootstrap/` (сейчас bootstrap есть, но используется только тестово через `_example`)

### D — qa
- Playwright e2e на все 5 routes с mock backend
- Тесты на theme switcher (auto/light/dark)
- Тесты на JWT 401 retry в /ask

---

## Open questions / решения для куратора

- ⚠️ **dev и prod на одной Supabase + Pinecone.** Когда заведём отдельные prod-credentials — обновить `.env` на VPS + перезапустить bots.
- ⚠️ **bot_guest/bot_admin shims остаются.** Можно удалить когда:
  - либо вручную обновить unit'ы на VPS (`/etc/systemd/system/bot-*.service` сейчас уже на новых путях после первой ручной установки)
  - либо широченнее sudoers для CI чтобы он мог сам устанавливать unit'ы
- ⚠️ **nip.io URL длинный и нечитаемый.** Покупка домена + DNS A → 178.105.54.29 → Caddy выпустит новый cert автоматически. ~$10/год.
- 🔵 **Recent feedback list на dashboard** — оставлять TODO до следующей итерации?

---

## Lessons learned (M1 + 4*)

1. **`pytest --collect-only ≠ pytest -q`** — collect только импорты, runtime ошибки видит только полный прогон.
2. **Patch-target sweep** при ренейме модулей покрывает 4 формы: `patch("...")`, `patch.object(...)`, `mocker.patch("...")`, `monkeypatch.setattr("...")`. Import-grep ловит только первую.
3. **Backward-compat retention OK** когда экономит массовый refactor тестов. Документировать в commit body.
4. **Curator коммитит из main loop.** Subagents fail на `git commit` (permission denial).
5. **STATUS.md > SendMessage spam** для коммуникации с куратором.
6. **Один implementer per file at a time.**
7. **Длинный `sleep N` после systemctl restart — антипаттерн.** Polling по реальному signal (curl /docs, is-active loop) надёжнее.
8. **ufw interface-agnostic by default.** Нужно либо `from <range>` либо `in on <iface>` чтобы не задеть legitimate bridge traffic.
9. **Docker `host-gateway` keyword резолвится в default bridge (docker0), не в bridge самого контейнера.** На мульти-bridge хостах нужно динамически детектить (`ip route show default` внутри контейнера) и пинить explicit IP.
10. **shadcn warning «Fast refresh only works when a file only exports components»** — не error, можно игнорить или вынести `buttonVariants` constants в отдельный файл.
