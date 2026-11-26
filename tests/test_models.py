from __future__ import annotations

import logging
from decimal import Decimal

from pydantic import TypeAdapter

from starvellapi.models import Chat, Message, MessagesPage, NotificationType, Offer, Order, OrderStatus, Profile

from .conftest import fixture


def test_fixtures_parse_without_warnings(caplog):
    with caplog.at_level(logging.WARNING, logger="starvellapi"):
        profile = Profile.model_validate(fixture("profile.json"))
        chats = TypeAdapter(list[Chat]).validate_python(fixture("chats.json"))
        page = MessagesPage.model_validate(fixture("messages.json"))
        order = Order.model_validate(fixture("order.json"))
        orders = TypeAdapter(list[Order]).validate_python(fixture("orders_list.json"))
        offer = Offer.model_validate(fixture("offer.json"))
        for e in fixture("socket_events.json"):
            if e["event"] == "message_created":
                Message.model_validate(e["args"][0])
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING], [r.getMessage() for r in caplog.records]

    assert profile.id == 1001 and profile.username == "seller"
    assert profile.balance is not None and profile.balance.rub_balance == 0
    assert chats and all(c.id for c in chats)
    assert chats[0].interlocutor(1001).id != 1001
    assert page.items and page.items[0].created_at.tzinfo is not None
    assert order.status == OrderStatus.CREATED and isinstance(order.status, OrderStatus)
    assert order.offer_public_id and order.offer_id
    # суммы приходят в копейках, модель отдаёт рубли
    assert order.base_price == 1.0 and order.total_price == 1.16
    assert order.title == "Roblox · Донат робуксов (моментально) · 40 робуксов"
    assert orders[0].user is not None
    assert offer.price == Decimal("1000") and offer.category_id == 40 and offer.game_id == 1
    assert offer.delivery_time.from_.value == 1


def test_sensitive_order_args_hidden():
    order = Order.model_validate(fixture("order.json"))
    sensitive = [a for a in order.order_args if a.is_sensitive]
    assert sensitive and all(a.shown_value == "***" for a in sensitive)


def test_payment_notification():
    payment = next(e["args"][0] for e in fixture("socket_events.json")
                   if e["event"] == "message_created" and (e["args"][0].get("metadata") or {}).get("notificationType") == "ORDER_PAYMENT")
    message = Message.model_validate(payment)
    assert message.is_notification
    assert message.notification_type == NotificationType.ORDER_PAYMENT
    assert message.order_id == message.order.id
    assert message.order.order_args


def test_unknown_enum_kept_as_string(caplog):
    order = Order.model_validate({"id": "1", "status": "SOMETHING_NEW"})
    assert order.status == "SOMETHING_NEW" and not isinstance(order.status, OrderStatus)


def test_two_date_formats():
    a = Message.model_validate({"id": "1", "createdAt": "2026-11-25T12:14:29.846Z"})
    b = Message.model_validate({"id": "2", "createdAt": "2026-11-25T12:12:06.146486+00:00"})
    assert a.created_at > b.created_at
