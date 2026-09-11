from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="应用日志级别，与 HTTP_LOG 独立",
    )
    http_log: bool = Field(default=False, description="是否打印 HTTP 入参和响应")
    api_v1_prefix: str = Field(default="/api/v1", description="业务 API 的 URL 前缀")
    database_url: str = Field(
        default="postgresql+psycopg://staratlas:staratlas@127.0.0.1:5432/fast_staratlas_ai",
        min_length=1,
        description="PostgreSQL SQLAlchemy URL，驱动使用 psycopg",
    )
    llm_config: Path = Field(default=Path("config/llm.yaml"), description="LLM 完整配置项 YAML 路径")

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.upper()
        return value


settings = Settings()
