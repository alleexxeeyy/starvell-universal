from __future__ import annotations

import asyncio
import threading

import pytest
from magic_filter import F

from starvellapi import Client, Dispatcher, NewMessageEvent, NewOrderEvent, Router, ThreadsafeClient, call_in_loop
from starvellapi.models import Message, Order


def msg_event(text: str, chat_id: str = "c1") -> NewMessageEvent:
    return NewMessageEvent(message=Message(id=text, chat_id=chat_id, content=text, author_id=2))


@pytest.fixture
def client(transport):
    transport.add("GET", "/api/profiles/me", {"user": {"id": 1, "username": "seller"}})
    return Client(session="s", transport=transport)


async def test_filters_di_and_context(client):
    dp = Dispatcher(client)
    dp["svbot"] = "BOT"
    router = Router()
    got = []

    @router.new_message(F.message.content.startswith("!"))
    async def command(event: NewMessageEvent, svbot):
        got.append((event.message.content, svbot))

    @router.new_order()
    async def order(ev):
        got.append(("order", ev.order.id))

    dp.include_router(router)
    await dp.feed_event(msg_event("привет"))
    await dp.feed_event(msg_event("!продавец"))
    await dp.feed_event(NewOrderEvent(order=Order(id="o1"), chat_id="c1"))
    assert got == [("!продавец", "BOT"), ("order", "o1")]


async def test_error_does_not_stop_other_handlers(client):
    dp = Dispatcher(client)
    errors, calls = [], []

    @dp.new_message()
    async def broken(event):
        raise ValueError("сломался")

    @dp.new_message()
    async def works(event):
        calls.append(event.message.id)

    @dp.error()
    async def on_error(exception, handler_name):
        errors.append((type(exception).__name__, handler_name.rsplit(".", 1)[-1]))

    await dp.feed_event(msg_event("a"))
    assert calls == ["a"] and errors == [("ValueError", "broken")]


async def test_parallel_chats_keep_order_inside_chat(client):
    dp = Dispatcher(client, mode="parallel_chats")
    order: list[str] = []

    @dp.new_message()
    async def slow(event):
        await asyncio.sleep(0.05 if event.message.content.endswith("1") else 0)
        order.append(event.message.content)

    for text, chat in (("a1", "A"), ("a2", "A"), ("b1", "B"), ("b2", "B")):
        dp._dispatch_parallel(msg_event(text, chat))
    await asyncio.gather(*list(dp._pending))
    assert order.index("a1") < order.index("a2") and order.index("b1") < order.index("b2")


async def test_call_in_loop_from_other_loop():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        async def where():
            return asyncio.get_running_loop()
        assert await call_in_loop(where(), loop) is loop
        assert await call_in_loop(where(), asyncio.get_running_loop()) is asyncio.get_running_loop()
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(2)
        loop.close()


async def test_threadsafe_client(client):
    sync = ThreadsafeClient(client, asyncio.get_running_loop(), timeout=5)
    result = {}

    def worker():
        result["me"] = sync.refresh()
    thread = threading.Thread(target=worker)
    thread.start()
    while thread.is_alive():
        await asyncio.sleep(0.01)
    assert result["me"].id == 1

    with pytest.raises(RuntimeError):
        sync.refresh()


async def test_transport_bound_to_one_loop():
    from starvellapi._transport import AiohttpTransport
    t = AiohttpTransport()
    other = asyncio.new_event_loop()
    try:
        t._loop = other
        with pytest.raises(RuntimeError):
            t._bind_loop()
    finally:
        other.close()
