from __future__ import annotations
import sys
import time
import asyncio
import logging
import itertools
import traceback
from html import escape
from logging import getLogger
from colorama import Fore

from starvellapi import (
    Client,
    ThreadsafeClient,
    call_in_loop,
    EventSource,
    JsonFileState,
    EventType,
    NewMessageEvent,
    NewOrderEvent,
    OrderSellerCompletedEvent,
    OrderCompletedEvent,
    OrderRefundedEvent,
    OrderStatusChangedEvent,
    ConnectionStatusEvent,
    BalanceUpdatedEvent,
    StarvellError,
)
from starvellapi.errors import APIError
from starvellapi.models import Message, Order

from __init__ import VERSION
from core.utils import set_title, shutdown, acquire_account_lock
from core.handlers import add_bot_event_handler, add_starvell_event_handler, call_bot_event, call_starvell_event
from core.blacklist import is_blacklisted, get_blacklist_entry
from settings import DATA, Settings as sett
from data import Data as data
from tgbot.telegrambot import get_telegram_bot, get_telegram_bot_loop
from tgbot.templates import (
    log_text,
    log_new_mess_kb,
    log_new_order_kb,
    log_order_kb,
    log_blacklisted_order_kb,
    destroy_kb,
)

from .deliveries import find_bindings, offer_matches, ensure_binding_ids, find_binding
from .msg_types import (
    ORDER_STATUSES,
    MsgUser,
    format_text,
    msg_account,
    msg_chat,
    msg_order,
    msg_user,
)


logger = getLogger("universal.starvell")

EVENTS_STATE_PATH = "bot_data/starvell_events.json"
MESSAGE_LIMIT = 1000
STAFF_ROLES = {"MODERATOR", "SUPPORT", "ARBITRAGE", "ADMIN"}
BUMP_COOLDOWN = 4 * 60 * 60
BUMP_EMPTY_RECHECK = 60 * 60
BUMP_EMPTY = -1.0

NOTIFICATION_LABELS = {
    "ORDER_PAYMENT": "Заказ оплачен",
    "ORDER_SELLER_COMPLETED": "Продавец выполнил заказ",
    "ORDER_REFUND": "Оформлен возврат",
    "ORDER_NOT_PAID_REMINDER": "Напоминание об оплате",
    "ORDER_COMPLETED": "Покупатель подтвердил заказ",
    "REVIEW_CREATED": "Новый отзыв",
    "ORDER_REFUND_REASON_SET": "Указана причина возврата",
}

PRIORITY_DELIVERY = 0
PRIORITY_NORMAL = 1
PRIORITY_LOW = 2


def order_link(order_id: str | None, text: str) -> str:
    return f'<a href="https://starvell.com/order/{order_id}">{text}</a>' if order_id else text


def chat_link(chat_id: str | None, text: str) -> str:
    return f'<a href="https://starvell.com/chat/{chat_id}">{text}</a>' if chat_id else text


def rub(value) -> str:
    return f"{float(value or 0):g}₽"


def order_args_text(order: Order) -> str:
    lines = []
    for arg in order.order_args:
        value = escape(arg.value or "")
        lines.append(f"・ <b>{escape(arg.name_ru or 'Поле')}:</b> " + (f"<tg-spoiler>{value}</tg-spoiler>" if arg.is_sensitive else value))
    return "\n".join(lines)


def get_starvell_bot() -> StarvellBot | None:
    if hasattr(StarvellBot, "instance"):
        return getattr(StarvellBot, "instance")


