from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.llm.config_provider import LLMConfigProvider
from app.llm.errors import (
    LLMError,
    LLMUpstreamError,
    LLMValidationError,
    ProfileNotFoundError,
    ProfileNotReadyError,
)
from app.llm.factory import ChatModelFactory
from app.llm.models import LLMProfile
from app.schemas.llm import ChatMessage, TokenUsage

logger = logging.getLogger(__name__)

_ROLE_TO_MESSAGE = {
    "system": SystemMessage,
    "user": HumanMessage,
    "assistant": AIMessage,
}


@dataclass(frozen=True)
class ChatResult:
    profile: str
    content: str
    usage: TokenUsage | None


@dataclass(frozen=True)
class StreamEvent:
    event: str
    data: dict[str, Any]


@dataclass(frozen=True)
class PreparedChat:
    primary: LLMProfile
    chain: list[LLMProfile]
    lc_messages: list[BaseMessage]


class EmptyContentError(Exception):
    """Upstream returned no assistant text."""


class ChatOrchestrator:
    def __init__(self, provider: LLMConfigProvider, factory: ChatModelFactory) -> None:
        self._provider = provider
        self._factory = factory

    def prepare(self, profile_name: str | None, messages: Sequence[ChatMessage]) -> PreparedChat:
        primary = self._resolve_primary(profile_name)
        self._validate_messages(primary, messages)
        return PreparedChat(
            primary=primary,
            chain=self._fallback_chain(primary),
            lc_messages=self._assemble(messages),
        )

    async def chat(self, profile_name: str | None, messages: Sequence[ChatMessage]) -> ChatResult:
        prepared = self.prepare(profile_name, messages)
        error_codes: list[str] = []
        for profile in prepared.chain:
            started = time.perf_counter()
            try:
                model = self._factory.create_chat_model(profile)
                response = await model.ainvoke(prepared.lc_messages)
                content = extract_text(getattr(response, "content", None))
                if not content.strip():
                    raise EmptyContentError
                usage = extract_usage(response)
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "llm_chat_success profile=%s latency_ms=%s usage=%s",
                    profile.name,
                    latency_ms,
                    _usage_log_value(usage),
                )
                return ChatResult(profile=profile.name, content=content, usage=usage)
            except LLMError:
                raise
            except Exception as exc:
                code, message = classify_upstream_error(exc)
                error_codes.append(code)
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.warning(
                    "llm_upstream_failed profile=%s error_code=%s error_type=%s latency_ms=%s",
                    profile.name,
                    code,
                    type(exc).__name__,
                    latency_ms,
                )
                continue
        raise LLMUpstreamError(*_final_upstream_error(error_codes))

    async def chat_stream(self, prepared: PreparedChat) -> AsyncIterator[StreamEvent]:
        error_codes: list[str] = []
        last_message = "上游调用失败"
        for profile in prepared.chain:
            started = time.perf_counter()
            sent_delta = False
            assembled: list[str] = []
            usage: TokenUsage | None = None
            try:
                model = self._factory.create_chat_model(profile)
                async for chunk in model.astream(prepared.lc_messages):
                    usage = extract_usage(chunk) or usage
                    text = chunk.content if isinstance(getattr(chunk, "content", None), str) else ""
                    if not text:
                        continue
                    sent_delta = True
                    assembled.append(text)
                    yield StreamEvent(event="delta", data={"content": text})
                content = "".join(assembled)
                if not content.strip():
                    raise EmptyContentError
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "llm_stream_success profile=%s latency_ms=%s usage=%s",
                    profile.name,
                    latency_ms,
                    _usage_log_value(usage),
                )
                yield StreamEvent(
                    event="done",
                    data={
                        "profile": profile.name,
                        "usage": usage.model_dump() if usage is not None else None,
                    },
                )
                return
            except LLMError:
                raise
            except Exception as exc:
                code, message = classify_upstream_error(exc)
                error_codes.append(code)
                last_message = message
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.warning(
                    "llm_upstream_failed profile=%s error_code=%s error_type=%s latency_ms=%s",
                    profile.name,
                    code,
                    type(exc).__name__,
                    latency_ms,
                )
                if sent_delta:
                    yield StreamEvent(event="error", data={"code": code, "message": message})
                    return
                continue
        code, message = _final_upstream_error(error_codes)
        yield StreamEvent(event="error", data={"code": code, "message": last_message if error_codes else message})

    def _resolve_primary(self, profile_name: str | None) -> LLMProfile:
        name = profile_name or self._provider.get_default_profile_name()
        profile = self._provider.get_profile(name)
        if profile is None:
            raise ProfileNotFoundError(name)
        if not profile.ready:
            raise ProfileNotReadyError(name)
        return profile

    def _fallback_chain(self, primary: LLMProfile) -> list[LLMProfile]:
        chain = [primary]
        seen = {primary.name}
        for name in self._provider.get_fallbacks():
            if name in seen:
                continue
            seen.add(name)
            profile = self._provider.get_profile(name)
            if profile is None or not profile.ready:
                continue
            chain.append(profile)
        return chain

    def _validate_messages(self, profile: LLMProfile, messages: Sequence[ChatMessage]) -> None:
        if len(messages) > profile.max_messages:
            raise LLMValidationError("消息条数超过上限")
        for message in messages:
            if len(message.content) > profile.max_content_length:
                raise LLMValidationError("消息内容长度超过上限")

    def _assemble(self, messages: Sequence[ChatMessage]) -> list[BaseMessage]:
        assembled: list[BaseMessage] = [SystemMessage(content=self._provider.get_system_prompt())]
        for message in messages:
            assembled.append(_ROLE_TO_MESSAGE[message.role](content=message.content))
        return assembled


def extract_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and item.get("type", "text") in {"text", "output_text"}:
                    parts.append(text)
        return "".join(parts)
    return ""


def extract_usage(message: Any) -> TokenUsage | None:
    meta = getattr(message, "usage_metadata", None)
    if not meta:
        return None
    if isinstance(meta, dict):
        prompt = meta.get("input_tokens")
        completion = meta.get("output_tokens")
        total = meta.get("total_tokens")
    else:
        prompt = getattr(meta, "input_tokens", None)
        completion = getattr(meta, "output_tokens", None)
        total = getattr(meta, "total_tokens", None)
    if prompt is None and completion is None and total is None:
        return None
    return TokenUsage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total)


def classify_upstream_error(exc: BaseException) -> tuple[str, str]:
    if isinstance(exc, EmptyContentError):
        return "upstream_failed", "上游返回空内容"
    type_name = type(exc).__name__.lower()
    if isinstance(exc, TimeoutError) or "timeout" in type_name:
        return "upstream_timeout", "上游调用超时"
    return "upstream_failed", "上游调用失败"


def _final_upstream_error(error_codes: list[str]) -> tuple[str, str]:
    if error_codes and all(code == "upstream_timeout" for code in error_codes):
        return "upstream_timeout", "上游调用超时"
    return "upstream_failed", "上游调用失败"


def _usage_log_value(usage: TokenUsage | None) -> dict[str, int | None] | None:
    if usage is None:
        return None
    return usage.model_dump()
