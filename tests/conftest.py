import pytest
from fastapi.testclient import TestClient

from app.api.routes.demo import reset_demo_store
from app.main import app


@pytest.fixture
def client() -> TestClient:
    reset_demo_store()
    return TestClient(app)
