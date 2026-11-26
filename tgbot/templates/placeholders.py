import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from __init__ import VERSION

from .. import callback_datas as calls


def plholders_text(to):
    if to == "account":
        txt = textwrap.dedent("""
            <b>🏷️ Заменители</b>
            
            <b>👤 Аккаунт</b> (<code>account</code>):

            ・ <code>{account.id}</code> — ID аккаунта
            ・ <code>{account.username}</code> — Никнейм аккаунта
            ・ <code>{account.balance}</code> — Баланс аккаунта (₽)
            ・ <code>{account.rating}</code> — Рейтинг аккаунта
            ・ <code>{account.reviews_count}</code> — Количество отзывов

            <i>Доступны во всех сообщениях и командах</i>
        """)
    elif to == "user":
        txt = textwrap.dedent("""
            <b>🏷️ Заменители</b>
            
            <b>👤 Собеседник</b> (<code>user</code>):

            ・ <code>{user.id}</code> — ID пользователя
            ・ <code>{user.username}</code> — Никнейм пользователя

            <i>Доступны во всех сообщениях и командах, кроме сообщений о статусе заказа</i>
        """)
    elif to == "chat":
        txt = textwrap.dedent("""
            <b>🏷️ Заменители</b>
            
            <b>💬 Чат</b> (<code>chat</code>):

            ・ <code>{chat.id}</code> — ID чата
            ・ <code>{chat.link}</code> — Ссылка на чат

            <i>Доступны в приветствии, командах, вызове продавца, сообщениях о заказе и авто-выдаче</i>
        """)
    elif to == "order":
        txt = textwrap.dedent("""
            <b>🏷️ Заменители</b>
            
            <b>📋 Заказ</b> (<code>order</code>):

            ・ <code>{order.id}</code> — ID заказа
            ・ <code>{order.short_id}</code> — Короткий номер заказа (как на сайте)
            ・ <code>{order.title}</code> — Название лота
            ・ <code>{order.quantity}</code> — Количество
            ・ <code>{order.price}</code> — Сумма, которую заплатил покупатель (₽)
            ・ <code>{order.base_price}</code> — Сумма, которую получите вы (₽)
            ・ <code>{order.status}</code> — Статус заказа
            ・ <code>{order.link}</code> — Ссылка на заказ
            ・ <code>{order.date}</code> — Дата оплаты

            <i>Доступны в сообщениях о заказах, ответе на отзыв и авто-выдаче</i>
        """)

    return txt


def plholders_kb(to, by, last_page=0):
    sym1 = "・" if to == "account" else ""
    sym2 = "・" if to == "user" else ""
    sym3 = "・" if to == "chat" else ""
    sym4 = "・" if to == "order" else ""

    if by == "mess":
        cb = calls.MessagesPagination(page=last_page).pack()
    else:
        cb = calls.CustomCommandsPagination(page=last_page).pack()

    if by == "mess":
        rows = [
            [
            InlineKeyboardButton(text=f"{sym1} 👤 Аккаунт {sym1}", callback_data=calls.PlaceholdersNavigation(to="account", by=by).pack()),
            InlineKeyboardButton(text=f"{sym2} 👤 Собеседник {sym2}", callback_data=calls.PlaceholdersNavigation(to="user", by=by).pack())
            ],
            [
            InlineKeyboardButton(text=f"{sym3} 💬 Чат {sym3}", callback_data=calls.PlaceholdersNavigation(to="chat", by=by).pack()),
            InlineKeyboardButton(text=f"{sym4} 📋 Заказ {sym4}", callback_data=calls.PlaceholdersNavigation(to="order", by=by).pack())
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=cb)],
        ]
    else:
        rows = [
            [
            InlineKeyboardButton(text=f"{sym1} 👤 Аккаунт {sym1}", callback_data=calls.PlaceholdersNavigation(to="account", by=by).pack()),
            InlineKeyboardButton(text=f"{sym2} 👤 Собеседник {sym2}", callback_data=calls.PlaceholdersNavigation(to="user", by=by).pack())
            ],
            [InlineKeyboardButton(text=f"{sym3} 💬 Чат {sym3}", callback_data=calls.PlaceholdersNavigation(to="chat", by=by).pack())],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=cb)],
        ]

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb