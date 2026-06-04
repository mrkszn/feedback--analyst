# Onboarding a new client

A *client* is one deployed instance: one set of bots, one Supabase project, one
Pinecone namespace. A client picks a **template** (its industry defaults) and
supplies its own secrets. Onboarding is copy → configure → run.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how clients fit the layered design,
and [TEMPLATE_AUTHORING.md](TEMPLATE_AUTHORING.md) for authoring the template a
client points at.

---

## 1. Copy the example client

`clients/_example/` is the committed reference. Copy it:

```bash
cp -r clients/_example clients/acme
```

> `clients/_example/` is tracked in the repo as the canonical example. **Real
> client directories (`clients/<name>/`) are private** — keep them gitignored or
> in a separate private repo. They hold deployment-specific config and reference
> secrets; never commit a populated `.env`.

---

## 2. Pick a template

Edit `clients/acme/config.yaml`. The minimal client config is just a template
reference plus a name:

```yaml
template: tg-restaurant
name: "Acme Diner"
```

`template:` must match a directory under `templates/` (today: `tg-restaurant`,
`tg-clinic`). The template supplies channels, presentations, storage selection,
prompts, and the question seed — see [TEMPLATE_AUTHORING.md](TEMPLATE_AUTHORING.md).

---

## 3. Fill in the environment

Copy the client's env template and fill real values:

```bash
cp clients/acme/.env.example clients/acme/.env   # then edit clients/acme/.env
```

The config files hold **no secrets** — only env-variable *names*. The actual
values live in `.env`. Required variables (from `clients/_example/.env.example`):

| Variable | Purpose |
|---|---|
| `TELEGRAM_GUEST_BOT_TOKEN` | guest bot token (@BotFather) |
| `TELEGRAM_ADMIN_BOT_TOKEN` | admin bot token (@BotFather) |
| `ADMIN_BOOTSTRAP_TOKEN` | one-time token to claim the first admin (`openssl rand -hex 16`) |
| `OPENAI_API_KEY` | chat + Whisper + embeddings |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | primary storage |
| `PINECONE_API_KEY`, `PINECONE_INDEX`, `PINECONE_NAMESPACE` | vector store |
| `MINI_APP_SESSION_SECRET` | admin Mini App JWT secret (`openssl rand -hex 32`) |
| `ALLOWED_MINI_APP_ORIGINS` | CORS allowlist (comma-separated, never `*`) |

`OPENAI_CHAT_MODEL`, `OPENAI_WHISPER_MODEL`, `OPENAI_EMBED_MODEL`,
`RESTAURANT_CONTEXT`, `VOICE_TMP_DIR`, `ENV`, `LOG_LEVEL` are optional / have
defaults. See `clients/_example/.env.example` for the full annotated list and
[ENVIRONMENTS.md](ENVIRONMENTS.md) for environment constraints.

---

## 4. (Optional) Override template defaults

Anything in the template config can be overridden per client via an `overrides:`
block. The example ships it commented out:

```yaml
template: tg-restaurant
name: "Acme Diner"

overrides:
  branding:
    bot_name: "Acme Bot"
  prompts:
    dialogue: overrides/prompts/dialogue.txt
```

`overrides:` is deep-merged on top of the template config (client wins; nested
dicts merge, scalars/lists replace). Custom prompt/asset files live under
`clients/acme/overrides/`. If you have no overrides, omit the block entirely — an
empty client proves the template loads as-is.

---

## 5. Run

```bash
python -m core.bootstrap clients/acme
```

This loads the merged config, builds the storage + vector adapters, and starts
every channel and presentation the template enables (guest bot, admin bot, HTTP
API) concurrently.

Before first run, apply the DB schema (`core/storage/migrations/0001_init.sql`)
to the client's Supabase project, then claim the first admin by messaging the
admin bot `/claim <ADMIN_BOOTSTRAP_TOKEN>`.

> For dev you can also run a single component directly:
> `python -m channels.telegram.guest_bot`,
> `python -m presentations.telegram_admin`,
> `python -m presentations.http_api`.

---

## 6. Deploy

See [DEPLOYMENT.md](DEPLOYMENT.md) for the systemd / VPS setup. The deploy reads
the same `clients/<name>/` directory and runs `python -m core.bootstrap
clients/<name>`.
