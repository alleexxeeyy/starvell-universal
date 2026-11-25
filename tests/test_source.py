from __future__ import annotations

import asyncio
from typing import Any

import pytest

from starvellapi import (
    Client,
    EventSource,
    MemoryState,
    NewMessageEvent,
    NewOrderEvent,
    OrderCompletedEvent,
    OrderSellerCompletedEvent,
)
from starvellapi._transport import TransportError

from .conftest import connected_ws, socket_frame

ME, BUYER = 1001, 2002
CHAT = "00000000-0000-7000-8000-00000000c001"


def order(order_id: str, status: str = "CREATED", sort_at: str = "2026-11-25T12:20:36.195Z", **extra: Any) -> dict:
    return {"id": order_id, "shortId": order_id[-8:].upper(), "status": status, "sellerId": ME, "buyerId": BUYER,
            "offerId": 7, "offerPublicId": "offer-pub", "quantity": 1, "basePrice": 100, "totalPrice": 116,
            "createdAt": sort_at, "sortAt": sort_at, "paidAt": sort_at, **extra}


def message(msg_id: str, content: str = "привет", author: int | None = BUYER, created: str = "2026-11-25T12:30:00.000Z", **extra: Any) -> dict:
    return {"id": msg_id, "chatId": CHAT, "content": content, "type": "DEFAULT", "authorId": author,
            "author": {"id": author, "username": "buyer" if author == BUYER else "seller"} if author else None,
            "createdAt": created, **extra}


def payment(msg_id: str, order_id: str, kind: str = "ORDER_PAYMENT", created: str = "2026-11-25T12:30:01.000Z") -> dict:
    return {**message(msg_id, "", None, created), "type": "NOTIFICATION",
            "metadata": {"orderId": order_id, "orderShortId": "SHORT", "notificationType": kind},
            "buyer": {"id": BUYER, "username": "buyer"}, "order": {"id": order_id, "status": "CREATED", "quantity": 1}}


def chat(last: dict) -> dict:
    return {"id": CHAT, "participants": [{"id": ME, "username": "seller"}, {"id": BUYER, "username": "buyer"}], "lastMessage": last}


@pytest.fixture
def client(transport):
    transport.add("GET", "/api/profiles/me", {"user": {"id": ME, "username": "seller", "publicId": "me-pub"}})
    return Client(session="s", transport=transport)


def make_source(client, state=None, **kw) -> EventSource:
    src = EventSource(client, state=state or MemoryState(), **kw)
    src.order_chat_wait = 0
    src.poll_chats_interval = 0
    src.poll_orders_interval = 0
    src.max_socket_failures = 1
    return src


async def collect(src: EventSource, n: int, timeout: float = 2.0) -> list:
    events = []
    try:
        while len(events) < n:
            events.append(await asyncio.wait_for(src.get(), timeout))
    except asyncio.TimeoutError:
        pass
    return events


async def quiet(src: EventSource, timeout: float = 0.3) -> list:
    return await collect(src, 100, timeout)


async def test_payment_via_socket(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", order("o1"))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m1", "o1")))
    ws.push(socket_frame("/chats", "message_created", message("m2", "прив", author=ME, metadata={"isAutoResponse": True})))
    ws.push(socket_frame("/chats", "message_created", message("m3", "куда писать ник?")))
    events = await collect(src, 3)
    await src.close()

    assert [type(e).__name__ for e in events] == ["NewOrderEvent", "NewMessageEvent", "NewMessageEvent"]
    new_order = events[0]
    assert new_order.order.offer_public_id == "offer-pub" and new_order.chat_id == CHAT
    assert events[1].message.is_notification and events[2].message.text == "куда писать ник?"


async def test_duplicates_and_own_messages(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    await src.start()
    frame = socket_frame("/chats", "message_created", message("m1"))
    ws.push(frame)
    ws.push(frame)
    ws.push(socket_frame("/chats", "message_created", message("m2", "моё", author=ME)))
    events = await quiet(src)
    await src.close()
    assert [e.message.id for e in events if isinstance(e, NewMessageEvent)] == ["m1"]


async def test_events_in_chat_order_even_with_slow_enrichment(client, transport, fast_realtime):
    async def slow_order(_):
        await asyncio.sleep(0.2)
        return order("o1")
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", slow_order)
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m1", "o1")))
    ws.push(socket_frame("/chats", "message_created", message("m2", "сразу после оплаты", created="2026-11-25T12:30:02.000Z")))
    events = await collect(src, 3)
    await src.close()
    assert [type(e).__name__ for e in events] == ["NewOrderEvent", "NewMessageEvent", "NewMessageEvent"]
    assert events[2].message.id == "m2"


async def test_sale_update_without_chat_notification(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [], [chat(message("old"))])
    transport.add("GET", "/api/orders/o2", order("o2"))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    await src.start()
    ws.push(socket_frame("/user-notifications", "sale_update", {"orderId": "o2", "orderShortId": "X", "delta": 1}))
    events = [e for e in await quiet(src, 0.5) if isinstance(e, NewOrderEvent)]
    await src.close()
    assert len(events) == 1 and events[0].order.id == "o2" and events[0].chat_id == CHAT


async def test_sale_update_and_notification_give_one_order_event(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", order("o1"))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    await src.start()
    ws.push(socket_frame("/user-notifications", "sale_update", {"orderId": "o1", "delta": 1}))
    ws.push(socket_frame("/chats", "message_created", payment("m1", "o1")))
    events = [e for e in await quiet(src, 0.5) if isinstance(e, NewOrderEvent)]
    await src.close()
    assert len(events) == 1


async def test_seller_completed_notification(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", order("o1", sellerCompletedAt="2026-11-25T12:40:00.000Z"))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m9", "o1", "ORDER_SELLER_COMPLETED")))
    events = await collect(src, 2)
    await src.close()
    assert isinstance(events[0], OrderSellerCompletedEvent)


