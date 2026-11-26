import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def _sel_fast_reply_kb(chat_id: str, page: int, send_call, pagination_call, page_to: str, last_row):
    fast_replies = sett.get("fast_replies")
    
    rows = []
    items_per_page = 10
    total_pages = math.ceil(len(fast_replies) / items_per_page)
    total_pages = total_pages if total_pages > 0 else 1

    if page < 0: page = 0
    elif page >= total_pages: page = total_pages - 1

    start_offset = page * items_per_page
    end_offset = start_offset + items_per_page

    for index, reply in list(enumerate(fast_replies))[start_offset:end_offset]:
        rows.append([InlineKeyboardButton(
            text=reply[:60], 
            callback_data=send_call(id=chat_id, index=index).pack()
        )])

    if total_pages > 1:
        buttons_row = []
        btn_back = InlineKeyboardButton(text="←", callback_data=pagination_call(id=chat_id, page=page-1).pack()) if page > 0 else InlineKeyboardButton(text="🛑", callback_data="null_answer")
        buttons_row.append(btn_back)

        btn_pages = InlineKeyboardButton(text=f"📃 {page+1}/{total_pages}", callback_data=calls.PageEnter(to=page_to, page=page, total=total_pages).pack())
        buttons_row.append(btn_pages)

        btn_next = InlineKeyboardButton(text="→", callback_data=pagination_call(id=chat_id, page=page+1).pack()) if page < total_pages - 1 else InlineKeyboardButton(text="🛑", callback_data="null_answer")
        buttons_row.append(btn_next)
        rows.append(buttons_row)

    rows.append([InlineKeyboardButton(text="🛠️ Управление", callback_data=calls.FastRepliesPagination(page=0).pack())])
    rows.append(last_row)

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def fast_sel_fast_reply_kb(chat_id: str, page=0):
    return _sel_fast_reply_kb(
        chat_id, page, calls.FastSendFastReply, calls.FastSelFastReplyPagination, "fast_sel_fast_reply",
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="destroy")]
    )


def sel_fast_reply_kb(chat_id: str, page=0):
    return _sel_fast_reply_kb(
        chat_id, page, calls.SendFastReply, calls.SelFastReplyPagination, "sel_fast_reply",
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.ChatPage(id=chat_id).pack())]
    )
