from typing import Any, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.llm.config_provider import SUPPORTED_PROVIDER
from app.llm.errors import ProfileNotReadyError
from app.llm.models import LLMProfile


class ChatModelFactory(Protocol):
    def create_chat_model(self, profile: LLMProfile) -> Any: ...


class LangchainChatModelFactory:
    def __init__(self) -> None:
        self._cache: dict[tuple[object, ...], BaseChatModel] = {}

    def create_chat_model(self, profile: LLMProfile) -> BaseChatModel:
        if profile.provider != SUPPORTED_PROVIDER or not profile.api_key.strip() or not profile.model:
            raise ProfileNotReadyError(profile.name)
        fingerprint = (
            profile.name,
            profile.provider,
            profile.model,
            profile.base_url,
            profile.api_key,
            profile.timeout_seconds,
            profile.temperature,
        )
        cached = self._cache.get(fingerprint)
        if cached is not None:
            return cached
        model = ChatOpenAI(
            model=profile.model,
            api_key=profile.api_key,
            base_url=profile.base_url,
            timeout=profile.timeout_seconds,
            max_retries=0,
            temperature=profile.temperature,
        )
        self._cache[fingerprint] = model
        return model
