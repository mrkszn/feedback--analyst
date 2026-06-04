# Architecture — M1 layered + template-based

This document is the high-level map of the codebase after the **M1 refactor**
(phases R1–R4). It explains the layers, what stays fixed across clients vs. what
varies, how data flows, and how a client instance boots.

The refactor turned a single hard-wired "telegram-waiter" into a **layered +
template-based** monorepo so that (a) onboarding a new client is hours not days,
(b) core bug-fixes reach every client automatically, and (c) the directory
structure itself declares what is customizable.

Real artifacts (git history is the source of truth):

| Phase | What | Commit |
|---|---|---|
| R1 | Layered structural rename (`core/` / `channels/` / `presentations/`) | `fa62669` |
| R2 | `StorageAdapter` / `VectorStore` Protocols + Supabase/Pinecone adapters | `64231ac` |
| R3 | Template loader + bootstrap + `tg-restaurant` template + `_example` client | `6c20b70` |
| R4 | Architecture docs + onboarding/authoring guides + `tg-clinic` stub | (this phase) |

The full rationale and phase plan live in
[REFACTOR_M1_PLAN.md](REFACTOR_M1_PLAN.md).

---

## Layers

```
telegram-waiter/
├── core/                     ← the kernel — same for every client
│   ├── agent/                LLM nodes (analyze, dialogue, card, extract, select,
│   │   ├── nodes/            synthesize_questions, admin_assistant) + analytics_agent
│   │   ├── analytics_agent/  two-phase analytics (interpret → execute → synthesize)
│   │   └── prompts.py        prompt-builder constants (ANALYZE/DIALOGUE/CARD/…)
│   ├── services/             business logic — all async (admin_auth, analytics,
│   │                         clients, questions, sessions, statistics)
│   ├── integrations/         SDK wrappers (openai_chat, openai_embed, whisper, pinecone)
│   ├── storage/              persistence boundary
│   │   ├── protocol.py       StorageAdapter Protocol
│   │   ├── adapters/         supabase (prod), in_memory (tests)
│   │   ├── vector/           VectorStore Protocol + pinecone adapter
│   │   └── migrations/       SQL schema (0001_init.sql = table source-of-truth)
│   ├── tools/                LangChain tool wrappers over services
│   ├── utils/                shared helpers
│   └── bootstrap/            R3 — loader, AppContext, registry, __main__
│
├── channels/                 ← capture layer: how feedback comes IN
│   └── telegram/
│       ├── guest_bot/        guest writes feedback → interview → card
│       └── common/           shared aiogram middleware
│
├── presentations/            ← admin-facing layer: how data goes OUT
│   ├── telegram_admin/       admin bot (questions, /statistics, /topics, miniapp)
│   └── http_api/             FastAPI thin layer for the admin Mini App
│
├── templates/                ← industry bundles (config + prompts + question seed)
│   ├── tg-restaurant/        first template (the original setup)
│   └── tg-clinic/            second template stub (extraction proof, R4)
│
└── clients/                  ← per-instance config (real clients gitignored / private)
    └── _example/             committed reference: template ref + .env.example
```

Dependency direction is one-way: **`channels/` and `presentations/` depend on
`core/`; `core/` never imports them.** The bot and the HTTP API are two
independent entry points that both call the same `core/services/*` directly via
Python import — they never call each other.

---

## What changes vs. what doesn't

| Stays fixed (every client) | Varies per client / template |
|---|---|
| `core/services/*` business logic | which `channels` / `presentations` are enabled (config) |
| `core/agent/*` LLM nodes | prompt text (`templates/<t>/prompts/*.txt`) |
| `StorageAdapter` / `VectorStore` Protocols | storage backend (adapter behind the Protocol) |
| `core/bootstrap/*` loader machinery | question seed (`templates/<t>/question_seed.json`) |
| DB schema (`core/storage/migrations/`) | secrets / env (`clients/<name>/.env`) |

A different backend (Postgres, Iiko, Bitrix) is added by writing one new adapter
that satisfies `StorageAdapter` — **no service code changes**.

---

## The storage boundary (R2)

`core/storage/protocol.py` defines `StorageAdapter` (a `typing.Protocol`); the
parallel `core/storage/vector/protocol.py` defines `VectorStore`. Services and
tools depend on these Protocols, not on Supabase/Pinecone.

- The **only** module allowed to call `get_supabase()` / `.table(...)` is
  `core/storage/adapters/supabase.py`.
