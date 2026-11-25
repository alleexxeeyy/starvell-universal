from __future__ import annotations

import asyncio
from logging import getLogger
from typing import Any

from pydantic import TypeAdapter

from .._http import Http
from .._limits import RateLimiter
from .._transport import Transport
from ..models import Profile


logger = getLogger("starvellapi")

_adapters: dict[Any, TypeAdapter] = {}


def parse(type_: Any, data: Any) -> Any:
    if data is None:
        return None
    adapter = _adapters.get(type_)
    if adapter is None:
        adapter = _adapters[type_] = TypeAdapter(type_)
    return adapter.validate_python(data)


def drop_none(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


class BaseClient:
    """
    Асинхронный клиент аккаунта Starvell.

    :param session: Значение cookie `session` или строка кук из браузера целиком.
    :type session: `str`

    :param user_agent: Юзер-агент браузера, _опционально_.
    :type user_agent: `str` or `None`

    :param proxy: Прокси `user:pass@ip:port`, `ip:port:user:pass`, `ip:port` или `socks5://...`, _опционально_.
    :type proxy: `str` or `None`

    :param timeout: Таймаут запросов в секундах.
    :type timeout: `float`

    :param transport: Свой транспорт (для тестов или другой HTTP-библиотеки), _опционально_.
    :type transport: `starvellapi.Transport` or `None`
    """

    def __init__(
        self,
        session: str,
        user_agent: str | None = None,
        proxy: str | None = None,
        timeout: float = 30,
        transport: Transport | None = None,
        limiter: RateLimiter | None = None
    ):
        self._http = Http(session, user_agent, proxy, timeout, transport, limiter)
        self._refresh_lock: asyncio.Lock | None = None
        self.me: Profile | None = None

    @property
    def id(self) -> int | None:
        return self.me.id if self.me else None

    @property
    def username(self) -> str | None:
        return self.me.username if self.me else None

    @property
    def session(self) -> str:
        return self._http.session

    @property
    def user_agent(self) -> str:
        return self._http.user_agent

    @property
    def proxy(self) -> str | None:
        return self._http.proxy

    async def __aenter__(self):
        try:
            await self.refresh()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def refresh(self) -> Profile:
        """
        Получает/обновляет профиль аккаунта (`GET /api/profiles/me`).

        :return: Профиль аккаунта.
        :rtype: `starvellapi.models.Profile`
        """

        self.me = await self._request("GET", "/api/profiles/me", type_=Profile)
        return self.me

    async def close(self):
        """
        Закрывает сетевую сессию клиента.
        """
        self._refresh_lock = None
        await self._http.close()

    async def _me_id(self) -> int:
        if self.me is None:
            if self._refresh_lock is None:
                self._refresh_lock = asyncio.Lock()
            async with self._refresh_lock:
                if self.me is None:
                    await self.refresh()
        return self.me.id

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        data: Any = None,
        type_: Any = None,
        key: str | None = None,
        idempotent: bool | None = None
    ) -> Any:
        result = await self._http.request(method, path, json=json, params=params, data=data, idempotent=idempotent)
        if key is not None:
            result = result.get(key) if isinstance(result, dict) else None
        return parse(type_, result) if type_ is not None else result
