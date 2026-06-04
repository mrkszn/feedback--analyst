# Template: `tg-clinic`

Industry bundle for **clinic / beauty-salon visit feedback over Telegram**. The
second template in the M1 architecture — authored by copying `tg-restaurant` and
swapping only the prompt tone and the question seed. It exists as the
**extraction proof**: a new industry needs no `core/` changes, just a new
`templates/<industry>/` bundle.

A client instance (`clients/<name>/`) references this template by name. See
[../../docs/ONBOARDING_CLIENT.md](../../docs/ONBOARDING_CLIENT.md) for the
per-client flow and [../../docs/TEMPLATE_AUTHORING.md](../../docs/TEMPLATE_AUTHORING.md)
for how templates are authored.

## What's in here

| File | Purpose |
|---|---|
| `config.yaml` | Same wiring as `tg-restaurant` (telegram guest + admin + HTTP API, Supabase + Pinecone) — only `name` differs. Holds no secrets, only env-var names. |
| `prompts/dialogue.txt` | Guest-dialogue prompt with a calmer, tactful clinic/salon tone (privacy-aware; avoids asking for sensitive medical detail). Keeps the `{restaurant_context}` placeholder. |
| `prompts/analyze.txt` | Feedback-analysis prompt — scoped to *service perception*, explicitly not medical interpretation. |
| `prompts/card.txt` | Client-card prompt — third-person for a clinic/salon administrator, excludes sensitive medical data. |
| `question_seed.json` | 7 clinic/salon questions (wait time, staff attentiveness, cleanliness, explanation clarity, NPS, price/value, improvement wish) matching the `questions` schema. |

## What this template overrides vs `tg-restaurant`

- **Prompt tone:** calm/tactful/privacy-aware instead of warm/casual.
- **Question seed:** clinic metrics instead of restaurant metrics.
- **Name:** "Telegram Clinic Feedback".

Channels, presentations, and storage are identical — proving a template swap is
purely content, not wiring.

## Running

```bash
python -m core.bootstrap clients/<name>   # where clients/<name>/config.yaml has `template: tg-clinic`
```
