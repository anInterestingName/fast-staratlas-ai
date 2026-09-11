import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, settings
from app.db.session import get_session
from app.main import app

CHAT_PATH = "/api/v1/llm/chat"


class FailingSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("unavailable"))

    def close(self) -> None:
        return None


def _failing_session() -> Iterator[FailingSession]:
    yield FailingSession()


@contextmanager
def temporary_route(path: str, endpoint: object, methods: list[str] | None = None) -> Iterator[None]:
    route = APIRoute(path, endpoint, methods=methods or ["GET"])
    app.router.routes.append(route)
    try:
        yield
    finally:
        app.router.routes.remove(route)


def assert_error_detail(body: object, *, code: str, message: str | None = None) -> dict[str, object]:
    assert isinstance(body, dict)
    detail = body["detail"]
    assert isinstance(detail, dict)
    assert detail["code"] == code
    assert isinstance(detail["message"], str)
    assert detail["message"]
    if message is not None:
        assert detail["message"] == message
    return detail


def test_missing_messages_returns_validation_object(client: TestClient) -> None:
    response = client.post(CHAT_PATH, json={})
    assert response.status_code == 422
    detail = assert_error_detail(response.json(), code="validation_error", message="请求参数校验失败")
    assert isinstance(detail.get("errors"), list)
    assert detail["errors"]
    assert "loc" in detail["errors"][0]
    assert "msg" in detail["errors"][0]
    assert "type" in detail["errors"][0]


def test_unregistered_path_returns_not_found_object(client: TestClient) -> None:
    response = client.get("/this-path-does-not-exist")
    assert response.status_code == 404
    assert_error_detail(response.json(), code="not_found", message="资源不存在")


def test_method_not_allowed_returns_object(client: TestClient) -> None:
    response = client.get(CHAT_PATH)
    assert response.status_code == 405
    assert_error_detail(response.json(), code="method_not_allowed", message="方法不允许")


def test_unhandled_exception_returns_internal_error(caplog: pytest.LogCaptureFixture) -> None:
    def boom() -> None:
        raise RuntimeError("secret")

    with (
        temporary_route("/__test/boom", boom),
        TestClient(app, raise_server_exceptions=False) as client,
        caplog.at_level(logging.ERROR, logger="app.core.exception_handlers"),
    ):
        response = client.get("/__test/boom")
    assert response.status_code == 500
    assert_error_detail(response.json(), code="internal_error", message="服务器内部错误")
    text = response.text
    assert "secret" not in text
    assert "Traceback" not in text
    assert "RuntimeError" not in text
    assert "internal_error" in response.text
    assert "RuntimeError" in caplog.text
    assert "secret" not in response.json()["detail"]["message"]


def test_unhandled_exception_debug_still_hides_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "debug", True)

    def boom() -> None:
        raise RuntimeError("secret")

    with temporary_route("/__test/boom-debug", boom), TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test/boom-debug")
    assert response.status_code == 500
    assert_error_detail(response.json(), code="internal_error", message="服务器内部错误")
    assert "secret" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_ready_failure_keeps_probe_model(client: TestClient) -> None:
    app.dependency_overrides[get_session] = _failing_session
    response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["database"] == "unavailable"
    assert "detail" not in body
    assert "code" not in body


def test_health_and_root_keep_success_shape(client: TestClient) -> None:
    health = client.get("/health")
    assert health.status_code == 200
    health_body = health.json()
    assert health_body["status"] == "ok"
    assert "data" not in health_body
    assert "code" not in health_body
    root = client.get("/")
    assert root.status_code == 200
    assert root.json() == {"message": "Hello World", "docs": "/docs"}


def test_log_level_and_http_log_defaults() -> None:
    assert Settings.model_fields["log_level"].default == "INFO"
    assert Settings.model_fields["http_log"].default is False
    assert settings.http_log is False or isinstance(settings.http_log, bool)


def test_ruff_is_the_only_style_tool() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "ruff>=" in text or "ruff==" in text
    assert "[tool.ruff]" in text
    assert '"black' not in text
    assert '"flake8' not in text
    assert '"isort' not in text
