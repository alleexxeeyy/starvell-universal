from __future__ import annotations

import asyncio
from typing import Any

import pytest

from starvellapi import (
    Client,
    ConnectionStatusEvent,
    EventSource,
    MemoryState,
    NewMessageEvent,
    NewOrderEvent,
    OrderCompletedEvent,
    OrderSellerCompletedEvent,
)
from starvellapi._transport import TransportError

from .conftest import connected_ws, json_response, socket_frame

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


async def collect(src: EventSource, n: int, timeout: float = 2.0, ack: bool = True) -> list:
    events = []
    try:
        while len(events) < n:
            event = await asyncio.wait_for(src.get(), timeout)
            if isinstance(event, ConnectionStatusEvent):
                continue
            if ack:
                src.ack(event)
            events.append(event)
    except asyncio.TimeoutError:
        pass
    return events


async def quiet(src: EventSource, timeout: float = 0.3, ack: bool = True) -> list:
    return await collect(src, 100, timeout, ack)


def state(**kw) -> MemoryState:
    return MemoryState({"initialized": True, "watermark": "2026-11-25T12:00:00+00:00", "seen": [], "chats": {}, "orders": {}, **kw})


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
    st = state(orders={"known": {"status": "CREATED", "events": ["NEW_ORDER"]}})
    transport.add("POST", "/api/orders/list", [
        order("closed", "COMPLETED", sort_at="2026-11-25T12:10:00.000Z"),
        order("done-by-hand", "CREATED", sort_at="2026-11-25T12:11:00.000Z", sellerCompletedAt="2026-11-25T12:12:00.000Z"),
        order("fresh", "CREATED", sort_at="2026-11-25T12:15:00.000Z"),
        order("known", "COMPLETED", sort_at="2026-11-25T11:00:00.000Z"),
    ])
    transport.add("POST", "/api/chats/list", [chat(message("m1", created="2026-11-25T11:00:00.000Z"))])
    transport.add("POST", "/api/messages/list-v2", {"items": [message("m1", created="2026-11-25T11:00:00.000Z")]})
    transport.add("GET", "/api/orders/closed", order("closed", "COMPLETED"))
    transport.add("GET", "/api/orders/done-by-hand", order("done-by-hand", sellerCompletedAt="2026-11-25T12:12:00.000Z"))
    transport.add("GET", "/api/orders/fresh", order("fresh"))
    transport.add("GET", "/api/orders/known", order("known", "COMPLETED"))
    src = make_source(client, state=st, use_socket=False)
    await src.start()
    events = await quiet(src, 0.5)
    await src.close()

    new_orders = [e.order.id for e in events if isinstance(e, NewOrderEvent)]
    assert new_orders == ["fresh"]
    assert all(e.catch_up for e in events if isinstance(e, NewOrderEvent))
    assert [e.order.id for e in events if isinstance(e, OrderCompletedEvent)] == ["known"]
    assert "closed" not in st.state["orders"]
    assert st.state["orders"]["done-by-hand"]["events"] == ["NEW_ORDER"]


async def test_restart_does_not_repeat_emitted_order(client, transport, fast_realtime):
    st = state(orders={"o1": {"status": "CREATED", "events": ["NEW_ORDER"]}})
    transport.add("POST", "/api/orders/list", [order("o1", sort_at="2026-11-25T12:15:00.000Z")])
    transport.add("POST", "/api/chats/list", [])
    src = make_source(client, state=st, use_socket=False)
    await src.start()
    events = await quiet(src, 0.4)
    await src.close()
    assert not [e for e in events if isinstance(e, NewOrderEvent)]


async def test_polling_when_socket_unavailable(client, transport, fast_realtime):
    st = state(seen=["m-old"])
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [chat(message("m-new", "есть кто?", created="2026-11-25T12:30:00.000Z"))])
    transport.add("POST", "/api/messages/list-v2", {"items": [
        message("m-new", "есть кто?", created="2026-11-25T12:30:00.000Z"),
        message("m-old", "старое", created="2026-11-25T11:00:00.000Z"),
    ]})
    transport.sockets.append(TransportError("сокет отклонён сервером, код 403", sent=True))
    src = make_source(client, state=st)
    src.socket_retry_interval = 60
    await src.start()
    events = await collect(src, 1)
    await asyncio.sleep(0.05)
    mode = src.mode
    await src.close()
    assert [e.message.id for e in events] == ["m-new"]
    assert mode == "polling"


