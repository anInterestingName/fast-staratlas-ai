from app.core.errors import AppError


class LLMError(AppError):
    """LLM 领域错误。"""

    def __init__(self, code: str, message: str, status_code: int, config: str | None = None) -> None:
        super().__init__(code, message, status_code)
        self.config = config
        self.profile = config


class ConfigNotFoundError(LLMError):
    def __init__(self, name: str) -> None:
        super().__init__("config_not_found", f"模型配置不存在: {name}", 404, name)


class ConfigNotReadyError(LLMError):
    def __init__(self, name: str) -> None:
        super().__init__("config_not_ready", f"模型配置未就绪: {name}", 503, name)


class ConfigExistsError(LLMError):
    def __init__(self, name: str) -> None:
        super().__init__("config_exists", f"模型配置已存在: {name}", 409, name)


class ConfigInvalidError(LLMError):
    def __init__(self, message: str) -> None:
        super().__init__("config_invalid", message, 500)


class ApiMismatchError(LLMError):
    def __init__(self, message: str) -> None:
        super().__init__("api_mismatch", message, 422)


class ProtocolNotSupportedError(LLMError):
    def __init__(self, name: str, protocol: str) -> None:
        super().__init__("protocol_not_supported", f"协议暂不支持调用: {protocol}", 503, name)


class LLMValidationError(LLMError):
    def __init__(self, message: str) -> None:
        super().__init__("validation_error", message, 422)


class LLMUpstreamError(LLMError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 503)
