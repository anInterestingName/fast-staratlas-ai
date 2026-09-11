from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.db.session import get_session
from app.main import app


class FailingSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("unavailable"))

    def close(self) -> None:
        return None


def _failing_session() -> Iterator[FailingSession]:
    yield FailingSession()


def test_settings_has_database_url() -> None:
    assert settings.database_url.startswith("postgresql")


def test_ready_ok(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["app"] == settings.app_name
    assert body["version"] == settings.app_version
    assert "postgresql" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "api_key" not in body


def test_ready_unavailable_does_not_leak_dsn(client: TestClient) -> None:
    app.dependency_overrides[get_session] = _failing_session
    response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["database"] == "unavailable"
    dumped = str(body).lower()
    assert "postgresql+" not in dumped
    assert "password" not in dumped
    assert "api_key" not in body
    assert settings.database_url not in str(body)


def test_health_ok_when_database_unavailable(client: TestClient) -> None:
    app.dependency_overrides[get_session] = _failing_session
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "database" not in body


def test_demo_routes_removed(client: TestClient) -> None:
    listed = client.get("/api/v1/demo")
    assert listed.status_code == 404
    created = client.post("/api/v1/demo", json={"name": "nebula", "message": "should not exist"})
    assert created.status_code == 404
    assert created.status_code != 201
    with pytest.raises(ModuleNotFoundError):
        import app.api.routes.demo  # noqa: F401


def test_no_business_sql_scripts() -> None:
    sql_dir = Path("doc/sql")
    if sql_dir.exists():
        assert list(sql_dir.glob("**/*.sql")) == []
    assert not Path("app/db/models").exists()
