import os

import pytest

from app.core.config import Settings
from app.llm.config_provider import SettingsLLMConfigProvider
from app.llm.factory import LangchainChatModelFactory
from tests.llm_fakes import make_profile


@pytest.fixture
def clean_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("LLM") or key in {"APP_NAME", "APP_VERSION", "DEBUG", "API_V1_PREFIX"}:
            monkeypatch.delenv(key, raising=False)


def test_nested_env_does_not_break_flat_settings(
    monkeypatch: pytest.MonkeyPatch,
    clean_llm_env: None,
) -> None:
    monkeypatch.setenv("APP_NAME", "custom-app")
    monkeypatch.setenv("LLM__DEFAULT_PROFILE", "fast")
    monkeypatch.setenv("LLM__FALLBACKS", '["smart","fast"]')
    monkeypatch.setenv("LLM__PROFILES__FAST__API_KEY", "test-key")
    monkeypatch.setenv("LLM__PROFILES__FAST__MODEL", "gpt-4.1-mini")
    loaded = Settings(_env_file=None)
    assert loaded.app_name == "custom-app"
    assert loaded.llm.default_profile == "fast"
    assert loaded.llm.fallbacks == ["smart", "fast"]
    assert loaded.llm.profiles["fast"].api_key == "test-key"
    assert loaded.llm.profiles["fast"].model == "gpt-4.1-mini"
    assert "smart" in loaded.llm.profiles


def test_settings_allow_empty_llm_keys(clean_llm_env: None) -> None:
    loaded = Settings(_env_file=None)
    provider = SettingsLLMConfigProvider(loaded)
    profiles = {item.name: item for item in provider.list_profiles()}
    assert profiles["fast"].ready is False
    assert profiles["smart"].ready is False
    assert profiles["smart"].api_key == ""


def test_factory_passes_model_timeout_and_disables_retries() -> None:
    factory = LangchainChatModelFactory()
    profile = make_profile("smart", model="gpt-4.1-mini", timeout_seconds=12, temperature=0.1)
    model = factory.create_chat_model(profile)
    assert model.model_name == "gpt-4.1-mini"
    assert model.request_timeout == 12
    assert model.max_retries == 0
    assert model.temperature == 0.1
