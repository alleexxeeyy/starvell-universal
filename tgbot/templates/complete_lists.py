import math
import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


_LISTS = {
    "included": {
        "title": "☑️➕ Включённые",
        "desc": "включённых лотов",
        "new": "☑️➕ Добавление включённого лота",
        "pagination": calls.IncludedCompleteOrdersPagination,
        "delete": calls.DeleteIncludedCompleteOrder,
        "add_cb": "enter_new_included_complete_offers",
    },
    "excluded": {
        "title": "☑️➖ Исключённые",
        "desc": "исключённых лотов",
        "new": "☑️➖ Добавление исключённого лота",
        "pagination": calls.ExcludedCompleteOrdersPagination,
        "delete": calls.DeleteExcludedCompleteOrder,
        "add_cb": "enter_new_excluded_complete_offers",
    },
}


def complete_list_text(kind: str):
    entries = sett.get("auto_complete_orders").get(kind) or []
    txt = textwrap.dedent(f"""
        <b>{_LISTS[kind]['title']}</b>
        Всего <b>{len(entries)}</b> {_LISTS[kind]['desc']}:
    """)
    return txt


def complete_list_kb(kind: str, page=0):
    entries: list[dict] = sett.get("auto_complete_orders").get(kind) or []
    conf = _LISTS[kind]
    
    rows = []
    items_per_page = 10
    total_pages = math.ceil(len(entries) / items_per_page)
    total_pages = total_pages if total_pages > 0 else 1

    if page < 0: page = 0
    elif page >= total_pages: page = total_pages - 1

    start_offset = page * items_per_page
    end_offset = start_offset + items_per_page

    for i, entry in enumerate(list(entries)[start_offset:end_offset], start=start_offset):
        title = str(entry.get("title") or entry.get("public_id") or "❌ Не указан")
        title_frmtd = title[:32] + ("..." if len(title) > 32 else "")
        public_id = entry.get("public_id")
        rows.append([
            InlineKeyboardButton(text=title_frmtd, url=f"https://starvell.com/offers/{public_id}")
            if public_id else
            InlineKeyboardButton(text=title_frmtd, callback_data="null_answer"),
            InlineKeyboardButton(text="🗑️", callback_data=conf["delete"](index=i).pack()),
        ])

    if total_pages > 1:
        buttons_row = []
        btn_back = InlineKeyboardButton(text="←", callback_data=conf["pagination"](page=page-1).pack()) if page > 0 else InlineKeyboardButton(text="🛑", callback_data="null_answer")
        buttons_row.append(btn_back)
        
        btn_pages = InlineKeyboardButton(text=f"📃 {page+1}/{total_pages}", callback_data=calls.PageEnter(to=f"complete_{kind}", page=page, total=total_pages).pack())
        buttons_row.append(btn_pages)

        btn_next = InlineKeyboardButton(text="→", callback_data=conf["pagination"](page=page+1).pack()) if page < total_pages - 1 else InlineKeyboardButton(text="🛑", callback_data="null_answer")
        buttons_row.append(btn_next)
        rows.append(buttons_row)

    rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data=conf["add_cb"])])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="complete").pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def complete_list_float_text(kind: str, placeholder: str):
    txt = textwrap.dedent(f"""
        <b>{_LISTS[kind]['title']}</b>
        \n{placeholder}
    """)
    return txt


def new_complete_list_float_text(kind: str, placeholder: str):
    txt = textwrap.dedent(f"""
        <b>{_LISTS[kind]['new']}</b>
        \n{placeholder}
    """)
    return txt
