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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
