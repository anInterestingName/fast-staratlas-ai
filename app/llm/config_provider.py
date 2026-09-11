from typing import Protocol

from app.core.config import LLMProfileSettings, LLMSettings, Settings, settings
from app.llm.models import LLMProfile

SUPPORTED_PROVIDER = "openai_compat"


def _normalize_base_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def is_profile_ready(profile: LLMProfileSettings) -> bool:
    return bool(
        profile.api_key.strip()
        and profile.model.strip()
        and profile.provider.strip() == SUPPORTED_PROVIDER
    )


def build_profile(name: str, raw: LLMProfileSettings, llm: LLMSettings) -> LLMProfile:
    return LLMProfile(
        name=name,
        provider=raw.provider.strip(),
        model=raw.model.strip(),
        base_url=_normalize_base_url(raw.base_url),
        api_key=raw.api_key,
        timeout_seconds=raw.timeout_seconds,
        temperature=raw.temperature,
        max_messages=raw.max_messages if raw.max_messages is not None else llm.max_messages,
        max_content_length=(
            raw.max_content_length if raw.max_content_length is not None else llm.max_content_length
        ),
        ready=is_profile_ready(raw),
    )


class LLMConfigProvider(Protocol):
    def list_profiles(self) -> list[LLMProfile]: ...

    def get_profile(self, name: str) -> LLMProfile | None: ...

    def get_default_profile_name(self) -> str: ...

    def get_fallbacks(self) -> list[str]: ...

    def get_system_prompt(self) -> str: ...


class SettingsLLMConfigProvider:
    def __init__(self, app_settings: Settings | None = None) -> None:
        self._settings = app_settings or settings

    def list_profiles(self) -> list[LLMProfile]:
        llm = self._settings.llm
        return [build_profile(name, raw, llm) for name, raw in llm.profiles.items()]

    def get_profile(self, name: str) -> LLMProfile | None:
        raw = self._settings.llm.profiles.get(name)
        if raw is None:
            return None
        return build_profile(name, raw, self._settings.llm)

    def get_default_profile_name(self) -> str:
        return self._settings.llm.default_profile

    def get_fallbacks(self) -> list[str]:
        return list(self._settings.llm.fallbacks)

    def get_system_prompt(self) -> str:
        return self._settings.llm.system_prompt
