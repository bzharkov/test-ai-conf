from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str = ""
    llm_model: str = ""
    llm_timeout_s: float = 30
    llm_enabled: bool = True

    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = 384

    database_url: str = "postgresql+asyncpg://app:app@db:5432/pcconf"
    redis_url: str = "redis://redis:6379/0"
    opendb_path: str = ""
    price_provider: str = "csv"
    catalog_source: str = "seed"

    default_budget_rub: int = 100000
    seed_dir: str = "data/seed"
    perf_scores_path: str = "data/perf_scores.csv"

    # power model (TZ section 7)
    power_k_cpu: float = 1.35
    power_margin: float = 1.3

    # recommender
    beam_width: int = 40
    beam_time_limit_s: float = 4.0
    rate_limit_per_min: int = 20
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_available(self) -> bool:
        return self.llm_enabled and bool(self.openrouter_api_key and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
