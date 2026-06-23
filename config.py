"""Единая точка чтения env-переменных. Импортируй `settings` из этого модуля."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: Literal["local", "staging", "prod"] = "local"
    log_level: str = "INFO"

    telegram_guest_bot_token: str = ""
    telegram_admin_bot_token: str = ""
    # Разовый токен для регистрации первого админа через /claim.
    # Source of truth по админам — таблица admin_users в Supabase.
    admin_bootstrap_token: str = ""
    # Whitelist для веб-логина админки через Telegram Login Widget
    # (POST /admin/auth/web): CSV из telegram-id. Пусто = никто не залогинится
    # этим путём. Mini App (/admin/auth) этот список не использует.
    admin_telegram_ids: str = ""

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-5.5"
    openai_whisper_model: str = "whisper-1"
    openai_embed_model: str = "text-embedding-3-small"
    openai_usage_tag: str = "local-dev"

    supabase_url: str = ""
    supabase_service_role_key: str = ""

    pinecone_api_key: str = ""
    pinecone_index: str = "client-cards"
    pinecone_namespace: str = "dev"

    voice_tmp_dir: str = "./tmp/voice"

    restaurant_context: str = ""

    # HTTP API (Phase 4A) — JWT secret для admin Mini App сессий; пустая строка
    # = API в режиме fail-loud (issue/verify_token поднимут RuntimeError).
    mini_app_session_secret: str = ""
    # CORS allowlist для admin Mini App (comma-separated origins). Пусто = CORS
    # отключён. Никогда не используем "*", это явный allowlist.
    allowed_mini_app_origins: str = ""
    # Публичный HTTPS URL admin Mini App'а (для /miniapp команды в боте).
    # Local dev — cloudflared/ngrok tunnel URL, prod — стабильный домен.
    admin_mini_app_url: str = ""

    # Public guest webapp (Phase 5) — JWT secret для гостевых сессий
    # ("вечер як стрічка" UX). Отдельный домен доверия от админского
    # mini_app_session_secret. Пусто = guest API в fail-loud (RuntimeError).
    guest_session_secret: str = ""
    # CORS allowlist для публичного guest webapp (comma-separated origins).
    # Пусто = guest endpoints не получают CORS-заголовков. Без "*".
    allowed_guest_origins: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
