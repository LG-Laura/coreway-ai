from redis.asyncio import Redis


class RedisClient:
    """Cliente async de Redis.

    En fases posteriores guarda ventanas de rate limit y estado efímero
    del circuit breaker. Hoy solo demuestra que el canal está abierto.
    """

    def __init__(self, url: str) -> None:
        self.client: Redis = Redis.from_url(url, decode_responses=True)

    async def ping(self) -> None:
        await self.client.ping()

    async def close(self) -> None:
        await self.client.aclose()
