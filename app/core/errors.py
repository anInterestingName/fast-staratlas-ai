class AppError(Exception):
    """通用领域错误，由统一异常处理转成 JSON `detail.code`/`detail.message`。"""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