async def test_reconnect_catches_up_missed_messages(client, transport, fast_realtime):
    st = state()
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [],
                  [chat(message("m-missed", "пока сокет лежал", created="2026-11-25T12:31:00.000Z"))])
    transport.add("POST", "/api/messages/list-v2", {"items": [message("m-missed", "пока сокет лежал", created="2026-11-25T12:31:00.000Z")]})
    first, second = connected_ws(), connected_ws()
    transport.sockets.extend([first, second])
    src = make_source(client, state=st)
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


async def test_unacked_order_comes_again_after_restart(client, transport, fast_realtime):
    st = state()
    transport.add("POST", "/api/orders/list", [], [order("o1", sort_at="2026-11-25T12:30:00.000Z")])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", order("o1"))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client, state=st)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m1", "o1")))
    events = await collect(src, 1, ack=False)
    assert isinstance(events[0], NewOrderEvent)
    await src.close()
    assert "o1" not in st.state["orders"] or "NEW_ORDER" not in st.state["orders"]["o1"]["events"]

    again = make_source(Client(session="s", transport=transport), state=st, use_socket=False)
    await again.start()
    events = [e for e in await quiet(again, 0.5) if isinstance(e, NewOrderEvent)]
    await again.close()
    assert [e.order.id for e in events] == ["o1"] and events[0].catch_up


async def test_acked_order_saved_immediately(client, transport, fast_realtime):
    st = state()
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", order("o1"))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client, state=st)
    src.save_interval = 3600
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m1", "o1")))
    await collect(src, 1)
    assert st.state["orders"]["o1"]["events"] == ["NEW_ORDER"]
    await src.close()


async def test_failed_first_run_does_not_flood_later(client, transport, fast_realtime):
    st = MemoryState()
    transport.add("POST", "/api/orders/list", TransportError("нет сети", sent=False))
    transport.add("POST", "/api/chats/list", [])
    src = make_source(client, state=st, use_socket=False)
    src.order_fetch_retries = 1
    await src.start()
    await asyncio.sleep(0.2)
    await src.close()
    assert st.state == {}

    transport.routes[("POST", "/api/orders/list")] = [[order("old1"), order("old2")]]
    again = make_source(Client(session="s", transport=transport), state=st, use_socket=False)
    await again.start()
    events = await quiet(again, 0.4)
    await again.close()
    assert not [e for e in events if isinstance(e, NewOrderEvent)]


