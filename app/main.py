from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.adapters.ai import build_ai_provider
from app.adapters.ai.resilient import ResilientAIProvider
from app.api.health import router as health_router
from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.errors import AIUnavailable
from app.infrastructure.database import Database
from app.infrastructure.events import DescriptionEventLog, EventBus
from app.infrastructure.redis import RedisClient
from app.middleware.observability import ObservabilityMiddleware
from app.middleware.rate_limit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Composition root.

    Aquí se construyen los adaptadores y se cuelgan de app.state.
    Los routers los reciben por request; no instancian clientes.
    Si Postgres o Redis no responden, el proceso no llega a servir tráfico.
    """

    settings = get_settings()
    database = Database(settings.database_url)
    redis = RedisClient(settings.redis_url)
    await database.ping()
    await redis.ping()
    events = EventBus()
    description_events = DescriptionEventLog(redis.client)
    events.subscribe(description_events.append)
    app.state.db = database
    app.state.redis = redis
    app.state.events = events
    app.state.description_events = description_events
    app.state.ai_provider = ResilientAIProvider(
        inner=build_ai_provider(settings.ai_provider),
        redis=redis.client,
        provider_name=settings.ai_provider,
        failure_threshold=settings.circuit_failure_threshold,
        recovery_seconds=settings.circuit_recovery_seconds,
        retry_attempts=settings.ai_retry_attempts,
    )
    yield
    await events.drain()
    await redis.close()
    await database.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_exception_handler(AIUnavailable, _ai_unavailable)
    # En FastAPI el último middleware agregado queda por fuera.
    # Observabilidad envuelve la cuota para medir también los 429.
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(ObservabilityMiddleware)
    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.api_prefix)
    return app


async def _ai_unavailable(_: Request, exc: AIUnavailable) -> JSONResponse:
    headers: dict[str, str] = {}
    if exc.retry_after_seconds is not None:
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return JSONResponse(status_code=503, content={"detail": exc.detail}, headers=headers)


app = create_app()
