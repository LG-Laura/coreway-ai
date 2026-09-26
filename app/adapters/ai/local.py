import re

from app.adapters.ai.errors import ProviderUnavailable
from app.core.context import simulate_provider_failure
from app.domain.catalog import Completion, CompletionRequest

_FIELD = re.compile(r"^(nombre|categoria|atributos|tono):\s*(.*)$", re.IGNORECASE)


class LocalAIProvider:
    """Adaptador de desarrollo. No sale a la red.

    Cumple el mismo puerto que un adaptador de OpenAI o Gemini. Sirve
    para recorrer el flujo y ver proveedor y modelo en la respuesta.
    """

    name = "local"
    model = "local-catalog-v1"

    async def complete(self, request: CompletionRequest) -> Completion:
        if simulate_provider_failure.get():
            raise ProviderUnavailable("fallo simulado del proveedor")
        return Completion(
            text=_describe(request.prompt),
            provider=self.name,
            model=self.model,
        )


def _describe(prompt: str) -> str:
    fields = {
        match.group(1).lower(): match.group(2).strip()
        for line in prompt.splitlines()
        if (match := _FIELD.match(line.strip()))
    }
    name = fields.get("nombre")
    category = fields.get("categoria")
    if not name or not category:
        return prompt.strip()
    attributes = fields.get("atributos") or "sin atributos cargados"
    tone = fields.get("tono") or "claro"
    return (
        f"{name} es un producto de {category}. "
        f"Se destaca por {attributes}. "
        f"La ficha está escrita en tono {tone}."
    )
