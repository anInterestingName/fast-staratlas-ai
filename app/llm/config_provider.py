from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.llm.item import LLMConfigItem
from app.llm.models import LLMConfig
from app.llm.store import YamlConfigStore


class LLMConfigProvider(Protocol):
    def list_configs(self) -> list[LLMConfig]: ...

    def get_config(self, name: str) -> LLMConfig | None: ...

    def create_config(self, name: str, item: LLMConfigItem) -> LLMConfig: ...

    def update_config(self, name: str, item: LLMConfigItem) -> LLMConfig: ...

    def delete_config(self, name: str) -> None: ...


class FileLLMConfigProvider:
    def __init__(self, path: Path | None = None) -> None:
        self._store = YamlConfigStore(path or Path(settings.llm_config))

    def list_configs(self) -> list[LLMConfig]:
        return self._store.list_configs()

    def get_config(self, name: str) -> LLMConfig | None:
        return self._store.get_config(name)

    def create_config(self, name: str, item: LLMConfigItem) -> LLMConfig:
        return self._store.create_config(name, item)

    def update_config(self, name: str, item: LLMConfigItem) -> LLMConfig:
        return self._store.update_config(name, item)

    def delete_config(self, name: str) -> None:
        self._store.delete_config(name)
