from fastapi import APIRouter

from app.api.routes import health, llm
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(llm.router, prefix=settings.api_v1_prefix)
