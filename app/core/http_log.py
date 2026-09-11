from __future__ import annotations

import json
import logging
from collections.abc import MutableMapping
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.logging import redact, redact_text, truncate

logger = logging.getLogger("app.http")

PROBE_PATHS = frozenset({"/health", "/ready"})
SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "x-api-key"})


class HttpLogMiddleware:
    """纯 ASGI 访问日志中间件，避免 BaseHTTPMiddleware 缓冲 SSE。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "") or ""
        if not settings.http_log or path in PROBE_PATHS:
            await self.app(scope, receive, send)
            return

        messages: list[Message] = []
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.disconnect":
                break
            if message["type"] == "http.request" and not message.get("more_body", False):
                break

        request_body = b"".join(item.get("body", b"") for item in messages if item["type"] == "http.request")
        method = scope.get("method", "")
        query = (scope.get("query_string") or b"").decode("latin-1")
        header_map = _header_map(scope.get("headers") or [])
        request_repr = _body_repr(request_body, header_map.get("content-type", ""))
        header_repr = _sensitive_header_repr(header_map)

        async def replay_receive() -> Message:
            if messages:
                return messages.pop(0)
            return await receive()

        status_code = 0
        content_type = ""
        is_sse = False
        response_chunks: list[bytes] = []
        stream_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, content_type, is_sse, stream_started
            if message["type"] == "http.response.start":
                status_code = int(message.get("status", 0))
                response_headers = _header_map(message.get("headers") or [])
                content_type = response_headers.get("content-type", "")
                is_sse = content_type.startswith("text/event-stream")
                if is_sse and not stream_started:
                    stream_started = True
                    logger.info(
                        "http_request method=%s path=%s query=%s request=%s headers=%s status=%s stream=start",
                        method,
                        path,
                        query,
                        request_repr,
                        header_repr,
                        status_code,
                    )
            elif message["type"] == "http.response.body" and not is_sse:
                response_chunks.append(message.get("body", b"") or b"")
            await send(message)

        try:
            await self.app(scope, replay_receive, send_wrapper)
        except Exception:
            if is_sse:
                logger.info(
                    "http_request method=%s path=%s query=%s request=%s headers=%s status=%s stream=error",
                    method,
                    path,
                    query,
                    request_repr,
                    header_repr,
                    status_code,
                )
            raise

        if is_sse:
            logger.info(
                "http_request method=%s path=%s query=%s request=%s headers=%s status=%s stream=end",
                method,
                path,
                query,
                request_repr,
                header_repr,
                status_code,
            )
            return

        response_repr = _body_repr(b"".join(response_chunks), content_type)
        logger.info(
            "http_request method=%s path=%s query=%s request=%s headers=%s status=%s response=%s",
            method,
            path,
            query,
            request_repr,
            header_repr,
            status_code,
            response_repr,
        )


def _header_map(headers: list[tuple[bytes, bytes]] | list[Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_key, raw_value in headers:
        key = raw_key.decode("latin-1").lower() if isinstance(raw_key, (bytes, bytearray)) else str(raw_key).lower()
        value = raw_value.decode("latin-1") if isinstance(raw_value, (bytes, bytearray)) else str(raw_value)
        result[key] = value
    return result


def _sensitive_header_repr(headers: MutableMapping[str, str]) -> str:
    present = {name: "***" for name in SENSITIVE_HEADERS if name in headers}
    return _dump(present)


def _body_repr(body: bytes, content_type: str) -> str:
    if not body:
        return ""
    text = body.decode("utf-8", errors="replace")
    lowered = content_type.lower()
    if "json" in lowered or text[:1] in "{[":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return truncate(redact_text(text))
        return truncate(_dump(redact(parsed)))
    return truncate(redact_text(text))


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
