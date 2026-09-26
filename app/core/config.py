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


@lru_cache
def get_settings() -> Settings:
    return Settings()
