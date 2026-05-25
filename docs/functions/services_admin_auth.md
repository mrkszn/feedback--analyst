# services.admin_auth — is_admin + claim_admin

## Назначение

Авторизация для admin-бота. Source of truth — таблица `admin_users` в Supabase.

- `is_admin(telegram_id)` — спрашивается на каждом входе в admin-команду.
- `claim_admin(telegram_id, token, name)` — разовая регистрация первого админа через `/claim <token>`. Если `admin_users` пустая И `token == settings.admin_bootstrap_token` — добавляем строку. Иначе отказ.

Эта функция также инициализирует **общий Supabase-клиент** в `db/client.py` (singleton через `lru_cache`), которым будут пользоваться все остальные сервисы (упомянуть в этом же коммите).

## Сигнатура

```python
from supabase import Client

async def is_admin(telegram_id: int, *, db: Client | None = None) -> bool: ...

async def claim_admin(
    telegram_id: int,
    token: str,
    *,
    name: str | None = None,
    db: Client | None = None,
) -> bool: ...
```

- `db` опционально — если `None`, берётся `db.client.get_supabase()`.
- `claim_admin` возвращает `True` если регистрация прошла, `False` если отказ (таблица не пуста или токен невалиден).

Также в `db/client.py`:
```python
from supabase import create_client, Client

@lru_cache(maxsize=1)
def get_supabase() -> Client: ...
```

## Зависимости

- `supabase-py` (`create_client`).
- `config.settings.supabase_url`, `supabase_service_role_key`, `admin_bootstrap_token`.

## Шаги реализации

1. `db/client.py`: `get_supabase()` создаёт `create_client(settings.supabase_url, settings.supabase_service_role_key)`. Кешируем через `functools.lru_cache(maxsize=1)`.
2. `services/admin_auth.py`:
   - `is_admin`: `db.table("admin_users").select("telegram_id").eq("telegram_id", telegram_id).limit(1).execute()` — вернуть `bool(resp.data)`.
   - `claim_admin`:
     - Сравнить токен с `settings.admin_bootstrap_token` (constant-time через `hmac.compare_digest`); если не совпадает → `False`.
     - Если `settings.admin_bootstrap_token` пуст — тоже `False` (защита от пустых дефолтов).
     - `count_resp = db.table("admin_users").select("telegram_id", count="exact").limit(1).execute()`; если `count_resp.count > 0` → `False` (токен «сгорел»).
     - Иначе `db.table("admin_users").insert({"telegram_id": telegram_id, "name": name}).execute()` → `True`.

`supabase-py` v2 в основном sync; оборачиваем blocking-вызовы в `await asyncio.to_thread(...)`.

## Edge cases

- **Пустой bootstrap-токен в env** → `claim_admin` всегда `False`.
- **`admin_users` стала непустой между check и insert (race)** → опционально полагаемся на UNIQUE PK; ловим `APIError` с code 23505 и возвращаем `False`.
- **Сетевой сбой Supabase** → пробрасываем (нет ретраев на этом уровне — caller решает).

## Тесты

`tests/test_services_admin_auth.py`:

- **Unit (mock db client):**
  - `test_is_admin_true_when_row_exists`
  - `test_is_admin_false_when_no_row`
  - `test_claim_admin_success_on_empty_table`
  - `test_claim_admin_rejects_wrong_token`
  - `test_claim_admin_rejects_when_table_not_empty`
  - `test_claim_admin_rejects_empty_bootstrap_token` (`settings.admin_bootstrap_token == ""`)
  - `test_claim_admin_constant_time_compare` — проверить что используется `hmac.compare_digest`.

Мокать `db.client.get_supabase` либо передавать MagicMock как `db=` параметр.

## /goal

> `is_admin`, `claim_admin` в `services/admin_auth.py`; `get_supabase` в `db/client.py`; unit-тесты зелёные; ruff/mypy чисто; коммит `feat(services): implement admin_auth + db client`.

## Команда

- T1; team_name `fn-svc-admin-auth`; team-lead/implementer/tester/reviewer.

## Permissions

Наследуются. Supabase сетевые вызовы — только в тестах с моками.

## Next

→ [services_client_upsert.md](services_client_upsert.md)
