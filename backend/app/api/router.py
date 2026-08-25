from fastapi import APIRouter

from app.api.routes import health

# Versioned API router. Future domain modules register their own
# routers here (see docs/07_API_Design.md for endpoint standards).
api_router = APIRouter()

api_router.include_router(health.router, tags=["system"])
