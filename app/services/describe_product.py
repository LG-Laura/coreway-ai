import logging
from datetime import datetime, timezone

from app.core.context import request_id_var
from app.domain.catalog import CompletionRequest, GeneratedDescription, ProductBrief
from app.domain.events import DescriptionEventPublisher, DescriptionGenerated
from app.domain.ports import AIProvider

logger = logging.getLogger(__name__)

_INSTRUCTION = (
    "Escribí una descripción corta de producto para una tienda online, "
    "en español, en una o dos oraciones."
)


class DescribeProduct:
    """Caso de uso: ficha de catálogo a partir de un brief."""

    def __init__(self, provider: AIProvider, events: DescriptionEventPublisher) -> None:
        self._provider = provider
        self._events = events

    async def execute(self, brief: ProductBrief) -> GeneratedDescription:
        completion = await self._provider.complete(
            CompletionRequest(instruction=_INSTRUCTION, prompt=_prompt(brief))
        )
        logger.info(
            "ai.completion",
            extra={
                "fields": {
                    "use_case": "describe_product",
                    "provider": completion.provider,
                    "model": completion.model,
                }
            },
        )
        self._events.publish(
            DescriptionGenerated(
                name=brief.name,
                category=brief.category,
                provider=completion.provider,
                model=completion.model,
                request_id=request_id_var.get(),
                occurred_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        return GeneratedDescription(
            text=completion.text,
            provider=completion.provider,
            model=completion.model,
        )


def _prompt(brief: ProductBrief) -> str:
    attributes = ", ".join(brief.attributes) if brief.attributes else "sin atributos cargados"
    return (
        f"nombre: {brief.name}\n"
        f"categoria: {brief.category}\n"
        f"atributos: {attributes}\n"
        f"tono: {brief.tone}"
    )
