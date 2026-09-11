import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import SystemMessage

from app.api.routes.demo import reset_demo_store
from app.llm.deps import get_chat_model_factory, get_config_provider
from app.main import app
from app.schemas.llm import ChatRequest, ChatResponse, LLMProfileItem
from tests.llm_fakes import (
    DEFAULT_SYSTEM_PROMPT,
    FakeChatModelFactory,
    InMemoryLLMConfigProvider,
    make_profile,
)

CHAT_PATH = "/api/v1/llm/chat"
STREAM_PATH = "/api/v1/llm/chat/stream"
PROFILES_PATH = "/api/v1/llm/profiles"
USER_MESSAGE = {"role": "user", "content": "hello"}


@pytest.fixture
def fake_provider() -> InMemoryLLMConfigProvider:
    return InMemoryLLMConfigProvider(
        profiles={
            "fast": make_profile("fast"),
            "smart": make_profile("smart"),
        },
        fallbacks=["fast"],
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
    reset_demo_store()
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
    assert "api_key" not in dumped
    assert "test-smart-key" not in dumped
    assert "test-fast-key" not in dumped
    assert "Authorization" not in dumped


def test_list_profiles_ready_without_secrets(llm_client: TestClient) -> None:
    response = llm_client.get(PROFILES_PATH)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    items = {item["name"]: item for item in body["items"]}
    assert items["smart"] == {"name": "smart", "ready": True, "model": "gpt-4o-mini"}
    assert set(items["smart"].keys()) == {"name", "ready", "model"}
    assert_no_secrets(body)


def test_list_profiles_marks_missing_key_not_ready(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
) -> None:
    fake_provider.profiles["fast"] = make_profile("fast", ready=False)
    response = llm_client.get(PROFILES_PATH)
    assert response.status_code == 200
    items = {item["name"]: item for item in response.json()["items"]}
    assert items["fast"]["ready"] is False
    assert_no_secrets(response.json())


def test_health_and_demo_do_not_depend_on_llm_keys(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    demo = client.get("/api/v1/demo")
    assert demo.status_code == 200
    assert demo.json()["total"] == 1


def test_chat_default_profile_success(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "smart"
    assert body["content"] == "fake-assistant-reply"
    assert body["usage"] == {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}
    assert set(body.keys()) <= {"profile", "content", "usage"}
    assert_no_secrets(body)
    assert fake_factory.created[0].model == "gpt-4o-mini"


def test_chat_specified_fast_profile(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    response = llm_client.post(CHAT_PATH, json={"profile": "fast", "messages": [USER_MESSAGE]})
    assert response.status_code == 200
    assert response.json()["profile"] == "fast"
    assert fake_factory.created[0].name == "fast"


def test_chat_uses_configured_model_name(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_provider.profiles["smart"] = make_profile("smart", model="gpt-4.1-mini")
    response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 200
    assert fake_factory.created[0].model == "gpt-4.1-mini"


def test_chat_prepends_system_prompt(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 200
    sent = fake_factory.invoke_messages[0]
    assert isinstance(sent[0], SystemMessage)
    assert sent[0].content == DEFAULT_SYSTEM_PROMPT
    assert sent[1].content == "hello"


def test_chat_rejects_extra_override_fields(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    for extra in (
        {"api_key": "sk-secret"},
        {"model": "gpt-4o"},
        {"base_url": "https://example.invalid/v1"},
        {"provider": "openai_compat"},
    ):
        response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE], **extra})
        assert response.status_code == 422
    assert fake_factory.created == []
    assert fake_factory.invoke_messages == []


def test_chat_rejects_empty_or_invalid_messages(
    llm_client: TestClient,
    fake_factory: FakeChatModelFactory,
) -> None:
    cases = [
        {"messages": []},
        {"messages": [{"role": "tool", "content": "hello"}]},
        {"messages": [{"role": "user", "content": "   "}]},
    ]
    for payload in cases:
        response = llm_client.post(CHAT_PATH, json=payload)
        assert response.status_code == 422
    assert fake_factory.created == []


def test_chat_rejects_over_max_messages(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_provider.profiles["smart"] = make_profile("smart", max_messages=1)
    response = llm_client.post(
        CHAT_PATH,
        json={
            "messages": [
                {"role": "user", "content": "one"},
                {"role": "user", "content": "two"},
            ]
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"
    assert fake_factory.created == []


def test_chat_rejects_over_max_content_length(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_provider.profiles["smart"] = make_profile("smart", max_content_length=3)
    response = llm_client.post(CHAT_PATH, json={"messages": [{"role": "user", "content": "abcd"}]})
    assert response.status_code == 422
    assert fake_factory.created == []


def test_chat_profile_not_found(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    response = llm_client.post(CHAT_PATH, json={"profile": "missing", "messages": [USER_MESSAGE]})
    assert response.status_code == 404
    assert response.json()["detail"] == {"code": "profile_not_found", "message": "模型档案不存在: missing"}
    assert fake_factory.created == []


def test_chat_profile_not_ready_does_not_fallback(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_provider.profiles["smart"] = make_profile("smart", ready=False)
    response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "profile_not_ready"
    assert fake_factory.created == []


def test_chat_fallback_to_ready_profile(
    llm_client: TestClient,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_factory.set_behavior("smart", fail=TimeoutError("timed out"))
    fake_factory.set_behavior("fast", content="from-fast")
    response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "fast"
    assert body["content"] == "from-fast"
    assert [item.name for item in fake_factory.created] == ["smart", "fast"]


def test_chat_all_profiles_fail(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    fake_factory.set_behavior("smart", fail=TimeoutError("timed out"))
    fake_factory.set_behavior("fast", fail=TimeoutError("timed out"))
    response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == "upstream_timeout"
    assert "content" not in body
    assert_no_secrets(body)


def test_chat_empty_content_is_not_success(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    fake_factory.set_behavior("smart", empty=True)
    fake_factory.set_behavior("fast", empty=True)
    response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "upstream_failed"


def test_chat_timeout_maps_to_upstream_timeout(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
) -> None:
    fake_provider.fallbacks = []
    fake_factory.set_behavior("smart", fail=TimeoutError("timed out"))
    response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "upstream_timeout"


def test_stream_success_has_delta_and_done(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    fake_factory.set_behavior("smart", stream_chunks=["Hel", "lo"])
    response = llm_client.post(STREAM_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers.get("cache-control") == "no-cache"
    events = parse_sse(response.text)
    assert events[0] == ("delta", {"content": "Hel"})
    assert events[1] == ("delta", {"content": "lo"})
    assert events[-1][0] == "done"
    assert events[-1][1]["profile"] == "smart"
    assert "error" not in {name for name, _ in events}
    assert_no_secrets(events)


def test_stream_invalid_request_is_json_not_sse(
    llm_client: TestClient,
    fake_factory: FakeChatModelFactory,
) -> None:
    response = llm_client.post(STREAM_PATH, json={"messages": []})
    assert response.status_code == 422
    assert "text/event-stream" not in response.headers.get("content-type", "")
    assert fake_factory.created == []


def test_stream_midway_failure_sends_error(llm_client: TestClient, fake_factory: FakeChatModelFactory) -> None:
    fake_factory.set_behavior(
        "smart",
        stream_chunks=["hello"],
        stream_fail_after=1,
        fail=RuntimeError("boom"),
    )
    response = llm_client.post(STREAM_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 200
    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert "delta" in names
    assert names[-1] == "error"
    assert "done" not in names
    assert events[-1][1]["code"] == "upstream_failed"


def test_failure_logs_profile_not_secrets(
    llm_client: TestClient,
    fake_provider: InMemoryLLMConfigProvider,
    fake_factory: FakeChatModelFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_provider.fallbacks = []
    fake_factory.set_behavior("smart", fail=TimeoutError("timed out"))
    with caplog.at_level(logging.WARNING, logger="app.llm.orchestrator"):
        response = llm_client.post(CHAT_PATH, json={"messages": [USER_MESSAGE]})
    assert response.status_code == 503
    assert "smart" in caplog.text
    assert "upstream_timeout" in caplog.text
    assert "test-smart-key" not in caplog.text
    assert "hello" not in caplog.text


def test_response_models_have_no_storage_source_fields() -> None:
    for model in (ChatRequest, ChatResponse, LLMProfileItem):
        names = set(model.model_fields)
        assert "api_key" not in names
        assert "base_url" not in names
        assert "provider" not in names
        assert "source" not in names


def test_no_profile_write_routes(llm_client: TestClient) -> None:
    assert llm_client.post(PROFILES_PATH, json={"name": "x"}).status_code in {404, 405}
    assert llm_client.put(f"{PROFILES_PATH}/smart", json={"model": "x"}).status_code in {404, 405}
    assert llm_client.delete(f"{PROFILES_PATH}/smart").status_code in {404, 405}


def test_no_llm_sql_scripts() -> None:
    sql_dir = Path("doc/sql")
    if not sql_dir.exists():
        return
    assert not any("llm" in path.name.lower() for path in sql_dir.rglob("*"))


def test_env_example_has_placeholder_keys_only() -> None:
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "LLM__PROFILES__SMART__API_KEY=" in text
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "API_KEY" in stripped:
            _name, _, value = stripped.partition("=")
            assert value == ""
            assert "sk-" not in value
