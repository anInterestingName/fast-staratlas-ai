from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.llm.models import IMAGE_APIS, TEXT_APIS, ApiType, LLMConfig, ProtocolType, ThinkLevel

CONFIG_NAME_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]{0,63}$"


class LLMConfigItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: ProtocolType
    api: ApiType
    baseurl: str = ""
    apikey: str | None = Field(
        default=None,
        description="仅写入。省略或 null 表示保留原密钥；传入字符串则替换。GET 响应永不包含此字段。",
        json_schema_extra={"writeOnly": True},
    )
    timeout: float = Field(default=60, gt=0)
    model: str = Field(min_length=1)
    stream: bool = False
    think: bool = False
    think_level: ThinkLevel = "medium"
    temperature: float = 0.2
    size: str | None = None
    quality: str | None = None
    n: int | None = Field(default=None, ge=1)
    max_messages: int = Field(default=20, ge=1)
    max_length: int = Field(default=8000, ge=1)

    @field_validator("baseurl", "model")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("apikey")
    @classmethod
    def strip_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def validate_combination(self) -> Self:
        if self.think and self.think_level == "none":
            raise ValueError("think=true 时 think_level 不能为 none")
        if self.api in IMAGE_APIS and self.think:
            raise ValueError("图像配置不能开启 think")
        if self.api in TEXT_APIS and (self.size or self.quality or self.n is not None):
            raise ValueError("文本配置不能设置 size/quality/n")
        if self.protocol == "anthropic" and self.api != "chat":
            raise ValueError("anthropic 仅支持 api=chat")
        return self


def resolved_apikey(item: LLMConfigItem) -> str:
    return item.apikey or ""


def is_ready(item: LLMConfigItem) -> bool:
    return bool(resolved_apikey(item) and item.model.strip())


def to_llm_config(name: str, item: LLMConfigItem) -> LLMConfig:
    return LLMConfig(
        name=name,
        protocol=item.protocol,
        api=item.api,
        baseurl=item.baseurl,
        apikey=resolved_apikey(item),
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
        ready=is_ready(item),
    )
