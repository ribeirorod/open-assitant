"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "OA_", "env_file": ".env", "extra": "ignore"}

    # --- Claude Agent SDK ---
    claude_model: str = "claude-sonnet-4-6"

    # --- Perplexity MCP ---
    perplexity_api_key: str = Field(default="", validation_alias="PERPLEXITY_API_KEY")

    # --- Voice (STT + TTS) — read without OA_ prefix ---
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    deepgram_api_key: str = Field(default="", validation_alias="DEEPGRAM_API_KEY")

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_allowed_users: list[str] = []  # usernames; empty = allow all

    # --- WhatsApp (Meta Cloud API) ---
    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""

    # --- Webhook server (for WhatsApp inbound) ---
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080

    # --- Google Workspace CLI ---
    gws_binary: str = "gws"  # path to the gws binary


settings = Settings()
