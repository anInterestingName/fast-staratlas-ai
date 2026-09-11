from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.llm.errors import ConfigExistsError, ConfigInvalidError, ConfigNotFoundError, LLMValidationError
from app.llm.item import CONFIG_NAME_PATTERN, LLMConfigItem, to_llm_config
from app.llm.models import LLMConfig

_NAME_RE = re.compile(CONFIG_NAME_PATTERN)


def validate_config_name(name: str) -> str:
    if not _NAME_RE.match(name):
        raise LLMValidationError("配置名必须以字母开头，仅含字母数字下划线和连字符，最长 64")
    return name


class YamlConfigStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def list_configs(self) -> list[LLMConfig]:
        with self._lock:
            return [to_llm_config(name, item) for name, item in self._load().items()]

    def get_config(self, name: str) -> LLMConfig | None:
        with self._lock:
            item = self._load().get(name)
            if item is None:
                return None
            return to_llm_config(name, item)

    def create_config(self, name: str, item: LLMConfigItem) -> LLMConfig:
        name = validate_config_name(name)
        with self._lock:
            data = self._load()
            if name in data:
                raise ConfigExistsError(name)
            data[name] = item
            self._dump(data)
            return to_llm_config(name, item)

    def update_config(self, name: str, item: LLMConfigItem) -> LLMConfig:
        with self._lock:
            data = self._load()
            current = data.get(name)
            if current is None:
                raise ConfigNotFoundError(name)
            incoming = item.model_dump(exclude_none=True)
            if item.apikey is None:
                incoming["apikey"] = current.apikey
            else:
                incoming["apikey"] = item.apikey
            merged = {**current.model_dump(), **incoming}
            data[name] = LLMConfigItem.model_validate(merged)
            self._dump(data)
            return to_llm_config(name, data[name])

    def delete_config(self, name: str) -> None:
        with self._lock:
            data = self._load()
            if name not in data:
                raise ConfigNotFoundError(name)
            del data[name]
            self._dump(data)

    def _load(self) -> dict[str, LLMConfigItem]:
        if not self._path.exists():
            return {}
        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigInvalidError("无法读取 LLM 配置文件") from exc
        if not isinstance(raw, dict):
            raise ConfigInvalidError("LLM 配置文件根必须是对象")
        configs = raw.get("configs", raw)
        if not isinstance(configs, dict):
            raise ConfigInvalidError("configs 必须是对象")
        parsed: dict[str, LLMConfigItem] = {}
        for name, value in configs.items():
            if not isinstance(name, str) or not _NAME_RE.match(name):
                raise ConfigInvalidError(f"非法配置名: {name}")
            if not isinstance(value, dict):
                raise ConfigInvalidError(f"配置 {name} 必须是对象")
            try:
                parsed[name] = LLMConfigItem.model_validate(value)
            except ValidationError as exc:
                raise ConfigInvalidError(f"配置 {name} 不合法") from exc
        return parsed

    def _dump(self, data: dict[str, LLMConfigItem]) -> None:
        payload: dict[str, Any] = {"configs": {name: _dump_item(item) for name, item in data.items()}}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        tmp.replace(self._path)


def _dump_item(item: LLMConfigItem) -> dict[str, Any]:
    payload = item.model_dump(exclude_none=True)
    payload["apikey"] = item.apikey or ""
    return payload
