from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, examples=["你好"])

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be blank")
        return stripped


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: str | None = Field(default=None, min_length=1, examples=["smart"])
    messages: list[ChatMessage] = Field(min_length=1)


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponse(BaseModel):
    profile: str = Field(examples=["smart"])
    content: str = Field(examples=["助手文本"])
    usage: TokenUsage | None = None


class LLMProfileItem(BaseModel):
    name: str = Field(examples=["smart"])
    ready: bool
    model: str = Field(examples=["gpt-4o-mini"])


class LLMProfileListResponse(BaseModel):
    total: int
    items: list[LLMProfileItem]


class LLMErrorBody(BaseModel):
    code: str
    message: str
