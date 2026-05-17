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

    # --- Selective memory layer (EXPERIMENT_PLAN.md) ---
    use_memory: bool = False                 # USE_MEMORY=1 turns the layer on
    memory_backend: str = "ours"             # ours | mem0 | naive_rag | recent_window
    memory_user_id: str = "default"          # single-user CLI; eval drivers override
    embedding_model: str = "all-MiniLM-L6-v2"
    memory_judge_model: str = "gpt-4o-mini"  # cheap judge during store
    memory_use_judge: bool = True             # False -> Day-1 heuristic only
    # Retrieval scoring weights (tunable in EXP-2)
    mem_alpha: float = 0.7                    # semantic similarity weight
    mem_beta: float = 0.2                     # query/type match weight
    mem_gamma: float = 0.1                    # recency decay weight
    mem_tau_days: float = 14.0                # recency half-life (days)
    mem_top_k: int = 8                        # default retrieval budget


# Module-level singleton – import this everywhere
settings = Settings()
