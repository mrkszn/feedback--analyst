# Phase 4B — `telegram-miniapp-template-vite` (reusable Vite + React skeleton)

Ты — orchestrator Phase 4B. Запускаешься внутри **нового пустого репозитория**
`telegram-miniapp-template-vite`. Твоя задача — построить **переиспользуемый
template** для admin Mini App'ов любых Telegram-бот проектов. Никакой
domain-логики — только generic skeleton.

## Stack rationale (важно для context'а)

**Vite + React, НЕ Next.js.** Telegram Mini App — это pure-client SPA внутри
WebView: `initData` доступен только в браузерном JS, JWT хранится только на
клиенте, SSR/RSC/Edge невозможны в принципе. Vite даёт:

- ~200 KB bundle vs Next.js ~500 KB+ baseline — критично для cold-load в WebView
- Instant HMR в dev
- Простая ментальная модель (нет 'use client' / server components / hydration)
- Static deploy на Vercel через @vercel/static-build — те же preview-deploys

Раньше документ постановки описывал Next.js — устарело, переключение принято
2026-06-04. Если найдёшь упоминания "Next.js" в `design/` или `docs/`, это
исторические артефакты — не следуй им.

## Required reads (в первый ход)

В **этом** репо ожидается уже скопированная папка `design/` (Voice design system
+ iterations). Если её нет — попроси юзера остановиться и скопировать.

1. `design/README.md` — full Voice brand / tone / visual rules.
2. `design/SKILL.md` — short rules (must-not-violate).
3. `design/colors_and_type.css` — base Voice CSS variables.
4. `design/iterations/README.md` — список активных design iterations.
5. **`design/iterations/insightflow/theme.css`** — **активная iteration** для этого
   instance (violet primary + cyan accent + Instrument Serif italic headings +
   live-theming hooks). Возьми CSS variables из этого файла как основные tokens.
6. `design/iterations/insightflow/screens/*.jsx` — reference paint для 5 экранов
   (Dashboard / Metrics / Topics / Clients / Ask). **НЕ копировать как есть** —
   это inline React+Babel mockup; ты пишешь production TS/TSX.
7. `design/iterations/insightflow/components.jsx` — primitives reference paint.
8. `design/ui_kits/admin/components.jsx` + `design/ui_kits/admin/screens/*.jsx` —
   старая Voice iteration, держи как secondary reference (особенно для primitives
   которых нет в insightflow).
9. `design/preview/components-*.html` — pixel-reference для каждого компонента.

После reads:
- `git branch --show-current` → должна быть `autonomous/<TS>` (launcher создал)
  ИЛИ если запускаешься без launcher'а — `main` (тогда: `git checkout -b feat/template-skeleton`).
- `git log --oneline` → пустой или только initial commit от GitHub.

## Что такое template (scope)

Generic skeleton, который КЛОНИРУЕТСЯ через GitHub «Use this template» для
**любого** будущего проекта Telegram-бот + Mini App. В template:

✅ Есть:
- Vite 5 + React 19 + TypeScript strict + Tailwind + shadcn/ui + Tremor + lucide-react + Geist + Instrument Serif
- Voice + InsightFlow design tokens (`iterations/insightflow/theme.css` → Tailwind config + globals.css)
- AppShell (header 44px + bottom-nav 56px + Telegram theme bridge)
- Telegram WebApp SDK wrapper (initData → POST {auth_endpoint} → JWT → store)
- Generic API client (axios + JWT interceptor)
- Generic compositional components: `KPICard`, `LineChartCard`, `BarChartCard`,
  `ChatWidget`, `Message`, `Sheet`, `Chip`, `Avatar`, `Header`, `BottomNav`
- ONE example route `src/routes/example/dashboard.tsx` — демо что shell работает
- `.env.example` с `VITE_API_BASE_URL` + `VITE_AUTH_ENDPOINT`
- README quick-start: clone, set env, replace example route, deploy на Vercel
- Vitest unit tests на telegram/auth + api/client
- Playwright smoke на bootstrap+auth (mock backend)
- `vercel.json` — rewrites для SPA fallback + headers для Telegram WebApp

