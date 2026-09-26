import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.context import request_id_var

logger = logging.getLogger("app.access")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class ObservabilityMiddleware:
    """Mide cada request HTTP y deja un log JSON con la latencia.

    El reloj es time.perf_counter: monótono, apto para duraciones.
    X-Response-Time-Ms sale cuando arrancan los headers (tiempo hasta
    el primer byte). El log cierra con la duración total del request.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Response-Time-Ms"] = f"{_elapsed_ms(started):.2f}"
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception(
                "http.request",
                extra={"fields": _fields(scope, status_code, started)},
            )
            raise
        else:
            log = logger.error if status_code >= 500 else logger.info
            log("http.request", extra={"fields": _fields(scope, status_code, started)})
        finally:
            request_id_var.reset(token)


def _request_id(scope: Scope) -> str:
    raw = _header(scope, b"x-request-id")
    if raw and _REQUEST_ID.fullmatch(raw):
        return raw
    return str(uuid.uuid4())


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("latin-1")
    return None


def _fields(scope: Scope, status_code: int, started: float) -> dict[str, object]:
    return {
        "method": scope.get("method"),
        "path": scope.get("path"),
        "status": status_code,
        "latency_ms": round(_elapsed_ms(started), 2),
    }


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000
