import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis

from app.domain.events import DescriptionGenerated

logger = logging.getLogger(__name__)

EventHandler = Callable[[DescriptionGenerated], Awaitable[None]]


class EventBus:
    """Publica en este proceso y sigue de largo.

    create_task corre los suscriptores en el event loop sin hacer
    esperar al request que ya tiene su respuesta.
    """

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []
        self._tasks: set[asyncio.Task[None]] = set()

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def publish(self, event: DescriptionGenerated) -> None:
        task = asyncio.create_task(self._dispatch(event))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        if not self._tasks:
            return
        await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _dispatch(self, event: DescriptionGenerated) -> None:
        for handler in self._handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception(
                    "event.handler_failed",
                    extra={"fields": {"event": "catalog.description_generated"}},
                )


class DescriptionEventLog:
    """Bitácora corta en Redis. Conserva las últimas 100 fichas generadas."""

    key = "events:descriptions"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def append(self, event: DescriptionGenerated) -> None:
        payload = {
            "event": "catalog.description_generated",
            "name": event.name,
            "category": event.category,
            "provider": event.provider,
            "model": event.model,
            "request_id": event.request_id,
            "occurred_at": event.occurred_at,
        }
        await self._redis.lpush(self.key, json.dumps(payload, ensure_ascii=False))
        await self._redis.ltrim(self.key, 0, 99)
        logger.info("event.appended", extra={"fields": payload})

    async def recent(self, limit: int) -> list[dict[str, object]]:
        rows = await self._redis.lrange(self.key, 0, limit - 1)
        return [json.loads(row) for row in rows]
