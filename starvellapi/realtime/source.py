from __future__ import annotations

import asyncio
import time
import traceback
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import TYPE_CHECKING, Any, Literal

from .._http import SOCKET_URL
from ..dispatcher.events import (
    ORDER_EVENTS,
    BalanceUpdatedEvent,
    BaseEvent,
    ChatReadEvent,
    KycStatusUpdatedEvent,
    NewMessageEvent,
    NewOrderEvent,
    OrderCompletedEvent,
    OrderRefundedEvent,
    OrderStatusChangedEvent,
    SocketEvent,
    _OrderEvent,
)
from ..errors import StarvellError, UnauthorizedError
from ..models import BalanceUpdate, Chat, ChatRead, Message, Order, OrderNotice, OrderStatus, UserType
from .engineio import SocketClosed, SocketIO
from .state import MemoryState, StateStore

if TYPE_CHECKING:
    from ..client import Client


logger = getLogger("starvellapi.realtime")

_sleep = asyncio.sleep
_now = time.monotonic

Mode = Literal["socket", "polling"]

NAMESPACES = ["/chats", "/user-notifications"]
STATUS_EVENTS: dict[str, type[_OrderEvent]] = {
    OrderStatus.COMPLETED: OrderCompletedEvent,
    OrderStatus.REFUND: OrderRefundedEvent,
}


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class _Seen:
    def __init__(self, limit: int):
        self.limit = limit
        self.items: OrderedDict[str, None] = OrderedDict()

    def __contains__(self, key: str) -> bool:
        return key in self.items

    def add(self, key: str) -> bool:
        if key in self.items:
            return False
        self.items[key] = None
        while len(self.items) > self.limit:
            self.items.popitem(last=False)
        return True

    def tail(self, n: int) -> list[str]:
        return list(self.items)[-n:]


