import textwrap
from html import escape
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from starvellapi.models import Chat, Message, NotificationType
from svbot.msg_types import fmt_date

from .. import callback_datas as calls


_NOTIFICATIONS = {
    NotificationType.ORDER_PAYMENT: "Заказ оплачен",
    NotificationType.ORDER_SELLER_COMPLETED: "Продавец выполнил заказ",
    NotificationType.ORDER_REFUND: "Оформлен возврат",
    NotificationType.ORDER_NOT_PAID_REMINDER: "Напоминание об оплате",
}

MAX_CHAT_TEXT = 3800
MAX_MESSAGE_TEXT = 700


def _message_text(msg: Message) -> str:
    if msg.is_notification:
        title = _NOTIFICATIONS.get(msg.notification_type, str(msg.notification_type or "Уведомление"))
        short_id = msg.order.short_id if msg.order else (msg.metadata.order_short_id if msg.metadata else None)
        order_id = msg.order_id
        label = f"*{title}{' ' + short_id if short_id else ''}*"
        return f'<a href="https://starvell.com/order/{order_id}"><i>{escape(label)}</i></a>' if order_id else f"<i>{escape(label)}</i>"
    raw = msg.text or ""
    text = escape(raw[:MAX_MESSAGE_TEXT] + ("..." if len(raw) > MAX_MESSAGE_TEXT else ""))
    if msg.images:
        text = f"<i>*Изображений: {len(msg.images)}*</i>" + (f" {text}" if text else "")
    return text or "<i>*Без сообщения*</i>"


def chat_text(chat: Chat, msgs: list[Message], me_id: int | None):
    user = chat.interlocutor(me_id)
    chat_name = f"👤 {escape(user.username)}" if user and user.username else "🔔 Starvell"

    parts = []
    for msg in msgs:
        if msg.author_id == me_id and me_id is not None:
            author = "Вы"
        elif msg.author and msg.author.username:
            author = escape(msg.author.username)
        else:
            author = "Starvell"
        parts.append(f"<b>{author}:</b> <i>{fmt_date(msg.created_at)}</i> <blockquote>{_message_text(msg)}</blockquote>")

    # телеграм режет сообщения длиннее 4096 символов - оставляем последние
    body = ""
    for part in reversed(parts):
        if len(body) + len(part) > MAX_CHAT_TEXT:
            break
        body = part + "\n" + body
    refund = "\n⚠️ <b>Покупатель запросил возврат</b>" if chat.has_active_refund_request else ""

    txt = textwrap.dedent(f"""
        <b>💬 {chat_name}</b>{refund}
    """) + "\n" + (body or "<i>Сообщений нет</i>")
    return txt


def chat_kb(chat_id: str):
    rows = [
        [
        InlineKeyboardButton(text="✏️ Ответить", callback_data="enter_chat_answer_message"),
        InlineKeyboardButton(text="⚡ Быстрый ответ", callback_data=calls.SelFastReplyPagination(id=chat_id, page=0).pack()),
        ],
        [
        InlineKeyboardButton(text="👀 Прочитать", callback_data="read_chat"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data=calls.ChatPage(id=chat_id).pack()),
        ],
        [InlineKeyboardButton(text="🌐 На сайте", url=f"https://starvell.com/chat/{chat_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_chats")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def chat_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>💬 Чат</b>
        \n{placeholder}
    """)
    return txt
