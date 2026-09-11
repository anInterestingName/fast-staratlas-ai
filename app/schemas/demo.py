from datetime import datetime

from pydantic import BaseModel, Field


class DemoCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["star-atlas"])
    message: str = Field(min_length=1, max_length=500, examples=["Hello from the demo API"])


class DemoItem(BaseModel):
    id: int = Field(examples=[1])
    name: str = Field(examples=["star-atlas"])
    message: str = Field(examples=["Hello from the demo API"])
    created_at: datetime


class DemoListResponse(BaseModel):
    total: int
    items: list[DemoItem]
