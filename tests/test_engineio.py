from __future__ import annotations

import asyncio

import pytest

from starvellapi.errors import UnauthorizedError
from starvellapi.realtime.engineio import SocketClosed, SocketIO

from .conftest import FakeWS, connected_ws, socket_frame


def make(transport, ws) -> SocketIO:
    transport.sockets.append(ws)
    return SocketIO(transport, "wss://starvell.com:8443/socket.io/?EIO=4&transport=websocket", {}, ["/chats", "/user-notifications"])


async def test_connect_and_events(transport):
    ws = connected_ws()
    sio = make(transport, ws)
    await sio.connect()
    assert ws.sent[:2] == ["40/chats,", "40/user-notifications,"]
    assert sio.ping_interval == 25 and sio.ping_timeout == 20

    ws.push("2")
    ws.push(socket_frame("/chats", "chat_read", {"chatId": "c"}))
    ws.push('42/user-notifications,["balance_updated",{"userId":1}]')
    got = []
    async for item in sio.events():
        got.append(item)
        if len(got) == 2:
            break
    assert "3" in ws.sent
    assert got[0] == ("/chats", "chat_read", [{"chatId": "c"}])
    assert got[1][1] == "balance_updated"


async def test_unauthorized_namespace(transport):
    ws = FakeWS(['0{"sid":"x","pingInterval":25000,"pingTimeout":20000}', '44/chats,{"message":"Unauthorized"}'])
    with pytest.raises(UnauthorizedError):
        await make(transport, ws).connect()
    assert ws.closed


async def test_drop_raises_socket_closed(transport):
    ws = connected_ws()
    sio = make(transport, ws)
    await sio.connect()
    ws.drop()
    with pytest.raises(SocketClosed):
        async for _ in sio.events():
            pass


async def test_silence_is_dead_connection(transport):
    ws = FakeWS(['0{"sid":"x","pingInterval":100,"pingTimeout":100}', '40/chats,{"sid":"y"}', '40/user-notifications,{"sid":"y"}'])
    sio = make(transport, ws)
    await sio.connect()
    with pytest.raises(SocketClosed):
        async for _ in sio.events():
            pass


async def test_server_namespace_disconnect(transport):
    ws = connected_ws()
    sio = make(transport, ws)
    await sio.connect()
    ws.push("41/chats,")
    with pytest.raises(SocketClosed):
        async for _ in sio.events():
            pass


async def test_handshake_timeout(transport, monkeypatch):
    ws = FakeWS(['0{"sid":"x","pingInterval":25000,"pingTimeout":20000}'])
    sio = make(transport, ws)
    sio.connect_timeout = 0.05
    with pytest.raises(SocketClosed):
        await sio.connect()
    await asyncio.sleep(0)