async def test_first_run_does_not_replay_old_orders(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [order("o5")])
    transport.add("POST", "/api/chats/list", [chat(message("m-old"))])
    src = make_source(client, use_socket=False)
    await src.start()
    events = await quiet(src, 0.4)
    await src.close()
    assert events == []


async def test_restart_catch_up_skips_orders_closed_while_offline(client, transport, fast_realtime):
    state = MemoryState({
        "watermark": "2026-11-25T12:00:00+00:00",
        "seen": [], "chats": {},
        "orders": {"known": {"status": "CREATED", "events": ["NEW_ORDER"]}},
    })
    transport.add("POST", "/api/orders/list", [
        order("closed", "COMPLETED", sort_at="2026-11-25T12:10:00.000Z"),
        order("done-by-hand", "CREATED", sort_at="2026-11-25T12:11:00.000Z", sellerCompletedAt="2026-11-25T12:12:00.000Z"),
        order("fresh", "CREATED", sort_at="2026-11-25T12:15:00.000Z"),
        order("known", "COMPLETED", sort_at="2026-11-25T11:00:00.000Z"),
    ])
    transport.add("POST", "/api/chats/list", [chat(message("m1", created="2026-11-25T11:00:00.000Z"))])
    transport.add("GET", "/api/orders/closed", order("closed", "COMPLETED"))
    transport.add("GET", "/api/orders/done-by-hand", order("done-by-hand", sellerCompletedAt="2026-11-25T12:12:00.000Z"))
    transport.add("GET", "/api/orders/fresh", order("fresh"))
    transport.add("GET", "/api/orders/known", order("known", "COMPLETED"))
    src = make_source(client, state=state, use_socket=False)
    await src.start()
    events = await quiet(src, 0.5)
    await src.close()

    new_orders = [e.order.id for e in events if isinstance(e, NewOrderEvent)]
    assert new_orders == ["fresh"]
    assert [e.order.id for e in events if isinstance(e, OrderCompletedEvent)] == ["known"]
    assert state.state["orders"]["closed"]["events"] == ["NEW_ORDER"]


async def test_restart_does_not_repeat_emitted_order(client, transport, fast_realtime):
    state = MemoryState({"watermark": "2026-11-25T12:00:00+00:00", "seen": [], "chats": {},
                         "orders": {"o1": {"status": "CREATED", "events": ["NEW_ORDER"]}}})
    transport.add("POST", "/api/orders/list", [order("o1", sort_at="2026-11-25T12:15:00.000Z")])
    transport.add("POST", "/api/chats/list", [])
    src = make_source(client, state=state, use_socket=False)
    await src.start()
    events = await quiet(src, 0.4)
    await src.close()
    assert not [e for e in events if isinstance(e, NewOrderEvent)]


async def test_polling_when_socket_unavailable(client, transport, fast_realtime):
    state = MemoryState({"watermark": "2026-11-25T12:00:00+00:00", "seen": ["m-old"], "chats": {}, "orders": {}})
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [chat(message("m-new", "есть кто?", created="2026-11-25T12:30:00.000Z"))])
    transport.add("POST", "/api/messages/list-v2", {"items": [
        message("m-new", "есть кто?", created="2026-11-25T12:30:00.000Z"),
        message("m-old", "старое", created="2026-11-25T11:00:00.000Z"),
    ]})
    transport.sockets.append(TransportError("сокет отклонён сервером, код 403", sent=True))
    src = make_source(client, state=state)
    src.socket_retry_interval = 60
    await src.start()
    events = await collect(src, 1)
    await asyncio.sleep(0.05)
    mode = src.mode
    await src.close()
    assert [e.message.id for e in events] == ["m-new"]
    assert mode == "polling"


async def test_reconnect_catches_up_missed_messages(client, transport, fast_realtime):
    state = MemoryState({"watermark": "2026-11-25T12:00:00+00:00", "seen": [], "chats": {}, "orders": {}})
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [],
                  [chat(message("m-missed", "пока сокет лежал", created="2026-11-25T12:31:00.000Z"))])
    transport.add("POST", "/api/messages/list-v2", {"items": [message("m-missed", "пока сокет лежал", created="2026-11-25T12:31:00.000Z")]})
    first, second = connected_ws(), connected_ws()
    transport.sockets.extend([first, second])
    src = make_source(client, state=state)
    src.max_socket_failures = 10
    await src.start()
    await asyncio.sleep(0.05)
    first.drop()
    events = await collect(src, 1)
    await src.close()
    assert [e.message.id for e in events] == ["m-missed"]


async def test_state_survives_close(client, transport, fast_realtime):
    state = MemoryState()
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", order("o1"))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client, state=state)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m1", "o1")))
    await collect(src, 2)
    await src.close()
    saved = state.state
    assert "m1" in saved["seen"] and saved["orders"]["o1"]["events"] == ["NEW_ORDER"]
    assert saved["watermark"].startswith("2026-11-25T12:")


async def test_unpaid_reminder_is_not_status_change(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o7", order("o7", "PRE_CREATED"))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m7", "o7", "ORDER_NOT_PAID_REMINDER")))
    events = await quiet(src)
    await src.close()
    assert [type(e).__name__ for e in events] == ["NewMessageEvent"]
