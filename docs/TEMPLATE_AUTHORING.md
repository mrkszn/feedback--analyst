# Authoring a template

A *template* is an industry bundle: the default config, prompts, and seed
questions that several clients of the same kind share. Clients reference a
template by name and override only what differs (see
[ONBOARDING_CLIENT.md](ONBOARDING_CLIENT.md)).

Templates live under `templates/<industry>/`. Today: `tg-restaurant` (the
original setup) and `tg-clinic` (a clinic/salon stub that proves a second
template extracts cleanly).

---

## When to author a new template

- **Copy `tg-restaurant`** when the new industry uses the same channels and
  presentations (Telegram guest bot + admin bot + HTTP API) and only the
  *prompts*, *tone*, and *questions* differ. This is the common case.
- **Author fresh** only if the wiring itself changes — e.g. a different channel
  or storage backend. That also means adding a runner/adapter in
  `core/` (see [ARCHITECTURE.md](ARCHITECTURE.md) → "Adding a new module").

---

## What a template contains

Mirror `templates/tg-restaurant/`:

```
templates/<industry>/
├── config.yaml          ← defaults: channels, presentations, storage, prompts, seed
├── prompts/
│   ├── dialogue.txt      ← guest-dialogue system prompt
│   ├── analyze.txt       ← feedback-analysis system prompt
│   └── card.txt          ← client-card synthesis prompt
├── question_seed.json   ← default interview questions
└── README.md            ← what this template is, what it overrides
```

---

## `config.yaml` schema

The config holds **no secrets** — only env-variable *names*. Fields (from
`templates/tg-restaurant/config.yaml`):

```yaml
name: "Telegram Restaurant Feedback"   # human label
version: "1.0"

channels:                               # capture layer — what's enabled
  - id: telegram_guest                  # must match a registry id (core/bootstrap/registry.py)
    token_env: TELEGRAM_GUEST_BOT_TOKEN

presentations:                          # admin-facing layer
  - id: telegram_admin
    token_env: TELEGRAM_ADMIN_BOT_TOKEN
  - id: http_api
    port_env: API_PORT
    cors_origins_env: ALLOWED_MINI_APP_ORIGINS

storage:
  primary:                              # type selects the StorageAdapter
    type: supabase
    url_env: SUPABASE_URL
    key_env: SUPABASE_SERVICE_ROLE_KEY
  vector:                               # type selects the VectorStore
    type: pinecone
    api_key_env: PINECONE_API_KEY
    index_env: PINECONE_INDEX
    namespace_env: PINECONE_NAMESPACE

prompts:                                # paths relative to the template dir
  dialogue: prompts/dialogue.txt
  analyze: prompts/analyze.txt
  card: prompts/card.txt

question_seed: question_seed.json
```

The `id` values under `channels` / `presentations` are the contract with the
bootstrap registry (`_CHANNELS` / `_PRESENTATIONS` in
`core/bootstrap/registry.py`). The `type` under `storage.primary` / `vector`
selects an adapter in `core/bootstrap/loader.py` (`build_storage` /
`build_vector`) — an unknown type fails loud at load.

---

## What to customize

| Part | Why you'd change it |
|---|---|
| `prompts/*.txt` | industry tone — a clinic is calmer/medical, a restaurant is warm/casual |
| `question_seed.json` | the metrics that matter for the industry |
| `name` / branding | the label clients see |

Leave channels/presentations/storage as-is unless the wiring genuinely differs.

### `question_seed.json` shape

A JSON array of question objects matching the `questions` table
(`core/storage/migrations/0001_init.sql`) and `StorageAdapter.create_question`:

```json
[
  {
    "text": "Как вы оцениваете скорость обслуживания?",
    "metric_key": "service_speed",
    "expected_type": "enum",
    "enum_values": ["быстро", "нормально", "медленно"]
  }
]
```

- `expected_type` ∈ `text | number | enum | boolean`.
- `enum_values` is a non-empty list **only** when `expected_type` is `enum`,
  otherwise `null`.
- `metric_key` must be unique within the seed (it's the analytics aggregation key).
- 5–7 questions is a good default.

### `prompts/*.txt`

Plain text. Keep any `{placeholder}` tokens verbatim — they're filled by the
prompt builders in `core/agent/prompts.py` (e.g. `dialogue.txt` uses
`{restaurant_context}`). In M1 these files are the template's documented
source-of-truth and future override hook; the live prompt builders still read
the constants in `core/agent/prompts.py` (wiring them to read template files is a
later phase).

---

## Worked example: `tg-clinic`

`templates/tg-clinic/` is a second template authored by copying `tg-restaurant`
and swapping the prompt tone (calmer, clinic/salon-appropriate) and the question
seed (relevant clinic metrics). It's the proof that extracting a new industry
template needs no `core/` changes. Use it as a reference when authoring your own.

---

## Verify

Point a throwaway client at the template and load it secret-free:

```bash
mkdir -p clients/_smoke && printf 'template: <industry>\nname: smoke\n' > clients/_smoke/config.yaml
python -m core.bootstrap clients/_smoke   # should start (or fail only on missing env at run, not load)
```

`load_client` is secret-free, so config errors (bad template name, unknown
storage type, missing prompt file) surface immediately without needing real
credentials.
