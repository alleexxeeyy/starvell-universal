import math
import time
import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett
from data import Data as data

from .. import callback_datas as calls


def _bump_categories() -> dict:
    from svbot.starvellbot import get_starvell_bot
    svbot = get_starvell_bot()
    if svbot is not None:
        return dict(svbot.bump_categories)
    return data.get("bump_categories") or {}


def _left(next_time: float) -> str:
    left = int(next_time - time.time())
    if left <= 0:
        return "сейчас"
    hours, minutes = left // 3600, left % 3600 // 60
    return f"{hours} ч. {minutes} мин." if hours else f"{max(minutes, 1)} мин."


def bump_text():
    config = sett.get("config")
    enabled = "✅" if config["starvell"]["auto_bump_offers"]["enabled"] else "❌"
    categories = _bump_categories()
    disabled = sum(1 for c in categories.values() if c.get("disabled"))
    disabled_frmtd = f" (и {disabled} выключено)" if disabled else ""
    
    txt = textwrap.dedent(f"""
        <b>⬆️ Авто-поднятие</b>
        <blockquote><b>(?)</b> Бот поднимает ваши лоты по категориям, как только Starvell это разрешает (обычно раз в 4 часа). Категории бот находит сам по заказам и авто-выдаче, можно добавить и по ссылке на лот.</blockquote>

        <b>💡 Включено:</b> {enabled}
        <b>📂 Категорий:</b> {len(categories) - disabled}{disabled_frmtd}
    """)
    return txt


def bump_kb(page=0):
    config = sett.get("config")
    enabled = "✅" if config["starvell"]["auto_bump_offers"]["enabled"] else "❌"
    categories = sorted(_bump_categories().values(), key=lambda c: (bool(c.get("disabled")), c.get("next_time", 0)))
    
    rows = [[InlineKeyboardButton(text=f"💡 Включено: {enabled}", callback_data="switch_auto_bump_offers_enabled")]]

    items_per_page = 8
    total_pages = math.ceil(len(categories) / items_per_page)
    total_pages = total_pages if total_pages > 0 else 1

    if page < 0: page = 0
    elif page >= total_pages: page = total_pages - 1

    start_offset = page * items_per_page
    end_offset = start_offset + items_per_page

    for cat in categories[start_offset:end_offset]:
        title = str(cat.get("title") or f"{cat['game_id']}:{cat['category_id']}")
        title_frmtd = title[:28] + ("..." if len(title) > 28 else "")
        disabled = cat.get("disabled")
        status = "выключена" if disabled else "нет лотов" if cat.get("empty") else _left(cat.get("next_time", 0))
        rows.append([
            InlineKeyboardButton(text=f"{'⏸ ' if disabled else ''}{title_frmtd} ・ {status}", callback_data="null_answer"),
            InlineKeyboardButton(text="▶️" if disabled else "⏸", callback_data=calls.DeleteBumpCategory(game=cat["game_id"], cat=cat["category_id"]).pack()),
        ])

    if total_pages > 1:
        buttons_row = []
        btn_back = InlineKeyboardButton(text="←", callback_data=calls.BumpCategoriesPagination(page=page-1).pack()) if page > 0 else InlineKeyboardButton(text="🛑", callback_data="null_answer")
        buttons_row.append(btn_back)

        btn_pages = InlineKeyboardButton(text=f"📃 {page+1}/{total_pages}", callback_data=calls.PageEnter(to="bump_categories", page=page, total=total_pages).pack())
        buttons_row.append(btn_pages)

        btn_next = InlineKeyboardButton(text="→", callback_data=calls.BumpCategoriesPagination(page=page+1).pack()) if page < total_pages - 1 else InlineKeyboardButton(text="🛑", callback_data="null_answer")
        buttons_row.append(btn_next)
        rows.append(buttons_row)

    rows.append([
        InlineKeyboardButton(text="➕ По ссылке на лот", callback_data="enter_bump_offer"),
        InlineKeyboardButton(text="🔍 Найти по заказам", callback_data="discover_bump_categories"),
    ])
    rows.append([InlineKeyboardButton(text="⬆️ Поднять сейчас", callback_data="bump_offers_now")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())])

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def bump_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>⬆️ Авто-поднятие</b>
        \n{placeholder}
    """)
    return txt
