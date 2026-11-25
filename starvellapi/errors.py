from __future__ import annotations

from typing import Any


class StarvellError(Exception):
    pass


class NetworkError(StarvellError):
    def __init__(self, url: str, error: str):
        self.url = url
        self.error = error
        super().__init__(f"Не удалось отправить запрос к {url}: {error}")


class BotCheckError(StarvellError):
    def __init__(self, url: str, status_code: int):
        self.url = url
        self.status_code = status_code
        super().__init__(
            f"Защита Starvell (QRATOR) не пропустила запрос к {url}, код {status_code}. "
            "Проверьте IP/прокси и User-Agent или повторите позже"
        )


class HTTPError(StarvellError):
    def __init__(self, url: str, status_code: int, text: str):
        self.url = url
        self.status_code = status_code
        self.text = text
        super().__init__(f"Ошибка запроса к {url}, код ответа {status_code}: {text[:500]}")


class APIError(StarvellError):
    def __init__(self, url: str, status_code: int, message: str, code: str | None = None, data: dict[str, Any] | None = None):
        self.url = url
        self.status_code = status_code
        self.message = message
        self.code = code
        self.data = data or {}
        super().__init__(f"{message} ({code})" if code else message)

    @property
    def retry_after(self) -> float | None:
        value = self.data.get("retryAfterSeconds")
        return float(value) if isinstance(value, (int, float)) else None


class UnauthorizedError(APIError):
    def __init__(self, url: str = "", status_code: int = 403, message: str = "", code: str | None = None, data: dict[str, Any] | None = None):
        super().__init__(url, status_code, message or "Сессия Starvell недействительна, обновите session", code, data)


class TwoFactorRequiredError(UnauthorizedError):
    pass


class RateLimitError(APIError):
    pass


class CooldownError(APIError):
    pass
