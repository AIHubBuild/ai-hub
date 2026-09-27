from fastapi import APIRouter

from app.api.routes import health
from app.domains.assistants import router as assistants_router

# Versioned API router. Future domain modules register their own
# routers here (see docs/07_API_Design.md for endpoint standards).
api_router = APIRouter()

api_router.include_router(health.router, tags=["system"])
api_router.include_router(assistants_router.router, tags=["assistants"])
