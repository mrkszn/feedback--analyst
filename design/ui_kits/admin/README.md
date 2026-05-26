# Voice / Admin — UI kit

Interactive recreation of the six template screens for the **Voice / Admin
Mini App** (Telegram WebApp).

This is a UI kit, not production code:

- React + Babel inline (no build step)
- All visuals via `colors_and_type.css` at the project root
- Mock data is in `data.jsx`; nothing hits a real API
- Mounted inside a 390×780 phone shell with a fake Telegram top bar so the
  composition reads as a Mini App, not a desktop page

## Files

| File | Role |
|---|---|
| `index.html`            | Entry. Phone frame + script loading. |
| `miniapp.jsx`           | Tab router + global feedback-detail sheet. |
| `components.jsx`        | `Icon`, `Header`, `BottomNav`, `KPICard`, `Spark`, `Chip`, `Avatar`, `FeedbackRow`, `SectionHead`. |
| `data.jsx`              | Mock feedback, topics, metrics, clients. |
| `screens/Dashboard.jsx` | KPI grid + top topics + recent feedback. Date range chips. |
| `screens/Metrics.jsx`   | Filter bar + line chart + per-day table. |
| `screens/Topics.jsx`    | Positive / negative tabs + top-5 bars + mentions. |
| `screens/Clients.jsx`   | Search + list + bottom-sheet deep dive. |
| `screens/Ask.jsx`       | Chat with the agent + thinking indicator + suggested prompts. |
| `ios-frame.jsx`         | Not currently wired into `index.html` — kept around in case we want a real iOS bezel later. |

## Screens

1. **App shell** — top header (44 px), 5-slot bottom nav (56 px) with center
   FAB style entry on the active tab. The shell is the wrapper in
   `miniapp.jsx`; every screen sits inside it.
2. **Dashboard** (`/overview`) — 4-up KPI grid, top topics mini-chart, recent
   feedback list, date range chips with custom-range affordance.
3. **Metrics** (`/metrics`) — metric picker, date range, day/week toggle.
   Tremor-style line chart (gradient area + dots) with daily values below.
4. **Topics** (`/topics`) — positive/negative tab, bar chart of top 5 topics,
   recent mentions list.
5. **Clients** — search field, list with sentiment + sessions metadata,
   bottom-sheet with full feedback history.
6. **Ask** — chat composer, suggested prompt cards, agent thinking indicator
   (3 amber dots), inline chart in agent reply.

## Domain neutrality

Component names are generic (`KPICard`, `FeedbackRow`). Mock copy is
delivery-service flavored to feel realistic but every string is a one-line
edit in `data.jsx`. The same kit re-skins for a restaurant / SaaS / e-comm
instance by swapping the data only.

## Caveats

- The Telegram chrome at the top is **decorative**. Real Mini Apps render
  inside Telegram and don't draw their own status row — the bar is here so
  the prototype reads like a Mini App and not a webpage.
- No real Telegram `BackButton` integration. The header back chevron is
  hidden on tab roots and replaced by the bottom-sheet pattern.
- Charts are hand-rolled SVG. In production they should come from Tremor
  (`<LineChart/>`, `<BarChart/>`) per the brief; the math + visuals match.
- Dark mode tokens exist in `colors_and_type.css` but this kit renders in
  light. Toggling is one `[data-theme="dark"]` away.
