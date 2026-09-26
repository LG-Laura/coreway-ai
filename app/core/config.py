from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración por entorno.

    Los nombres de campo se leen de variables de entorno en mayúsculas
    (database_url <- DATABASE_URL). La misma imagen sirve en local y en
    cualquier otro entorno: cambia el entorno, no el código.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Coreway AI Gateway"
    app_env: str = "local"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://coreway:coreway@localhost:5432/coreway"
    redis_url: str = "redis://localhost:6379/0"
    ai_provider: str = "local"

    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60
    circuit_failure_threshold: int = 3
    circuit_recovery_seconds: int = 15
    ai_retry_attempts: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
