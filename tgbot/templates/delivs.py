import math
import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett
from svbot.deliveries import binding_title, binding_ref

from .. import callback_datas as calls


def delivs_text():
    auto_deliveries = sett.get("auto_deliveries")
    txt = textwrap.dedent(f"""
        <b>🚀 Авто-выдача</b>
        Всего <b>{len(auto_deliveries)}</b> привязок авто-выдачи:
    """)
    return txt


def delivs_kb(page=0):
    auto_deliveries: list = sett.get("auto_deliveries")
    
    rows = []
    items_per_page = 10
    total_pages = math.ceil(len(auto_deliveries) / items_per_page)
    total_pages = total_pages if total_pages > 0 else 1

    if page < 0: page = 0
    elif page >= total_pages: page = total_pages - 1

    start_offset = page * items_per_page
    end_offset = start_offset + items_per_page

    for index, deliv in list(enumerate(auto_deliveries))[start_offset:end_offset]:
        piece = deliv.get("piece")
        sym = "📦" if piece else "💬"
        if not deliv.get("enabled", True):
            sym = "⏸"
        title = binding_title(deliv)
        title_frmtd = title[:32] + ("..." if len(title) > 32 else "")
        
        if piece:
            part = f"{len(deliv.get('goods') or [])} шт."
        else:
            part = " ".join(deliv.get("message") or []) or "❌ Не задано"
            part = part[:32] + ("..." if len(part) > 32 else "")
        
        rows.append([InlineKeyboardButton(
            text=f"{sym} {title_frmtd} ・ {part}", 
            callback_data=calls.AutoDeliveryPage(id=binding_ref(deliv, index)).pack()
        )])

    if total_pages > 1:
        buttons_row = []
        btn_back = InlineKeyboardButton(text="←", callback_data=calls.AutoDeliveriesPagination(page=page-1).pack()) if page > 0 else InlineKeyboardButton(text="🛑", callback_data="null_answer")
        buttons_row.append(btn_back)

        btn_pages = InlineKeyboardButton(text=f"📃 {page+1}/{total_pages}", callback_data=calls.PageEnter(to="auto_deliveries", page=page, total=total_pages).pack())
        buttons_row.append(btn_pages)

        btn_next = InlineKeyboardButton(text="→", callback_data=calls.AutoDeliveriesPagination(page=page+1).pack()) if page < total_pages - 1 else InlineKeyboardButton(text="🛑", callback_data="null_answer")
        buttons_row.append(btn_next)
        rows.append(buttons_row)

    rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data="enter_new_auto_delivery_offers")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def deliv_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>🚀 Авто-выдача</b>
        \n{placeholder}
    """)
    return txt


def new_deliv_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>➕🚀 Добавление авто-выдачи</b>
        \n{placeholder}
    """)
    return txt


def new_deliv_piece_kb(last_page=0):
    rows = [
        [InlineKeyboardButton(text="📦 Поштучно (товар на каждую покупку)", callback_data=calls.SetNewDelivPiece(val=True).pack())],
        [InlineKeyboardButton(text="💬 Одно сообщение", callback_data=calls.SetNewDelivPiece(val=False).pack())],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.AutoDeliveriesPagination(page=last_page).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb
