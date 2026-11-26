import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls
    

def other_text():
    config = sett.get("config")
    
    read_chat = "✅" if config["starvell"]["read_chat"] else "❌"
    review_replies = "✅" if config["starvell"]["auto_review_replies"] else "❌"
    watermark_enabled = "✅" if config["starvell"]["watermark"]["enabled"] else "❌"
    watermark_value = config["starvell"]["watermark"]["value"] or "❌ Не задано"
    
    txt = textwrap.dedent(f"""
        <b>🔧 Прочее</b>

        <b>👀 Чтение чата:</b> {read_chat}
        <blockquote><b>(?)</b> Будет помечать чат как прочитанный перед тем, как отправить сообщение.</blockquote>

        <b>⭐ Автоответ на отзывы:</b> {review_replies}
        <blockquote><b>(?)</b> На каждый новый отзыв бот ответит сообщением «⭐ Ответ на отзыв» из раздела «💬 Сообщения». Ответ виден всем на странице профиля.</blockquote>

        <b>©️ Водяной знак:</b> {watermark_enabled}
        <b>🏷️©️ Значение:</b> {watermark_value}
    """)
    return txt


def other_kb():
    config = sett.get("config")
    
    read_chat = "✅" if config["starvell"]["read_chat"] else "❌"
    review_replies = "✅" if config["starvell"]["auto_review_replies"] else "❌"
    watermark_enabled = "✅" if config["starvell"]["watermark"]["enabled"] else "❌"
    watermark_value = config["starvell"]["watermark"]["value"] or "❌ Не задано"
    
    rows = [
        [InlineKeyboardButton(text=f"👀 Чтение чата: {read_chat}", callback_data="switch_read_chat_enabled")],
        [InlineKeyboardButton(text=f"⭐ Автоответ на отзывы: {review_replies}", callback_data="switch_auto_review_replies")],
        [InlineKeyboardButton(text=f"©️ Водяной знак: {watermark_enabled}", callback_data="switch_watermark_enabled")],
        [InlineKeyboardButton(text=f"🏷️©️ Значение: {watermark_value}", callback_data="enter_watermark_value")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def other_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>🔧 Прочее</b>
        \n{placeholder}
    """)
    return txt