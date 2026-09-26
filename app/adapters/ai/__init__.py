from app.adapters.ai.local import LocalAIProvider
from app.domain.ports import AIProvider


def build_ai_provider(provider_name: str) -> AIProvider:
    """Elige el adaptador al arrancar.

    Un nombre desconocido corta el arranque. El servicio no se entera
    de esta decisión: recibe el puerto ya construido.
    """

    if provider_name == "local":
        return LocalAIProvider()
    raise ValueError(f"AI_PROVIDER desconocido: {provider_name}")
