from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.routes.demo import reset_demo_store
from app.llm.deps import get_chat_model_factory
from app.main import app
from tests.llm_fakes import GuardChatModelFactory


@pytest.fixture(autouse=True)
def _guard_real_llm_factory() -> Iterator[None]:
    app.dependency_overrides[get_chat_model_factory] = lambda: GuardChatModelFactory()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    reset_demo_store()
    with TestClient(app) as test_client:
        yield test_client
