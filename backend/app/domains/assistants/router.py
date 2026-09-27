from fastapi import APIRouter

from app.domains.assistants.registry import get_catalogue
from app.domains.assistants.schemas import AssistantCatalogueResponse

router = APIRouter()


@router.get("/assistants", response_model=AssistantCatalogueResponse)
async def list_assistants() -> AssistantCatalogueResponse:
    return AssistantCatalogueResponse(
        success=True,
        message="Assistant catalogue retrieved",
        data=get_catalogue(),
    )
