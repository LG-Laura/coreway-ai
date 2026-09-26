import json
import logging
import re
import time

from redis.exceptions import RedisError
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.infrastructure.redis import RedisClient

logger = logging.getLogger("app.ratelimit")

_CLIENT_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SKIP_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class RateLimitMiddleware:
    """Cuota fija por cliente en una ventana de Redis.

    X-Client-Id identifica a quien llama. Si no viene, se usa la IP.
    /health y la documentación no consumen cuota: si lo hicieran, un
    balanceador o /docs podrían dejar afuera al tráfico real.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or _skipped(scope):
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        client_id = _client_id(scope)
        try:
            decision = await _hit(
                scope["app"].state.redis,
                client_id,
                settings.rate_limit_requests,
                settings.rate_limit_window_seconds,
            )
        except RedisError:
            logger.exception("rate_limit.unavailable", extra={"fields": {"client_id": client_id}})
            await _send_json(
                send,
                503,
                {"detail": "No se pudo verificar la cuota."},
            )
            return

        if not decision.allowed:
            logger.warning(
                "rate_limit.blocked",
                extra={
                    "fields": {
                        "client_id": client_id,
                        "limit": decision.limit,
                        "window_seconds": settings.rate_limit_window_seconds,
                    }
                },
            )
            await _send_json(
                send,
                429,
                {
                    "detail": "Cuota excedida para este cliente.",
                    "limit": decision.limit,
                    "window_seconds": settings.rate_limit_window_seconds,
                },
                extra_headers={
                    "Retry-After": str(decision.retry_after),
                    "X-RateLimit-Limit": str(decision.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-RateLimit-Limit"] = str(decision.limit)
                headers["X-RateLimit-Remaining"] = str(decision.remaining)
            await send(message)

        await self.app(scope, receive, send_wrapper)


class _Decision:
    def __init__(self, allowed: bool, limit: int, remaining: int, retry_after: int) -> None:
        self.allowed = allowed
        self.limit = limit
        self.remaining = remaining
        self.retry_after = retry_after


async def _hit(redis: RedisClient, client_id: str, limit: int, window_seconds: int) -> _Decision:
    window_id = int(time.time()) // window_seconds
    key = f"ratelimit:{client_id}:{window_id}"
    count = await redis.client.incr(key)
    if count == 1:
        await redis.client.expire(key, window_seconds)
    remaining_window = window_seconds - (int(time.time()) % window_seconds)
    return _Decision(
        allowed=count <= limit,
        limit=limit,
        remaining=max(limit - count, 0),
        retry_after=remaining_window,
    )


def _skipped(scope: Scope) -> bool:
    path = scope.get("path", "")
    return path in _SKIP_PATHS or path.startswith("/docs")


def _client_id(scope: Scope) -> str:
    raw = _header(scope, b"x-client-id")
    if raw and _CLIENT_ID.fullmatch(raw):
        return raw
    client = scope.get("client")
    if client:
        return str(client[0])
    return "unknown"


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1")
    return None


async def _send_json(
    send: Send,
    status: int,
    payload: dict[str, object],
    extra_headers: dict[str, str] | None = None,
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    for key, value in (extra_headers or {}).items():
        headers.append((key.lower().encode(), value.encode()))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})
