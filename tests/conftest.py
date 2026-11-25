from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starvellapi import _http, _limits  # noqa: E402
from starvellapi._transport import Response, TransportError, WebSocketClosed  # noqa: E402
from starvellapi.realtime import source  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name: str) -> Any:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return json.load(f)


def json_response(data: Any, status: int = 200, headers: dict[str, str] | None = None) -> Response:
    return Response(status, json.dumps(data, ensure_ascii=False), {"content-type": "application/json; charset=utf-8", **(headers or {})})


def html_response(status: int, text: str = "<html>blocked</html>") -> Response:
    return Response(status, text, {"content-type": "text/html", "server": "QRATOR"})


class FakeWS:
    def __init__(self, frames: list[str] | None = None):
        self.incoming: asyncio.Queue = asyncio.Queue()
        self.sent: list[str] = []
        self.closed = False
        for frame in frames or []:
            self.incoming.put_nowait(frame)

    def push(self, frame: str):
        self.incoming.put_nowait(frame)

    def drop(self):
        self.incoming.put_nowait(WebSocketClosed("обрыв"))

    async def send(self, data: str):
        if self.closed:
            raise WebSocketClosed("закрыт")
        self.sent.append(data)

    async def receive(self, timeout: float | None = None) -> str:
        item = await asyncio.wait_for(self.incoming.get(), timeout)
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self):
        self.closed = True


class FakeTransport:
    def __init__(self):
        self.routes: dict[tuple[str, str], list[Any]] = {}
        self.calls: list[dict[str, Any]] = []
        self.sockets: list[Any] = []

    def add(self, method: str, path: str, *responses: Any):
        self.routes.setdefault((method, path), []).extend(responses)

    async def request(self, method, url, *, headers=None, params=None, json=None, data=None, timeout=None) -> Response:
        path = url.split("starvell.com", 1)[-1]
        self.calls.append({"method": method, "path": path, "json": json, "params": params, "headers": headers})
        queue = self.routes.get((method, path))
        if not queue:
            return json_response({"success": False, "message": f"нет ответа для {method} {path}"}, 404)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, BaseException):
            raise item
        if asyncio.iscoroutinefunction(item):
            item = await item(json)
        elif callable(item):
            item = item(json)
        return item if isinstance(item, Response) else json_response(item)

    async def ws_connect(self, url, *, headers=None, timeout=None):
        if not self.sockets:
            raise TransportError("нет сокета", sent=False)
        item = self.sockets.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self):
        pass


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, delay: float):
        self.now += max(delay, 0)
        await asyncio.sleep(0)


@pytest.fixture
def clock(monkeypatch):
    c = FakeClock()
    for module in (_http, _limits):
        monkeypatch.setattr(module, "_now", c)
        monkeypatch.setattr(module, "_sleep", c.sleep)
    return c


@pytest.fixture
def fast_realtime(monkeypatch):
    async def no_sleep(delay):
        await asyncio.sleep(0)
    monkeypatch.setattr(source, "_sleep", no_sleep)


@pytest.fixture
def transport():
    return FakeTransport()


def connected_ws(namespaces=("/chats", "/user-notifications")) -> FakeWS:
    ws = FakeWS(['0{"sid":"x","upgrades":[],"pingInterval":25000,"pingTimeout":20000}'])
    for ns in namespaces:
        ws.push(f'40{ns},{{"sid":"y"}}')
    return ws


def socket_frame(namespace: str, event: str, *args: Any) -> str:
    return f"42{namespace}," + json.dumps([event, *args], ensure_ascii=False)
