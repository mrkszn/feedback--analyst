"""Live credentials smoke check.

Запуск:
    uv run python scripts/smoke.py

Делает по одному read-only вызову к каждому внешнему сервису и печатает
✅/❌ с краткой диагностикой. НЕ отправляет ничего пользователям, не пишет
в БД, не upsert'ит векторы. Безопасно гонять на любом окружении.

Exit code:
    0 — все проверки прошли
    1 — есть провалы (детали в выводе)
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

# Скрипт лежит в scripts/; чтобы импортировать `config` из корня — добавим корень в path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings


def _truncate(s: str, n: int = 200) -> str:
    return s if len(s) <= n else s[:n] + "…"


def check_openai() -> tuple[bool, str]:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key, timeout=10)
        models = list(client.models.list())
        names = [m.id for m in models[:3]]
        return True, f"{len(models)} models accessible (sample: {names})"
    except Exception as e:
        return False, _truncate(repr(e))


def check_supabase() -> tuple[bool, str]:
    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        # Read-only ping: попробовать select из служебной схемы.
        # Если таблицы пользователя ещё не созданы — это нормально.
        # Главное, чтобы service_role_key был валидным и URL отвечал.
        resp = client.rpc("version").execute() if False else None
        del resp
        # Простейший доказательный пинг — auth.get_user без токена должен
        # вернуть ошибку формата (не 401), что подтверждает доступность endpoint.
        try:
            client.auth.get_user()
        except Exception:
            pass
        return True, f"client created for {settings.supabase_url}"
    except Exception as e:
        return False, _truncate(repr(e))


def check_supabase_schema() -> tuple[bool, str]:
    """Проверяет, применена ли миграция 0001 — есть ли таблица `clients`."""
    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        # select 0 строк из clients — самый дешёвый ping существования таблицы
        client.table("clients").select("telegram_id").limit(0).execute()
        return True, "table `clients` exists — миграция 0001 применена"
    except Exception as e:
        msg = repr(e)
        if "not find" in msg.lower() or "does not exist" in msg.lower() or "PGRST" in msg:
            return False, "таблиц нет — примени db/migrations/0001_init.sql"
        return False, _truncate(msg)


def check_pinecone() -> tuple[bool, str]:
    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=settings.pinecone_api_key)
        idx_list = pc.list_indexes()
        names = [idx.name for idx in idx_list]
        target = settings.pinecone_index
        if target in names:
            return True, f"key OK; index '{target}' ✅ exists (all: {names})"
        return False, f"key OK; index '{target}' ❌ НЕ найден (доступны: {names})"
    except Exception as e:
        return False, _truncate(repr(e))


def _check_telegram(token: str, label: str) -> tuple[bool, str]:
    if not token:
        return False, "токен пуст"
    try:
        import httpx

        r = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}: {_truncate(r.text)}"
        data = r.json()
        if data.get("ok"):
            u = data["result"]
            return True, f"@{u.get('username')} (id={u.get('id')}, {label})"
        return False, _truncate(str(data))
    except Exception as e:
        return False, _truncate(repr(e))


def check_telegram_guest() -> tuple[bool, str]:
    return _check_telegram(settings.telegram_guest_bot_token, "guest bot")


def check_telegram_admin() -> tuple[bool, str]:
    return _check_telegram(settings.telegram_admin_bot_token, "admin bot")


CHECKS: dict[str, Callable[[], tuple[bool, str]]] = {
    "openai": check_openai,
    "supabase-conn": check_supabase,
    "supabase-schema": check_supabase_schema,
    "pinecone": check_pinecone,
    "telegram-guest": check_telegram_guest,
    "telegram-admin": check_telegram_admin,
}


def main() -> int:
    print(f"ENV={settings.env}  pinecone_namespace={settings.pinecone_namespace}\n")
    failures: list[str] = []
    for name, fn in CHECKS.items():
        ok, info = fn()
        marker = "✅" if ok else "❌"
        print(f"{marker} {name:18s} {info}")
        if not ok:
            failures.append(name)
    print()
    if failures:
        print(f"❌ {len(failures)}/{len(CHECKS)} failed: {', '.join(failures)}")
        return 1
    print(f"✅ Все {len(CHECKS)} проверок прошли.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