❌ НЕ в template (это работа Phase 4C — instance):
- Доменные страницы `/dashboard /metrics /topics /clients /ask` с реальными данными
- Доменные API types (`OverviewResponse`, `MetricPoint` и т.д.)
- Доменный copy («Сессии», «Топики», «Клиенты»)

Domain-neutral именование везде: `KPICard` НЕ `RestaurantKPICard`. Mock-data
в `src/routes/example/` — generic ("Active users", "Avg score") **не** restaurant-specific.

## Tech stack (обязательно)

| Слой | Технология |
|---|---|
| Build | Vite 5 + TypeScript strict |
| UI | React 19 |
| Router | `react-router-dom` v7 (data-router API) |
| Styling | Tailwind CSS + shadcn/ui (CLI installs primitives) |
| Charts | Tremor (`<LineChart/>`, `<BarChart/>`) |
| Icons | lucide-react (24px grid, stroke 1.75) |
| Fonts | `@fontsource-variable/geist` + `@fontsource-variable/geist-mono` + `@fontsource/instrument-serif` |
| Telegram | `@twa-dev/sdk` (или ручной wrapper над `window.Telegram.WebApp`) |
| HTTP | axios |
| State | Zustand (только session/auth, остальное — local component state) |
| Test | Vitest + @testing-library/react; Playwright для smoke |
| Lint | ESLint + Prettier |
| Package mgr | pnpm |

## Design rules (hard — Voice + InsightFlow extension)

Из `design/SKILL.md` + `design/iterations/insightflow/`:

1. **Geist Sans** для body + **Geist Mono** для numerals (tabular-nums) + **Instrument Serif italic** для headings.
2. **Lucide icons only.** 24px grid, stroke 1.75, `currentColor`. No emoji-as-icon.
3. **Card = 1px border + 14px radius (InsightFlow extension) + 16/20px padding. No shadow.**
4. **No background gradients** на page surfaces (исключение: brand-mark circle + опциональный radial brand glow в header).
5. **No imagery** — admin dashboard, не consumer app.
6. **Mobile-first** 375×667 baseline, tablet 768 secondary.
7. **Bottom-nav 56px, header 44px**, safe-area-inset аккуратно.
8. **Russian primary**, sentence case, формальное «Вы».
9. **Max 1 emoji per screen** (в admin почти всегда — 0).
10. **No animations fluff** — micro-transitions ≤200ms cubic-bezier(0.2,0,0,1), без spring/parallax.
11. **Brand palette** — primary `#7c3aed` (violet), accent `#06b6d4` (cyan). Все остальные цвета — из `iterations/insightflow/theme.css`.

## Sub-tasks (= commits) — 7 атомарных

### #1 — `chore: bootstrap Vite + React + TypeScript + Tailwind`

- `pnpm create vite@latest . --template react-ts` — strict tsconfig.
- `pnpm add -D tailwindcss postcss autoprefixer && pnpm dlx tailwindcss init -p`
- `pnpm add react-router-dom@latest axios zustand clsx`
- `pnpm add lucide-react @tremor/react`
- `pnpm add @fontsource-variable/geist @fontsource-variable/geist-mono @fontsource/instrument-serif`
- `pnpm add @twa-dev/sdk`
- `pnpm add -D vitest @testing-library/react @testing-library/jest-dom jsdom @playwright/test eslint prettier eslint-config-prettier`
- `.gitignore` стандартный Vite + `.env.local`.
- `tsconfig.json` strict (`strict: true`, `noUncheckedIndexedAccess: true`).
- `vite.config.ts` — алиас `@/* → ./src/*`.
- Удали `src/App.css`, `src/assets/*`, дефолтный counter в App.tsx — нужен голый каркас.

### #2 — `feat(design): Voice + InsightFlow tokens (Tailwind config + globals.css)`

- Перенеси CSS variables из `design/iterations/insightflow/theme.css` в
  `src/styles/tokens.css` (split light/dark layers, добавь Telegram-theme-bridge `var(--tg-theme-*)` overlay).
- В `tailwind.config.ts`: extend theme.colors (brand, accent, surface, ink etc),
  theme.fontFamily (sans/mono/serif), theme.borderRadius (14px card, 18px sheet),
  theme.spacing (8/16/20/24 ladder).
