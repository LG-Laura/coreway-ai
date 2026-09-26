from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

router = APIRouter(tags=["ops"])


class HealthStatus(BaseModel):
    status: str
    postgres: str
    redis: str


@router.get("/health", response_model=HealthStatus)
async def health(request: Request, response: Response) -> HealthStatus:
    """Liveness del proceso y de sus dos dependencias.

    Vive fuera de /api/v1: es un contrato operativo, no de producto.
    Un balanceador o Compose pueden pegarle sin conocer la versión de la API.
    """

    postgres = await _probe(request.app.state.db.ping)
    redis_status = await _probe(request.app.state.redis.ping)
    status = "ok" if postgres == "up" and redis_status == "up" else "degraded"
    if status != "ok":
        response.status_code = 503
    return HealthStatus(status=status, postgres=postgres, redis=redis_status)


async def _probe(ping) -> str:
    try:
        await ping()
    except Exception:
        return "down"
    return "up"
