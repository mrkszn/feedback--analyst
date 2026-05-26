# Phase 4B — `telegram-miniapp-template` (reusable Next.js skeleton)

Ты — orchestrator Phase 4B. Запускаешься внутри **нового пустого репозитория**
`telegram-miniapp-template`. Твоя задача — построить **переиспользуемый
template** для admin Mini App'ов любых Telegram-бот проектов. Никакой
domain-логики — только generic skeleton.

## Required reads (в первый ход)

В **этом** репо ожидается уже скопированная папка `design/` (Voice design system).
Если её нет — попроси юзера остановиться и скопировать.

1. `design/README.md` — full Voice brand / tone / visual rules.
2. `design/SKILL.md` — short rules (must-not-violate).
3. `design/colors_and_type.css` — CSS variables (тебе их интегрировать в Tailwind config + globals.css).
4. `design/ui_kits/admin/components.jsx` + `design/ui_kits/admin/screens/*.jsx` — reference paint;
   **НЕ копировать как есть** — это inline React+Babel mockup; ты пишешь production TS/TSX.
5. `design/preview/components-*.html` — pixel-reference для каждого компонента.

После reads:
- `git branch --show-current` → должна быть `autonomous/<TS>` (launcher создал)
  ИЛИ если запускаешься без launcher'а — `main` (тогда: `git checkout -b feat/template-skeleton`).
- `git log --oneline` → пустой или только initial commit от GitHub.

## Что такое template (scope)

Generic skeleton, который КЛОНИРУЕТСЯ через GitHub «Use this template» для
**любого** будущего проекта Telegram-бот + Mini App. В template:

✅ Есть:
- Next.js 16 + TypeScript + Tailwind + shadcn/ui + Tremor + lucide-react + Geist
- Voice design tokens (colors_and_type.css → Tailwind + globals.css)
- AppShell (header 44px + bottom-nav 56px + Telegram theme bridge)
- Telegram WebApp SDK wrapper (initData → POST {auth_endpoint} → JWT → store)
- Generic API client (axios + JWT interceptor)
- Generic compositional components: `KPICard`, `LineChartCard`, `BarChartCard`,
  `ChatWidget`, `Message`, `Sheet`, `Chip`, `Avatar`, `Header`, `BottomNav`
- ONE example page `(example)/dashboard/page.tsx` — демо что shell работает
- `.env.example` с `NEXT_PUBLIC_API_BASE_URL` + `NEXT_PUBLIC_AUTH_ENDPOINT`
- README quick-start: clone, set env, replace `(example)`, deploy
- Vitest unit tests на telegram/auth + api/client
- Playwright smoke на bootstrap+auth (mock backend)

❌ НЕ в template (это работа Phase 4C — instance):
- Доменные страницы `/dashboard /metrics /topics /clients /ask` с реальными данными
- Доменные API types (`OverviewResponse`, `MetricPoint` и т.д.)
- Доменный copy («Сессии», «Топики», «Клиенты»)

Domain-neutral именование везде: `KPICard` НЕ `RestaurantKPICard`. Mock-data
в `(example)` — generic ("Active users", "Avg score") **не** restaurant-specific.

## Tech stack (обязательно)

| Слой | Технология |
|---|---|
| Framework | Next.js 16 (App Router) + TypeScript strict |
| Styling | Tailwind CSS + shadcn/ui (CLI installs primitives) |
| Charts | Tremor (`<LineChart/>`, `<BarChart/>`) |
| Icons | lucide-react (24px grid, stroke 1.75) |
| Fonts | Geist Sans + Geist Mono via `next/font/google` |
| Telegram | `@twa-dev/sdk` (или ручной wrapper над `window.Telegram.WebApp`) |
| HTTP | axios |
| State | Zustand (только session/auth, остальное — local component state) |
| Test | Vitest + @testing-library/react; Playwright для smoke |
| Lint | ESLint + Prettier |

## Voice design rules (hard, из design/README.md)

