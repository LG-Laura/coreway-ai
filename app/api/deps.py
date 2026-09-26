from collections.abc import AsyncIterator

from fastapi import Request

from app.core.config import get_settings
from app.core.context import simulate_provider_failure
from app.services.describe_product import DescribeProduct
from app.services.list_events import ListDescriptionEvents


def get_describe_product(request: Request) -> DescribeProduct:
    return DescribeProduct(request.app.state.ai_provider, request.app.state.events)


def get_list_events(request: Request) -> ListDescriptionEvents:
    return ListDescriptionEvents(request.app.state.description_events)


async def arm_provider_failure_switch(request: Request) -> AsyncIterator[None]:
    """En local, X-Debug-Provider-Failure: true hace fallar al adaptador.

    Sirve para ver reintentos y el circuit breaker sin un proveedor real.
    """

    settings = get_settings()
    enabled = (
        settings.app_env == "local"
        and request.headers.get("x-debug-provider-failure", "").lower() == "true"
    )
    token = simulate_provider_failure.set(enabled)
    try:
        yield
    finally:
        simulate_provider_failure.reset(token)
