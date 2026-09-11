from typing import Annotated

from fastapi import Depends

from app.llm.config_provider import LLMConfigProvider, SettingsLLMConfigProvider
from app.llm.factory import ChatModelFactory, LangchainChatModelFactory
from app.llm.orchestrator import ChatOrchestrator

_settings_provider = SettingsLLMConfigProvider()
_chat_model_factory = LangchainChatModelFactory()


def get_config_provider() -> LLMConfigProvider:
    return _settings_provider


def get_chat_model_factory() -> ChatModelFactory:
    return _chat_model_factory


def get_chat_orchestrator(
    provider: Annotated[LLMConfigProvider, Depends(get_config_provider)],
    factory: Annotated[ChatModelFactory, Depends(get_chat_model_factory)],
) -> ChatOrchestrator:
    return ChatOrchestrator(provider=provider, factory=factory)
