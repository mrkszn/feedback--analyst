---
name: voice-design
description: Use this skill to generate well-branded interfaces and assets for Voice — a Telegram Mini App + bot platform for collecting customer feedback and showing analytics. Contains essential design guidelines, colors, type, fonts, assets, and UI-kit components for prototyping.
user-invocable: true
---

Read the `README.md` file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy
assets out and create static HTML files for the user to view. If working on
production code, you can copy assets and read the rules here to become an
expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they
want to build or design, ask some questions, and act as an expert designer
who outputs HTML artifacts _or_ production code, depending on the need.

## Quick orientation

- **What Voice is**: a Telegram Mini App that helps businesses see analytics
  on customer feedback collected by a paired Telegram bot.
- **Two surfaces**: Voice / Admin (purple, the Mini App) and
  Voice / Receiver (indigo, the customer-facing bot).
- **Tech context**: Vite 5 + React 19 + Tailwind + shadcn/ui + Tremor charts.
  Mobile-first (375 px baseline). (Stack switched from Next.js — Mini App is a
  pure WebView SPA, SSR is impossible, so Vite gives ~200 KB bundle vs Next ~500
  KB+ — critical for cold-load UX in Telegram.)
- **Tone**: professional-warm, Linear / Notion / Stripe register — dense,
  business-focused, Russian-first copy, no marketing hype, max 1 emoji per
  screen.

## Files in this skill

- `README.md` — full content + visual + iconography guidelines (read first).
- `colors_and_type.css` — drop-in CSS variables for colour, type, spacing,
  radii, shadows; light + dark + Telegram theme bridge.
- `fonts/` — _none shipped_; Geist Sans + Geist Mono are loaded from Google
  Fonts inside the CSS. Substitute by editing `--font-sans` / `--font-mono`.
- `assets/` — brand marks (`voice-admin.svg`, `voice-receiver.svg`) plus PNG
  fallbacks.
- `preview/` — 23 small HTML cards specimening every primitive (colors,
  type, spacing, components). Open any of them as a reference.
- `ui_kits/admin/` — high-fidelity React+Babel UI kit for the six template
  screens of the Admin Mini App. `index.html` is a click-thru prototype.
- `iterations/` — extended design experiments stacked on top of Voice tokens.
  Currently: `iterations/insightflow/` (violet + cyan brand, Instrument Serif
  italic headings, live theming via Tweaks panel). See `iterations/README.md`
  for which iteration is the active reference for Phase 4B/4C.
- `SKILL.md` — this file.

## Hard rules (the ones that get violated most)

1. **No background gradients on page surfaces.** The only gradient allowed
   is the brand-mark circle.
2. **No imagery.** No stock photos, no illustrations of people. Voice is a
   dashboard.
3. **Geist Sans + Geist Mono only.** Pinned with `font-variant-numeric:
   tabular-nums` for any numeric cell.
4. **Lucide icons only.** 24 px grid, stroke 1.75, always `currentColor`.
   No emoji as icons. No SVG drawn from scratch.
5. **Card = 1 px border + 12 px radius + 16/20 px padding. No shadow.**
6. **Mobile-first.** Design at 375 px. Hit targets ≥ 44 px.
7. **Russian primary, English fallback.** "Вы" formal for admin, "ты" warm
   for the Receiver bot. Sentence case for everything.

If you're unsure about a motif, default to plain. The Voice brand is
deliberately quiet — restraint reads as professional here.
