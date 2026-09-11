from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMProfile:
    name: str
    provider: str
    model: str
    base_url: str | None
    api_key: str = field(repr=False)
    timeout_seconds: float
    temperature: float
    max_messages: int
    max_content_length: int
    ready: bool
