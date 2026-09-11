from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.llm.config_provider import FileLLMConfigProvider
from app.llm.factory import LangchainChatModelFactory, reasoning_effort_for
from app.llm.item import LLMConfigItem
from app.llm.store import YamlConfigStore
from tests.llm_fakes import make_config

CONFIGS_PATH = "/api/v1/llm/configs"

SAMPLE = {
    "protocol": "openai",
    "api": "chat",
    "baseurl": "https://api.openai.com/v1",
    "apikey": "secret-one",
    "timeout": 60,
    "model": "gpt-4o-mini",
    "stream": False,
    "think": False,
}


def test_settings_has_llm_config_path() -> None:
    loaded = Settings(_env_file=None)
    assert Path(loaded.llm_config).as_posix().endswith("config/llm.yaml")


def test_yaml_store_keeps_independent_credentials(tmp_path: Path) -> None:
    store = YamlConfigStore(tmp_path / "llm.yaml")
    store.create_config("gpt-mini", LLMConfigItem.model_validate(SAMPLE))
    other = {**SAMPLE, "baseurl": "https://api.deepseek.com", "apikey": "secret-two", "model": "deepseek-chat"}
    store.create_config("deepseek-r1", LLMConfigItem.model_validate(other))
    first = store.get_config("gpt-mini")
    second = store.get_config("deepseek-r1")
    assert first is not None and second is not None
    assert first.baseurl != second.baseurl
    assert first.apikey == "secret-one"
    assert second.apikey == "secret-two"


def test_yaml_store_empty_key_not_ready(tmp_path: Path) -> None:
    store = YamlConfigStore(tmp_path / "llm.yaml")
    created = store.create_config("gpt-mini", LLMConfigItem.model_validate({**SAMPLE, "apikey": ""}))
    assert created.ready is False


def test_think_true_rejects_none_level() -> None:
    with pytest.raises(ValidationError):
        LLMConfigItem.model_validate({**SAMPLE, "think": True, "think_level": "none"})


def test_factory_maps_think_to_reasoning_effort() -> None:
    factory = LangchainChatModelFactory()
    config = make_config("smart", think=True, think_level="high", temperature=0.7)
    model = factory.create_chat_model(config)
    assert model.reasoning_effort == "high"
    assert reasoning_effort_for(config) == "high"


def test_update_with_apikey_replaces_secret(tmp_path: Path) -> None:
    store = YamlConfigStore(tmp_path / "llm.yaml")
    store.create_config("gpt-mini", LLMConfigItem.model_validate(SAMPLE))
    item = LLMConfigItem.model_validate({**SAMPLE, "apikey": "secret-two"})
    updated = store.update_config("gpt-mini", item)
    assert updated.apikey == "secret-two"
    reloaded = store.get_config("gpt-mini")
    assert reloaded is not None
    assert reloaded.apikey == "secret-two"


def test_update_omits_apikey_keeps_secret(tmp_path: Path) -> None:
    store = YamlConfigStore(tmp_path / "llm.yaml")
    store.create_config("gpt-mini", LLMConfigItem.model_validate(SAMPLE))
    item = LLMConfigItem.model_validate({k: v for k, v in SAMPLE.items() if k != "apikey"} | {"model": "gpt-4.1"})
    updated = store.update_config("gpt-mini", item)
    assert updated.model == "gpt-4.1"
    assert updated.apikey == "secret-one"
    assert updated.ready is True


def test_crud_create_get_update_delete(
    client: TestClient,
    file_config_provider: FileLLMConfigProvider,
) -> None:
    created = client.post(CONFIGS_PATH, json={"name": "gpt-mini", **SAMPLE})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "gpt-mini"
    assert body["ready"] is True
    assert body["has_key"] is True
    assert "apikey" not in body
    assert "secret-one" not in created.text

    listed = client.get(CONFIGS_PATH)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    detail = client.get(f"{CONFIGS_PATH}/gpt-mini")
    assert detail.status_code == 200
    assert detail.json()["baseurl"] == SAMPLE["baseurl"]
    assert "apikey" not in detail.json()

    duplicate = client.post(CONFIGS_PATH, json={"name": "gpt-mini", **SAMPLE})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "config_exists"

    updated = client.put(
        f"{CONFIGS_PATH}/gpt-mini",
        json={k: v for k, v in SAMPLE.items() if k != "apikey"} | {"model": "gpt-4.1-mini"},
    )
    assert updated.status_code == 200
    assert updated.json()["model"] == "gpt-4.1-mini"
    assert updated.json()["has_key"] is True

    rotated = client.put(
        f"{CONFIGS_PATH}/gpt-mini",
        json={**SAMPLE, "model": "gpt-4.1-mini", "apikey": "secret-rotated"},
    )
    assert rotated.status_code == 200
    assert rotated.json()["has_key"] is True
    assert "secret-rotated" not in rotated.text
    stored = file_config_provider.get_config("gpt-mini")
    assert stored is not None
    assert stored.apikey == "secret-rotated"

    deleted = client.delete(f"{CONFIGS_PATH}/gpt-mini")
    assert deleted.status_code == 204
    missing = client.get(f"{CONFIGS_PATH}/gpt-mini")
    assert missing.status_code == 404
