from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    app: str = Field(examples=["fast-staratlas-ai"])
    version: str = Field(examples=["0.1.0"])


class ReadyResponse(BaseModel):
    status: str = Field(examples=["ok"])
    app: str = Field(examples=["fast-staratlas-ai"])
    version: str = Field(examples=["0.1.0"])
    database: str = Field(examples=["ok"])
