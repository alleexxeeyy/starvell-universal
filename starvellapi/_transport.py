from __future__ import annotations

import asyncio
import json as _json
import ssl
from dataclasses import dataclass, field
from typing import Any, Protocol

import aiohttp
import certifi


class TransportError(Exception):
    def __init__(self, error: str, sent: bool):
        self.error = error
        # sent=False - запрос точно не ушёл на сервер, его можно повторить даже для изменяющих методов
        self.sent = sent
        super().__init__(error)


class WebSocketClosed(Exception):
    pass


@dataclass
class Response:
    status: int
    text: str
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def is_json(self) -> bool:
        return "json" in self.headers.get("content-type", "")

    def json(self) -> Any:
        return _json.loads(self.text) if self.text else None


class WebSocket(Protocol):
    async def send(self, data: str): ...

    async def receive(self, timeout: float | None = None) -> str: ...

    async def close(self): ...


class Transport(Protocol):
    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        timeout: float | None = None
    ) -> Response: ...

    async def ws_connect(self, url: str, *, headers: dict[str, str] | None = None, timeout: float | None = None) -> WebSocket: ...

    async def close(self): ...


def make_proxy_url(proxy: str | None) -> str | None:
    if not proxy:
        return None
    proxy = proxy.strip()
    if "://" in proxy:
        return proxy
    parts = proxy.split(":")
    # ip:port:user:pass → user:pass@ip:port
    if "@" not in proxy and len(parts) == 4:
        proxy = f"{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return f"http://{proxy}"


class _AiohttpWebSocket:
    def __init__(self, ws: aiohttp.ClientWebSocketResponse):
        self._ws = ws

    async def send(self, data: str):
        try:
            await self._ws.send_str(data)
        except (aiohttp.ClientError, ConnectionError, RuntimeError) as e:
            raise WebSocketClosed(str(e)) from e

    async def receive(self, timeout: float | None = None) -> str:
        msg = await self._ws.receive(timeout=timeout)
        if msg.type == aiohttp.WSMsgType.TEXT:
            return msg.data
        if msg.type == aiohttp.WSMsgType.BINARY:
            return msg.data.decode(errors="replace")
        if msg.type == aiohttp.WSMsgType.ERROR:
            raise WebSocketClosed(str(self._ws.exception() or "ошибка сокета"))
        raise WebSocketClosed(f"сокет закрыт ({msg.type.name}, код {self._ws.close_code})")

    async def close(self):
        try: await asyncio.wait_for(self._ws.close(), timeout=5)
        except Exception: pass


class AiohttpTransport:
    def __init__(self, proxy: str | None = None, timeout: float = 30):
        self.proxy_url = make_proxy_url(proxy)
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ssl = ssl.create_default_context(cafile=certifi.where())

    def _bind_loop(self):
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError(
                "Клиент Starvell уже работает в другом event loop. "
                "Из других потоков используйте starvellapi.ThreadsafeClient или call_in_loop"
            )

    def _get_session(self) -> aiohttp.ClientSession:
        self._bind_loop()
        if self._session is None or self._session.closed:
            connector = None
            if self.proxy_url:
                from aiohttp_socks import ProxyConnector
                connector = ProxyConnector.from_url(self.proxy_url, ssl=self._ssl)
            else:
                connector = aiohttp.TCPConnector(ssl=self._ssl)
            self._session = aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self._session

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        timeout: float | None = None
    ) -> Response:
        session = self._get_session()
        try:
            async with session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                data=data,
                timeout=aiohttp.ClientTimeout(total=timeout or self.timeout)
            ) as resp:
                text = await resp.text(errors="replace")
                return Response(resp.status, text, {k.lower(): v for k, v in resp.headers.items()})
        except aiohttp.ClientConnectorError as e:
            raise TransportError(str(e) or type(e).__name__, sent=False) from e
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            if _is_proxy_connect_error(e):
                raise TransportError(str(e) or type(e).__name__, sent=False) from e
            raise TransportError(str(e) or type(e).__name__, sent=True) from e

    async def ws_connect(self, url: str, *, headers: dict[str, str] | None = None, timeout: float | None = None) -> WebSocket:
        session = self._get_session()
        try:
            ws = await asyncio.wait_for(session.ws_connect(
                url,
                headers=headers,
                autoping=True,
                timeout=aiohttp.ClientWSTimeout(ws_close=10),
                max_msg_size=4 * 1024 * 1024
            ), timeout=timeout or self.timeout)
        except aiohttp.WSServerHandshakeError as e:
            raise TransportError(f"сокет отклонён сервером, код {e.status}", sent=True) from e
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            raise TransportError(str(e) or type(e).__name__, sent=False) from e
        return _AiohttpWebSocket(ws)

    async def close(self):
        session, self._session = self._session, None
        self._loop = None
        if session is not None and not session.closed:
            try: await asyncio.wait_for(session.close(), timeout=10)
            except asyncio.TimeoutError: pass


def _is_proxy_connect_error(e: BaseException) -> bool:
    try:
        from aiohttp_socks import ProxyConnectionError, ProxyError, ProxyTimeoutError
    except ImportError:
        return False
    return isinstance(e, (ProxyConnectionError, ProxyError, ProxyTimeoutError))
