from fastapi import APIRouter

from app.api.v1.products import router as products_router
from app.core.config import get_settings

router = APIRouter()
router.include_router(products_router)


@router.get("/info")
async def info() -> dict[str, str]:
    settings = get_settings()
    return {
        "service": settings.app_name,
        "environment": settings.app_env,
    }
