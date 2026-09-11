from fastapi import APIRouter

from app.api.routes import demo, health
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(demo.router, prefix=settings.api_v1_prefix)
