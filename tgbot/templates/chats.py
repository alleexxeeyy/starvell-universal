import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from starvellapi.models import Chat

from .. import callback_datas as calls


CHATS_PER_PAGE = 10


def chats_text(page: int):
    txt = textwrap.dedent(f"""
        <b>💬 Чаты</b>
        Страница <b>{page + 1}</b>, новые сверху:
    """)
    return txt


def chats_kb(chats: list[Chat], me_id: int | None, page: int = 0):
    rows = []
    for chat in chats:
        user = chat.interlocutor(me_id)
        name = (user.username if user else None) or "Starvell"
        unread = f"🔴 {chat.unread_message_count} ・ " if chat.unread_message_count else ""
        last = (chat.last_message.text if chat.last_message else "") or ("🖼" if chat.last_message and chat.last_message.images else "")
        last = last.replace("\n", " ")
        text = f"{unread}{name}: {last}"
        rows.append([InlineKeyboardButton(
            text=text[:60] + ("..." if len(text) > 60 else ""),
            callback_data=calls.ChatPage(id=chat.id).pack()
        )])

    buttons_row = [
        InlineKeyboardButton(text="←", callback_data=calls.ChatsPagination(page=page-1).pack()) if page > 0 else InlineKeyboardButton(text="🛑", callback_data="null_answer"),
        InlineKeyboardButton(text=f"📃 {page+1}", callback_data=calls.ChatsPagination(page=page).pack()),
        InlineKeyboardButton(text="→", callback_data=calls.ChatsPagination(page=page+1).pack()) if len(chats) >= CHATS_PER_PAGE else InlineKeyboardButton(text="🛑", callback_data="null_answer"),
    ]
    rows.append(buttons_row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def chats_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>💬 Чаты</b>
        \n{placeholder}
    """)
    return txt
