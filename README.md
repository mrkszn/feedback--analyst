# telegram-waiter

A Telegram feedback collector + adaptive interview bot, with an admin
counterpart. A guest leaves free-text or voice feedback; the bot runs a short,
LLM-driven interview, extracts structured metrics, and builds a per-visit client
card. Admins manage interview questions and read analytics via a second bot and
an HTTP API (admin Mini App backend).

- **Stack:** Python 3.12, [uv](https://docs.astral.sh/uv/), aiogram, FastAPI,
  LangChain/LangGraph, OpenAI (chat + Whisper + embeddings).
- **Stores:** Supabase (Postgres) + Pinecone (vectors).

## Modular architecture (M1)

The project is organized as a **layered + template-based monorepo** so a new
client is hours to onboard, core fixes reach every client, and the directory
structure declares what's customizable:

- **`core/`** — the kernel, identical for every client: agent (LLM nodes),
  services (async business logic), integrations, storage (behind a
  `StorageAdapter` Protocol), tools, and the bootstrap loader.
- **`channels/`** — capture layer (how feedback comes in): the Telegram guest bot.
- **`presentations/`** — admin-facing layer (how data goes out): the Telegram
  admin bot and the HTTP API.
- **`templates/`** — industry bundles (config + prompts + question seed):
  `tg-restaurant`, `tg-clinic`.
- **`clients/`** — per-instance config; a client picks a template and supplies
  its own secrets. Real client dirs are private; `clients/_example/` is the
  committed reference.

Full overview: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Quick start

```bash
uv sync --frozen
cp .env.example .env          # fill in tokens / keys
```

Run a client instance (all configured channels + presentations):

```bash
python -m core.bootstrap clients/_example
```

Or run a single component directly (dev):

```bash
python -m channels.telegram.guest_bot
python -m presentations.telegram_admin
python -m presentations.http_api
```

Apply the DB schema from `core/storage/migrations/0001_init.sql` to your
Supabase project before first run.

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — layered + template architecture
- [docs/ONBOARDING_CLIENT.md](docs/ONBOARDING_CLIENT.md) — add a new client
- [docs/TEMPLATE_AUTHORING.md](docs/TEMPLATE_AUTHORING.md) — author a new template
- [docs/HTTP_API.md](docs/HTTP_API.md) — admin Mini App API contract
- [docs/LANGGRAPH.md](docs/LANGGRAPH.md) — LangGraph node patterns
- [docs/ENVIRONMENTS.md](docs/ENVIRONMENTS.md) — environment constraints
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — deploy (systemd / VPS)
- [docs/GIT.md](docs/GIT.md) — commit conventions

## Development

```bash
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run mypy .
```
