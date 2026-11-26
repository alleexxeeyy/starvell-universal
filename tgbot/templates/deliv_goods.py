import math
import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett
from svbot.deliveries import resolve_binding, good_hash

from .. import callback_datas as calls


def _goods(ref: str) -> list[str]:
    _, deliv = resolve_binding(sett.get("auto_deliveries"), ref)
    return (deliv or {}).get("goods") or []


def deliv_goods_text(ref: str):
    goods = _goods(ref)
    txt = textwrap.dedent(f"""
        <b>📦 Товары авто-выдачи</b>
        Всего <b>{len(goods)}</b> товаров, на покупку N штук бот выдаёт N строк:
    """)
    return txt


def deliv_goods_kb(ref: str, page=0):
    goods = _goods(ref)
    
    rows = []
    items_per_page = 10
    total_pages = math.ceil(len(goods) / items_per_page)
    total_pages = total_pages if total_pages > 0 else 1

    if page < 0: page = 0
    elif page >= total_pages: page = total_pages - 1

    start_offset = page * items_per_page
    end_offset = start_offset + items_per_page

    for i, good in enumerate(list(goods)[start_offset:end_offset], start=start_offset):
        rows.append([
            InlineKeyboardButton(text=good[:60], callback_data="null_answer"),
            InlineKeyboardButton(text="🗑️", callback_data=calls.DeleteDelivGood(index=i, h=good_hash(good)).pack()),
        ])

    if total_pages > 1:
        buttons_row = []
        btn_back = InlineKeyboardButton(text="←", callback_data=calls.DelivGoodsPagination(page=page-1).pack()) if page > 0 else InlineKeyboardButton(text="🛑", callback_data="null_answer")
        buttons_row.append(btn_back)

        btn_pages = InlineKeyboardButton(text=f"📃 {page+1}/{total_pages}", callback_data=calls.PageEnter(to="deliv_goods", page=page, total=total_pages).pack())
        buttons_row.append(btn_pages)

        btn_next = InlineKeyboardButton(text="→", callback_data=calls.DelivGoodsPagination(page=page+1).pack()) if page < total_pages - 1 else InlineKeyboardButton(text="🛑", callback_data="null_answer")
        buttons_row.append(btn_next)
        rows.append(buttons_row)

    rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data="enter_auto_delivery_goods_add")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.AutoDeliveryPage(id=ref).pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def deliv_goods_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>📦 Товары авто-выдачи</b>
        \n{placeholder}
    """)
    return txt


def new_deliv_goods_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>➕📦 Добавление товаров</b>
        \n{placeholder}
    """)
    return txt
