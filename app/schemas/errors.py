from pydantic import BaseModel, Field


class ValidationErrorItem(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ErrorDetail(BaseModel):
    code: str = Field(examples=["validation_error"])
    message: str = Field(examples=["请求参数校验失败"])
    errors: list[ValidationErrorItem] | None = None
