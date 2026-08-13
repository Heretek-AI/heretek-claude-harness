"""Environment-driven settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TIER1_", env_file=".env", extra="ignore")

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    dashboard_path: str = ""

    # LLM
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.io/v1"
    minimax_model: str = "MiniMax-Text-01"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    ollama_base_url: str = ""
    local_model: str = "llama3.1:8b"
    llm_timeout_s: float = 60.0

    # Memory
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    memory_ttl_s: int = 3600

    # Cognee
    cognee_graph_path: str = ".cognee_data"
    cognee_llm_provider: str = "openai"

    # Consensus
    max_rounds: int = 3
    charlie_veto_confidence: float = 0.7
    unanimous_confidence_floor: float = 0.7

    # NATS
    nats_url: str = "nats://localhost:4222"

    # Postgres
    postgres_dsn: str = "postgresql://tier1:tier1@localhost:5432/tier1"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_ttl_s: int = 3600

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "tier1_deliberations"

    # cognee
    cognee_url: str = "http://localhost:8001"

    # mem0
    mem0_url: str = "http://localhost:8002"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
