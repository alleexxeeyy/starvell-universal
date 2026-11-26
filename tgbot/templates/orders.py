import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from starvellapi.models import Order, OrderStatus

from .. import callback_datas as calls


ORDERS_PER_PAGE = 10
ORDERS_FILTERS = [
    (None, "Все"),
    (OrderStatus.CREATED, "Оплаченные"),
    (OrderStatus.COMPLETED, "Завершённые"),
    (OrderStatus.REFUND, "Возвраты"),
]
STATUS_EMOJI = {
    OrderStatus.PRE_CREATED: "⏳",
    OrderStatus.CREATED: "🟢",
    OrderStatus.COMPLETED: "✅",
    OrderStatus.REFUND: "📦",
    OrderStatus.FAILED: "⚪",
}


def order_filter(st: int):
    if 0 <= st < len(ORDERS_FILTERS):
        return ORDERS_FILTERS[st]
    return ORDERS_FILTERS[0]


def orders_text(page: int, st: int = -1):
    txt = textwrap.dedent(f"""
        <b>📋 Заказы</b>
        Продажи ・ <b>{order_filter(st)[1]}</b> ・ страница <b>{page + 1}</b>:
    """)
    return txt


def orders_kb(orders: list[Order], page: int = 0, st: int = -1):
    rows = []
    for order in orders:
        sym = STATUS_EMOJI.get(order.status, "❔")
        if order.status == OrderStatus.CREATED and order.seller_completed_at:
            sym = "☑️"
        buyer = order.user.username if order.user and order.user.username else "-"
        text = f"{sym} {order.short_id} ・ {order.total_price or 0:g}₽ ・ {buyer} ・ {order.title}"
        rows.append([InlineKeyboardButton(
            text=text[:60] + ("..." if len(text) > 60 else ""),
            callback_data=calls.OrderPage(id=order.id).pack()
        )])

    current = st if 0 <= st < len(ORDERS_FILTERS) else 0
    rows.append([
        InlineKeyboardButton(text=("· " if i == current else "") + name,
                             callback_data=calls.OrdersPagination(page=0, st=i if i else -1).pack())
        for i, (_, name) in enumerate(ORDERS_FILTERS)
    ])
    rows.append([
        InlineKeyboardButton(text="←", callback_data=calls.OrdersPagination(page=page-1, st=st).pack()) if page > 0 else InlineKeyboardButton(text="🛑", callback_data="null_answer"),
        InlineKeyboardButton(text=f"📃 {page+1}", callback_data=calls.OrdersPagination(page=page, st=st).pack()),
        InlineKeyboardButton(text="→", callback_data=calls.OrdersPagination(page=page+1, st=st).pack()) if len(orders) >= ORDERS_PER_PAGE else InlineKeyboardButton(text="🛑", callback_data="null_answer"),
    ])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def orders_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>📋 Заказы</b>
        \n{placeholder}
    """)
    return txt
