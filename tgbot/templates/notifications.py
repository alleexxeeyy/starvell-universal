import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


NOTIFICATION_EVENTS = [
    ("new_user_message", "Новое сообщение"),
    ("new_system_message", "Системное сообщение"),
    ("moderation", "Сообщение модерации"),
    ("new_order", "Новый заказ"),
    ("order_status_changed", "Статус заказа изменился"),
    ("new_review", "Новый отзыв"),
    ("out_of_stock", "Проблемы авто-выдачи"),
    ("balance_updated", "Баланс изменился"),
    ("connection", "Проблемы соединения"),
]


def notifications_text():
    config = sett.get("config")
    
    enabled = "✅" if config["starvell"]["notifications"]["enabled"] else "❌"
    chat_id = config["starvell"]["notifications"]["chat_id"] or "Текущий"
    events = config["starvell"]["notifications"]["events"] or {}
    events_frmtd = "\n".join(f"{'🟢' if events.get(key) else '🔴'} {name}" for key, name in NOTIFICATION_EVENTS)
    
    txt = textwrap.dedent(f"""
        <b>🔔 Уведомления</b>

        <b>💡 Включено:</b> {enabled}
        <b>💬 Чат:</b> {chat_id}
    """) + "\n" + events_frmtd
    return txt


def notifications_kb():
    config = sett.get("config")
    
    enabled = "✅" if config["starvell"]["notifications"]["enabled"] else "❌"
    chat_id = config["starvell"]["notifications"]["chat_id"] or "Текущий"
    events = config["starvell"]["notifications"]["events"] or {}
    
    rows = [
        [InlineKeyboardButton(text=f"💡 Включено: {enabled}", callback_data="switch_notifications_enabled")],
        [InlineKeyboardButton(text=f"💬 Чат: {chat_id}", callback_data="enter_notifications_chat_id")],
    ]
    for key, name in NOTIFICATION_EVENTS:
        rows.append([InlineKeyboardButton(
            text=f"{'🟢' if events.get(key) else '🔴'} {name}",
            callback_data=calls.SwitchNotificationEvent(key=key).pack()
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())])
    
    if config["starvell"]["notifications"]["chat_id"]:
        rows[1].append(InlineKeyboardButton(text=f"❌ Очистить", callback_data="clean_notifications_chat_id"))
    
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def notifications_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>🔔 Уведомления</b>
        \n{placeholder}
    """)
    return txt