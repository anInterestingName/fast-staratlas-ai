from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.llm.config_provider import LLMConfigProvider
from app.llm.errors import (
    ApiMismatchError,
    ConfigNotFoundError,
    ConfigNotReadyError,
    LLMError,
    LLMUpstreamError,
    LLMValidationError,
    ProtocolNotSupportedError,
)
from app.llm.factory import ChatModelFactory
from app.llm.models import TEXT_APIS, LLMConfig
from app.schemas.llm import ChatMessage, TokenUsage

logger = logging.getLogger(__name__)

_ROLE_TO_MESSAGE = {
    "system": SystemMessage,
    "user": HumanMessage,
    "assistant": AIMessage,
}


@dataclass(frozen=True)
class ChatResult:
    config: str
    content: str
    usage: TokenUsage | None


@dataclass(frozen=True)
class StreamEvent:
    event: str
    data: dict[str, Any]


@dataclass(frozen=True)
class PreparedChat:
    primary: LLMConfig
    chain: list[LLMConfig]
    lc_messages: list[BaseMessage]


@dataclass(frozen=True)
class ImageResult:
    config: str
    images: list[dict[str, str | None]]


class EmptyContentError(Exception):
    """Upstream returned no assistant text."""


class ChatOrchestrator:
    def __init__(self, provider: LLMConfigProvider, factory: ChatModelFactory) -> None:
        self._provider = provider
        self._factory = factory

    def prepare(
        self,
        config_name: str,
        fallback_name: str | None,
        messages: Sequence[ChatMessage],
    ) -> PreparedChat:
        primary = self._resolve_primary(config_name)
        self._assert_api(primary, TEXT_APIS, "当前配置不是对话接口")
        self._validate_messages(primary, messages)
        return PreparedChat(
            primary=primary,
            chain=self._fallback_chain(primary, fallback_name, TEXT_APIS),
            lc_messages=self._assemble(messages),
        )

    async def chat(self, config_name: str, fallback_name: str | None, messages: Sequence[ChatMessage]) -> ChatResult:
        prepared = self.prepare(config_name, fallback_name, messages)
        return await self.chat_prepared(prepared)

    async def chat_prepared(self, prepared: PreparedChat) -> ChatResult:
        error_codes: list[str] = []
        last_protocol: ProtocolNotSupportedError | None = None
        for config in prepared.chain:
            started = time.perf_counter()
            try:
                model = self._factory.create_chat_model(config)
                response = await model.ainvoke(prepared.lc_messages)
                content = extract_text(getattr(response, "content", None))
                if not content.strip():
                    raise EmptyContentError
                usage = extract_usage(response)
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "llm_chat_success config=%s latency_ms=%s usage=%s",
                    config.name,
                    latency_ms,
                    _usage_log_value(usage),
                )
                return ChatResult(config=config.name, content=content, usage=usage)
            except ProtocolNotSupportedError as exc:
                last_protocol = exc
                error_codes.append(exc.code)
                continue
            except LLMError:
                raise
            except Exception as exc:
                code, _message = classify_upstream_error(exc)
                error_codes.append(code)
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.warning(
                    "llm_upstream_failed config=%s error_code=%s error_type=%s latency_ms=%s",
                    config.name,
                    code,
                    type(exc).__name__,
                    latency_ms,
                )
                continue
        if last_protocol is not None and all(code == "protocol_not_supported" for code in error_codes):
            raise last_protocol
        raise LLMUpstreamError(*_final_upstream_error(error_codes))

    async def chat_stream(self, prepared: PreparedChat) -> AsyncIterator[StreamEvent]:
        error_codes: list[str] = []
        last_message = "上游调用失败"
        for config in prepared.chain:
            started = time.perf_counter()
            sent_delta = False
            assembled: list[str] = []
            usage: TokenUsage | None = None
            try:
                model = self._factory.create_chat_model(config)
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
                    "llm_stream_success config=%s latency_ms=%s usage=%s",
                    config.name,
                    latency_ms,
                    _usage_log_value(usage),
                )
                yield StreamEvent(
                    event="done",
                    data={
                        "config": config.name,
                        "usage": usage.model_dump() if usage is not None else None,
                    },
                )
                return
            except ProtocolNotSupportedError as exc:
                error_codes.append(exc.code)
                last_message = exc.message
                continue
            except LLMError:
                raise
            except Exception as exc:
                code, message = classify_upstream_error(exc)
                error_codes.append(code)
                last_message = message
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.warning(
                    "llm_upstream_failed config=%s error_code=%s error_type=%s latency_ms=%s",
                    config.name,
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

    async def generate_image(self, config_name: str, fallback_name: str | None, prompt: str) -> ImageResult:
        primary = self._resolve_primary(config_name)
        self._assert_api(primary, {"image.generate"}, "当前配置不是图像生成接口")
        self._validate_prompt(primary, prompt)
        chain = self._fallback_chain(primary, fallback_name, {"image.generate"})
        return await self._run_image(chain, lambda cfg: self._factory.generate_image(cfg, prompt))

    async def edit_image(
        self,
        config_name: str,
        fallback_name: str | None,
        prompt: str,
        image: bytes,
        mask: bytes | None,
        filename: str,
        mask_filename: str,
    ) -> ImageResult:
        primary = self._resolve_primary(config_name)
        self._assert_api(primary, {"image.edit"}, "当前配置不是图像编辑接口")
        self._validate_prompt(primary, prompt)
        if not image:
            raise LLMValidationError("图像文件不能为空")
        chain = self._fallback_chain(primary, fallback_name, {"image.edit"})
        return await self._run_image(
            chain,
            lambda cfg: self._factory.edit_image(cfg, prompt, image, mask, filename, mask_filename),
        )

    async def _run_image(self, chain: list[LLMConfig], invoker: Any) -> ImageResult:
        error_codes: list[str] = []
        last_protocol: ProtocolNotSupportedError | None = None
        for config in chain:
            started = time.perf_counter()
            try:
                images = await invoker(config)
                if not images:
                    raise EmptyContentError
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.info("llm_image_success config=%s latency_ms=%s", config.name, latency_ms)
                return ImageResult(config=config.name, images=images)
            except ProtocolNotSupportedError as exc:
                error_codes.append(exc.code)
                last_protocol = exc
                continue
            except LLMError:
                raise
            except Exception as exc:
                code, _message = classify_upstream_error(exc)
                error_codes.append(code)
                latency_ms = int((time.perf_counter() - started) * 1000)
                logger.warning(
                    "llm_upstream_failed config=%s error_code=%s error_type=%s latency_ms=%s",
                    config.name,
                    code,
                    type(exc).__name__,
                    latency_ms,
                )
                continue
        if last_protocol is not None and all(code == "protocol_not_supported" for code in error_codes):
            raise last_protocol
        raise LLMUpstreamError(*_final_upstream_error(error_codes))

    def _resolve_primary(self, name: str) -> LLMConfig:
        config = self._provider.get_config(name)
        if config is None:
            raise ConfigNotFoundError(name)
        if not config.ready:
            raise ConfigNotReadyError(name)
        return config

    def _fallback_chain(self, primary: LLMConfig, fallback_name: str | None, allowed: set[str]) -> list[LLMConfig]:
        chain = [primary]
        if not fallback_name or fallback_name == primary.name:
            return chain
        fallback = self._provider.get_config(fallback_name)
        if fallback is None:
            raise ConfigNotFoundError(fallback_name)
        self._assert_api(fallback, allowed, "备用配置接口类型不匹配")
        if fallback.api != primary.api and not (primary.api in TEXT_APIS and fallback.api in TEXT_APIS):
            raise ApiMismatchError("主配置与备用配置的 api 必须同类")
        if fallback.ready:
            chain.append(fallback)
        return chain

    def _assert_api(self, config: LLMConfig, allowed: set[str], message: str) -> None:
        if config.api not in allowed:
            raise ApiMismatchError(message)

    def _validate_messages(self, config: LLMConfig, messages: Sequence[ChatMessage]) -> None:
        if len(messages) > config.max_messages:
            raise LLMValidationError("消息条数超过上限")
        for message in messages:
            if len(message.content) > config.max_length:
                raise LLMValidationError("消息内容长度超过上限")

    def _validate_prompt(self, config: LLMConfig, prompt: str) -> None:
        stripped = prompt.strip()
        if not stripped:
            raise LLMValidationError("prompt 不能为空")
        if len(stripped) > config.max_length:
            raise LLMValidationError("prompt 长度超过上限")

    def _assemble(self, messages: Sequence[ChatMessage]) -> list[BaseMessage]:
        return [_ROLE_TO_MESSAGE[message.role](content=message.content) for message in messages]


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