def split_text(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    chunks, current = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current or not chunks:
        chunks.append(current)
    return chunks


class StarvellBot:
    def __new__(cls, *args, **kwargs) -> StarvellBot:
        if not hasattr(cls, "instance"):
            cls.instance = super(StarvellBot, cls).__new__(cls)
        return getattr(cls, "instance")

    def __init__(self):
        self.config = sett.get("config")
        self.messages = sett.get("messages")
        self.custom_commands = sett.get("custom_commands")
        self.auto_deliveries = sett.get("auto_deliveries")
        if ensure_binding_ids(self.auto_deliveries):
            sett.set("auto_deliveries", self.auto_deliveries)
        self.auto_complete_orders = sett.get("auto_complete_orders")

        self.initialized_users = data.get("initialized_users")
        self.cached_orders = data.get("cached_orders")
        self.bump_categories = data.get("bump_categories")

        api = self.config["starvell"]["api"]
        self.account = self.client = Client(
            session=api["session"],
            user_agent=api["user_agent"] or None,
            proxy=api["proxy"] or None,
            timeout=api["requests_timeout"] or 30
        )
        self.loop: asyncio.AbstractEventLoop | None = None
        self.sync: ThreadsafeClient | None = None
        self.source: EventSource | None = None

        self._outbox: asyncio.PriorityQueue | None = None
        self._outbox_seq = itertools.count()
        self._order_locks: dict[str, asyncio.Lock] = {}
        self._usernames: dict[str, str] = {}
        self._tasks: set[asyncio.Task] = set()
        self._bump_lock: asyncio.Lock | None = None
        self._setting_gen: dict[str, int] = {}

    # --- общее ---

    def call(self, coro):
        # из loop'а Telegram-бота и других loop'ов: await svbot.call(svbot.account.get_chats())
        return call_in_loop(coro, self.loop)

    def _spawn(self, coro) -> asyncio.Task:
        task = self.loop.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def msg(self, message_name: str, messages_config_name: str = "messages",
            messages_data: dict = DATA, **kwargs) -> str | None:
        kwargs.setdefault("account", msg_account(self.client.me))
        messages = sett.get(messages_config_name, messages_data) or {}
        mess = messages.get(message_name, {})
        if not mess.get("enabled"):
            return None
        lines: list[str] = mess.get("text", [])
        if not lines:
            return None
        return format_text("\n".join(lines), **kwargs)

    def log_to_tg(self, text: str, kb=None):
        tgbot, loop = get_telegram_bot(), get_telegram_bot_loop()
        if tgbot is None or loop is None:
            return
        asyncio.run_coroutine_threadsafe(tgbot.log_event(text=text, kb=kb), loop)

    def notify(self, event_key: str, text: str, kb=None):
        notifications = self.config["starvell"]["notifications"]
        if notifications["enabled"] and notifications["events"].get(event_key):
            self.log_to_tg(text, kb)

    def _watermarked(self, text: str) -> str:
        watermark = self.config["starvell"]["watermark"]
        if watermark["enabled"] and watermark["value"]:
            return f"{text}\n{watermark['value']}"
        return text

    def _save_setting(self, name: str):
        # ядро - единственный писатель привязок: склад списывается здесь, TG правит через edit_setting
        sett.set(name, getattr(self, name))
        self._setting_gen[name] = self._setting_gen.get(name, 0) + 1

    async def edit_setting(self, name: str, func):
        # func меняет значение на месте в loop ядра, между чтением и записью нет await
        value = getattr(self, name)
        result = func(value)
        if name == "auto_deliveries":
            ensure_binding_ids(value)
        self._save_setting(name)
        return result

    # --- отправка ---

    async def _outbox_worker(self):
        while True:
            _, _, coro_factory, future = await self._outbox.get()
            if future.cancelled():
                continue
            try:
                future.set_result(await coro_factory())
            except Exception as e:
                if not future.done():
                    future.set_exception(e)

    async def _queued(self, priority: int, coro_factory):
        # выдача товара идёт вперёд приветствий и команд, если упёрлись в лимит сообщений
        future = self.loop.create_future()
        await self._outbox.put((priority, next(self._outbox_seq), coro_factory, future))
        return await future

    async def send_message(self, chat_id: str, text: str, exclude_watermark: bool = False,
                           max_attempts: int = 3, priority: int = PRIORITY_NORMAL) -> Message | None:
        if not text:
            return None
        body = text if exclude_watermark else self._watermarked(text)
        last = None
        for chunk in split_text(body):
            last = await self._queued(priority, lambda chunk=chunk: self._send_with_retries(chat_id, chunk, max_attempts))
            if last is None:
                return None
        if self.config["starvell"]["read_chat"]:
            try: await self.client.read_chat(chat_id)
            except StarvellError: pass
        return last

    async def _send_with_retries(self, chat_id: str, text: str, max_attempts: int) -> Message | None:
        for attempt in range(1, max_attempts + 1):
            try:
                return await self.client.send_message(chat_id, text)
            except StarvellError as e:
                if getattr(e, "maybe_delivered", False):
                    # мог дойти - не дублируем, проверяем по истории
                    if await self._was_sent(chat_id, text):
                        return Message(chat_id=chat_id, content=text, author_id=self.client.id)
                logger.warning(f"{Fore.LIGHTRED_EX}Не удалось отправить сообщение в чат {chat_id} (попытка {attempt}/{max_attempts}): {Fore.WHITE}{e}")
                if attempt < max_attempts:
                    await asyncio.sleep(2 * attempt)
        return None

    async def _was_sent(self, chat_id: str, text: str, limit: int = 30) -> bool:
        try:
            page = await self.client.get_messages(chat_id, limit=limit)
        except StarvellError:
            return False
        probe = text.strip()[:300]
        return any(
            m.author_id == self.client.id and probe and probe in (m.content or "")
            for m in page.items
        )

    # --- аккаунт ---

    async def refresh_account(self):
        try:
            await self.client.refresh()
        except Exception as e:
            logger.error(f"{Fore.LIGHTRED_EX}Ошибка при обновлении аккаунта: {Fore.WHITE}{e}")
        self._set_title()

    def _set_title(self):
        me = self.client.me
        balance = me.balance.rub_balance if me and me.balance and me.balance.rub_balance is not None else "?"
        set_title(f"Starvell Universal v{VERSION} | {self.client.username}: {balance}₽")

    async def check_banned(self):
        try:
            await self.client.refresh()
            user = self.client.me.user if self.client.me else None
            if user is not None and user.is_banned:
                from core.console import log_panel
                log_panel(
                    logger, "■ Аккаунт Starvell заблокирован",
                    body="К сожалению, на заблокированном аккаунте бот работать не может.\n"
                         "Напишите в поддержку Starvell, чтобы узнать причину блокировки.",
                    level=logging.CRITICAL, color="red"
                )
                shutdown()
        except Exception as e:
            logger.error(f"{Fore.LIGHTRED_EX}Ошибка при проверке на блокировку: {Fore.WHITE}{e}")

    # --- консоль ---

    def log_new_message(self, message: Message):
        from core.console import log_panel
        author = message.author.username if message.author else "Starvell"
        text = message.text
        if message.is_notification and not text:
            short_id = message.order.short_id if message.order else (message.metadata.order_short_id if message.metadata else None)
            label = NOTIFICATION_LABELS.get(message.notification_type, str(message.notification_type or "уведомление"))
            text = f"{Fore.LIGHTBLACK_EX}*{label}{' ' + short_id if short_id else ''}*{Fore.RESET}"
        if message.images:
            text = f"{Fore.LIGHTMAGENTA_EX}*Изображения ({len(message.images)})*{Fore.RESET}" + ((" " + text) if text else "")
        log_panel(logger, f"💬 Чат с {Fore.LIGHTCYAN_EX}{self.chat_username(message.chat_id) or author}",
                  body=f"{Fore.LIGHTWHITE_EX}{author}:{Fore.RESET} {text}", color="bright_blue")

    def log_new_order(self, order: Order, buyer: str | None):
        from core.console import log_panel
        log_panel(logger, f"🛒 Новый заказ {order.short_id}", [
            ("Покупатель", buyer or "-"),
            ("Лот", order.title or "-"),
            ("Количество", order.quantity or 1),
            ("Сумма", f"{order.total_price or 0:g} ₽ {Fore.LIGHTBLACK_EX}· вам {Fore.RESET}{order.base_price or 0:g} ₽"),
        ])

    def log_order_status(self, order: Order, status_frmtd: str):
        from core.console import log_panel
        log_panel(logger, f"🔄 Заказ {order.short_id}: {status_frmtd}", [
            ("Лот", order.title or "-"),
            ("Сумма", f"{order.total_price or 0:g} ₽"),
        ], color="grey62")

    # --- кэш и помощники ---

    def chat_username(self, chat_id: str | None) -> str | None:
        return self._usernames.get(chat_id) if chat_id else None

    def _remember_username(self, chat_id: str | None, username: str | None):
        if chat_id and username:
            self._usernames[chat_id] = username

    async def buyer_username(self, chat_id: str | None, message: Message | None = None) -> str | None:
        if message is not None:
            user = message.buyer or (message.author if message.author_id != self.client.id else None)
            if user and user.username:
                self._remember_username(chat_id, user.username)
                return user.username
        if chat_id in self._usernames:
            return self._usernames[chat_id]
        if not chat_id:
            return None
        try:
            chat = await self.client.get_chat(chat_id)
            user = chat.interlocutor(self.client.id)
            if user and user.username:
                self._remember_username(chat_id, user.username)
                return user.username
        except StarvellError:
            pass
        return None

    async def find_order_chat(self, order: Order) -> str | None:
        cached = self.cached_orders.get(order.id) or {}
        if cached.get("chat_id"):
            return cached["chat_id"]
        if not order.buyer_id:
            return None
        for offset in (0, 50):
            chats = await self.client.get_chats(limit=50, offset=offset)
            for chat in chats:
                if any(user.id == order.buyer_id for user in chat.participants):
                    user = chat.interlocutor(self.client.id)
                    self._remember_username(chat.id, user.username if user else None)
                    return chat.id
            if len(chats) < 50:
                break
        return None

    def _cache_order(self, order: Order, chat_id: str | None, buyer: str | None) -> dict:
        cached = self.cached_orders.setdefault(order.id, {})
        cached.update({
            "short_id": order.short_id,
            "title": order.title,
            "quantity": order.quantity or 1,
            "price": order.total_price,
            "base_price": order.base_price,
            "status": str(order.status) if order.status else None,
            "buyer": buyer or cached.get("buyer"),
            "chat_id": chat_id or cached.get("chat_id"),
            "offer_public_id": order.offer_public_id,
            "created_at": (order.paid_at or order.created_at).isoformat() if (order.paid_at or order.created_at) else cached.get("created_at"),
        })
        return cached

    def _save_orders(self):
        # состояние выдачи пишем сразу, а не раз в 3 секунды: после падения важно знать, что уже отправлено
        data.set("cached_orders", self.cached_orders)

    def _lock(self, order_id: str) -> asyncio.Lock:
        lock = self._order_locks.get(order_id)
        if lock is None:
            lock = self._order_locks[order_id] = asyncio.Lock()
        return lock

    # --- автовыдача ---

    async def auto_deliver(self, order: Order, chat_id: str | None, buyer: str | None = None) -> bool:
        async with self._lock(order.id):
            cached = self.cached_orders.setdefault(order.id, {})
            delivery = cached.get("delivery") or {}
            if delivery.get("state") == "delivered":
                return True

            matches = find_bindings(self.auto_deliveries, order)
            if not matches:
                return False
            if len(matches) > 1:
                logger.warning(f"{Fore.YELLOW}Заказ {order.short_id}: лот попал в {len(matches)} привязки автовыдачи, выдаю по первой")
            index, binding = matches[0]

            if order.offer_details and order.offer_details.auto_delivery:
                logger.info(f"{Fore.YELLOW}Заказ {order.short_id}: у лота включена автовыдача Starvell, бот не выдаёт повторно")
                return False
            if not chat_id:
                self.notify("out_of_stock", log_text(
                    f"⚠️ Авто-выдача не сработала в {order_link(order.id, 'заказе #' + escape(order.short_id or ''))}",
                    f"<b>🛍️ Лот:</b> {escape(order.title or '-')}"
                    f"\n\n💬 Не нашёл чат с покупателем, выдайте товар вручную"
                ), log_order_kb(order.id))
                return False

            if delivery.get("state") not in ("delivering", "partial"):
                if binding.get("piece"):
                    quantity = max(order.quantity or 1, 1)
                    stock: list[str] = binding.get("goods") or []
                    if len(stock) < quantity:
                        await self._out_of_stock(order, chat_id, len(stock), quantity)
                        return False
                    parts, binding["goods"] = stock[:quantity], stock[quantity:]
                    # сначала списываем со склада и запоминаем выданное - потом отправляем
                    self._save_setting("auto_deliveries")
                    text = "\n".join(parts)
                    delivery = {"state": "delivering", "binding": binding.get("id", index), "goods": parts, "text": text, "sent": 0}
                else:
                    text = format_text("\n".join(binding.get("message") or []),
                                       order=msg_order(order), user=MsgUser(order.buyer_id, buyer or "-"),
                                       chat=msg_chat(chat_id), account=msg_account(self.client.me))
                    if not text.strip():
                        return False
                    delivery = {"state": "delivering", "binding": binding.get("id", index), "text": text, "sent": 0}
                cached["delivery"] = delivery
                self._save_orders()

            chunks = split_text(self._watermarked(delivery["text"]))
            for i in range(delivery.get("sent", 0), len(chunks)):
                result = await self._queued(PRIORITY_DELIVERY, lambda chunk=chunks[i]: self._deliver_chunk(chat_id, chunk))
                if result == "failed":
                    delivery["state"] = "partial" if i else "failed"
                    self._save_orders()
                    if i == 0 and delivery.get("goods") is not None:
                        # ни одна часть не ушла - возвращаем товар на склад
                        self._return_goods(delivery["binding"], delivery["goods"])
                        delivery.pop("goods", None)
                        cached.pop("delivery", None)
                        self._save_orders()
                    self.notify("out_of_stock", log_text(
                        f"❌ Не удалось выдать товар в {order_link(order.id, 'заказе #' + escape(order.short_id or ''))}",
                        f"<b>👤 Покупатель:</b> {escape(buyer or '-')}"
                        f"\n<b>🛍️ Лот:</b> {escape(order.title or '-')}"
                        f"\n\n📨 Сообщение с товаром не отправилось, проверьте чат и выдайте вручную"
                    ), log_new_order_kb(chat_id, order.id))
                    return False
                delivery["sent"] = i + 1
                self._save_orders()

            delivery["state"] = "delivered"
            delivery.pop("text", None)
            self._save_orders()
            logger.info(f"{Fore.LIGHTGREEN_EX}Заказ {order.short_id} выдан автоматически")
            if self.config["starvell"]["read_chat"]:
                try: await self.client.read_chat(chat_id)
                except StarvellError: pass
            return True

    async def _deliver_chunk(self, chat_id: str, chunk: str) -> str:
        for attempt in range(1, 4):
            try:
                await self.client.send_message(chat_id, chunk)
                return "sent"
            except StarvellError as e:
                if getattr(e, "maybe_delivered", False) and await self._was_sent(chat_id, chunk):
                    return "sent"
                logger.warning(f"{Fore.LIGHTRED_EX}Выдача: не отправилось сообщение (попытка {attempt}/3): {Fore.WHITE}{e}")
                await asyncio.sleep(3 * attempt)
        return "failed"

    def _return_goods(self, ref, goods: list[str]):
        _, binding = find_binding(self.auto_deliveries, ref)
        if binding is None:
            logger.warning(f"{Fore.YELLOW}Привязку автовыдачи удалили во время выдачи, товар не вернулся на склад: {Fore.WHITE}{len(goods)} шт.")
            return
        binding["goods"] = list(goods) + list(binding.get("goods") or [])
        self._save_setting("auto_deliveries")

    async def _resume_delivery(self, order: Order, chat_id: str | None) -> bool:
        # после перезапуска выдача могла оборваться: проверяем историю чата, чтобы не выдать дважды
        cached = self.cached_orders.get(order.id) or {}
        delivery = cached.get("delivery") or {}
        if delivery.get("state") not in ("delivering", "partial") or not chat_id:
            return False
        chunks = split_text(self._watermarked(delivery.get("text") or ""))
        sent = delivery.get("sent", 0)
        if sent < len(chunks) and await self._was_sent(chat_id, chunks[sent], limit=50):
            delivery["sent"] = sent + 1
            self._save_orders()
        return True

    async def _out_of_stock(self, order: Order, chat_id: str, left: int, need: int):
        logger.warning(f"{Fore.YELLOW}Заказ {order.short_id}: товары для автовыдачи закончились (осталось {left}, нужно {need})")
        self.notify("out_of_stock", log_text(
            f"📭 Закончились товары для {order_link(order.id, 'заказа #' + escape(order.short_id or ''))}",
            f"<b>🛍️ Лот:</b> {escape(order.title or '-')}"
            f"\n<b>🛒 Нужно:</b> {need} шт."
            f"\n<b>📦 Осталось:</b> {left} шт."
            f"\n\n⚠️ Выдайте товар вручную и пополните авто-выдачу"
        ), log_new_order_kb(chat_id, order.id))
        text = self.msg("out_of_stock", order=msg_order(order))
        if text:
            await self.send_message(chat_id, text, priority=PRIORITY_DELIVERY)

    async def order_action(self, order_id: str, do: str) -> tuple[Order, bool]:
        # из TG: под замком заказа, чтобы двойной тап и автовыдача не сработали одновременно
        async with self._lock(order_id):
            order = await self.client.get_order(order_id)
            if do == "complete":
                if order.seller_completed_at is not None or order.is_closed:
                    return order, False
                await self.client.complete_order(order.id)
                cached = self.cached_orders.setdefault(order.id, {})
                cached["seller_completed"] = True
            elif do == "refund":
                if order.is_closed:
                    return order, False
                await self.client.refund_order(order.id)
                cached = self.cached_orders.get(order.id)
                if cached is not None:
                    cached["status"] = "REFUND"
            else:
                raise ValueError(do)
            self._save_orders()
            logger.info(f"{Fore.LIGHTGREEN_EX}Заказ {order.short_id}: {'отмечен выполненным' if do == 'complete' else 'возврат'} из Telegram")
            return order, True

    def is_auto_complete(self, order: Order) -> bool:
        conf = self.config["starvell"]["auto_complete_orders"]
        if not conf["enabled"]:
            return False
        lists = self.auto_complete_orders
        if conf["all"]:
            return not offer_matches(lists.get("excluded") or [], order)
        return offer_matches(lists.get("included") or [], order)

    async def complete_order(self, order: Order) -> bool:
        cached = self.cached_orders.setdefault(order.id, {})
        if cached.get("seller_completed") or order.seller_completed_at is not None:
            return True
        try:
            await self.client.complete_order(order.id)
        except StarvellError as e:
            logger.error(f"{Fore.LIGHTRED_EX}Не удалось отметить заказ {order.short_id} выполненным: {Fore.WHITE}{e}")
            return False
        cached["seller_completed"] = True
        self._save_orders()
        logger.info(f"{Fore.LIGHTGREEN_EX}Заказ {order.short_id} отмечен выполненным")
        return True

    # --- поднятие (как в FunPay Universal: по категориям, ожидание от сервера) ---

    def register_category(self, game_id: int | None, category_id: int | None, title: str | None = None):
        if not game_id or not category_id:
            return
        key = f"{game_id}:{category_id}"
        entry = self.bump_categories.get(key)
        if entry is None:
            self.bump_categories[key] = {"game_id": game_id, "category_id": category_id, "title": title, "next_time": 0}
        elif title and not entry.get("title"):
            entry["title"] = title

    def _register_known_categories(self):
        for binding in self.auto_deliveries or []:
            for entry in binding.get("offers") or []:
                self.register_category(entry.get("game_id"), entry.get("category_id"), entry.get("title"))

    async def add_bump_category(self, game_id: int, category_id: int, title: str | None = None):
        self.register_category(game_id, category_id, title)
        data.set("bump_categories", self.bump_categories)

    async def toggle_bump_category(self, game_id: int, category_id: int) -> bool | None:
        # удалять нельзя: категории привязок и заказов бот добавит снова - поэтому выключаем
        cat = self.bump_categories.get(f"{game_id}:{category_id}")
        if cat is None:
            return None
        cat["disabled"] = not cat.get("disabled", False)
        data.set("bump_categories", self.bump_categories)
        return not cat["disabled"]

    async def discover_categories(self) -> int:
        before = len(self.bump_categories)
        self._register_known_categories()
        await self._discover_categories()
        data.set("bump_categories", self.bump_categories)
        return len(self.bump_categories) - before

    async def _discover_categories(self):
        try:
            orders = await self.client.get_orders(limit=50)
        except StarvellError as e:
            logger.debug(f"Поиск категорий по заказам: {e}")
            return
        for order in orders:
            details = order.offer_details
            if details and details.game and details.category:
                self.register_category(details.game.id, details.category.id, details.title)

    async def bump_offers(self, force: bool = False) -> list[tuple[str, float | None]]:
        # из цикла и из TG одновременно не поднимаем
        async with self._bump_lock:
            return await self._bump_offers(force)

    async def _bump_offers(self, force: bool) -> list[tuple[str, float | None]]:
        results = []
        now = time.time()
        for key, cat in list(self.bump_categories.items()):
            if cat.get("disabled") or (not force and cat.get("next_time", 0) > now):
                continue
            try:
                wait = await self.client.bump_offers(cat["game_id"], [cat["category_id"]])
            except APIError as e:
                if e.status_code == 404 or "не найден" in (e.message or "").lower():
                    # в категории нет активных лотов: не ошибка, проверим позже
                    if not cat.get("empty"):
                        logger.info(f"{Fore.YELLOW}В категории {cat.get('title') or key} нет активных лотов, поднимать нечего")
                    cat["empty"] = True
                    cat["next_time"] = now + BUMP_EMPTY_RECHECK
                    results.append((key, BUMP_EMPTY))
                    continue
                logger.error(f"{Fore.LIGHTRED_EX}Ошибка при поднятии лотов в {cat.get('title') or key}: {Fore.WHITE}{e}")
                cat["next_time"] = now + 600
                continue
            except StarvellError as e:
                logger.error(f"{Fore.LIGHTRED_EX}Ошибка при поднятии лотов в {cat.get('title') or key}: {Fore.WHITE}{e}")
                cat["next_time"] = now + 600
                continue
            cat.pop("empty", None)
            if wait is None:
                cat["next_time"] = now + BUMP_COOLDOWN
                cat["last_bump"] = now
                logger.info(f"{Fore.LIGHTGREEN_EX}Подняты лоты в категории {cat.get('title') or key}")
            else:
                cat["next_time"] = now + max(wait, 60)
                logger.debug(f"Лоты в {cat.get('title') or key} можно поднять через {int(wait)} сек.")
            results.append((key, wait))
            await asyncio.sleep(1)
        data.set("bump_categories", self.bump_categories)
        return results

    async def _clean_bump_categories(self):
        # категории без лотов не поднимаем и не опрашиваем
        for key, cat in list(self.bump_categories.items()):
            try:
                offers = await self.client.get_my_offers(cat["category_id"], limit=5)
            except StarvellError:
                continue
            if not offers:
                self.bump_categories.pop(key, None)
            await asyncio.sleep(1)
        data.set("bump_categories", self.bump_categories)

    # --- фоновые задачи ---

    async def _on_starvell_bot_init(self):
        async def config_loop():
            while True:
                for name in ("config", "messages", "custom_commands", "auto_deliveries", "auto_complete_orders"):
                    gen = self._setting_gen.get(name, 0)
                    value = await asyncio.to_thread(sett.get, name)
                    # пока читали файл, ядро могло его переписать (списание товара) - это чтение устарело
                    if gen != self._setting_gen.get(name, 0):
                        continue
                    if value != getattr(self, name):
                        setattr(self, name, value)
                        if name == "auto_deliveries" and ensure_binding_ids(value):
                            self._save_setting(name)
                if await asyncio.to_thread(data.get, "initialized_users") != self.initialized_users:
                    await asyncio.to_thread(data.set, "initialized_users", self.initialized_users)
                if await asyncio.to_thread(data.get, "cached_orders") != self.cached_orders:
                    await asyncio.to_thread(data.set, "cached_orders", self.cached_orders)
                await asyncio.sleep(3)

        async def refresh_loop():
            while True:
                await asyncio.sleep(30 * 60)
                await self.refresh_account()

        async def banned_loop():
            while True:
                await asyncio.sleep(15 * 60)
                await self.check_banned()

        async def bump_loop():
            await self._discover_categories()
            last_clean = time.time()
            while True:
                try:
                    if self.config["starvell"]["auto_bump_offers"]["enabled"]:
                        self._register_known_categories()
                        await self.bump_offers()
                    if time.time() - last_clean > 6 * 60 * 60:
                        await self._clean_bump_categories()
                        last_clean = time.time()
                except Exception:
                    logger.error(f"{Fore.LIGHTRED_EX}Ошибка в цикле поднятия: {Fore.WHITE}{traceback.format_exc()}")
                await asyncio.sleep(30)

        for loop_func in (config_loop, refresh_loop, banned_loop, bump_loop, self._outbox_worker):
            self._spawn(self._guard(loop_func))

    async def _guard(self, loop_func):
        while True:
            try:
                await loop_func()
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error(f"{Fore.LIGHTRED_EX}Фоновая задача {loop_func.__name__} упала, перезапускаю: {Fore.WHITE}{traceback.format_exc()}")
                await asyncio.sleep(10)

    async def _listen(self):
        async for event in self.source:
            try:
                await call_starvell_event(event.type, [self, event], skip_modules=await self.is_blacklisted_event(event))
            except Exception:
                logger.error(f"{Fore.LIGHTRED_EX}Ошибка при обработке события {event.type}: {Fore.WHITE}{traceback.format_exc()}")
            finally:
                # подтверждаем только после хендлеров: не успели - событие придёт снова после перезапуска
                self.source.ack(event)

    async def is_blacklisted_event(self, event) -> bool:
        if isinstance(event, NewMessageEvent):
            author = event.message.author
            return bool(author and author.id != self.client.id and is_blacklisted(author.username))
        if isinstance(event, NewOrderEvent):
            return is_blacklisted(await self.buyer_username(event.chat_id, event.message))
        return False

    # --- хендлеры событий ---

    async def _on_new_message(self, event: NewMessageEvent):
        message = event.message
        author = message.author
        self._remember_username(message.chat_id, author.username if author and author.id != self.client.id else None)
        self.log_new_message(message)

        is_staff = bool(author and STAFF_ROLES & set(author.roles or []))
        if message.is_notification:
            if message.notification_type == "REVIEW_CREATED" and message.order_id:
                await self._on_new_review(message)
                return
            if not message.order_id:
                self.notify("new_system_message", log_text(
                    f"🔔 Системное сообщение в {chat_link(message.chat_id, 'чате')}",
                    f"<blockquote>{escape(message.text or '') or '<i>Без текста</i>'}</blockquote>"
                ), log_new_mess_kb(message.chat_id))
            return
        if is_staff:
            who = "модерации" if "MODERATOR" in (author.roles or []) else "поддержки"
            self.notify("moderation", log_text(
                f"🛡 Сообщение от {who} Starvell в {chat_link(message.chat_id, 'чате')}",
                f"<b>👮 {escape(author.username or '-')}:</b> <blockquote>{escape(message.text or '') or '<i>Без текста</i>'}</blockquote>"
            ), log_new_mess_kb(message.chat_id))
            return
        if author is None or author.id == self.client.id:
            return

        blacklisted = is_blacklisted(author.username)
        text = escape(message.text or "")
        if message.images:
            text = f"<i>*Изображений: {len(message.images)}*</i>" + (f" {text}" if text else "")
        self.notify("new_user_message", log_text(
            f"{'🚫 ' if blacklisted else ''}💬 Новое сообщение в {chat_link(message.chat_id, 'чате')}{' (покупатель в ЧС)' if blacklisted else ''}",
            f"<b>{escape(author.username or '-')}:</b> <blockquote>{text or '<i>Без сообщения</i>'}</blockquote>"
        ), log_new_mess_kb(message.chat_id))
        if blacklisted:
            return

        if message.chat_id not in self.initialized_users:
            self.initialized_users.append(message.chat_id)
            text = self.msg("first_message", user=msg_user(author), chat=msg_chat(message.chat_id))
            if text:
                await self.send_message(message.chat_id, text, priority=PRIORITY_LOW)

        content = (message.text or "").strip()
        lowered = content.lower()
        if lowered in ("!продавец", "!seller"):
            tgbot, loop = get_telegram_bot(), get_telegram_bot_loop()
            if tgbot and loop:
                asyncio.run_coroutine_threadsafe(tgbot.call_seller(author.username or "-", message.chat_id), loop)
            text = self.msg("cmd_seller", user=msg_user(author), chat=msg_chat(message.chat_id))
            if text:
                await self.send_message(message.chat_id, text)
            return
        commands = {k.lower(): v for k, v in (self.custom_commands or {}).items()}
        if lowered in commands:
            text = format_text("\n".join(commands[lowered]), user=msg_user(author), chat=msg_chat(message.chat_id),
                               account=msg_account(self.client.me))
            await self.send_message(message.chat_id, text)

    async def find_review(self, order_id: str):
        # отзыв появляется в списке не мгновенно - пара попыток
        for attempt in range(3):
            try:
                for review in await self.client.get_reviews(limit=20):
                    if review.order_id == order_id:
                        return review
            except StarvellError as e:
                logger.warning(f"{Fore.LIGHTRED_EX}Не удалось получить отзывы: {Fore.WHITE}{e}")
            await asyncio.sleep(3 * (attempt + 1))
        return None

    async def _on_new_review(self, message: Message):
        order_id = message.order_id
        cached = self.cached_orders.get(order_id) or {}
        short_id = (message.metadata.order_short_id if message.metadata else None) or cached.get("short_id") or order_id
        review = await self.find_review(order_id)
        buyer = (review.author.username if review and review.author else None) or cached.get("buyer") or "-"
        stars = "⭐" * (review.rating or 0) if review and review.rating else "?"
        logger.info(f"{Fore.LIGHTYELLOW_EX}Новый отзыв по заказу {short_id} от {buyer}: {stars}")

        replied = False
        if review and not review.review_response and self.config["starvell"]["auto_review_replies"]:
            try:
                order = await self.client.get_order(order_id)
            except StarvellError:
                order = Order(id=order_id, short_id=short_id)
            text = self.msg("order_review_reply", user=MsgUser(review.author_id, buyer), order=msg_order(order))
            if text:
                try:
                    await self.client.create_review_response(review.id, text[:1000])
                    replied = True
                    logger.info(f"{Fore.LIGHTGREEN_EX}Ответил на отзыв по заказу {short_id}")
                except StarvellError as e:
                    logger.error(f"{Fore.LIGHTRED_EX}Не удалось ответить на отзыв по заказу {short_id}: {Fore.WHITE}{e}")

        content = escape(review.content or "") if review else ""
        self.notify("new_review", log_text(
            f"🌟 Новый отзыв в {order_link(order_id, f'заказе #{escape(short_id)}')}",
            f"<b>👤 Оставил:</b> {escape(buyer)}"
            f"\n<b>✨ Оценка:</b> {stars}"
            f"\n<b>🏷️ Текст:</b> " + (f"<blockquote>{content}</blockquote>" if content else "<i>Без текста</i>")
            + ("\n\n✅ Бот ответил на отзыв" if replied else "")
        ), log_order_kb(order_id, message.chat_id))

    async def _on_new_order(self, event: NewOrderEvent):
        order = event.order
        chat_id = event.chat_id
        buyer = await self.buyer_username(chat_id, event.message)
        cached = self._cache_order(order, chat_id, buyer)
        self._save_orders()
        if order.offer_details and order.offer_details.game and order.offer_details.category:
            self.register_category(order.offer_details.game.id, order.offer_details.category.id, order.offer_details.title)

        if await self._resume_delivery(order, chat_id):
            await self.auto_deliver(order, chat_id, buyer)
            return
        if (cached.get("delivery") or {}).get("state") == "delivered":
            return

        self.log_new_order(order, buyer)
        entry = get_blacklist_entry(buyer)
        if entry is not None:
            await self._handle_blacklisted_order(order, chat_id, buyer, entry)
            return

        args = order_args_text(order)
        self.notify("new_order", log_text(
            f"📋 Новый заказ {order_link(order.id, '#' + escape(order.short_id or ''))}",
            f"<b>👤 Покупатель:</b> {escape(buyer or '-')}"
            f"\n<b>🛍️ Лот:</b> {escape(order.title or '-')}"
            f"\n<b>🛒 Количество:</b> {order.quantity or 1}"
            f"\n<b>💰 Сумма:</b> {rub(order.total_price)} (вам {rub(order.base_price)})"
            + (f"\n\n<b>📝 Данные покупателя:</b>\n{args}" if args else "")
            + ("\n\n⏪ <i>Заказ найден после перерыва в работе бота</i>" if event.catch_up else "")
        ), log_new_order_kb(chat_id, order.id, completed=order.seller_completed_at is not None))

        buyer_user = MsgUser(order.buyer_id, buyer or "-")
        if chat_id:
            text = self.msg("new_order", order=msg_order(order), user=buyer_user, chat=msg_chat(chat_id))
            if text:
                await self.send_message(chat_id, text)
            if chat_id not in self.initialized_users:
                self.initialized_users.append(chat_id)
                text = self.msg("first_message", user=buyer_user, chat=msg_chat(chat_id))
                if text:
                    await self.send_message(chat_id, text, priority=PRIORITY_LOW)

        delivered = await self.auto_deliver(order, chat_id, buyer)
        if delivered and self.is_auto_complete(order):
            await self.complete_order(order)

    async def _handle_blacklisted_order(self, order: Order, chat_id: str | None, buyer: str | None, entry: dict):
        refunded = False
        if self.config["starvell"]["blacklist"]["auto_refund"]:
            try:
                await self.client.refund_order(order.id)
                refunded = True
                logger.info(f"{Fore.YELLOW}Заказ {order.short_id} от покупателя из ЧС возвращён")
            except StarvellError as e:
                logger.error(f"{Fore.LIGHTRED_EX}Не удалось вернуть заказ {order.short_id} покупателя из ЧС: {Fore.WHITE}{e}")
            if refunded and chat_id:
                text = self.msg("blacklist_order_refunded", order=msg_order(order))
                if text:
                    await self.send_message(chat_id, text)
        self.notify("new_order", log_text(
            f"🚫 {order_link(order.id, 'Заказ #' + escape(order.short_id or ''))} от покупателя из ЧС",
            f"<b>👤 Покупатель:</b> {escape(buyer or '-')}"
            f"\n<b>📝 Причина ЧС:</b> {escape(entry.get('reason') or '') or 'не указана'}"
            f"\n<b>🛍️ Лот:</b> {escape(order.title or '-')}"
            f"\n<b>💰 Сумма:</b> {rub(order.total_price)}"
            f"\n\n{'📦 Заказ автоматически возвращён' if refunded else '⚠️ Модули этот заказ не обрабатывают, решите вручную'}"
        ), log_blacklisted_order_kb(chat_id, order.id, buyer or "", refunded))

    async def _on_order_status(self, event: OrderSellerCompletedEvent | OrderCompletedEvent | OrderRefundedEvent | OrderStatusChangedEvent):
        order = event.order
        cached = self.cached_orders.get(order.id)
        if cached is not None:
            cached["status"] = str(order.status) if order.status else cached.get("status")
            if isinstance(event, OrderSellerCompletedEvent):
                cached["seller_completed"] = True
            self._save_orders()
        chat_id = event.chat_id or (cached or {}).get("chat_id")

        if isinstance(event, OrderSellerCompletedEvent):
            status_frmtd = "Выполнен продавцом"
        elif isinstance(event, OrderCompletedEvent):
            status_frmtd = "Подтверждён покупателем"
        elif isinstance(event, OrderRefundedEvent):
            status_frmtd = "Возврат"
        else:
            status_frmtd = ORDER_STATUSES.get(order.status, str(order.status))
        self.log_order_status(order, status_frmtd.lower())
        buyer = (cached or {}).get("buyer")
        self.notify("order_status_changed", log_text(
            f"🔃 Статус {order_link(order.id, 'заказа #' + escape(order.short_id or ''))} изменился на «{status_frmtd}»",
            (f"<b>👤 Покупатель:</b> {escape(buyer)}\n" if buyer else "")
            + f"<b>🛍️ Лот:</b> {escape(order.title or (cached or {}).get('title') or '-')}"
            f"\n<b>💰 Сумма:</b> {rub(order.total_price or (cached or {}).get('price'))}"
        ), log_order_kb(order.id, chat_id))

        if not chat_id or is_blacklisted((cached or {}).get("buyer")):
            return
        name = "order_completed" if isinstance(event, OrderCompletedEvent) else "order_refunded" if isinstance(event, OrderRefundedEvent) else None
        if name:
            text = self.msg(name, order=msg_order(order), chat=msg_chat(chat_id))
            if text:
                await self.send_message(chat_id, text)

    async def _on_connection_status(self, event: ConnectionStatusEvent):
        titles = {
            "unauthorized": ("🔐 Сессия Starvell недействительна", "⚠️ Бот перестал получать события. Обновите <b>Session</b> в разделе «🔒 Авторизация»"),
            "bot_check": ("🛡 Starvell ограничил запросы", "⚠️ Защита сайта не пропускает бота. Проверьте прокси в разделе «🛜 Соединение» или подождите"),
        }
        if event.status in titles:
            title, text = titles[event.status]
            self.notify("connection", log_text(title, text), destroy_kb())

    async def _on_balance_updated(self, event: BalanceUpdatedEvent):
        if self.client.me and self.client.me.balance and event.balance.rub_balance is not None:
            self.client.me.balance.rub_balance = event.balance.rub_balance
            self._set_title()
        if event.balance.rub_balance is not None:
            withdrawable = f"\n<b>👜 К выводу:</b> {rub(event.balance.withdrawable_rub_balance)}" if event.balance.withdrawable_rub_balance is not None else ""
            self.notify("balance_updated", log_text("💰 Баланс изменился", f"<b>💰 Баланс:</b> {rub(event.balance.rub_balance)}{withdrawable}"), destroy_kb())

    # --- запуск ---

    async def run_bot(self):
        from core.console import log_panel

        self.loop = asyncio.get_running_loop()
        self._outbox = asyncio.PriorityQueue()
        self._bump_lock = asyncio.Lock()
        await self.client.refresh()
        account_pid = acquire_account_lock(str(self.client.id))
        if account_pid is not None:
            log_panel(
                logger, "■ Бот на этом аккаунте Starvell уже запущен",
                body=f"Аккаунт {Fore.LIGHTWHITE_EX}{self.client.username}{Fore.RESET} уже обслуживает другой бот"
                     f"{f' (процесс {account_pid})' if account_pid else ''} — один аккаунт, один бот.\n"
                     f"Закройте это окно: если оставить два бота на одном аккаунте, заказы и сообщения будут обрабатываться дважды.",
                level=logging.ERROR, color="red"
            )
            from core.bootreport import notify_crash
            notify_crash("", reason=(
                f"На аккаунте Starvell <b>{escape(self.client.username or '')}</b> уже работает другой бот — один аккаунт, один бот. "
                f"Закройте лишнюю копию и перезапустите этого бота"
            ), throttle_key="account_locked")
            if not sys.stdin.isatty():
                time.sleep(60)
            sys.exit(1)

        self.sync = ThreadsafeClient(self.client, self.loop, timeout=60)
        me = self.client.me
        rows = [("Никнейм", self.client.username), ("ID", self.client.id)]
        if me and me.balance:
            rows.append(("Баланс", f"{me.balance.rub_balance or 0:g} ₽ {Fore.LIGHTBLACK_EX}· к выводу {Fore.RESET}{me.balance.withdrawable_rub_balance or 0:g} ₽"))
        if me and me.user:
            rows.append(("Рейтинг", f"{me.user.rating or 0} ({me.user.reviews_count or 0} отзывов)"))
        proxy = self.config["starvell"]["api"]["proxy"]
        if proxy:
            from utils import mask_proxy
            rows.append(("Прокси", mask_proxy(proxy)))
        log_panel(logger, "👤 Аккаунт Starvell", rows, message=f"{Fore.YELLOW}Starvell бот запущен и активен")
        self._set_title()

        add_bot_event_handler("ON_STARVELL_BOT_INIT", StarvellBot._on_starvell_bot_init, 0)
        add_starvell_event_handler(EventType.NEW_MESSAGE, StarvellBot._on_new_message, 0)
        add_starvell_event_handler(EventType.NEW_ORDER, StarvellBot._on_new_order, 0)
        for event_type in (EventType.ORDER_SELLER_COMPLETED, EventType.ORDER_COMPLETED,
                           EventType.ORDER_REFUNDED, EventType.ORDER_STATUS_CHANGED):
            add_starvell_event_handler(event_type, StarvellBot._on_order_status, 0)
        add_starvell_event_handler(EventType.CONNECTION_STATUS, StarvellBot._on_connection_status, 0)
        add_starvell_event_handler(EventType.BALANCE_UPDATED, StarvellBot._on_balance_updated, 0)

        self.source = EventSource(self.client, state=JsonFileState(EVENTS_STATE_PATH))
        await self.source.start()
        self._spawn(self._listen())
        await call_bot_event("ON_STARVELL_BOT_INIT", [self])
