from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FastAPI project skeleton generated from the official fastapi-new scaffold.",
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello World", "docs": "/docs"}


app.include_router(api_router)
