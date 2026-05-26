# Phase 4C — `telegram-waiter-admin-miniapp` (Voice admin Mini App instance)

Ты — orchestrator Phase 4C. Запускаешься внутри **нового репозитория**
`telegram-waiter-admin-miniapp`, который был создан через GitHub "Use this
template" от `telegram-miniapp-template`. Твоя задача — превратить generic
template в **рабочий admin Mini App для конкретного проекта `telegram-waiter`**:
заменить `(example)/` на реальные 5 страниц с подключением к FastAPI backend.

## Required reads (в первый ход)

1. `design/` — уже скопирован из template repo (Voice design system, ты можешь
   на него ссылаться как ИНПУТ). Особое внимание:
   - `design/ui_kits/admin/screens/Dashboard.jsx` — reference paint для /
   - `design/ui_kits/admin/screens/Metrics.jsx` — reference paint для /metrics
   - `design/ui_kits/admin/screens/Topics.jsx` — reference paint для /topics
   - `design/ui_kits/admin/screens/Clients.jsx` — reference paint для /clients
   - `design/ui_kits/admin/screens/Ask.jsx` — reference paint для /ask
   - `design/ui_kits/admin/components.jsx` — visual reference (НЕ копировать как есть; это inline React+Babel mock)
2. `README.md` — текущий quick-start template'а; обновишь под instance.
3. `app/(example)/` — placeholder dashboard, который ты УДАЛИШЬ и заменишь.
4. `components/` (kpi, charts, chat, layout, ui) — generic primitives, готовы для использования.
5. `lib/api/client.ts` — axios + JWT interceptor готов.
6. `lib/telegram/auth.ts` — bootstrap flow готов.

## Backend API контракт (FastAPI из telegram-waiter Phase 4A)

Все типы строго соответствуют backend Pydantic-схемам. Скопируй в
`lib/api/types.ts` (как `interface`, не `type` где возможен extend):

```typescript
// auth
interface AuthRequest { init_data: string }
interface AuthResponse { token: string; telegram_id: number }

// overview
interface TopicCount { topic: string; count: number; avg_sentiment: number }
interface OverviewResponse {
  sessions_count: number
  avg_sentiment: number | null
  top_positive_topics: TopicCount[]
  top_negative_topics: TopicCount[]
}

// metrics — union: либо points (numeric), либо distribution (enum/boolean)
interface MetricPoint { bucket: string; count: number; avg: number | null; min: number | null; max: number | null }
interface CategoryCount { value: string; count: number; pct: number }
interface MetricsResponse {
  metric_key: string
  expected_type: 'number' | 'enum' | 'boolean' | 'text' | 'unknown'
  points: MetricPoint[] | null
  distribution: CategoryCount[] | null
  total: number | null
  unknown: number | null
  enum_values: string[] | null
}

// topics
interface TopicsResponse { topics: TopicCount[] }

// semantic
interface SemanticSearchRequest { query: string; top_k: number }
interface SemanticHit {
  session_id: string
  client_id: number | null
  score: number
  summary_text: string
  sentiment: string | null
  started_at: string | null
}
interface SemanticSearchResponse { hits: SemanticHit[] }

// clients
interface ClientProfileResponse {
  telegram_id: number
  name: string | null
  sessions_count: number
  last_session_at: string | null
  avg_sentiment: number | null
  recent_cards: Array<Record<string, unknown>>
  top_topics: TopicCount[]
}

// ask
interface AskRequest { question: string; history?: Array<{ role: 'user' | 'assistant'; content: string }> }
interface AskResponse { answer_text: string; tools_used: string[]; chart_text: string | null }
```

## Endpoints для подключения

| Page | Method | Path | Query / Body |
|---|---|---|---|
| /dashboard | GET | `/admin/overview` | `?date_from=ISO&date_to=ISO` |
| /metrics | GET | `/admin/metrics` | `?metric_key=...&date_from&date_to&group_by=day` |
| /topics | GET | `/admin/topics` | `?date_from&date_to&sentiment=positive\|negative` |
| /clients (search) | POST | `/admin/semantic` | `{ query, top_k }` |
| /clients/{id} | GET | `/admin/clients/{telegram_id}` | — |
| /ask | POST | `/admin/ask` | `{ question, history? }` |

Все запросы (кроме `/admin/auth`) требуют `Authorization: Bearer ${token}` — это уже сделано в `lib/api/client.ts`.

## Текущее состояние (стартовая точка)

- Ветка: `main` (или `autonomous/<TS>` если launcher настроен — иначе fork)
- `git log --oneline` показывает 8+ коммитов template'а
- `app/(example)/` — placeholder, к удалению на commit #1

## Time budget

- Старт: NOW
- Soft deadline: START + 2h 30m — после wind-down
- Hard deadline: START + 3h

## Sub-tasks (= commits) — 6 атомарных

