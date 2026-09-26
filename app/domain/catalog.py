from dataclasses import dataclass


@dataclass(frozen=True)
class ProductBrief:
    name: str
    category: str
    attributes: tuple[str, ...]
    tone: str


@dataclass(frozen=True)
class CompletionRequest:
    """Lo que el caso de uso le pide a cualquier proveedor.

    instruction dice la tarea. prompt trae los datos. Ningún adaptador
    obliga al servicio a conocer OpenAI, Gemini ni otro SDK.
    """

    instruction: str
    prompt: str


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    model: str


@dataclass(frozen=True)
class GeneratedDescription:
    text: str
    provider: str
    model: str
