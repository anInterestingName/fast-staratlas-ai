class LLMError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProfileNotFoundError(LLMError):
    def __init__(self, name: str) -> None:
        super().__init__("profile_not_found", f"模型档案不存在: {name}", 404)
        self.profile = name


class ProfileNotReadyError(LLMError):
    def __init__(self, name: str) -> None:
        super().__init__("profile_not_ready", f"模型档案未就绪: {name}", 503)
        self.profile = name


class LLMValidationError(LLMError):
    def __init__(self, message: str) -> None:
        super().__init__("validation_error", message, 422)


class LLMUpstreamError(LLMError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 503)