### #1 — `chore: scaffold admin routes + replace (example) + types from backend`

- Удали `app/(example)/` целиком.
- Создай новые routes: `app/dashboard/page.tsx`, `app/metrics/page.tsx`, `app/topics/page.tsx`, `app/clients/page.tsx`, `app/ask/page.tsx` — пока заглушки `<Header title="..." /><main>TODO</main>`.
- Создай новый `app/layout.tsx` (или замени) с BottomNav на 5 slots: Главная (`/dashboard`), Метрики (`/metrics`), Топики (`/topics`), Клиенты (`/clients`), Чат (`/ask`).
- Обнови `app/page.tsx`: после bootstrap → redirect на `/dashboard` (вместо `/(example)/dashboard`).
- В `lib/api/types.ts` добавь все интерфейсы из «Backend API контракт» выше.
- В `lib/api/admin.ts` (new) добавь wrapper-функции для каждого endpoint'а (типизированные через типы выше). Используй `apiClient` из `lib/api/client.ts`.
- Тесты: smoke-тест что страницы рендерятся без ошибок (Vitest + render).

### #2 — `feat(dashboard): KPI overview + top topics + recent feedback`

Реализуй `/dashboard` по reference paint `design/ui_kits/admin/screens/Dashboard.jsx`:

- **Date-range chips** наверху: «7 дней», «30 дней», «90 дней», "custom" (пока скрыт за TODO).
- **KPI 4-up grid:** Сессий, Средний sentiment, Топиков, Позитив %.
  - Используй `KPICard` из template.
  - Данные из `GET /admin/overview` (просто `summary_overview`).
  - `avg_sentiment` форматировать: `>0.33 → "позитив"`, `<-0.33 → "негатив"`, иначе нейтрально.
- **Top topics секция:** top 3 positive + top 3 negative, side-by-side компактно.
- **Recent feedback list (плейсхолдер):** TODO для следующей итерации — пока пусто или скрыть.
- Loading state: skeleton (используй shadcn shimmer класс `animate-shimmer` если уже есть, или просто `opacity-50` блоки).
- Error state: «Не удалось загрузить данные. Попробуйте позже.»

Тесты: рендер с mock-данными (axios-mock-adapter) → проверь что 4 KPI и top-topics видны.

### #3 — `feat(metrics): filter bar + chart + table + enum/number routing`

Реализуй `/metrics` по `design/ui_kits/admin/screens/Metrics.jsx`:

- **Filter bar (горизонтальный scroll):**
  - Metric picker (dropdown shadcn — список metric_keys через `GET /admin/overview` или статичный fallback)
  - Date range chips (как в /dashboard)
  - Group by toggle: «День / Неделя» (только для numeric)
- **Conditional rendering на основе `expected_type`:**
  - `number`: `LineChartCard` с x=bucket, y=avg + per-day table снизу
  - `enum` / `boolean`: `BarChartCard` с distribution (sorted desc by count) + total + unknown count если >0
  - `text`: сообщение «Текстовая метрика — используйте /topics или /clients»
  - `unknown`: «Метрика не найдена»
- Reuse `LineChartCard` + `BarChartCard` из template, передавай Voice violet primary.
- Empty state: «По метрике X за период Y данных нет.»

Тесты: рендер с mock-numeric → LineChart visible; mock-enum → BarChart visible.

### #4 — `feat(topics): positive/negative tabs + BarChart + mentions`

Реализуй `/topics` по `design/ui_kits/admin/screens/Topics.jsx`:

- Date-range chips наверху.
- Tabs «Позитивные» / «Негативные» (shadcn `<Tabs>`).
- Top-5 `BarChartCard` (горизонтальные бары — `<BarChart layout="vertical">`) для выбранной вкладки.
- Под чартом — list «recent mentions» (заглушка пока, потом подключим semantic search filtered by topic).
- API: `GET /admin/topics?sentiment=positive` ИЛИ `?sentiment=negative`.

Тесты: switching tabs триггерит новый запрос с правильным sentiment param.

### #5 — `feat(clients): search + list + deep-dive sheet`

Реализуй `/clients` по `design/ui_kits/admin/screens/Clients.jsx`:

- **Search input** (lucide search icon, shadcn Input). Debounce 300ms.
- При пустом query — пустой state «Введите запрос для поиска клиентов» (НЕ дёргаем backend).
- При query — `POST /admin/semantic { query, top_k: 10 }` → список карточек:
  - Avatar (initials), name (или `client {id}` если name null), sentiment chip, дата последней сессии, кусок summary_text 80 символов.
- Tap на карточку → bottom-sheet (shadcn `<Sheet>`) deep-dive:
  - `GET /admin/clients/{client_id}` → полный профиль
  - Sessions count, avg sentiment, top topics chips, recent_cards (по 3 строки)
- Sheet закрывается tap'ом outside или Telegram BackButton.

