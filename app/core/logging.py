from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import settings

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
MAX_LOG_BODY = 4096
TRUNCATION_MARK = "...<truncated>"
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "token",
        "key",
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "database_url",
    }
)
_CREDENTIAL_URL = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s\"']+@[^\s\"']+")
_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def parse_log_level(name: str) -> int:
    return _LEVELS.get(name.upper(), logging.INFO)


def configure_logging() -> None:
    app_logger = logging.getLogger("app")
    app_logger.setLevel(parse_log_level(settings.log_level))
    # HTTP 访问日志由 HTTP_LOG 独立控制，不随 LOG_LEVEL 静音。
    logging.getLogger("app.http").setLevel(logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT)


def truncate(text: str, limit: int = MAX_LOG_BODY) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}{TRUNCATION_MARK}"


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
                redacted[key] = "***"
            else:
                redacted[key] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(text: str) -> str:
    if _looks_like_connection_string(text):
        return "***"
    return _CREDENTIAL_URL.sub("***", text)


def _looks_like_connection_string(value: str) -> bool:
    lower = value.lower()
    if "://" not in lower:
        return False
    scheme, _, rest = lower.partition("://")
    if "@" in rest:
        return True
    return scheme.startswith(("postgresql", "postgres", "mysql", "mongodb", "redis", "amqp"))
