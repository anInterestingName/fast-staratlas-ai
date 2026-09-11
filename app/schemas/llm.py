from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.llm.item import LLMConfigItem
from app.llm.models import LLMConfig
from app.schemas.errors import ErrorDetail


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

    config: str = Field(min_length=1, examples=["gpt-mini"])
    fallback: str | None = Field(default=None, min_length=1, examples=["deepseek-r1"])
    messages: list[ChatMessage] = Field(min_length=1)


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponse(BaseModel):
    config: str = Field(examples=["gpt-mini"])
    content: str = Field(examples=["助手文本"])
    usage: TokenUsage | None = None


class LLMConfigPublic(BaseModel):
    name: str
    protocol: str
    api: str
    baseurl: str
    timeout: float
    model: str
    stream: bool
    think: bool
    think_level: str
    temperature: float
    size: str | None = None
    quality: str | None = None
    n: int | None = None
    max_messages: int
    max_length: int
    ready: bool
    has_key: bool


class LLMConfigListResponse(BaseModel):
    total: int
    items: list[LLMConfigPublic]


class LLMConfigCreateRequest(LLMConfigItem):
    name: str = Field(min_length=1, examples=["gpt-mini"])


class ImageGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: str = Field(min_length=1)
    fallback: str | None = Field(default=None, min_length=1)
    prompt: str = Field(min_length=1)


class ImageAsset(BaseModel):
    b64_json: str | None = None
    url: str | None = None


class ImageResponse(BaseModel):
    config: str
    images: list[ImageAsset]


def public_config(item: LLMConfig) -> LLMConfigPublic:
    return LLMConfigPublic(
        name=item.name,
        protocol=item.protocol,
        api=item.api,
        baseurl=item.baseurl,
        timeout=item.timeout,
        model=item.model,
        stream=item.stream,
        think=item.think,
        think_level=item.think_level,
        temperature=item.temperature,
        size=item.size,
        quality=item.quality,
        n=item.n,
        max_messages=item.max_messages,
        max_length=item.max_length,
        ready=item.ready,
        has_key=item.has_key,
    )


LLMErrorBody = ErrorDetail
