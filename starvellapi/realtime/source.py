from __future__ import annotations

import asyncio
import time
import traceback
from collections import OrderedDict, deque
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import TYPE_CHECKING, Any, Literal

from pydantic import ValidationError

from .._http import SOCKET_URL
from ..dispatcher.events import (
    BalanceUpdatedEvent,
    BaseEvent,
    ChatReadEvent,
    ConnectionStatusEvent,
    KycStatusUpdatedEvent,
    NewMessageEvent,
    NewOrderEvent,
    OrderCompletedEvent,
    OrderRefundedEvent,
    OrderSellerCompletedEvent,
    OrderStatusChangedEvent,
    SocketEvent,
    _OrderEvent,
)
from ..errors import BotCheckError, SourceClosedError, StarvellError, UnauthorizedError
from ..models import BalanceUpdate, ChatRead, Message, NotificationType, Order, OrderNotice, OrderStatus, UserType
from .engineio import SocketClosed, SocketIO
from .state import MemoryState, StateStore

if TYPE_CHECKING:
    from ..client import Client


logger = getLogger("starvellapi.realtime")

_sleep = asyncio.sleep
_now = time.monotonic

Mode = Literal["socket", "polling"]

NAMESPACES = ["/chats", "/user-notifications"]
NEW_ORDER = NewOrderEvent.type.value
STATUS_EVENTS: dict[str, type[_OrderEvent]] = {
    OrderStatus.COMPLETED: OrderCompletedEvent,
    OrderStatus.REFUND: OrderRefundedEvent,
}
_CLOSED = object()


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _status(order: Order) -> str | None:
    return str(order.status) if order.status else None


