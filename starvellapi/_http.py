from __future__ import annotations

import asyncio
import random
import time
from logging import getLogger
from typing import Any
from urllib.parse import quote

from ._limits import RateLimiter, group_of
from ._transport import AiohttpTransport, Response, Transport, TransportError
from .errors import (
    APIError,
    BotCheckError,
    CooldownError,
    HTTPError,
    NetworkError,
    RateLimitError,
    TwoFactorRequiredError,
    UnauthorizedError,
)


logger = getLogger("starvellapi")

BASE_URL = "https://starvell.com"
SOCKET_URL = "wss://starvell.com:8443/socket.io/?EIO=4&transport=websocket"

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

UNAUTHORIZED_CODES = {"SESSION_NOT_FOUND", "ACCESS_COOKIE_MISSING", "SESSION_EXPIRED", "UNAUTHORIZED"}
TWO_FACTOR_CODES = {"TWOFA_CODE_IS_REQUIRED"}
COOLDOWN_CODES = {"OFFERS_BUMP_COOLDOWN"}
RETRY_STATUSES = {502, 503, 504}
MAX_RETRY_AFTER = 300.0

_sleep = asyncio.sleep
_now = time.monotonic


def parse_session(value: str) -> str:
    value = (value or "").strip()
    if "session=" not in value and ";" not in value:
        return value
    for part in value.split(";"):
        key, _, val = part.strip().partition("=")
        if key == "session":
            return val.strip()
    return ""


def path_id(value: Any) -> str:
    # id из данных покупателя не должен менять путь запроса
    return quote(str(value), safe="")


class Http:
    def __init__(
        self,
        session: str,
        user_agent: str | None = None,
        proxy: str | None = None,
        timeout: float = 30,
        transport: Transport | None = None,
        limiter: RateLimiter | None = None,
        retries: int = 3,
        rate_limit_retries: int = 5,
        max_wait: float = 90
    ):
        self.session = parse_session(session)
        if not self.session:
            raise TypeError("Нужна session: значение cookie session или строка кук целиком")
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.proxy = proxy
        self.timeout = timeout
        self.transport: Transport = transport or AiohttpTransport(proxy=proxy, timeout=timeout)
        self.limiter = limiter or RateLimiter()
        self.retries = max(1, retries)
        self.rate_limit_retries = max(1, rate_limit_retries)
        # сколько максимум ждать на лимитах один запрос: дальше RateLimitError, а не минуты тишины
        self.max_wait = max_wait
        self._pause_until: dict[str, float] = {}

    @property
    def headers(self) -> dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "cookie": f"session={self.session}",
            "origin": BASE_URL,
            "referer": f"{BASE_URL}/",
            "user-agent": self.user_agent,
        }

    @property
    def socket_headers(self) -> dict[str, str]:
        return {"cookie": f"session={self.session}", "origin": BASE_URL, "user-agent": self.user_agent}

    async def _send(self, method: str, url: str, idempotent: bool, data: Any, **kwargs) -> Response:
        error = ""
        for attempt in range(self.retries):
            try:
                # одноразовые тела (multipart) собираются заново на каждую попытку
                body = data() if callable(data) else data
                return await self.transport.request(method, url, headers=self.headers, data=body, **kwargs)
            except TransportError as e:
                error = e.error
                if e.sent and not idempotent:
                    raise NetworkError(url, error, maybe_delivered=True) from e
                logger.debug(f"{method} {url}: {error}, попытка {attempt + 1}/{self.retries}")
                if attempt < self.retries - 1:
                    await _sleep(min(2 ** attempt, 5))
        raise NetworkError(url, error)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        idempotent: bool | None = None
    ) -> Any:
        if not path.startswith("/"):
            raise ValueError("Путь запроса должен начинаться с / - на чужой хост сессия не отправляется")
        url = f"{BASE_URL}{path}"
        group = group_of(path)
        if idempotent is None:
            idempotent = method == "GET"
        if method != "GET" and json is None and data is None:
            # Starvell отклоняет пустое тело при Content-Type: application/json
            json = {}

        deadline = _now() + self.max_wait
        for attempt in range(self.rate_limit_retries):
            pause = self._pause_until.get(group, 0) - _now()
            if pause > 0:
                if _now() + pause > deadline:
                    raise RateLimitError(url, 429, "Starvell ограничил запросы, попробуйте позже", data={"retryAfterSeconds": pause})
                await _sleep(pause)
            await self.limiter.acquire(path)
            resp = await self._send(method, url, idempotent, data, params=params, json=json)

            if resp.status == 429:
                body = _safe_json(resp)
                if _is_cooldown(_error_code(body)):
                    # кулдаун (например, поднятие лотов) - это ответ «рано», а не перегрузка, повторять нельзя
                    raise _api_error(url, resp, body)
                delay = _retry_delay(resp, attempt, body)
                self._pause_until[group] = max(self._pause_until.get(group, 0), _now() + delay)
                if attempt < self.rate_limit_retries - 1 and _now() + delay <= deadline:
                    logger.debug(f"{url}: 429, следующая попытка через {delay:.1f} сек.")
                    continue
                raise RateLimitError(url, 429, "Слишком много запросов к Starvell", data={"retryAfterSeconds": delay})

            if resp.status in RETRY_STATUSES and idempotent and attempt < self.rate_limit_retries - 1:
                delay = _retry_delay(resp, attempt)
                if _now() + delay <= deadline:
                    logger.debug(f"{url}: {resp.status}, следующая попытка через {delay:.1f} сек.")
                    await _sleep(delay)
                    continue
            return self._handle(url, resp, idempotent)

        raise RateLimitError(url, 429, "Слишком много запросов к Starvell")

    def _handle(self, url: str, resp: Response, idempotent: bool) -> Any:
        if not resp.is_json:
            # QRATOR стоит в server у всех ответов, поэтому защиту узнаём по HTML вместо JSON
            if resp.status in (401, 403) or 200 <= resp.status < 300 and "html" in resp.headers.get("content-type", ""):
                raise BotCheckError(url, resp.status)
            if 200 <= resp.status < 300:
                return resp.text or None
            raise HTTPError(url, resp.status, resp.text, maybe_delivered=not idempotent and resp.status >= 500)

        try:
            body = resp.json()
        except ValueError:
            raise HTTPError(url, resp.status, resp.text, maybe_delivered=not idempotent) from None
        if 200 <= resp.status < 300:
            return body
        raise _api_error(url, resp, body)

    async def close(self):
        await self.transport.close()


