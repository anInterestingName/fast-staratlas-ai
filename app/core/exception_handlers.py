from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.errors import AppError
from app.schemas.errors import ErrorDetail, ValidationErrorItem

logger = logging.getLogger(__name__)

FIXED_MESSAGES = {
    "validation_error": "请求参数校验失败",
    "not_found": "资源不存在",
    "method_not_allowed": "方法不允许",
    "internal_error": "服务器内部错误",
    "http_error": "请求失败",
}


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


def error_content(
    code: str,
    message: str,
    errors: list[ValidationErrorItem] | None = None,
) -> dict[str, Any]:
    return {"detail": ErrorDetail(code=code, message=message, errors=errors).model_dump(exclude_none=True)}


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    items = [_compact_validation_error(error) for error in exc.errors()]
    return JSONResponse(
        status_code=422,
        content=error_content("validation_error", FIXED_MESSAGES["validation_error"], items),
    )


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    resource = getattr(exc, "config", None) or getattr(exc, "profile", None)
    if resource is not None:
        logger.warning(
            "app_error code=%s status=%s error_type=%s config=%s",
            exc.code,
            exc.status_code,
            type(exc).__name__,
            resource,
        )
    else:
        logger.warning(
            "app_error code=%s status=%s error_type=%s",
            exc.code,
            exc.status_code,
            type(exc).__name__,
        )
    return JSONResponse(status_code=exc.status_code, content=error_content(exc.code, exc.message))


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    if _is_code_message_detail(detail):
        payload = {"code": str(detail["code"]), "message": str(detail["message"])}
        return JSONResponse(status_code=exc.status_code, content={"detail": payload}, headers=exc.headers)
    code, message = _code_for_http_status(exc.status_code)
    return JSONResponse(status_code=exc.status_code, content=error_content(code, message), headers=exc.headers)


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    include_exc_info = settings.debug or settings.log_level == "DEBUG"
    logger.error("unhandled_error error_type=%s", type(exc).__name__, exc_info=include_exc_info)
    return JSONResponse(
        status_code=500,
        content=error_content("internal_error", FIXED_MESSAGES["internal_error"]),
    )


def _compact_validation_error(error: dict[str, Any]) -> ValidationErrorItem:
    loc = [part if isinstance(part, (str, int)) else str(part) for part in error.get("loc", ())]
    return ValidationErrorItem(loc=loc, msg=str(error.get("msg", "")), type=str(error.get("type", "")))


def _is_code_message_detail(detail: object) -> bool:
    return isinstance(detail, dict) and "code" in detail and "message" in detail


def _code_for_http_status(status_code: int) -> tuple[str, str]:
    if status_code == 404:
        return "not_found", FIXED_MESSAGES["not_found"]
    if status_code == 405:
        return "method_not_allowed", FIXED_MESSAGES["method_not_allowed"]
    if status_code == 422:
        return "validation_error", FIXED_MESSAGES["validation_error"]
    return "http_error", FIXED_MESSAGES["http_error"]
