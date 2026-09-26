from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DescriptionGenerated:
    """Hecho ya ocurrido: la ficha se generó.

    Viaja con datos de auditoría. El texto completo se queda en la
    respuesta HTTP; el evento no lo repite.
    """

    name: str
    category: str
    provider: str
    model: str
    request_id: str | None
    occurred_at: str


class DescriptionEventPublisher(Protocol):
    """El caso de uso publica y sigue. No espera a los suscriptores."""

    def publish(self, event: DescriptionGenerated) -> None: ...
