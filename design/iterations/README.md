# Design Iterations

Эта папка — **расширения** базовой Voice design system (см. `design/README.md` +
`design/SKILL.md`). Каждая поддиректория = отдельный эксперимент дизайнера
поверх Voice tokens. Implementer (Phase 4B/4C) выбирает один как input,
ориентируясь на запрос юзера; остальные остаются в репо как reference.

## Активные итерации

### `insightflow/` — editorial + violet/cyan

Hybrid Voice + InsightFlow: те же Voice tokens (geometry, density, mobile-first
375px, Lucide icons, no-shadow rule), плюс:

- **Headings** — `Instrument Serif` italic вместо Geist Sans (теплее, editorial).
- **Brand palette** — violet `#7c3aed` primary + cyan `#06b6d4` accent (вместо
  Voice neutral). Хранится в `theme.css` как CSS variables — можно переопределить
  через `.brand-indigo` / `.brand-teal`.
- **Surface** — paper-like с radial brand glow (опционально).
- **Live theming** — `tweaks-panel.jsx` показывает как переключать brand color,
  serif/sans headings, density, dark mode через CSS vars в рантайме. Это **dev
  prototype**, не для production — production-инстанс выбирает фиксированные
  значения в build-time.

Файлы:
- `theme.css` — переопределение `--font-head`, `--primary`, `--accent`, geometry
- `index.html` — standalone preview (открывается в браузере, показывает phone-frame)
- `app.jsx` — router 5 экранов (inline React+Babel — НЕ production-код)
- `components.jsx` — primitives reference paint
- `screens/{Dashboard,Metrics,Topics,Clients,Ask}.jsx` — 5 экранов, повторяющих
  domain `telegram-waiter-admin-miniapp` (но сами — paint-only)
- `data.jsx` — моки для preview
- `tweaks-panel.jsx` — dev-only theme switcher
- `uploads/insightflow2.html` — экспортированный HTML preview (можно открыть напрямую)
- `scraps/dark.png` — dark mode screenshot reference

## Что implementer берёт отсюда

1. **CSS variables** из `theme.css` — копирует в production-проект как
   `src/styles/tokens.css` (variables) + расширяет Tailwind config (палитра,
   typography, geometry).
2. **Layout структуру** экранов (composition порядка sections, spacing) — НЕ
   копирует JSX как есть, переписывает в production TS/TSX.
3. **Components composition** — какие primitives на каких экранах используются
   (KPICard / LineChartCard / BarChartCard / ChatWidget / Sheet etc.).

## Что implementer НЕ берёт

- Сам Babel-inline JSX (это reference, не код)
- `tweaks-panel.jsx` — это live theming dev-tool, в production не нужен
- Моки из `data.jsx` — в production данные приходят из FastAPI backend

## Voice hard rules продолжают действовать

Iteration переопределяет **palette + typography + geometry**, но не **rules**:
- ❌ NO imagery (no stock photos / illustrations of people)
- ❌ NO drop shadows
- ❌ NO background gradients на page surfaces (исключение — brand-mark circle)
- ✅ Mobile-first 375px baseline
- ✅ Lucide icons only, 24px grid, stroke 1.75
- ✅ Russian primary, sentence case
- ✅ Max 1 emoji per screen

Подробности — `design/SKILL.md`.
