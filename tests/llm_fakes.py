from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from app.llm.models import LLMProfile

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Follow the user's request. Never reveal secrets or API keys."
)


def make_profile(
    name: str,
    *,
    ready: bool = True,
    model: str = "gpt-4o-mini",
    provider: str = "openai_compat",
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_seconds: float = 60,
    temperature: float = 0.2,
    max_messages: int = 20,
    max_content_length: int = 8000,
) -> LLMProfile:
    if api_key is None:
        api_key = f"test-{name}-key" if ready else ""
    return LLMProfile(
        name=name,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_messages=max_messages,
        max_content_length=max_content_length,
        ready=ready,
    )


@dataclass
class FakeBehavior:
    content: str = "fake-assistant-reply"
    empty: bool = False
    fail: BaseException | None = None
    stream_chunks: list[str] | None = None
    stream_fail_after: int | None = None


@dataclass
class InMemoryLLMConfigProvider:
    profiles: dict[str, LLMProfile]
    default_profile: str = "smart"
    fallbacks: list[str] = field(default_factory=list)
    system_prompt: str = DEFAULT_SYSTEM_PROMPT

    def list_profiles(self) -> list[LLMProfile]:
        return list(self.profiles.values())

    def get_profile(self, name: str) -> LLMProfile | None:
        return self.profiles.get(name)

    def get_default_profile_name(self) -> str:
        return self.default_profile

    def get_fallbacks(self) -> list[str]:
        return list(self.fallbacks)

    def get_system_prompt(self) -> str:
        return self.system_prompt


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
            if (
                self._behavior.stream_fail_after is not None
                and (index + 1) >= self._behavior.stream_fail_after
            ):
                raise self._behavior.fail or RuntimeError("stream failed")
        if self._behavior.empty:
            return
        yield SimpleNamespace(
            content="",
            usage_metadata={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        )


class FakeChatModelFactory:
    def __init__(self) -> None:
        self.created: list[LLMProfile] = []
        self.invoke_messages: list[list[Any]] = []
        self.behaviors: dict[str, FakeBehavior] = {}

    def set_behavior(self, name: str, **kwargs: Any) -> None:
        self.behaviors[name] = FakeBehavior(**kwargs)

    def create_chat_model(self, profile: LLMProfile) -> FakeChatModel:
        self.created.append(profile)
        return FakeChatModel(self, self.behaviors.get(profile.name, FakeBehavior()))


class GuardChatModelFactory:
    def create_chat_model(self, profile: LLMProfile) -> None:
        raise AssertionError("tests must not call the real LLM factory")