async def test_broken_order_does_not_swallow_message(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", json_response({"success": False, "message": "ошибка"}, 500))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    src.order_fetch_retries = 1
    src.order_retry_delays = ()
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m1", "o1")))
    events = await quiet(src)
    await src.close()
    assert [type(e).__name__ for e in events] == ["NewMessageEvent"]


async def test_own_purchase_is_not_a_sale(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/p1", {**order("p1"), "sellerId": 777, "buyerId": ME})
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m1", "p1")))
    events = await quiet(src)
    await src.close()
    assert not [e for e in events if isinstance(e, NewOrderEvent)]


async def test_payment_found_by_status_change_gives_new_order(client, transport, fast_realtime):
    st = state(orders={"o9": {"status": "PRE_CREATED", "events": []}})
    transport.add("POST", "/api/orders/list", [order("o9", "CREATED", sort_at="2026-11-25T12:40:00.000Z")])
    transport.add("POST", "/api/chats/list", [chat(message("m-last", created="2026-11-25T12:41:00.000Z"))])
    transport.add("POST", "/api/messages/list-v2", {"items": []})
    transport.add("GET", "/api/orders/o9", order("o9", "CREATED"))
    src = make_source(client, state=st, use_socket=False)
    await src.start()
    events = await quiet(src, 0.5)
    await src.close()
    new = [e for e in events if isinstance(e, NewOrderEvent)]
    assert [e.order.id for e in new] == ["o9"] and new[0].chat_id == CHAT


async def test_catch_up_uses_after_id(client, transport, fast_realtime):
    st = state(chats={CHAT: "m1"}, seen=["m1"])
    calls = []

    def messages(body):
        calls.append(body)
        return {"items": [message("m3", "третье", created="2026-11-25T12:33:00.000Z"),
                          message("m2", "второе", created="2026-11-25T12:32:00.000Z")]}
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [chat(message("m3", "третье", created="2026-11-25T12:33:00.000Z"))])
    transport.add("POST", "/api/messages/list-v2", messages)
    src = make_source(client, state=st, use_socket=False)
    await src.start()
    events = await quiet(src, 0.5)
    await src.close()
    assert [e.message.id for e in events] == ["m2", "m3"]
    assert calls[0]["afterId"] == "m1"


async def test_get_after_close_stops_iteration(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    src = make_source(client, use_socket=False)
    await src.start()
    waiter = asyncio.ensure_future(src.__anext__())
    await asyncio.sleep(0.05)
    await src.close()
    while True:
        try:
            event = await asyncio.wait_for(waiter, 1)
        except StopAsyncIteration:
            break
        assert isinstance(event, ConnectionStatusEvent)
        waiter = asyncio.ensure_future(src.__anext__())


async def test_polling_without_ack_gives_one_new_order(client, transport, fast_realtime):
    st = state()
    transport.add("POST", "/api/orders/list", [order("o1", sort_at="2026-11-25T12:30:00.000Z")])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", order("o1"))
    src = make_source(client, state=st, use_socket=False)
    await src.start()
    events = [e for e in await quiet(src, 0.5, ack=False) if isinstance(e, NewOrderEvent)]
    await src.close()
    assert len(events) == 1


async def test_retry_after_failed_fetch_delivers_order(client, transport, fast_realtime):
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", json_response({"success": False, "message": "ошибка"}, 500), order("o1"))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    src.order_fetch_retries = 1
    src.order_retry_delays = (0.0,)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m1", "o1")))
    events = await quiet(src, 0.5)
    await src.close()
    assert [type(e).__name__ for e in events].count("NewOrderEvent") == 1


async def test_own_message_does_not_jump_unacked(client, transport, fast_realtime):
    st = state(chats={CHAT: "m0"}, seen=["m0"])
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client, state=st)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", message("m1", "от покупателя", created="2026-11-25T12:30:00.000Z")))
    ws.push(socket_frame("/chats", "message_created", message("m2", "наш автоответ", author=ME, created="2026-11-25T12:30:01.000Z")))
    events = await collect(src, 1, ack=False)
    await asyncio.sleep(0.05)
    src._save(force=True)
    assert st.state["chats"][CHAT] == "m0"
    src.ack(events[0])
    src._save(force=True)
    assert st.state["chats"][CHAT] == "m2"
    await src.close()


async def test_held_messages_survive_reconnect_during_sync(client, transport, fast_realtime):
    gate = asyncio.Event()

    async def slow_orders(_):
        await gate.wait()
        return []
    st = state()
    transport.add("POST", "/api/orders/list", [], slow_orders)
    transport.add("POST", "/api/chats/list", [])
    first, second = connected_ws(), connected_ws()
    transport.sockets.extend([first, second])
    src = make_source(client, state=st)
    src.max_socket_failures = 10
    await src.start()
    await asyncio.sleep(0.05)
    first.push(socket_frame("/chats", "message_created", message("m-held", "во время догона", created="2026-11-25T12:30:00.000Z")))
    await asyncio.sleep(0.02)
    first.drop()
    await asyncio.sleep(0.05)
    second.push(socket_frame("/chats", "message_created", message("m-next", "после реконнекта", created="2026-11-25T12:31:00.000Z")))
    await asyncio.sleep(0.02)
    gate.set()
    events = await collect(src, 2)
    await src.close()
    assert [e.message.id for e in events] == ["m-held", "m-next"]


async def test_failed_sync_is_retried_before_flush(client, transport, fast_realtime):
    st = state()
    transport.add("POST", "/api/orders/list", [], TransportError("сбой", sent=False), [])
    transport.add("POST", "/api/chats/list", [])
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client, state=st)
    src.sync_retry_delays = (0.0,)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", message("m1", created="2026-11-25T12:30:00.000Z")))
    events = await collect(src, 1)
    await src.close()
    order_calls = [c for c in transport.calls if c["path"] == "/api/orders/list"]
    assert len(order_calls) >= 3 and [e.message.id for e in events] == ["m1"]


