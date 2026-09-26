from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings
from app.infrastructure.database import Database
from app.infrastructure.redis import RedisClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Composition root.

    Aquí se construyen los adaptadores de infraestructura y se cuelgan de
    app.state. Los routers los reciben por request; no instancian clientes.
    Si Postgres o Redis no responden, el proceso no llega a servir tráfico.
    """

    settings = get_settings()
    database = Database(settings.database_url)
    redis = RedisClient(settings.redis_url)
    await database.ping()
    await redis.ping()
    app.state.db = database
    app.state.redis = redis
    yield
    await redis.close()
    await database.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.api_prefix)
    return app


app = create_app()
