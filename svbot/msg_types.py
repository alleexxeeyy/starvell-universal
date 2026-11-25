from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

import pytz

from starvellapi.models import Message, Offer, Order, OrderStatus, Profile, UserShort


ORDER_STATUSES = {
    OrderStatus.PRE_CREATED: "Ожидает оплаты",
    OrderStatus.CREATED: "Оплачен",
    OrderStatus.COMPLETED: "Завершён",
    OrderStatus.REFUND: "Возврат",
    OrderStatus.FAILED: "Не оплачен",
}

_PLACEHOLDER = re.compile(r"\{([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*)\}")
_MSK = pytz.timezone("Europe/Moscow")


def fmt_date(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    return dt.astimezone(_MSK).strftime("%d.%m.%Y %H:%M")


def format_text(text: str, **kwargs) -> str:
    # неизвестный заменитель остаётся как есть, а не ломает всё сообщение
    def replace(match: re.Match) -> str:
        parts = match.group(1).split(".")
        if parts[0] not in kwargs:
            return match.group(0)
        obj = kwargs[parts[0]]
        try:
            for part in parts[1:]:
                obj = obj[part] if isinstance(obj, dict) else getattr(obj, part)
        except (AttributeError, KeyError, TypeError):
            return match.group(0)
        return match.group(0) if obj is None else str(obj)
    return _PLACEHOLDER.sub(replace, text)


@dataclass
class MsgAccount:
    id: int | None
    username: str | None
    balance: str
    rating: str
    reviews_count: int


@dataclass
class MsgUser:
    id: int | None
    username: str


@dataclass
class MsgChat:
    id: str | None
    link: str | None


@dataclass
class MsgOrder:
    id: str | None
    short_id: str | None
    title: str
    quantity: int
    price: str
    base_price: str
    status: str
    link: str | None
    date: str


@dataclass
class MsgOffer:
    id: int | None
    public_id: str | None
    title: str
    price: str
    link: str | None


def _rub(value) -> str:
    if value is None:
        return "-"
    return f"{float(value):g}"


def msg_account(profile: Profile | None) -> MsgAccount:
    user = profile.user if profile else None
    balance = profile.balance.rub_balance if profile and profile.balance else None
    return MsgAccount(
        id=profile.id if profile else None,
        username=profile.username if profile else None,
        balance=_rub(balance),
        rating=str(user.rating) if user and user.rating is not None else "-",
        reviews_count=user.reviews_count or 0 if user else 0,
    )


def msg_user(user: UserShort | None) -> MsgUser:
    return MsgUser(id=user.id if user else None, username=(user.username if user else None) or "-")


def msg_user_from_message(message: Message) -> MsgUser:
    return msg_user(message.author or message.buyer)


def msg_chat(chat_id: str | None) -> MsgChat:
    return MsgChat(id=chat_id, link=f"https://starvell.com/chat/{chat_id}" if chat_id else None)


def msg_order(order: Order) -> MsgOrder:
    return MsgOrder(
        id=order.id,
        short_id=order.short_id,
        title=order.title or "-",
        quantity=order.quantity or 1,
        price=_rub(order.total_price),
        base_price=_rub(order.base_price),
        status=ORDER_STATUSES.get(order.status, str(order.status or "-")),
        link=order.link,
        date=fmt_date(order.paid_at or order.created_at),
    )


def msg_offer(offer: Offer) -> MsgOffer:
    return MsgOffer(id=offer.id, public_id=offer.public_id, title=offer.title or "-", price=_rub(offer.price), link=offer.link)
