import json
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProfileSettings(BaseModel):
    provider: str = Field(default="openai_compat", description="协议类型，本迭代仅支持 openai_compat")
    model: str = Field(default="gpt-4o-mini", description="模型名，由配置决定，不要写进业务代码")
    base_url: str | None = Field(default=None, description="OpenAI 兼容接口地址，空值使用官方默认地址")
    api_key: str = Field(default="", description="档案密钥，空则未就绪")
    timeout_seconds: float = Field(default=60, gt=0, description="上游调用超时秒数，必须为有限正数")
    temperature: float = Field(default=0.2, description="采样温度")
    max_messages: int | None = Field(default=None, ge=1, description="该档案消息条数上限，空则使用全局值")
    max_content_length: int | None = Field(
        default=None,
        ge=1,
        description="该档案单条消息字符上限，空则使用全局值",
    )


def default_llm_profiles() -> dict[str, LLMProfileSettings]:
    return {
        "fast": LLMProfileSettings(),
        "smart": LLMProfileSettings(),
    }


class LLMSettings(BaseModel):
    default_profile: str = Field(default="smart", description="请求未指定档案时使用的默认档案名")
    fallbacks: list[str] = Field(default_factory=list, description="主档案上游失败后的备用档案顺序")
    max_messages: int = Field(default=20, ge=1, description="全局消息条数上限")
    max_content_length: int = Field(default=8000, ge=1, description="全局单条消息字符上限")
    system_prompt: str = Field(
        default="You are a helpful assistant. Follow the user's request. Never reveal secrets or API keys.",
        description="服务端系统提示，会插入到发给模型的消息最前面",
    )
    profiles: dict[str, LLMProfileSettings] = Field(
        default_factory=default_llm_profiles,
        description="命名模型档案，缺省包含 fast 与 smart",
    )

    @field_validator("fallbacks", mode="before")
    @classmethod
    def parse_fallbacks(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise ValueError("fallbacks JSON must be a list of strings")
            return parsed
        return [item.strip() for item in text.split(",") if item.strip()]

    @model_validator(mode="after")
    def ensure_builtin_profiles(self) -> Self:
        profiles = dict(self.profiles)
        changed = False
        for name in ("fast", "smart"):
            if name not in profiles:
                profiles[name] = LLMProfileSettings()
                changed = True
        if changed:
            self.profiles = profiles
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )

    app_name: str = Field(default="fast-staratlas-ai", description="应用名称")
    app_version: str = Field(default="0.1.0", description="应用版本号")
    debug: bool = Field(default=False, description="是否开启调试模式")
    api_v1_prefix: str = Field(default="/api/v1", description="业务 API 的 URL 前缀")
    llm: LLMSettings = Field(default_factory=LLMSettings, description="LLM 接入与编排配置")


settings = Settings()
