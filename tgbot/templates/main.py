import textwrap
from html import escape
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils import github_str_to_dt
from .. import callback_datas as calls


def error_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>❌ Ошибка</b>
        \n<blockquote>{placeholder}</blockquote>
    """)
    return txt


def back_kb(cb: str):
    rows = [[InlineKeyboardButton(text="⬅️ Назад", callback_data=cb)]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(confirm_cb: str, cancel_cb: str):
    rows = [[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_cb),
        InlineKeyboardButton(text="❌ Отменить", callback_data=cancel_cb)
    ]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def destroy_kb():
    rows = [[InlineKeyboardButton(text="❌ Закрыть", callback_data="destroy")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def new_release_text(release):
    tag = release["tag_name"]
    desc = release.get("body", "Без описания")
    url = release["html_url"]
    published_at = github_str_to_dt(
        release["published_at"]
    ).strftime("%d.%m.%Y %H:%M:%S")

    txt = textwrap.dedent(f"""
        <b>🚀 Доступна новая версия — <a href="{url}">{tag}</a></b>
        \n<b>💎 Изменения:</b>\n<blockquote>{desc}</blockquote>
        \n<b>📅 Дата выхода:</b> {published_at}
    """)
    return txt


def new_release_kb():
    rows = [
        [InlineKeyboardButton(text="⬇️ Установить", callback_data="install_update")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="destroy")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def new_sign_text(user):
    username = "@" + user.username.replace("@", "")
    txt = textwrap.dedent(f"""
        <b>🔑 Новая авторизация</b>

        Пользователь <b>{username}</b> только что авторизовался в боте
        
        ❗ <b>Если это были не Вы</b>, как можно скорее перейдите в раздел <b>«🔑 Авторизации»</b> в меню бота и удалите этого пользователя, а после смените пароль от Telegram бота
    """)
    return txt


def do_action_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>🧩 Действие</b>
        \n{placeholder}
    """)
    return txt


def log_text(title: str, text=""):
    txt = textwrap.dedent(f"""
        <b>{title}</b>
        \n{text}
    """)
    return txt


def sign_text(placeholder: str):
    return f"<b>🔐 Авторизация</b>\n\n{placeholder}"

def _site_row(chat_id: str | None = None, order_id: str | None = None):
    row = []
    if chat_id:
        row.append(InlineKeyboardButton(text="💬 Диалог", url=f"https://starvell.com/chat/{chat_id}"))
    if order_id:
        row.append(InlineKeyboardButton(text="📋 Заказ", url=f"https://starvell.com/order/{order_id}"))
    return row


def log_new_mess_kb(chat_id: str):
    rows = [
        [
        InlineKeyboardButton(text="✏️ Ответить", callback_data=calls.RememberChatId(id=chat_id, do="send_mess").pack()),
        InlineKeyboardButton(text="⚡ Быстрый ответ", callback_data=calls.RememberChatId(id=chat_id, do="send_fast_reply").pack())
        ],
        _site_row(chat_id),
        [InlineKeyboardButton(text="🚫 В ЧС", callback_data=calls.RememberChatId(id=chat_id, do="blacklist").pack())],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="destroy")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def log_new_order_kb(chat_id: str | None, order_id: str, completed: bool = False):
    rows = []
    if chat_id:
        rows.append([
            InlineKeyboardButton(text="✏️ Ответить", callback_data=calls.RememberChatId(id=chat_id, do="send_mess").pack()),
            InlineKeyboardButton(text="⚡ Быстрый ответ", callback_data=calls.RememberChatId(id=chat_id, do="send_fast_reply").pack())
        ])
    actions = [InlineKeyboardButton(text="📦 Возврат", callback_data=calls.RememberOrderId(id=order_id, do="refund").pack())]
    if not completed:
        actions.insert(0, InlineKeyboardButton(text="☑️ Выполнил", callback_data=calls.RememberOrderId(id=order_id, do="complete").pack()))
    rows.append(actions)
    rows.append(_site_row(chat_id, order_id))
    if chat_id:
        rows.append([InlineKeyboardButton(text="🚫 В ЧС", callback_data=calls.RememberChatId(id=chat_id, do="blacklist").pack())])
    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="destroy")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def log_order_kb(order_id: str, chat_id: str | None = None):
    rows = [_site_row(chat_id, order_id), [InlineKeyboardButton(text="❌ Закрыть", callback_data="destroy")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def log_blacklisted_order_kb(chat_id: str | None, order_id: str, username: str, refunded: bool = False):
    rows = []
    if not refunded:
        rows.append([InlineKeyboardButton(text="📦 Возврат", callback_data=calls.RememberOrderId(id=order_id, do="refund").pack())])
    rows.append(_site_row(chat_id, order_id))
    if chat_id:
        rows.append([InlineKeyboardButton(text="✅ Убрать из ЧС", callback_data=calls.RememberChatId(id=chat_id, do="unblacklist").pack())])
    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="destroy")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def log_offer_kb(public_id: str):
    rows = [
        [InlineKeyboardButton(text="🛍 Лот", url=f"https://starvell.com/offers/edit/{public_id}")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="destroy")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def call_seller_text(username: str, chat_id: str):
    txt = textwrap.dedent(f"""
        ❗ <b>{escape(username)}</b> вызывает вас в <a href="https://starvell.com/chat/{chat_id}">чат</a>
    """)
    return txt


def call_seller_kb(chat_id: str):
    rows = [
        [InlineKeyboardButton(text="✏️ Ответить", callback_data=calls.RememberChatId(id=chat_id, do="send_mess").pack())],
        [InlineKeyboardButton(text="💬 Перейти в диалог", url=f"https://starvell.com/chat/{chat_id}")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="destroy")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
