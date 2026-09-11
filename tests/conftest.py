from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.llm.config_provider import FileLLMConfigProvider
from app.llm.deps import get_chat_model_factory, get_config_provider
from app.main import app
from tests.llm_fakes import GuardChatModelFactory


class FakeSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        return None

    def close(self) -> None:
        return None


def _ok_session() -> Iterator[FakeSession]:
    yield FakeSession()


@pytest.fixture(autouse=True)
def file_config_provider(tmp_path: Path) -> Iterator[FileLLMConfigProvider]:
    provider = FileLLMConfigProvider(tmp_path / "llm.yaml")
    app.dependency_overrides[get_config_provider] = lambda: provider
    app.dependency_overrides[get_chat_model_factory] = lambda: GuardChatModelFactory()
    app.dependency_overrides[get_session] = _ok_session
    yield provider
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
