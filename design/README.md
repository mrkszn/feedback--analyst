# Voice — Design System

A design system for **Voice**, a Telegram Mini App + bot platform that helps
businesses collect customer feedback through surveys and conversation, and
gives owners analytics on top of it.

The platform ships as two paired Telegram surfaces:

| Surface | Audience | Role |
|---|---|---|
| **Voice / Admin** (purple) | Business owner, manager | KPI overview, drill-downs, search, ask-an-agent. The Mini App. |
| **Voice / Receiver** (indigo) | End customer | Conversational bot that collects the feedback. |

Voice is **domain-neutral** — a template. The same product gets re-skinned for
a restaurant, a booking service, an e-commerce shop, a SaaS tool. Component
naming stays generic (`KPICard`, not `RestaurantKPICard`); only mock copy is
themed per instance.

---

## Source materials

This system was assembled from:

- **Original product brief** (Russian) — pasted by the user; covers tech stack,
  audience, page list and tone direction.
- **Brand marks** — two logo variants uploaded by the user:
  - `uploads/07-voice-A-ADMIN_FEEDBACK.svg` — Admin (purple)
  - `uploads/07-voice-F-Feedback_Receiver.svg` — Receiver (indigo)
- **Reference repo** — [`mrkszn/telegram-miniapp-template`](https://github.com/mrkszn/telegram-miniapp-template) — currently a
  placeholder (empty README only). No existing code to lift from; the
  visual system below is the starting point that downstream agents will build
  against.

If you have access to a newer iteration of the template repo, or to a Figma
file, link it and we'll fold it in.

---

## Index

| File / folder | What's in it |
|---|---|
| `README.md` | This file — context, content rules, visual foundations, iconography. |
| `SKILL.md` | Cross-compatible Agent Skill manifest (works in Claude Code too). |
| `colors_and_type.css` | All color + type CSS variables, light + dark, plus Telegram-theme bridges. |
| `fonts/` | Geist Sans + Geist Mono (Google Fonts). |
| `assets/` | Logo SVGs, Telegram-style iconography. |
| `preview/` | Small HTML cards rendered into the Design System tab. |
| `ui_kits/admin/` | Full UI kit for the **Voice / Admin** Mini App. Six screens, interactive. |
| `slides/` | _Not used in this system — no deck template was provided._ |

---

## Product context — what Voice does

A business installs two Telegram bots:

1. **Receiver bot** talks to their customers, runs micro-surveys, captures
   open-text comments, sometimes voice notes. It's friendly and short.
2. **Admin bot** opens the Voice Mini App for the business owner. They see:
   - KPI dashboard (counts, average sentiment, top topics)
   - Metrics drill-down (line + bar charts per metric)
   - Topics drill-down (positive / negative breakdown + mentions)
   - Clients list + per-client deep dive
   - "Ask" — a chat-style agent for ad-hoc questions over their data

Backend is FastAPI; frontend is Next.js 16 + Tailwind + shadcn/ui + Tremor
charts, mounted inside Telegram WebApp.

---

## CONTENT FUNDAMENTALS

The Voice voice is **professional-warm, sparse, Russian-first**. Closer to
Linear and Stripe than to consumer apps.

### Tone

- **Direct, no hype.** "Feedback за 7 дней" — not "🎉 Look at all this amazing
  feedback!". The product is a tool; the copy gets out of the way.
- **Calm density.** A KPI card has a label, a number, and a delta. No
  motivational sentence underneath.
- **Russian primary, English fallback.** Russian copy for end-users and
  admins; technical strings, code identifiers and component names stay
  English (`KPICard`, `metric_key`).
- **Domain-neutral in template-layer.** "feedback", "users / clients",
  "sessions", "topics", "metrics" — never "guests", "diners", "shoppers".
  Industry-specific words only appear in mock data.

### Casing

- **Sentence case for everything user-facing**: headings, buttons, labels,
  menu items. "Recent feedback", not "Recent Feedback".
- **Numbers and units**: thin space between value and unit ("12 отзывов",
  "4.6 / 5"). Percentages tight ("+12%").
- **No ALL CAPS**, except small overline labels in 11px tracking-wide for
  section dividers ("OVERVIEW", "METRICS").

### Pronouns + voice

- **"Вы" formal** in Russian admin copy. The user is running a business; the
  app addresses them as a peer, not a friend.
- **"Ты" friendly** in Receiver bot copy — the bot is talking to a customer
  doing a 30-second survey, warmer register makes sense.
- No first-person ("I", "we") from the product itself; the product is
  invisible. The Ask agent does say "I" because it's a literal conversation.

### Emoji + punctuation

- **Emoji: max 1 per screen.** Almost always avoided. The bot might use a
  single 👋 in its greeting; the admin app uses **none**.
- **Use real typographic punctuation**: em dash (—), curly quotes («…»
  Russian, "…" English), proper ellipsis (…). Never `--` or `...`.
- **No trailing exclamation marks** in admin copy. Receiver copy: at most one
  per message, only on the welcome.

### Length

- Button labels: 1–2 words. ("Open", "Reply", "Search clients".)
- Tooltips + helper text: ≤ 60 characters.
- Empty states: one line of plain explanation + one CTA. No illustrations
  with a paragraph underneath.
- Error states: state what happened in plain language, give a single
  retry / undo affordance.

### Examples (canonical voice)

> **Good.** "Нет данных за выбранный период."
> **Bad.**  "Упс! Похоже, здесь ещё ничего нет 🙈"
>
> **Good.** "Спросите что-нибудь о ваших отзывах."  (Ask placeholder)
> **Bad.**  "Привет! Я ваш AI-помощник, готов помочь вам разобраться…"
>
> **Good.** "12 отзывов · +18% к прошлой неделе"
> **Bad.**  "Wow! You got 12 new pieces of feedback (+18% week over week 🚀)"

---

## VISUAL FOUNDATIONS

Voice is a **dense, business-focused mobile dashboard**. Everything below
serves clarity over flash.

### Color

Two parallel palettes — one tuned for the Admin Mini App (purple primary,
amber accent), one for the Receiver bot (indigo). Both ship in light and dark.

- **Primary, Admin**: violet 500 (`#8b5cf6`) → violet 800 (`#5b21b6`).
  Used for active states, primary buttons, the brand mark, sentiment-positive
  fills.
- **Primary, Receiver**: indigo 500 (`#6366f1`) → indigo 700 (`#4338ca`).
- **Accent**: amber 500 (`#f59e0b`). Pulled from the orange dashed line in
  the Admin logo. Sparingly — for "needs attention" badges, the orange dot in
  the KPI delta when it's flat, and the Ask agent thinking indicator.
- **Neutrals**: slate scale, OKLCH-tuned. `bg`, `surface`, `surface-2`,
  `border`, `border-strong`, `text-1`, `text-2`, `text-3`, `text-disabled`.
- **Semantic**: success (emerald 500), warning (amber 500), danger (rose
  500), info (sky 500). All have a `-soft` background companion (8% alpha).
- **Telegram bridge**: every semantic var has a `var(--tg-theme-*)` fallback
  layer. When mounted in Telegram, the app picks up the user's chat theme;
  outside Telegram, it falls back to the Voice palette.

### Type

- **Display + Body**: **Geist Sans** (Vercel's geometric grotesk). Pulled
  from Google Fonts. 400 / 500 / 600 / 700. Good Cyrillic coverage.
  Substitution flag: Geist Sans is the canonical face; if you prefer the
  internal "Manrope" or system stack, swap `--font-sans` in
  `colors_and_type.css`.
- **Mono**: **Geist Mono** for numbers in KPI cards, code blocks, the metric
  table's value column.
- **Scale** (mobile baseline):
  - `display`  28 / 32 / -0.02em / 600
  - `h1`       22 / 28 / -0.01em / 600
  - `h2`       18 / 24 / -0.005em / 600
  - `h3`       16 / 22 / 0 / 600
  - `body`     15 / 22 / 0 / 400
  - `body-sm`  13 / 18 / 0 / 400
  - `caption`  12 / 16 / 0 / 500
  - `overline` 11 / 14 / 0.08em / 600 — uppercase
- **Tabular numerals on by default** for every KPI / chart label
  (`font-variant-numeric: tabular-nums`).

### Spacing + layout

- **4px base grid.** Spacing tokens: 2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64.
- **Page padding**: 16px mobile, 24px ≥ 768.
- **Card padding**: 16px mobile, 20px ≥ 768.
- **Section gap**: 24px.
- **Mobile baseline**: 375 × 667. Tablet at 768. The Mini App is
  always vertical inside Telegram's webview — no landscape layout.
- **Fixed elements**: a bottom-nav (56px tall) sits above the safe-area
  inset. Top has a 44px header with the Telegram BackButton bridge — when
  Telegram's native back is active, we hide our in-app one.

### Backgrounds, gradients, imagery

- **No full-bleed photography.** No stock imagery, no illustrations of
  people. This is a dashboard.
- **No background gradients** on page surfaces — flat `--surface`.
- **One gradient allowed**: the brand-mark circle (violet 500 → violet 800
  diagonal). It appears only in the logo and on a single "hero" surface in
  onboarding. Never as a page background.
- **No patterns, no textures, no noise.**

### Borders, shadows, elevation

- **Borders carry the heavy lifting**, not shadows. `--border`
  (slate 200 / slate 800) on every card; `--border-strong` on focused or
  hovered surfaces.
- **Shadow scale** — soft and shallow, sized for mobile glass:
  - `shadow-1` — popover / sheet header divider. `0 1px 0 rgba(15,23,42,0.04)`.
  - `shadow-2` — floating action button, bottom-nav top edge. `0 -4px 12px rgba(15,23,42,0.06)`.
  - `shadow-3` — modal sheet. `0 24px 48px -12px rgba(15,23,42,0.18)`.
- **Inner shadows**: only on pressed buttons (`inset 0 1px 0 rgba(0,0,0,0.06)`).
- **Protection gradients**: not used. Bottom-nav has a 12px top fade to
  surface so list content doesn't visually collide.

### Corner radii

- **Radius tokens**: 4 (tag), 6 (input), 8 (button, small card), 12 (card),
  16 (sheet / modal), 999 (pill, avatar).
- **Cards** use 12. **Sheets** use 16 with the top two corners only.
- No mixed radii on the same surface.

### Hover + press + focus

- **Hover** (desktop only — pointer: fine): `--surface-hover`, a 4% darken
  of `--surface`. Borders go to `--border-strong`. No motion.
- **Press / active**: 96% scale on the whole control, opacity 0.85 on text,
  120ms ease-out. Felt on real touch.
- **Focus**: 2px outline in `--ring` (primary at 40% alpha), offset 2px.
  Always visible for keyboard.
- **Disabled**: 40% opacity, no pointer events. Never grey-out borders.

### Motion

- **No motion fluff.** No parallax, no scroll-jacking, no spring physics.
- **Transitions**: 120ms (state), 200ms (layout). Easing
  `cubic-bezier(0.2, 0, 0, 1)` — the standard Tailwind / shadcn ease-out.
- **Bottom-sheet open**: 240ms, same ease, translateY only.
- **Loading**: a 1.2s linear shimmer on skeletons, that's it.

### Transparency + blur

- **Used twice**: (a) the bottom-nav has a `backdrop-blur(12px)` with
  `--surface` at 80% so content visible behind feels grounded, and (b) the
  modal scrim is `rgba(15,23,42,0.5)` flat — no blur, to keep perceived
  performance high on mid-range Android.
- Everything else is opaque.

### Cards

- 1px solid `--border`
- 12px radius
- 16px (mobile) / 20px (tablet) padding
- No shadow
- Optional 1px inner top highlight in dark mode (`box-shadow: inset 0 1px 0 rgba(255,255,255,0.04)`).

---

## ICONOGRAPHY

Voice uses **[Lucide](https://lucide.dev)** as its icon set, loaded from CDN
in mocks and as the `lucide-react` package in production.

### Why Lucide

- Same stroke language as Telegram's own UI (1.5px on a 24px grid).
- shadcn/ui ships against Lucide by default; same as Stripe + Linear's
  visual register.
- Covers everything in the Voice surface area: chart, search, filter, chat,
  user, back, more, plus, minus, check, x, alert, ring-bell, trending-up,
  trending-down, dots, arrow-right.

### Rules

- **24px** in nav + headers, **20px** inline with body text, **16px** inside
  badges and chips. Stroke `1.75`.
- **Color**: `currentColor` always. Never tint an icon a different colour
  from the text next to it, except: red for destructive, green for success,
  amber for warning when no text is present.
- **Filled variants**: only the brand mark and active bottom-nav state.
  Everything else is stroke.
- **No emoji as icons** in the Admin app. The Receiver bot may use a single
  👋 in its first greeting; that's the only place emoji is allowed in the
  whole product.
- **No unicode symbols as icons** (no `→`, no `★`, no `•` standing in for an
  icon — only inside body text as typographic glyphs).

### Logos

The two brand marks live in `assets/`:

- `assets/voice-admin.svg` — purple, with the amber centre line. Used in the
  Mini App splash and the admin-bot avatar.
- `assets/voice-receiver.svg` — indigo, no centre line. Used in the receiver
  bot avatar.

The waveform speech-bubble glyph (white-on-color) is the only proprietary
illustration; don't redraw it. Both are exported at 512×512 with a
256-viewBox so they scale cleanly down to 24px favicons.

### Substitution flag

- **Geist Sans / Geist Mono** are loaded from Google Fonts. If you have a
  licensed copy of the canonical typeface (or want Inter Display / Manrope
  instead), swap `--font-sans` and `--font-mono` in `colors_and_type.css`.
- **Lucide** is a placeholder for any heavier brand-specific icon set. If
  the Voice team commissions custom icons, drop the SVG sprite in
  `assets/icons/` and update the docs.

---

## How to read this system

If you're an agent building a screen, slide, or asset for Voice:

1. Start with `colors_and_type.css` — link it from your HTML.
2. Read `SKILL.md` for the short version of these rules.
3. Pull components from `ui_kits/admin/` — they're high-fidelity, slot-in
   recreations of the six template pages.
4. If you need an icon, write `<i data-lucide="search"></i>` and load Lucide
   from CDN; don't hand-roll SVGs.
5. If you need imagery, **stop**. Voice does not use imagery. Use type,
   colour, and whitespace.

If something looks wrong, it probably is — flag back to the user before
inventing a new motif.
