# Template: `tg-restaurant`

Industry default bundle for **restaurant / cafe feedback collection over Telegram** —
the original telegram-waiter setup, extracted as the first template (M1 / Phase R3).

A client instance (`clients/<name>/`) references this template by name and may
override any field. See `docs/ONBOARDING_CLIENT.md` for the per-client flow.

## What's in here

| File | Purpose |
|---|---|
| `config.yaml` | Declares channels (guest bot), presentations (admin bot + HTTP API), storage (Supabase + Pinecone), prompt paths, and the question seed. Holds **no secrets** — only env-var *names*. |
| `prompts/dialogue.txt` | Guest-dialogue system prompt (warm interviewer tone). Mirrors `DIALOGUE_SYSTEM` in `core/agent/prompts.py`. |
| `prompts/analyze.txt` | Free-text feedback analysis prompt. Mirrors `ANALYZE_SYSTEM`. |
| `prompts/card.txt` | Client-card synthesis prompt. Mirrors `CARD_SYSTEM`. |
| `question_seed.json` | 7 default interview questions for an empty `questions` table (text / number / enum / boolean), matching the schema in `core/storage/migrations/0001_init.sql`. |

## Running

A client built on this template runs via the bootstrap entry point:

```bash
python -m core.bootstrap clients/<name>
```

This starts every channel and presentation declared in the merged config. The
legacy per-component entry points (`python -m channels.telegram.guest_bot`, etc.)
still work for dev.

## Customizing per client

In `clients/<name>/config.yaml`, set `template: tg-restaurant` and add an
`overrides:` block to change any field — e.g. point a prompt at a custom file
under `clients/<name>/overrides/prompts/`.
