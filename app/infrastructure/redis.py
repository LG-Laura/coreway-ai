from redis.asyncio import Redis


class RedisClient:
    """Cliente async de Redis.

    Guarda la cuota por cliente, el estado del circuit breaker y la
    bitácora corta de fichas generadas.
    """

    def __init__(self, url: str) -> None:
        self.client: Redis = Redis.from_url(url, decode_responses=True)

    async def ping(self) -> None:
        await self.client.ping()

    async def close(self) -> None:
        await self.client.aclose()
