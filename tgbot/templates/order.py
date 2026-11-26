import textwrap
from html import escape
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from starvellapi.models import Order, OrderStatus
from svbot.msg_types import ORDER_STATUSES, fmt_date

from .. import callback_datas as calls


def order_text(order: Order, buyer: str | None, cached: dict | None = None):
    status = ORDER_STATUSES.get(order.status, str(order.status or "-"))
    if order.status == OrderStatus.CREATED and order.seller_completed_at:
        status += ", вы отметили выполнение"
    delivery = (cached or {}).get("delivery") or {}
    delivery_frmtd = {
        "delivered": "✅ Выдан ботом",
        "delivering": "⏳ Выдаётся",
        "partial": "⚠️ Выдан не полностью",
        "failed": "❌ Не удалось выдать",
    }.get(delivery.get("state"), "")
    args = "\n".join(
        f"<b>・ {escape(a.name_ru or 'Поле')}:</b> "
        + (f"<tg-spoiler>{escape(a.value or '')}</tg-spoiler>" if a.is_sensitive else escape(a.value or ""))
        for a in order.order_args
    )

    txt = textwrap.dedent(f"""
        <b>📋 Заказ {escape(order.short_id or '')}</b>

        <b>👤 Покупатель:</b> {escape(buyer or '-')}
        <b>🛍️ Лот:</b> {escape(order.title or '-')}
        <b>🔢 Количество:</b> {order.quantity or 1}
        <b>💰 Сумма:</b> {order.total_price or 0:g}₽ (вам {order.base_price or 0:g}₽)
        <b>📌 Статус:</b> {status}
        <b>📅 Оплачен:</b> {fmt_date(order.paid_at or order.created_at)}
    """)
    if delivery_frmtd:
        txt += f"<b>🚀 Авто-выдача:</b> {delivery_frmtd}\n"
    if args:
        txt += f"\n<b>📝 Данные покупателя:</b>\n{args}\n"
    return txt


def order_kb(order: Order, chat_id: str | None, last_page: int = 0, st: int = -1):
    rows = []
    if order.status == OrderStatus.CREATED:
        actions = [InlineKeyboardButton(text="📦 Возврат", callback_data=calls.OrderAction(id=order.id, do="refund").pack())]
        if not order.seller_completed_at:
            actions.insert(0, InlineKeyboardButton(text="☑️ Выполнил", callback_data=calls.OrderAction(id=order.id, do="complete").pack()))
        rows.append(actions)
    if chat_id:
        rows.append([InlineKeyboardButton(text="💬 Чат", callback_data=calls.ChatPage(id=chat_id).pack())])
    rows.append([InlineKeyboardButton(text="🌐 На сайте", url=f"https://starvell.com/order/{order.id}")])
    rows.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.OrderPage(id=order.id).pack()),
        InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.OrdersPagination(page=last_page, st=st).pack()),
    ])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def order_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>📋 Заказ</b>
        \n{placeholder}
    """)
    return txt
