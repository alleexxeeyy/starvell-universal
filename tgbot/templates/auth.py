import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def auth_text():
    config = sett.get("config")
    
    session = config["starvell"]["api"]["session"]
    session = session[:6] + ("*" * 10) if session else "❌ Не задано"
    user_agent = config["starvell"]["api"]["user_agent"] or "❌ Не задано"
    
    txt = textwrap.dedent(f"""
        <b>🔒 Авторизация</b>

        <b>🍪 Session:</b> {session}
        <b>🎩 User Agent:</b> {user_agent}
    """)
    return txt


def auth_kb():
    config = sett.get("config")
    
    session = config["starvell"]["api"]["session"]
    session = session[:6] + ("*" * 10) if session else "❌ Не задано"
    user_agent = config["starvell"]["api"]["user_agent"] or "❌ Не задано"
    
    rows = [
        [InlineKeyboardButton(text=f"🍪 Session: {session}", callback_data="enter_session")],
        [InlineKeyboardButton(text=f"🎩 User Agent: {user_agent}", callback_data="enter_user_agent")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def auth_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>🔒 Авторизация</b>
        \n{placeholder}
    """)
    return txt