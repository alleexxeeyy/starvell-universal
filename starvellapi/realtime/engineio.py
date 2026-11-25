from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from logging import getLogger
from typing import Any

from .._transport import Transport, TransportError, WebSocket, WebSocketClosed
from ..errors import UnauthorizedError


logger = getLogger("starvellapi.realtime")

_sleep = asyncio.sleep


class SocketClosed(Exception):
    pass


class SocketIO:
    """
    Минимальный клиент Socket.IO v4 (Engine.IO v4, только websocket) - ровно то, что использует Starvell:
    подключение неймспейсов, события `42`, ping/pong. Бинарные пакеты и ack не нужны.
    """

    connect_timeout = 15.0

    def __init__(self, transport: Transport, url: str, headers: dict[str, str], namespaces: list[str]):
        self.transport = transport
        self.url = url
        self.headers = headers
        self.namespaces = list(namespaces)
        self.ping_interval = 25.0
        self.ping_timeout = 20.0
        self._ws: WebSocket | None = None
        self._send_lock: asyncio.Lock | None = None

    @property
    def connected(self) -> bool:
        return self._ws is not None

    async def connect(self):
        try:
            self._ws = await self.transport.ws_connect(self.url, headers=self.headers, timeout=self.connect_timeout)
        except TransportError as e:
            raise SocketClosed(e.error) from e
        self._send_lock = asyncio.Lock()
        try:
            opened = await self._ws.receive(timeout=self.connect_timeout)
            if not opened.startswith("0"):
                raise SocketClosed(f"неожиданный первый пакет: {opened[:100]}")
            info = json.loads(opened[1:] or "{}")
            self.ping_interval = info.get("pingInterval", 25000) / 1000
            self.ping_timeout = info.get("pingTimeout", 20000) / 1000

            for ns in self.namespaces:
                await self._send(f"40{ns},")
            pending = set(self.namespaces)
            while pending:
                packet = await self._ws.receive(timeout=self.connect_timeout)
                if packet == "2":
                    await self._send("3")
                    continue
                ns, kind, payload = _parse(packet)
                if ns not in pending:
                    continue
                if kind == "0":
                    pending.discard(ns)
                elif kind == "4":
                    message = (payload or {}).get("message", "") if isinstance(payload, dict) else str(payload)
                    if "unauthorized" in message.lower():
                        raise UnauthorizedError(self.url, 403, f"Сокет Starvell не принял сессию ({ns})")
                    raise SocketClosed(f"неймспейс {ns} отклонён: {message}")
        except asyncio.TimeoutError as e:
            await self.close()
            raise SocketClosed("сервер не ответил на подключение") from e
        except WebSocketClosed as e:
            await self.close()
            raise SocketClosed(str(e)) from e
        except BaseException:
            await self.close()
            raise

    async def events(self) -> AsyncIterator[tuple[str, str, list[Any]]]:
        """
        События `(namespace, event, args)`, пока соединение живо. При обрыве - `SocketClosed`.
        """
        if self._ws is None:
            raise SocketClosed("сокет не подключён")
        # сервер шлёт ping каждые ping_interval, тишина дольше interval + timeout - соединение мёртвое
        silence = self.ping_interval + self.ping_timeout
        while True:
            try:
                packet = await self._ws.receive(timeout=silence)
            except asyncio.TimeoutError as e:
                raise SocketClosed(f"нет данных от сервера {silence:.0f} сек.") from e
            except WebSocketClosed as e:
                raise SocketClosed(str(e)) from e
            if packet == "2":
                await self._send("3")
                continue
            if packet.startswith("1"):
                raise SocketClosed("сервер закрыл соединение")
            if not packet.startswith("4"):
                continue
            ns, kind, payload = _parse(packet)
            if kind == "2" and isinstance(payload, list) and payload and isinstance(payload[0], str):
                yield ns, payload[0], payload[1:]
            elif kind == "1":
                raise SocketClosed(f"сервер отключил неймспейс {ns}")
            elif kind == "4":
                raise SocketClosed(f"ошибка неймспейса {ns}: {payload}")

    async def emit(self, namespace: str, event: str, *args: Any):
        await self._send(f"42{namespace}," + json.dumps([event, *args], ensure_ascii=False, separators=(",", ":")))

    async def _send(self, data: str):
        if self._ws is None or self._send_lock is None:
            raise SocketClosed("сокет не подключён")
        async with self._send_lock:
            try:
                await asyncio.wait_for(self._ws.send(data), timeout=10)
            except (WebSocketClosed, asyncio.TimeoutError) as e:
                raise SocketClosed(f"не удалось отправить пакет: {e}") from e

    async def close(self):
        ws, self._ws = self._ws, None
        if ws is not None:
            try: await ws.send("1")
            except Exception: pass
            await ws.close()


def _parse(packet: str) -> tuple[str, str, Any]:
    # "4" + тип socket.io + "/ns," + json; неймспейс "/" может быть без префикса
    body = packet[1:]
    kind, body = body[:1], body[1:]
    ns = "/"
    if body.startswith("/"):
        ns, _, body = body.partition(",")
    while body[:1].isdigit():
        body = body[1:]
    try:
        payload = json.loads(body) if body else None
    except ValueError:
        payload = body
    return ns, kind, payload
