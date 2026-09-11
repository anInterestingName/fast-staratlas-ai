from dataclasses import dataclass, field
from typing import Literal

ProtocolType = Literal["openai", "anthropic"]
ApiType = Literal["chat", "responses", "image.generate", "image.edit"]
ThinkLevel = Literal["none", "minimal", "low", "medium", "high", "xhigh"]

TEXT_APIS = frozenset({"chat", "responses"})
IMAGE_APIS = frozenset({"image.generate", "image.edit"})
SUPPORTED_PROTOCOL = "openai"


@dataclass(frozen=True)
class LLMConfig:
    name: str
    protocol: str
    api: str
    baseurl: str
    apikey: str = field(repr=False)
    timeout: float
    model: str
    stream: bool
    think: bool
    think_level: str
    temperature: float
    size: str | None
    quality: str | None
    n: int | None
    max_messages: int
    max_length: int
    ready: bool

    @property
    def has_key(self) -> bool:
        return bool(self.apikey.strip())
