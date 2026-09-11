import logging

from fastapi import APIRouter, Response, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.deps import DbSession
from app.db.session import ping_database
from app.schemas.health import HealthResponse, ReadyResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
    )


@router.get("/ready", response_model=ReadyResponse)
def ready(response: Response, session: DbSession) -> ReadyResponse:
    payload = {
        "app": settings.app_name,
        "version": settings.app_version,
    }
    try:
        ping_database(session)
    except SQLAlchemyError as exc:
        logger.warning("database ready check failed: %s", type(exc).__name__)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(status="unavailable", database="unavailable", **payload)
    return ReadyResponse(status="ok", database="ok", **payload)