- The **only** module that talks to the Pinecone SDK is the integration wrapped
  by `core/storage/vector/pinecone.py`.
- `core/storage/adapters/in_memory.py` is the test double.

Granularity is *data-access*: adapter methods fetch/mutate rows and return plain
`dict`/`list[dict]`. All aggregation (sentiment scoring, topic histograms, metric
summaries) stays in the services — storage holds no business logic.

---

## Data flow

**Feedback capture (write path):**

```
guest → channels/telegram/guest_bot
          → core/agent/nodes (analyze → dialogue → extract → card)
          → core/services (sessions, clients, questions)
          → StorageAdapter (Supabase)  +  VectorStore (Pinecone, client card)
```

**Analytics (read path):**

```
admin → presentations/telegram_admin  (or presentations/http_api)
          → core/services (analytics, statistics)  /  core/agent/analytics_agent
          → StorageAdapter (Supabase)  +  VectorStore (Pinecone semantic search)
          → rendered back to admin (bot message / JSON)
```

---

## Module inventory (current)

These are the concrete "modules" wired today:

- **Channel:** `telegram_guest` (`channels/telegram/guest_bot`)
- **Presentations:** `telegram_admin`, `http_api`
- **Storage adapter:** `supabase` (prod), `in_memory` (tests)
- **Vector adapter:** `pinecone`
- **LLM provider:** OpenAI (chat + Whisper + embeddings) via `core/integrations/*`

Each channel/presentation is referenced by a stable `id` in template config and
resolved by the bootstrap registry (below).

---

## Bootstrap flow (R3)

A client instance runs with a single command:

```bash
python -m core.bootstrap clients/_example
```

The flow (`core/bootstrap/`):

1. **`loader.load_client(client_dir)`** reads `clients/<name>/config.yaml`,
   resolves its `template:` to `templates/<template>/config.yaml`, and
   **deep-merges** the client's `overrides:` on top of the template config.
2. It validates the storage/vector `type` and builds **factories**
   (`build_storage` / `build_vector` return a zero-arg callable, *not* a live
   adapter). `load_client` is **secret-free** — it touches no env and opens no
   connection, so a clean checkout / CI with no `.env` can load configs safely.
3. It returns an **`AppContext`** (`context.py`): the merged config, the two
   factories, and resolved `template_dir` / `client_dir`. `storage` / `vector`
   start as `None`.
4. **`AppContext.run()`** is where secrets are expected: it calls the factories
   to build the live adapters, then resolves every configured channel and
   presentation through **`registry.resolve_runner`** and runs them concurrently
   under one `asyncio.gather`.

The registry (`registry.py`) maps each config `id` to a runner that **reuses the
existing per-component entry point** — `telegram_guest` → the guest bot's
`main()`, `telegram_admin` → the admin bot's `main()`, `http_api` → a
programmatic `uvicorn.Server`. No aiogram/uvicorn wiring is duplicated.

> The legacy per-component entry points still work for dev:
> `python -m channels.telegram.guest_bot`,
> `python -m presentations.telegram_admin`,
> `python -m presentations.http_api`. Bootstrap is the parallel
> "run one client with one command" path, not a replacement.

---

## Adding a new module

- **New channel / presentation** → write its runner in
  `core/bootstrap/registry.py` and register the `id` in `_CHANNELS` /
  `_PRESENTATIONS`. The config `id` is the contract.
- **New storage / vector backend** → write an adapter satisfying the Protocol,
  add a branch in `build_storage` / `build_vector`.
- **New industry template** → copy `templates/tg-restaurant/`. See
  [TEMPLATE_AUTHORING.md](TEMPLATE_AUTHORING.md).
- **New client** → copy `clients/_example/`. See
  [ONBOARDING_CLIENT.md](ONBOARDING_CLIENT.md).

---

## Related docs

- [REFACTOR_M1_PLAN.md](REFACTOR_M1_PLAN.md) — the M1 phase plan + rationale
- [ONBOARDING_CLIENT.md](ONBOARDING_CLIENT.md) — add a new client
- [TEMPLATE_AUTHORING.md](TEMPLATE_AUTHORING.md) — author a new template
- [HTTP_API.md](HTTP_API.md) — the FastAPI contract for the admin Mini App
- [LANGGRAPH.md](LANGGRAPH.md) — LangGraph node patterns
- [ENVIRONMENTS.md](ENVIRONMENTS.md) — environment constraints
- [DEPLOYMENT.md](DEPLOYMENT.md) — deploy (systemd / VPS)
