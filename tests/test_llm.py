import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from app.llm.deps import get_chat_model_factory, get_config_provider
from app.main import app
from app.schemas.llm import ChatRequest, ChatResponse, LLMConfigPublic
from tests.llm_fakes import FakeChatModelFactory, InMemoryLLMConfigProvider, make_config

CHAT_PATH = "/api/v1/llm/chat"
STREAM_PATH = "/api/v1/llm/chat/stream"
CONFIGS_PATH = "/api/v1/llm/configs"
GENERATE_PATH = "/api/v1/llm/images/generate"
EDIT_PATH = "/api/v1/llm/images/edit"
USER_MESSAGE = {"role": "user", "content": "hello"}
CHAT_BODY = {"config": "gpt-mini", "messages": [USER_MESSAGE]}


@pytest.fixture
def fake_provider() -> InMemoryLLMConfigProvider:
    return InMemoryLLMConfigProvider(
        configs={
            "gpt-mini": make_config("gpt-mini"),
            "deepseek-r1": make_config("deepseek-r1", model="deepseek-reasoner"),
        }
    )


@pytest.fixture
def fake_factory() -> FakeChatModelFactory:
    return FakeChatModelFactory()


@pytest.fixture
def llm_client(
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
) -> Iterator[TestClient]:
    app.dependency_overrides[get_config_provider] = lambda: fake_provider
    app.dependency_overrides[get_chat_model_factory] = lambda: fake_factory
    with TestClient(app) as test_client:
        yield test_client


def parse_sse(body: str) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    for chunk in body.split("\n\n"):
        if not chunk.strip():
            continue
        event_name: str | None = None
        data: dict[str, object] | None = None
        for line in chunk.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:") :].strip())
        if event_name is not None:
            events.append((event_name, data or {}))
    return events


def assert_no_secrets(payload: object) -> None:
    dumped = json.dumps(payload)
    assert "apikey" not in dumped
    assert "test-gpt-mini-key" not in dumped
    assert "test-deepseek-r1-key" not in dumped
    assert "Authorization" not in dumped


def test_list_configs_ready_without_secrets(llm_client: TestClient) -> None:
    response = llm_client.get(CONFIGS_PATH)
    assert response.status_code == 200
    body = response.json()
    names = {item["name"]: item for item in body["items"]}
    assert names["gpt-mini"]["ready"] is True
    assert names["gpt-mini"]["has_key"] is True
    assert names["gpt-mini"]["api"] == "chat"
    assert_no_secrets(body)


def test_list_configs_marks_missing_key_not_ready(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
) -> None:
    fake_provider.configs["gpt-mini"] = make_config("gpt-mini", ready=False)
    response = llm_client.get(CONFIGS_PATH)
    item = next(entry for entry in response.json()["items"] if entry["name"] == "gpt-mini")
    assert item["ready"] is False
    assert item["has_key"] is False
    assert_no_secrets(response.json())


