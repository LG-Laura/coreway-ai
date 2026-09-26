from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/info")
async def info() -> dict[str, str]:
    settings = get_settings()
    return {
        "service": settings.app_name,
        "environment": settings.app_env,
    }
