from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from app.llm.item import LLMConfigItem, to_llm_config
from app.llm.models import LLMConfig


def make_config(
    name: str,
    *,
    ready: bool = True,
    protocol: str = "openai",
    api: str = "chat",
    model: str = "gpt-4o-mini",
    apikey: str | None = None,
    baseurl: str = "https://api.openai.com/v1",
    timeout: float = 60,
    temperature: float = 0.2,
    think: bool = False,
    think_level: str = "medium",
    stream: bool = False,
    size: str | None = None,
    quality: str | None = None,
    n: int | None = None,
    max_messages: int = 20,
    max_length: int = 8000,
) -> LLMConfig:
    if apikey is None:
        apikey = f"test-{name}-key" if ready else ""
    return LLMConfig(
        name=name,
        protocol=protocol,
        api=api,
        baseurl=baseurl,
        apikey=apikey,
        timeout=timeout,
        model=model,
        stream=stream,
        think=think,
        think_level=think_level,
        temperature=temperature,
        size=size,
        quality=quality,
        n=n,
        max_messages=max_messages,
        max_length=max_length,
        ready=ready,
    )


@dataclass
class FakeBehavior:
    content: str = "fake-assistant-reply"
    empty: bool = False
    fail: BaseException | None = None
    stream_chunks: list[str] | None = None
    stream_fail_after: int | None = None
    images: list[dict[str, str | None]] | None = None


@dataclass
class InMemoryLLMConfigProvider:
    configs: dict[str, LLMConfig] = field(default_factory=dict)

    def list_configs(self) -> list[LLMConfig]:
        return list(self.configs.values())

    def get_config(self, name: str) -> LLMConfig | None:
        return self.configs.get(name)

    def create_config(self, name: str, item: LLMConfigItem) -> LLMConfig:
        created = to_llm_config(name, item)
        self.configs[name] = created
        return created

    def update_config(self, name: str, item: LLMConfigItem) -> LLMConfig:
        updated = to_llm_config(name, item)
        self.configs[name] = updated
        return updated

    def delete_config(self, name: str) -> None:
        self.configs.pop(name, None)


class FakeChatModel:
    def __init__(self, factory: "FakeChatModelFactory", behavior: FakeBehavior) -> None:
        self._factory = factory
        self._behavior = behavior

    async def ainvoke(self, messages: Any, **kwargs: Any) -> SimpleNamespace:
        self._factory.invoke_messages.append(list(messages))
        if self._behavior.fail is not None:
            raise self._behavior.fail
        if self._behavior.empty:
            return SimpleNamespace(content="", usage_metadata=None)
        return SimpleNamespace(
            content=self._behavior.content,
            usage_metadata={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        )

    async def astream(self, messages: Any, **kwargs: Any):
        self._factory.invoke_messages.append(list(messages))
        if self._behavior.fail is not None and self._behavior.stream_fail_after is None:
            raise self._behavior.fail
        chunks = self._behavior.stream_chunks
        if chunks is None:
            chunks = [] if self._behavior.empty else [self._behavior.content]
        for index, text in enumerate(chunks):
            yield SimpleNamespace(content=text, usage_metadata=None)
            if self._behavior.stream_fail_after is not None and (index + 1) >= self._behavior.stream_fail_after:
                raise self._behavior.fail or RuntimeError("stream failed")
        if self._behavior.empty:
            return
        yield SimpleNamespace(
            content="",
            usage_metadata={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        )


class FakeChatModelFactory:
    def __init__(self) -> None:
        self.created: list[LLMConfig] = []
        self.invoke_messages: list[list[Any]] = []
        self.behaviors: dict[str, FakeBehavior] = {}

    def set_behavior(self, name: str, **kwargs: Any) -> None:
        self.behaviors[name] = FakeBehavior(**kwargs)

    def clear_cache(self) -> None:
        return None

    def create_chat_model(self, config: LLMConfig) -> FakeChatModel:
        self.created.append(config)
        return FakeChatModel(self, self.behaviors.get(config.name, FakeBehavior()))

    async def generate_image(self, config: LLMConfig, prompt: str) -> list[dict[str, str | None]]:
        self.created.append(config)
        behavior = self.behaviors.get(config.name, FakeBehavior())
        if behavior.fail is not None:
            raise behavior.fail
        if behavior.images is not None:
            return behavior.images
        return [{"b64_json": "ZmFrZQ==", "url": None}]

    async def edit_image(
        self,
        config: LLMConfig,
        prompt: str,
        image: bytes,
        mask: bytes | None = None,
        filename: str = "image.png",
        mask_filename: str = "mask.png",
    ) -> list[dict[str, str | None]]:
        self.created.append(config)
        behavior = self.behaviors.get(config.name, FakeBehavior())
        if behavior.fail is not None:
            raise behavior.fail
        if behavior.images is not None:
            return behavior.images
        return [{"b64_json": "ZWRpdA==", "url": None}]


class GuardChatModelFactory:
    def clear_cache(self) -> None:
        return None

    def create_chat_model(self, config: LLMConfig) -> None:
        raise AssertionError("tests must not call the real LLM factory")

    async def generate_image(self, config: LLMConfig, prompt: str) -> list[dict[str, str | None]]:
        raise AssertionError("tests must not call the real LLM factory")

    async def edit_image(
        self,
        config: LLMConfig,
        prompt: str,
        image: bytes,
        mask: bytes | None = None,
        filename: str = "image.png",
        mask_filename: str = "mask.png",
    ) -> list[dict[str, str | None]]:
        raise AssertionError("tests must not call the real LLM factory")