1. **Geist Sans + Geist Mono only**. `font-variant-numeric: tabular-nums` для KPI numbers.
2. **Lucide icons only.** 24px grid, stroke 1.75, `currentColor`. No emoji-as-icon.
3. **Card = 1px border + 12px radius + 16/20px padding. No shadow.**
4. **No background gradients** на page surfaces (исключение: brand-mark circle).
5. **No imagery** — Voice — dashboard, не consumer app.
6. **Mobile-first** 375×667 baseline, tablet 768 secondary.
7. **Bottom-nav 56px, header 44px**, safe-area-inset аккуратно.
8. **Russian primary**, sentence case, формальное «Вы».
9. **Max 1 emoji per screen** (в admin почти всегда — 0).
10. **No animations fluff** — micro-transitions ≤200ms cubic-bezier(0.2,0,0,1), без spring/parallax.

## Sub-tasks (= commits) — 7 атомарных

### #1 — `chore: bootstrap Next.js 16 + TypeScript + Tailwind`

- `npx create-next-app@latest . --typescript --tailwind --app --no-src-dir --import-alias "@/*" --no-eslint` (потом установим ESLint отдельно с воспроизводимой конфигурацией)
- `package.json` minimal: только то что нужно. Установи lucide-react, @tremor/react, axios, zustand, clsx.
- `.gitignore` стандартный Next.js + `.env.local`.
- Никакого app/-кода кроме скелета.

### #2 — `feat(design): Voice design tokens (Tailwind + globals.css)`

- `design/colors_and_type.css` → разбить:
  - CSS variables → `app/globals.css` (light + dark + Telegram-bridge layer)
  - Type scale, radii, spacing → `tailwind.config.ts` (extend theme.colors, theme.fontFamily, theme.borderRadius, theme.boxShadow)
- Geist Sans + Geist Mono через `next/font/google` в `app/layout.tsx`.
- Установка shadcn/ui: `npx shadcn@latest init` с base color = slate, primary color = violet, CSS variables = yes.
- Добавь shadcn primitives: button, input, dialog, sheet, dropdown-menu (через `npx shadcn@latest add ...`).

### #3 — `feat(telegram): WebApp SDK wrapper + theme bridge + safe-area`

- `lib/telegram/sdk.ts` — wrapper над `window.Telegram?.WebApp` (`initData`, `themeParams`, `BackButton`, `MainButton`, `ready()`, `expand()`). Type-safe.
- `lib/telegram/theme.ts` — читает `tgWebApp.themeParams` → выставляет CSS variables `var(--tg-theme-*)`. Если вне Telegram — fallback на Voice palette.
- `components/layout/ThemeProvider.tsx` — applies theme on mount + reacts to `themeChanged` event.
- `app/layout.tsx` — обернуть `{children}` в ThemeProvider, добавить env-injection шапку с tg-script.
- Тесты на theme.ts (Vitest): задал mock-themeParams → проверь CSS variables на root.

### #4 — `feat(auth): initData → JWT auth flow + Zustand session store`

- `lib/telegram/auth.ts` — функция `bootstrapAuth(apiBaseUrl, authEndpoint)`:
  1. Читает `initData` из `window.Telegram.WebApp.initData`
  2. `POST {apiBaseUrl}{authEndpoint}` body `{ init_data }`
  3. Receives `{ token, ... }` — кладёт в Zustand store
  4. Returns store state
- `lib/state/session-store.ts` — Zustand: `{ token, telegramId, isReady, error, bootstrap() }`.
- `lib/hooks/useAuth.ts` — convenience hook.
- `app/page.tsx` — bootstrap → если ready → redirect to `(example)/dashboard`; если error → error UI.
- Тесты: mock window.Telegram, mock fetch, проверь что bootstrap идёт правильным URL.

### #5 — `feat(api): axios client with JWT interceptor + generic types`

- `lib/api/client.ts` — axios instance:
  - `baseURL = NEXT_PUBLIC_API_BASE_URL`
  - Request interceptor: `Authorization: Bearer ${token}` из session store
  - Response interceptor: 401 → clear session + редирект на root
- `lib/api/types.ts` — generic типы: `ApiError`, `Paginated<T>`. Без domain-types.
- `lib/hooks/useApi.ts` — generic hook `useApi<T>(key: string, fetcher: () => Promise<T>)` — простой data-fetching helper без SWR/React-Query (template остаётся минималистичным; instance может добавить).
- Тесты: axios interceptor добавляет Authorization, 401 чистит store.

### #6 — `feat(layout): AppShell — Header + BottomNav + safe-area`

