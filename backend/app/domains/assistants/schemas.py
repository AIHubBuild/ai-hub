from typing import Literal

from pydantic import BaseModel

AssistantStatus = Literal["available", "in_development"]


class AssistantCatalogueEntry(BaseModel):
    id: str
    name: str
    description: str
    status: AssistantStatus
    capabilities: list[str]
    launch_url: str | None
    repository_url: str


class AssistantCatalogueResponse(BaseModel):
    success: bool
    message: str
    data: list[AssistantCatalogueEntry]