def test_chat_success(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    response = llm_client.post(CHAT_PATH, json=CHAT_BODY)
    assert response.status_code == 200
    body = response.json()
    assert body["config"] == "gpt-mini"
    assert body["content"] == "fake-assistant-reply"
    assert fake_factory.created[0].name == "gpt-mini"
    assert_no_secrets(body)


def test_chat_does_not_inject_system_prompt(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    response = llm_client.post(CHAT_PATH, json=CHAT_BODY)
    assert response.status_code == 200
    sent = fake_factory.invoke_messages[0]
    assert isinstance(sent[0], HumanMessage)
    assert sent[0].content == "hello"


def test_chat_requires_config(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 422
    assert fake_factory.created == []


def test_chat_rejects_extra_override_fields(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    for extra in (
        {"apikey": "sk-secret"},
        {"model": "gpt-4o"},
        {"baseurl": "https://example.invalid/v1"},
        {"think": True},
    ):
        response = llm_client.post(CHAT_PATH, json={**CHAT_BODY, **extra})
        assert response.status_code == 422
    assert fake_factory.created == []


def test_chat_fallback_to_ready_config(
    llm_client: TestClient,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_factory.set_behavior("gpt-mini", fail=TimeoutError("timed out"))
    response = llm_client.post(
        CHAT_PATH,
        json={"config": "gpt-mini", "fallback": "deepseek-r1", "messages": [USER_MESSAGE]},
    )
    assert response.status_code == 200
    assert response.json()["config"] == "deepseek-r1"
    assert [item.name for item in fake_factory.created] == ["gpt-mini", "deepseek-r1"]


def test_chat_primary_not_ready_does_not_fallback(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_provider.configs["gpt-mini"] = make_config("gpt-mini", ready=False)
    response = llm_client.post(
        CHAT_PATH,
        json={"config": "gpt-mini", "fallback": "deepseek-r1", "messages": [USER_MESSAGE]},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "config_not_ready"
    assert fake_factory.created == []


def test_chat_api_mismatch(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_provider.configs["poster"] = make_config(
        "poster",
        api="image.generate",
        model="gpt-image-1",
        size="1024x1024",
    )
    response = llm_client.post(CHAT_PATH, json={"config": "poster", "messages": [USER_MESSAGE]})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "api_mismatch"
    assert fake_factory.created == []


def test_chat_stream_success(llm_client: TestClient) -> None:
    response = llm_client.post(STREAM_PATH, json=CHAT_BODY)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert "delta" in names
    assert names[-1] == "done"
    assert events[-1][1]["config"] == "gpt-mini"


def test_chat_stream_flag_uses_sse(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
) -> None:
    fake_provider.configs["gpt-mini"] = make_config("gpt-mini", stream=True)
    response = llm_client.post(CHAT_PATH, json=CHAT_BODY)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")


def test_generate_image_success(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_provider.configs["poster"] = make_config(
        "poster",
        api="image.generate",
        model="gpt-image-1",
        size="1024x1024",
    )
    response = llm_client.post(GENERATE_PATH, json={"config": "poster", "prompt": "a cat"})
    assert response.status_code == 200
    body = response.json()
    assert body["config"] == "poster"
    assert body["images"][0]["b64_json"] == "ZmFrZQ=="
    assert fake_factory.created[0].name == "poster"


def test_edit_image_success(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
) -> None:
    fake_provider.configs["editor"] = make_config("editor", api="image.edit", model="gpt-image-1", size="1024x1024")
    response = llm_client.post(
        EDIT_PATH,
        data={"config": "editor", "prompt": "make blue"},
        files={"image": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["config"] == "editor"


def test_config_not_found(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    response = llm_client.post(CHAT_PATH, json={"config": "missing", "messages": [USER_MESSAGE]})
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "config_not_found"
    assert fake_factory.created == []


def test_fallback_not_found(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    response = llm_client.post(
        CHAT_PATH,
        json={"config": "gpt-mini", "fallback": "missing", "messages": [USER_MESSAGE]},
    )
    assert response.status_code == 404
    assert fake_factory.created == []


def test_chat_rejects_over_max_length(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_provider.configs["gpt-mini"] = make_config("gpt-mini", max_length=3)
    response = llm_client.post(
        CHAT_PATH, json={"config": "gpt-mini", "messages": [{"role": "user", "content": "abcd"}]}
    )
    assert response.status_code == 422
    assert fake_factory.created == []


def test_failure_logs_config_not_secrets(
    llm_client: TestClient,
    fake_factory: FakeChatModelFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_factory.set_behavior("gpt-mini", fail=TimeoutError("timed out"))
    with caplog.at_level(logging.WARNING, logger="app.llm.orchestrator"):
        response = llm_client.post(CHAT_PATH, json=CHAT_BODY)
    assert response.status_code == 503
    assert "gpt-mini" in caplog.text
    assert "upstream_timeout" in caplog.text
    assert "test-gpt-mini-key" not in caplog.text


def test_response_models_have_no_secret_fields() -> None:
    for model in (ChatRequest, ChatResponse, LLMConfigPublic):
        names = set(model.model_fields)
        assert "apikey" not in names
        assert "api_key" not in names


def test_env_example_points_to_yaml() -> None:
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "LLM_CONFIG=" in text
    yaml_text = Path("config/llm.yaml").read_text(encoding="utf-8")
    assert 'apikey: ""' in yaml_text or "apikey: ''" in yaml_text or "apikey:" in yaml_text
    assert "sk-" not in yaml_text