class EventSource:
    """
    Поток событий аккаунта Starvell.

    Основной канал - socket.io (`wss://starvell.com:8443`). Если сокет недоступен (обрывы подряд, защита QRATOR),
    источник переходит на опрос REST и раз в `socket_retry_interval` пробует вернуться на сокет.
    После переподключения и перезапуска догоняет пропущенное: сообщения новее последнего увиденного и заказы.
    Дубли отсекаются по id на всех путях, состояние (что уже выдано событиями) переживает перезапуск через `state`.
    События одного чата выходят строго по порядку.

    :param client: Клиент Starvell.
    :param state: Хранилище состояния (`JsonFileState` для бота), по умолчанию - в памяти.
    :param use_socket: Использовать сокет (иначе только опрос).
    :param own_messages: Выдавать ли свои сообщения (по умолчанию нет).
    :param socket_events: Выдавать ли каждое событие сокета как `SocketEvent`.
    """

    poll_chats_interval = 4.0
    poll_orders_interval = 6.0
    socket_retry_interval = 300.0
    reconnect_delays = (1.0, 3.0, 5.0, 10.0, 20.0, 30.0)
    max_socket_failures = 3
    stable_after = 60.0
    order_chat_wait = 10.0
    order_fetch_retries = 3
    catch_up_margin = timedelta(seconds=30)
    save_interval = 5.0
    sync_chats_limit = 20
    sync_orders_limit = 30

    def __init__(
        self,
        client: Client,
        state: StateStore | None = None,
        use_socket: bool = True,
        own_messages: bool = False,
        socket_events: bool = False,
        socket_url: str = SOCKET_URL
    ):
        self.client = client
        self.store = state or MemoryState()
        self.use_socket = use_socket
        self.own_messages = own_messages
        self.socket_events = socket_events
        self.socket_url = socket_url
        self.mode: Mode | None = None

        self._queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self._tasks: set[asyncio.Task] = set()
        self._chat_queues: dict[str, asyncio.Queue] = {}
        self._chat_workers: dict[str, asyncio.Task] = {}
        self._socket: SocketIO | None = None
        self._runner: asyncio.Task | None = None

        self._seen = _Seen(5000)
        self._orders: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._chat_last: OrderedDict[str, str] = OrderedDict()
        self._chat_by_user: dict[int, str] = {}
        self._watermark: datetime | None = None
        self._first_run = True
        self._dirty = False
        self._last_save = 0.0

    def __aiter__(self):
        return self

    async def __anext__(self) -> BaseEvent:
        return await self.get()

    async def get(self) -> BaseEvent:
        return await self._queue.get()

    async def start(self):
        if self._runner is not None:
            raise RuntimeError("Источник событий уже запущен")
        self._load()
        if self.client.me is None:
            await self.client.refresh()
        self._runner = asyncio.ensure_future(self._run())

    async def close(self):
        runner, self._runner = self._runner, None
        tasks = [t for t in (runner, *self._tasks, *self._chat_workers.values()) if t is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._chat_workers.clear()
        self._chat_queues.clear()
        if self._socket is not None:
            await self._socket.close()
            self._socket = None
        self._save(force=True)

    # --- состояние ---

    def _load(self):
        state = self.store.load()
        if not state:
            return
        self._first_run = False
        if state.get("watermark"):
            try: self._watermark = _utc(datetime.fromisoformat(state["watermark"]))
            except ValueError: self._watermark = None
        for msg_id in state.get("seen", []):
            self._seen.add(msg_id)
        for order_id, info in (state.get("orders") or {}).items():
            self._orders[order_id] = {"status": info.get("status"), "events": list(info.get("events", []))}
        self._chat_last.update(state.get("chats") or {})

    def _save(self, force: bool = False):
        if not self._dirty and not force:
            return
        if not force and _now() - self._last_save < self.save_interval:
            return
        while len(self._orders) > 1000:
            self._orders.popitem(last=False)
        while len(self._chat_last) > 300:
            self._chat_last.popitem(last=False)
        state = {
            "watermark": self._watermark.isoformat() if self._watermark else None,
            "seen": self._seen.tail(500),
            "orders": dict(self._orders),
            "chats": dict(self._chat_last),
        }
        try:
            self.store.save(state)
            self._dirty = False
            self._last_save = _now()
        except Exception:
            logger.warning(f"Не удалось сохранить состояние событий: {traceback.format_exc()}")

    def _touch(self, dt: datetime | None):
        dt = _utc(dt)
        if dt is not None and (self._watermark is None or dt > self._watermark):
            self._watermark = dt
            self._dirty = True

    def _threshold(self) -> datetime | None:
        return self._watermark - self.catch_up_margin if self._watermark else None

    # --- основной цикл ---

    def _set_mode(self, mode: Mode):
        if self.mode != mode:
            if mode == "socket":
                logger.info("События Starvell: подключён сокет")
            else:
                logger.warning(f"События Starvell: сокет недоступен, опрашиваю сайт (новая попытка сокета через {self.socket_retry_interval:.0f} сек.)")
            self.mode = mode

    async def _run(self):
        await self._safe(self._sync(initial=True))
        failures = 0
        socket_retry_at = 0.0
        while True:
            if self.use_socket and _now() >= socket_retry_at:
                connected_at = await self._socket_session()
                if connected_at is not None and _now() - connected_at >= self.stable_after:
                    failures = 0
                else:
                    failures += 1
                if failures >= self.max_socket_failures:
                    failures = 0
                    socket_retry_at = _now() + self.socket_retry_interval
                    self._set_mode("polling")
                    continue
                await _sleep(self.reconnect_delays[min(failures, len(self.reconnect_delays) - 1)])
                continue
            self._set_mode("polling")
            await self._poll_until(socket_retry_at if self.use_socket else None)

    async def _socket_session(self) -> float | None:
        sio = SocketIO(self.client._http.transport, self.socket_url, self.client._http.socket_headers, NAMESPACES)
        try:
            await sio.connect()
        except UnauthorizedError as e:
            logger.error(f"События Starvell: {e}")
            await _sleep(60)
            return None
        except SocketClosed as e:
            logger.debug(f"Не удалось подключить сокет Starvell: {e}")
            return None
        self._socket = sio
        connected_at = _now()
        self._set_mode("socket")
        # догоняем и после первого подключения: между стартовым догоном и сокетом могли прийти сообщения
        self._spawn(self._safe(self._sync()))
        try:
            async for namespace, name, args in sio.events():
                try:
                    await self._on_socket(namespace, name, args)
                except Exception:
                    logger.error(f"Ошибка разбора события сокета {namespace} {name}: {traceback.format_exc()}")
                self._save()
        except SocketClosed as e:
            logger.info(f"Сокет Starvell отключился: {e}, переподключаюсь")
        finally:
            self._socket = None
            await sio.close()
        return connected_at

    async def _poll_until(self, until: float | None):
        next_chats = next_orders = 0.0
        while until is None or _now() < until:
            now = _now()
            if now >= next_chats:
                await self._safe(self._sync_chats())
                next_chats = now + self.poll_chats_interval
            if now >= next_orders:
                await self._safe(self._sync_orders())
                next_orders = now + self.poll_orders_interval
            self._save()
            await _sleep(1.0)

    async def _safe(self, coro):
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except UnauthorizedError as e:
            logger.error(f"События Starvell: {e}")
            await _sleep(30)
        except StarvellError as e:
            logger.warning(f"События Starvell: {e}")
        except Exception:
            logger.error(f"Ошибка в источнике событий Starvell: {traceback.format_exc()}")

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    # --- сокет ---

    async def _on_socket(self, namespace: str, name: str, args: list[Any]):
        payload = args[0] if args and isinstance(args[0], dict) else {}
        if self.socket_events:
            self._emit(SocketEvent(namespace=namespace, name=name, args=args, raw={"args": args}))

        if namespace == "/chats" and name == "message_created":
            self._feed(Message.model_validate(payload), payload)
        elif namespace == "/chats" and name == "chat_read":
            self._emit(ChatReadEvent(read=ChatRead.model_validate(payload), raw=payload))
        elif name == "sale_update":
            notice = OrderNotice.model_validate(payload)
            if notice.order_id:
                self._spawn(self._safe(self._order_fallback(notice.order_id)))
        elif name == "order_refunded_global":
            order_id = payload.get("orderId") or payload.get("id")
            if order_id:
                self._spawn(self._safe(self._check_order(str(order_id))))
        elif name == "balance_updated":
            self._emit(BalanceUpdatedEvent(balance=BalanceUpdate.model_validate(payload), raw=payload))
        elif name == "kyc_status_updated":
            self._emit(KycStatusUpdatedEvent(data=payload, raw=payload))

    # --- сообщения (очередь на чат) ---

    def _feed(self, message: Message, raw: dict[str, Any]):
        if not message.id or not message.chat_id:
            return
        queue = self._chat_queues.get(message.chat_id)
        if queue is None:
            queue = self._chat_queues[message.chat_id] = asyncio.Queue()
            self._chat_workers[message.chat_id] = asyncio.ensure_future(self._chat_worker(message.chat_id, queue))
        queue.put_nowait((message, raw))

    async def _chat_worker(self, chat_id: str, queue: asyncio.Queue):
        try:
            while True:
                try:
                    message, raw = await asyncio.wait_for(queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    if queue.empty():
                        return
                    continue
                await self._safe(self._process_message(message, raw))
        finally:
            if self._chat_queues.get(chat_id) is queue:
                del self._chat_queues[chat_id]
                self._chat_workers.pop(chat_id, None)

    async def _process_message(self, message: Message, raw: dict[str, Any]):
        if not self._seen.add(message.id):
            return
        self._dirty = True
        self._touch(message.created_at)
        self._chat_last[message.chat_id] = message.id
        self._chat_last.move_to_end(message.chat_id)

        for user in (message.buyer, message.author):
            if user is not None and user.id is not None and user.id != self.client.id:
                self._chat_by_user[user.id] = message.chat_id

        if message.is_notification and message.order_id:
            await self._order_from_message(message)

        mine = message.author_id is not None and message.author_id == self.client.id
        if mine and not self.own_messages:
            return
        self._emit(NewMessageEvent(message=message, raw=raw))

    # --- заказы ---

    def _claim(self, order_id: str, event: str) -> bool:
        info = self._orders.setdefault(order_id, {"status": None, "events": []})
        self._orders.move_to_end(order_id)
        if event in info["events"]:
            return False
        info["events"].append(event)
        self._dirty = True
        return True

    async def _fetch_order(self, order_id: str) -> Order | None:
        for attempt in range(self.order_fetch_retries):
            try:
                return await self.client.get_order(order_id)
            except UnauthorizedError:
                raise
            except StarvellError as e:
                logger.debug(f"Не удалось получить заказ {order_id}: {e}")
                await _sleep(2 * (attempt + 1))
        return None

    async def _order_from_message(self, message: Message):
        order = await self._fetch_order(message.order_id) or message.order
        if order is None:
            return
        if order.seller_id is not None and order.seller_id != self.client.id:
            return
        kind = message.notification_type
        event_cls = ORDER_EVENTS.get(kind) if kind else None
        if event_cls is None:
            status = str(order.status) if order.status else None
            known = (self._orders.get(order.id) or {}).get("status")
            if known == status:
                return
            if known is None and order.status not in STATUS_EVENTS:
                # первое упоминание заказа без смены статуса (напоминание об оплате и т.п.) - только запоминаем
                self._orders.setdefault(order.id, {"status": status, "events": []})["status"] = status
                self._dirty = True
                return
            event_cls = STATUS_EVENTS.get(order.status, OrderStatusChangedEvent)
        self._emit_order(event_cls, order, message.chat_id, message, kind)

    def _emit_order(
        self,
        event_cls: type[_OrderEvent],
        order: Order,
        chat_id: str | None,
        message: Message | None = None,
        kind: str | None = None,
        previous_status: str | None = None
    ):
        key = event_cls.type.value if event_cls is not OrderStatusChangedEvent else f"{event_cls.type.value}:{order.status}"
        info = self._orders.get(order.id) or {}
        previous_status = previous_status or info.get("status")
        if not self._claim(order.id, key):
            self._orders[order.id]["status"] = str(order.status) if order.status else None
            return
        self._orders[order.id]["status"] = str(order.status) if order.status else None
        self._touch(order.sort_at or order.paid_at or order.created_at)
        kwargs: dict[str, Any] = {"order": order, "chat_id": chat_id, "message": message, "notification_type": kind,
                                  "raw": order.model_dump(mode="json", by_alias=True, exclude_none=True)}
        if event_cls is OrderStatusChangedEvent:
            kwargs["previous_status"] = previous_status
        self._emit(event_cls(**kwargs))

    async def _order_fallback(self, order_id: str):
        # sale_update приходит раньше уведомления в чате; если уведомления так и нет - находим чат сами
        await _sleep(self.order_chat_wait)
        info = self._orders.get(order_id)
        if info and NewOrderEvent.type.value in info["events"]:
            return
        order = await self._fetch_order(order_id)
        if order is None or not order.is_paid:
            return
        chat_id = await self._find_chat(order.buyer_id)
        logger.debug(f"Заказ {order.short_id}: уведомление в чате не пришло, событие по sale_update")
        self._emit_order(NewOrderEvent, order, chat_id)

    async def _check_order(self, order_id: str):
        order = await self._fetch_order(order_id)
        if order is None or (order.seller_id is not None and order.seller_id != self.client.id):
            return
        info = self._orders.get(order_id) or {}
        if info.get("status") == str(order.status):
            return
        event_cls = STATUS_EVENTS.get(order.status, OrderStatusChangedEvent)
        self._emit_order(event_cls, order, await self._find_chat(order.buyer_id))

    async def _find_chat(self, user_id: int | None) -> str | None:
        if user_id is None:
            return None
        if user_id in self._chat_by_user:
            return self._chat_by_user[user_id]
        for chat in await self.client.get_chats(limit=50):
            for user in chat.participants:
                if user.id is not None and user.id != self.client.id:
                    self._chat_by_user.setdefault(user.id, chat.id)
        return self._chat_by_user.get(user_id)

    # --- догон и опрос ---

    async def _sync(self, initial: bool = False):
        await self._sync_orders(initial)
        await self._sync_chats(initial)
        self._first_run = False
        self._save(force=True)

    async def _sync_chats(self, initial: bool = False):
        chats: list[Chat] = await self.client.get_chats(limit=self.sync_chats_limit)
        threshold = self._threshold()
        for chat in reversed(chats):
            for user in chat.participants:
                if user.id is not None and user.id != self.client.id:
                    self._chat_by_user[user.id] = chat.id
            last = chat.last_message
            if last is None or not last.id or last.id in self._seen:
                continue
            created = _utc(last.created_at)
            if self._first_run:
                # первый запуск: старое не выдаём, только запоминаем, откуда считать новое
                self._seen.add(last.id)
                self._chat_last[chat.id] = last.id
                self._touch(created)
                continue
            if threshold is not None and created is not None and created < threshold:
                self._seen.add(last.id)
                continue
            page = await self.client.get_messages(chat.id, limit=20)
            for message in sorted(page.items, key=lambda m: _utc(m.created_at) or datetime.min.replace(tzinfo=timezone.utc)):
                if message.id in self._seen:
                    continue
                m_created = _utc(message.created_at)
                if threshold is not None and m_created is not None and m_created < threshold:
                    self._seen.add(message.id)
                    continue
                self._feed(message, message.model_dump(mode="json", by_alias=True, exclude_none=True))

    async def _sync_orders(self, initial: bool = False):
        orders: list[Order] = await self.client.get_orders(UserType.SELLER, limit=self.sync_orders_limit)
        threshold = self._threshold()
        for short in reversed(orders):
            if not short.id:
                continue
            info = self._orders.get(short.id)
            status = str(short.status) if short.status else None
            if self._first_run:
                self._orders[short.id] = {"status": status, "events": [NewOrderEvent.type.value] if short.is_paid else []}
                self._touch(short.sort_at or short.created_at)
                self._dirty = True
                continue
            if info is None:
                if not short.is_paid:
                    continue
                when = _utc(short.sort_at or short.created_at)
                if threshold is not None and when is not None and when < threshold:
                    self._orders[short.id] = {"status": status, "events": [NewOrderEvent.type.value]}
                    continue
                order = await self._fetch_order(short.id) or short
                if order.is_closed or order.seller_completed_at is not None:
                    # заказ закрыли или выполнили, пока бот был выключен - выдавать по нему уже нечего
                    self._orders[short.id] = {"status": status, "events": [NewOrderEvent.type.value]}
                    self._dirty = True
                    continue
                buyer_id = order.buyer_id or (short.user.id if short.user else None)
                self._emit_order(NewOrderEvent, order, await self._find_chat(buyer_id))
            elif info.get("status") != status:
                order = await self._fetch_order(short.id) or short
                event_cls = STATUS_EVENTS.get(order.status, OrderStatusChangedEvent)
                self._emit_order(event_cls, order, await self._find_chat(order.buyer_id), previous_status=info.get("status"))

    def _emit(self, event: BaseEvent):
        if event.client is None:
            event.client = self.client
        self._queue.put_nowait(event)
