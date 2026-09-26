from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.deps import arm_provider_failure_switch, get_describe_product, get_list_events
from app.domain.catalog import ProductBrief
from app.services.describe_product import DescribeProduct
from app.services.list_events import ListDescriptionEvents

router = APIRouter(prefix="/products", tags=["catalog"])


class DescribeProductRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "Zapatillas Urban",
                    "category": "calzado",
                    "attributes": ["livianas", "blancas"],
                    "tone": "claro",
                }
            ]
        },
    )

    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=80)
    attributes: list[str] = Field(default_factory=list, max_length=20)
    tone: str = Field(default="claro", min_length=1, max_length=40)

    @field_validator("name", "category", "tone")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("no puede estar vacío")
        return cleaned

    @field_validator("attributes")
    @classmethod
    def clean_attributes(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item or len(item) > 60 for item in cleaned):
            raise ValueError("cada atributo debe tener entre 1 y 60 caracteres")
        return cleaned

    def to_brief(self) -> ProductBrief:
        return ProductBrief(
            name=self.name,
            category=self.category,
            attributes=tuple(self.attributes),
            tone=self.tone,
        )


class DescribeProductResponse(BaseModel):
    description: str
    provider: str
    model: str


class DescriptionEventResponse(BaseModel):
    event: str
    name: str
    category: str
    provider: str
    model: str
    request_id: str | None = None
    occurred_at: str


@router.post(
    "/descriptions",
    response_model=DescribeProductResponse,
    dependencies=[Depends(arm_provider_failure_switch)],
)
async def describe_product(
    body: DescribeProductRequest,
    use_case: Annotated[DescribeProduct, Depends(get_describe_product)],
) -> DescribeProductResponse:
    result = await use_case.execute(body.to_brief())
    return DescribeProductResponse(
        description=result.text,
        provider=result.provider,
        model=result.model,
    )


@router.get("/events", response_model=list[DescriptionEventResponse])
async def list_events(
    use_case: Annotated[ListDescriptionEvents, Depends(get_list_events)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[dict[str, object]]:
    return await use_case.execute(limit)
