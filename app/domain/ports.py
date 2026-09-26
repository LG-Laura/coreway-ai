from typing import Protocol

from app.domain.catalog import Completion, CompletionRequest


class AIProvider(Protocol):
    """Puerto de salida hacia un modelo de lenguaje.

    El caso de uso depende de esta interfaz. Cambiar de proveedor es
    cambiar el adaptador que se construye al arrancar, no el servicio.
    """

    async def complete(self, request: CompletionRequest) -> Completion: ...