def _safe_json(resp: Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return None


def _error_code(body: Any) -> str | None:
    if isinstance(body, dict) and isinstance(body.get("data"), dict):
        code = body["data"].get("code")
        return code if isinstance(code, str) else None
    return None


def _is_cooldown(code: str | None) -> bool:
    return bool(code) and (code in COOLDOWN_CODES or code.endswith("_COOLDOWN"))


def _api_error(url: str, resp: Response, body: Any) -> APIError:
    message = body.get("message") if isinstance(body, dict) else None
    if isinstance(message, list):
        message = "; ".join(str(m) for m in message)
    message = str(message or f"Ошибка Starvell, код ответа {resp.status}")
    data = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), dict) else {}
    code = _error_code(body)
    if code in TWO_FACTOR_CODES:
        return TwoFactorRequiredError(url, resp.status, message, code, data)
    if code in UNAUTHORIZED_CODES or resp.status == 401:
        return UnauthorizedError(url, resp.status, message, code, data)
    if _is_cooldown(code):
        return CooldownError(url, resp.status, message, code, data)
    if resp.status == 429:
        return RateLimitError(url, resp.status, message, code, data)
    return APIError(url, resp.status, message, code, data)


def _retry_delay(resp: Response, attempt: int, body: Any = None) -> float:
    if isinstance(body, dict) and isinstance(body.get("data"), dict):
        seconds = body["data"].get("retryAfterSeconds")
        if isinstance(seconds, (int, float)) and seconds > 0:
            return min(float(seconds), MAX_RETRY_AFTER) + random.uniform(0.2, 0.8)
    value = resp.headers.get("retry-after")
    if value:
        try:
            return min(max(float(value), 0.5), MAX_RETRY_AFTER) + random.uniform(0.2, 0.8)
        except ValueError:
            pass
    return min(5 * 2 ** attempt, 120) + random.uniform(0.2, 0.8)
