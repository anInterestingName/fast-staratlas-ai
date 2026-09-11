from typing import Any, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from openai import AsyncOpenAI

from app.llm.errors import ApiMismatchError, ConfigNotReadyError, ProtocolNotSupportedError
from app.llm.models import SUPPORTED_PROTOCOL, TEXT_APIS, LLMConfig


class ChatModelFactory(Protocol):
    def create_chat_model(self, config: LLMConfig) -> Any: ...

    def clear_cache(self) -> None: ...

    async def generate_image(self, config: LLMConfig, prompt: str) -> list[dict[str, str | None]]: ...

    async def edit_image(
        self,
        config: LLMConfig,
        prompt: str,
        image: bytes,
        mask: bytes | None = None,
        filename: str = "image.png",
        mask_filename: str = "mask.png",
    ) -> list[dict[str, str | None]]: ...


def reasoning_effort_for(config: LLMConfig) -> str | None:
    if config.think:
        return config.think_level
    if config.think_level == "none":
        return "none"
    return None


def _base_url(config: LLMConfig) -> str | None:
    return config.baseurl.strip() or None


class LangchainChatModelFactory:
    def __init__(self) -> None:
        self._cache: dict[tuple[object, ...], BaseChatModel] = {}

    def clear_cache(self) -> None:
        self._cache.clear()

    def create_chat_model(self, config: LLMConfig) -> BaseChatModel:
        _ensure_openai_ready(config)
        if config.api not in TEXT_APIS:
            raise ApiMismatchError("当前配置不是对话接口")
        effort = reasoning_effort_for(config)
        fingerprint = (
            config.name,
            config.protocol,
            config.api,
            config.model,
            config.baseurl,
            config.apikey,
            config.timeout,
            config.temperature,
            config.think,
            config.think_level,
        )
        cached = self._cache.get(fingerprint)
        if cached is not None:
            return cached
        kwargs: dict[str, Any] = {
            "model": config.model,
            "api_key": config.apikey,
            "base_url": _base_url(config),
            "timeout": config.timeout,
            "max_retries": 0,
            "use_responses_api": config.api == "responses",
        }
        if effort is not None:
            kwargs["reasoning_effort"] = effort
        if effort is None or effort == "none":
            kwargs["temperature"] = config.temperature
        model = ChatOpenAI(**kwargs)
        self._cache[fingerprint] = model
        return model

    async def generate_image(self, config: LLMConfig, prompt: str) -> list[dict[str, str | None]]:
        _ensure_openai_ready(config)
        if config.api != "image.generate":
            raise ApiMismatchError("当前配置不是图像生成接口")
        client = _openai_client(config)
        kwargs: dict[str, Any] = {"model": config.model, "prompt": prompt}
        if config.size:
            kwargs["size"] = config.size
        if config.quality:
            kwargs["quality"] = config.quality
        if config.n:
            kwargs["n"] = config.n
        result = await client.images.generate(**kwargs)
        return _image_assets(result)

    async def edit_image(
        self,
        config: LLMConfig,
        prompt: str,
        image: bytes,
        mask: bytes | None = None,
        filename: str = "image.png",
        mask_filename: str = "mask.png",
    ) -> list[dict[str, str | None]]:
        _ensure_openai_ready(config)
        if config.api != "image.edit":
            raise ApiMismatchError("当前配置不是图像编辑接口")
        client = _openai_client(config)
        kwargs: dict[str, Any] = {
            "model": config.model,
            "prompt": prompt,
            "image": (filename, image),
        }
        if mask is not None:
            kwargs["mask"] = (mask_filename, mask)
        if config.size:
            kwargs["size"] = config.size
        if config.n:
            kwargs["n"] = config.n
        result = await client.images.edit(**kwargs)
        return _image_assets(result)


def _ensure_openai_ready(config: LLMConfig) -> None:
    if not config.ready:
        raise ConfigNotReadyError(config.name)
    if config.protocol != SUPPORTED_PROTOCOL:
        raise ProtocolNotSupportedError(config.name, config.protocol)


def _openai_client(config: LLMConfig) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=config.apikey, base_url=_base_url(config), timeout=config.timeout)


def _image_assets(result: Any) -> list[dict[str, str | None]]:
    assets: list[dict[str, str | None]] = []
    for item in getattr(result, "data", []) or []:
        assets.append(
            {
                "b64_json": getattr(item, "b64_json", None),
                "url": getattr(item, "url", None),
            }
        )
    return assets
