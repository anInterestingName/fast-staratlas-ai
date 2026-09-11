import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.logging import TRUNCATION_MARK, redact, truncate
from app.llm.deps import get_chat_model_factory, get_config_provider
from app.main import app
from tests.llm_fakes import FakeChatModelFactory, InMemoryLLMConfigProvider, make_config

CHAT_PATH = "/api/v1/llm/chat"
STREAM_PATH = "/api/v1/llm/chat/stream"
USER_MESSAGE = {"role": "user", "content": "hello"}
SECRET_TOKEN = "Bearer super-secret-token"
PROFILE_KEY = "test-gpt-mini-key"
CHAT_BODY = {"config": "gpt-mini", "messages": [USER_MESSAGE]}


@pytest.fixture
def fake_provider() -> InMemoryLLMConfigProvider:
    return InMemoryLLMConfigProvider(configs={"gpt-mini": make_config("gpt-mini")})


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


def test_http_log_disabled_omits_bodies(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "http_log", False)
    with caplog.at_level(logging.INFO, logger="app.http"):
        response = llm_client.post(CHAT_PATH, json=CHAT_BODY)
    assert response.status_code == 200
    assert "hello" not in caplog.text
    assert "fake-assistant-reply" not in caplog.text
    assert "http_request" not in caplog.text


def test_http_log_enabled_records_request_and_response(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "http_log", True)
    with caplog.at_level(logging.INFO, logger="app.http"):
        response = llm_client.post(CHAT_PATH, json=CHAT_BODY)
    assert response.status_code == 200
    assert "http_request" in caplog.text
    assert "method=POST" in caplog.text
    assert CHAT_PATH in caplog.text
    assert "hello" in caplog.text
    assert "fake-assistant-reply" in caplog.text


def test_http_log_redacts_authorization_and_keys(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "http_log", True)
    with caplog.at_level(logging.INFO, logger="app.http"):
        response = llm_client.post(
            CHAT_PATH,
            json={**CHAT_BODY, "key": "sk-secret-value"},
            headers={"Authorization": SECRET_TOKEN, "X-API-Key": "header-secret-key"},
        )
    assert response.status_code == 422
    assert SECRET_TOKEN not in caplog.text
    assert "sk-secret-value" not in caplog.text
    assert "header-secret-key" not in caplog.text
    assert PROFILE_KEY not in caplog.text
    assert "authorization=***" in caplog.text or '"authorization":"***"' in caplog.text
    assert '"key":"***"' in caplog.text


def test_http_log_skips_probe_bodies(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "http_log", True)
    with caplog.at_level(logging.INFO, logger="app.http"):
        health = client.get("/health")
        ready = client.get("/ready")
    assert health.status_code == 200
    assert ready.status_code == 200
    assert "http_request" not in caplog.text
    assert '"status":"ok"' not in caplog.text.replace(" ", "")
    assert "fast-staratlas-ai" not in caplog.text


def test_http_log_sse_does_not_record_deltas(
    llm_client: TestClient,
    fake_factory: FakeChatModelFactory,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "http_log", True)
    fake_factory.set_behavior("gpt-mini", stream_chunks=["Hel", "lo"])
    with caplog.at_level(logging.INFO, logger="app.http"):
        response = llm_client.post(STREAM_PATH, json=CHAT_BODY)
    assert response.status_code == 200
    assert "stream=start" in caplog.text
    assert "stream=end" in caplog.text
    assert "Hel" not in caplog.text
    assert "event: delta" not in caplog.text
    assert '"content":"Hel"' not in caplog.text


def test_http_log_truncates_long_body(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "http_log", True)
    long_text = "x" * 5000
    with caplog.at_level(logging.INFO, logger="app.http"):
        response = llm_client.post(
            CHAT_PATH,
            json={"config": "gpt-mini", "messages": [{"role": "user", "content": long_text}]},
        )
    assert response.status_code == 200
    assert TRUNCATION_MARK in caplog.text
    assert long_text not in caplog.text


def test_http_log_independent_of_log_level(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "http_log", True)
    monkeypatch.setattr(settings, "log_level", "ERROR")
    with caplog.at_level(logging.INFO, logger="app.http"):
        response = llm_client.post(CHAT_PATH, json=CHAT_BODY)
    assert response.status_code == 200
    assert "fake-assistant-reply" in caplog.text


def test_domain_error_logs_code_without_http_body(
    llm_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "http_log", False)
    with caplog.at_level(logging.WARNING):
        response = llm_client.post(CHAT_PATH, json={"config": "missing", "messages": [USER_MESSAGE]})
    assert response.status_code == 404
    assert "config_not_found" in caplog.text
    assert "ConfigNotFoundError" in caplog.text
    assert "hello" not in caplog.text
    assert PROFILE_KEY not in caplog.text
    assert "api_key" not in caplog.text


def test_env_example_documents_http_log_and_log_level() -> None:
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "LOG_LEVEL=INFO" in text
    assert "HTTP_LOG=false" in text
    assert "开发" in text and "生产" in text


def test_redact_and_truncate_helpers() -> None:
    payload = {
        "key": "sk-secret",
        "TOKEN": "abc",
        "nested": {"password": "p", "text": "ok"},
        "url": "postgresql+psycopg://staratlas:staratlas@127.0.0.1:5432/db",
    }
    redacted = redact(payload)
    assert redacted["key"] == "***"
    assert redacted["TOKEN"] == "***"
    assert redacted["nested"]["password"] == "***"
    assert redacted["nested"]["text"] == "ok"
    assert redacted["url"] == "***"
    assert truncate("a" * 10, 4) == f"aaaa{TRUNCATION_MARK}"
    assert truncate("short", 10) == "short"