- `components/layout/AppShell.tsx`:
  - Header 44px: opt left back-arrow (если `useTelegramBackButton` неактивен), middle title, opt right slot
  - Main scroll area (flex-1)
  - BottomNav 56px: 4-5 slots, accept `items: NavItem[]` prop (icon + label + href)
  - Safe-area-inset через `padding-bottom: env(safe-area-inset-bottom)`
- `components/layout/Header.tsx`, `components/layout/BottomNav.tsx` — separate.
- `components/layout/BackButton.tsx` — Telegram BackButton bridge.
- Используй lucide-react иконки. shadcn button где уместно.

### #7 — `feat(components): generic KPICard + LineChartCard + BarChartCard + ChatWidget`

- `components/kpi/KPICard.tsx`:
  - props: `{ label, value, delta?, deltaKind?, spark? }`
  - 12 radius, 1px border, no shadow
  - Geist Mono для value, tabular-nums
- `components/charts/LineChartCard.tsx` — обёртка `<LineChart>` from @tremor/react с Voice цветами (violet primary)
- `components/charts/BarChartCard.tsx` — то же для BarChart
- `components/chat/ChatWidget.tsx` — composer + scroll-area + messages list
- `components/chat/Message.tsx` — bubble. Props: `{ role: 'user'|'agent'|'thinking', content, chart? }`
- `(example)/dashboard/page.tsx` — демо: AppShell + KPICard grid 4-up (generic mock: "Active users", "Avg session", "Topics", "Reply rate") + один LineChartCard со mock-данными.
- README quick-start: 5 шагов (clone → install → set NEXT_PUBLIC_API_BASE_URL → replace `(example)` → deploy).
- Vitest на: KPICard renders props correctly; ChatWidget submits on enter.

## Final commits (если останется время)

- `test: Playwright smoke (bootstrap → auth-mock → /example/dashboard renders)`
- `docs: README — full quick-start, env vars, deployment guide (Vercel/VPS)`

## Out of scope

- ❌ Доменные страницы (Phase 4C)
- ❌ Реальная backend-интеграция (template работает с mock backend в Playwright)
- ❌ Deploy конфигурация (только инструкции в README)
- ❌ i18n библиотеки — template Russian by default, но без heavy framework
- ❌ State management кроме session-store (Zustand)
- ❌ SWR/React-Query — instance может добавить
- ❌ Storybook — overhead не оправдан для template

## Hard rules

1. **Bash discipline:** одна Bash-call = одна команда. Никаких `&&;|`.
2. **Domain-neutral** в каждом файле template'а. Mock-data — generic.
3. **Commit-before-next** — после каждого шага зелёные тесты + git commit + git status clean.
4. **Не модифицируй `design/`** — это input, read-only. Если что-то нужно "выдрать" из дизайна → переписывай как TS-код в template, не копируй inline JSX.
5. **TypeScript strict.** `tsc --noEmit` clean после каждого коммита.
6. **Mobile-first.** Все компоненты рендерятся корректно при 375px width.
7. **Никаких backend-вызовов в template** — только mock в Playwright или Vitest.

## Verification (gate перед финальным отчётом)

1. `pnpm install && pnpm dev` — стартует без ошибок на localhost:3000
2. `pnpm test` (Vitest) — все юниты зелёные
3. `pnpm test:e2e` (Playwright) — bootstrap smoke зелёный
4. `pnpm lint && pnpm typecheck` — clean
5. Открыть http://localhost:3000 в браузере (mobile viewport DevTools) → видеть AppShell + (example)/dashboard
6. Telegram BackButton bridge тестируется руками: открой страницу `?tg=mock` (mock Telegram env), bottom-nav + back работают

## Финальный отчёт

1. `git log --oneline` — список 7+ commits
2. Test counts: было 0 / стало N
3. Структура файлов tree:
   ```
   app/
     layout.tsx
     page.tsx
     (example)/dashboard/page.tsx
     globals.css
   components/{kpi,charts,chat,layout}/
   lib/{telegram,api,state,hooks}/
   tests/{unit,e2e}/
   design/ ← input, read-only
   ```
4. README quick-start ссылка
5. **Mark this repo as Template на GitHub:** Settings → Template repository ✓ (это user сделает в UI)
6. Готовность к Phase 4C: instance клонирует через "Use this template" → заменяет `(example)/` на domain pages → подключает реальный backend
