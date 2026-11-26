import textwrap
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import Settings as sett

from .. import callback_datas as calls


def complete_text():
    config = sett.get("config")
    
    enabled = "✅" if config["starvell"]["auto_complete_orders"]["enabled"] else "❌"
    all = "Всех лотов" if config["starvell"]["auto_complete_orders"]["all"] else "Указанных лотов"
    
    auto_complete_orders = sett.get("auto_complete_orders")
    included = len(auto_complete_orders["included"])
    excluded = len(auto_complete_orders["excluded"])
    
    txt = textwrap.dedent(f"""
        <b>☑️ Авто-подтверждение</b>
        <blockquote><b>(?)</b> После авто-выдачи бот сам отметит заказ выполненным. Окончательно заказ закрывает покупатель.</blockquote>

        <b>💡 Включено:</b> {enabled}
        <b>📦 Подтверждать заказы:</b> {all}
        <blockquote><b>(?)</b> "Всех лотов" - подтверждаются заказы всех лотов с авто-выдачей, кроме исключённых. "Указанных лотов" - только тех, что добавлены во включённые.</blockquote>

        <b>➕ Включённые:</b> {included}
        <b>➖ Исключённые:</b> {excluded}
    """)
    return txt


def complete_kb():
    config = sett.get("config")
    
    enabled = "✅" if config["starvell"]["auto_complete_orders"]["enabled"] else "❌"
    all = "Всех лотов" if config["starvell"]["auto_complete_orders"]["all"] else "Указанных лотов"
    
    auto_complete_orders = sett.get("auto_complete_orders")
    included = len(auto_complete_orders["included"])
    excluded = len(auto_complete_orders["excluded"])
    
    rows = [
        [InlineKeyboardButton(text=f"💡 Включено: {enabled}", callback_data="switch_auto_complete_orders_enabled")],
        [InlineKeyboardButton(text=f"📦 Подтверждать заказы: {all}", callback_data="switch_auto_complete_orders_all")],
        [
        InlineKeyboardButton(text=f"➕ Включённые: {included}", callback_data=calls.IncludedCompleteOrdersPagination(page=0).pack()),
        InlineKeyboardButton(text=f"➖ Исключённые: {excluded}", callback_data=calls.ExcludedCompleteOrdersPagination(page=0).pack())
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=calls.MenuNavigation(to="default").pack())]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    return kb


def complete_float_text(placeholder: str):
    txt = textwrap.dedent(f"""
        <b>☑️ Авто-подтверждение</b>
        \n{placeholder}
    """)
    return txt
