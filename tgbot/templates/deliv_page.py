import textwrap
from html import escape
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett
from svbot.deliveries import binding_title, offer_links, resolve_binding

from .. import callback_datas as calls


MAX_SHOWN_MESSAGE = 1000


def deliv_page_text(ref: str):
    _, deliv = resolve_binding(sett.get("auto_deliveries"), ref)
    
    enabled = "✅" if deliv.get("enabled", True) else "❌"
    piece = deliv.get("piece")
    piece_str = "Поштучно" if piece else "Сообщением"
    offers_frmtd = offer_links(deliv.get("offers"))

    if piece:
        part = f"<b>📦 Товары:</b> {len(deliv.get('goods') or [])} шт."
    else:
        message = "\n".join(deliv.get("message") or [])
        if len(message) > MAX_SHOWN_MESSAGE:
            message = message[:MAX_SHOWN_MESSAGE] + "..."
        part = f"<b>💬 Сообщение:</b> <blockquote>{escape(message) or '❌ Не задано'}</blockquote>"
    
    txt = textwrap.dedent(f"""
        <b>📄🚀 Страница авто-выдачи</b>

        <b>💡 Включено:</b> {enabled}
        <b>⚡ Тип выдачи:</b> {piece_str}
        <b>🛍️ Лоты:</b> {offers_frmtd}
    """) + "\n" + part
    return txt


def deliv_page_kb(ref: str, page: int = 0):
    _, deliv = resolve_binding(sett.get("auto_deliveries"), ref)
    
    enabled = "✅" if deliv.get("enabled", True) else "❌"
    piece = deliv.get("piece")
    piece_str = "Поштучно" if piece else "Сообщением"
    title = binding_title(deliv)
    title_frmtd = title[:32] + ("..." if len(title) > 32 else "")
    
    total_goods = len(deliv.get("goods") or [])
    message = " ".join(deliv.get("message") or []) or "❌ Не задано"
    message = message[:32] + ("..." if len(message) > 32 else "")
    
    rows = [
        [InlineKeyboardButton(text=f"💡 Включено: {enabled}", callback_data="switch_auto_delivery_enabled")],
        [InlineKeyboardButton(text=f"⚡ Тип выдачи: {piece_str}", callback_data="switch_auto_delivery_piece")],
        [InlineKeyboardButton(text=f"🛍️ Лоты: {title_frmtd}", callback_data="enter_auto_delivery_offers")],
        [
        InlineKeyboardButton(text=f"💬 Сообщение: {message}", callback_data="enter_auto_delivery_message")
        if not piece else InlineKeyboardButton(text=f"📦 Товары: {total_goods} шт. | 👈 Нажми для редактирования", callback_data=calls.DelivGoodsPagination(page=0).pack())
        ],
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data="confirm_deleting_auto_delivery")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.AutoDeliveriesPagination(page=page).pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def deliv_page_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>📄🚀 Страница авто-выдачи</b>
        \n{placeholder}
    """)
    return txt
