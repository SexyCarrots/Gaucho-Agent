"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gaucho_db_path: str = "./gaucho_agent.db"
    canvas_ics_url: str = ""
    ucsb_api_base: str = "https://api.ucsb.edu"
    ucsb_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    local_timezone: str = "America/Los_Angeles"
    sync_user_agent: str = "gaucho-agent/0.1"


# Module-level singleton – import this everywhere
settings = Settings()