- Импортируй fonts в `src/main.tsx`:
  ```ts
  import '@fontsource-variable/geist'
  import '@fontsource-variable/geist-mono'
  import '@fontsource/instrument-serif/400-italic.css'
  ```
- Установка shadcn/ui для Vite: следуй [shadcn Vite guide](https://ui.shadcn.com/docs/installation/vite). Base color = slate, primary color = violet, CSS variables = yes.
- Добавь shadcn primitives: button, input, dialog, sheet, dropdown-menu, tabs, badge (через `pnpm dlx shadcn@latest add ...`).

### #3 — `feat(telegram): WebApp SDK wrapper + theme bridge + safe-area`

- `src/lib/telegram/sdk.ts` — wrapper над `window.Telegram?.WebApp` (`initData`, `themeParams`, `BackButton`, `MainButton`, `ready()`, `expand()`). Type-safe.
- `src/lib/telegram/theme.ts` — читает `tgWebApp.themeParams` → выставляет CSS variables `var(--tg-theme-*)`. Если вне Telegram — fallback на InsightFlow palette.
- `src/components/layout/ThemeProvider.tsx` — applies theme on mount + reacts to `themeChanged` event.
- `src/main.tsx` — обернуть `<App />` в `<ThemeProvider>`, добавить tg-script в `index.html` head.
- Тесты на theme.ts (Vitest): задал mock-themeParams → проверь CSS variables на root.

### #4 — `feat(auth): initData → JWT auth flow + Zustand session store`

- `src/lib/telegram/auth.ts` — функция `bootstrapAuth(apiBaseUrl, authEndpoint)`:
  1. Читает `initData` из `window.Telegram.WebApp.initData`
  2. `POST {apiBaseUrl}{authEndpoint}` body `{ init_data }`
  3. Receives `{ token, ... }` — кладёт в Zustand store
  4. Returns store state
- `src/lib/state/session-store.ts` — Zustand: `{ token, telegramId, isReady, error, bootstrap() }`.
- `src/lib/hooks/useAuth.ts` — convenience hook.
- `src/routes/root.tsx` — bootstrap → если ready → `<Navigate to="/example/dashboard">`; если error → error UI.
- Тесты: mock window.Telegram, mock fetch, проверь что bootstrap идёт правильным URL.

### #5 — `feat(api): axios client with JWT interceptor + generic types`

- `src/lib/api/client.ts` — axios instance:
  - `baseURL = import.meta.env.VITE_API_BASE_URL`
  - Request interceptor: `Authorization: Bearer ${token}` из session store
  - Response interceptor: 401 → clear session + редирект на root
- `src/lib/api/types.ts` — generic типы: `ApiError`, `Paginated<T>`. Без domain-types.
- `src/lib/hooks/useApi.ts` — generic hook `useApi<T>(key, fetcher)` — простой data-fetching helper без SWR/React-Query (template остаётся минималистичным; instance может добавить).
- Тесты: axios interceptor добавляет Authorization, 401 чистит store.

### #6 — `feat(layout): AppShell — Header + BottomNav + safe-area`

- `src/components/layout/AppShell.tsx`:
  - Header 44px: opt left back-arrow (если `useTelegramBackButton` неактивен), middle title (Instrument Serif italic), opt right slot
  - Main scroll area (flex-1)
  - BottomNav 56px: 4-5 slots, accept `items: NavItem[]` prop (icon + label + href)
  - Safe-area-inset через `padding-bottom: env(safe-area-inset-bottom)`
- `src/components/layout/Header.tsx`, `src/components/layout/BottomNav.tsx` — separate.
- `src/components/layout/BackButton.tsx` — Telegram BackButton bridge.
- Используй lucide-react иконки. shadcn button где уместно.

### #7 — `feat(components): generic KPICard + LineChartCard + BarChartCard + ChatWidget + example route`

- `src/components/kpi/KPICard.tsx`:
  - props: `{ label, value, delta?, deltaKind?, spark? }`
  - 14 radius, 1px border, no shadow
  - Geist Mono для value, tabular-nums
- `src/components/charts/LineChartCard.tsx` — обёртка `<LineChart>` from @tremor/react с InsightFlow violet/cyan палитрой
- `src/components/charts/BarChartCard.tsx` — то же для BarChart
- `src/components/chat/ChatWidget.tsx` — composer + scroll-area + messages list
- `src/components/chat/Message.tsx` — bubble. Props: `{ role: 'user'|'agent'|'thinking', content, chart? }`
- `src/routes/example/dashboard.tsx` — демо: AppShell + KPICard grid 4-up (generic mock: "Active users", "Avg session", "Topics", "Reply rate") + один LineChartCard со mock-данными.
- Router setup в `src/main.tsx`: `createBrowserRouter([{path:'/', element:<Root/>}, {path:'/example/dashboard', element:<ExampleDashboard/>}])`.
- `vercel.json` — `{ "rewrites": [{"source":"/(.*)", "destination":"/index.html"}], "headers":[{"source":"/(.*)", "headers":[{"key":"Content-Security-Policy", "value":"frame-ancestors https://web.telegram.org https://*.telegram.org"}]}]}`.
- README quick-start: 5 шагов (clone → install → set VITE_API_BASE_URL → replace example route → deploy на Vercel).
- Vitest на: KPICard renders props correctly; ChatWidget submits on enter.

## Final commits (если останется время)

- `test: Playwright smoke (bootstrap → auth-mock → /example/dashboard renders)`
- `docs: README — full quick-start, env vars, Vercel deployment guide`

## Out of scope

- ❌ Доменные страницы (Phase 4C)
- ❌ Реальная backend-интеграция (template работает с mock backend в Playwright)
- ❌ Tweaks panel из InsightFlow — это dev-only прототип, в template не нужен (instance может включить опционально)
- ❌ i18n библиотеки — template Russian by default, но без heavy framework
- ❌ State management кроме session-store (Zustand)
- ❌ SWR/React-Query — instance может добавить
- ❌ Storybook — overhead не оправдан для template
- ❌ SSR / server components — Vite SPA, всё клиентское

## Hard rules

1. **Bash discipline:** одна Bash-call = одна команда. Никаких `&&;|`.
2. **Domain-neutral** в каждом файле template'а. Mock-data — generic.
3. **Commit-before-next** — после каждого шага зелёные тесты + git commit + git status clean.
4. **Не модифицируй `design/`** — это input, read-only. Если что-то нужно "выдрать" из дизайна → переписывай как TS-код в template, не копируй inline JSX.
5. **TypeScript strict.** `tsc --noEmit` clean после каждого коммита.
6. **Mobile-first.** Все компоненты рендерятся корректно при 375px width.
7. **Никаких backend-вызовов в template** — только mock в Playwright или Vitest.
8. **import.meta.env** для env vars (НЕ process.env — это Vite).

## Verification (gate перед финальным отчётом)

1. `pnpm install && pnpm dev` — стартует без ошибок на localhost:5173 (Vite default)
2. `pnpm test` (Vitest) — все юниты зелёные
3. `pnpm test:e2e` (Playwright) — bootstrap smoke зелёный
4. `pnpm lint && pnpm typecheck` — clean
5. `pnpm build` — production build проходит, генерится `dist/` с index.html + bundled JS/CSS
6. Открыть http://localhost:5173 в браузере (mobile viewport DevTools) → видеть AppShell + /example/dashboard
7. Telegram BackButton bridge тестируется руками: открой страницу `?tg=mock` (mock Telegram env), bottom-nav + back работают

## Финальный отчёт

1. `git log --oneline` — список 7+ commits
2. Test counts: было 0 / стало N
3. Структура файлов tree:
   ```
   src/
     main.tsx
     routes/
       root.tsx
       example/dashboard.tsx
     components/{kpi,charts,chat,layout,ui}/
     lib/{telegram,api,state,hooks}/
     styles/{tokens.css,globals.css}
   tests/{unit,e2e}/
   public/
   vite.config.ts
   vercel.json
   tailwind.config.ts
   design/ ← input, read-only
   ```
4. README quick-start ссылка
5. **Mark this repo as Template на GitHub:** Settings → Template repository ✓ (это user сделает в UI)
6. Готовность к Phase 4C: instance клонирует через "Use this template" → заменяет `src/routes/example/` на domain pages → подключает реальный backend
