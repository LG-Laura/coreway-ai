import logging
import time

from redis.asyncio import Redis
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.adapters.ai.errors import ProviderUnavailable
from app.domain.catalog import Completion, CompletionRequest
from app.domain.errors import AIUnavailable
from app.domain.ports import AIProvider

logger = logging.getLogger(__name__)


class ResilientAIProvider:
    """Reintentos cortos y circuit breaker delante del adaptador real.

    Los reintentos absorben un fallo aislado. Si el proveedor sigue
    caído, el breaker se abre y las llamadas siguientes ni lo tocan.
    El estado vive en Redis para que todos los workers vean la misma pausa.
    """

    def __init__(
        self,
        inner: AIProvider,
        redis: Redis,
        provider_name: str,
        failure_threshold: int,
        recovery_seconds: int,
        retry_attempts: int,
    ) -> None:
        self._inner = inner
        self._redis = redis
        self._provider_name = provider_name
        self._failure_threshold = failure_threshold
        self._recovery_seconds = recovery_seconds
        self._retry_attempts = retry_attempts

    async def complete(self, request: CompletionRequest) -> Completion:
        retry_after = await self._open_for()
        if retry_after is not None:
            logger.warning(
                "ai.circuit_open",
                extra={
                    "fields": {
                        "provider": self._provider_name,
                        "retry_after_seconds": retry_after,
                    }
                },
            )
            raise AIUnavailable(
                "El proveedor de IA está en pausa. Reintentá cuando termine la ventana.",
                retry_after_seconds=retry_after,
            )
        try:
            completion = await self._call_with_retry(request)
        except ProviderUnavailable as exc:
            await self._record_failure()
            raise AIUnavailable("El proveedor de IA no respondió.") from exc
        await self._record_success()
        return completion

    async def _call_with_retry(self, request: CompletionRequest) -> Completion:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._retry_attempts),
            wait=wait_exponential(multiplier=0.05, min=0.05, max=0.2),
            retry=retry_if_exception_type(ProviderUnavailable),
            reraise=True,
            before_sleep=self._log_retry,
        ):
            with attempt:
                return await self._inner.complete(request)
        raise ProviderUnavailable("sin intentos")

    def _log_retry(self, retry_state) -> None:
        logger.warning(
            "ai.retry",
            extra={
                "fields": {
                    "provider": self._provider_name,
                    "attempt": retry_state.attempt_number,
                }
            },
        )

    async def _open_for(self) -> int | None:
        raw = await self._redis.get(self._open_key)
        if raw is None:
            return None
        remaining = float(raw) - time.time()
        if remaining <= 0:
            return None
        return max(int(remaining), 1)

    async def _record_failure(self) -> None:
        failures = await self._redis.incr(self._fail_key)
        if failures == 1:
            await self._redis.expire(self._fail_key, self._recovery_seconds * 4)
        if failures >= self._failure_threshold:
            open_until = time.time() + self._recovery_seconds
            await self._redis.set(self._open_key, f"{open_until:.3f}", ex=self._recovery_seconds)
            logger.warning(
                "ai.circuit_opened",
                extra={
                    "fields": {
                        "provider": self._provider_name,
                        "failures": failures,
                        "recovery_seconds": self._recovery_seconds,
                    }
                },
            )

    async def _record_success(self) -> None:
        await self._redis.delete(self._fail_key, self._open_key)

    @property
    def _fail_key(self) -> str:
        return f"circuit:{self._provider_name}:failures"

    @property
    def _open_key(self) -> str:
        return f"circuit:{self._provider_name}:open_until"