Тесты: search триггерит semantic, sheet open + close, deep-dive загружает profile.

### #6 — `feat(ask): chat widget wired to /admin/ask`

Реализуй `/ask` по `design/ui_kits/admin/screens/Ask.jsx`:

- Используй `ChatWidget` + `Message` из template.
- Suggested prompts (3-4 chip'а сверху для пустого состояния):
  - «Топ-3 жалобы за неделю»
  - «Сводка за 30 дней»
  - «Что хвалят клиенты»
  - «Найди жалобы на скорость»
- Submit → `POST /admin/ask { question, history }`:
  - `history` строится из всех предыдущих message в локальном state (последние 6, role=user|assistant)
  - while loading → render «thinking» message (3 amber dots indicator)
- Response: render `answer_text` как Message с role=assistant. Если есть `chart_text` — отрендерь под message в `<pre>` или monospace `code-block` (markdown style).
- Сохраняй conversation в Zustand store или local React state (не нужна persistence между сессиями для MVP).
- Edge case: 401 → re-bootstrap auth → retry submit (transparent для user).

Тесты: submit → request с правильным body, render assistant response, chart_text shown if present.

## Финальные коммиты (bonus, если останется время)

- `feat(dashboard): wire recent feedback list to semantic search`
- `docs: README — backend URL config, deploy instructions (Vercel/ngrok dev)`
- `test(e2e): Playwright smoke на все 5 страниц с mock backend`

## Out of scope

- ❌ Server-side rendering — все страницы `"use client"` (template уже так)
- ❌ Real-time updates / WebSocket — Backlog
- ❌ Caching beyond axios defaults — добавит instance в будущем по необходимости
- ❌ Сложный chart-зум / pan — Tremor дефолты достаточно
- ❌ Multi-language i18n — Russian-only сейчас
- ❌ Avatar fetching по url из Telegram — Generate initials из name (или client {id})

## Hard rules

1. **Bash discipline:** одна Bash-call = одна команда. Никаких `&&;|`.
2. **Domain-specific копи только в этом instance.** В template — оставайся generic. Здесь — формальное «Вы», feedback-восемнадцать. Никакого "ресторан" вне design/ (это input).
3. **Voice rules (из `design/SKILL.md`):**
   - Max 1 emoji per screen (admin — лучше 0)
   - Sentence case for everything
   - Card = 12 radius + 1px border + no shadow
   - Geist Sans/Mono, mono numerals tabular
   - Mobile-first 375px
4. **Reuse template primitives** — никогда не reimport напрямую из дизайна, только generic компоненты template'а.
5. **Backend URL через env** — `NEXT_PUBLIC_API_BASE_URL` из `.env.local`. Не хардкодить.
6. **Commit-before-next** — после каждого шага зелёные тесты + git status clean.
7. **TypeScript strict** — `tsc --noEmit` clean после каждого коммита.
8. **Date handling** — всегда ISO 8601 с timezone (UTC), не локальный. Backend ожидает Z-suffix.

## Verification (gate перед финальным отчётом)

1. `pnpm typecheck` — clean
2. `pnpm test` (Vitest) — все зелёные
3. `pnpm test:e2e` (Playwright) — bootstrap + базовая навигация работают с mock backend
4. `pnpm build` — production build проходит
5. `pnpm dev` запускается на localhost:3000 — открыть в mobile-viewport DevTools, пройти все 5 tab'ов (потребуется живой backend или mock; для smoke достаточно компиляции страниц)
6. Все 5 страниц соответствуют визуально reference paint из `design/ui_kits/admin/screens/*.jsx` (структура + цвета + spacing)

## Финальный отчёт

1. `git log --oneline` — список 6+ commits
2. Test counts: было / стало
3. Screenshots/notes какая страница к какому endpoint'у подключена (для ручной проверки)
4. Готовность к hosting (Iteration 1 — local + ngrok, Iteration 2 — VPS, Iteration 3 — Vercel)
5. **Bot integration TODO:** в `telegram-waiter/bot_admin/` нужна команда `/miniapp` → возвращает inline button с `WebAppInfo(url=ADMIN_MINI_APP_URL)`. Это **отдельная мини-задача в `telegram-waiter`** (НЕ в этом репо), оставь подсказку в README.

## Env-config для instance

В `.env.example`:

```
NEXT_PUBLIC_API_BASE_URL=https://your-backend-host.com
NEXT_PUBLIC_AUTH_ENDPOINT=/admin/auth
NEXT_PUBLIC_APP_ENV=development
```

В README поясни:
- Local dev: backend на `http://localhost:8000`, Mini App на `http://localhost:3000`, ngrok-tunnel поверх 3000 для Telegram
- Prod: backend на VPS/render, Mini App на Vercel (или тот же VPS)
- CORS на backend стороне (`ALLOWED_MINI_APP_ORIGINS`) должен включать URL Mini App'а