async def test_corrupted_state_replays_orders_not_chats(client, transport, fast_realtime):
    st = MemoryState({"initialized": True, "corrupted": True})
    transport.add("POST", "/api/orders/list", [order("open1", sort_at="2026-11-25T10:00:00.000Z")])
    transport.add("POST", "/api/chats/list", [chat(message("old-msg", created="2026-11-25T09:00:00.000Z"))])
    transport.add("POST", "/api/messages/list-v2", {"items": [message("old-msg", created="2026-11-25T09:00:00.000Z")]})
    transport.add("GET", "/api/orders/open1", order("open1"))
    src = make_source(client, state=st, use_socket=False)
    await src.start()
    events = await quiet(src, 0.4)
    await src.close()
    assert [e.order.id for e in events if isinstance(e, NewOrderEvent)] == ["open1"]
    assert not [e for e in events if isinstance(e, NewMessageEvent)]


async def test_order_pagination_in_catch_up(client, transport, fast_realtime):
    st = state()
    page1 = [order(f"a{i}", sort_at="2026-11-25T12:30:00.000Z") for i in range(3)]
    page2 = [order("deep", sort_at="2026-11-25T12:20:00.000Z")]

    def orders(body):
        return page1 if body["offset"] == 0 else page2
    transport.add("POST", "/api/orders/list", orders)
    transport.add("POST", "/api/chats/list", [])
    for o in page1 + page2:
        transport.add("GET", f"/api/orders/{o['id']}", o)
    src = make_source(client, state=st, use_socket=False)
    src.sync_orders_limit = 3
    await src.start()
    events = await quiet(src, 0.5)
    await src.close()
    assert "deep" in [e.order.id for e in events if isinstance(e, NewOrderEvent)]


async def test_close_leaves_no_workers(client, transport, fast_realtime):
    gate = asyncio.Event()

    async def slow_order(_):
        await gate.wait()
        return order("o1")
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", slow_order)
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client)
    await src.start()
    ws.push(socket_frame("/chats", "message_created", payment("m1", "o1")))
    await asyncio.sleep(0.05)
    await src.close()
    assert not src._chat_workers and not src._tasks
    leftover = [t for t in asyncio.all_tasks() if "chat_worker" in repr(t)]
    assert not leftover


async def test_dispatcher_parallel_stop_keeps_ack(client, transport, fast_realtime):
    from starvellapi import Dispatcher
    st = state()
    transport.add("POST", "/api/orders/list", [])
    transport.add("POST", "/api/chats/list", [])
    transport.add("GET", "/api/orders/o1", order("o1"))
    ws = connected_ws()
    transport.sockets.append(ws)
    src = make_source(client, state=st)
    dp = Dispatcher(client, mode="parallel_chats")
    started = asyncio.Event()

    @dp.new_order()
    async def slow_delivery(event):
        started.set()
        await asyncio.sleep(0.1)

    task = asyncio.ensure_future(dp.run(source=src))
    await asyncio.sleep(0.05)
    ws.push(socket_frame("/chats", "message_created", payment("m1", "o1")))
    await asyncio.wait_for(started.wait(), 2)
    dp.stop()
    await task
    assert st.state["orders"]["o1"]["events"] == ["NEW_ORDER"]
