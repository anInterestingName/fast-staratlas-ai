from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.http_log import HttpLogMiddleware
from app.core.logging import configure_logging
from app.db.session import engine

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FastAPI project skeleton generated from the official fastapi-new scaffold.",
    lifespan=lifespan,
    debug=False,
)

register_exception_handlers(app)
app.add_middleware(HttpLogMiddleware)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello World", "docs": "/docs"}


app.include_router(api_router)