def _raw(model) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


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
    источник опрашивает REST и раз в `socket_retry_interval` пробует вернуться на сокет.
    После каждого подключения и перезапуска догоняет пропущенное: незакрытые оплаченные заказы и сообщения
    после последнего подтверждённого. События одного чата выходят по порядку.

    Событие считается обработанным только после `ack(event)` (`Dispatcher` подтверждает сам, после хендлеров).
    Неподтверждённое к перезапуску событие придёт снова, поэтому изменяющие действия в хендлерах
    (выдача товара) должны помнить, что уже сделано.

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
    order_retry_delays = (5.0, 15.0, 30.0, 60.0, 120.0)
    new_chat_margin = timedelta(seconds=30)
    save_interval = 5.0
    sync_chats_limit = 20
    sync_orders_limit = 30
    chat_pages = 5

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

        self._queue: asyncio.Queue = asyncio.Queue()
        self._tasks: set[asyncio.Task] = set()
        self._chat_queues: dict[str, deque] = {}
        self._chat_workers: dict[str, asyncio.Task] = {}
        self._socket: SocketIO | None = None
        self._runner: asyncio.Task | None = None
        self._saver: asyncio.Task | None = None
        self._sync_task: asyncio.Task | None = None
        self._held: list | None = None
        self._closed = False
        self._last_status: tuple | None = None

        # подтверждённое (уходит в state)
        self._initialized = False
        self._p_orders: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._p_seen = _Seen(1000)
        self._p_chats: OrderedDict[str, str] = OrderedDict()
        self._watermark: datetime | None = None
        # в памяти процесса
        self._seen = _Seen(5000)
        self._claimed: set[tuple[str, str]] = set()
        self._order_status: dict[str, str | None] = {}
        self._retrying: set[str] = set()
        self._chat_by_user: OrderedDict[int, str] = OrderedDict()
        self._dirty = False
        self._last_save = 0.0

    def __aiter__(self):
        return self

    async def __anext__(self) -> BaseEvent:
        try:
            return await self.get()
        except SourceClosedError:
            raise StopAsyncIteration from None

    async def get(self) -> BaseEvent:
        if self._closed and self._queue.empty():
            raise SourceClosedError()
        item = await self._queue.get()
        if item is _CLOSED:
            self._queue.put_nowait(_CLOSED)
            raise SourceClosedError()
        return item

    async def start(self):
        if self._runner is not None:
            raise RuntimeError("Источник событий уже запущен")
        self._load()
        if self.client.me is None:
            await self.client.refresh()
        self._runner = asyncio.ensure_future(self._run())
        self._runner.add_done_callback(self._on_runner_done)
        self._saver = asyncio.ensure_future(self._save_loop())

    async def close(self):
        if self._closed:
            return
        self._closed = True
        tasks = [t for t in (self._runner, self._saver, self._sync_task, *self._tasks, *self._chat_workers.values()) if t is not None]
        self._runner = self._saver = self._sync_task = None
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
        self._queue.put_nowait(_CLOSED)

    def _on_runner_done(self, task: asyncio.Task):
        if not task.cancelled() and task.exception() is not None:
            logger.critical(f"Источник событий Starvell остановился: {task.exception()!r}")

    # --- подтверждение и состояние ---

    def ack(self, event: BaseEvent):
        """
        Подтверждает, что событие обработано: после перезапуска оно не придёт снова.
        """
        token, event.ack_token = event.ack_token, None
        if not token:
            return
        if token[0] == "message":
            self._ack_message(*token[1:])
            self._save()
        elif token[0] == "order":
            _, order_id, key, status = token
            self._record(order_id, key, status)
            # заказы пишем сразу: от этого зависит, не выдастся ли товар второй раз после падения
            self._save(force=True)

    def _ack_message(self, msg_id: str, chat_id: str | None, created: str | None):
        self._p_seen.add(msg_id)
        if chat_id:
            self._p_chats[chat_id] = msg_id
            self._p_chats.move_to_end(chat_id)
        if created:
            self._advance(_utc(datetime.fromisoformat(created)))
        self._dirty = True

    def _record(self, order_id: str, key: str | None, status: str | None):
        info = self._p_orders.setdefault(order_id, {"status": status, "events": []})
        if key and key not in info["events"]:
            info["events"].append(key)
        info["status"] = status
        self._p_orders.move_to_end(order_id)
        self._dirty = True

    def _advance(self, dt: datetime | None):
        if dt is not None and (self._watermark is None or dt > self._watermark):
            self._watermark = dt
            self._dirty = True

    def _load(self):
        state = self.store.load() or {}
        self._initialized = bool(state.get("initialized"))
        if state.get("watermark"):
            try: self._watermark = _utc(datetime.fromisoformat(state["watermark"]))
            except ValueError: self._watermark = None
        for msg_id in state.get("seen") or []:
            self._p_seen.add(msg_id)
            self._seen.add(msg_id)
        for order_id, info in (state.get("orders") or {}).items():
            if isinstance(info, dict):
                self._p_orders[order_id] = {"status": info.get("status"), "events": list(info.get("events") or [])}
                self._order_status[order_id] = info.get("status")
        for chat_id, msg_id in (state.get("chats") or {}).items():
            self._p_chats[chat_id] = msg_id

    def _save(self, force: bool = False):
        if not self._initialized or (not self._dirty and not force):
            return
        if not force and _now() - self._last_save < self.save_interval:
            return
        while len(self._p_orders) > 1500:
            self._p_orders.popitem(last=False)
        while len(self._p_chats) > 500:
            self._p_chats.popitem(last=False)
        state = {
            "version": 2,
            "initialized": True,
            "watermark": self._watermark.isoformat() if self._watermark else None,
            "seen": self._p_seen.tail(1000),
            "orders": dict(self._p_orders),
            "chats": dict(self._p_chats),
        }
        try:
            self.store.save(state)
            self._dirty = False
            self._last_save = _now()
        except Exception:
            logger.warning(f"Не удалось сохранить состояние событий: {traceback.format_exc()}")

    async def _save_loop(self):
        while True:
            await _sleep(self.save_interval)
            self._save()

    # --- основной цикл ---

    def _set_mode(self, mode: Mode):
        if self.mode == mode:
            return
        self.mode = mode
        if mode == "socket":
            logger.info("События Starvell: подключён сокет")
        else:
            logger.warning(f"События Starvell: сокет недоступен, опрашиваю сайт (новая попытка сокета через {self.socket_retry_interval:.0f} сек.)")
        self._connection_status(mode)

    def _connection_status(self, status: str, error: BaseException | None = None):
        key = (status, type(error).__name__ if error else None)
        if key == self._last_status:
            return
        self._last_status = key
        self._emit(ConnectionStatusEvent(status=status, error=str(error) if error else None))

    async def _run(self):
        delay = 5.0
        while True:
            error = await self._safe(self._sync())
            if error is None or self._initialized:
                break
            # первый запуск без успешного догона: иначе не понять, какие заказы старые
            logger.warning(f"События Starvell: не удалось получить начальное состояние, повтор через {delay:.0f} сек.")
            await _sleep(delay)
            delay = min(delay * 2, 120)

        failures = 0
        socket_retry_at = 0.0
        while True:
            try:
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
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error(f"Ошибка в цикле событий Starvell: {traceback.format_exc()}")
                await _sleep(5)

    async def _socket_session(self) -> float | None:
        sio = SocketIO(self.client._http.transport, self.socket_url, self.client._http.socket_headers, NAMESPACES)
        try:
            await sio.connect()
        except UnauthorizedError as e:
            logger.error(f"События Starvell: {e}")
            self._connection_status("unauthorized", e)
            await _sleep(60)
            return None
        except SocketClosed as e:
            logger.debug(f"Не удалось подключить сокет Starvell: {e}")
            return None
        self._socket = sio
        connected_at = _now()
        self._set_mode("socket")
        # пока догоняем пропущенное, сообщения сокета придерживаем - так порядок в чате не нарушится
        self._held = []
        self._start_sync()
        try:
            async for namespace, name, args in sio.events():
                try:
                    await self._on_socket(namespace, name, args)
                except Exception:
                    logger.error(f"Ошибка разбора события сокета {namespace} {name}: {traceback.format_exc()}")
        except SocketClosed as e:
            logger.info(f"Сокет Starvell отключился: {e}, переподключаюсь")
        finally:
            self._socket = None
            await sio.close()
            if self._sync_task is None or self._sync_task.done():
                self._flush_held()
        return connected_at

    def _start_sync(self):
        if self._sync_task is not None and not self._sync_task.done():
            return
        self._sync_task = asyncio.ensure_future(self._sync_and_flush())

    async def _sync_and_flush(self):
        try:
            await self._safe(self._sync())
        finally:
            self._flush_held()

    def _flush_held(self):
        held, self._held = self._held, None
        for message, raw in held or []:
            self._feed(message, raw)

    async def _poll_until(self, until: float | None):
        next_chats = next_orders = 0.0
        backoff = 0
        while until is None or _now() < until:
            now = _now()
            errors = []
            if now >= next_chats:
                errors.append(await self._safe(self._sync_chats()))
                next_chats = now + self.poll_chats_interval
            if now >= next_orders:
                errors.append(await self._safe(self._sync_orders()))
                next_orders = now + self.poll_orders_interval
            if any(isinstance(e, BotCheckError) for e in errors):
                # QRATOR: частые запросы только продлят блокировку
                backoff += 1
                await _sleep(min(60 * 2 ** (backoff - 1), 900))
                continue
            if errors and all(e is None for e in errors):
                backoff = 0
                if self._last_status and self._last_status[0] != "polling":
                    self._connection_status("polling")
            await _sleep(1.0)

    async def _safe(self, coro) -> BaseException | None:
        try:
            await coro
            return None
        except asyncio.CancelledError:
            raise
        except UnauthorizedError as e:
            logger.error(f"События Starvell: {e}")
            self._connection_status("unauthorized", e)
            await _sleep(30)
            return e
        except BotCheckError as e:
            logger.warning(f"События Starvell: {e}")
            self._connection_status("bot_check", e)
            return e
        except StarvellError as e:
            logger.warning(f"События Starvell: {e}")
            return e
        except Exception as e:
            logger.error(f"Ошибка в источнике событий Starvell: {traceback.format_exc()}")
            return e

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
            message = Message.model_validate(payload)
            if self._held is not None:
                self._held.append((message, payload))
            else:
                self._feed(message, payload)
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
        if not message.id or not message.chat_id or not self._seen.add(message.id):
            return
        queue = self._chat_queues.get(message.chat_id)
        if queue is None:
            queue = self._chat_queues[message.chat_id] = deque()
        queue.append((message, raw))
        if message.chat_id not in self._chat_workers:
            self._chat_workers[message.chat_id] = asyncio.ensure_future(self._chat_worker(message.chat_id, queue))

    async def _chat_worker(self, chat_id: str, queue: deque):
        try:
            while queue:
                message, raw = queue.popleft()
                await self._safe(self._process_message(message, raw))
        finally:
            # без await между проверкой очереди и удалением воркера - новое сообщение запустит новый воркер
            if self._chat_workers.get(chat_id) is asyncio.current_task():
                del self._chat_workers[chat_id]
            if not queue and self._chat_queues.get(chat_id) is queue:
                del self._chat_queues[chat_id]

    async def _process_message(self, message: Message, raw: dict[str, Any]):
        self._remember_chat(message)
        mine = message.author_id is not None and message.author_id == self.client.id
        created = _utc(message.created_at)
        token = ("message", message.id, message.chat_id, created.isoformat() if created else None)
        try:
            if message.is_notification and message.order_id:
                await self._order_from_message(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error(f"Ошибка разбора заказа из сообщения {message.id}: {traceback.format_exc()}")
        finally:
            if mine and not self.own_messages:
                self._ack_message(*token[1:])
            else:
                self._emit(NewMessageEvent(message=message, raw=raw), token)

    def _remember_chat(self, message: Message):
        for user in (message.buyer, message.seller, message.author):
            if user is not None and user.id is not None and user.id != self.client.id:
                self._chat_by_user[user.id] = message.chat_id
                self._chat_by_user.move_to_end(user.id)
        while len(self._chat_by_user) > 2000:
            self._chat_by_user.popitem(last=False)

    # --- заказы ---

    def _done(self, order_id: str, key: str) -> bool:
        return (order_id, key) in self._claimed or key in (self._p_orders.get(order_id) or {}).get("events", [])

    async def _fetch_order(self, order_id: str) -> Order | None:
        for attempt in range(self.order_fetch_retries):
            try:
                return await self.client.get_order(order_id)
            except UnauthorizedError:
                raise
            except (StarvellError, ValidationError) as e:
                logger.debug(f"Не удалось получить заказ {order_id}: {e}")
                if attempt < self.order_fetch_retries - 1:
                    await _sleep(2 * (attempt + 1))
        return None

    async def _order_from_message(self, message: Message):
        order = await self._fetch_order(message.order_id)
        if order is None:
            self._retry_later(message.order_id, message.chat_id, message, message.notification_type)
            return
        await self._handle_order(order, message.chat_id, message, message.notification_type)

    def _retry_later(self, order_id: str, chat_id: str | None, message: Message | None, kind: str | None):
        if order_id in self._retrying or self._closed:
            return
        self._retrying.add(order_id)

        async def retry():
            try:
                for delay in self.order_retry_delays:
                    await _sleep(delay)
                    order = await self._fetch_order(order_id)
                    if order is not None:
                        await self._handle_order(order, chat_id, message, kind)
                        return
                logger.error(f"Не удалось получить заказ {order_id} с Starvell: событие по нему не выдано, проверьте заказ вручную")
            finally:
                self._retrying.discard(order_id)
        self._spawn(self._safe(retry()))

    async def _handle_order(
        self,
        order: Order,
        chat_id: str | None,
        message: Message | None,
        kind: str | None,
        catch_up: bool = False
    ):
        if not order.id or order.seller_id is None or order.seller_id != self.client.id:
            # своя покупка или заказ без продавца - не наша продажа
            return
        status = _status(order)
        if kind == NotificationType.ORDER_PAYMENT or (kind is None and order.is_paid):
            await self._maybe_new_order(order, chat_id, message, kind, catch_up)
        if kind == NotificationType.ORDER_SELLER_COMPLETED:
            self._emit_order(OrderSellerCompletedEvent, order, chat_id, message, kind, OrderSellerCompletedEvent.type.value)
        if kind == NotificationType.ORDER_REFUND:
            self._emit_order(OrderRefundedEvent, order, chat_id, message, kind, OrderRefundedEvent.type.value)

        previous = self._order_status.get(order.id)
        if previous is not None and previous != status:
            cls = STATUS_EVENTS.get(order.status, OrderStatusChangedEvent)
            key = cls.type.value if cls is not OrderStatusChangedEvent else f"{cls.type.value}:{status}"
            self._emit_order(cls, order, chat_id, message, kind, key, catch_up, previous)
        self._order_status[order.id] = status

    async def _maybe_new_order(self, order: Order, chat_id: str | None, message: Message | None, kind: str | None, catch_up: bool):
        if self._done(order.id, NEW_ORDER) or not order.is_paid:
            return
        if order.is_closed or (catch_up and order.seller_completed_at is not None):
            # закрыт или уже выполнен, пока бот не видел, - выдавать нечего
            self._record(order.id, NEW_ORDER, _status(order))
            return
        if chat_id is None:
            chat_id = await self._find_chat(order)
            if chat_id is None:
                logger.warning(f"Не нашёл чат с покупателем по заказу {order.short_id or order.id}")
        self._emit_order(NewOrderEvent, order, chat_id, message, kind, NEW_ORDER, catch_up)

    def _emit_order(
        self,
        cls: type[_OrderEvent],
        order: Order,
        chat_id: str | None,
        message: Message | None,
        kind: str | None,
        key: str,
        catch_up: bool = False,
        previous_status: str | None = None
    ):
        if self._done(order.id, key):
            return
        kwargs: dict[str, Any] = {"order": order, "chat_id": chat_id, "message": message, "notification_type": kind,
                                  "catch_up": catch_up, "raw": _raw(order)}
        if cls is OrderStatusChangedEvent:
            kwargs["previous_status"] = previous_status
        event = cls(**kwargs)
        self._claimed.add((order.id, key))
        self._emit(event, ("order", order.id, key, _status(order)))

    async def _order_fallback(self, order_id: str):
        # sale_update приходит раньше уведомления в чате; если уведомления так и нет - находим чат сами
        await _sleep(self.order_chat_wait)
        if self._done(order_id, NEW_ORDER):
            return
        order = await self._fetch_order(order_id)
        if order is None:
            self._retry_later(order_id, None, None, None)
            return
        logger.debug(f"Заказ {order.short_id}: уведомление в чате не пришло, событие по sale_update")
        await self._handle_order(order, None, None, None)

    async def _check_order(self, order_id: str):
        order = await self._fetch_order(order_id)
        if order is not None:
            await self._handle_order(order, None, None, None)

    async def _find_chat(self, order: Order) -> str | None:
        user_id = order.buyer_id or (order.user.id if order.user else None)
        if user_id is None:
            return None
        if user_id in self._chat_by_user:
            return self._chat_by_user[user_id]
        for method in (self.client.get_chats_with_open_orders, self.client.get_chats):
            try:
                chats = await method(limit=50)
            except UnauthorizedError:
                raise
            except Exception as e:
                logger.debug(f"Поиск чата с покупателем: {e}")
                continue
            for chat in chats:
                for user in chat.participants:
                    if user.id is not None and user.id != self.client.id and chat.id:
                        self._chat_by_user[user.id] = chat.id
            if user_id in self._chat_by_user:
                return self._chat_by_user[user_id]
        return None

    # --- догон и опрос ---

    async def _sync(self):
        await self._sync_orders()
        await self._sync_chats()
        if not self._initialized:
            self._initialized = True
            self._save(force=True)

    async def _sync_orders(self):
        orders: list[Order] = await self.client.get_orders(UserType.SELLER, limit=self.sync_orders_limit)
        for short in reversed(orders):
            if not short.id:
                continue
            status = _status(short)
            if not self._initialized:
                # первый запуск: всё, что уже есть, считаем обработанным
                self._record(short.id, NEW_ORDER if short.is_paid else None, status)
                self._order_status[short.id] = status
                continue
            need_new = short.is_paid and not short.is_closed and not self._done(short.id, NEW_ORDER)
            previous = self._order_status.get(short.id)
            if not need_new and (previous is None or previous == status):
                self._order_status.setdefault(short.id, status)
                continue
            order = await self._fetch_order(short.id)
            if order is None:
                continue
            await self._handle_order(order, None, None, None, catch_up=True)

    async def _sync_chats(self):
        chats = await self.client.get_chats(limit=self.sync_chats_limit)
        for chat in reversed(chats):
            if not chat.id:
                continue
            for user in chat.participants:
                if user.id is not None and user.id != self.client.id:
                    self._chat_by_user[user.id] = chat.id
            last = chat.last_message
            if last is None or not last.id:
                continue
            if not self._initialized:
                created = _utc(last.created_at)
                self._seen.add(last.id)
                self._ack_message(last.id, chat.id, created.isoformat() if created else None)
                continue
            if last.id in self._seen:
                continue
            for message in await self._missed_messages(chat.id):
                self._feed(message, _raw(message))

    async def _missed_messages(self, chat_id: str) -> list[Message]:
        after = self._p_chats.get(chat_id)
        collected: dict[str, Message] = {}
        if after:
            try:
                for _ in range(self.chat_pages):
                    page = await self.client.get_messages(chat_id, limit=50, after_id=after)
                    for m in page.items:
                        if m.id:
                            collected[m.id] = m
                    if not page.has_more_after or not page.items:
                        break
                    newest = max(page.items, key=lambda m: _utc(m.created_at) or datetime.min.replace(tzinfo=timezone.utc))
                    if newest.id == after:
                        break
                    after = newest.id
                return self._chronological(collected.values())
            except StarvellError as e:
                logger.debug(f"Догон чата {chat_id} от {after}: {e}, беру последние сообщения")
        page = await self.client.get_messages(chat_id, limit=20)
        border = self._watermark - self.new_chat_margin if self._watermark else None
        return self._chronological(
            m for m in page.items
            if m.id and (border is None or (_utc(m.created_at) is not None and _utc(m.created_at) >= border))
        )

    @staticmethod
    def _chronological(messages) -> list[Message]:
        return sorted(messages, key=lambda m: _utc(m.created_at) or datetime.min.replace(tzinfo=timezone.utc))

    def _emit(self, event: BaseEvent, token: Any = None):
        if event.client is None:
            event.client = self.client
        event.ack_token = token
        self._queue.put_nowait(event)
